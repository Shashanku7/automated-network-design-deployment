import argparse
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector
from llama_index.core.indices.vector_store.base import VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

QWEN_EMBEDDING_MODEL = os.getenv("QWEN_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "qwen-tech-docs")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

SPARSE_TOP_K = 100

if QDRANT_URL is None or QDRANT_API_KEY is None:
    raise ValueError("Set QDRANT_URL and QDRANT_API_KEY environment variables before running.")

hf_auth_kwargs = {"trust_remote_code": True}
if HUGGINGFACE_TOKEN:
    hf_auth_kwargs["token"] = HUGGINGFACE_TOKEN

embedding_model = HuggingFaceEmbedding(
    model_name=QWEN_EMBEDDING_MODEL,
    trust_remote_code=True,
    token=HUGGINGFACE_TOKEN,
    device=os.getenv("EMBEDDING_DEVICE", "cpu"),
)


def encode_sparse_doc(text: str, top_k: int = SPARSE_TOP_K) -> SparseVector:
    embedding = embedding_model.get_text_embedding(text)
    embedding_array = np.array(embedding)
    
    top_indices = np.argsort(np.abs(embedding_array))[-top_k:]
    top_values = embedding_array[top_indices]
    
    normalized = top_values / (np.linalg.norm(top_values) + 1e-8)
    
    return SparseVector(
        indices=top_indices.tolist(),
        values=normalized.tolist(),
    )


encode_sparse_query = encode_sparse_doc


def create_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def create_vector_store(client: QdrantClient) -> QdrantVectorStore:
    return QdrantVectorStore(
        collection_name=QDRANT_COLLECTION_NAME,
        client=client,
        enable_hybrid=True,
        sparse_doc_fn=encode_sparse_doc,
        sparse_query_fn=encode_sparse_query,
        dense_vector_name="dense",
        sparse_vector_name="sparse",
    )


def create_vector_index(vector_store: QdrantVectorStore) -> VectorStoreIndex:
    return VectorStoreIndex.from_vector_store(vector_store, embed_model=embedding_model)


def create_retriever(index: VectorStoreIndex):
    return index.as_retriever(similarity_top_k=5)


def query_switch_details(question: str) -> str:
    client = create_qdrant_client()
    vector_store = create_vector_store(client)
    index = create_vector_index(vector_store)
    retriever = create_retriever(index)
    nodes = retriever.retrieve(question)
    
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