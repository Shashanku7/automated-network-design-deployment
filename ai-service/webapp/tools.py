import os
from llama_index.core.tools import FunctionTool
from config import (
    QDRANT_COLLECTION,
    RETRIEVAL_TOP_K,
    MIN_SCORE_THRESHOLD,
    create_qdrant_client,
    extract_product_model,
    get_embedding_model,
)
from search import create_vector_store, create_vector_index

_qdrant_client = create_qdrant_client()
_embed_model = get_embedding_model()  # None on CPU-only machines

def _build_retriever():
    """Build vector retriever if GPU embedding model is available, else return None."""
    if _embed_model is None:
        return None
    vs = create_vector_store(_qdrant_client)
    idx = create_vector_index(vs)
    return idx.as_retriever(similarity_top_k=RETRIEVAL_TOP_K)

_retriever = _build_retriever()

# Firecrawl
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
        result = app.search(query=query, limit=limit, timeout=15000, scrape_options=opts)
    except Exception as exc:
        return f"[firecrawl_search error] {type(exc).__name__}: {exc}"

    items = getattr(result, "web", None) or getattr(result, "data", None) or []
    if not items:
        return f"[firecrawl_search] No results found for: {query}"

    lines = [f"Firecrawl search results for query: '{query}'\n"]
    for i, item in enumerate(items, start=1):
        metadata = getattr(item, "metadata", item)
        title = getattr(metadata, "title", getattr(item, "title", "")) or ""
        url = getattr(metadata, "url", getattr(item, "url", "")) or ""
        desc = getattr(metadata, "description", getattr(item, "description", "")) or ""
        lines.extend([f"--- Result {i} ---", f"Title: {title}", f"URL: {url}"])
        if desc: lines.append(f"Summary: {desc}")
        md = getattr(item, "markdown", None)
        if md:
            lines.append(f"Content ({len(md)} chars):")
            lines.append(md[:4000])
        lines.append("")
    return "\n".join(lines)

firecrawl_search_tool = FunctionTool.from_defaults(
    fn=firecrawl_search, name="firecrawl_search",
    description="Search web for latest HPE Aruba info."
)

# RAG Tools
def list_available_products() -> str:
    results = _qdrant_client.scroll(
        collection_name=QDRANT_COLLECTION, limit=1000,
        with_payload=["product_model", "source"], with_vectors=False,
    )
    catalog = {}
    for point in results[0]:
        pm = point.payload.get("product_model", "Unknown")
        src = os.path.basename(point.payload.get("source", ""))
        if pm not in catalog: catalog[pm] = {"count": 0, "source": src}
        catalog[pm]["count"] += 1
    lines = ["Available HPE Aruba Networking Switch Families:\n"]
    for model in sorted(catalog.keys()):
        info = catalog[model]
        lines.append(f"  - {model}: {info['count']} datasheet chunks (source: {info['source']})")
    return "\n".join(lines)

def search_product_specs(product_model: str, query: str) -> str:
    MAX_RESULTS = 10

    # GPU path: proper RAG vector search
    if _retriever is not None:
        try:
            nodes = _retriever.retrieve(f"{product_model} {query}")
            matched = [n for n in nodes if n.metadata.get("product_model") == product_model]
        except: matched = []
    else:
        matched = []

    if not matched:
        raw = _qdrant_client.scroll(collection_name=QDRANT_COLLECTION, limit=1000, with_payload=True)[0]
        matched = [pt for pt in raw if pt.payload.get("product_model") == product_model]
        return "\n".join([f"--- {product_model} Chunk {i} ---\nSource: {os.path.basename(p.payload.get('source', 'unknown'))}\n{p.payload.get('text', '')}\n" for i, p in enumerate(matched[:MAX_RESULTS], 1)])

    return "\n".join([f"--- {product_model} Chunk {i} ---\nSource: {os.path.basename(n.metadata.get('source', 'unknown'))}\n{n.text}\n" for i, n in enumerate(matched[:MAX_RESULTS], 1)])

def search_across_products(query: str) -> str:
    if _retriever is None:
        # CPU fallback: keyword scroll across all docs
        raw = _qdrant_client.scroll(collection_name=QDRANT_COLLECTION, limit=500, with_payload=True)[0]
        kw = query.lower()
        matched = [pt for pt in raw if kw in pt.payload.get("text", "").lower()]
        parts = []
        for i, pt in enumerate(matched[:25], 1):
            pm = extract_product_model(pt.payload.get("source", ""))
            src = os.path.basename(pt.payload.get("source", "unknown"))
            parts.append(f"--- Chunk {i} [{pm}] ---\nSource: {src}\n{pt.payload.get('text', '')}\n")
        return "\n".join(parts)

    nodes = _retriever.retrieve(query)
    nodes = [n for n in nodes if n.score >= MIN_SCORE_THRESHOLD]
    parts = []
    for i, n in enumerate(nodes, 1):
        pm = extract_product_model(n.metadata.get("source", "unknown"))
        src_base = os.path.basename(n.metadata.get("source", "unknown"))
        parts.append(f"--- Chunk {i} [{pm}] ---\nSource: {src_base}\n{n.text}\n")
    return "\n".join(parts)

catalog_tool = FunctionTool.from_defaults(fn=list_available_products, name="list_available_products")
product_search_tool = FunctionTool.from_defaults(fn=search_product_specs, name="search_product_specs")
broad_search_tool = FunctionTool.from_defaults(fn=search_across_products, name="search_across_products")

def search_config_guides(query: str) -> str:
    from config import QDRANT_CONFIG_COLLECTION
    if _embed_model is None:
        # CPU fallback: keyword scroll
        try:
            raw = _qdrant_client.scroll(collection_name=QDRANT_CONFIG_COLLECTION, limit=500, with_payload=True)[0]
            kw = query.lower()
            matched = [pt for pt in raw if kw in pt.payload.get("text", "").lower()]
            if not matched:
                return f"No configuration guide results found for: {query}"
            parts = []
            for i, pt in enumerate(matched[:10], 1):
                src_base = os.path.basename(pt.payload.get("source", "unknown"))
                parts.append(f"--- Config Guide Chunk {i} ---\nSource: {src_base}\n{pt.payload.get('text', '')}\n")
            return "\n".join(parts)
        except Exception as exc:
            return f"[search_config_guides fallback error] {type(exc).__name__}: {exc}"

    try:
        vs = create_vector_store(_qdrant_client, collection_name=QDRANT_CONFIG_COLLECTION)
        idx = create_vector_index(vs)
        retriever = idx.as_retriever(similarity_top_k=RETRIEVAL_TOP_K)
        nodes = retriever.retrieve(query)
        matched = [n for n in nodes if n.score >= MIN_SCORE_THRESHOLD]
    except Exception as exc:
        return f"[search_config_guides error] {type(exc).__name__}: {exc}"
        
    if not matched:
        return f"No configuration guide results found for: {query}"
        
    parts = []
    for i, r in enumerate(matched, 1):
        src_base = os.path.basename(r.metadata.get("source", "unknown"))
        parts.append(f"--- Config Guide Chunk {i} (score: {r.score:.4f}) ---\nSource: {src_base}\n{r.text}\n")
    return "\n".join(parts)

config_guide_tool = FunctionTool.from_defaults(
    fn=search_config_guides, name="search_config_guides",
    description=(
        "Search AOS-CX configuration guides for CLI command syntax, feature "
        "configuration steps, and best practices. Use for writing accurate "
        "CLI configuration commands for each switch in the design."
    ),
)
