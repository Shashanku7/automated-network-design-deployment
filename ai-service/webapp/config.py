import os, sys
from pathlib import Path

import httpx
from llama_index.llms.ollama import Ollama
from llama_index.storage.chat_store.postgres import PostgresChatStore
from config import (
    OLLAMA_API_KEY,
    OLLAMA_MODEL,
    OLLAMA_BASE_URL,
    QWEN_CODE_MODEL,
    FALLBACK_OLLAMA_BASE_URL,
    FALLBACK_OLLAMA_API_KEY,
    IMAGE_SERVICE_URL,
    TOPOLOGY_SERVICE_URL,
    POSTGRES_URI,
    CHAT_TOKEN_LIMIT,
    create_qdrant_client,
)

# Webapp paths
WEBAPP_DIR = Path(__file__).resolve().parent
ROOT_DIR = WEBAPP_DIR.parent
OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
STATIC_DIR = WEBAPP_DIR / "static"

# ── Ollama endpoint resolution ─────────────────
def _resolve_ollama_endpoint():
    try:
        httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3.0).raise_for_status()
        print(f"Ollama reachable at {OLLAMA_BASE_URL}", flush=True)
        return OLLAMA_BASE_URL, OLLAMA_API_KEY
    except Exception:
        print(
            f"Ollama {OLLAMA_BASE_URL} unreachable, "
            f"falling back to {FALLBACK_OLLAMA_BASE_URL}",
            flush=True,
        )
        return FALLBACK_OLLAMA_BASE_URL, FALLBACK_OLLAMA_API_KEY

_resolved_base_url, _resolved_api_key = _resolve_ollama_endpoint()

# LLM Init
def _create_llm(model: str) -> Ollama:
    kwargs = dict(
        model=model,
        base_url=_resolved_base_url,
        request_timeout=400.0,
        context_window=262144,
        is_function_calling_model=True,
        temperature=0.4,
    )
    if _resolved_api_key:
        kwargs["headers"] = {"Authorization": f"Bearer {_resolved_api_key}"}
    return Ollama(**kwargs)

llm = _create_llm(OLLAMA_MODEL)

llm_qwen_coder = _create_llm(QWEN_CODE_MODEL)

# Qdrant client (singleton)
_qdrant_client = create_qdrant_client()

# PostgresChatStore (persistent chat/phase memory)
chat_store = PostgresChatStore.from_uri(uri=POSTGRES_URI)
