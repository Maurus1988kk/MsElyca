"""Interface texts in Italian and English.

The language is chosen from config ("ui_language": "auto" | "it" | "en"); with "auto"
Elyca uses Italian when Windows is in Italian, English otherwise.
To add a language: add its code to every entry of STRINGS and to SUPPORTED.
"""
from __future__ import annotations

import ctypes
import logging

log = logging.getLogger(__name__)

SUPPORTED = ("it", "en")
_lang = "en"

STRINGS: dict[str, dict[str, str]] = {
    # --- app / tray -------------------------------------------------------------
    "already_running": {
        "it": "Elyca è già in esecuzione.\n\nPer il menu (con \"Esci\"): icona in basso a destra vicino "
              "all'orologio, oppure tieni premuto Ctrl e fai clic destro sulla mascotte.",
        "en": "Elyca is already running.\n\nFor the menu (with \"Quit\"): the icon at the bottom right near "
              "the clock, or hold Ctrl and right-click the mascot.",
    },
    "startup_title": {"it": "Elyca è attiva", "en": "Elyca is running"},
    "startup_body": {
        "it": "Premi {hotkey} per parlarle. Per il menu: icona in basso a destra vicino all'orologio, "
              "oppure Ctrl + tasto destro sulla mascotte.",
        "en": "Press {hotkey} to talk to her. For the menu: the icon at the bottom right near the clock, "
              "or Ctrl + right-click on the mascot.",
    },
    "tray_tooltip": {"it": "Elyca — {hotkey} per parlarle", "en": "Elyca — {hotkey} to talk"},
    "menu_hide": {"it": "Nascondi", "en": "Hide"},
    "menu_show": {"it": "Mostra", "en": "Show"},
    "menu_pause": {"it": "Pausa movimento", "en": "Pause movement"},
    "menu_sleep": {"it": "Fallo dormire", "en": "Put to sleep"},
    "menu_forget": {"it": "Dimentica la conversazione", "en": "Forget the conversation"},
    "menu_tts": {"it": "Leggi le risposte ad alta voce", "en": "Read answers aloud"},
    "menu_config": {"it": "Apri config", "en": "Open config"},
    "menu_quit": {"it": "Esci", "en": "Quit"},
    "config_restart": {
        "it": "Dopo aver salvato config.json, riavvia Elyca per applicare le modifiche.",
        "en": "After saving config.json, restart Elyca to apply the changes.",
    },
    "hotkey_failed": {
        "it": "Non riesco a registrare la hotkey {spec}. Cambiala in config.json.",
        "en": "Could not register the hotkey {spec}. Change it in config.json.",
    },
    # --- chat --------------------------------------------------------------------
    "input_placeholder": {"it": "Chiedi qualcosa a Elyca…  (Esc per chiudere)",
                          "en": "Ask Elyca something…  (Esc to close)"},
    "input_reply": {"it": "Rispondi…  (Esc per chiudere)", "en": "Reply…  (Esc to close)"},
    "input_heard": {"it": "Hai detto: «{text}»", "en": "You said: “{text}”"},
    "brain_generic_error": {"it": "Ops, qualcosa è andato storto (dettagli nel log).",
                            "en": "Oops, something went wrong (details in the log)."},
    "brain_empty": {"it": "Non mi è venuto in mente niente… riprova!",
                    "en": "Nothing came to mind… try again!"},
    # --- Ollama ------------------------------------------------------------------
    "ollama_not_running": {
        "it": "Non trovo Ollama, il programma gratuito che mi fa pensare. Installalo da ollama.com/download, "
              "avvialo e riprova.",
        "en": "I can't find Ollama, the free program that lets me think. Install it from ollama.com/download, "
              "start it and try again.",
    },
    "ollama_pulling": {
        "it": "Scarico il mio cervello ({model}), serve solo la prima volta… {progress}",
        "en": "Downloading my brain ({model}), only needed the first time… {progress}",
    },
    "ollama_pull_failed": {
        "it": "Non sono riuscita a scaricare il modello «{model}». Controlla la connessione o il nome in config.json.",
        "en": "I couldn't download the model “{model}”. Check your connection or the name in config.json.",
    },
    "ollama_http": {"it": "Ollama ha risposto con un errore ({code}).",
                    "en": "Ollama replied with an error ({code})."},
    "ollama_error": {"it": "Ollama: {msg}", "en": "Ollama: {msg}"},
    "ollama_interrupted": {"it": "La risposta di Ollama si è interrotta.",
                           "en": "Ollama's answer was interrupted."},
    # --- Claude (optional) -------------------------------------------------------
    "claude_no_key": {
        "it": "Manca la chiave API di Claude: imposta la variabile d'ambiente ANTHROPIC_API_KEY e riavviami "
              "(oppure usa il backend gratuito \"ollama\" in config.json).",
        "en": "The Claude API key is missing: set the ANTHROPIC_API_KEY environment variable and restart me "
              "(or use the free \"ollama\" backend in config.json).",
    },
    "claude_bad_key": {"it": "La chiave API non è valida. Controlla ANTHROPIC_API_KEY.",
                       "en": "The API key is not valid. Check ANTHROPIC_API_KEY."},
    "claude_permission": {"it": "La chiave API non ha i permessi per questo modello.",
                          "en": "The API key has no access to this model."},
    "claude_model_missing": {"it": "Il modello «{model}» non esiste. Controlla anthropic_model in config.json.",
                             "en": "The model “{model}” does not exist. Check anthropic_model in config.json."},
    "claude_rate_limited": {"it": "Troppe richieste in poco tempo: riprova tra un momento.",
                            "en": "Too many requests: try again in a moment."},
    "claude_bad_request": {"it": "Richiesta non valida (dettagli nel log).",
                           "en": "Invalid request (details in the log)."},
    "claude_status": {"it": "Il servizio di Claude ha risposto con un errore ({code}). Riprova più tardi.",
                      "en": "The Claude service replied with an error ({code}). Try again later."},
    "claude_timeout": {"it": "Claude ci sta mettendo troppo a rispondere. Riprova.",
                       "en": "Claude is taking too long to answer. Try again."},
    "claude_connection": {"it": "Non riesco a collegarmi a Claude. Controlla la connessione a internet.",
                          "en": "I can't reach Claude. Check your internet connection."},
    "claude_refusal": {"it": "Mi dispiace, su questo non posso aiutarti.",
                       "en": "Sorry, I can't help with that."},
    # --- voice -------------------------------------------------------------------
    "voice_not_understood": {"it": "Non ho capito bene… riprova parlando un po' più vicino al microfono.",
                             "en": "I didn't quite get that… try again a bit closer to the microphone."},
    "mic_unavailable": {"it": "Non riesco a usare il microfono ({err}). È collegato?",
                        "en": "I can't use the microphone ({err}). Is it connected?"},
    "rec_failed": {"it": "La registrazione non è riuscita.", "en": "The recording failed."},
    "ptt_too_short": {"it": "Tieni premuta la combinazione mentre parli, poi rilasciala.",
                      "en": "Hold the key combination while you speak, then release it."},
    "stt_loading": {"it": "Preparo le orecchie… (solo la prima volta può volerci un po')",
                    "en": "Getting my ears ready… (the first time may take a while)"},
    "stt_failed": {"it": "Non sono riuscita a trascrivere (dettagli nel log).",
                   "en": "I couldn't transcribe that (details in the log)."},
}


def _windows_language() -> str:
    try:
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    except Exception:  # noqa: BLE001 - non su Windows
        return "en"
    return "it" if (langid & 0x3FF) == 0x10 else "en"  # 0x10 = LANG_ITALIAN


def set_language(setting: str) -> str:
    """Imposta la lingua da config ("auto", "it", "en") e la ritorna."""
    global _lang
    setting = (setting or "auto").lower()
    _lang = setting if setting in SUPPORTED else _windows_language()
    log.info("Lingua dell'interfaccia: %s", _lang)
    return _lang


def lang() -> str:
    return _lang


def t(key: str, **kwargs) -> str:
    entry = STRINGS.get(key)
    if entry is None:
        log.warning("Testo mancante: %s", key)
        return key
    text = entry.get(_lang) or entry["en"]
    return text.format(**kwargs) if kwargs else text
