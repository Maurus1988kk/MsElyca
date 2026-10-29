"""Dettatura con faster-whisper su CPU."""
from __future__ import annotations

import logging
import os
import time

import numpy as np

from config import BASE_DIR

log = logging.getLogger(__name__)

MODELS_DIR = BASE_DIR / "models"
# su Windows senza "modalità sviluppatore" Hugging Face avvisa che non può usare i symlink: è innocuo
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


class SpeechToText:
    def __init__(self, cfg: dict) -> None:
        from faster_whisper import WhisperModel  # import pesante: solo al primo uso

        t0 = time.time()
        name = cfg["whisper_model"]
        # al primo uso il modello viene scaricato in models/ (small ≈ 0,5 GB, medium ≈ 1,5 GB)
        self.model = WhisperModel(name, device="cpu", compute_type=cfg["whisper_compute_type"],
                                  download_root=str(MODELS_DIR))
        language = str(cfg["whisper_language"]).lower()
        if language == "auto":
            from i18n import lang
            language = lang()
        self.language = language or None  # "" = riconoscimento automatico di Whisper
        log.info("Modello Whisper '%s' pronto in %.1f s", name, time.time() - t0)

    def transcribe(self, audio: np.ndarray) -> str:
        t0 = time.time()
        segments, info = self.model.transcribe(audio, language=self.language, beam_size=1, vad_filter=True)
        text = " ".join(s.text.strip() for s in segments).strip()
        log.info("Trascritti %.1f s di audio in %.1f s (lingua %s)", audio.size / 16000,
                 time.time() - t0, info.language)
        return text
