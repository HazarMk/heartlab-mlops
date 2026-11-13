$ErrorActionPreference = 'Stop'
$body = @{ features = @(13.2, 1.78, 2.14, 11.2, 100, 2.65, 2.76, 0.26, 1.28, 4.38, 1.05, 3.4, 1050) } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/predict' -ContentType 'application/json' -Body $body
