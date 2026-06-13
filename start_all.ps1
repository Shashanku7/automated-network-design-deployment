# start_all.ps1
# Starts all 3 services in separate terminal windows automatically.
# Run from the project root:
#   .\start_all.ps1
#
# To stop everything, just close the 3 terminal windows it opens.

$ROOT     = Split-Path -Parent $MyInvocation.MyCommand.Path
$PYTHON   = "C:\Users\BMSCECSE\AppData\Local\Programs\Python\Python310\python.exe"
$NPM      = "C:\Program Files\nodejs\npm.cmd"
$NODE_DIR = "C:\Program Files\nodejs"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Automated Network Design - Dev Stack  " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ─── 1. Topology Gatekeeper (Port 8002) ──────────────────────────────────────
Write-Host "[1/3] Starting Topology Gatekeeper on port 8002..." -ForegroundColor Yellow
$topoDir = Join-Path $ROOT "topology_generation"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "& {
        Set-Location '$topoDir';
        Write-Host 'Topology Gatekeeper (Port 8002)' -ForegroundColor Cyan;
        & '$PYTHON' -m uvicorn app:app --port 8002 --reload
    }"
)

Start-Sleep -Seconds 2

# ─── 2. AI Service (Port 8000) ───────────────────────────────────────────────
Write-Host "[2/3] Starting AI Service on port 8000..." -ForegroundColor Yellow
$aiDir = Join-Path $ROOT "ai-service"
$aiScript = Join-Path $aiDir "start_ai_service.ps1"

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "& '$aiScript'"
)

Start-Sleep -Seconds 2

# ─── 3. Frontend Dev Server (Port 5173) ──────────────────────────────────────
Write-Host "[3/3] Starting Frontend on port 5173..." -ForegroundColor Yellow
$frontendDir = Join-Path $ROOT "frontend\code"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "& {
        `$env:PATH = 'C:\Program Files\nodejs;' + `$env:PATH;
        Set-Location '$frontendDir';
        Write-Host 'Frontend Dev Server (Port 5173)' -ForegroundColor Cyan;
        & '$NPM' run dev
    }"
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  All 3 services launched!              " -ForegroundColor Green
Write-Host "----------------------------------------" -ForegroundColor Green
Write-Host "  Gatekeeper : http://localhost:8002    " -ForegroundColor White
Write-Host "  AI Service : http://localhost:8000    " -ForegroundColor White
Write-Host "  Frontend   : http://localhost:5173    " -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Opening browser in 3 seconds..." -ForegroundColor Cyan
Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
Write-Host "Close the 3 terminal windows to stop." -ForegroundColor Gray
