"""
Shared configuration and utilities for the RAG pipeline.

Single source of truth for environment variables, embedding model,
Qdrant client, and sparse vector construction.
"""

import math
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from llama_index.embeddings.ollama import OllamaEmbedding
from qdrant_client import QdrantClient, models
from qdrant_client.models import SparseVector

# ──────────────────────────────────────────────
# Environment
# ──────────────────────────────────────────────
dotenv_path = Path(__file__).resolve().parent.parent / ".env"
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
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_AGENT_TASKS = "agent-tasks"
TOPIC_AGENT_EVENTS = "agent-events"

# ──────────────────────────────────────────────
# RAG constants
# ──────────────────────────────────────────────
EMBEDDING_MAX_TOKENS = 1536
CHUNK_MAX_TOKENS = 1024         # HybridChunker target (fits within embedding limit)
RETRIEVAL_TOP_K = 25            # Consistent across all retrieval paths
MIN_SCORE_THRESHOLD = 0.25      # Drop chunks below this relevance score
MIN_CHUNK_LENGTH = 50           # Drop chunks shorter than this (chars)

# ──────────────────────────────────────────────
# Embedding model  (singleton — expensive to load)
# ──────────────────────────────────────────────
_embedding_model = None
_embedding_model_checked = False


def get_embedding_model():
    """
    Returns the shared HuggingFace embedding model, lazily initialized.

    Auto-detects CUDA GPU availability:
      - GPU present  → loads the full local Qwen3-AWQ model for proper RAG search.
      - CPU only     → returns None; callers fall back to fast keyword scroll search.
    """
    global _embedding_model, _embedding_model_checked
    if _embedding_model_checked:
        return _embedding_model
    _embedding_model_checked = True

    import torch
    if not torch.cuda.is_available():
        print(
            "[Embedding] No CUDA GPU detected — skipping heavy Qwen3 model. "
            "Falling back to keyword-based search (fast, CPU-friendly)."
        )
        return None

    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    print(f"[Embedding] CUDA GPU detected! Loading local model from {QWEN_EMBEDDING_MODEL}...")
    _embedding_model = HuggingFaceEmbedding(
        model_name=QWEN_EMBEDDING_MODEL,
        trust_remote_code=True,
        token=HUGGINGFACE_TOKEN,
        device="cuda",
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
        print("WARNING: QDRANT_URL or QDRANT_API_KEY not set. Falling back to local in-memory Qdrant database.")
        return QdrantClient(":memory:")
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


# ──────────────────────────────────────────────
# BM25 Sparse Vectors  (replaces the fake dense→sparse conversion)
# ──────────────────────────────────────────────
# Simple tokenizer for BM25: lowercase, split on non-alphanumeric, drop short tokens
_BM25_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def _bm25_tokenize(text: str) -> list[str]:
    """Tokenize text for BM25: lowercase, split on non-alnum, drop <=2 char tokens."""
    return [t for t in _BM25_SPLIT_RE.split(text.lower()) if len(t) > 2]


class BM25SparseEncoder:
    """
    Builds BM25-based sparse vectors for true keyword/lexical matching.

    Vocabulary is built from the corpus at index time. At query time,
    only tokens present in the vocabulary are encoded — unknown tokens
    are ignored (which is the correct BM25 behaviour).

    Parameters
    ----------
    k1 : float
        BM25 term-frequency saturation parameter (default 1.5).
    b : float
        BM25 document-length normalisation parameter (default 0.75).
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.vocab: dict[str, int] = {}          # token → integer index
        self.idf: dict[str, float] = {}          # token → IDF weight
        self.avg_dl: float = 0.0                 # average document length
        self._fitted = False

    # ── Fit (index time) ────────────────────────

    def fit(self, documents: list[str]) -> "BM25SparseEncoder":
        """
        Build vocabulary and compute IDF from a list of document texts.
        Call this once after chunking, before encoding.
        """
        n_docs = len(documents)
        doc_freq: Counter = Counter()
        total_len = 0

        for doc in documents:
            tokens = _bm25_tokenize(doc)
            total_len += len(tokens)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                doc_freq[token] += 1

        self.avg_dl = total_len / max(n_docs, 1)

        # Build vocab (sorted for deterministic indices)
        self.vocab = {token: idx for idx, token in enumerate(sorted(doc_freq.keys()))}

        # IDF with smoothing: log((N - df + 0.5) / (df + 0.5) + 1)
        for token, df in doc_freq.items():
            self.idf[token] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)

        self._fitted = True
        return self

    # ── Encode (index + query time) ─────────────

    def encode(self, text: str) -> SparseVector:
        """
        Encode a single text into a BM25 sparse vector.
        Works for both documents (after fit) and queries.
        """
        if not self._fitted:
            raise RuntimeError("Call .fit(documents) before .encode()")

        tokens = _bm25_tokenize(text)
        doc_len = len(tokens)
        tf_counts = Counter(tokens)

        indices: list[int] = []
        values: list[float] = []

        for token, tf in tf_counts.items():
            if token not in self.vocab:
                continue  # Skip tokens not in the index vocabulary

            idx = self.vocab[token]
            idf = self.idf.get(token, 0.0)

            # BM25 score for this term
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avg_dl, 1))
            score = idf * numerator / denominator

            if score > 0:
                indices.append(idx)
                values.append(score)

        # Handle edge case: no valid tokens
        if not indices:
            indices = [0]
            values = [0.0]

        return SparseVector(indices=indices, values=values)

    def encode_batch(self, texts: list[str]) -> list[SparseVector]:
        """Encode a batch of texts into sparse vectors."""
        return [self.encode(text) for text in texts]

    # ── Persistence ─────────────────────────────

    def save(self, path: Path) -> None:
        """Save the fitted encoder state to a JSON file."""
        import json
        state = {
            "vocab": self.vocab,
            "idf": self.idf,
            "avg_dl": self.avg_dl,
            "k1": self.k1,
            "b": self.b,
        }
        path.write_text(json.dumps(state), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "BM25SparseEncoder":
        """Load a fitted encoder from a JSON file."""
        import json
        state = json.loads(path.read_text(encoding="utf-8"))
        encoder = cls(k1=state["k1"], b=state["b"])
        encoder.vocab = state["vocab"]
        encoder.idf = state["idf"]
        encoder.avg_dl = state["avg_dl"]
        encoder._fitted = True
        return encoder


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
