"""
Document ingestion pipeline for the RAG knowledge base.

Parses HPE Aruba CX switch datasheets (PDF), chunks them with a
structure-aware HybridChunker, embeds with Qwen3-Embedding, builds
hash-based sparse vectors, and uploads to Qdrant for hybrid retrieval
(dense + Qdrant-native sparse with IDF modifier).
"""

import os
import re
import uuid
from pathlib import Path
from typing import Iterable

import numpy as np
from llama_index.core.schema import MetadataMode
from llama_index.readers.docling import DoclingReader
from llama_index.node_parser.docling import DoclingNodeParser
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
)
from docling_core.transforms.serializer.markdown import (
    MarkdownParams,
    MarkdownTableSerializer,
)
from qdrant_client import models
from qdrant_client.models import PointStruct

from config import (
    QWEN_EMBEDDING_MODEL,
    QDRANT_COLLECTION,
    HUGGINGFACE_TOKEN,
    EMBEDDING_MAX_TOKENS,
    CHUNK_MAX_TOKENS,
    MIN_CHUNK_LENGTH,
    get_embedding_model,
    create_qdrant_client,
    text_to_sparse_vector,
    extract_product_model,
)


# ============================================================================
# Custom Serializer for Improved Table Formatting
# ============================================================================
class OptimizedTableSerializerProvider(ChunkingSerializerProvider):
    """
    Custom serializer provider that uses full Markdown formatting for tables.
    Non-compact mode produces proper multi-line tables where each row is on
    its own line — this helps embedding models associate cell values with
    their column headers in wide comparison/spec tables.
    """
    def get_serializer(self, doc):
        return ChunkingDocSerializer(
            doc=doc,
            table_serializer=MarkdownTableSerializer(),
            params=MarkdownParams(
                compact_tables=False,  # Full multi-line table format for better embedding
            ),
        )


DATA_DIR = Path("data")
PDF_PATTERN = "*.pdf"

hf_auth_kwargs = {"trust_remote_code": True}
if HUGGINGFACE_TOKEN:
    hf_auth_kwargs["token"] = HUGGINGFACE_TOKEN


# ── Document converter with optimized pipeline for native PDFs ────
# Since these are digital PDFs (not scanned), we configure Docling to:
# - Use the PDF's embedded text layer directly (force_backend_text=True)
# - Use ACCURATE table structure detection with cell matching
# - Skip OCR (not needed for native text PDFs)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.datamodel.base_models import InputFormat

pipeline_options = PdfPipelineOptions(
    do_table_structure=True,
    do_ocr=False,                 # Skip OCR — native text PDFs don't need it
    force_backend_text=True,      # Use PDF's embedded text layer directly
    table_structure_options=PdfPipelineOptions.model_fields[
        "table_structure_options"
    ].default.__class__(
        do_cell_matching=True,    # Match detected cells to text content
        mode=TableFormerMode.ACCURATE,
    ),
)

doc_converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
    }
)

reader = DoclingReader(
    export_type=DoclingReader.ExportType.JSON,
    doc_converter=doc_converter,
)

# ── Tokenizer (for HybridChunker) ────────────────
try:
    qwen_tokenizer = HuggingFaceTokenizer.from_pretrained(
        QWEN_EMBEDDING_MODEL,
        max_tokens=EMBEDDING_MAX_TOKENS,
        **hf_auth_kwargs,
    )
except Exception as exc:
    raise RuntimeError(
        "Unable to load the Qwen tokenizer. If the model is private, set HUGGINGFACE_TOKEN."
    ) from exc

# ── Node parser with structure-aware HybridChunker ─
# HybridChunker respects document structure (headings, sections, tables)
# instead of splitting blindly at line boundaries. merge_peers=True
# combines adjacent small sections under the same heading into one chunk.
node_parser = DoclingNodeParser(
    chunker=HybridChunker(
        tokenizer=qwen_tokenizer,
        max_tokens=CHUNK_MAX_TOKENS,
        merge_peers=True,
        serializer_provider=OptimizedTableSerializerProvider(),
    )
)

# ── Embedding model ──────────────────────────────
embedding_model = get_embedding_model()


# ============================================================================
# PDF Loading
# ============================================================================
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
        print(f"  📄 Loading: {pdf_path.name}")
        documents.extend(
            reader.load_data(pdf_path, extra_info={"source": str(pdf_path)})
        )
    return documents


# ============================================================================
# Chunking (HybridChunker — structure-aware)
# ============================================================================

# Approximate chars-per-token ratio for estimating token counts from char length.
# Qwen tokenizer typically yields ~4-5 chars per token for English + technical text.
_CHARS_PER_TOKEN = 4.5
_MAX_CHUNK_CHARS = int(CHUNK_MAX_TOKENS * _CHARS_PER_TOKEN)  # ~3456 chars


def _clean_ocr_text(text: str) -> str:
    """
    Fix common Docling OCR artifacts in HPE datasheet text.

    Handles issues like:
    - "Networking6000" → "Networking 6000"
    - "48GCL44SFP" → "48G CL4 4SFP"  (common SKU parsing issue)
    - "Class4PoE" → "Class4 PoE"
    - Missing spaces before/after parentheses in model numbers
    """
    # Insert space between a word and a number that are jammed together
    # e.g., "Networking6000" → "Networking 6000"
    text = re.sub(r'([a-zA-Z])(\d{3,})', r'\1 \2', text)

    # Insert space between number and uppercase letter
    # e.g., "370WSwitch" → "370W Switch", "4SFP+Switch" → "4SFP+ Switch"
    text = re.sub(r'(\d+[A-Z+]*[W])([A-Z][a-z])', r'\1 \2', text)

    # "Class4PoE" → "Class4 PoE", "PoE4SFP" → "PoE 4SFP"
    text = re.sub(r'(PoE)(\d)', r'\1 \2', text)
    text = re.sub(r'(\d)(PoE)', r'\1 \2', text)

    # "4SFP370W" → "4SFP 370W"
    text = re.sub(r'(\d+SFP\+?)(\d)', r'\1 \2', text)

    # "48GCL4" → "48G CL4"
    text = re.sub(r'(\d+G)(CL\d)', r'\1 \2', text)

    # "16GBeMMC" → "16GB eMMC"
    text = re.sub(r'(\d+GB)(eMMC)', r'\1 \2', text)

    return text


def _split_oversized_table_chunk(text: str, metadata: dict) -> list[tuple[str, dict]]:
    """
    Split an oversized chunk containing a markdown table into smaller pieces.

    Strategy: keep the header row + separator, then split data rows into
    groups that fit within the token limit. Each sub-chunk gets the full
    header so it remains self-contained.

    Returns list of (text, metadata) tuples.
    """
    lines = text.split('\n')

    # Find the table structure
    header_lines = []
    data_lines = []
    non_table_prefix = []
    non_table_suffix = []
    in_table = False
    past_table = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and not past_table:
            in_table = True
            if not data_lines and (
                stripped.startswith('|-') or
                all(c in '-| ' for c in stripped)
            ):
                # This is a separator row — part of the header
                header_lines.append(line)
            elif not header_lines:
                # First table line is the header
                header_lines.append(line)
            elif len(header_lines) == 1 and (
                stripped.startswith('|-') or
                all(c in '-| ' for c in stripped)
            ):
                # Second line is the separator
                header_lines.append(line)
            else:
                data_lines.append(line)
        elif in_table and not stripped.startswith('|'):
            past_table = True
            non_table_suffix.append(line)
        elif not in_table:
            non_table_prefix.append(line)
        else:
            non_table_suffix.append(line)

    # If no table structure found or small enough, return as-is
    if not header_lines or not data_lines:
        return [(text, metadata)]

    header_text = '\n'.join(header_lines)
    header_len = len(header_text)
    prefix_text = '\n'.join(non_table_prefix).strip()
    suffix_text = '\n'.join(non_table_suffix).strip()

    # Calculate how many data rows fit per sub-chunk
    # Reserve space for header + prefix + suffix
    overhead = header_len + len(prefix_text) + len(suffix_text) + 20  # padding
    available = _MAX_CHUNK_CHARS - overhead
    if available <= 0:
        available = _MAX_CHUNK_CHARS // 2

    # Group data rows into sub-chunks
    chunks = []
    current_rows = []
    current_len = 0

    for row in data_lines:
        row_len = len(row) + 1  # +1 for newline
        if current_len + row_len > available and current_rows:
            # Emit current group
            chunk_text_parts = []
            if prefix_text:
                chunk_text_parts.append(prefix_text)
            chunk_text_parts.append(header_text)
            chunk_text_parts.append('\n'.join(current_rows))
            chunk_text = '\n'.join(chunk_text_parts)
            chunks.append((chunk_text, metadata.copy()))
            current_rows = []
            current_len = 0

        current_rows.append(row)
        current_len += row_len

    # Emit remaining rows
    if current_rows:
        chunk_text_parts = []
        if prefix_text:
            chunk_text_parts.append(prefix_text)
        chunk_text_parts.append(header_text)
        chunk_text_parts.append('\n'.join(current_rows))
        if suffix_text:
            chunk_text_parts.append(suffix_text)
        chunk_text = '\n'.join(chunk_text_parts)
        chunks.append((chunk_text, metadata.copy()))

    return chunks


def chunk_documents(documents):
    """
    Parse documents into nodes using the structure-aware HybridChunker,
    then post-process to:
    1. Clean OCR text artifacts
    2. Split oversized table chunks
    3. Filter out empty/short chunks
    """
    print(f"  🔧 Chunking {len(documents)} document(s) with HybridChunker (max_tokens={CHUNK_MAX_TOKENS})...")
    nodes = node_parser.get_nodes_from_documents(documents)
    print(f"  ✅ Generated {len(nodes)} raw nodes")

    # Post-process: clean OCR text and split oversized chunks
    from llama_index.core.schema import TextNode

    processed_nodes = []
    split_count = 0
    for node in nodes:
        text = node.get_content(metadata_mode=MetadataMode.NONE)

        # 1. Clean OCR artifacts
        cleaned = _clean_ocr_text(text)

        # 2. Check if chunk is oversized and contains a table
        if len(cleaned) > _MAX_CHUNK_CHARS and '|' in cleaned:
            sub_chunks = _split_oversized_table_chunk(cleaned, node.metadata)
            if len(sub_chunks) > 1:
                split_count += 1
                for sub_text, sub_meta in sub_chunks:
                    new_node = TextNode(
                        text=sub_text,
                        metadata=sub_meta,
                        excluded_embed_metadata_keys=node.excluded_embed_metadata_keys,
                        excluded_llm_metadata_keys=node.excluded_llm_metadata_keys,
                    )
                    # Preserve the doc reference
                    new_node.relationships = node.relationships.copy()
                    processed_nodes.append(new_node)
                continue
            else:
                # Couldn't split further, use cleaned text
                node.text = cleaned
        else:
            node.text = cleaned

        processed_nodes.append(node)

    if split_count > 0:
        print(f"  ✂️  Split {split_count} oversized table chunks into smaller pieces")

    nodes = processed_nodes

    # Filter out empty or very short chunks
    original_count = len(nodes)
    nodes = [
        n for n in nodes
        if len(n.get_content(metadata_mode=MetadataMode.NONE).strip()) >= MIN_CHUNK_LENGTH
    ]
    filtered = original_count - len(nodes)
    if filtered > 0:
        print(f"  🗑️  Filtered {filtered} chunks shorter than {MIN_CHUNK_LENGTH} chars")

    # Print chunk statistics
    table_nodes = [n for n in nodes if "table" in str(n.metadata).lower()]
    texts = [n.get_content(metadata_mode=MetadataMode.NONE) for n in nodes]
    lengths = [len(t) for t in texts]
    print(f"  📊 Chunk stats: {len(nodes)} chunks, "
          f"avg={np.mean(lengths):.0f} chars, "
          f"min={np.min(lengths)}, max={np.max(lengths)}, "
          f"{len(table_nodes)} contain table content")

    # Warn about any remaining oversized chunks
    oversized = [l for l in lengths if l > _MAX_CHUNK_CHARS]
    if oversized:
        print(f"  ⚠️  {len(oversized)} chunks still exceed {_MAX_CHUNK_CHARS} chars "
              f"(max={max(oversized)})")

    return nodes


# ============================================================================
# Embedding
# ============================================================================
def embed_texts(texts: list[str]) -> tuple[list[list[float]], list[models.SparseVector]]:
    """
    Build dense embeddings (Qwen) and sparse vectors (hash TF) for a list of texts.

    Sparse vectors use raw term-frequency values. Qdrant applies IDF weighting
    natively during search via ``SparseVectorParams(modifier=Modifier.IDF)``.

    Returns:
        dense_embeddings: List of dense vectors
        sparse_vectors: List of Qdrant SparseVectors
    """
    print(f"  🧠 Building dense embeddings for {len(texts)} chunks...")
    dense_embeddings = embedding_model.get_text_embedding_batch(texts, show_progress=True)

    print(f"  📝 Building sparse vectors (hash TF — Qdrant native IDF)...")
    sparse_vectors = [text_to_sparse_vector(t) for t in texts]

    return dense_embeddings, sparse_vectors


# ============================================================================
# Payload Builder (enriched metadata)
# ============================================================================
def build_payload(node):
    """Build a Qdrant payload with enriched metadata."""
    text = node.get_content(metadata_mode=MetadataMode.NONE)
    source = node.metadata.get("source", "")

    return {
        "node_id": node.id_,
        "source": source,
        "doc_id": node.ref_doc_id,
        "text": text,
        "product_model": extract_product_model(source),
        "text_length": len(text),
    }


# ============================================================================
# Qdrant Collection Management (non-destructive)
# ============================================================================
def ensure_collection(client, collection_name: str, vector_size: int):
    """
    Ensure the Qdrant collection exists with the correct schema.

    Always deletes any existing collection and creates a fresh one
    to guarantee the schema (dense + sparse with IDF modifier,
    full-text payload index) matches.
    """
    if collection_name in [c.name for c in client.get_collections().collections]:
        client.delete_collection(collection_name)
        print(f"  🗑️  Deleted existing collection '{collection_name}'")

    # Create new collection with dense + sparse vectors
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "dense": models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                modifier=models.Modifier.IDF,
            ),
        },
    )

    # Full-text index on ``text`` — enables BM25 scoring in Qdrant
    client.create_payload_index(
        collection_name=collection_name,
        field_name="text",
        field_type=models.TextIndexType.TEXT,
    )

    print(f"  ✅ Created hybrid collection (dense + sparse + BM25 FT index): {collection_name}")


# ============================================================================
# Upload to Qdrant (with progress)
# ============================================================================
def upload_nodes_to_qdrant(nodes, dense_vectors, sparse_vectors, client, collection_name: str):
    """Upload chunked nodes with hybrid vectors to Qdrant in batches."""
    batch_size = 32
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

    total_batches = (len(points) + batch_size - 1) // batch_size
    for batch_num, start in enumerate(range(0, len(points), batch_size), 1):
        batch = points[start : start + batch_size]
        client.upsert(
            collection_name=collection_name,
            points=batch,
        )
        print(f"  📤 Uploaded batch {batch_num}/{total_batches} ({len(batch)} points)")


# ============================================================================
# Main
# ============================================================================
def main():
    print("\n🚀 Starting RAG ingestion pipeline\n")

    pdf_paths = get_pdf_paths(DATA_DIR)
    print(f"📁 Found {len(pdf_paths)} PDF file(s) in {DATA_DIR.resolve()}\n")

    # 1. Load PDFs
    print("── Step 1: Loading PDFs ──")
    documents = load_pdf_documents(pdf_paths)

    # 2. Chunk with HybridChunker
    print("\n── Step 2: Chunking ──")
    nodes = chunk_documents(documents)

    # 3. Embed
    print("\n── Step 3: Embedding ──")
    node_texts = [node.get_content(metadata_mode=MetadataMode.NONE) for node in nodes]
    dense_embeddings, sparse_vectors = embed_texts(node_texts)

    if len(dense_embeddings) == 0:
        raise RuntimeError("No embeddings were created from the PDF documents.")

    # 4. Upload to Qdrant
    print("\n── Step 4: Uploading to Qdrant ──")
    qdrant_client = create_qdrant_client()
    ensure_collection(
        qdrant_client,
        QDRANT_COLLECTION,
        vector_size=len(dense_embeddings[0]),
    )
    upload_nodes_to_qdrant(nodes, dense_embeddings, sparse_vectors, qdrant_client, QDRANT_COLLECTION)

    print(
        f"\n✅ Done! Uploaded {len(nodes)} hybrid-embedded chunks from "
        f"{len(pdf_paths)} PDF(s) to Qdrant collection '{QDRANT_COLLECTION}'."
    )
    print(f"   Dense vector dim: {len(dense_embeddings[0])}")
    print(f"   Chunker: HybridChunker (max_tokens={CHUNK_MAX_TOKENS})")


if __name__ == "__main__":
    main()
