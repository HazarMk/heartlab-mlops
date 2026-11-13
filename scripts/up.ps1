param([string]$KeycloakPassword)
$ErrorActionPreference = 'Stop'
if (-not $KeycloakPassword) {
    $secure = Read-Host 'Entrez le mot de passe administrateur Keycloak (utilisez le mot de passe existant si le portail a déjà été démarré)' -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $KeycloakPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}
$env:KEYCLOAK_ADMIN_PASSWORD = $KeycloakPassword
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'Services démarrés. Entraînez/chargez le modèle si nécessaire, puis ouvrez http://127.0.0.1:4200.'
