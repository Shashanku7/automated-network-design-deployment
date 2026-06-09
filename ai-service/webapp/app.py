"""FastAPI webapp – Network Automation Multi-Agent Workflow with WebSocket streaming."""

import asyncio, json, os, re, sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path so we can import config/search modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from llama_index.llms.ollama import Ollama
from llama_index.core.agent.workflow import (
    AgentWorkflow, FunctionAgent, AgentInput, AgentOutput, ToolCall, ToolCallResult,
)
from llama_index.core.tools import FunctionTool
from llama_index.core.llms import ChatMessage, MessageRole

from config import (
    QDRANT_COLLECTION,
    OLLAMA_API_KEY,
    OLLAMA_MODEL,
    OLLAMA_BASE_URL,
    IMAGE_SERVICE_URL,
    RETRIEVAL_TOP_K,
    MIN_SCORE_THRESHOLD,
    create_qdrant_client,
    extract_product_model,
)
from search import create_vector_store, create_vector_index

# ── Config ────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── LLM ─────────────────────────────────────────
llm = Ollama(
    model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL,
    request_timeout=400.0, context_window=131072,
    is_function_calling_model=True,
    headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
)

llm_plain = Ollama(
    model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL,
    request_timeout=400.0, context_window=131072,
    is_function_calling_model=False,
    headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
)

# ── Qdrant client + retriever ─────────────────────
_qdrant_client = create_qdrant_client()

def _build_retriever():
    vs = create_vector_store(_qdrant_client)
    idx = create_vector_index(vs)
    return idx.as_retriever(similarity_top_k=RETRIEVAL_TOP_K)

_retriever = _build_retriever()

# ── RAG Tools (multi-query strategy) ─────────────

def list_available_products() -> str:
    """List all available product families in the knowledge base with their chunk counts.
    Call this FIRST to discover what products are available before searching."""
    results = _qdrant_client.scroll(
        collection_name=QDRANT_COLLECTION,
        limit=1000,
        with_payload=["product_model", "source"],
        with_vectors=False,
    )
    catalog = {}
    for point in results[0]:
        pm = point.payload.get("product_model", "Unknown")
        src = os.path.basename(point.payload.get("source", ""))
        if pm not in catalog:
            catalog[pm] = {"count": 0, "source": src}
        catalog[pm]["count"] += 1

    lines = ["Available HPE Aruba Networking Switch Families:\n"]
    for model in sorted(catalog.keys()):
        info = catalog[model]
        lines.append(f"  - {model}: {info['count']} datasheet chunks (source: {info['source']})")
    lines.append(f"\nTotal: {sum(v['count'] for v in catalog.values())} chunks across {len(catalog)} product families")
    lines.append("\nUse 'search_product_specs' with a specific product_model to get detailed specs.")
    return "\n".join(lines)


def search_product_specs(query: str, product_model: str) -> str:
    """Search for specific technical specs WITHIN a single product family.

    Args:
        query: What you're looking for (e.g. 'PoE power budget', 'stacking',
               'port density', 'switching capacity')
        product_model: The product family to search in (e.g. 'CX 6200',
                       'CX 6300', 'CX 4100i'). Must match a value from
                       list_available_products.
    """

    # ── 1. Dedicated retriever with large pool so the specific product ──
    #    chunks are likely to be in the top results  (hybrid: dense + BM25)
    TOP_K = 150
    MAX_RESULTS = 30
    try:
        vs = create_vector_store(_qdrant_client)
        idx = create_vector_index(vs)
        retriever = idx.as_retriever(similarity_top_k=TOP_K)
        nodes = retriever.retrieve(f"{product_model} {query}")
        matched = [
            n for n in nodes
            if n.metadata.get("product_model") == product_model
            or extract_product_model(n.metadata.get("source", "")) == product_model
        ]
    except Exception:
        matched = []

    if matched:
        parts = []
        for i, n in enumerate(matched[:MAX_RESULTS], 1):
            src = os.path.basename(n.metadata.get("source", "unknown"))
            parts.append(f"--- {product_model} Chunk {i} (score: {n.score:.4f}) ---\nSource: {src}\n{n.text}\n")
        return "\n".join(parts)

    # ── 2. Fallback: brute-force scroll + Python-side filter ──
    #    (proven to work because list_available_products uses the same unfiltered scroll)
    raw = _qdrant_client.scroll(
        collection_name=QDRANT_COLLECTION,
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )[0]

    product_chunks = [
        pt for pt in raw
        if pt.payload.get("product_model") == product_model
    ]

    if not product_chunks:
        return f"No data found for product model '{product_model}'. Check list_available_products for valid names."

    parts = []
    for i, point in enumerate(product_chunks[:MAX_RESULTS], 1):
        src = os.path.basename(point.payload.get("source", "unknown"))
        text = point.payload.get("text", "")
        parts.append(f"--- {product_model} Chunk {i} ---\nSource: {src}\n{text}\n")
    return "\n".join(parts)


def search_across_products(query: str) -> str:
    """Search across ALL product families for a general networking query.
    Use this for broad questions like 'what switches support VSX' or
    'compare PoE budgets across product lines'.

    Args:
        query: A natural-language question about networking equipment specs.
    """
    nodes = _retriever.retrieve(query)
    nodes = [n for n in nodes if n.score >= MIN_SCORE_THRESHOLD]
    parts = []
    for i, n in enumerate(nodes, 1):
        src = n.metadata.get("source", "unknown")
        # Derive product_model from source filename since retriever metadata lacks it
        pm = extract_product_model(src)
        src_base = os.path.basename(src)
        parts.append(f"--- Chunk {i} [{pm}] (score: {n.score:.4f}) ---\nSource: {src_base}\n{n.text}\n")
    return "\n".join(parts)


catalog_tool = FunctionTool.from_defaults(
    fn=list_available_products, name="list_available_products",
    description=(
        "Lists all available HPE Aruba Networking product families in the knowledge base. "
        "Call this FIRST to discover what switch series are available before doing detailed searches."
    ),
)

product_search_tool = FunctionTool.from_defaults(
    fn=search_product_specs, name="search_product_specs",
    description=(
        "Search for detailed specs WITHIN a specific product family (e.g., 'CX 6200', 'CX 6300'). "
        "Use this to get port counts, PoE budgets, stacking options, switching capacity, etc. "
        "for a single product line. Requires product_model from list_available_products."
    ),
)

broad_search_tool = FunctionTool.from_defaults(
    fn=search_across_products, name="search_across_products",
    description=(
        "Search across ALL product families for broad queries like 'which switches support VSX' "
        "or 'compare PoE budgets'. Use for cross-product comparisons."
    ),
)

# ── Agents ────────────────────────────────────
agent1 = FunctionAgent(
    name="prompt_rephraser",
    description="Rephrases user prompts for network development.",
    system_prompt=(
        "You are a Network Development Prompt Engineer.\n"
        "The user's request includes a STRUCTURED BUILDING & FLOOR BREAKDOWN with:\n"
        "- Multiple buildings, each with a name and floor count\n"
        "- Per-floor details: department/area name, student count, staff count, admin count, VOIP device count, IPTV count.\n\n"
        "Rephrase the user's request into a detailed, structured prompt for a network "
        "topology designer. PRESERVE the per-building and per-floor breakdown tables — "
        "do NOT flatten them into aggregates. Include: purpose, user/device counts per "
        "building and floor, performance needs, physical constraints, security, budget. "
        "Make reasonable assumptions if missing.\n"
        "Output ONLY the refined prompt."
    ), llm=llm,
)

agent2 = FunctionAgent(
    name="topology_designer",
    description="Designs network topologies with VSF, VSX, LAG, and QoS.",
    system_prompt=(
        "You are a Senior Network Topology Architect.\n"
        "The input contains a STRUCTURED BUILDING & FLOOR BREAKDOWN with per-building \n"
        "names, floor counts, and per-floor department names with student, staff, admin, VOIP phone, IPTV counts.\n\n"
        "First, intelligently select the appropriate architectural tier model based on the following criteria:\n\n"
        "  - **2-Tier (Collapsed Core + Access):**\n"
        "     • Best for single-building campuses or small networks with < 500 total endpoints.\n"
        "     • Chosen when budget is constrained and simplicity is prioritized.\n"
        "     • Core switches also perform distribution duties, reducing device count and latency.\n\n"
        "  - **3-Tier (Core, Distribution, Access):**\n"
        "     • Best for multi-building campuses or networks with >= 500 total endpoints.\n"
        "     • Chosen when high performance, scalability, and clear traffic separation are needed.\n"
        "     • The dedicated distribution layer aggregates access switches and enforces policies.\n\n"
        "  **Provide a clear 2-3 sentence justification for your choice, referencing total user count, "
        "  number of buildings/floors, and performance requirements.**\n\n"
        "Then, design a detailed topology that reflects this physical structure:\n"
        "1. **Topology overview** — the chosen tier (2-tier or 3-tier) and your justification\n"
        "2. Layer breakdown — map each building to its own distribution block (if 3-tier). "
        "   For each floor, calculate total endpoints (Users + VoIP + IPTV + 1 AP per 25 users). "
        "   To ensure physical density and a 20% growth margin, calculate required access ports as: "
        "   Required Ports = (Total Endpoints * 1.2). Specify how many 24-port or 48-port switches are needed based on this total.\n"
        "3. High-availability: VSF, VSX, LAG (LACP), QoS\n"
        "4. Link design (speeds, LAG bundles, redundancy). Explicitly state if high-density student areas require Multi-Gigabit (Smart Rate) access links for Wi-Fi 6/6E APs.\n"
        "5. VLAN plan — keep every department isolated using VLAN, create VLANs per building or per floor/department, "
        "   assign subnets sized to actual user counts (students, staffs, admins, VOIP phones, IPTV), include QoS markings\n"
        "6. Redundancy & failover — If using VSX at the Core/Distribution layer, utilize VSX Active-Gateway for default gateways. Do NOT combine VRRP with VSX Active-Gateway on the same segment.\n"
        "Do NOT include a Bill of Materials."
    ), llm=llm,
)

agent3 = FunctionAgent(
    name="device_selector",
    description="Selects networking devices from qwen-tech-docs datasheets using multiple search tools.",
    system_prompt=(
        "You are a Network Hardware Specialist with access to HPE Aruba Networking datasheets.\n\n"
        "MANDATORY WORKFLOW — follow these steps IN ORDER:\n\n"
        "STEP 1: Call 'list_available_products' to discover all available switch families.\n\n"
        "STEP 2: MANDATORY — Call 'list_available_products' to get the catalog, then call "
        "'search_product_specs' for EVERY single family in that catalog. You must query ALL of them: "
        "CX 4100i, CX 5420, CX 6000, CX 6100, CX 6200, CX 6300, CX 6300L, CX 6400. "
        "Do NOT skip any family, even if you think it is not suitable. "
        "Do NOT make any recommendations until you have queried EVERY family.\n\n"
        "STEP 3: Use 'search_across_products' for cross-cutting questions like:\n"
        "  - 'Which switches support VSF stacking?'\n"
        "  - 'Which switches have Multi-Gigabit (Smart Rate) ports or 10G/25G uplinks?'\n\n"
        "STEP 4: Compare specs across product families for each role and select the best fit based on:\n"
        "  - Physical Port Density: Ensure the total physical ports provided by the switches on a floor mathematically EXCEED the total estimated endpoints plus growth margins provided by the topology designer.\n"
        "  - PoE budget vs. PoE device count (phones, APs, IPTV)\n"
        "  - Downstream Port Speed: Ensure high-density wireless zones utilize switches supporting Smart Rate (2.5GbE+) for AP connectivity.\n"
        "  - Uplink speed requirements\n"
        "  - Stacking/redundancy capabilities (VSF, VSX)\n"
        "  - Cost effectiveness\n\n"
        "STEP 5: Present a Bill of Materials table with columns:\n"
        "  Building/Floor | Role | Model & SKU | Key Specs | Qty | Justification\n"
        "  Group rows by building.\n\n"
        "RULES:\n"
        "- You MUST call the search tools BEFORE recommending any device.\n"
        "- You MUST search MULTIPLE product families per role (not just one).\n"
        "- Base recommendations ONLY on retrieved datasheet specs.\n"
        "- Calculate Wi-Fi AP quantities: approx 25-30 users per AP. Add these APs to the total floor port count requirement.\n"
        "- Prioritize cost-effectiveness without sacrificing quality and performance.\n"
    ), llm=llm, tools=[catalog_tool, product_search_tool, broad_search_tool],
)

agent4 = FunctionAgent(
    name="d2_diagram_generator",
    description="Generates D2 diagram code for network topology visualization.",
    system_prompt=(
        "You are a D2 Diagram Specialist.\n"
        "Given a network topology design and Bill of Materials (BOM), generate "
        "valid D2 diagram code that visualizes the topology.\n\n"
        "D2 RULES:\n"
        "- Use `direction: down` for top-to-bottom layout\n"
        "- In D2, containers are IMPLICIT — just nest children inside `{}`. Do NOT use `shape: container` (it is invalid and will cause errors)\n"
        "- Use `style` blocks with fill, stroke, font-color, border-radius\n"
        "- Use arrows (->) for connections, label them inline\n"
        "- Do NOT use `icon:` — D2 does not support custom icons and they cause errors\n"
        "- Use descriptive labels instead (e.g., label: \"Access Switch\\nCX 6200F\")\n\n"
        "STRUCTURE:\n"
        "1. Core Layer (top container with VSX pair)\n"
        "2. Server/Management block (if present), connected to core\n"
        "3. Each building as a container with its distribution switch\n"
        "4. Each floor as a sub-container with access switch, end devices, Wi-Fi APs\n"
        "5. Connections: core -> building_dist, building_dist -> floor_access, "
        "access -> devices, access -> wifi\n"
        "6. Security zones (if sensitive areas mentioned)\n\n"
        "COLOR SCHEME:\n"
        "- Core: fill \"#1a1a2e\", stroke \"#e94560\"\n"
        "- Building: fill \"#0f3460\", stroke \"#533483\"\n"
        "- Dist switch: fill \"#16213e\", stroke \"#0f3460\"\n"
        "- Floor: fill \"#1a1a40\", stroke \"#533483\"\n"
        "- Access switch: fill \"#533483\", stroke \"#e94560\"\n"
        "- End devices: fill \"#e94560\", stroke \"#ff6b6b\"\n"
        "- Wi-Fi AP: fill \"#4ecca3\", stroke \"#36b37e\"\n"
        "- Server: fill \"#2d4059\", stroke \"#ea5455\"\n"
        "- Security: fill \"#800020\", stroke \"#ff4444\"\n\n"
        "Include VLAN info and subnet details inside end-device labels.\n"
        "Output ONLY the D2 code — no explanations, no markdown fences."
    ), llm=llm,
)


PHASES = [
    (1, "Prompt Rephrasing", agent1),
    (2, "Network Topology Design", agent2),
    (3, "Device Selection & BOM", agent3),
    (4, "D2 Diagram Generation", agent4),
]

# ── Helpers ───────────────────────────────────
def _strip_ansi(t):
    return re.sub(r"\033\[[0-9;]*m", "", t)

def _parse_chunks(raw):
    """Parse RAG output into list of {index, score, source, text} dicts.

    Handles multiple output formats:
      1. Ranked:   --- CX 6300 Chunk 1 (score: 0.8234) ---
      2. Cross:    --- Chunk 1 [CX 6300] (score: 0.8234) ---
      3. Unranked: --- CX 6300 Chunk 1 ---
    """
    chunks = []

    # Pattern 1: Product-specific ranked — "--- CX 6300 Chunk 1 (score: 0.8234) ---"
    pattern_ranked = r"--- (?:.*?)Chunk (\d+)(?: \(score: ([\d.]+)\))? ---\nSource: (.+?)\n(.*?)(?=--- (?:.*?)Chunk |\Z)"
    for m in re.finditer(pattern_ranked, raw, re.DOTALL):
        chunks.append({
            "index": int(m.group(1)),
            "score": float(m.group(2)) if m.group(2) else 0.0,
            "source": m.group(3).strip(),
            "text": m.group(4).strip()[:500],
        })

    # Pattern 2: Cross-product — "--- Chunk 1 [CX 6300] (score: 0.8234) ---"
    if not chunks:
        pattern_cross = r"--- Chunk (\d+) \[(.+?)\](?: \(score: ([\d.]+)\))? ---\nSource: (.+?)\n(.*?)(?=--- Chunk |\Z)"
        for m in re.finditer(pattern_cross, raw, re.DOTALL):
            chunks.append({
                "index": int(m.group(1)),
                "score": float(m.group(3)) if m.group(3) else 0.0,
                "source": f"[{m.group(2)}] {m.group(4).strip()}",
                "text": m.group(5).strip()[:500],
            })

    return chunks

async def _generate_diagram_via_service(diagram_code: str) -> dict:
    """Send D2 diagram code to the Image Generation Service for rendering."""
    import httpx
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{IMAGE_SERVICE_URL}/api/generate-diagram",
            json={"diagram_code": diagram_code},
        )
        resp.raise_for_status()
        return resp.json()

def _save(prompt, rephrased, topology, devices, diagram_code="", diagram_url=None):
    ts = datetime.now()
    fp = OUTPUT_DIR / f"{ts:%Y-%m-%d_%H-%M-%S}_run.md"
    content = (
        f"# Network Automation Run\n\n**Date:** {ts:%Y-%m-%d %H:%M:%S}  \n"
        f"**Model:** {OLLAMA_MODEL}\n\n---\n\n## User Prompt\n\n{prompt}\n\n---\n\n"
        f"## Phase 1: Rephrased Prompt\n\n{_strip_ansi(rephrased)}\n\n---\n\n"
        f"## Phase 2: Network Topology\n\n{_strip_ansi(topology)}\n\n---\n\n"
        f"## Phase 3: Device Selection & BOM\n\n{_strip_ansi(devices)}\n\n---\n\n"
        f"## Phase 4: D2 Diagram Code\n\n```d2\n{_strip_ansi(diagram_code)}\n```\n"
    )
    if diagram_url:
        content += f"\n---\n\n## Topology Diagram\n\nGenerated diagram: `{diagram_url}`\n"
    fp.write_text(content, encoding="utf-8")
    return fp

# ── FastAPI ───────────────────────────────────────
app = FastAPI(title="Network Automation Assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")

class ChatRequest(BaseModel):
    message: str
    history: list = []

@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Simple LLM chat endpoint for the copilot sidebar."""
    messages = [ChatMessage(role=MessageRole.SYSTEM, content=(
        "You are a Network Design AI Assistant. Answer questions about network design, "
        "HPE Aruba - CX products, VLANs, QoS, VSF, VSX, LAG, and general networking. "
        "Be concise and technical."
    ))]
    for h in req.history[-10:]:
        role = MessageRole.USER if h.get("role") == "user" else MessageRole.ASSISTANT
        messages.append(ChatMessage(role=role, content=h.get("content", "")))
    messages.append(ChatMessage(role=MessageRole.USER, content=req.message))
    resp = await llm.achat(messages)
    return {
        "role": "assistant",
        "content": str(resp.message.content),
        "timestamp": datetime.now().isoformat(),
    }

async def _send(ws, **kw):
    await ws.send_text(json.dumps(kw))

async def _run_phase(ws, phase_num, phase_name, agent, initial_msg):
    """Run one agent phase with event streaming and HITL approval."""
    wf = AgentWorkflow(agents=[agent], root_agent=agent.name, timeout=400.0)
    history: list[ChatMessage] = []
    msg = initial_msg
    iteration = 0

    while True:
        iteration += 1
        await _send(ws, type="phase_start", phase=phase_num, name=phase_name, iteration=iteration)

        # Retry up to 3 times on transient LLM errors (e.g. Ollama cloud 500s)
        max_retries = 3
        response_text = ""
        for attempt in range(1, max_retries + 1):
            try:
                if history:
                    handler = wf.run(chat_history=history + [ChatMessage(role=MessageRole.USER, content=msg)])
                else:
                    handler = wf.run(user_msg=msg)

                async for ev in handler.stream_events():
                    if isinstance(ev, AgentInput):
                        await _send(ws, type="agent_input", agent=ev.current_agent_name, model=OLLAMA_MODEL)
                    elif isinstance(ev, ToolCall):
                        await _send(ws, type="tool_call", tool_name=ev.tool_name, tool_kwargs=ev.tool_kwargs)
                    elif isinstance(ev, ToolCallResult):
                        out = str(ev.tool_output)
                        if ev.tool_name in ("search_product_specs", "search_across_products"):
                            chunks = _parse_chunks(out)
                            await _send(ws, type="rag_result", tool_name=ev.tool_name, chunks=chunks, total=len(chunks))
                        else:
                            await _send(ws, type="tool_result", tool_name=ev.tool_name, output=out[:2000])
                    elif isinstance(ev, AgentOutput):
                        response_text = str(ev.response)
                        if ev.tool_calls:
                            for tc in ev.tool_calls:
                                await _send(ws, type="tool_call", tool_name=tc.tool_name, tool_kwargs=tc.tool_kwargs)
                        else:
                            await _send(ws, type="agent_response", agent=ev.current_agent_name, content=response_text)

                resp = await handler
                response_text = str(resp)
                break  # Success — exit retry loop
            except Exception as llm_err:
                import traceback
                traceback.print_exc()
                if attempt < max_retries:
                    await _send(ws, type="agent_response", agent=agent.name,
                                content=f"⚠️ LLM error (attempt {attempt}/{max_retries}): {str(llm_err)[:200]}. Retrying in 5s…")
                    await asyncio.sleep(5)
                else:
                    await _send(ws, type="agent_response", agent=agent.name,
                                content=f"❌ LLM failed after {max_retries} attempts: {str(llm_err)[:300]}. Approving with partial result.")
        history.append(ChatMessage(role=MessageRole.USER, content=msg))
        history.append(ChatMessage(role=MessageRole.ASSISTANT, content=response_text))

        await _send(ws, type="approval_request", phase=phase_num, name=phase_name)
        data = json.loads(await ws.receive_text())

        if data.get("approved"):
            await _send(ws, type="phase_approved", phase=phase_num, name=phase_name)
            return response_text
        else:
            msg = data.get("feedback", "Please revise.")
            await _send(ws, type="phase_revision", phase=phase_num, feedback=msg)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        data = json.loads(await ws.receive_text())
        prompt = data["content"]
        await _send(ws, type="user_echo", content=prompt)

        rephrased = await _run_phase(ws, 1, "Prompt Rephrasing", agent1, prompt)
        topology = await _run_phase(ws, 2, "Network Topology Design", agent2, rephrased)
        ctx = f"## Original Requirements\n{prompt}\n\n## Approved Topology\n{topology}"
        devices = await _run_phase(ws, 3, "Device Selection & BOM", agent3, ctx)

        # Phase 4: D2 Diagram Generation
        d2_ctx = f"## Approved Topology\n{topology}\n\n## Bill of Materials\n{devices}"
        diagram_code = await _run_phase(ws, 4, "D2 Diagram Generation", agent4, d2_ctx)

        # Render D2 code via Image Generation Service
        diagram_url = None
        await _send(ws, type="phase_start", phase=5, name="Topology Diagram", iteration=1)
        try:
            result = await _generate_diagram_via_service(diagram_code)
            if result.get("success"):
                diagram_url = f"{IMAGE_SERVICE_URL}{result['url']}"
                await _send(ws, type="diagram_ready",
                            url=diagram_url,
                            filename=result.get("filename", ""),
                            download_url=f"{IMAGE_SERVICE_URL}{result['url']}/download")
            else:
                await _send(ws, type="diagram_error",
                            message=result.get("error", "Unknown error from image service"))
        except Exception as img_err:
            await _send(ws, type="diagram_error",
                        message=f"Image service unavailable: {str(img_err)}")

        fp = _save(prompt, rephrased, topology, devices, diagram_code, diagram_url)
        await _send(ws, type="workflow_complete", saved_to=str(fp),
                    diagram_url=diagram_url)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await _send(ws, type="error", message=str(e))
        except:
            pass
