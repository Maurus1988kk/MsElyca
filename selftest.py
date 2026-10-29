"""Autodiagnosi: Elyca.exe --selftest (o python main.py --selftest).

Controlla, senza aprire finestre, che le librerie e i componenti necessari siano presenti
e funzionanti, e scrive il risultato in logs/selftest.txt. Codice di uscita 0 = tutto ok.
"""
from __future__ import annotations

import os
import platform
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

from config import BASE_DIR, LOG_DIR, load_config


def _check(name: str, fn, results: list) -> None:
    t0 = time.time()
    try:
        detail = fn() or ""
        results.append((True, name, f"{detail} ({time.time() - t0:.1f}s)"))
    except Exception as e:  # noqa: BLE001 - è una diagnosi: riportiamo qualunque errore
        results.append((False, name, f"{e.__class__.__name__}: {e}"))
        results.append((None, "", traceback.format_exc().strip().replace("\n", "\n      ")))


def run() -> int:
    cfg = load_config()
    results: list = []

    def qt():
        from PySide6 import __version__
        from PySide6.QtWidgets import QApplication  # noqa: F401
        return f"PySide6 {__version__}"

    def anthropic_sdk():
        import anthropic
        key = "presente" if os.environ.get("ANTHROPIC_API_KEY") else "NON impostata"
        return f"anthropic {anthropic.__version__}, ANTHROPIC_API_KEY {key}"

    def ollama():
        import json
        import urllib.request
        url = cfg["brain"]["ollama_url"].rstrip("/") + "/api/tags"
        with urllib.request.urlopen(url, timeout=3) as r:
            models = [m["name"] for m in json.load(r).get("models", [])]
        return f"raggiungibile, modelli: {', '.join(models) or 'nessuno'}"

    def microphone():
        import sounddevice as sd
        d = sd.query_devices(kind="input")
        return f"{d['name']} ({int(d['default_samplerate'])} Hz)"

    def tts():
        out = {}

        def job():
            try:
                import comtypes
                comtypes.CoInitialize()
                import pyttsx3
                engine = pyttsx3.init()
                voices = [v.name for v in engine.getProperty("voices")]
                wav = Path(tempfile.gettempdir()) / "elyca_selftest.wav"
                engine.save_to_file("Prova", str(wav))
                engine.runAndWait()
                out["ok"] = f"voci: {', '.join(voices)}; file audio {wav.stat().st_size} byte"
                wav.unlink(missing_ok=True)
            except Exception as e:  # noqa: BLE001
                out["err"] = e
        t = threading.Thread(target=job)
        t.start()
        t.join(30)
        if "err" in out:
            raise out["err"]
        return out.get("ok", "timeout")

    def whisper():
        import faster_whisper
        from voice.stt import MODELS_DIR
        if not MODELS_DIR.exists():
            return f"faster-whisper {faster_whisper.__version__}; modello non ancora scaricato (avverrà al primo uso)"
        import numpy as np
        from voice.stt import SpeechToText
        stt = SpeechToText(cfg["voice"])
        stt.transcribe(np.zeros(16000, dtype=np.float32))
        return f"faster-whisper {faster_whisper.__version__}; modello '{cfg['voice']['whisper_model']}' caricato e funzionante"

    _check("Interfaccia (Qt)", qt, results)
    _check("SDK Anthropic", anthropic_sdk, results)
    _check("Ollama", ollama, results)
    _check("Microfono", microphone, results)
    _check("Sintesi vocale", tts, results)
    _check("Dettatura (Whisper)", whisper, results)

    lines = [f"Elyca selftest - {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"Eseguibile: {sys.executable} (frozen={getattr(sys, 'frozen', False)})",
             f"Cartella: {BASE_DIR}", f"Windows: {platform.platform()}", ""]
    for ok, name, detail in results:
        if ok is None:
            lines.append(f"      {detail}")
        else:
            lines.append(f"[{'OK' if ok else 'ERRORE'}] {name}: {detail}")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / "selftest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Ollama spento non è un errore dell'app: non conta per il codice di uscita
    failures = [r for r in results if r[0] is False and r[1] != "Ollama"]
    return 1 if failures else 0
