param(
  [string]$PythonBin = "python"
)

$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RootDir

& $PythonBin -m pip install --upgrade pip
& $PythonBin -m pip install -r requirements-build.txt

if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path release) { Remove-Item release -Recurse -Force }

& $PythonBin -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onefile `
  --name expenses-tracker.exe `
  run_gui.py

New-Item -ItemType Directory -Path release | Out-Null
Compress-Archive -Path dist/expenses-tracker.exe -DestinationPath release/expenses-tracker-windows-x86_64.zip -Force

Write-Host "Build Windows listo en: release/expenses-tracker-windows-x86_64.zip"
