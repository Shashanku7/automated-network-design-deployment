import os, sys
from pathlib import Path
from llama_index.llms.ollama import Ollama
from config import (
    OLLAMA_API_KEY,
    OLLAMA_MODEL,
    OLLAMA_BASE_URL,
    IMAGE_SERVICE_URL,
)

# Paths
WEBAPP_DIR = Path(__file__).resolve().parent
ROOT_DIR = WEBAPP_DIR.parent
OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
STATIC_DIR = WEBAPP_DIR / "static"

# LLM Init
llm = Ollama(
    model=OLLAMA_MODEL, 
    base_url=OLLAMA_BASE_URL,
    request_timeout=400.0, 
    context_window=262144,
    is_function_calling_model=True,
    headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
)

llm_qwen_coder = Ollama(
    model="qwen3-coder:480b-cloud", 
    base_url=OLLAMA_BASE_URL,
    request_timeout=400.0, 
    context_window=262144,
    is_function_calling_model=True,
    headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
)