"""Cervello di Elyca: backend LLM selezionabile da config, cronologia breve,
chiamate in un thread separato (la UI non si blocca mai)."""
from __future__ import annotations

import logging
import threading
from collections import deque

from PySide6.QtCore import QObject, Signal

from brain.base import Backend, BrainError
from i18n import t

log = logging.getLogger(__name__)


def make_backend(cfg: dict) -> Backend:
    name = str(cfg["backend"]).lower()
    if name == "anthropic":
        from brain.anthropic_backend import AnthropicBackend
        return AnthropicBackend(cfg)
    if name != "ollama":
        log.warning("Backend sconosciuto %r: uso ollama", name)
    from brain.ollama_backend import OllamaBackend
    return OllamaBackend(cfg)


class Brain(QObject):
    """Gestisce domanda -> risposta in streaming su un thread di lavoro.

    I segnali arrivano nel thread della UI (connessione in coda automatica).
    Ogni richiesta ha un id: le risposte di richieste superate vengono ignorate.
    """

    chunk = Signal(int, str)      # (id richiesta, pezzo di testo)
    status = Signal(int, str)     # (id richiesta, messaggio di stato, es. download del modello)
    finished = Signal(int, str)   # (id richiesta, testo completo)
    failed = Signal(int, str)     # (id richiesta, messaggio d'errore per l'utente)

    def __init__(self, cfg: dict, backend: Backend | None = None) -> None:
        super().__init__()
        self.system = cfg["system_prompt"]
        self.backend = backend or make_backend(cfg)
        self.history: deque[tuple[str, str]] = deque(maxlen=max(0, int(cfg["history_turns"])))
        self._lock = threading.Lock()
        self._next_id = 0
        self._cancel: threading.Event | None = None
        log.info("Cervello: backend %s", self.backend.name)

    def ask(self, question: str) -> int:
        """Avvia una richiesta e ne ritorna l'id. Annulla quella precedente, se in corso."""
        self.cancel()
        with self._lock:
            self._next_id += 1
            req_id = self._next_id
            cancel = self._cancel = threading.Event()
            messages: list[dict] = []
            for q, a in self.history:
                messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": question})
        threading.Thread(target=self._run, args=(req_id, question, messages, cancel),
                         name=f"brain-{req_id}", daemon=True).start()
        return req_id

    def cancel(self) -> None:
        with self._lock:
            if self._cancel is not None:
                self._cancel.set()
                self._cancel = None

    def clear_history(self) -> None:
        with self._lock:
            self.history.clear()

    def _run(self, req_id: int, question: str, messages: list[dict], cancel: threading.Event) -> None:
        parts: list[str] = []
        self.backend.status_callback = lambda msg: None if cancel.is_set() else self.status.emit(req_id, msg)
        try:
            for text in self.backend.stream_reply(self.system, messages, cancel):
                if cancel.is_set():
                    return
                parts.append(text)
                self.chunk.emit(req_id, text)
        except BrainError as e:
            if not cancel.is_set():
                self.failed.emit(req_id, str(e))
            return
        except Exception:
            log.exception("Errore inatteso nel backend")
            if not cancel.is_set():
                self.failed.emit(req_id, t("brain_generic_error"))
            return
        if cancel.is_set():
            return
        answer = "".join(parts).strip()
        if not answer:
            self.failed.emit(req_id, t("brain_empty"))
            return
        with self._lock:
            self.history.append((question, answer))
        self.finished.emit(req_id, answer)
