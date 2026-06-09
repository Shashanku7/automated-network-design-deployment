"""
Quick diagnostic: test Qdrant scroll filter for product_model.
Run with: python diagnostic_scroll.py
"""
import os, sys
sys.path.insert(0, str(__file__).rsplit("/", 1)[0])

from config import create_qdrant_client, QDRANT_COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = create_qdrant_client()

# 1. List all product models via scroll (no filter)
print("=== All product models (first 20 points) ===")
all_points = client.scroll(collection_name=QDRANT_COLLECTION, limit=20, with_payload=True, with_vectors=False)[0]
for p in all_points:
    pm = p.payload.get("product_model", "<MISSING>")
    src = p.payload.get("source", "<MISSING>")
    print(f"product_model={pm!r:15} | source={os.path.basename(src)}")

# 2. Try exact scroll for a specific model
for model in ["CX 6400", "CX 6300", "CX 6200"]:
    print(f"\n=== Scroll for product_model={model!r} ===")
    points = client.scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter=Filter(must=[FieldCondition(key="product_model", match=MatchValue(value=model))]),
        limit=5,
        with_payload=True,
        with_vectors=False,
    )[0]
    if points:
        print(f"  Found {len(points)} points")
        for p in points[:2]:
            text_preview = p.payload.get("text", "")[:120].replace("\n", " ")
            print(f"  - {text_preview}...")
    else:
        print("  0 points returned")
