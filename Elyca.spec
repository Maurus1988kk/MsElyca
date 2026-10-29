# -*- mode: python ; coding: utf-8 -*-
# Build di Elyca.exe (un solo file, senza console). Uso: .\build_exe.ps1
# oppure: pyinstaller --noconfirm Elyca.spec
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = []
binaries = []
# voce: modello VAD di faster-whisper e librerie native di CTranslate2
datas += collect_data_files("faster_whisper")
binaries += collect_dynamic_libs("ctranslate2")

hiddenimports = [
    # caricati dinamicamente (importlib) e quindi invisibili a PyInstaller
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    "comtypes.stream",
    # backend importati solo quando servono
    "brain.anthropic_backend",
    "brain.ollama_backend",
    "voice.recorder",
    "voice.stt",
    "voice.tts",
]

excludes = [
    "tkinter", "matplotlib", "IPython", "pytest",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtPdf",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Elyca",
    icon="packaging/elyca.ico",
    version="packaging/version_info.txt",
    console=False,
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
)
