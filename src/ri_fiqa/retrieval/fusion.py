
"""Fusión ponderada de rankings mediante RRF."""

from collections import defaultdict
from math import isfinite

from ri_fiqa.retrieval.common import SearchResult


def weighted_rrf(
    bm25_ids: list[str],
    semantic_ids: list[str],
    *,
    k: int = 60,
    semantic_weight: float = 0.75,
    top_k: int = 1000,
) -> list[SearchResult]:
    """Combina BM25 y embeddings mediante RRF ponderado."""

    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k debe ser un entero positivo.")

    if (
        isinstance(top_k, bool)
        or not isinstance(top_k, int)
        or top_k < 1
    ):
        raise ValueError("top_k debe ser un entero positivo.")

    if (
        isinstance(semantic_weight, bool)
        or not isinstance(semantic_weight, (int, float))
        or not isfinite(semantic_weight)
        or not 0 < semantic_weight < 1
    ):
        raise ValueError(
            "semantic_weight debe estar entre 0 y 1, sin extremos."
        )

    if len(bm25_ids) != len(set(bm25_ids)):
        raise ValueError("IDs duplicados en BM25.")

    if len(semantic_ids) != len(set(semantic_ids)):
        raise ValueError("IDs duplicados en el ranking semántico.")

    bm25_weight = 1.0 - semantic_weight
    scores = defaultdict(float)

    # Cada posición comienza en 1.
    for rank, doc_id in enumerate(bm25_ids, start=1):
        scores[doc_id] += bm25_weight / (k + rank)

    for rank, doc_id in enumerate(semantic_ids, start=1):
        scores[doc_id] += semantic_weight / (k + rank)

    results = [
        SearchResult(doc_id=doc_id, score=score)
        for doc_id, score in scores.items()
    ]

    # Mantener nuestra convención de desempate.
    results.sort(
        key=lambda result: (result.score, result.doc_id),
        reverse=True
    )

    return results[:top_k]
