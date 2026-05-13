import os
from pathlib import Path
from typing import Iterable
import uuid

from dotenv import load_dotenv

from llama_index.core.schema import MetadataMode
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.readers.docling import DoclingReader
from llama_index.node_parser.docling import DoclingNodeParser
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.transforms.chunker.line_chunker import LineBasedTokenChunker
from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
)
from docling_core.transforms.serializer.markdown import (
    MarkdownParams,
    MarkdownTableSerializer,
)

try:
    from qdrant_client import QdrantClient, models
    from qdrant_client.models import Distance, PointStruct, VectorParams
except ImportError as exc:
    raise ImportError(
        "Please install qdrant-client to run this script: pip install qdrant-client"
    ) from exc

from sklearn.feature_extraction.text import TfidfVectorizer

# ============================================================================
# Custom Serializer for Improved Table Formatting
# ============================================================================
class OptimizedTableSerializerProvider(ChunkingSerializerProvider):
    """
    Custom serializer provider that uses optimized Markdown formatting for tables.
    This ensures tables are rendered compactly while maintaining readability.
    """
    def get_serializer(self, doc):
        return ChunkingDocSerializer(
            doc=doc,
            table_serializer=MarkdownTableSerializer(),
            params=MarkdownParams(
                compact_tables=True,  # Compact table format for embedding
            ),
        )

dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

QWEN_EMBEDDING_MODEL = os.getenv("QWEN_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
QWEN_EMBEDDING_MAX_TOKENS = 4096
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "qwen-tech-docs")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
DATA_DIR = Path("data")
PDF_PATTERN = "*.pdf"

if QDRANT_URL is None or QDRANT_API_KEY is None:
    raise ValueError(
        "Set QDRANT_URL and QDRANT_API_KEY environment variables before running."
    )

hf_auth_kwargs = {"trust_remote_code": True}
if HUGGINGFACE_TOKEN:
    hf_auth_kwargs["token"] = HUGGINGFACE_TOKEN

reader = DoclingReader(
    export_type=DoclingReader.ExportType.JSON
)

try:
    qwen_tokenizer = HuggingFaceTokenizer.from_pretrained(
        QWEN_EMBEDDING_MODEL,
        max_tokens=QWEN_EMBEDDING_MAX_TOKENS,
        **hf_auth_kwargs,
    )
except Exception as exc:
    raise RuntimeError(
        "Unable to load the Qwen tokenizer. If the model is private, set HUGGINGFACE_TOKEN."
    ) from exc

node_parser = DoclingNodeParser(
    chunker=LineBasedTokenChunker(
        tokenizer=qwen_tokenizer,
        max_tokens=512,  # Smaller chunks for better table handling
        repeat_prefix="**Table Context:** ",  # Prefix for table chunks
        omit_prefix_on_overflow=True,  # Skip prefix if it would overflow
    )
)

embedding_model = HuggingFaceEmbedding(
    model_name=QWEN_EMBEDDING_MODEL,
    trust_remote_code=True,
    token=HUGGINGFACE_TOKEN,
    device=os.getenv("EMBEDDING_DEVICE", "cpu"),
    embed_batch_size=4,
    show_progress_bar=True,
)


def build_sparse_vectors(texts: list[str]) -> list[models.SparseVector]:
    vectorizer = TfidfVectorizer(stop_words="english", max_features=32768)
    matrix = vectorizer.fit_transform(texts)
    sparse_vectors = []
    for row in matrix:
        row = row.tocsr()
        sparse_vectors.append(
            models.SparseVector(
                indices=row.indices.tolist(),
                values=row.data.tolist(),
            )
        )
    return sparse_vectors


def get_pdf_paths(data_dir: Path) -> list[Path]:
    pdf_paths = sorted(data_dir.glob(PDF_PATTERN))
    if not pdf_paths:
        raise FileNotFoundError(f"No PDF files found in {data_dir.resolve()}")
    return pdf_paths


def load_pdf_documents(pdf_paths: Iterable[Path]):
    """
    Load PDF documents using DoclingReader.
    
    The JSON export preserves:
    - Document structure (sections, headings)
    - Table structure and content
    - Page layout information
    - Reading order
    """
    documents = []
    for pdf_path in pdf_paths:
        print(f"Loading: {pdf_path.name}")
        documents.extend(
            reader.load_data(pdf_path, extra_info={"source": str(pdf_path)})
        )
    return documents


def chunk_documents(documents):
    """
    Parse documents into nodes with proper table handling.
    
    The LineBasedTokenChunker will:
    1. Split content at line boundaries for better table handling
    2. Use token-aware chunking aligned with embedding model
    3. Add context prefixes for table chunks
    """
    print(f"Chunking {len(documents)} document(s) with line-based chunker for better table handling...")
    nodes = node_parser.get_nodes_from_documents(documents)
    print(f"Generated {len(nodes)} nodes from documents")
    
    # Optional: Print table statistics
    table_nodes = [n for n in nodes if "table" in str(n.metadata).lower()]
    print(f"  - {len(table_nodes)} nodes contain table content")
    
    return nodes


def create_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int):
    # Delete existing collection to avoid duplicates
    try:
        client.delete_collection(collection_name)
        print(f"Deleted existing collection: {collection_name}")
    except Exception as e:
        print(f"No existing collection to delete or error: {e}")
    
    # Create new hybrid collection with dense and sparse vectors
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "dense": models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(),
        },
    )
    print(f"Created hybrid collection: {collection_name}")


def embed_texts(texts: list[str]) -> tuple[list[list[float]], list[models.SparseVector]]:
    # Dense embeddings for semantic search
    dense_embeddings = embedding_model.get_text_embedding_batch(texts, show_progress=True)

    # Sparse TF-IDF vectors for keyword search
    sparse_embeddings = build_sparse_vectors(texts)

    return dense_embeddings, sparse_embeddings


def build_payload(node):
    text = node.get_content(metadata_mode=MetadataMode.NONE)
    return {
        "node_id": node.id_,
        "source": node.metadata.get("source"),
        "doc_id": node.ref_doc_id,
        "text": text,
    }


def upload_nodes_to_qdrant(nodes, dense_vectors, sparse_vectors, client: QdrantClient, collection_name: str):
    batch_size = 128
    points = []
    for node, dense_vec, sparse_vec in zip(nodes, dense_vectors, sparse_vectors):
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector={
                    "dense": dense_vec,
                    "sparse": sparse_vec,
                },
                payload=build_payload(node),
            )
        )

    for start in range(0, len(points), batch_size):
        client.upsert(
            collection_name=collection_name,
            points=points[start : start + batch_size],
        )


def main():
    pdf_paths = get_pdf_paths(DATA_DIR)
    documents = load_pdf_documents(pdf_paths)
    nodes = chunk_documents(documents)

    node_texts = [node.get_content(metadata_mode=MetadataMode.NONE) for node in nodes]
    dense_embeddings, sparse_embeddings = embed_texts(node_texts)

    qdrant_client = create_qdrant_client()
    if len(dense_embeddings) == 0:
        raise RuntimeError("No embeddings were created from the PDF documents.")

    ensure_collection(
        qdrant_client,
        QDRANT_COLLECTION_NAME,
        vector_size=len(dense_embeddings[0]),
    )
    upload_nodes_to_qdrant(nodes, dense_embeddings, sparse_embeddings, qdrant_client, QDRANT_COLLECTION_NAME)
    print(
        f"Uploaded {len(nodes)} hybrid-embedded chunks from {len(pdf_paths)} PDF(s) "
        f"to Qdrant collection '{QDRANT_COLLECTION_NAME}'."
    )


if __name__ == "__main__":
    main()



