#!/usr/bin/env bash

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON_EXE:-python}"
NPM="npm"

echo ""
echo "========================================"
echo "  Automated Network Design - Dev Stack  "
echo "========================================"
echo ""

# ─── 0. Firecrawl Web Scraper (Port 3002) ────────────────────────────────────
echo "[0/4] Starting Firecrawl Docker container..."
FIRECRAWL_DIR="$ROOT/firecrawl"

if [ ! -d "$FIRECRAWL_DIR" ]; then
  echo "Cloning Firecrawl repository for the first time..."
  git clone https://github.com/mendableai/firecrawl.git "$FIRECRAWL_DIR"
fi

(
  cd "$FIRECRAWL_DIR"
  echo "Firecrawl Web Scraper (Port 3002)"
  echo "Starting Docker containers in background..."
  docker compose up -d
  echo "Containers started!"
) &

sleep 3

# ─── 1. Topology Gatekeeper (Port 8002) ──────────────────────────────────────
echo "[1/4] Starting Topology Gatekeeper on port 8002..."
TOPO_DIR="$ROOT/topology_generation"

(
  cd "$TOPO_DIR"

  echo "Topology Gatekeeper (Port 8002)"

  VENV="$TOPO_DIR/.venv"
  VENV_PY="$VENV/Scripts/python.exe"

  # Linux/Mac venv path fallback
  if [ ! -f "$VENV/bin/python" ] && [ ! -f "$VENV_PY" ]; then
    echo "Creating venv for Gatekeeper..."
    "$PYTHON" -m venv "$VENV"
  fi

  echo "Installing Gatekeeper dependencies..."

  if [ -f "$VENV/bin/python" ]; then
    PY_BIN="$VENV/bin/python"
  else
    PY_BIN="$VENV_PY"
  fi

  "$PY_BIN" -m pip install --quiet -r requirements.txt
  "$PY_BIN" -m uvicorn app:app --port 8002 --reload
) &

sleep 2

# ─── 2. AI Service (Port 8000) ───────────────────────────────────────────────
echo "[2/4] Starting AI Service on port 8000..."
AI_DIR="$ROOT/ai-service"
AI_SCRIPT="$AI_DIR/start_ai_service.ps1"

(
  cd "$AI_DIR"
  pwsh -NoExit -ExecutionPolicy Bypass -File "$AI_SCRIPT"
) &

sleep 2

# ─── 3. Java Gateway (Port 8080) ─────────────────────────────────────────────
echo "[3/4] Starting Java Gateway on port 8080..."
GATEWAY_DIR="$ROOT/gateway"

(
  cd "$GATEWAY_DIR"
  echo "Java Gateway (Port 8080)"
  echo "Starting Quarkus DevServices..."
  mvn quarkus:dev
) &

sleep 5

# ─── 4. Frontend Dev Server (Port 5173) ───────────────────────────────────────
echo "[4/4] Starting Frontend on port 5173..."
FRONTEND_DIR="$ROOT/frontend/code"

(
  cd "$FRONTEND_DIR"
  echo "Frontend Dev Server (Port 5173)"

  if [ ! -d "node_modules" ]; then
    echo "Installing Node dependencies..."
    "$NPM" install
  fi

  "$NPM" run dev
) &

echo ""
echo "========================================"
echo "  All services launched!               "
echo "----------------------------------------"
echo "  Firecrawl  : http://localhost:3002   "
echo "  Gatekeeper : http://localhost:8002   "
echo "  AI Service : http://localhost:8000   "
echo "  Gateway    : http://localhost:8080   "
echo "  Frontend   : http://localhost:5173   "
echo "========================================"
echo ""
echo "Opening browser in 3 seconds..."
sleep 3

# Cross-platform browser open
if command -v xdg-open >/dev/null; then
  xdg-open "http://localhost:5173"
elif command -v open >/dev/null; then
  open "http://localhost:5173"
fi

echo "Close background jobs or terminal to stop services."
