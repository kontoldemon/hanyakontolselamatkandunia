$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $root "src"
Set-Location (Join-Path $root "src\cloudsentinel")

Write-Host "CloudSentinel local demo"
Write-Host "SSH:      127.0.0.1:2222"
Write-Host "Admin:    http://localhost:8080"
Write-Host "Stream:   http://localhost:3001"
Write-Host "Firewall: dry-run (no host changes)"
Write-Host ""

python -m cloudsentinel.server --config configs/usas-production.yaml --env .env.local
