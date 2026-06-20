# `app.py` — Network Automation Multi-Agent Workflow

A FastAPI webapp that orchestrates a **5-agent LLM pipeline** for automated campus network design. It communicates via **Kafka** with the Gateway and supports **human-in-the-loop (HITL)** approval/revision at each phase.

---

## Configuration

Reads `.env` for model, vector-store, and service URLs.

| Variable | Purpose |
|---|---|
| `QWEN_EMBEDDING_MODEL` | HuggingFace embedding model for RAG |
| `QDRANT_*` | Qdrant vector-database connection |
| `OLLAMA_*` | Ollama LLM endpoint & model name |
| `QWEN_CODE_MODEL` | Coder LLM for CLI config generation |
| `IMAGE_SERVICE_URL` | External diagram-generation microservice |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker connection |
| `POSTGRES_URI` | Chat store connection |
| `TOP_K` | Number of RAG chunks to retrieve (25) |
| `SPARSE_K` | Top-k sparse-vector indices (100) |

---

## LLM & Embedding Setup

- **`llm`** — `Ollama` instance with function-calling enabled, 131k context window, 400 s timeout.
- **`llm_qwen_coder`** — Separate coder LLM for CLI generation.
- **`embed_model`** — `HuggingFaceEmbedding` (Qwen3-Embedding-8B) for turning text into dense vectors.

---

## RAG Pipeline — Qdrant Hybrid Search

### `_sparse(text, top_k=SPARSE_K)`
Converts an embedding vector into a `SparseVector` by keeping the top-`k` dimensions with the largest magnitudes. Enables **hybrid (dense + sparse)** retrieval in Qdrant.

### `_build_retriever()`
Creates a Qdrant vector-store client, wraps it in a `VectorStoreIndex`, and returns a retriever that fetches the top `TOP_K` (25) chunks per query.

### Search Tools
- `search_network_device_datasheets(query)` — Queries `qwen-tech-docs` for equipment specs (registered as `network_device_lookup`)
- `list_available_products()` — Lists all product families from the knowledge base
- `search_product_specs(query)` — Gets detailed specs for a specific product family
- `search_across_products(query)` — Cross-product search for HA/uplink requirements
- `search_config_guides(query)` — Queries `qwen-config-guides` for CLI syntax verification
- `firecrawl_search(query)` — Web search for latest standards and pricing

---

## Agents (defined in `agents.py`)

### Agent 1 — `prompt_rephraser`
Refines the user's raw multi-building floorplan into a structured, detailed prompt for the topology designer. Preserves per-building, per-floor breakdowns and infers missing assumptions.

### Agent 2 — `topology_designer`
Receives the rephrased prompt and produces a full network topology including:
- Topology type, layer-by-layer breakdown
- High-availability (VSF, VSX, LAG, QoS)
- VLAN/subnet plan sized to per-floor user counts
- Redundancy / failover scheme
- ASCII diagram of buildings, floors, and links

Uses `firecrawl_search` to verify latest standards before designing.

### Agent 3 — `device_selector`
Has access to product catalog and RAG lookup tools. Analyses the topology per building/floor, calls datasheet tools, and produces a Bill of Materials (BOM) table with model/SKU, specs, quantities, and justifications.

### Agent 4 — `react_topology_architect`
Generates a **JSON object** with `nodes` and `edges` arrays for a React Flow interactive topology diagram. Follows strict layout rules (campus vs datacenter), icon type mapping, and edge styling. Output ONLY valid JSON — no explanations or markdown fences.

### Agent 5 — `cli_config_generator`
Generates per-switch CLI configuration commands for HPE Aruba CX switches. Uses `search_config_guides` to verify AOS-CX CLI syntax. Produces production-ready configs grouped by building and switch role.

### Phase registry — `PHASES` (line 192)
Orders the five agents as phases 1→2→3→4→5.

---

## Kafka Integration

The service doesn't serve direct WebSocket connections. Instead it communicates via two Kafka topics:

| Topic | Direction | Content |
|---|---|---|
| `agent-tasks` | Gateway → AI Service | Task messages with `project_id`, `phase`, `input_context`, `history` |
| `agent-events` | AI Service → Gateway | Streaming events: `TOKEN`, `TOOL_CALL`, `TOOL_RESULT`, `FINAL_ANSWER`, `ERROR` |

### `kafka_handler.py`
- **Consumer**: Reads tasks from `agent-tasks`, runs the appropriate agent via `routes.py` async runner, sends streaming events back to `agent-events`.
- **Producer**: Sends `FINAL_ANSWER`, `TOKEN`, `TOOL_CALL`, `TOOL_RESULT`, `ERROR` events to the Gateway.

---

## WebSocket Handling

WebSocket events are now handled **by the Gateway** (Java/Quarkus), which bridges between the frontend WS and the Kafka topics. See `gateway/` for details.

---

## REST Endpoints

### `POST /api/chat` *(routes.py)*
Simple LLM chat endpoint for the copilot sidebar. Accepts a `ChatRequest` (`message` + `history`), formats the conversation with a system prompt, calls `llm.achat()`, and returns the assistant's reply. Keeps only the last 10 history entries.

---

## Output Reports

### `_save(prompt, rephrased, topology, devices, diagram_code, cli_config="", diagram_url=None)` *(utils.py)*
Writes a timestamped markdown run report to `output/` containing all agent outputs.

---

## Data Flow Summary

```
User Prompt (via Gateway WS → Kafka)
    │
    ▼
Phase 1: prompt_rephraser ─────────────────► rephrased text
    │
    ▼
Phase 2: topology_designer ────────────────► topology design
    │
    ▼
Phase 3: device_selector ──────────────────► BOM table
    │
    ▼
Phase 4: react_topology_architect ─────────► React Flow JSON (nodes + edges)
    │
    ▼
Phase 5: cli_config_generator ─────────────► per-switch CLI configs
    │
    ▼
Gateway sends FINAL_ANSWER per phase,
frontend stores results in ProjectContext
```
