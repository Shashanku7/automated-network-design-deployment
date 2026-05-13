"""FastAPI webapp – Network Automation Multi-Agent Workflow with WebSocket streaming."""

import asyncio, json, os, re
from datetime import datetime
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
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
from llama_index.core import VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector

# ── Config ────────────────────────────────────
dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

QWEN_EMBEDDING_MODEL = os.getenv("QWEN_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "qwen-tech-docs")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_MODEL = "gemma4:31b-cloud"
OLLAMA_BASE_URL = "https://api.ollama.com"
TOP_K = 25
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
IMAGE_SERVICE_URL = os.getenv("IMAGE_SERVICE_URL", "http://localhost:8001")

# ── LLM ───────────────────────────────────────
llm = Ollama(
    model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL,
    request_timeout=400.0, context_window=131072,
    is_function_calling_model=True,
    headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
)

# ── Embedding ─────────────────────────────────
embed_model = HuggingFaceEmbedding(
    model_name=QWEN_EMBEDDING_MODEL, trust_remote_code=True,
    token=HF_TOKEN, device=os.getenv("EMBEDDING_DEVICE", "cpu"),
)

# ── Qdrant retriever ──────────────────────────
SPARSE_K = 100

def _sparse(text, top_k=SPARSE_K):
    emb = np.array(embed_model.get_text_embedding(text))
    idx = np.argsort(np.abs(emb))[-top_k:]
    vals = emb[idx] / (np.linalg.norm(emb[idx]) + 1e-8)
    return SparseVector(indices=idx.tolist(), values=vals.tolist())

def _build_retriever():
    cl = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    vs = QdrantVectorStore(
        collection_name=QDRANT_COLLECTION, client=cl, enable_hybrid=True,
        sparse_doc_fn=_sparse, sparse_query_fn=_sparse,
        dense_vector_name="dense", sparse_vector_name="sparse",
    )
    idx = VectorStoreIndex.from_vector_store(vs, embed_model=embed_model)
    return idx.as_retriever(similarity_top_k=TOP_K)

_retriever = _build_retriever()

# ── RAG tool ──────────────────────────────────
def search_network_device_datasheets(query: str) -> str:
    """Search qwen-tech-docs for networking component datasheets. Returns top 25 chunks."""
    nodes = _retriever.retrieve(query)
    parts = []
    for i, n in enumerate(nodes, 1):
        src = os.path.basename(n.metadata.get("source", "unknown"))
        parts.append(f"--- Chunk {i} (score: {n.score:.4f}) ---\nSource: {src}\n{n.text}\n")
    return "\n".join(parts)

rag_tool = FunctionTool.from_defaults(
    fn=search_network_device_datasheets, name="network_device_lookup",
    description="Searches qwen-tech-docs datasheets for networking components. Returns top 25 chunks.",
)

# ── Agents ────────────────────────────────────
agent1 = FunctionAgent(
    name="prompt_rephraser",
    description="Rephrases user prompts for network development.",
    system_prompt=(
        "You are a Network Development Prompt Engineer.\n"
        "The user's request includes a STRUCTURED BUILDING & FLOOR BREAKDOWN with:\n"
        "- Multiple buildings, each with a name and floor count\n"
        "- Per-floor details: department/area name, student count, staff count, admin count\n\n"
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
        "names, floor counts, and per-floor department names with student/staff/admin counts.\n\n"
        "Design a detailed topology that reflects this physical structure:\n"
        "1. Topology overview (type)\n"
        "2. Layer breakdown — map each building to its own distribution block and \n"
        "   each floor to access-layer switches sized for the user counts on that floor\n"
        "3. High-availability: VSF, VSX, LAG (LACP), QoS\n"
        "4. Link design (speeds, LAG bundles, redundancy)\n"
        "5. VLAN/subnet plan — create VLANs per building or per floor/department as \n"
        "   appropriate, assign subnets sized to actual user counts (students, staff, \n"
        "   admins on each floor), include QoS markings\n"
        "6. Redundancy & failover (VRRP/HSRP, VSX)\n"
        "7. ASCII diagram showing buildings, floors, and inter-building links\n\n"
        "Do NOT include a Bill of Materials. Output ONLY the topology."
    ), llm=llm,
)

agent3 = FunctionAgent(
    name="device_selector",
    description="Selects networking devices from qwen-tech-docs datasheets.",
    system_prompt=(
        "You are a Network Hardware Specialist.\n"
        "The topology you receive is based on a multi-building campus with per-floor \n"
        "user counts (students, staff, admins). Use these counts to size hardware:\n"
        "1. Analyse topology layer by layer and building by building.\n"
        "2. Call 'network_device_lookup' for each device role. You MUST call it.\n"
        "3. Match retrieved datasheets to roles. Size access switches based on the \n"
        "   number of users per floor (port density). Calculate Wi-Fi AP quantities \n"
        "   based on per-floor user counts (approx 25-30 users per AP).\n"
        "4. Present a Bill of Materials table with: building/floor, role, model & SKU, \n"
        "   specs, qty, justification. Group by building where applicable.\n\n"
        "CRITICAL: Call network_device_lookup BEFORE recommending. "
        "Base recommendations ONLY on retrieved datasheets."
    ), llm=llm, tools=[rag_tool],
)

PHASES = [
    (1, "Prompt Rephrasing", agent1),
    (2, "Network Topology Design", agent2),
    (3, "Device Selection & BOM", agent3),
]

# ── Helpers ───────────────────────────────────
def _strip_ansi(t):
    return re.sub(r"\033\[[0-9;]*m", "", t)

def _parse_chunks(raw):
    """Parse RAG output into list of {index, score, source, text} dicts."""
    chunks = []
    for block in re.split(r"--- Chunk (\d+) \(score: ([\d.]+)\) ---", raw):
        pass  # fallback: send raw
    # Simpler regex approach
    pattern = r"--- Chunk (\d+) \(score: ([\d.]+)\) ---\nSource: (.+?)\n(.*?)(?=--- Chunk|\Z)"
    for m in re.finditer(pattern, raw, re.DOTALL):
        chunks.append({
            "index": int(m.group(1)), "score": float(m.group(2)),
            "source": m.group(3).strip(), "text": m.group(4).strip()[:300],
        })
    return chunks

async def _generate_diagram_via_service(topology: str, bom: str) -> dict:
    """Call the Image Generation Service to create a topology diagram PNG."""
    import httpx
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{IMAGE_SERVICE_URL}/api/generate-diagram",
            json={"topology": topology, "bom": bom},
        )
        resp.raise_for_status()
        return resp.json()

def _save(prompt, rephrased, topology, devices, diagram_url=None):
    ts = datetime.now()
    fp = OUTPUT_DIR / f"{ts:%Y-%m-%d_%H-%M-%S}_run.md"
    content = (
        f"# Network Automation Run\n\n**Date:** {ts:%Y-%m-%d %H:%M:%S}  \n"
        f"**Model:** {OLLAMA_MODEL}\n\n---\n\n## User Prompt\n\n{prompt}\n\n---\n\n"
        f"## Phase 1: Rephrased Prompt\n\n{_strip_ansi(rephrased)}\n\n---\n\n"
        f"## Phase 2: Network Topology\n\n{_strip_ansi(topology)}\n\n---\n\n"
        f"## Phase 3: Device Selection & BOM\n\n{_strip_ansi(devices)}\n"
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
        "You are a Network Design Copilot. Answer questions about network design, "
        "HPE Aruba products, VLANs, QoS, VSF, VSX, LAG, and general networking. "
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
                        if ev.tool_name == "network_device_lookup":
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

        # Generate topology diagram via Image Generation Service
        diagram_url = None
        await _send(ws, type="phase_start", phase=4, name="Topology Diagram", iteration=1)
        try:
            result = await _generate_diagram_via_service(topology, devices)
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

        fp = _save(prompt, rephrased, topology, devices, diagram_url)
        await _send(ws, type="workflow_complete", saved_to=str(fp),
                    diagram_url=diagram_url)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await _send(ws, type="error", message=str(e))
        except:
            pass
