# Run ChillPrint locally for the demo: FastAPI on :8000 and the production web build on :3000.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File scripts\start_local.ps1 [-SkipBuild]
# The web app falls back to web/public/demo automatically if the API is down or the laptop is offline.
param([switch]$SkipBuild)

$root = Split-Path -Parent $PSScriptRoot
$engine = Join-Path $root "engine"
$web = Join-Path $root "web"

Write-Host "Starting API on http://localhost:8000 ..."
Start-Process -FilePath (Join-Path $engine ".venv\Scripts\python.exe") `
  -ArgumentList "-m", "uvicorn", "chillprint.api.main:app", "--port", "8000" `
  -WorkingDirectory $engine -WindowStyle Minimized

Set-Location $web
$env:NEXT_PUBLIC_API_BASE = "http://localhost:8000"
if (-not $SkipBuild) {
  Write-Host "Building the web app ..."
  npm run build
  if ($LASTEXITCODE -ne 0) { throw "web build failed" }
}
Write-Host "Starting web on http://localhost:3000 ..."
npm run start
