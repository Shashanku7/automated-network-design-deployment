"""
Document ingestion pipeline for the RAG knowledge base.

Supports two ingestion modes:
  1. datasheets  — HPE Aruba CX switch datasheets (data/), chunked with
     structure-aware HybridChunker, OCR-cleaned.
  2. config_guides — Configuration guide PDFs (config_guides/), chunked
     with the same HybridChunker, no datasheet-specific OCR cleanup.

Both modes:
  - Use Docling with Granite Docling code/formula enrichment for
    accurate extraction of CLI commands, config snippets, and formulas
  - Use SmolVLM-256M for automatic picture description and
    classification (topology diagrams, CLI screenshots, etc.)
  - Use structure-aware HybridChunker with native table handling
    (repeat_table_header=True, omit_header_on_overflow=True)
  - Embed with Qwen3-Embedding, build hash-based sparse vectors,
    and upload to Qdrant for hybrid retrieval (dense + Qdrant-native
    sparse with IDF modifier).

Usage:
    python ingest.py                 # default: datasheets
    python ingest.py datasheets       # ingest datasheets only
    python ingest.py config_guides    # ingest config guides only
    python ingest.py all              # ingest both
"""

import os
import re
import uuid
import argparse
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
    QDRANT_CONFIG_COLLECTION,
    HUGGINGFACE_TOKEN,
    EMBEDDING_MAX_TOKENS,
    CHUNK_MAX_TOKENS,
    MIN_CHUNK_LENGTH,
    TINY_CHUNK_MERGE_THRESHOLD,
    CONFIG_GUIDES_DIR,
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
CONFIG_GUIDES_DATA_DIR = CONFIG_GUIDES_DIR
PDF_PATTERN = "*.pdf"

hf_auth_kwargs = {"trust_remote_code": True}
if HUGGINGFACE_TOKEN:
    hf_auth_kwargs["token"] = HUGGINGFACE_TOKEN


# ── Document converter: datasheets (native PDFs, no OCR) ────────
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableFormerMode,
    CodeFormulaVlmOptions,
    AcceleratorOptions,
    AcceleratorDevice,
    smolvlm_picture_description,
)
from docling.datamodel.base_models import InputFormat

_pipeline_options_datasheet = PdfPipelineOptions(
    do_table_structure=True,
    do_ocr=False,
    force_backend_text=True,
    do_code_enrichment=True,
    do_formula_enrichment=True,
    code_formula_options=CodeFormulaVlmOptions.from_preset("granite_docling"),
    generate_picture_images=True,
    images_scale=2.0,
    do_picture_classification=True,
    do_picture_description=True,
    picture_description_options=smolvlm_picture_description,
    document_timeout=300,
    table_structure_options=PdfPipelineOptions.model_fields[
        "table_structure_options"
    ].default.__class__(
        do_cell_matching=True,
        mode=TableFormerMode.ACCURATE,
    ),
    accelerator_options=AcceleratorOptions(
        num_threads=4,
        device=AcceleratorDevice.AUTO,
    ),
)

doc_converter_datasheet = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=_pipeline_options_datasheet),
    }
)

# ── Document converter: config guides ─────────────
_pipeline_options_config = PdfPipelineOptions(
    do_table_structure=True,
    do_ocr=False,
    force_backend_text=True,
    do_code_enrichment=True,
    do_formula_enrichment=True,
    code_formula_options=CodeFormulaVlmOptions.from_preset("granite_docling"),
    generate_picture_images=True,
    images_scale=2.0,
    do_picture_classification=True,
    do_picture_description=True,
    picture_description_options=smolvlm_picture_description,
    document_timeout=300,
    table_structure_options=PdfPipelineOptions.model_fields[
        "table_structure_options"
    ].default.__class__(
        do_cell_matching=True,
        mode=TableFormerMode.ACCURATE,
    ),
    accelerator_options=AcceleratorOptions(
        num_threads=4,
        device=AcceleratorDevice.AUTO,
    ),
)

doc_converter_config = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=_pipeline_options_config),
    }
)

reader_datasheet = DoclingReader(
    export_type=DoclingReader.ExportType.JSON,
    doc_converter=doc_converter_datasheet,
)

reader_config = DoclingReader(
    export_type=DoclingReader.ExportType.JSON,
    doc_converter=doc_converter_config,
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
        repeat_table_header=True,
        omit_header_on_overflow=True,
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


def load_pdf_documents(pdf_paths: Iterable[Path], reader=None):
    """
    Load PDF documents using DoclingReader.

    The JSON export preserves:
    - Document structure (sections, headings)
    - Table structure and content
    - Page layout information
    - Reading order
    """
    if reader is None:
        reader = reader_datasheet
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


def _merge_small_chunks(nodes, merge_threshold: int = TINY_CHUNK_MERGE_THRESHOLD):
    """
    Merge chunks shorter than *merge_threshold* chars into their predecessor,
    so tiny dangling fragments are absorbed into the surrounding section
    rather than polluting the index as standalone chunks.

    To prevent unbounded growth, merging stops once the predecessor reaches
    ~CHUNK_MAX_TOKENS (in chars).  Chunks that would push over the cap are
    kept as-is.

    Merging only happens when the two chunks share the same top-level heading
    (``headings[0]`` from metadata), so content never crosses a major section
    boundary.  If either chunk lacks heading metadata, merging proceeds
    conservatively (they are likely adjacent in the same section).
    """
    if len(nodes) <= 1:
        return nodes

    def _top_heading(node_) -> str | None:
        h = node_.metadata.get("headings")
        return h[0] if isinstance(h, list) and h else None

    # Rough char budget: 1 token ≈ 4 chars for technical English
    char_cap = CHUNK_MAX_TOKENS * 4

    merged = [nodes[0]]
    for node in nodes[1:]:
        text = node.get_content(metadata_mode=MetadataMode.NONE).strip()
        if len(text) < merge_threshold:
            # Don't merge across a top-level section boundary
            prev_top = _top_heading(merged[-1])
            cur_top = _top_heading(node)
            if prev_top is not None and cur_top is not None and prev_top != cur_top:
                merged.append(node)
                continue

            prev_text = merged[-1].get_content(metadata_mode=MetadataMode.NONE)
            combined_len = len(prev_text) + 2 + len(text)  # "\n\n" separator
            if combined_len <= char_cap:
                merged[-1].text = prev_text + "\n\n" + text
                continue
        merged.append(node)

    merged_count = len(nodes) - len(merged)
    if merged_count:
        print(f"  🔗 Merged {merged_count} small chunks into predecessors")
    return merged


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


def chunk_documents(documents, clean_ocr=True):
    """
    Parse documents into nodes using the structure-aware HybridChunker,
    which natively handles:
    - Table splitting with repeated headers across chunk boundaries
    - Tokenization-aware section merging (merge_peers)
    - Oversized chunk overflow with header omission

    Post-processing:
    1. Clean OCR text artifacts (datasheets only)
    2. Filter out empty/short chunks
    """
    print(f"  🔧 Chunking {len(documents)} document(s) with HybridChunker (max_tokens={CHUNK_MAX_TOKENS})...")
    nodes = node_parser.get_nodes_from_documents(documents)
    print(f"  ✅ Generated {len(nodes)} raw nodes")

    processed_nodes = []
    for node in nodes:
        text = node.get_content(metadata_mode=MetadataMode.NONE)
        if clean_ocr:
            node.text = _clean_ocr_text(text)
        else:
            node.text = text
        processed_nodes.append(node)

    nodes = processed_nodes

    # Merge tiny chunks into predecessors to avoid standalone fragments
    nodes = _merge_small_chunks(nodes)

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
        field_schema=models.TextIndexType.TEXT,
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
# Pipeline runner
# ============================================================================
def run_pipeline(data_dir: Path, collection_name: str, reader, clean_ocr: bool, label: str):
    """Run the full ingestion pipeline for a given data directory and collection."""
    print(f"\n{'='*60}")
    print(f"🚀 Starting {label} ingestion pipeline")
    print(f"{'='*60}\n")

    pdf_paths = get_pdf_paths(data_dir)
    print(f"📁 Found {len(pdf_paths)} PDF file(s) in {data_dir.resolve()}\n")

    # 1. Load PDFs
    print("── Step 1: Loading PDFs ──")
    documents = load_pdf_documents(pdf_paths, reader=reader)

    # 2. Chunk with HybridChunker
    print("\n── Step 2: Chunking ──")
    nodes = chunk_documents(documents, clean_ocr=clean_ocr)

    # 3. Embed
    print("\n── Step 3: Embedding ──")
    node_texts = [node.get_content(metadata_mode=MetadataMode.NONE) for node in nodes]
    dense_embeddings, sparse_vectors = embed_texts(node_texts)

    if len(dense_embeddings) == 0:
        raise RuntimeError(f"No embeddings were created from the {label} PDF documents.")

    # 4. Upload to Qdrant
    print("\n── Step 4: Uploading to Qdrant ──")
    qdrant_client = create_qdrant_client()
    ensure_collection(
        qdrant_client,
        collection_name,
        vector_size=len(dense_embeddings[0]),
    )
    upload_nodes_to_qdrant(nodes, dense_embeddings, sparse_vectors, qdrant_client, collection_name)

    print(
        f"\n✅ Done! Uploaded {len(nodes)} hybrid-embedded chunks from "
        f"{len(pdf_paths)} PDF(s) to Qdrant collection '{collection_name}'."
    )
    print(f"   Dense vector dim: {len(dense_embeddings[0])}")
    print(f"   Chunker: HybridChunker (max_tokens={CHUNK_MAX_TOKENS})")


# ============================================================================
# Main
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="RAG ingestion pipeline — datasheets and/or config guides."
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="datasheets",
        choices=["datasheets", "config_guides", "all"],
        help="Which PDFs to ingest (default: datasheets)",
    )
    args = parser.parse_args()

    pipelines = []

    if args.mode in ("datasheets", "all"):
        pipelines.append(
            (DATA_DIR, QDRANT_COLLECTION, reader_datasheet, True, "datasheets")
        )

    if args.mode in ("config_guides", "all"):
        pipelines.append(
            (CONFIG_GUIDES_DATA_DIR, QDRANT_CONFIG_COLLECTION, reader_config, False, "config guides")
        )

    for data_dir, collection, reader, clean_ocr, label in pipelines:
        run_pipeline(data_dir, collection, reader, clean_ocr, label)


if __name__ == "__main__":
    main()
