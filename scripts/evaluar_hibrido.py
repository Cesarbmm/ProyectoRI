
"""Fusiona rankings BM25/MiniLM y evalúa FiQA validation."""

import argparse
import json

from collections import defaultdict
from pathlib import Path
from time import perf_counter

from ri_fiqa.evaluation import (
    evaluate_query,
    aggregate_metrics,
    write_trec_ranking,
)
from ri_fiqa.retrieval.fusion import weighted_rrf


BASE_DIR = Path(__file__).resolve().parents[1]
RESULTS = BASE_DIR / "results"

BM25_RUN = RESULTS / (
    "bm25_k1-1.2_b-0.5_validation_top1000.trec"
)

# SEMANTIC_RUN = RESULTS / (
#     "semantic_minilm_validation_top1000.trec"
# )

QRELS_PATH = RESULTS / "qrels_validation.trec"

DEPTH = 1000


def read_run(path):
    """Lee rankings TREC usando la columna rank."""
    grouped = defaultdict(list)
    seen_docs = defaultdict(set)
    seen_ranks = defaultdict(set)

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            fields = line.split()

            if len(fields) != 6:
                raise ValueError(
                    f"{path.name}:{line_number}: "
                    "se esperaban 6 columnas."
                )

            qid, _, doc_id, rank_text, _, _ = fields
            rank = int(rank_text)

            if rank < 1:
                raise ValueError("Posición inválida.")

            if doc_id in seen_docs[qid]:
                raise ValueError(
                    f"Documento duplicado: {qid}/{doc_id}"
                )

            if rank in seen_ranks[qid]:
                raise ValueError(
                    f"Posición duplicada en consulta {qid}"
                )

            seen_docs[qid].add(doc_id)
            seen_ranks[qid].add(rank)
            grouped[qid].append((rank, doc_id))

    rankings = {}

    for qid, rows in grouped.items():
        rows.sort(key=lambda item: item[0])

        if [r for r, _ in rows] != list(
            range(1, len(rows) + 1)
        ):
            raise ValueError(
                f"Posiciones no consecutivas: {qid}"
            )

        rankings[qid] = [
            doc_id for _, doc_id in rows
        ]

    return rankings


def read_qrels(path):
    """Obtiene los documentos relevantes de cada consulta."""
    relevant = defaultdict(set)

    with path.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            qid, _, doc_id, relevance = line.split()

            relevant.setdefault(qid, set())

            if int(relevance) > 0:
                relevant[qid].add(doc_id)

    return dict(relevant)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--k", type=int, default=60
    )
    parser.add_argument(
        "--semantic-weight", type=float, default=0.75
    )

    parser.add_argument(
        "--semantic-model",
        choices=["minilm", "bge"],
        default="minilm",
        help="Encoder semántico cuyos rankings se fusionarán."
    )

    args = parser.parse_args()

    semantic_run = RESULTS / (
    f"semantic_{args.semantic_model}_validation_top1000.trec"
)

    # Validamos antes de abrir archivos de salida.
    if args.k < 1 or not 0 < args.semantic_weight < 1:
        parser.error("Parámetros RRF inválidos.")

    for path in (BM25_RUN, semantic_run, QRELS_PATH):
        if not path.is_file():
            parser.error(f"No existe: {path}")

    print("[1/3] Leyendo rankings existentes...")

    bm25 = read_run(BM25_RUN)
    semantic = read_run(semantic_run)
    qrels = read_qrels(QRELS_PATH)

    unexpected = (set(bm25) | set(semantic)) - set(qrels)

    if unexpected:
        raise ValueError(
            "Los rankings contienen consultas "
            "que no pertenecen a validation."
        )

    query_ids = sorted(qrels)

    print("Consultas:", len(query_ids))

    name = (
        f"hybrid_{args.semantic_model}_rrf_k{args.k}"
        f"_w{args.semantic_weight:g}"
    )

    run_path = RESULTS / (
        f"{name}_validation_top{DEPTH}.trec"
    )

    metrics_path = RESULTS / (
        f"{name}_validation_metrics.json"
    )

    print("[2/3] Fusionando y evaluando...")

    started = perf_counter()
    per_query = {}

    with run_path.open("w", encoding="utf-8") as file:
        for qid in query_ids:
            results = weighted_rrf(
                bm25_ids=bm25.get(qid, []),
                semantic_ids=semantic.get(qid, []),
                k=args.k,
                semantic_weight=args.semantic_weight,
                top_k=DEPTH,
            )

            ranked_ids = [
                result.doc_id for result in results
            ]

            per_query[qid] = evaluate_query(
                ranked_ids,
                qrels[qid],
                depth=DEPTH,
            )

            write_trec_ranking(
                file=file,
                query_id=qid,
                results=results,
                run_name=name,
            )

    elapsed = perf_counter() - started
    aggregate = aggregate_metrics(per_query)

    print("[3/3] Guardando métricas...")

    report = {
        "model": "weighted_rrf",
        "dataset": "BeIR/fiqa",
        "split": "validation",
        "queries_evaluated": len(query_ids),
        "retrieval_depth": DEPTH,
        "rrf_k": args.k,
        "semantic_weight": args.semantic_weight,
        "bm25_run": BM25_RUN.name,
        "semantic_run": semantic_run.name,
        "semantic_model": args.semantic_model,
        "trec_score_policy": "ordinal_rank_descending",
        "fusion_seconds": elapsed,
        "aggregate": aggregate,
        "per_query": per_query,
    }

    with metrics_path.open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(report, file, indent=2)

    print("\n=== HYBRID RRF / VALIDATION ===")

    for metric, value in aggregate.items():
        print(f"{metric:15s}: {value:.6f}")

    print(f"\nTiempo de fusión: {elapsed:.2f} s")
    print("Métricas:", metrics_path)
    print("Ranking:", run_path)


if __name__ == "__main__":
    main()
