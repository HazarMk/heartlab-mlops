$ErrorActionPreference = 'Stop'
$env:MLFLOW_TRACKING_URI = 'http://localhost:5000'
python src/generate_data.py --drift
python src/drift.py --retrain
if ($LASTEXITCODE -eq 1) {
    Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/reload'
} elseif ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
