
"""Evaluación final de todos los modelos sobre FiQA."""

import argparse
import json

from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from datasets import load_from_disk

from ri_fiqa.config import SELECTED_CONFIG
from ri_fiqa.evaluation import (
    evaluate_query,
    aggregate_metrics,
    write_trec_ranking,
)
from ri_fiqa.search_service import SearchService


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RESULTS = ROOT / "results"

DEPTH = 1000

# Referencias experimentales congeladas de validation.
REFERENCES = {
    "jaccard": "jaccard_validation_metrics.json",
    "tfidf": "tfidf_validation_metrics.json",
    "bm25": "bm25_k1-1.2_b-0.5_validation_metrics.json",
    "bge": "semantic_bge_validation_metrics.json",
    "hybrid": (
        "hybrid_bge_rrf_k10_w0.9_validation_metrics.json"
    ),
}


def load_evaluation_data(split):
    """Carga consultas y relevancias de una partición."""

    queries = load_from_disk(str(RAW / "queries"))
    qrels = load_from_disk(str(RAW / "qrels"))[split]

    query_lookup = {
        str(row["_id"]): row["text"]
        for row in queries
    }

    relevant = defaultdict(set)

    for row in qrels:
        qid = str(row["query-id"])
        doc_id = str(row["corpus-id"])

        relevant.setdefault(qid, set())

        if int(row["score"]) > 0:
            relevant[qid].add(doc_id)

    query_ids = sorted(relevant)

    missing = set(query_ids) - set(query_lookup)

    if missing:
        raise ValueError(
            f"{len(missing)} consultas no existen en FiQA."
        )

    return query_lookup, relevant, query_ids, qrels


def verify_baseline(model, per_query):
    """Comprueba que el servicio reproduce validation."""

    path = RESULTS / REFERENCES[model]

    if not path.is_file():
        raise FileNotFoundError(
            f"No existe el baseline: {path}"
        )

    with path.open(encoding="utf-8") as file:
        reference = json.load(file)

    expected = reference["per_query"]

    if set(per_query) != set(expected):
        raise ValueError(
            "El servicio y el baseline tienen "
            "consultas diferentes."
        )

    differences = []

    for qid, metrics in per_query.items():
        for metric, value in metrics.items():
            delta = abs(
                value - expected[qid][metric]
            )

            if delta > 1e-9:
                differences.append(
                    (qid, metric, delta)
                )

    if differences:
        differences.sort(
            key=lambda row: row[2],
            reverse=True
        )

        print("\n[ERROR] Diferencias con validation:")

        for qid, metric, delta in differences[:5]:
            print(
                f"QID={qid} "
                f"{metric}: diferencia={delta:.8f}"
            )

        raise RuntimeError(
            "El servicio no reproduce el baseline. "
            "No continuar a test."
        )

    print(
        "[OK] Todas las métricas por consulta "
        "coinciden con el baseline."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Evaluación unificada FiQA."
    )

    parser.add_argument(
        "--model",
        choices=SearchService.MODELS,
        required=True,
    )

    parser.add_argument(
        "--split",
        choices=["validation", "test"],
        default="validation",
    )

    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
    )

    parser.add_argument(
        "--verify-baseline",
        action="store_true",
    )

    parser.add_argument(
        "--frozen",
        action="store_true",
        help="Confirma los parámetros fijados para test.",
    )

    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("batch-size debe ser positivo.")

    if args.split == "test" and not args.frozen:
        parser.error(
            "Para evaluar test debes utilizar --frozen."
        )

    if args.split == "test" and args.verify_baseline:
        parser.error(
            "--verify-baseline es exclusivo de validation."
        )

    RESULTS.mkdir(parents=True, exist_ok=True)

    name = f"service_{args.model}_{args.split}"

    metrics_path = RESULTS / f"{name}_metrics.json"
    run_path = RESULTS / f"{name}_top{DEPTH}.trec"

    if args.split == "test":
        if metrics_path.exists() or run_path.exists():
            parser.error(
                "Ya existen resultados de test para "
                "este modelo. No se sobrescribirán."
            )

    print("[1/4] Preparando consultas y relevancias...")

    query_lookup, relevant, query_ids, qrels = (
        load_evaluation_data(args.split)
    )

    expected_count = (
        500 if args.split == "validation" else 648
    )

    if len(query_ids) != expected_count:
        raise ValueError(
            f"Se esperaban {expected_count} consultas; "
            f"hay {len(query_ids)}."
        )

    texts = [
        query_lookup[qid]
        for qid in query_ids
    ]

    print("Modelo:", args.model)
    print("Partición:", args.split)
    print("Consultas:", len(query_ids))
    print("Profundidad:", DEPTH)

    print("[2/4] Ejecutando recuperación...")

    service = SearchService(device=args.device)

    started = perf_counter()

    rankings = service.rank_many(
        texts,
        model=args.model,
        top_k=DEPTH,
        batch_size=args.batch_size,
    )

    elapsed = perf_counter() - started

    if len(rankings) != len(query_ids):
        raise RuntimeError(
            "No se generó un ranking por consulta."
        )

    print("[3/4] Calculando métricas...")

    per_query = {}

    for qid, ranking in zip(query_ids, rankings):
        ranked_ids = [
            item.doc_id for item in ranking
        ]

        per_query[qid] = evaluate_query(
            ranked_ids,
            relevant[qid],
            depth=DEPTH,
        )

    aggregate = aggregate_metrics(per_query)

    if args.verify_baseline:
        verify_baseline(args.model, per_query)

    print("[4/4] Exportando resultados...")

    with run_path.open(
        "w", encoding="utf-8"
    ) as file:
        for qid, ranking in zip(
            query_ids, rankings
        ):
            write_trec_ranking(
                file=file,
                query_id=qid,
                results=ranking,
                run_name=args.model,
            )

    # Exportar los qrels de test para verificación externa.
    if args.split == "test":
        qrels_path = RESULTS / "qrels_test.trec"

        if not qrels_path.exists():
            with qrels_path.open(
                "w", encoding="utf-8"
            ) as file:
                for row in qrels:
                    file.write(
                        f"{row['query-id']} 0 "
                        f"{row['corpus-id']} "
                        f"{int(row['score'])}\n"
                    )

    report = {
        "model": args.model,
        "dataset": "BeIR/fiqa",
        "split": args.split,
        "queries_evaluated": len(query_ids),
        "retrieval_depth": DEPTH,
        "configuration": asdict(SELECTED_CONFIG),
        "trec_score_policy": "ordinal_rank_descending",
        "execution_seconds": elapsed,
        "aggregate": aggregate,
        "per_query": per_query,
    }

    with metrics_path.open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"\n=== {args.model.upper()} / "
        f"{args.split.upper()} ==="
    )

    for metric, value in aggregate.items():
        print(f"{metric:15s}: {value:.6f}")

    print(f"\nTiempo de recuperación: {elapsed:.2f} s")
    print("Reporte:", metrics_path)
    print("Ranking:", run_path)


if __name__ == "__main__":
    main()
