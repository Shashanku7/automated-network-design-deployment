"""
Search / retrieval module for the RAG knowledge base.

Provides hybrid retrieval (dense + BM25 sparse) against the Qdrant
vector store. Used by both the CLI and the multi-agent workflow.
"""

import argparse
import os
from pathlib import Path

from llama_index.core.indices.vector_store.base import VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore

from config import (
    QDRANT_COLLECTION,
    RETRIEVAL_TOP_K,
    MIN_SCORE_THRESHOLD,
    get_embedding_model,
    create_qdrant_client,
    BM25SparseEncoder,
)

# ── BM25 encoder (loaded from state saved at ingest time) ─────
BM25_STATE_PATH = Path(__file__).resolve().parent / "bm25_state.json"

_bm25_encoder = None


def _get_bm25_encoder() -> BM25SparseEncoder:
    """Lazily load the BM25 encoder from the saved state file."""
    global _bm25_encoder
    if _bm25_encoder is None:
        if not BM25_STATE_PATH.exists():
            raise FileNotFoundError(
                f"BM25 state file not found at {BM25_STATE_PATH}. "
                f"Run ingest.py first to build the BM25 vocabulary."
            )
        _bm25_encoder = BM25SparseEncoder.load(BM25_STATE_PATH)
    return _bm25_encoder


# ── Sparse encoding functions for QdrantVectorStore ───────────

def encode_sparse_doc(text: str):
    """Encode a document text into a BM25 sparse vector."""
    return _get_bm25_encoder().encode(text)


def encode_sparse_query(text: str):
    """Encode a query text into a BM25 sparse vector."""
    return _get_bm25_encoder().encode(text)


# ── Retriever setup ──────────────────────────────────────────

embedding_model = get_embedding_model()


def create_vector_store(client=None) -> QdrantVectorStore:
    """Create a QdrantVectorStore with hybrid (dense + BM25 sparse) search."""
    if client is None:
        client = create_qdrant_client()
    return QdrantVectorStore(
        collection_name=QDRANT_COLLECTION,
        client=client,
        enable_hybrid=True,
        sparse_doc_fn=encode_sparse_doc,
        sparse_query_fn=encode_sparse_query,
        dense_vector_name="dense",
        sparse_vector_name="sparse",
    )


def create_vector_index(vector_store: QdrantVectorStore) -> VectorStoreIndex:
    return VectorStoreIndex.from_vector_store(vector_store, embed_model=embedding_model)


def create_retriever(index: VectorStoreIndex, top_k: int = RETRIEVAL_TOP_K):
    return index.as_retriever(
        similarity_top_k=top_k,
        vector_store_query_mode="hybrid",  # enable dense + sparse (BM25) search
    )


def query_switch_details(question: str) -> str:
    """Run a hybrid retrieval query and return formatted results."""
    client = create_qdrant_client()
    vector_store = create_vector_store(client)
    index = create_vector_index(vector_store)
    retriever = create_retriever(index)
    nodes = retriever.retrieve(question)

    # Filter out low-relevance results
    nodes = [n for n in nodes if n.score >= MIN_SCORE_THRESHOLD]

    results = []
    for i, node in enumerate(nodes, 1):
        results.append(f"--- Result {i} ---\n{node.text}\n")

    return "\n".join(results)


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the Qwen tech docs collection.")
    parser.add_argument(
        "--query",
        type=str,
        default="What information is available in the Qwen technical documentation?",
        help="Question to ask about the Qwen technical documentation.",
    )
    args = parser.parse_args()

    answer = query_switch_details(args.query)
    print("\n=== Search Result ===")
    print(answer)


if __name__ == "__main__":
    main()