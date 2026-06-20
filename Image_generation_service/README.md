# Image Generation Service

Standalone microservice for generating network topology diagrams (SVG) from AI-generated designs using **D2** ([d2lang.com](https://d2lang.com)) rendered via Kroki.io.

**Port:** 8001

## Why D2?

- **Containers** — Buildings nest floors nest devices naturally
- **Clean output** — Professional, readable diagrams without manual layout
- **Styling** — Built-in support for colors, borders, and label formatting
- **Reliable** — Deterministic code generation (no LLM syntax errors)

## Architecture

```
ai-service (port 8000)
    └── After Phase 4 (D2 code generated)
         └── POST /api/generate-diagram ──→ Image Generation Service (port 8001)
                                               ├── Parses topology text (regex)
                                               ├── Generates D2 diagram code
                                               ├── Renders SVG via Kroki.io
                                               └── Saves to generated_diagrams/
```

## Setup

```bash
cd Image_generation_service
pip install -r requirements.txt
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KROKI_URL` | `http://localhost:8003` | Kroki.io rendering endpoint |

## Running

```bash
python app.py                        # port 8001
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
./run.sh                             # convenience script (shares ai-service venv)
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/generate-diagram` | Generate SVG from topology text + BOM |
| `GET` | `/api/diagrams/{filename}` | View generated diagram |
| `GET` | `/api/diagrams/{filename}/download` | Download diagram file |
| `GET` | `/api/diagrams` | List all generated diagrams |
| `GET` | `/health` | Health check |

## Example

```bash
curl -X POST http://localhost:8001/api/generate-diagram \
  -H "Content-Type: application/json" \
  -d '{
    "topology": "Building 1: Main Block (3 floors)...",
    "bom": "Core switch: Aruba CX 8360..."
  }'
```

## Output

Generated SVGs saved to `generated_diagrams/` with timestamps.

## Dependencies

fastapi, uvicorn, httpx, python-dotenv, Pillow. See `requirements.txt`.
