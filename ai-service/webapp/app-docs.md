# `app.py` — Network Automation Multi-Agent Workflow

A FastAPI webapp that orchestrates a **3-agent LLM pipeline** for automated campus network design. It streams each agent's output over **WebSocket** in real time, supports **human-in-the-loop (HITL)** approval/revision at each phase, and optionally generates a topology diagram via an external image service.

---

## Configuration (lines 28–43)

Reads `.env` for model, vector-store, and service URLs. Creates an `output/` directory for saving run reports.

| Variable | Purpose |
|---|---|
| `QWEN_EMBEDDING_MODEL` | HuggingFace embedding model for RAG |
| `QDRANT_*` | Qdrant vector-database connection |
| `OLLAMA_*` | Ollama LLM endpoint & model name |
| `IMAGE_SERVICE_URL` | External diagram-generation microservice |
| `TOP_K` | Number of RAG chunks to retrieve (25) |
| `SPARSE_K` | Top-k sparse-vector indices (100) |

---

## LLM & Embedding Setup (lines 44–56)

- **`llm`** — `Ollama` instance with function-calling enabled, 131k context window, 400 s timeout.
- **`embed_model`** — `HuggingFaceEmbedding` (Qwen3-Embedding-8B) for turning text into dense vectors.

---

## RAG Pipeline — Qdrant Hybrid Search (lines 58–92)

### `_sparse(text, top_k=SPARSE_K)` *(line 61)*
Converts an embedding vector into a `SparseVector` by keeping the top-`k` dimensions with the largest magnitudes. This enables **hybrid (dense + sparse)** retrieval in Qdrant.

### `_build_retriever()` *(line 67)*
Creates a Qdrant vector-store client, wraps it in a `VectorStoreIndex`, and returns a retriever that fetches the top `TOP_K` (25) chunks per query.

### `search_network_device_datasheets(query)` *(line 80)*
RAG tool exposed to the agents. Queries the `qwen-tech-docs` collection and returns the top 25 chunks with their scores and source filenames. Registered as `network_device_lookup` — the device-selector agent *must* call this before recommending hardware.

---

## Agents (lines 94–157)

### Agent 1 — `prompt_rephraser` *(line 95)*
Refines the user's raw multi-building floorplan into a structured, detailed prompt for the topology designer. Preserves per-building, per-floor breakdowns and infers missing assumptions.

### Agent 2 — `topology_designer` *(line 112)*
Receives the rephrased prompt and produces a full network topology including:
- Topology type, layer-by-layer breakdown
- High-availability (VSF, VSX, LAG, QoS)
- VLAN/subnet plan sized to per-floor user counts
- Redundancy / failover scheme
- ASCII diagram of buildings, floors, and links

### Agent 3 — `device_selector` *(line 134)*
Has access to the `network_device_lookup` RAG tool. Analyses the topology per building/floor, calls the datasheet retriever, and produces a Bill of Materials (BOM) table with model/SKU, specs, quantities, and justifications.

### Agent 4 — `d2_diagram_generator` *(line 153)*
Generates valid [D2](https://d2lang.com) diagram code from the approved topology and BOM. Follows a strict color scheme, container hierarchy (core → buildings → floors → access switches → end devices), and connection labeling. Produces the actual D2 source code that is sent directly to Kroki.io for rendering — replaces the previously hardcoded `_build_d2_from_topology` logic in the Image Service.

### Phase registry — `PHASES` *(line 190)*
Orders the four agents as phases 1→2→3→4.

---

## Helper Functions (lines 159–201)

### `_strip_ansi(t)` *(line 160)*
Removes ANSI escape sequences before saving markdown reports.

### `_parse_chunks(raw)` *(line 163)*
Parses the RAG tool's output text into a structured list of `{index, score, source, text}` dicts. Used by the WebSocket handler to send structured RAG results to the frontend.

### `_generate_diagram_via_service(diagram_code)` *(line 215)*
Sends the AI-generated D2 diagram code to the Image Generation Service (`IMAGE_SERVICE_URL`) for rendering via Kroki.io. Returns the JSON response containing the URL to the rendered SVG.

### `_save(prompt, rephrased, topology, devices, diagram_code="", diagram_url=None)` *(line 226)*
Writes a timestamped markdown run report to `output/` containing all agent outputs (including the D2 source code) and a link to the rendered diagram.

---

## FastAPI Endpoints (lines 203–352)

### `GET /` *(line 219)*
Serves the frontend `static/index.html`.

### `POST /api/chat` *(line 223)*
Simple LLM chat endpoint for the copilot sidebar. Accepts a `ChatRequest` (`message` + `history`), formats the conversation with a system prompt, calls `llm.achat()`, and returns the assistant's reply. Keeps only the last 10 history entries.

### WebSocket — `GET /ws` *(line 351)*
The core endpoint that orchestrates the full multi-agent workflow:

1. **Receive** user prompt via WebSocket.
2. **Echo** it back (`user_echo`).
3. **Run Phase 1** — `prompt_rephraser` → rephrased prompt.
4. **Run Phase 2** — `topology_designer` (receives rephrased prompt) → topology.
5. **Run Phase 3** — `device_selector` (receives original prompt + approved topology) → BOM.
6. **Run Phase 4** — `d2_diagram_generator` (receives topology + BOM) → D2 diagram code.
7. **Phase 5** — Sends D2 code to Image Service for Kroki.io rendering.
8. **Save** the run report via `_save()` (includes D2 source code in the report).
9. Send `workflow_complete` event with the report path and diagram URL.

All errors and disconnections are handled gracefully.

---

### `_send(ws, **kw)` *(line 242)*
Utility helper that JSON-encodes keyword arguments and pushes the message over the WebSocket.

### `_run_phase(ws, phase_num, phase_name, agent, initial_msg)` *(line 245)*
Runs a single agent phase with:
- **Event streaming** — forwards `AgentInput`, `ToolCall`, `ToolCallResult`, `AgentOutput` events to the frontend in real time.
- **RAG chunk parsing** — when the tool `network_device_lookup` fires, its output is parsed and sent as structured `rag_result` events.
- **Retry loop** — up to 3 retries on transient LLM errors (with 5 s delay).
- **Human-in-the-loop** — sends an `approval_request` event, then waits for the user's decision. If approved, returns the response text. If rejected, incorporates user feedback and re-runs the phase.

---

## Data Flow Summary

```
User Prompt
    │
    ▼
Phase 1: prompt_rephraser ─────────────────► rephrased text
    │                                              │
    │                                              ▼
    │                              Phase 2: topology_designer ──────────► topology
    │                                              │                        │
    │                                              │                        ▼
    │  ┌───────────────────────────────────────────┤    Phase 3: device_selector ──────► BOM
    │  │  original prompt                          │        │
    │  ▼                                          │        │
    │  context for Phase 3 ◄───────────────────────┘        │
    │                                                       │
    ▼                                                       ▼
    └─────────────────────►  Phase 4: d2_diagram_generator ◄─┘
                                        │
                                        ▼
                                  D2 diagram code
                                        │
                                        ▼
                            Phase 5: Render via Kroki
                                        │
                                        ▼
                                  Save Report + Diagram URL
```
