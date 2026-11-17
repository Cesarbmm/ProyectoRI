
"""Métricas de evaluación para Recuperación de Información."""

from math import log2
from statistics import fmean


def precision_at_k(ranked_ids, relevant_ids, k):
    """Proporción de relevantes en los primeros k."""
    hits = sum(
        doc_id in relevant_ids
        for doc_id in ranked_ids[:k]
    )
    return hits / k


def recall_at_k(ranked_ids, relevant_ids, k):
    """Fracción de relevantes conocidos recuperados."""
    if not relevant_ids:
        return 0.0

    hits = sum(
        doc_id in relevant_ids
        for doc_id in ranked_ids[:k]
    )
    return hits / len(relevant_ids)


def average_precision_at_k(ranked_ids, relevant_ids, k):
    """AP hasta k, normalizada por todos los relevantes."""
    if not relevant_ids:
        return 0.0

    hits = 0
    precision_sum = 0.0

    for rank, doc_id in enumerate(ranked_ids[:k], 1):
        if doc_id in relevant_ids:
            hits += 1
            precision_sum += hits / rank

    return precision_sum / len(relevant_ids)


def reciprocal_rank_at_k(ranked_ids, relevant_ids, k):
    """Recíproco de la posición del primer relevante."""
    for rank, doc_id in enumerate(ranked_ids[:k], 1):
        if doc_id in relevant_ids:
            return 1.0 / rank

    return 0.0


def ndcg_at_k(ranked_ids, relevant_ids, k):
    """NDCG para relevancia binaria."""
    if not relevant_ids:
        return 0.0

    dcg = sum(
        1.0 / log2(rank + 1)
        for rank, doc_id in enumerate(ranked_ids[:k], 1)
        if doc_id in relevant_ids
    )

    ideal_hits = min(k, len(relevant_ids))

    idcg = sum(
        1.0 / log2(rank + 1)
        for rank in range(1, ideal_hits + 1)
    )

    return dcg / idcg


def evaluate_query(ranked_ids, relevant_ids, depth=1000):
    """Evalúa un ranking completo a la profundidad elegida."""

    if (
        isinstance(depth, bool)
        or not isinstance(depth, int)
        or depth < 100
    ):
        raise ValueError("depth debe ser un entero >= 100.")

    ranked_ids = list(ranked_ids)
    relevant_ids = set(relevant_ids)

    if len(ranked_ids) != len(set(ranked_ids)):
        raise ValueError(
            "El ranking contiene IDs duplicados."
        )

    if len(ranked_ids) > depth:
        ranked_ids = ranked_ids[:depth]

    return {
        f"AP@{depth}": average_precision_at_k(
            ranked_ids, relevant_ids, depth
        ),
        "P@5": precision_at_k(
            ranked_ids, relevant_ids, 5
        ),
        "P@10": precision_at_k(
            ranked_ids, relevant_ids, 10
        ),
        "Recall@10": recall_at_k(
            ranked_ids, relevant_ids, 10
        ),
        "Recall@100": recall_at_k(
            ranked_ids, relevant_ids, 100
        ),
        "RR@10": reciprocal_rank_at_k(
            ranked_ids, relevant_ids, 10
        ),
        "NDCG@10": ndcg_at_k(
            ranked_ids, relevant_ids, 10
        ),
    }


def aggregate_metrics(per_query):
    """Promedia métricas sobre todas las consultas evaluadas."""
    if not per_query:
        raise ValueError("No hay consultas para evaluar.")

    keys = list(next(iter(per_query.values())))

    aggregated = {}

    for key in keys:
        values = [
            metrics[key]
            for metrics in per_query.values()
        ]

        if key.startswith("AP@"):
            name = key.replace("AP@", "MAP@", 1)
        elif key.startswith("RR@"):
            name = key.replace("RR@", "MRR@", 1)
        else:
            name = key

        aggregated[name] = fmean(values)

    return aggregated



def write_trec_ranking(
    file,
    query_id: str,
    results,
    run_name: str
) -> None:
    """
    Exporta un ranking al formato TREC.

    La columna score contiene una puntuación ordinal,
    no la similitud original del recuperador.

    Esto elimina empates durante la evaluación externa.
    """
    total = len(results)

    for rank, result in enumerate(results, start=1):
        evaluation_score = total - rank + 1

        file.write(
            f"{query_id} Q0 {result.doc_id} "
            f"{rank} {evaluation_score} {run_name}\n"
        )
