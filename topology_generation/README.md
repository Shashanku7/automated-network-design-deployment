# Topology Gatekeeper — JSON Validation Service

Microservice that validates AI-generated React Flow topology JSON before it reaches the frontend. Applies a 4-layer validation gate to catch malformed or semantically incorrect topology data.

**Port:** 8002

## Purpose

The AI Service (Agent 4) generates React Flow JSON (nodes + edges) representing the network topology. This service ensures the output is valid, structurally sound, and semantically correct before forwarding to the frontend.

## 4-Layer Validation

| Layer | Check | What it validates |
|-------|-------|-------------------|
| 1 | JSON Extraction | Valid JSON parsing, stripping markdown fences |
| 2 | Structural Schema | Required keys (`nodes`, `edges`), correct types, coordinate formats |
| 3 | Reference Integrity | Edge `source`/`target` IDs reference existing nodes |
| 4 | Cross-phase Semantics | Node labels match approved topology, BOM consistency |

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/validate-topology` | Validate topology JSON from AI output |
| `GET` | `/health` | Health check |

### Validate Request

```json
{
  "llm_output": "```json\n{\"nodes\": [...], \"edges\": [...]}\n```",
  "topology_text": "Building 1: Core switch...",
  "bom_text": "Aruba CX 8360..."
}
```

### Validate Response

```json
{
  "status": "ok",
  "code": "{\"nodes\": [...], \"edges\": [...]}"
}
```

On error:
```json
{
  "status": "error",
  "message": "Missing or empty 'nodes' list."
}
```

## Setup

```bash
cd topology_generation
pip install -r requirements.txt
```

## Running

```bash
uvicorn app:app --host 0.0.0.0 --port 8002 --reload
```

## Dependencies

fastapi, uvicorn, httpx, syntax-checker. See `requirements.txt`.
