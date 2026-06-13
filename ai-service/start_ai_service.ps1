# start_ai_service.ps1
# Helper script called by start_all.ps1 to run the AI service.
# Handles venv creation, dependency install, and uvicorn startup.

$AI_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PYTHON  = "C:\Users\BMSCECSE\AppData\Local\Programs\Python\Python310\python.exe"
$VENV    = Join-Path $AI_DIR ".venv"
$VENV_PY = Join-Path $VENV "Scripts\python.exe"
$VENV_PIP = Join-Path $VENV "Scripts\pip.exe"

Set-Location $AI_DIR
Write-Host "AI Service (Port 8000)" -ForegroundColor Cyan

# Create venv if missing
if (-not (Test-Path $VENV_PY)) {
    Write-Host "Creating venv..." -ForegroundColor Yellow
    & $PYTHON -m venv $VENV
}

# Always ensure required packages are installed
Write-Host "Verifying dependencies..." -ForegroundColor Yellow
& $VENV_PIP install --quiet `
    fastapi `
    "uvicorn[standard]" `
    httpx `
    python-dotenv `
    llama-index `
    llama-index-llms-ollama `
    llama-index-embeddings-huggingface `
    firecrawl-py `
    qdrant-client `
    numpy

if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Some packages may have failed to install." -ForegroundColor Red
}

Write-Host "Starting uvicorn..." -ForegroundColor Green
& $VENV_PY -m uvicorn webapp.app:app --host 0.0.0.0 --port 8000 --reload
