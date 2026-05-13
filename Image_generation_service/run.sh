#!/bin/bash
# Start the Image Generation Service
# Uses the ai-service's venv since dependencies are shared

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$(dirname "$SCRIPT_DIR")/ai-service/.venv"

if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

cd "$SCRIPT_DIR"
echo "🖼️  Starting Image Generation Service on port 8001..."
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
