"""
Shared configuration and utilities for the RAG pipeline.

Single source of truth for environment variables, embedding model,
and Qdrant client.
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from qdrant_client import QdrantClient, models

# ──────────────────────────────────────────────
# Environment
# ──────────────────────────────────────────────
dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

QWEN_EMBEDDING_MODEL = os.getenv("QWEN_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "qwen-tech-docs")
QDRANT_CONFIG_COLLECTION = os.getenv("QDRANT_CONFIG_COLLECTION", "qwen-config-guides")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://api.ollama.com")
IMAGE_SERVICE_URL = os.getenv("IMAGE_SERVICE_URL", "http://localhost:8001")
TOPOLOGY_SERVICE_URL = os.getenv("TOPOLOGY_SERVICE_URL", "http://localhost:8002")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_AGENT_TASKS = os.getenv("TOPIC_AGENT_TASKS", "agent-tasks")
TOPIC_AGENT_EVENTS = os.getenv("TOPIC_AGENT_EVENTS", "agent-events")

# PostgreSQL chat store
POSTGRES_URI = os.getenv("POSTGRES_URI", "postgresql+asyncpg://postgres:password@localhost:5433/network_design")
CHAT_TOKEN_LIMIT = int(os.getenv("CHAT_TOKEN_LIMIT", "3000"))

# ──────────────────────────────────────────────
# RAG constants
# ──────────────────────────────────────────────
EMBEDDING_MAX_TOKENS = 1536
CHUNK_MAX_TOKENS = 1024         # HybridChunker target (fits within embedding limit)
RETRIEVAL_TOP_K = 25            # Consistent across all retrieval paths
MIN_SCORE_THRESHOLD = 0.25      # Drop chunks below this relevance score
MIN_CHUNK_LENGTH = 200           # Drop chunks shorter than this (chars)
TINY_CHUNK_MERGE_THRESHOLD = 400 # Merge chunks shorter than this into predecessor

CONFIG_GUIDES_DIR = Path(__file__).resolve().parent / "config_guides"


# ──────────────────────────────────────────────
# Embedding model  (singleton — expensive to load)
# ──────────────────────────────────────────────
_embedding_model = None


def get_embedding_model() -> HuggingFaceEmbedding:
    """Return the shared embedding model, lazily initialized."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = HuggingFaceEmbedding(
            model_name=QWEN_EMBEDDING_MODEL,
            trust_remote_code=True,
            token=HUGGINGFACE_TOKEN,
            device=os.getenv("EMBEDDING_DEVICE", "cpu"),
            embed_batch_size=4,
            show_progress_bar=True,
        )
    return _embedding_model


# ──────────────────────────────────────────────
# Qdrant client
# ──────────────────────────────────────────────
def create_qdrant_client() -> QdrantClient:
    """Create a Qdrant client from environment config."""
    if QDRANT_URL is None or QDRANT_API_KEY is None:
        raise ValueError(
            "Set QDRANT_URL and QDRANT_API_KEY environment variables before running."
        )
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=120)


# ──────────────────────────────────────────────
# Sparse vectors (Qdrant-native TF-IDF, no state)
# ──────────────────────────────────────────────
_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def text_to_sparse_vector(text: str) -> models.SparseVector:
    """
    Convert text to a sparse vector via term-frequency hashing.

    No vocabulary/state needed — tokens are mapped to indices via
    hash, so documents and queries are always consistent. Qdrant
    applies IDF weighting natively via ``Modifier.IDF`` at search time.
    """
    tokens = [t for t in _SPLIT_RE.split(text.lower()) if len(t) > 2]
    tf: dict[str, int] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    indices = [hash(t) & 0x7FFFFFFF for t in tf]
    values = [float(v) for v in tf.values()]
    if not indices:
        indices = [0]
        values = [0.0]
    return models.SparseVector(indices=indices, values=values)


# ──────────────────────────────────────────────
# Product model extraction from filenames
# ──────────────────────────────────────────────
_CX_MODEL_RE = re.compile(r"CX\s*\d+\w*")


def extract_product_model(source_path: str) -> str:
    """Extract the HPE CX product model from a source filename.

    Example: 'HPE Aruba Networking CX 6200 Switch Series-...'  →  'CX 6200'
    """
    match = _CX_MODEL_RE.search(source_path)
    return match.group(0) if match else ""
