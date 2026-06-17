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
from webapp.kafka_handler import KafkaManager

# from llama_index.llms.ollama import Ollama
from llama_index.llms.openrouter import OpenRouter
from llama_index.core.agent.workflow import (
    AgentWorkflow, FunctionAgent, AgentInput, AgentOutput, ToolCall, ToolCallResult,
)
from llama_index.core.tools import FunctionTool
from llama_index.core.llms import ChatMessage, MessageRole

from config import (
    QDRANT_COLLECTION,
    QDRANT_CONFIG_COLLECTION,
    OLLAMA_API_KEY,
    OLLAMA_MODEL,
    OLLAMA_BASE_URL,
    OPENROUTER_API_KEY,
    IMAGE_SERVICE_URL,
    RETRIEVAL_TOP_K,
    MIN_SCORE_THRESHOLD,
    create_qdrant_client,
    extract_product_model,
    get_embedding_model,
    text_to_sparse_vector,
)
from qdrant_client import models

# ── Config ────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── LLM ─────────────────────────────────────────
# llm = Ollama(
#     model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL,
#     request_timeout=400.0, context_window=262144,
#     is_function_calling_model=True,
#     headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
#     temperature=0.3,
# )
#
# llm_qwen_coder= Ollama(
#     model="qwen3-coder:480b-cloud", base_url=OLLAMA_BASE_URL,
#     request_timeout=400.0, context_window=262144,
#     is_function_calling_model=True,
#     headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
# )

llm = OpenRouter(
    api_key=OPENROUTER_API_KEY,
    model="google/gemma-4-31b-it:free",
    temperature=0.4,
    is_function_calling_model=True,
    context_window=32000,
)

llm_qwen_coder= OpenRouter(
    model="openai/gpt-oss-120b:free",
    is_function_calling_model=True,
    context_window=32000,
)

# ── Qdrant client ─────────────────────────────────
_qdrant_client = create_qdrant_client()

# ── Hybrid search (dense + sparse RRF fusion) ───────────
def hybrid_search(
    query_text: str,
    *,
    collection_name: str = QDRANT_COLLECTION,
    top_k: int = 25,
    dense_limit: int = 50,
    sparse_limit: int = 50,
    filter_condition: models.Filter | None = None,
) -> list[dict]:
    """Hybrid search via Qdrant prefetch + RRF fusion.

    Fuses dense (semantic) and sparse (TF-IDF with Qdrant IDF modifier)
    results using Qdrant's ``query_points`` API with ``Fusion.RRF``.

    Parameters
    ----------
    filter_condition : optional
        Qdrant Filter applied as a post-filter to the fused results.

    Returns
    -------
    List of dicts with keys: ``id``, ``score``, ``text``, ``source``,
    ``product_model``, ``doc_id``.
    """
    embed_model = get_embedding_model()
    query_dense = embed_model.get_query_embedding(query_text)
    query_sparse = text_to_sparse_vector(query_text)

    prefetch = [
        models.Prefetch(query=query_dense, using="dense", limit=dense_limit),
        models.Prefetch(query=query_sparse, using="sparse", limit=sparse_limit),
    ]

    if filter_condition:
        prefetch = [
            models.Prefetch(
                query=query_dense, using="dense", limit=dense_limit,
                filter=filter_condition,
            ),
            models.Prefetch(
                query=query_sparse, using="sparse", limit=sparse_limit,
                filter=filter_condition,
            ),
        ]

    result = _qdrant_client.query_points(
        collection_name=collection_name,
        prefetch=prefetch,
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        with_payload=True,
        limit=top_k,
    )

    out = []
    for point in result.points:
        payload = point.payload or {}
        out.append({
            "id": point.id,
            "score": point.score,
            "text": payload.get("text", ""),
            "source": payload.get("source", ""),
            "product_model": payload.get("product_model", ""),
            "doc_id": payload.get("doc_id", ""),
        })
    return out


# ── Firecrawl self-hosted search tool ─────────────────────

# Default to the self-hosted instance on port 3002
_FIRECRAWL_BASE_URL = os.getenv("FIRECRAWL_BASE_URL", "http://localhost:3002")

# Lazy-initialised Firecrawl client so we don't crash on import if the
# container hasn't started yet.
_firecrawl_app = None

def _get_firecrawl_app():
    """Return a cached FirecrawlApp pointing at the self-hosted instance."""
    global _firecrawl_app
    if _firecrawl_app is None:
        from firecrawl import FirecrawlApp
        _firecrawl_app = FirecrawlApp(api_key="local", api_url=_FIRECRAWL_BASE_URL)
    return _firecrawl_app


def firecrawl_search(query: str, limit: int = 5) -> str:
    """
    Web search using a self-hosted Firecrawl instance.

    Use this tool when you need up-to-date or external information that is not
    contained in the local RAG knowledge base — e.g. latest HPE Aruba product
    releases, competitor comparisons, pricing, white-papers, or technical
    blog posts.

    Each result includes the full scraped page content (markdown) so you
    can read the actual article / datasheet without additional calls.

    Args:
        query: The search query (natural language).
        limit: Maximum number of results to return (default 5, max 10).
    """
    limit = min(limit, 10)
    try:
        app = _get_firecrawl_app()
        from firecrawl.v2.types import ScrapeOptions
        opts = ScrapeOptions(formats=["markdown"])
        result = app.search(query=query, limit=limit, scrape_options=opts)
    except Exception as exc:
        return f"[firecrawl_search error] {type(exc).__name__}: {exc}"

    # When scrape_options is passed the results are Document objects with metadata + markdown.
    # Without scrape_options they'd be SearchResultWeb items.
    items = getattr(result, "web", None) or getattr(result, "data", None) or []
    if not items:
        return f"[firecrawl_search] No results found for: {query}"

    lines: list[str] = [f"Firecrawl search results for query: '{query}'\n"]
    for i, item in enumerate(items, start=1):
        # Extract metadata — item could be Document (has .metadata) or SearchResultWeb (has direct attrs)
        metadata = getattr(item, "metadata", item)
        title = getattr(metadata, "title", getattr(item, "title", "")) or ""
        url = getattr(metadata, "url", getattr(item, "url", "")) or ""
        desc = getattr(metadata, "description", getattr(item, "description", "")) or ""

        lines.append(f"--- Result {i} ---")
        lines.append(f"Title: {title}")
        lines.append(f"URL: {url}")
        if desc:
            lines.append(f"Summary: {desc}")

        # Full page markdown content (available when scrape_options is passed)
        md = getattr(item, "markdown", None)
        if md:
            lines.append(f"Content ({len(md)} chars):")
            lines.append(md)
        lines.append("")

    # Brief summary of what was found
    total_chars = sum(len(getattr(i, "markdown", "") or "") for i in items)
    lines.append(f"[Retrieved {len(items)} pages, {total_chars} total chars of content]")
    return "\n".join(lines)


firecrawl_search_tool = FunctionTool.from_defaults(
    fn=firecrawl_search,
    name="firecrawl_search",
    description=(
        "Search the web using a self-hosted Firecrawl instance. "
        "Use this for up-to-date or external information not in the local RAG knowledge base, "
        "such as latest HPE Aruba product releases, pricing, or technical blogs."
    ),
)

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
    from qdrant_client import models as qmodels

    TOP_K = 150
    MAX_RESULTS = 30
    filter_cond = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="product_model",
                match=qmodels.MatchValue(value=product_model),
            )
        ]
    )

    try:
        results = hybrid_search(
            f"{product_model} {query}",
            top_k=TOP_K, dense_limit=TOP_K * 2, sparse_limit=TOP_K * 2,
            filter_condition=filter_cond,
        )
    except Exception:
        results = []

    if results:
        parts = []
        for i, r in enumerate(results[:MAX_RESULTS], 1):
            src = os.path.basename(r["source"])
            parts.append(
                f"--- {product_model} Chunk {i} (score: {r['score']:.4f}) ---\n"
                f"Source: {src}\n{r['text']}\n"
            )
        return "\n".join(parts)

    # ── Fallback: brute-force scroll + Python-side filter ──
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
    results = hybrid_search(query, top_k=RETRIEVAL_TOP_K)
    results = [r for r in results if r["score"] >= MIN_SCORE_THRESHOLD]
    parts = []
    for i, r in enumerate(results, 1):
        pm = extract_product_model(r["source"])
        src_base = os.path.basename(r["source"])
        parts.append(f"--- Chunk {i} [{pm}] (score: {r['score']:.4f}) ---\nSource: {src_base}\n{r['text']}\n")
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


def search_config_guides(query: str) -> str:
    """Search the AOS-CX configuration guide knowledge base for CLI syntax,
    feature configuration steps, and best practices.

    Use this tool when you need to verify exact CLI command syntax, feature
    configuration procedures, or best practices for HPE Aruba CX switches.
    The knowledge base includes AOS-CX 10.13 guides covering fundamentals,
    VSF, VSX, VXLAN, IP services, monitoring, and more.

    Args:
        query: What CLI configuration you need (e.g. 'configure VSX keepalive',
               'VSF member numbering', 'VLAN trunk configuration')
    """
    try:
        results = hybrid_search(
            query,
            collection_name=QDRANT_CONFIG_COLLECTION,
            top_k=RETRIEVAL_TOP_K,
        )
        results = [r for r in results if r["score"] >= MIN_SCORE_THRESHOLD]
    except Exception as exc:
        return f"[search_config_guides error] {type(exc).__name__}: {exc}"
    if not results:
        return f"No configuration guide results found for: {query}"
    parts = []
    for i, r in enumerate(results, 1):
        src_base = os.path.basename(r["source"])
        parts.append(f"--- Config Guide Chunk {i} (score: {r['score']:.4f}) ---\nSource: {src_base}\n{r['text']}\n")
    return "\n".join(parts)


config_guide_tool = FunctionTool.from_defaults(
    fn=search_config_guides, name="search_config_guides",
    description=(
        "Search AOS-CX configuration guides for CLI command syntax, feature "
        "configuration steps, and best practices. Use for writing accurate "
        "CLI configuration commands for each switch in the design."
    ),
)

# ── Agents ────────────────────────────────────
agent1 = FunctionAgent(
    name="prompt_rephraser",
    description="Rephrases user prompts for network development.",
    system_prompt=(
        "You are a Network Development Prompt Engineer.\n"
        "The user's request includes a STRUCTURED BUILDING & FLOOR BREAKDOWN with:\n"
        "- Multiple buildings, each with a name and department count\n"
        "- Per-department details: department/area name, student count, staff count, admin count, VOIP device count, IPTV count, printer count.\n\n"
        "Rephrase the user's request into a detailed, structured prompt for a network "
        "topology designer. PRESERVE the per-building and per-department breakdown tables — "
        "do NOT flatten them into aggregates. Include: purpose, user/device counts per "
        "building and department, performance needs, physical constraints, security, budget. "
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
        "names, department counts, and per-department details with student, staff, admin, VOIP phone, IPTV, and printer counts.\n\n"
        "MANDATORY: You MUST use the 'firecrawl_search' tool BEFORE designing the topology to verify the latest standards, "
        "best practices, and any new HPE Aruba models or technologies. This is NON-NEGOTIABLE to ensure your design matches the latest data. "
        "You MUST search for: latest HPE Aruba campus design best practices, current VSF/VSX recommendations, and any new switch series or features.\n\n"
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
        "   For each department, calculate total endpoints (Users + VoIP + IPTV + Printers + 1 AP per 25 users). "
        "   To ensure physical density and a 20% growth margin, calculate required access ports as: "
        "   Required Ports = (Total Endpoints * 1.2). Specify how many 24-port or 48-port switches are needed based on this total.\n"
        "3. High-availability: VSF, VSX, LAG (LACP), QoS\n"
        "4. Link design (speeds, LAG bundles, redundancy). Explicitly state if high-density student areas require Multi-Gigabit (Smart Rate) access links for Wi-Fi 6/6E APs.\n"
        "5. VLAN plan — keep every department isolated using VLAN, create VLANs per building or per department, "
        "   assign subnets sized to actual user counts (students, staffs, admins, VOIP phones, IPTV, printers), include QoS markings\n"
        "6. Redundancy & failover — If using VSX at the Core/Distribution layer, utilize VSX Active-Gateway for default gateways. Do NOT combine VRRP with VSX Active-Gateway on the same segment.\n"
        "Do NOT include a Bill of Materials."
    ), llm=llm, tools=[firecrawl_search_tool],
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
        "CX 4100i, CX 5420, CX 6000, CX 6100, CX 6200, CX 6300, CX 6300L, CX 6400, "
        "CX 8320, CX 8360, CX 8400, CX 9300. "
        "Do NOT skip any family, even if you think it is not suitable. "
        "Do NOT make any recommendations until you have queried EVERY family.\n\n"
        "STEP 3: Use 'search_across_products' for cross-cutting questions like:\n"
        "  - 'Which switches support VSX for core/distribution redundancy?'\n"
        "  - 'Which switches have 25G/100G uplinks for core aggregation?'\n"
        "  - 'Which switches have Multi-Gigabit (Smart Rate) ports or 10G/25G uplinks?'\n\n"
        "STEP 3b: MANDATORY — Use 'firecrawl_search' to search the web for the latest HPE Aruba product information, "
        "pricing, and any new product releases or updates. This is NON-NEGOTIABLE to ensure your recommendations match the latest data. "
        "You MUST perform this search BEFORE making any final recommendations, even if you think the local datasheets are sufficient.\n\n"
        "STEP 4: Compare specs across product families for each role and select the best fit based on:\n"
        "  - Physical Port Density: Ensure the total physical ports provided by the switches on a department mathematically EXCEED the total estimated endpoints plus growth margins provided by the topology designer.\n"
        "  - PoE budget vs. PoE device count (phones, APs, IPTV, printers)\n"
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
        "- Calculate Wi-Fi AP quantities: approx 25-30 users per AP. Add these APs to the total department port count requirement.\n"
        "- Prioritize cost-effectiveness without sacrificing quality and performance.\n"
    ), llm=llm, tools=[catalog_tool, product_search_tool, broad_search_tool, firecrawl_search_tool],
)

agent4 = FunctionAgent(
    name="d2_diagram_generator",
    description="Generates D2 diagram code for network topology visualization.",
    system_prompt=(
        "You are a D2 Diagram Specialist.\n"
        "Given a network topology design and Bill of Materials (BOM), generate "
        "valid D2 diagram code that visualizes the topology.\n\n"
        "CRITICAL D2 RULES:\n"
        "- First line MUST be exactly: `direction: down` on its own line\n"
        "- `style` blocks are ONLY allowed INSIDE a container — NEVER at the document root\n"
        "- Every `style` block MUST be inside `{ }` of a named node\n"
        "- In D2, containers are IMPLICIT — just nest children inside `{}`. Do NOT use `shape: container`\n"
        "- Use arrows (->) for connections, label them inline\n"
        "- Do NOT use `icon:` — D2 does not support custom icons\n"
        "- ALL labels with special characters (spaces, slashes, commas) MUST use double quotes\n\n"
        "REQUIREMENTS:\n"
        "- Each switch (core, distribution, access) MUST be a SEPARATE individual node — do NOT combine switches into one block.\n"
        "- Each department label MUST include the department/area name AND floor number.\n"
        "- Each switch node label MUST include the switch model name (e.g., CX 6400, CX 6200, CX 8360).\n"
        "- End devices and Wi-Fi APs can be aggregated per department.\n\n"
        "STRUCTURE:\n"
        "1. Core Layer — individual switch nodes (e.g., core1, core2 for VSX pair)\n"
        "2. Server/Management block (if present, one node), connected to core\n"
        "3. Each building as a container with distribution switch nodes (one per switch)\n"
        "4. Each department as a sub-container with:\n"
        "   - A label showing department name AND floor number (e.g., \"Dept 1 - MCA\")\n"
        "   - Individual access switch nodes (one per switch with model name)\n"
        "   - ONE aggregated end-device group node\n"
        "   - ONE Wi-Fi AP node\n"
        "5. Connections: core -> building_dist, building_dist -> floor_access, access -> devices, access -> wifi\n"
        "6. Security zones (if sensitive areas mentioned)\n\n"
        "NAMING CONVENTIONS:\n"
        "- Core switches: core_sw1, core_sw2 (with model in label, e.g., \"CX 8360\")\n"
        "- Distribution switches: dist_b1_sw1 (building 1 switch 1, with model in label)\n"
        "- Access switches: acc_b1_d1_sw1 (building 1, department 1, switch 1, with model in label)\n"
        "- Floor nodes: f1_dept_name (e.g., f1_mca, f2_library)\n\n"
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
        "Output ONLY the D2 code — no explanations, no markdown fences.\n\n"
        "EXAMPLE:\n"
        "direction: down\n"
        "\n"
        "core_sw1: \"Core Switch 1\\nCX 8360\" {\n"
        "  style: {\n"
        "    fill: \"#1a1a2e\"\n"
        "    stroke: \"#e94560\"\n"
        "  }\n"
        "}\n"
        "\n"
        "core_sw2: \"Core Switch 2\\nCX 8360\" {\n"
        "  style: {\n"
        "    fill: \"#1a1a2e\"\n"
        "    stroke: \"#e94560\"\n"
        "  }\n"
        "}\n"
        "\n"
        "b1: \"Building 1 - PG Block\" {\n"
        "  style: {\n"
        "    fill: \"#0f3460\"\n"
        "    stroke: \"#533483\"\n"
        "  }\n"
        "  dist_b1_sw1: \"Distribution\\nCX 6400\" {\n"
        "    style: {\n"
        "      fill: \"#16213e\"\n"
        "      stroke: \"#0f3460\"\n"
        "    }\n"
        "  }\n"
        "  d1_mca: \"Dept 1 - MCA\" {\n"
        "    style: {\n"
        "      fill: \"#1a1a40\"\n"
        "      stroke: \"#533483\"\n"
        "    }\n"
        "    acc_b1_d1_sw1: \"Access\\nCX 6200\" {\n"
        "      style: {\n"
        "        fill: \"#533483\"\n"
        "        stroke: \"#e94560\"\n"
        "      }\n"
        "    }\n"
        "    devices: \"End Devices\\nVLAN 10\\n200 Users\" {\n"
        "      style: {\n"
        "        fill: \"#e94560\"\n"
        "        stroke: \"#ff6b6b\"\n"
        "      }\n"
        "    }\n"
        "    wifi: \"Wi-Fi AP\\n8x AP\" {\n"
        "      style: {\n"
        "        fill: \"#4ecca3\"\n"
        "        stroke: \"#36b37e\"\n"
        "      }\n"
        "    }\n"
        "    acc_b1_d1_sw1 -> devices: Access\n"
        "    acc_b1_d1_sw1 -> wifi: PoE\n"
        "  }\n"
        "  dist_b1_sw1 -> d1_mca.acc_b1_d1_sw1: 10G\n"
        "}\n"
        "core_sw1 -> b1.dist_b1_sw1: 10G Fiber\n"
        "core_sw2 -> b1.dist_b1_sw1: 10G Fiber"
    ), llm=llm_qwen_coder,
)


agent5 = FunctionAgent(
    name="cli_config_generator",
    description="Generates per-switch CLI configuration commands from the approved topology and BOM.",
    system_prompt=(
        "You are a Senior Network Automation Engineer specializing in HPE Aruba CX switches.\n\n"
        "Your task is to generate a detailed, step-by-step CLI configuration for EVERY switch\n"
        "in the design. You will receive:\n"
        "1. The approved network topology (tier model, VLAN plan, HA design)\n"
        "2. The Bill of Materials (switch models, roles, quantities per building/department)\n"
        "3. The D2 diagram code (visual topology reference)\n\n"
        "MANDATORY: You MUST use the 'search_config_guides' tool to verify the exact CLI syntax\n"
        "for every feature you configure. Do NOT guess CLI commands — always verify with\n"
        "the AOS-CX configuration guides. Search for:\n"
        "  - VSF configuration (member numbering, link, split-detection)\n"
        "  - VSX configuration (keepalive, link, active-gateway, inter-switch linking)\n"
        "  - VLAN configuration (creation, trunk/access ports, allowed VLANs)\n"
        "  - LAG/LACP configuration and interface binding\n"
        "  - QoS configuration (trust, schedule-profile, queue profiles)\n"
        "  - SNMP and management access configuration\n"
        "  - Spanning Tree (MSTP/RSTP) configuration\n"
        "  - OSPF/BGP routing configuration if applicable\n\n"
        "OUTPUT FORMAT — Group by building, then by switch role, then per-switch:\n\n"
        "---\n"
        "## Building: <building name>\n"
        "\n"
        "### Switch: <hostname> — <role> (<model>)\n"
        "```\n"
        "configure terminal\n"
        "hostname <hostname>\n"
        "...\n"
        "end\n"
        "write memory\n"
        "```\n"
        "\n"
        "Configuration blocks per switch (in this order):\n"
        "1. **Base config**: hostname, enable password, banner, NTP, DNS\n"
        "2. **VSF/VSX config**: member number (VSF), keepalive+link (VSX), active-gateway\n"
        "3. **VLANs**: create VLANs per the approved VLAN plan with names\n"
        "4. **Interfaces**: assign VLANs to access/trunk ports, LAG members, LACP\n"
        "5. **LAG**: port-channel creation, member interfaces, allowed VLANs\n"
        "6. **Routing**: VLAN interfaces (SVIs), OSPF/BGP config where applicable\n"
        "7. **QoS**: trust settings, queue profiles for VOICE/VIDEO/DATA\n"
        "8. **Management**: SNMP, SSH, AAA, logging\n"
        "9. **Spanning Tree**: MSTP region config, root priority per VLAN\n"
        "10. **Verification**: show commands to validate the config\n\n"
        "RULES:\n"
        "- Use the exact VLAN numbers and subnetting from the approved topology\n"
        "- Use the exact switch models from the BOM\n"
        "- Include EVERY switch from the design — core, distribution, and access\n"
        "- Make configurations production-ready with proper interface descriptions\n"
        "- Group switches by building, then by layer (core → distribution → access)\n"
        "- Use only AOS-CX CLI syntax — verify EVERY command type with search_config_guides\n"
        "- If you're unsure about a command, search the config guides\n"
    ), llm=llm_qwen_coder, tools=[config_guide_tool],
)


PHASES = [
    (1, "Prompt Rephrasing", agent1),
    (2, "Network Topology Design", agent2),
    (3, "Device Selection & BOM", agent3),
    (4, "D2 Diagram Generation", agent4),
    (5, "CLI Configuration Generation", agent5),
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

def _format_tool_events(events: list[dict]) -> str:
    if not events:
        return "_(no tool calls)_\n"
    lines: list[str] = []
    for ev in events:
        name = ev.get("tool_name", "?")
        inp = ev.get("input", "")
        out = ev.get("output", "")
        lines.append(f"### {name}\n")
        lines.append(f"**Input:**\n```\n{inp}\n```\n")
        lines.append(f"**Output:**\n```\n{_strip_ansi(out)}\n```\n")
    return "\n".join(lines)


def _save(prompt, rephrased, topology, devices, diagram_code="", diagram_url=None,
          tools_1=None, tools_2=None, tools_3=None, tools_4=None, tools_5=None,
          cli_config=""):
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
    if cli_config:
        content += f"\n---\n\n## Phase 5: CLI Configuration\n\n{_strip_ansi(cli_config)}\n"
    fp.write_text(content, encoding="utf-8")
    return fp

# ── Kafka Task Processor ──────────────────────────
kafka_mgr = KafkaManager()

async def process_kafka_task(task_data: dict):
    project_id = task_data.get("project_id")
    task_id = task_data.get("task_id")
    phase_idx = task_data.get("phase", 1)
    input_ctx = task_data.get("input_context")
    history = task_data.get("history", [])

    # Find the agent for this phase
    matching_phases = [p for p in PHASES if p[0] == phase_idx]
    if not matching_phases:
        await kafka_mgr.send_event({
            "project_id": project_id, "task_id": task_id, "agent_name": "system",
            "event_type": "error", "data": f"Invalid phase: {phase_idx}", "is_final": True
        })
        return

    _, phase_name, agent = matching_phases[0]
    await _run_phase_kafka(kafka_mgr, project_id, task_id, phase_idx, phase_name, agent, input_ctx, history, model_name=OLLAMA_MODEL)

# ── FastAPI ───────────────────────────────────────
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await kafka_mgr.start()
    asyncio.create_task(kafka_mgr.consume_tasks(process_kafka_task))
    yield
    # Shutdown
    await kafka_mgr.stop()

app = FastAPI(title="Network Automation Assistant", lifespan=lifespan)
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

async def _run_phase(ws, phase_num, phase_name, agent, initial_msg, model_name=""):
    """Run one agent phase with event streaming and HITL approval.

    Returns
    -------
    tuple[str, list[dict]]
        (response_text, tool_events) where each tool_event has
        ``tool_name``, ``input``, and ``output`` keys.
    """
    wf = AgentWorkflow(agents=[agent], root_agent=agent.name, timeout=400.0)
    history: list[ChatMessage] = []
    msg = initial_msg
    iteration = 0
    tool_events: list[dict] = []

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
                        await _send(ws, type="agent_input", agent=ev.current_agent_name, model=model_name)
                    elif isinstance(ev, ToolCall):
                        await _send(ws, type="tool_call", tool_name=ev.tool_name, tool_kwargs=ev.tool_kwargs)
                    elif isinstance(ev, ToolCallResult):
                        out = str(ev.tool_output)
                        # Collect for save
                        tool_events.append({
                            "tool_name": ev.tool_name,
                            "input": str(getattr(ev, "tool_kwargs", ev.tool_name)),
                            "output": out,
                        })
                        if ev.tool_name in ("search_product_specs", "search_across_products"):
                            chunks = _parse_chunks(out)
                            await _send(ws, type="rag_result", tool_name=ev.tool_name, chunks=chunks, total=len(chunks))
                        elif ev.tool_name == "search_config_guides":
                            await _send(ws, type="config_rag_result", tool_name=ev.tool_name, output=out, total_chars=len(out))
                        else:
                            await _send(ws, type="tool_result", tool_name=ev.tool_name, output=out)
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
            return response_text, tool_events
        else:
            msg = data.get("feedback", "Please revise.")
            tool_events.append({
                "tool_name": "__revision_request__",
                "input": msg,
                "output": f"Phase {phase_num} revised with feedback",
            })
            await _send(ws, type="phase_revision", phase=phase_num, feedback=msg)

async def _run_phase_kafka(kafka_mgr, project_id, task_id, phase_num, phase_name, agent, initial_msg, history=None, model_name=""):
    """Run one agent phase and stream events to Kafka."""
    print(f"\n=== START PHASE {phase_num}: {phase_name} ===", flush=True)
    print(f"Project: {project_id}", flush=True)
    print(f"Task: {task_id}", flush=True)
    print(f"Agent: {agent.name}", flush=True)
    wf = AgentWorkflow(agents=[agent], root_agent=agent.name, timeout=400.0)
    # Convert history dicts to ChatMessage objects if provided
    chat_history = []
    if history:
        for h in history:
            role = MessageRole.USER if str(h.get("role")).upper() == "USER" else MessageRole.ASSISTANT
            chat_history.append(ChatMessage(role=role, content=h.get("content", "")))
    
    await kafka_mgr.send_event({
        "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
        "event_type": "TOKEN", "data": f"Starting phase {phase_num}: {phase_name}", "is_final": False
    })

    try:
        if chat_history:
            handler = wf.run(chat_history=chat_history + [ChatMessage(role=MessageRole.USER, content=initial_msg)])
        else:
            handler = wf.run(user_msg=initial_msg)

        async for ev in handler.stream_events():
            base_event = {"project_id": project_id, "task_id": task_id, "agent_name": agent.name, "is_final": False}
            if isinstance(ev, AgentInput):
                pass # Already sent start event
            elif isinstance(ev, ToolCall):
                await kafka_mgr.send_event({**base_event, "event_type": "TOOL_CALL", "payload": {"name": ev.tool_name, "args": ev.tool_kwargs}})
            elif isinstance(ev, ToolCallResult):
                await kafka_mgr.send_event({**base_event, "event_type": "TOOL_RESULT", "payload": {"name": ev.tool_name, "output": str(ev.tool_output)}})
            elif isinstance(ev, AgentOutput):
                if not ev.tool_calls:
                    await kafka_mgr.send_event({**base_event, "event_type": "TOKEN", "data": str(ev.response)})

        resp = await handler
        await kafka_mgr.send_event({
            "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
            "event_type": "FINAL_ANSWER", "data": str(resp), "is_final": True
        })
        return str(resp)
    except Exception as e:
        await kafka_mgr.send_event({
            "project_id": project_id, "task_id": task_id, "agent_name": agent.name,
            "event_type": "ERROR", "data": str(e), "is_final": True
        })
        raise e

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        data = json.loads(await ws.receive_text())
        prompt = data["content"]
        await _send(ws, type="user_echo", content=prompt)

        rephrased, tools_1 = await _run_phase(ws, 1, "Prompt Rephrasing", agent1, prompt, model_name=OLLAMA_MODEL)
        topology, tools_2 = await _run_phase(ws, 2, "Network Topology Design", agent2, rephrased, model_name=OLLAMA_MODEL)
        ctx = f"## Refined Requirements\n{rephrased}\n\n## Approved Topology\n{topology}"
        devices, tools_3 = await _run_phase(ws, 3, "Device Selection & BOM", agent3, ctx, model_name=OLLAMA_MODEL)

        # Phase 4: D2 Diagram Generation
        d2_ctx = f"## Approved Topology\n{topology}\n\n## Bill of Materials\n{devices}"
        diagram_code, tools_4 = await _run_phase(ws, 4, "D2 Diagram Generation", agent4, d2_ctx, model_name="gpt-oss-120b")

        # Render D2 code via Image Generation Service (non-agent step)
        diagram_url = None
        await _send(ws, type="phase_start", phase="diagram", name="Rendering Topology Diagram", iteration=1)
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
                            message=result.get("error", "Unknown error from image service"),
                            diagram_code=result.get("diagram_code", ""))
        except Exception as img_err:
            await _send(ws, type="diagram_error",
                        message=f"Image service unavailable: {str(img_err)}")

        # Phase 5: CLI Configuration Generation
        cli_ctx = (
            f"## Approved Topology\n{topology}\n\n"
            f"## Bill of Materials\n{devices}\n\n"
            f"## D2 Diagram Code\n```d2\n{diagram_code}\n```"
        )
        cli_config, tools_5 = await _run_phase(ws, 5, "CLI Configuration Generation", agent5, cli_ctx, model_name="qwen3-coder:480b-cloud")

        fp = _save(prompt, rephrased, topology, devices, diagram_code, diagram_url,
                    tools_1, tools_2, tools_3, tools_4, tools_5, cli_config)
        await _send(ws, type="workflow_complete", saved_to=str(fp),
                    diagram_url=diagram_url,
                    has_cli_config=bool(cli_config))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await _send(ws, type="error", message=str(e))
        except:
            pass
