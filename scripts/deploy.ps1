# Build and run Advisor Pulse production container on http://localhost:18080
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".env")) {
  Write-Host "WARNING: .env missing — Gemini features will be disabled. Copy .env.example to .env"
}

Write-Host "Building frontend + API image..."
docker compose build

Write-Host "Starting Advisor Pulse on http://localhost:18080 ..."
docker compose up -d

Write-Host "Waiting for health..."
Start-Sleep -Seconds 5
try {
  $h = Invoke-RestMethod "http://127.0.0.1:18080/api/health"
  Write-Host "OK: $($h.product) v$($h.version) — investors=$($h.investors_loaded)"
  Write-Host "Open: http://127.0.0.1:18080/"
} catch {
  Write-Host "Health check not ready yet — try http://127.0.0.1:18080/ in a few seconds."
  Write-Host $_
}
