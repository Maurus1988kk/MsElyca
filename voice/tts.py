"""Lettura ad alta voce con pyttsx3 (voci SAPI di Windows), in un thread dedicato.

pyttsx3 non è thread-safe: il motore vive tutto in un solo thread di lavoro.
Il testo viene letto frase per frase, così si può interrompere tra una frase e l'altra.
"""
from __future__ import annotations

import logging
import queue
import re
import threading
from collections.abc import Callable

log = logging.getLogger(__name__)

_ITALIAN_HINTS = ("italian", "ital", "it-it", "it_it", "elsa", "cosimo", "isabella", "diego")
_ENGLISH_HINTS = ("english", "en-us", "en-gb", "en_us", "en_gb", "zira", "david", "hazel", "mark")


def _clean(text: str) -> str:
    text = re.sub(r"[*_`#>|~]+", " ", text)                  # simboli Markdown
    text = re.sub(r"https?://\S+", " link ", text)            # niente URL lette lettera per lettera
    text = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", " ", text)  # emoji
    return re.sub(r"\s+", " ", text).strip()


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?…;:])\s+", text) if s.strip()]


class TextToSpeech:
    def __init__(self, cfg: dict, on_speaking: Callable[[bool], None]) -> None:
        self.cfg = cfg
        self.on_speaking = on_speaking
        self._queue: queue.Queue[tuple[int, str]] = queue.Queue()
        self._generation = 0
        self._thread: threading.Thread | None = None

    def speak(self, text: str) -> None:
        text = _clean(text)
        if not text:
            return
        if self._thread is None:
            self._thread = threading.Thread(target=self._worker, name="tts", daemon=True)
            self._thread.start()
        self._generation += 1
        self._queue.put((self._generation, text))

    def stop(self) -> None:
        """Interrompe la lettura (alla fine della frase in corso)."""
        self._generation += 1

    # ------------------------------------------------------------------ thread
    def _worker(self) -> None:
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass
        try:
            import pyttsx3
            engine = pyttsx3.init()
            self._configure(engine)
        except Exception:
            log.exception("Impossibile inizializzare la sintesi vocale")
            return
        while True:
            gen, text = self._queue.get()
            if gen != self._generation:
                continue
            self.on_speaking(True)
            try:
                for sentence in _sentences(text):
                    if gen != self._generation:
                        break
                    engine.say(sentence)
                    engine.runAndWait()
            except Exception:
                log.exception("Errore durante la lettura")
            finally:
                if self._queue.empty():
                    self.on_speaking(False)

    def _configure(self, engine) -> None:
        engine.setProperty("rate", int(self.cfg["tts_rate"]))
        wanted = str(self.cfg["tts_voice"]).lower().strip()
        voices = engine.getProperty("voices") or []
        log.info("Voci disponibili: %s", ", ".join(v.name for v in voices))

        def text_of(v) -> str:
            langs = " ".join(str(x) for x in (getattr(v, "languages", None) or []))
            return f"{v.name} {v.id} {langs}".lower()

        chosen = None
        if wanted:
            chosen = next((v for v in voices if wanted in text_of(v)), None)
        if chosen is None:
            from i18n import lang
            hints = _ITALIAN_HINTS if lang() == "it" else _ENGLISH_HINTS
            chosen = next((v for v in voices if any(h in text_of(v) for h in hints)), None)
        if chosen is not None:
            engine.setProperty("voice", chosen.id)
            log.info("Voce scelta: %s", chosen.name)
        else:
            log.warning("Nessuna voce nella lingua dell'interfaccia: uso la voce predefinita di Windows")
