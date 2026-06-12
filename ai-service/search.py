"""Qdrant hybrid search with native prefetch + RRF fusion.

Fuses dense (semantic) and sparse (TF-IDF with Qdrant IDF modifier)
results using Qdrant's ``query_points`` API with ``Fusion.RRF``.
"""

from config import QDRANT_COLLECTION, get_embedding_model, text_to_sparse_vector
from qdrant_client import QdrantClient, models


def hybrid_search(
    qdrant_client: QdrantClient,
    query_text: str,
    *,
    collection_name: str = QDRANT_COLLECTION,
    top_k: int = 25,
    dense_limit: int = 50,
    sparse_limit: int = 50,
    filter_condition: models.Filter | None = None,
) -> list[dict]:
    """
    Hybrid search via Qdrant's native prefetch + RRF fusion.

    Parameters
    ----------
    filter_condition : optional
        Qdrant ``Filter`` applied as a post-filter to the fused results.
        Useful for scoping results (e.g. ``product_model == "CX 6200"``).

    Returns
    -------
    List of dicts with keys: ``id``, ``score``, ``text``, ``source``,
    ``product_model``, ``doc_id``.
    """
    embed_model = get_embedding_model()
    query_dense = embed_model.get_query_embedding(query_text)
    query_sparse = text_to_sparse_vector(query_text)

    prefetch = [
        models.PrefetchQuery(query=query_dense, using="dense", limit=dense_limit),
        models.PrefetchQuery(query=query_sparse, using="sparse", limit=sparse_limit),
    ]

    if filter_condition:
        prefetch = [
            models.PrefetchQuery(
                query=query_dense,
                using="dense",
                limit=dense_limit,
                filter=filter_condition,
            ),
            models.PrefetchQuery(
                query=query_sparse,
                using="sparse",
                limit=sparse_limit,
                filter=filter_condition,
            ),
        ]

    result = qdrant_client.query_points(
        collection_name=collection_name,
        prefetch=prefetch,
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        with_payload=True,
        limit=top_k,
    )

    out = []
    for point in result.points:
        payload = point.payload or {}
        out.append({
            "id": point.id,
            "score": point.score,
            "text": payload.get("text", ""),
            "source": payload.get("source", ""),
            "product_model": payload.get("product_model", ""),
            "doc_id": payload.get("doc_id", ""),
        })
    return out
