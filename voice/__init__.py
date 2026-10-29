"""Voce di Elyca: dettatura push-to-talk (faster-whisper) e lettura delle risposte (pyttsx3).

Le librerie pesanti vengono importate solo quando servono: se la voce è disattivata
in config, l'app non le carica nemmeno.
"""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Signal

from i18n import t

log = logging.getLogger(__name__)

MIN_AUDIO_S = 0.4


class Voice(QObject):
    transcribed = Signal(str)        # testo dettato (può essere vuoto se non ha capito)
    failed = Signal(str)             # messaggio d'errore per l'utente
    status = Signal(str)             # avvisi (es. caricamento del modello)
    speaking_changed = Signal(bool)

    def __init__(self, cfg: dict) -> None:
        super().__init__()
        self.cfg = cfg
        self.enabled = bool(cfg["enabled"])
        self.tts_enabled = bool(cfg["tts_enabled"])
        self._recorder = None
        self._stt = None
        self._stt_lock = threading.Lock()
        self._tts = None

    # ------------------------------------------------------------------ dettatura
    @property
    def recording(self) -> bool:
        return self._recorder is not None

    @property
    def recording_full(self) -> bool:
        return self._recorder is not None and self._recorder.full

    def start_recording(self) -> bool:
        if self._recorder is not None:
            return True
        try:
            from voice.recorder import Recorder
            rec = Recorder(float(self.cfg["max_record_s"]))
            rec.start()
        except Exception as e:
            log.exception("Microfono non disponibile")
            self.failed.emit(t("mic_unavailable", err=e.__class__.__name__))
            return False
        self._recorder = rec
        log.info("Registrazione avviata")
        return True

    def stop_recording(self) -> bool:
        """Ferma la registrazione e avvia la trascrizione. Ritorna False se non c'era audio utile."""
        rec, self._recorder = self._recorder, None
        if rec is None:
            return False
        try:
            audio = rec.stop()
        except Exception:
            log.exception("Errore fermando la registrazione")
            self.failed.emit(t("rec_failed"))
            return False
        seconds = audio.size / 16000
        log.info("Registrazione finita: %.1f s", seconds)
        if seconds < MIN_AUDIO_S:
            self.failed.emit(t("ptt_too_short"))
            return False
        threading.Thread(target=self._transcribe, args=(audio,), name="stt", daemon=True).start()
        return True

    def _transcribe(self, audio) -> None:
        try:
            with self._stt_lock:
                if self._stt is None:
                    self.status.emit(t("stt_loading"))
                    from voice.stt import SpeechToText
                    self._stt = SpeechToText(self.cfg)
            text = self._stt.transcribe(audio)
        except Exception:
            log.exception("Trascrizione non riuscita")
            self.failed.emit(t("stt_failed"))
            return
        self.transcribed.emit(text)

    # ------------------------------------------------------------------ lettura
    def speak(self, text: str) -> None:
        if not (self.enabled and self.tts_enabled):
            return
        if self._tts is None:
            from voice.tts import TextToSpeech
            self._tts = TextToSpeech(self.cfg, self.speaking_changed.emit)
        self._tts.speak(text)

    def stop_speaking(self) -> None:
        if self._tts is not None:
            self._tts.stop()
