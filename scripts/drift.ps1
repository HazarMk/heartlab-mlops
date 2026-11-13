$ErrorActionPreference = 'Stop'
python src/generate_data.py --drift
python src/drift.py
if ($LASTEXITCODE -gt 1) { exit $LASTEXITCODE }
