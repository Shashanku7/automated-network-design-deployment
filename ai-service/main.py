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

from config import (
    QDRANT_COLLECTION,
    OLLAMA_API_KEY,
    OLLAMA_MODEL,
    OLLAMA_BASE_URL,
    RETRIEVAL_TOP_K,
    MIN_SCORE_THRESHOLD,
    get_embedding_model,
    create_qdrant_client,
    extract_product_model,
)
from search import create_vector_store, create_vector_index


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
# Configuration  (from shared config module)
# ──────────────────────────────────────────────
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

llm_plain = Ollama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    request_timeout=120.0,
    context_window=131072,
    is_function_calling_model=False,
    headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
)

# ──────────────────────────────────────────────
# Qdrant hybrid retriever  (uses BM25 sparse from search module)
# ──────────────────────────────────────────────
def _build_retriever():
    """Create a hybrid Qdrant retriever against the qwen-tech-docs collection."""
    _client = create_qdrant_client()
    vector_store = create_vector_store(_client)
    index = create_vector_index(vector_store)
    return _client, index.as_retriever(similarity_top_k=RETRIEVAL_TOP_K)


_qdrant_client, _retriever = _build_retriever()


# ──────────────────────────────────────────────
# RAG Tools  (multi-query strategy for Phase 3)
# ──────────────────────────────────────────────

def list_available_products() -> str:
    """List all available product families in the knowledge base.
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

    _section("PRODUCT CATALOG", MAGENTA)
    lines = ["Available HPE Aruba Networking Switch Families:\n"]
    for model in sorted(catalog.keys()):
        info = catalog[model]
        line = f"  - {model}: {info['count']} datasheet chunks (source: {info['source']})"
        lines.append(line)
        print(f"    {MAGENTA}{line}{RESET}")
    lines.append(f"\nTotal: {sum(v['count'] for v in catalog.values())} chunks across {len(catalog)} product families")
    lines.append("\nUse 'search_product_specs' with a specific product_model to get detailed specs.")
    print()
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
    _section(f"PRODUCT SEARCH — {product_model}: {query}", MAGENTA)

    # ── 1. Dedicated retriever with large pool so the specific product ──
    #    chunks are likely to be in the top results  (hybrid: dense + BM25)
    TOP_K = 150
    MAX_RESULTS = 30
    try:
        vs = create_vector_store(_qdrant_client)
        idx = create_vector_index(vs)
        retriever = idx.as_retriever(similarity_top_k=TOP_K)
        nodes = retriever.retrieve(f"{product_model} {query}")
        matched_nodes = [
            n for n in nodes
            if n.metadata.get("product_model") == product_model
            or extract_product_model(n.metadata.get("source", "")) == product_model
        ]
    except Exception as exc:
        # Retriever error – gracefully fall back to scroll
        print(f"    {RED} Retriever error: {exc}{RESET}")
        matched_nodes = []

    if matched_nodes:
        parts = []
        for i, n in enumerate(matched_nodes[:MAX_RESULTS], 1):
            src = os.path.basename(n.metadata.get("source", "unknown"))
            print(f"    {MAGENTA}[{product_model} Chunk {i:>2}/{len(matched_nodes)}]{RESET}  "
                  f"score={n.score:.4f}  source={src}")
            preview = n.text[:120].replace("\n", " ")
            print(f"        {DIM}{preview}…{RESET}")
            parts.append(f"--- {product_model} Chunk {i} (score: {n.score:.4f}) ---\nSource: {src}\n{n.text}\n")
        print()
        return "\n".join(parts)

    # ── 2. Fallback: brute-force scroll + Python-side filter ──
    #    (proven to work because list_available_products uses the same unfiltered scroll)
    _section("FALLBACK — Using Qdrant scroll", YELLOW)
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
        print(f"    {MAGENTA}[{product_model} Chunk {i}]{RESET}  (unranked)")
        parts.append(f"--- {product_model} Chunk {i} ---\nSource: {src}\n{text}\n")
    print()
    return "\n".join(parts)


def search_across_products(query: str) -> str:
    """Search across ALL product families for a general networking query.

    Args:
        query: A natural-language question about networking equipment specs.
    """
    _section(f"CROSS-PRODUCT SEARCH — {query}", MAGENTA)
    nodes = _retriever.retrieve(query)
    nodes = [n for n in nodes if n.score >= MIN_SCORE_THRESHOLD]

    parts = []
    for i, n in enumerate(nodes, 1):
        src = n.metadata.get("source", "unknown")
        pm = extract_product_model(src)
        src_base = os.path.basename(src)
        print(f"    {MAGENTA}[Chunk {i:>2}/{len(nodes)} — {pm}]{RESET}  "
              f"score={n.score:.4f}  source={src_base}")
        parts.append(f"--- Chunk {i} [{pm}] (score: {n.score:.4f}) ---\nSource: {src_base}\n{n.text}\n")

    print()
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
    llm=llm_plain,
)
    name="topology_designer",
    description="Designs network topologies with VSF, VSX, LAG, and QoS.",
    system_prompt=(
        "You are a Senior Network Topology Architect.\n\n"
        "Given a refined network development prompt, first intelligently select the appropriate "
        "architectural tier model, then design a detailed network topology.\n\n"
        "TIER SELECTION CRITERIA:\n"
        "  - **2-Tier (Collapsed Core + Access):**\n"
        "    • Best for single-building campuses or small networks with < 500 total endpoints.\n"
        "    • Chosen when budget is constrained and simplicity is prioritized.\n"
        "    • Core switches also perform distribution duties, reducing device count and latency.\n\n"
        "  - **3-Tier (Core, Distribution, Access):**\n"
        "    • Best for multi-building campuses or networks with >= 500 total endpoints.\n"
        "    • Chosen when high performance, scalability, and clear traffic separation are needed.\n"
        "    • The dedicated distribution layer aggregates access switches and enforces policies.\n\n"
        "  **Provide a clear 2-3 sentence justification for your choice, referencing total user count, "
        "  number of buildings/floors, and performance requirements.**\n\n"
        "Your output MUST include:\n"
        "  1. **Topology overview** – chosen tier (2-tier vs 3-tier) with justification\n"
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
        "  - 'Which switches have 10G/25G uplinks?'\n\n"
        "STEP 4: Compare specs across product families for each role and select the best fit based on:\n"
        "  - Port density vs. user counts per floor\n"
        "  - PoE budget vs. PoE device count (phones, APs, IPTV)\n"
        "  - Uplink speed requirements\n"
        "  - Stacking/redundancy capabilities (VSF, VSX)\n"
        "  - Cost effectiveness\n\n"
        "STEP 5: Present a **Bill of Materials** table with columns:\n"
        "  Device Role | Model & SKU | Key Specs | Qty | Justification\n"
        "  Group rows by topology layer.\n\n"
        "RULES:\n"
        "- You MUST call the search tools BEFORE recommending any device.\n"
        "- You MUST search MULTIPLE product families per role (not just one).\n"
        "- Base recommendations ONLY on retrieved datasheet specs.\n"
        "- Prioritize cost-effectiveness without sacrificing quality and performance.\n"
    ),
    llm=llm,
    tools=[catalog_tool, product_search_tool, broad_search_tool],
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
**Qdrant Collection:** {QDRANT_COLLECTION}  
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
    _kv("Qdrant collection", QDRANT_COLLECTION, indent=2)

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
