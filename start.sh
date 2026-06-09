#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Unified launcher for the Network Automation stack
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
#  Services started:
#    1. AI-Service (FastAPI)           → http://localhost:8000
#    2. Image Generation Service       → http://localhost:8001
#    3. React Frontend (Vite dev)      → http://localhost:5173
#
#  Usage:
#    ./start.sh           # Start all services
#    ./start.sh --no-frontend   # Skip React frontend (backend only)
#    ./start.sh --stop    # Stop all running services
#
set -euo pipefail

# ── Resolve paths relative to this script ──────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AI_SERVICE_DIR="$SCRIPT_DIR/ai-service"
IMAGE_SERVICE_DIR="$SCRIPT_DIR/Image_generation_service"
FRONTEND_DIR="$SCRIPT_DIR/frontend/code"

# ── PID file for cleanup ──────────────────────────
PID_FILE="$SCRIPT_DIR/.running_pids"

# ── Colors ─────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

log()   { echo -e "${GREEN}[✓]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[!]${RESET} $*"; }
err()   { echo -e "${RED}[✗]${RESET} $*"; }
info()  { echo -e "${CYAN}[i]${RESET} $*"; }

# ── Stop handler ───────────────────────────────────
stop_services() {
    echo ""
    echo -e "${BOLD}${RED}━━━ Stopping services ━━━${RESET}"
    if [ -f "$PID_FILE" ]; then
        while IFS='|' read -r pid name; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null && log "Stopped $name (PID $pid)" || warn "Failed to stop $name (PID $pid)"
            else
                info "$name (PID $pid) already stopped"
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    else
        warn "No PID file found. Trying to find processes..."
        # Fallback: kill by port
        for port in 8000 8001 5173; do
            pid=$(lsof -ti ":$port" 2>/dev/null || true)
            if [ -n "$pid" ]; then
                kill "$pid" 2>/dev/null && log "Killed process on port $port (PID $pid)"
            fi
        done
    fi
    echo -e "${GREEN}All services stopped.${RESET}"
    exit 0
}

# ── Trap Ctrl+C to stop all services ──────────────
cleanup() {
    echo ""
    warn "Caught interrupt signal — shutting down all services..."
    stop_services
}
trap cleanup SIGINT SIGTERM

# ── Handle --stop flag ────────────────────────────
if [ "${1:-}" = "--stop" ]; then
    stop_services
fi

SKIP_FRONTEND=false
if [ "${1:-}" = "--no-frontend" ]; then
    SKIP_FRONTEND=true
fi

# ── Banner ─────────────────────────────────────────
echo -e "${BOLD}${CYAN}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Network Automation Stack — Unified Launcher"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${RESET}"

# ── Clear old PID file ────────────────────────────
rm -f "$PID_FILE"

# ── Pre-flight checks ─────────────────────────────
echo -e "${BOLD}Pre-flight checks...${RESET}"

# Check uv
if ! command -v uv &>/dev/null; then
    err "uv not found. Install: https://docs.astral.sh/uv/"
    exit 1
fi
log "uv found: $(uv --version)"

# Check node/npm (for frontend)
if [ "$SKIP_FRONTEND" = false ]; then
    if ! command -v node &>/dev/null; then
        warn "node not found — skipping frontend"
        SKIP_FRONTEND=true
    else
        log "node found: $(node --version)"
    fi
fi

# Check directories
[ -d "$AI_SERVICE_DIR" ]       || { err "ai-service dir not found: $AI_SERVICE_DIR"; exit 1; }
[ -d "$IMAGE_SERVICE_DIR" ]    || { err "Image service dir not found: $IMAGE_SERVICE_DIR"; exit 1; }
[ -f "$AI_SERVICE_DIR/.env" ]  || { warn ".env not found in ai-service — defaults will be used"; }

echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. AI-Service (FastAPI backend) — port 8000
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo -e "${BOLD}${BLUE}[1/3] Starting AI-Service (FastAPI) → http://localhost:8000${RESET}"
(
    cd "$AI_SERVICE_DIR"
    uv run uvicorn webapp.app:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --log-level info \
        2>&1 | sed "s/^/  ${BLUE}[ai-service]${RESET} /"
) &
AI_PID=$!
echo "${AI_PID}|AI-Service (port 8000)" >> "$PID_FILE"
log "AI-Service started (PID $AI_PID)"

# Give it a moment to bind
sleep 2

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. Image Generation Service — port 8001
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo -e "${BOLD}${MAGENTA}[2/3] Starting Image Generation Service → http://localhost:8001${RESET}"
(
    cd "$IMAGE_SERVICE_DIR"
    # Prefer ai-service's uv venv (shared deps), else use system python
    VENV_DIR="$AI_SERVICE_DIR/.venv"
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
    fi
    uvicorn app:app \
        --host 0.0.0.0 \
        --port 8001 \
        --reload \
        --log-level info \
        2>&1 | sed "s/^/  ${MAGENTA}[image-svc]${RESET} /"
) &
IMG_PID=$!
echo "${IMG_PID}|Image Generation Service (port 8001)" >> "$PID_FILE"
log "Image Generation Service started (PID $IMG_PID)"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. React Frontend (Vite dev server) — port 5173
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if [ "$SKIP_FRONTEND" = false ]; then
    echo -e "${BOLD}${GREEN}[3/3] Starting React Frontend (Vite) → http://localhost:5173${RESET}"

    # Install deps if needed
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        warn "node_modules not found — running npm install..."
        (cd "$FRONTEND_DIR" && npm install 2>&1 | tail -3)
    fi

    (
        cd "$FRONTEND_DIR"
        npm run dev 2>&1 | sed "s/^/  ${GREEN}[frontend]${RESET}  /"
    ) &
    FE_PID=$!
    echo "${FE_PID}|React Frontend (port 5173)" >> "$PID_FILE"
    log "React Frontend started (PID $FE_PID)"
else
    info "Skipping frontend (--no-frontend or node not found)"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Summary
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}  All services running!${RESET}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  ${BLUE}AI-Service:${RESET}       http://localhost:8000"
echo -e "  ${MAGENTA}Image Service:${RESET}    http://localhost:8001"
if [ "$SKIP_FRONTEND" = false ]; then
    echo -e "  ${GREEN}React Frontend:${RESET}   http://localhost:5173"
fi
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop all services${RESET}"
echo -e "  ${YELLOW}Or run: ./start.sh --stop${RESET}"
echo ""

# ── Wait for all background processes ─────────────
wait
