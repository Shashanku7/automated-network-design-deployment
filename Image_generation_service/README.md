# Image Generation Service

Standalone microservice for generating network topology diagram images (PNG) from the AI-generated topology designs using **D2** ([d2lang.com](https://d2lang.com)).

## Why D2?

- **Containers** — Buildings nest floors nest devices naturally
- **Clean output** — Professional, readable diagrams without manual layout
- **Styling** — Built-in support for colors, borders, and label formatting
- **Reliable** — Deterministic code generation (no LLM syntax errors)

## Architecture

```
ai-service (port 8000)
    └── After Phase 3 (BOM) completes
         └── POST /api/generate-diagram ──→ Image_generation_service (port 8001)
                                              ├── Parses topology text (regex)
                                              ├── Generates D2 diagram code
                                              ├── Renders PNG via kroki.io
                                              └── Saves to generated_diagrams/
```

## Setup

```bash
cd Image_generation_service
pip install -r requirements.txt
```

## Running

```bash
# Start the service (default port 8001)
python app.py

# Or with uvicorn directly
uvicorn app:app --host 0.0.0.0 --port 8001 --reload

# Or use the convenience script (shares ai-service venv)
./run.sh
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/generate-diagram` | Generate a PNG from topology text |
| `GET` | `/api/diagrams/{filename}` | View a generated diagram |
| `GET` | `/api/diagrams/{filename}/download` | Download a generated diagram |
| `GET` | `/api/diagrams` | List all generated diagrams |
| `GET` | `/health` | Health check |

## Example Request

```bash
curl -X POST http://localhost:8001/api/generate-diagram \
  -H "Content-Type: application/json" \
  -d '{
    "topology": "Building 1: Main Block (3 floors)...",
    "bom": "Core switch: Aruba CX 8360..."
  }'
```

## Output

Generated PNGs are saved to `generated_diagrams/` folder with timestamps.
