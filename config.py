"""Configurazione: config.json accanto a main.py (o accanto all'.exe).

Al primo avvio il file viene creato con i valori di default. Le chiavi
mancanti (es. aggiunte in versioni successive) vengono aggiunte senza toccare
quelle già personalizzate.
"""
from __future__ import annotations

import copy
import json
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

if getattr(sys, "frozen", False):  # eseguibile PyInstaller
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

CONFIG_PATH = BASE_DIR / "config.json"
LOG_DIR = BASE_DIR / "logs"

# ┌──────────────────────────────────────────────────────────────────────────┐
# │ DO NOT CHANGE YOUR SETTINGS HERE! These are only the initial values used │
# │ to create config.json. Elyca reads config.json: edit that one instead    │
# │ (tray menu or Ctrl + right-click on the mascot → Open config).           │
# └──────────────────────────────────────────────────────────────────────────┘
DEFAULTS: dict = {
    "general": {
        "ui_language": "auto",         # "auto" (from Windows), "it" or "en"
    },
    "mascot": {
        "height_px": 120,              # mascot height (logical pixels, scaled by Windows DPI)
        "fps": 30,
        "walk_speed_px_s": 45,
        "idle_min_s": 4.0,             # shortest pause between walks
        "idle_max_s": 12.0,
        "wave_chance": 0.15,           # chance of waving at the end of a pause
        "edge_margin_px": 4,           # distance from the right screen edge
        "avoid_cursor_distance_px": 70,
        "sleep_after_minutes": 5,      # 0 = never falls asleep by herself
        "trail_delay_s": 0.3,          # beads lag behind when moving/dragged (0 = off)
    },
    "overlay": {
        "hide_on_fullscreen": True,
        "startup_notice": True,        # notification at startup with hotkey and icon location
    },
    "hotkeys": {
        "chat": "Ctrl+Alt+E",
        "push_to_talk": "Ctrl+Alt+V",  # hold it while speaking (requires voice.enabled)
    },
    "bubble": {
        "max_width_px": 280,
        "font_size_pt": 10,
        "chars_per_second": 45,        # typing speed of the answer
        "min_display_s": 4.0,          # the bubble stays at least this long...
        "seconds_per_char": 0.05,      # ...plus this for each character
        "conversation_timeout_s": 120, # the chat box closes after this long without typing (0 = never)
    },
    "brain": {
        "backend": "ollama",           # "ollama" (free, local) or "anthropic" (Claude, needs an API key)
        "ollama_model": "qwen2.5:3b",
        "ollama_url": "http://localhost:11434",
        "ollama_auto_pull": True,      # download the model automatically if missing
        "anthropic_model": "claude-haiku-5-5",
        "anthropic_effort": "low",     # low | medium | high: higher = more reasoning, slower
        "max_tokens": 2048,
        "history_turns": 6,            # question/answer pairs remembered (0 = no memory)
        "timeout_s": 60,
        "system_prompt": (
            "You are Elyca, a small cheerful mascot shaped like a double helix of colorful beads, "
            "who lives on the user's Windows desktop and helps them while they work. "
            "Always reply in the same language the user writes in. Be friendly and concise: "
            "usually 1-3 sentences, at most a short list. "
            "Your text appears in a small plain-text speech bubble: do not use Markdown, "
            "headings, tables or long code blocks."
        ),
    },
    "voice": {
        "enabled": False,              # enables dictation and reading answers aloud
        "whisper_model": "small",      # small (faster) or medium (more accurate, slower)
        "whisper_language": "auto",    # "auto" = interface language, "" = Whisper detection, or a code like "it"
        "whisper_compute_type": "int8",
        "max_record_s": 30,
        "tts_enabled": True,           # read answers aloud
        "tts_voice": "",               # part of a Windows voice name ("" = first voice in the interface language)
        "tts_rate": 185,               # reading speed (about words per minute)
    },
}


def _merge(defaults: dict, user: dict) -> tuple[dict, bool]:
    """Unisce user sopra defaults. Ritorna (risultato, mancavano_chiavi)."""
    out = copy.deepcopy(defaults)
    missing = False
    for key, dval in defaults.items():
        if key not in user:
            missing = True
            continue
        uval = user[key]
        if isinstance(dval, dict) and isinstance(uval, dict):
            out[key], sub_missing = _merge(dval, uval)
            missing = missing or sub_missing
        else:
            out[key] = uval
    # mantieni anche chiavi extra dell'utente
    for key, uval in user.items():
        if key not in defaults:
            out[key] = uval
    return out, missing


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        save_config(DEFAULTS, path)
        log.info("Creato %s con i valori di default", path)
        return copy.deepcopy(DEFAULTS)
    try:
        user = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(user, dict):
            raise ValueError("il file non contiene un oggetto JSON")
    except Exception:
        log.exception("config.json non valido: uso i default (il file non viene modificato)")
        return copy.deepcopy(DEFAULTS)
    cfg, missing = _merge(DEFAULTS, user)
    if missing:
        save_config(cfg, path)
        log.info("Aggiunte a config.json le nuove chiavi di default")
    return cfg


def save_config(cfg: dict, path: Path = CONFIG_PATH) -> None:
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
