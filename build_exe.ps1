# Crea dist\Elyca.exe. Uso (dalla cartella del progetto):  .\build_exe.ps1
# Opzione -CopyModels: copia anche il modello vocale (models\) accanto all'exe, così non va riscaricato.
param([switch]$CopyModels)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = ".\.venv\Scripts\python.exe"

& $py -m pip install --quiet pyinstaller
& $py packaging\make_icon.py
& $py -m PyInstaller --noconfirm --clean Elyca.spec
if ($LASTEXITCODE -ne 0) { throw "Build non riuscita" }

if ($CopyModels -and (Test-Path models)) {
    Copy-Item -Recurse -Force models dist\models
    Write-Host "Modelli vocali copiati in dist\models"
}
$size = [math]::Round((Get-Item dist\Elyca.exe).Length / 1MB)
Write-Host "Pronto: dist\Elyca.exe ($size MB)"
