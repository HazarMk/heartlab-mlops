$ErrorActionPreference = 'Stop'

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3.11 -m venv .venv
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
Write-Host 'Environnement Python prêt.'
