# Elyca

**A tiny AI companion that lives on your Windows desktop.**
Elyca is an animated mascot — a double helix of colorful beads with a big smiling face — that strolls
along the right edge of your screen without ever getting in your way. Call her with a hotkey and she
answers you with a **free, local AI model** ([Ollama](https://ollama.com)), by text or by voice.

*[Leggi in italiano](README.it.md)*

![Elyca's animation states](docs/states.png)

## Features

- **Never in the way** — transparent, always on top, clicks pass through her, she never steals focus,
  steps aside when your mouse gets close, and hides while a full-screen app (video, slides, games) is in front.
- **Chat in a speech bubble** — press `Ctrl+Alt+E`, type, and keep the conversation going right under the bubble.
- **Free and private by default** — answers come from Ollama running on your PC; no account, no API key.
  The model is downloaded automatically the first time.
- **Voice (optional)** — hold `Ctrl+Alt+V` and speak (dictation with faster-whisper, offline on the CPU);
  answers can be read aloud with the Windows voices.
- **Alive** — idle sway, walking, waving, thinking, listening, falling asleep when you're away, eyes that
  follow your cursor, and beads that trail behind when she moves or you drag her.
- **Italian and English** interface, chosen automatically from Windows.
- Multi-monitor and high-DPI aware, ~1% CPU, tray menu, single `.exe`.

![Chatting with Elyca](docs/chat.png)

## Requirements

- Windows 10 or 11 (64-bit)
- [Ollama](https://ollama.com/download) installed and running (free). Elyca downloads her default model
  (`qwen2.5:3b`, about 2 GB) on the first question.
- For voice: a microphone; about 0.5 GB of disk space for the speech model (downloaded on first use).

## Quick start (exe)

1. Install [Ollama](https://ollama.com/download).
2. Download `Elyca.exe` from the [Releases](../../releases) page and put it in a folder of its own
   (it creates `config.json` and `logs\` next to itself).
3. Double-click `Elyca.exe`. Press **`Ctrl+Alt+E`** and say hi.

## Run from source

```powershell
git clone https://github.com/Maurus1988kk/MsElyca.git
cd MsElyca
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Or double-click `avvia_elyca.cmd`, which starts Elyca without a console window (closing the terminal
won't close her). If PowerShell blocks `Activate.ps1`: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## How to use

| What | How |
|---|---|
| Chat | **`Ctrl+Alt+E`** opens the text box; **Enter** sends. The box **stays open below the answer**, so you can keep chatting. **Esc** (or `Ctrl+Alt+E` again) ends the conversation and gives focus back to your previous app; clicking elsewhere or 2 minutes without typing also closes it. |
| Talk | With `voice.enabled: true`: **hold `Ctrl+Alt+V`** while speaking and release when done. The text is sent like a typed question (inside an open conversation too). |
| Move her | Hold **Ctrl** and drag her. She then walks back to the right edge of that monitor. |
| Menu | Right-click the tray icon, or **Ctrl + right-click on the mascot**: Show/Hide, Pause movement, Put to sleep, Forget the conversation, Read answers aloud, Open config, Quit. |

> **Can't see the tray icon?** Windows 11 hides new icons. Use Ctrl + right-click on the mascot, or enable
> Elyca in *Settings → Personalization → Taskbar → Other system tray icons*.

![Ctrl + drag trail effect](docs/trail.png)

## Configuration

Settings live in `config.json`, created next to `main.py` / `Elyca.exe` on first run (menu → *Open config*).
Restart Elyca after editing it. Missing keys are added automatically when you update Elyca.
**Don't edit `config.py`**: it only holds the initial values.

| Key | Default | Meaning |
|---|---|---|
| `general.ui_language` | `auto` | Interface language: `auto` (from Windows), `it`, `en` |
| `brain.backend` | `ollama` | `ollama` (free, local) or `anthropic` (Claude, see below) |
| `brain.ollama_model` | `qwen2.5:3b` | Any model from the [Ollama library](https://ollama.com/library) |
| `brain.ollama_auto_pull` | `true` | Download the model automatically if it's missing |
| `brain.history_turns` | `6` | Question/answer pairs she remembers (in memory only) |
| `brain.system_prompt` | | Elyca's personality and answer style |
| `hotkeys.chat` / `hotkeys.push_to_talk` | `Ctrl+Alt+E` / `Ctrl+Alt+V` | Modifiers: `Ctrl`, `Alt`, `Shift`, `Win`; keys: letters, digits, `F1`–`F24`, `Space`… |
| `voice.enabled` | `false` | Enable dictation and reading answers aloud |
| `voice.whisper_model` | `small` | `small` (fast) or `medium` (more accurate, slower) |
| `voice.whisper_language` | `auto` | `auto` = interface language, `""` = automatic detection, or a code like `it` |
| `voice.tts_voice` / `voice.tts_rate` | `""` / `185` | Part of a Windows voice name (empty = first voice in the interface language), reading speed |
| `mascot.height_px` | `120` | Mascot size |
| `mascot.sleep_after_minutes` | `5` | Falls asleep after this much inactivity (`0` = never) |
| `mascot.trail_delay_s` | `0.3` | How much the beads lag behind when moving (`0` = off) |
| `overlay.hide_on_fullscreen` | `true` | Hide while a full-screen app is in front |
| `bubble.conversation_timeout_s` | `120` | Close the chat box after this long without typing (`0` = never) |

See `config.py` for every option with a short comment.

### Optional: Claude (Anthropic API)

For smarter answers you can switch to Claude: set `brain.backend` to `anthropic`, create an API key at
[platform.claude.com](https://platform.claude.com) and store it once as a user environment variable:

```powershell
setx ANTHROPIC_API_KEY "sk-ant-..."
```

Then close and reopen any open terminal/IDE and restart Elyca. The default model is `claude-haiku-5-5`
(`brain.anthropic_model`). API usage is billed by Anthropic. Never put the key in `config.json`.

## Troubleshooting

`Elyca.exe --selftest` (or `python main.py --selftest`) checks the interface, Ollama, microphone, speech
synthesis, Whisper and the optional Claude SDK without opening any window, and writes the report to
`logs\selftest.txt`. The normal log is `logs\elyca.log`.

## Build the exe

```powershell
.\build_exe.ps1               # creates dist\Elyca.exe
.\build_exe.ps1 -CopyModels   # ...and copies the downloaded speech model next to it
```

The script generates the icon (`packaging\elyca.ico`, drawn by the same code as the mascot) and builds
with `Elyca.spec` (single file, no console, version info from `packaging\version_info.txt`).
`python packaging\make_screenshots.py` regenerates the images in `docs\`.

## Project structure

```
main.py              startup, logging, single instance, --selftest
config.py            config.json defaults and merging
i18n.py              interface texts (Italian / English)
selftest.py          self-diagnosis
mascot/              drawing (QPainter, no image files), animation states, movement, bead trail
overlay/             transparent window, Win32 (click-through, focus, hotkeys, full-screen detection),
                     speech/chat bubbles, tray icon
brain/               LLM backends behind a common interface: Ollama (default), Anthropic (optional)
voice/               push-to-talk recording, faster-whisper dictation, pyttsx3 text-to-speech
packaging/           icon, version info, screenshot generator
```

**Adding a new AI backend:** create `brain/<name>_backend.py` with a subclass of `Backend`
(`brain/base.py`) that streams the answer as text chunks, and register it in `make_backend()`
in `brain/__init__.py`.

## License

[MIT](LICENSE)
