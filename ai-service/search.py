"""Bridge between raw Qdrant client and LlamaIndex vector-store index.

Provides the two helpers used by app.py for creating retrievers.
"""

from config import QDRANT_COLLECTION, get_embedding_model


def create_vector_store(qdrant_client):
    """Wrap a QdrantClient in a LlamaIndex QdrantVectorStore."""
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    return QdrantVectorStore(client=qdrant_client, collection_name=QDRANT_COLLECTION)


def create_vector_index(vector_store):
    """Build a VectorStoreIndex from an existing vector store."""
    from llama_index.core import VectorStoreIndex
    return VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=get_embedding_model(),
    )
