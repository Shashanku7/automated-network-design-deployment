import os, sys
from pathlib import Path

from llama_index.llms.ollama import Ollama
from llama_index.storage.chat_store.postgres import PostgresChatStore
from config import (
    OLLAMA_API_KEY,
    OLLAMA_MODEL,
    OLLAMA_BASE_URL,
    QWEN_CODE_MODEL,
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

# LLM Init
def _create_llm(model: str) -> Ollama:
    return Ollama(
        model=model,
        base_url=OLLAMA_BASE_URL,
        request_timeout=400.0,
        context_window=262144,
        is_function_calling_model=True,
        headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
    )

llm = _create_llm(OLLAMA_MODEL)

llm_qwen_coder = _create_llm(QWEN_CODE_MODEL)

# Qdrant client (singleton)
_qdrant_client = create_qdrant_client()

# PostgresChatStore (persistent chat/phase memory)
chat_store = PostgresChatStore.from_uri(uri=POSTGRES_URI)
