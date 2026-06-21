# AI Service — Multi-Agent LLM Orchestrator

Core backend that orchestrates a 5-agent LLM pipeline for automated campus network design. Uses RAG (Qdrant hybrid search) for grounded hardware recommendations and communicates via Kafka + WebSocket.

**Port:** 8000

## Architecture

```
Gateway/Kafka ──→ webapp/app.py ──→ 5 Agents (LlamaIndex)
                    │                      │
                    ├── routes.py          ├── Agent 1: Prompt Rephraser
                    ├── agents.py          ├── Agent 2: Topology Designer
                    ├── tools.py           ├── Agent 3: Device Selector
                    └── kafka_handler.py                                               ├── Agent 4: React Topology Architect
                                           └── Agent 5: CLI Config Generator
                              │
                              ├── Qdrant (hybrid search: datasheets + config guides)
                              ├── Ollama (LLM: gemma4, qwen3-coder)
                              ├── Firecrawl (web search)
                              └── Image Gen Service (diagram rendering)
```

## Agents

| # | Agent | Tool Access | Output |
|---|-------|-------------|--------|
| 1 | Prompt Rephraser | — | Structured prompt from user input |
| 2 | Topology Designer | `firecrawl_search_tool` | Network topology with VSF/VSX/LAG/QoS and VLAN |
| 3 | Device Selector | `catalog_tool`, `product_search_tool` (Qdrant RAG), `firecrawl_search_tool`, `broad_search_tool` | BOM with SKU, specs, quantities |
| 4 | React Topology Architect | — | React Flow nodes+edges JSON for interactive topology |
| 5 | CLI Config Generator | `config_guide_tool` | Device CLI configuration commands |

## Setup

```bash
cd ai-service
uv sync

# Configure environment
cp .env.example .env
# Required vars:
#   QDRANT_URL, QDRANT_API_KEY
#   OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_API_KEY
#   HUGGINGFACE_TOKEN (for embedding model)
#   IMAGE_SERVICE_URL (default: http://localhost:8001)
#   KAFKA_BOOTSTRAP_SERVERS (default: localhost:9092)
#   POSTGRES_URI (default: postgresql://postgres:root@localhost:5433/network_design)
```

## Running

```bash
# Direct
uv run uvicorn webapp.app:app --host 0.0.0.0 --port 8000 --reload

# Via start.sh
./start.sh
```

## Ingest Pipeline

Populate Qdrant with HPE Aruba datasheets and config guides:

```bash
# Equipment datasheets (data/*.pdf) → qwen-tech-docs collection
python ingest.py datasheets

# Configuration guides (config_guides/*.pdf) → qwen-config-guides collection
python ingest.py config_guides

# Both
python ingest.py all
```

Uses DoclingReader for PDF parsing, Qwen3-Embedding-8B for dense vectors, and SPLADE-style sparse vectors for hybrid search.

## Key Files

| File | Purpose |
|------|---------|
| `webapp/app.py` | FastAPI entry, lifespan (Kafka start/stop) |
| `webapp/routes.py` | WebSocket (`/ws`) + REST (`/api/chat`) routes |
| `webapp/agents.py` | 5 FunctionAgent definitions with tool bindings |
| `webapp/tools.py` | RAG tools (hybrid search, product search, Firecrawl, catalog lookup) |
| `webapp/kafka_handler.py` | Kafka consumer/producer for agent tasks/events |
| `webapp/config.py` | LLM, Qdrant, PostgresChatStore config |
| `webapp/utils.py` | Report saving, chunk parsing |
| `config.py` | Shared sparse vector config |
| `ingest.py` | PDF → Qdrant ingestion |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_URL` | — | Qdrant cluster URL |
| `QDRANT_API_KEY` | — | Qdrant API key |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `gemma4:31b-cloud` | Main LLM |
| `OLLAMA_API_KEY` | — | Ollama API key |
| `QWEN_CODE_MODEL` | `qwen3-coder:480b-cloud` | CLI generation LLM |
| `HUGGINGFACE_TOKEN` | — | For Qwen3-Embedding-8B |
| `IMAGE_SERVICE_URL` | `http://localhost:8001` | Diagram rendering |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker |
| `POSTGRES_URI` | — | Chat store connection |

## API

### WebSocket — `ws://localhost:8000/ws`

Full-duplex streaming for multi-agent workflow. Events: `USER_INPUT`, `AGENT_EVENT`, `TOKEN`, `TOOL_CALL`, `TOOL_RESULT`, `FINAL_ANSWER`, `APPROVAL_REQ`, `DIAGRAM_READY`, `WORKFLOW_COMPLETE`, `ERROR`.

### REST — `POST /api/chat`

Simple LLM chat for the copilot sidebar.

### Kafka — `agent-tasks` / `agent-events`

Async task distribution and event streaming between Gateway and AI Service.

## Dependencies

Python 3.14+, FastAPI, LlamaIndex, aiokafka, qdrant-client, firecrawl-py, docling, torch, numpy. See `pyproject.toml`.
