# start_all.ps1
# Starts all 3 services in separate terminal windows automatically.
# Run from the project root:
#   .\start_all.ps1
#
# To stop everything, just close the 3 terminal windows it opens.

$ROOT     = Split-Path -Parent $MyInvocation.MyCommand.Path
$PYTHON   = if ($env:PYTHON_EXE) { $env:PYTHON_EXE } else { "python" }
$NPM      = "npm"

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
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "& {
        Set-Location '$topoDir';
        Write-Host 'Topology Gatekeeper (Port 8002)' -ForegroundColor Cyan;
        `$VENV = Join-Path '$topoDir' '.venv';
        `$VENV_PY = Join-Path `$VENV 'Scripts\python.exe';
        if (-not (Test-Path `$VENV_PY)) {
            Write-Host 'Creating venv for Gatekeeper...' -ForegroundColor Yellow;
            & '$PYTHON' -m venv `$VENV;
        }
        Write-Host 'Installing Gatekeeper dependencies...' -ForegroundColor Yellow;
        & `$VENV_PY -m pip install --quiet -r requirements.txt;
        & `$VENV_PY -m uvicorn app:app --port 8002 --reload
    }"
)

Start-Sleep -Seconds 2

# ─── 2. AI Service (Port 8000) ───────────────────────────────────────────────
Write-Host "[2/3] Starting AI Service on port 8000..." -ForegroundColor Yellow
$aiDir = Join-Path $ROOT "ai-service"
$aiScript = Join-Path $aiDir "start_ai_service.ps1"

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "& '$aiScript'"
)

Start-Sleep -Seconds 2

# ─── 3. Java Gateway (Port 8080) ───────────────────────────────────────────────
Write-Host "[3/4] Starting Java Gateway on port 8080..." -ForegroundColor Yellow
$gatewayDir = Join-Path $ROOT "gateway"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "& {
        Set-Location '$gatewayDir';
        Write-Host 'Java Gateway (Port 8080)' -ForegroundColor Cyan;
        Write-Host 'Starting Quarkus DevServices...' -ForegroundColor Yellow;
        & mvn quarkus:dev
    }"
)

Start-Sleep -Seconds 5

# ─── 4. Frontend Dev Server (Port 5173) ──────────────────────────────────────
Write-Host "[4/4] Starting Frontend on port 5173..." -ForegroundColor Yellow
$frontendDir = Join-Path $ROOT "frontend\code"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "& {
        Set-Location '$frontendDir';
        Write-Host 'Frontend Dev Server (Port 5173)' -ForegroundColor Cyan;
        if (-not (Test-Path 'node_modules')) {
            Write-Host 'Installing Node dependencies...' -ForegroundColor Yellow;
            & '$NPM' install;
        }
        & '$NPM' run dev
    }"
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  All 4 services launched!              " -ForegroundColor Green
Write-Host "----------------------------------------" -ForegroundColor Green
Write-Host "  Gatekeeper : http://localhost:8002    " -ForegroundColor White
Write-Host "  AI Service : http://localhost:8000    " -ForegroundColor White
Write-Host "  Gateway    : http://localhost:8080    " -ForegroundColor White
Write-Host "  Frontend   : http://localhost:5173    " -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Opening browser in 3 seconds..." -ForegroundColor Cyan
Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
Write-Host "Close the 4 terminal windows to stop." -ForegroundColor Gray
