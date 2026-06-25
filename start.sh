#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.start_pids"

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

kill_process_tree() {
    local parent_pid=$1
    if kill -0 "$parent_pid" 2>/dev/null; then
        local children=$(pgrep -P "$parent_pid" 2>/dev/null || true)
        for child in $children; do
            kill_process_tree "$child"
        done
        kill "$parent_pid" 2>/dev/null || true
    fi
}

stop_services() {
    echo ""
    echo -e "${BOLD}${RED}━━━ Stopping services ━━━${RESET}"
    if [ -f "$PID_FILE" ]; then
        while IFS='|' read -r pid name; do
            if kill -0 "$pid" 2>/dev/null; then
                kill_process_tree "$pid"
                log "Stopped $name (PID $pid) and its descendants"
            else
                info "$name (PID $pid) already stopped"
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    else
        warn "No PID file found."
    fi

    # Always perform a final port-based cleanup sweep
    info "Performing final port cleanup sweep..."
    for port in 8000 8001 8002 5173 8080; do
        pids=$(lsof -ti ":$port" 2>/dev/null || true)
        for p in $pids; do
            kill_process_tree "$p"
            log "Killed process tree on port $port (PID $p)"
        done
    done

    echo -e "${GREEN}All services stopped.${RESET}"
    exit 0
}


cleanup() {
    echo ""
    warn "Caught interrupt — shutting down all services..."
    stop_services
}
trap cleanup SIGINT SIGTERM

if [ "${1:-}" = "--stop" ]; then
    stop_services
fi

SKIP_FRONTEND=false
if [ "${1:-}" = "--no-frontend" ]; then
    SKIP_FRONTEND=true
fi

echo -e "${BOLD}${CYAN}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Network Automation Stack — Unified Launcher"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${RESET}"

rm -f "$PID_FILE"

echo -e "${BOLD}Pre-flight checks...${RESET}"

for cmd in uv python3 npm java; do
    if ! command -v "$cmd" &>/dev/null; then
        err "$cmd not found"
        exit 1
    fi
    log "$cmd found: $($cmd --version | head -1)"
done

if [ "$SKIP_FRONTEND" = false ]; then
    if ! command -v node &>/dev/null; then
        warn "node not found — skipping frontend"
        SKIP_FRONTEND=true
    else
        log "node found: $(node --version)"
    fi
fi

[ -f "$SCRIPT_DIR/gateway/mvnw" ] || { err "gateway/mvnw not found"; exit 1; }
log "mvnw found"

[ -f "$SCRIPT_DIR/ai-service/.env" ] || warn ".env not found in ai-service — defaults will be used"

echo ""

# ---- 1. Topology Gatekeeper (8002) ----
echo -e "${BOLD}${BLUE}[1/5] Topology Gatekeeper → http://localhost:8002${RESET}"
TOPO_DIR="$SCRIPT_DIR/topology_generation"
TOPO_LOG="/tmp/gatekeeper.log"
: > "$TOPO_LOG"
(
    cd "$TOPO_DIR"
    uv venv --quiet 2>/dev/null || true
    warn "Installing deps..."
    uv pip install --quiet -r requirements.txt 2>&1 | tail -1
    exec uv run uvicorn app:app --port 8002 --reload --log-level info
) > >(tee -a "$TOPO_LOG" | sed "s/^/  ${BLUE}[gatekeeper]${RESET} /") 2>&1 &
TOPO_PID=$!
echo "$TOPO_PID|Gatekeeper (8002)" >> "$PID_FILE"
log "Gatekeeper started (PID $TOPO_PID)"
sleep 2

# ---- 2. AI Service (8000) ----
echo -e "${BOLD}${MAGENTA}[2/5] AI Service → http://localhost:8000${RESET}"
AI_DIR="$SCRIPT_DIR/ai-service"
AI_LOG="/tmp/ai-service.log"
: > "$AI_LOG"
(
    cd "$AI_DIR"
    uv venv --quiet 2>/dev/null || true
    warn "Installing deps..."
    uv pip install --quiet \
        fastapi "uvicorn[standard]" httpx python-dotenv aiokafka \
        firecrawl-py qdrant-client asyncpg \
        llama-index llama-index-llms-ollama llama-index-embeddings-ollama \
        llama-index-llms-mistralai llama-index-llms-openrouter \
        llama-index-embeddings-huggingface \
        llama-index-node-parser-docling llama-index-readers-docling \
        llama-index-vector-stores-qdrant \
        llama-index-storage-chat-store-postgres 2>&1 | tail -1
    warn "Installing torch + numpy..."
    uv pip install --quiet torch numpy 2>&1 || warn "torch/numpy install failed (non-fatal)"
    exec uv run uvicorn webapp.app:app --host 0.0.0.0 --port 8000 --reload --log-level info
) > >(tee -a "$AI_LOG" | sed "s/^/  ${MAGENTA}[ai-service]${RESET} /") 2>&1 &
AI_PID=$!
echo "$AI_PID|AI Service (8000)" >> "$PID_FILE"
log "AI Service started (PID $AI_PID)"
sleep 2

# ---- 3. Image Generation Service (8001) ----
echo -e "${BOLD}${CYAN}[3/5] Image Generation → http://localhost:8001${RESET}"
IMG_DIR="$SCRIPT_DIR/Image_generation_service"
IMG_LOG="/tmp/image-gen.log"
: > "$IMG_LOG"
(
    cd "$IMG_DIR"
    VENV="$AI_DIR/.venv"
    if [ -d "$VENV" ]; then
        export UV_PROJECT_ENVIRONMENT="$VENV"
    fi
    exec uv run uvicorn app:app --host 0.0.0.0 --port 8001 --reload --log-level info
) > >(tee -a "$IMG_LOG" | sed "s/^/  ${CYAN}[image-gen]${RESET} /") 2>&1 &
IMG_PID=$!
echo "$IMG_PID|Image Gen (8001)" >> "$PID_FILE"
log "Image Gen started (PID $IMG_PID)"
sleep 2

# ---- 4. Gateway (8080) ----
echo -e "${BOLD}${YELLOW}[4/5] Gateway → http://localhost:8080${RESET}"
GW_DIR="$SCRIPT_DIR/gateway"
GW_LOG="/tmp/gateway.log"
: > "$GW_LOG"
(
    cd "$GW_DIR"
    exec ./mvnw quarkus:dev -DskipTests=true -Dquarkus.http.port=8080
) > >(tee -a "$GW_LOG" | sed "s/^/  ${YELLOW}[gateway]${RESET} /") 2>&1 &
GW_PID=$!
echo "$GW_PID|Gateway (8080)" >> "$PID_FILE"
log "Gateway started (PID $GW_PID)"

# ---- 5. Frontend (5173) ----
if [ "$SKIP_FRONTEND" = false ]; then
    echo -e "${BOLD}${GREEN}[5/5] Frontend → http://localhost:5173${RESET}"
    FE_DIR="$SCRIPT_DIR/frontend/code"
    FE_LOG="/tmp/frontend.log"
    : > "$FE_LOG"
    if [ ! -d "$FE_DIR/node_modules" ]; then
        warn "node_modules missing — running npm install..."
        (cd "$FE_DIR" && npm install 2>&1 | tail -3)
    fi
    (
        cd "$FE_DIR"
        exec npm run dev
    ) > >(tee -a "$FE_LOG" | sed "s/^/  ${GREEN}[frontend]${RESET} /") 2>&1 &
    FE_PID=$!
    echo "$FE_PID|Frontend (5173)" >> "$PID_FILE"
    log "Frontend started (PID $FE_PID)"
else
    info "Skipping frontend (--no-frontend or node missing)"
fi

# ---- Summary ----
echo ""
echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}  All services running!${RESET}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  ${BLUE}Gatekeeper:${RESET}       http://localhost:8002"
echo -e "  ${MAGENTA}AI Service:${RESET}      http://localhost:8000"
echo -e "  ${CYAN}Image Gen:${RESET}        http://localhost:8001"
echo -e "  ${YELLOW}Gateway:${RESET}         http://localhost:8080"
if [ "$SKIP_FRONTEND" = false ]; then
    echo -e "  ${GREEN}Frontend:${RESET}       http://localhost:5173"
fi
echo ""
echo -e "  ${YELLOW}Logs:${RESET}"
echo -e "  ${YELLOW}  tail -f /tmp/gatekeeper.log${RESET}"
echo -e "  ${YELLOW}  tail -f /tmp/ai-service.log${RESET}"
echo -e "  ${YELLOW}  tail -f /tmp/image-gen.log${RESET}"
echo -e "  ${YELLOW}  tail -f /tmp/gateway.log${RESET}"
if [ "$SKIP_FRONTEND" = false ]; then
    echo -e "  ${YELLOW}  tail -f /tmp/frontend.log${RESET}"
fi
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop all services${RESET}"
echo ""

wait
