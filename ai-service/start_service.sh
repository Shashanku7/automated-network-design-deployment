#!/usr/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.service_pids"

stop_services() {
    if [ -f "$PID_FILE" ]; then
        while IFS='|' read -r pid name; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null
                echo "Stopped $name (PID $pid)"
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    # Fallback: kill by port
    for port in 8000 8001 5173; do
        pid=$(lsof -ti ":$port" 2>/dev/null || true)
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null
            echo "Killed process on port $port (PID $pid)"
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
echo "$!|AI Service (port 8000)" >> "$PID_FILE"
echo "Started AI service (PID $!)"

cd "$SCRIPT_DIR/../Image_generation_service"
./run.sh > /tmp/image-gen.log 2>&1 &
echo "$!|Image Generation Service (port 8001)" >> "$PID_FILE"
echo "Started Image generation service (PID $!)"

cd "$SCRIPT_DIR/../frontend/code"
npm install > /tmp/frontend-install.log 2>&1
npm run dev > /tmp/frontend.log 2>&1 &
echo "$!|Frontend (port 5173)" >> "$PID_FILE"
echo "Started Frontend dev server (PID $!)"

echo ""
echo "All services started. Use '$0 --stop' to stop."
echo "  AI service:        tail -f /tmp/ai-service.log"
echo "  Image generation:  tail -f /tmp/image-gen.log"
echo "  Frontend:          tail -f /tmp/frontend.log"
