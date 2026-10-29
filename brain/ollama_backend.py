"""Backend Ollama in locale (API HTTP /api/chat, risposta in streaming NDJSON).

Se il modello non è ancora presente lo scarica da solo (/api/pull) mostrando l'avanzamento,
così chi installa Elyca non deve usare la riga di comando.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator

from brain.base import Backend, BrainError
from i18n import t

log = logging.getLogger(__name__)


class OllamaBackend(Backend):
    name = "ollama"

    def __init__(self, cfg: dict) -> None:
        self.model = cfg["ollama_model"]
        self.base = cfg["ollama_url"].rstrip("/")
        self.timeout = float(cfg["timeout_s"])
        self.auto_pull = bool(cfg.get("ollama_auto_pull", True))

    # ------------------------------------------------------------------ HTTP
    def _post(self, path: str, payload: dict):
        req = urllib.request.Request(self.base + path, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            log.error("Ollama HTTP %s su %s: %s", e.code, path, detail)
            if e.code == 404 and "not found" in detail.lower():
                raise _ModelMissing() from None
            raise BrainError(t("ollama_http", code=e.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            log.error("Ollama non raggiungibile su %s: %s", self.base, e)
            raise BrainError(t("ollama_not_running")) from None

    @staticmethod
    def _lines(resp, cancel: threading.Event) -> Iterator[dict]:
        with resp:
            try:
                for raw in resp:
                    if cancel.is_set():
                        return
                    line = raw.strip()
                    if line:
                        data = json.loads(line)
                        if "error" in data:
                            log.error("Ollama: %s", data["error"])
                            raise BrainError(t("ollama_error", msg=data["error"]))
                        yield data
            except (TimeoutError, OSError) as e:
                log.error("Ollama interrotto: %s", e)
                raise BrainError(t("ollama_interrupted")) from None

    # ------------------------------------------------------------------ chat
    def stream_reply(self, system: str, messages: list[dict], cancel: threading.Event) -> Iterator[str]:
        payload = {"model": self.model, "stream": True,
                   "messages": [{"role": "system", "content": system}, *messages]}
        try:
            resp = self._post("/api/chat", payload)
        except _ModelMissing:
            if not self.auto_pull:
                raise BrainError(t("ollama_pull_failed", model=self.model)) from None
            self._pull(cancel)
            if cancel.is_set():
                return
            try:
                resp = self._post("/api/chat", payload)
            except _ModelMissing:
                raise BrainError(t("ollama_pull_failed", model=self.model)) from None

        for data in self._lines(resp, cancel):
            chunk = data.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            if data.get("done"):
                break

    # ------------------------------------------------------------------ download del modello
    def _pull(self, cancel: threading.Event) -> None:
        log.info("Modello %s assente: lo scarico", self.model)
        self.report_status(t("ollama_pulling", model=self.model, progress=""))
        try:
            resp = self._post("/api/pull", {"model": self.model, "stream": True})
        except _ModelMissing:
            raise BrainError(t("ollama_pull_failed", model=self.model)) from None
        last = 0.0
        ok = False
        for data in self._lines(resp, cancel):
            status = data.get("status", "")
            total, done = data.get("total"), data.get("completed")
            if total and done is not None and time.time() - last > 0.5:
                last = time.time()
                pct = int(done * 100 / total)
                self.report_status(t("ollama_pulling", model=self.model,
                                     progress=f"{pct}% ({done / 1e9:.1f}/{total / 1e9:.1f} GB)"))
            if status == "success":
                ok = True
        if not ok and not cancel.is_set():
            raise BrainError(t("ollama_pull_failed", model=self.model))
        log.info("Modello %s scaricato", self.model)


class _ModelMissing(Exception):
    pass
