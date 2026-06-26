"""RAG tools, Firecrawl web search, and hybrid search for the multi-agent workflow."""

import os
import re
from pathlib import Path

from llama_index.core.tools import FunctionTool
from qdrant_client import models

from config import (
    QDRANT_COLLECTION,
    QDRANT_CONFIG_COLLECTION,
    RETRIEVAL_TOP_K,
    MIN_SCORE_THRESHOLD,
    extract_product_model,
    get_embedding_model,
    text_to_sparse_vector,
)
from webapp.config import _qdrant_client


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
_FIRECRAWL_BASE_URL = os.getenv("FIRECRAWL_BASE_URL", "http://localhost:3002")
_firecrawl_app = None


def _get_firecrawl_app():
    global _firecrawl_app
    if _firecrawl_app is None:
        from firecrawl import FirecrawlApp
        _firecrawl_app = FirecrawlApp(api_key="local", api_url=_FIRECRAWL_BASE_URL)
    return _firecrawl_app


def firecrawl_search(query: str, limit: int = 5) -> str:
    limit = min(limit, 10)
    try:
        app = _get_firecrawl_app()
        from firecrawl.v2.types import ScrapeOptions
        opts = ScrapeOptions(formats=["markdown"])
        result = app.search(query=query, limit=limit, scrape_options=opts)
    except Exception as exc:
        return f"[firecrawl_search error] {type(exc).__name__}: {exc}"

    items = getattr(result, "web", None) or getattr(result, "data", None) or []
    if not items:
        return f"[firecrawl_search] No results found for: {query}"

    lines: list[str] = [f"Firecrawl search results for query: '{query}'\n"]
    for i, item in enumerate(items, start=1):
        metadata = getattr(item, "metadata", item)
        title = getattr(metadata, "title", getattr(item, "title", "")) or ""
        url = getattr(metadata, "url", getattr(item, "url", "")) or ""
        desc = getattr(metadata, "description", getattr(item, "description", "")) or ""

        lines.append(f"--- Result {i} ---")
        lines.append(f"Title: {title}")
        lines.append(f"URL: {url}")
        if desc:
            lines.append(f"Summary: {desc}")

        md = getattr(item, "markdown", None)
        if md:
            lines.append(f"Content ({len(md)} chars):")
            lines.append(md)
        lines.append("")

    total_chars = sum(len(getattr(i, "markdown", "") or "") for i in items)
    lines.append(f"[Retrieved {len(items)} pages, {total_chars} total chars of content]")
    return "\n".join(lines)


firecrawl_search_tool = FunctionTool.from_defaults(
    fn=firecrawl_search,
    name="firecrawl_search",
    description="Search the web for current HPE Aruba product information",
)


# ── RAG Tools (multi-query strategy) ─────────────
def list_available_products() -> str:
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
