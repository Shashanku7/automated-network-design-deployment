"""Bridge between raw Qdrant client and LlamaIndex vector-store index.

Provides the two helpers used by app.py for creating retrievers.
Enables hybrid search (dense + BM25 sparse) for better retrieval accuracy.
"""

from pathlib import Path

from config import QDRANT_COLLECTION, get_embedding_model, BM25SparseEncoder


# Load the fitted BM25 encoder that was saved during ingestion
_BM25_STATE_PATH = Path(__file__).resolve().parent / "bm25_state.json"
_BM25_ENCODER = None


def _get_bm25_encoder() -> BM25SparseEncoder:
    global _BM25_ENCODER
    if _BM25_ENCODER is None:
        _BM25_ENCODER = BM25SparseEncoder.load(_BM25_STATE_PATH)
    return _BM25_ENCODER


def _sparse_query(text: str):
    """Convert query text to BM25 sparse vector for hybrid search."""
    return _get_bm25_encoder().encode(text)


def create_vector_store(qdrant_client, collection_name=QDRANT_COLLECTION):
    """Wrap a QdrantClient in a LlamaIndex QdrantVectorStore with hybrid search."""
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    return QdrantVectorStore(
        client=qdrant_client,
        collection_name=collection_name,
        enable_hybrid=True,
        sparse_doc_fn=_sparse_query,
        sparse_query_fn=_sparse_query,
        dense_vector_name="dense",
        sparse_vector_name="sparse",
    )


def create_vector_index(vector_store):
    """Build a VectorStoreIndex from an existing vector store."""
    from llama_index.core import VectorStoreIndex
    return VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=get_embedding_model(),
    )
