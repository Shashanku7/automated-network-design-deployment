#!/usr/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.service_pids"

stop_services() {
    echo "Stopping services..."

    # Kill processes from PID file (kill process group to catch children)
    if [ -f "$PID_FILE" ]; then
        while IFS='|' read -r pid name; do
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                # Kill entire process group
                kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null
                echo "Stopped $name (PID $pid)"
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi

    # Fallback: kill by process name pattern
    for pattern in "uvicorn" "run.sh" "node.*npm" "node.*vite"; do
        pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "$pids" | xargs kill 2>/dev/null || true
        fi
    done

    # Final fallback: kill by port
    for port in 8000 8001 5173; do
        if command -v fuser &>/dev/null; then
            fuser -k "$port/tcp" 2>/dev/null || true
        elif command -v lsof &>/dev/null; then
            pids=$(lsof -ti ":$port" 2>/dev/null || true)
            if [ -n "$pids" ]; then
                echo "$pids" | xargs kill 2>/dev/null || true
            fi
        fi
    done

    # Wait briefly then force kill anything left
    sleep 1
    for port in 8000 8001 5173; do
        if command -v fuser &>/dev/null; then
            fuser -k -9 "$port/tcp" 2>/dev/null || true
        elif command -v lsof &>/dev/null; then
            pids=$(lsof -ti ":$port" 2>/dev/null || true)
            if [ -n "$pids" ]; then
                echo "$pids" | xargs kill -9 2>/dev/null || true
            fi
        fi
    done

    echo "All services stopped."
    exit 0
}

if [ "${1:-}" = "--stop" ]; then
    stop_services
fi

# Clear old PIDs
rm -f "$PID_FILE"

cd "$SCRIPT_DIR"
source .venv/bin/activate
uvicorn webapp.app:app --host 0.0.0.0 --port 8000 --reload > /tmp/ai-service.log 2>&1 &
AI_PID=$!
echo "$AI_PID|AI Service (port 8000)" >> "$PID_FILE"
echo "Started AI service (PID $AI_PID)"

cd "$SCRIPT_DIR/../Image_generation_service"
./run.sh > /tmp/image-gen.log 2>&1 &
IMG_PID=$!
echo "$IMG_PID|Image Generation Service (port 8001)" >> "$PID_FILE"
echo "Started Image generation service (PID $IMG_PID)"

cd "$SCRIPT_DIR/../frontend/code"
npm install > /tmp/frontend-install.log 2>&1
npm run dev > /tmp/frontend.log 2>&1 &
FE_PID=$!
echo "$FE_PID|Frontend (port 5173)" >> "$PID_FILE"
echo "Started Frontend dev server (PID $FE_PID)"

echo ""
echo "All services started. Use '$0 --stop' to stop."
echo "  AI service:        tail -f /tmp/ai-service.log"
echo "  Image generation:  tail -f /tmp/image-gen.log"
echo "  Frontend:          tail -f /tmp/frontend.log"
