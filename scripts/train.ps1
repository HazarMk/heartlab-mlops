$ErrorActionPreference = 'Stop'
$env:MLFLOW_TRACKING_URI = 'http://127.0.0.1:5000'

# Fail early with a clear message instead of waiting for MLflow's HTTP retries.
try {
    $null = Invoke-RestMethod -Uri "$env:MLFLOW_TRACKING_URI/health" -TimeoutSec 3
} catch {
    throw "Le moteur Docker fonctionne, mais MLflow n'est pas accessible sur $env:MLFLOW_TRACKING_URI. Dans ce dossier, lancez 'docker compose up -d mlflow', attendez 'healthy' avec 'docker compose ps', puis relancez .\scripts\train.ps1."
}

& '.\.venv\Scripts\python.exe' -m dvc repro --force train
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
