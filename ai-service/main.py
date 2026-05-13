"""
Network Automation Multi-Agent Workflow  (Human-in-the-Loop)
============================================================

Three phases, each with interactive approval before proceeding:

  Phase 1 – Prompt Rephraser   → user approves or requests changes
  Phase 2 – Topology Designer  → user approves or requests changes
  Phase 3 – Device Selector    → final output (RAG over qwen-tech-docs)
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

from llama_index.llms.ollama import Ollama
from llama_index.core.agent.workflow import (
    AgentWorkflow,
    FunctionAgent,
    AgentInput,
    AgentOutput,
    ToolCall,
    ToolCallResult,
)
from llama_index.core.tools import FunctionTool
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core import VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector


# ──────────────────────────────────────────────
# Terminal colours
# ──────────────────────────────────────────────
CYAN, GREEN, YELLOW, RED, MAGENTA = (
    "\033[96m", "\033[92m", "\033[93m", "\033[91m", "\033[95m",
)
BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"


def _banner(title, color=CYAN):
    w = 70
    print(f"\n{color}{BOLD}{'━' * w}\n  {title}\n{'━' * w}{RESET}\n")


def _section(label, color=YELLOW):
    print(f"\n{color}{BOLD}▸ {label}{RESET}")


def _kv(key, value, indent=4):
    print(f"{' ' * indent}{DIM}{key}:{RESET} {value}")


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

QWEN_EMBEDDING_MODEL = os.getenv("QWEN_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "qwen-tech-docs")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

OLLAMA_MODEL = "gemma4:31b-cloud"
OLLAMA_BASE_URL = "https://api.ollama.com"
RETRIEVAL_TOP_K = 25

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────
# LLM  (Ollama Cloud – Gemma 4)
# ──────────────────────────────────────────────
llm = Ollama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    request_timeout=120.0,
    context_window=131072,
    is_function_calling_model=True,
    headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
)

# ──────────────────────────────────────────────
# Embedding model
# ──────────────────────────────────────────────
embedding_model = HuggingFaceEmbedding(
    model_name=QWEN_EMBEDDING_MODEL,
    trust_remote_code=True,
    token=HUGGINGFACE_TOKEN,
    device=os.getenv("EMBEDDING_DEVICE", "cpu"),
)

# ──────────────────────────────────────────────
# Qdrant hybrid retriever  (mirrors search.py)
# ──────────────────────────────────────────────
SPARSE_TOP_K = 100


def _encode_sparse(text: str, top_k: int = SPARSE_TOP_K) -> SparseVector:
    """Build a sparse vector from the dense embedding (mirrors ingest.py)."""
    embedding = embedding_model.get_text_embedding(text)
    arr = np.array(embedding)
    top_indices = np.argsort(np.abs(arr))[-top_k:]
    top_values = arr[top_indices]
    normalised = top_values / (np.linalg.norm(top_values) + 1e-8)
    return SparseVector(indices=top_indices.tolist(), values=normalised.tolist())


def _build_retriever():
    """Create a hybrid Qdrant retriever against the qwen-tech-docs collection."""
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    vector_store = QdrantVectorStore(
        collection_name=QDRANT_COLLECTION_NAME,
        client=client,
        enable_hybrid=True,
        sparse_doc_fn=_encode_sparse,
        sparse_query_fn=_encode_sparse,
        dense_vector_name="dense",
        sparse_vector_name="sparse",
    )
    index = VectorStoreIndex.from_vector_store(
        vector_store, embed_model=embedding_model,
    )
    return index.as_retriever(similarity_top_k=RETRIEVAL_TOP_K)


_retriever = _build_retriever()


# ──────────────────────────────────────────────
# RAG Tool  (for Phase 3)
# ──────────────────────────────────────────────
def search_network_device_datasheets(query: str) -> str:
    """Search the qwen-tech-docs knowledge base for networking component datasheets.

    This tool searches an indexed collection of networking equipment datasheets
    (switches, routers, access points, modules, transceivers) using hybrid
    dense+sparse retrieval.  It returns the top 25 most relevant chunks with
    their source documents and similarity scores.

    Args:
        query: A natural-language question or description of the networking
               components you are looking for.

    Returns:
        A formatted string containing the top 25 retrieved datasheet chunks,
        each with its rank, source PDF, relevance score, and full text content.
    """
    nodes = _retriever.retrieve(query)

    _section(f"RAG RETRIEVAL — {len(nodes)} chunks retrieved", MAGENTA)
    _kv("Query", query)
    print()

    chunks: list[str] = []
    for i, nws in enumerate(nodes, 1):
        source = nws.metadata.get("source", "unknown")
        score = nws.score
        text = nws.text

        print(f"    {MAGENTA}[Chunk {i:>2}/{len(nodes)}]{RESET}  "
              f"score={score:.4f}  source={os.path.basename(source)}")
        preview = text[:150].replace("\n", " ")
        print(f"        {DIM}{preview}…{RESET}")

        chunks.append(
            f"--- Chunk {i} (score: {score:.4f}) ---\n"
            f"Source: {os.path.basename(source)}\n{text}\n"
        )

    print()
    return "\n".join(chunks)


network_device_lookup_tool = FunctionTool.from_defaults(
    fn=search_network_device_datasheets,
    name="network_device_lookup",
    description=(
        "Searches the qwen-tech-docs knowledge base containing datasheets "
        "and specifications of networking components (switches, routers, "
        "access points, modules, transceivers, etc.).  Returns the top 25 "
        "most relevant datasheet chunks."
    ),
)


# ──────────────────────────────────────────────
# Agent Definitions  (no can_handoff_to — flow
# is controlled manually with HITL between phases)
# ──────────────────────────────────────────────
prompt_rephraser_agent = FunctionAgent(
    name="prompt_rephraser",
    description="Rephrases user prompts for network development.",
    system_prompt=(
        "You are a Network Development Prompt Engineer.\n\n"
        "Your job is to take the user's original request and rephrase it into "
        "a detailed, structured prompt that a network topology designer can "
        "act on.  The refined prompt MUST include (when inferable):\n"
        "  • Purpose / use-case of the network\n"
        "  • Number and types of end-devices or users\n"
        "  • Performance requirements (bandwidth, latency, redundancy)\n"
        "  • Physical or logical constraints (floors, buildings, campuses)\n"
        "  • Security or compliance needs\n"
        "  • Budget tier (if mentioned)\n\n"
        "If information is missing, make reasonable assumptions for a "
        "professional enterprise network and state them explicitly.\n\n"
        "Output ONLY the refined prompt."
    ),
    llm=llm,
)

topology_designer_agent = FunctionAgent(
    name="topology_designer",
    description="Designs network topologies with VSF, VSX, LAG, and QoS.",
    system_prompt=(
        "You are a Senior Network Topology Architect.\n\n"
        "Given a refined network development prompt, design a detailed "
        "network topology.  Your output MUST include:\n"
        "  1. **Topology overview** – type (star, spine-leaf, 3-tier, etc.)\n"
        "  2. **Layer breakdown** – core, distribution, access with device counts\n"
        "  3. **High-availability design** – incorporate these technologies:\n"
        "       • VSF (Virtual Switching Framework) – stacking\n"
        "       • VSX (Virtual Switching Extension) – active-active redundancy\n"
        "       • LAG (Link Aggregation / LACP) – bundling parallel links\n"
        "       • QoS (Quality of Service) – traffic classification & queuing\n"
        "  4. **Link design** – uplink speeds, LAG bundles, redundancy paths\n"
        "  5. **VLAN / subnet plan** – purpose, IP ranges, QoS markings\n"
        "  6. **Redundancy & failover** – VRRP/HSRP, dual-homing, VSX\n"
        "  7. **Diagram** – a clear textual or ASCII diagram\n\n"
        "Do NOT include a Bill of Materials — that will be produced later.\n"
        "Output ONLY the topology design."
    ),
    llm=llm,
)

device_selector_agent = FunctionAgent(
    name="device_selector",
    description="Selects networking devices from qwen-tech-docs datasheets.",
    system_prompt=(
        "You are a Network Hardware Specialist.\n\n"
        "You receive a network topology design and the original user\n"
        "requirements.  Your task is to:\n\n"
        "  STEP 1:  Analyse the topology layer by layer (core, distribution,\n"
        "           access, wireless, edge/security).\n"
        "  STEP 2:  For EACH device role, call the 'network_device_lookup'\n"
        "           tool with a specific search query describing the needs\n"
        "           (e.g. '48-port PoE+ access switch with 10G uplinks and\n"
        "           VSF stacking support').\n"
        "           You MUST call this tool AT LEAST ONCE.\n"
        "  STEP 3:  Review ALL retrieved datasheet chunks and match devices\n"
        "           to each topology role.\n"
        "  STEP 4:  For EACH role recommend: model name & series, key specs,\n"
        "           quantity, and brief justification from the datasheet.\n"
        "  STEP 5:  Present a **Bill of Materials (BOM)** as a structured\n"
        "           table grouped by topology layer.  The BOM MUST include:\n"
        "           • Device role  • Recommended model & SKU\n"
        "           • Key specs (ports, PoE, throughput, VSF/VSX)\n"
        "           • Quantity  • Unit justification\n\n"
        "CRITICAL: You MUST call network_device_lookup BEFORE recommending.\n"
        "Base recommendations ONLY on retrieved datasheets — do NOT hallucinate."
    ),
    llm=llm,
    tools=[network_device_lookup_tool],
)


# ──────────────────────────────────────────────
# Event-streaming helper
# ──────────────────────────────────────────────
async def _stream_and_collect(handler) -> str:
    """Stream workflow events with detailed logging, return final response."""
    async for event in handler.stream_events():
        if isinstance(event, AgentInput):
            _section("Agent Input")
            for msg in event.input[-3:]:
                role = msg.role if hasattr(msg, "role") else "unknown"
                content = str(msg.content) if hasattr(msg, "content") else str(msg)
                if len(content) > 600:
                    content = content[:600] + f"… [{len(content)} chars total]"
                _kv(f"  [{role}]", "")
                for line in content.split("\n"):
                    print(f"        {line}")

        elif isinstance(event, ToolCall):
            _section("Tool Call", RED)
            _kv("Tool name", event.tool_name)
            _kv("Tool ID", event.tool_id)
            _kv("Tool kwargs", str(event.tool_kwargs))

        elif isinstance(event, ToolCallResult):
            _section("Tool Result", RED)
            _kv("Tool name", event.tool_name)
            output_str = str(event.tool_output)
            _kv("Output length", f"{len(output_str)} chars")
            if event.tool_name == "network_device_lookup":
                print(f"\n{MAGENTA}{BOLD}    ┌─ Retrieved Chunks ─────────────────────────{RESET}")
                for line in output_str.split("\n"):
                    print(f"    │ {line}")
                print(f"{MAGENTA}{BOLD}    └──────────────────────────────────────────────{RESET}")
            elif len(output_str) > 800:
                print(f"    {DIM}{output_str[:800]}…{RESET}")
            else:
                print(f"    {DIM}{output_str}{RESET}")

        elif isinstance(event, AgentOutput):
            agent_name = event.current_agent_name
            _section(f"Agent Output — {agent_name}", GREEN)
            response_text = str(event.response)
            if event.tool_calls:
                for tc in event.tool_calls:
                    _kv("→ Calls tool", f"{tc.tool_name}({tc.tool_kwargs})")
            else:
                _kv("Response length", f"{len(response_text)} chars")
                print(f"\n{GREEN}    ┌─ Agent Response ──────────────────────────────{RESET}")
                for line in response_text.split("\n"):
                    print(f"    │ {line}")
                print(f"{GREEN}    └──────────────────────────────────────────────{RESET}")

    response = await handler
    return str(response)


# ──────────────────────────────────────────────
# Single-phase runner with Human-in-the-Loop
# ──────────────────────────────────────────────
async def _run_phase(
    phase_num: int,
    phase_name: str,
    agent: FunctionAgent,
    initial_message: str,
) -> str:
    """
    Run one agent in a loop until the user approves.
    On each iteration the user can type feedback to revise, or 'approve' to proceed.
    """
    wf = AgentWorkflow(agents=[agent], root_agent=agent.name)
    chat_history: list[ChatMessage] = []
    current_msg = initial_message
    iteration = 0

    while True:
        iteration += 1
        _banner(
            f"PHASE {phase_num}: {phase_name}  (iteration {iteration})", CYAN
        )
        _kv("Agent", agent.name, indent=2)
        _kv("Model", OLLAMA_MODEL, indent=2)

        # Build the run call
        if chat_history:
            messages = chat_history + [
                ChatMessage(role=MessageRole.USER, content=current_msg),
            ]
            handler = wf.run(chat_history=messages)
        else:
            handler = wf.run(user_msg=current_msg)

        # Stream events & get response
        response_text = await _stream_and_collect(handler)

        # Update conversation history for potential re-runs
        chat_history.append(
            ChatMessage(role=MessageRole.USER, content=current_msg)
        )
        chat_history.append(
            ChatMessage(role=MessageRole.ASSISTANT, content=response_text)
        )

        # ── Human review ──────────────────────────
        print(f"\n{YELLOW}{BOLD}{'─' * 70}")
        print(f"  ✋  HUMAN REVIEW — {phase_name}")
        print(f"{'─' * 70}{RESET}")
        print(f"  Type {GREEN}'approve'{RESET} (or {GREEN}'y'{RESET}) to proceed to the next phase.")
        print(f"  Or type your feedback / change request to revise this phase.\n")

        user_input = input(f"  {BOLD}Your decision ▸{RESET} ").strip()

        if user_input.lower() in ("approve", "yes", "y", "ok", "next", ""):
            _section(f"✅  {phase_name} APPROVED", GREEN)
            return response_text
        else:
            _section(f"🔄  Revision requested — re-running {phase_name}", YELLOW)
            print(f"    Feedback: {user_input}\n")
            current_msg = user_input


# ──────────────────────────────────────────────
# Main interactive workflow
# ──────────────────────────────────────────────
def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from a string."""
    return re.sub(r"\033\[[0-9;]*m", "", text)


def _save_run_output(
    user_prompt: str,
    rephrased: str,
    topology: str,
    device_selection: str,
) -> Path:
    """Save the full run output to a timestamped markdown file in output/."""
    ts = datetime.now()
    filename = ts.strftime("%Y-%m-%d_%H-%M-%S") + "_run.md"
    filepath = OUTPUT_DIR / filename

    content = f"""# Network Automation Run

**Date:** {ts.strftime("%Y-%m-%d %H:%M:%S")}  
**Model:** {OLLAMA_MODEL}  
**Qdrant Collection:** {QDRANT_COLLECTION_NAME}  
**Retrieval Top-K:** {RETRIEVAL_TOP_K}  

---

## User Prompt

{user_prompt}

---

## Phase 1: Rephrased Prompt

{_strip_ansi(rephrased)}

---

## Phase 2: Network Topology Design

{_strip_ansi(topology)}

---

## Phase 3: Device Selection & Bill of Materials (RAG)

{_strip_ansi(device_selection)}
"""

    filepath.write_text(content, encoding="utf-8")
    return filepath


async def run(user_prompt: str) -> str:
    """Run the full 3-phase workflow with human-in-the-loop at each stage."""
    _banner("Network Automation Multi-Agent Workflow (Human-in-the-Loop)")
    _kv("User prompt", user_prompt, indent=2)
    _kv("LLM", f"{OLLAMA_MODEL} via {OLLAMA_BASE_URL}", indent=2)
    _kv("Retrieval top-k", str(RETRIEVAL_TOP_K), indent=2)
    _kv("Qdrant collection", QDRANT_COLLECTION_NAME, indent=2)

    # ── Phase 1: Rephrase ────────────────────
    rephrased = await _run_phase(
        1, "Prompt Rephrasing", prompt_rephraser_agent, user_prompt,
    )

    # ── Phase 2: Topology ────────────────────
    topology = await _run_phase(
        2, "Network Topology Design", topology_designer_agent, rephrased,
    )

    # ── Phase 3: Device Selection (RAG) ──────
    device_context = (
        f"## Original User Requirements\n{user_prompt}\n\n"
        f"## Approved Network Topology & BOM\n{topology}"
    )
    final = await _run_phase(
        3, "Device Selection (RAG)", device_selector_agent, device_context,
    )

    # ── Save output ──────────────────────────
    out_path = _save_run_output(user_prompt, rephrased, topology, final)

    _banner("WORKFLOW COMPLETE", GREEN)
    print(final)
    print(f"\n  {DIM}📁  Output saved to: {out_path}{RESET}\n")
    return final


# ──────────────────────────────────────────────
# CLI entry-point
# ──────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Network Automation – 3-agent workflow with human-in-the-loop",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=(
            "I need a network for a 3-floor office building with 200 employees, "
            "each floor has about 60-70 users.  We need WiFi everywhere, "
            "a server room on the ground floor, and guest network isolation."
        ),
        help="Describe the network you need.",
    )
    args = parser.parse_args()

    asyncio.run(run(args.prompt))


if __name__ == "__main__":
    main()
