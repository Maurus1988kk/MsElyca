"""Registrazione dal microfono (16 kHz mono float32, il formato che vuole Whisper)."""
from __future__ import annotations

import logging
import threading

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

TARGET_RATE = 16000


class Recorder:
    def __init__(self, max_seconds: float) -> None:
        self.max_seconds = max_seconds
        self._chunks: list[np.ndarray] = []
        self._frames = 0
        self._rate = TARGET_RATE
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self._chunks, self._frames = [], 0
        try:
            self._open(TARGET_RATE)
        except sd.PortAudioError:
            # alcuni microfoni non accettano 16 kHz: registriamo al loro rate e ricampioniamo
            rate = int(sd.query_devices(kind="input")["default_samplerate"])
            log.info("Il microfono non supporta 16 kHz, registro a %d Hz", rate)
            self._open(rate)

    def _open(self, rate: int) -> None:
        self._rate = rate
        self._stream = sd.InputStream(samplerate=rate, channels=1, dtype="float32", callback=self._callback)
        self._stream.start()

    def _callback(self, indata, frames, _time, status) -> None:
        if status:
            log.debug("Audio: %s", status)
        with self._lock:
            if self._frames < self.max_seconds * self._rate:
                self._chunks.append(indata[:, 0].copy())
                self._frames += frames

    @property
    def full(self) -> bool:
        return self._frames >= self.max_seconds * self._rate

    def stop(self) -> np.ndarray:
        """Ferma la registrazione e ritorna l'audio a 16 kHz."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        with self._lock:
            audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, dtype=np.float32)
            self._chunks = []
        if self._rate != TARGET_RATE and audio.size:
            n = int(audio.size * TARGET_RATE / self._rate)
            audio = np.interp(np.linspace(0, audio.size - 1, n), np.arange(audio.size), audio).astype(np.float32)
        return audio
