# Deploy Advisor Pulse to Railway (personal account)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

railway whoami
if ($LASTEXITCODE -ne 0) {
  Write-Host "Not logged in. Run: railway login"
  exit 1
}

try { railway status 2>&1 | Out-Null } catch { }
$st = railway status 2>&1 | Out-String
if ($st -match 'No linked project') {
  railway init --name advisor-pulse --json
}

$line = Get-Content .env | Where-Object { $_ -match '^GEMINI_API_KEY=' } | Select-Object -First 1
$key = $line.Substring('GEMINI_API_KEY='.Length)

railway service link advisor-pulse 2>$null
railway variables set "GEMINI_API_KEY=$key" "GEMINI_MODEL=gemini-2.0-flash" "PYTHONPATH=/app/backend"
railway up --detach
railway domain 2>$null
Write-Host "Live: https://advisor-pulse-production.up.railway.app"
railway status
