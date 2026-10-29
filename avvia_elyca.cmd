@echo off
rem Avvia Elyca senza finestra del terminale: chiudere PowerShell o PyCharm non la chiude.
rem Per fermarla: icona nel tray (in basso a destra) -> Esci.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
