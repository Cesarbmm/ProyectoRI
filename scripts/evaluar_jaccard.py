
"""Evaluación experimental de Jaccard sobre FiQA validation."""

import argparse
import json

from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from datasets import load_from_disk

from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.retrieval.jaccard import JaccardRetriever
from ri_fiqa.evaluation import (
    evaluate_query,
    aggregate_metrics,
)


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
RESULTS_DIR = BASE_DIR / "results"

INDEX_PATH = (
    BASE_DIR / "data" / "processed"
    / "inverted_index_stopwords.json.gz"
)


def main():
    parser = argparse.ArgumentParser(
        description="Evalúa Jaccard usando FiQA validation."
    )

    parser.add_argument(
        "--depth",
        type=int,
        default=1000,
        help="Profundidad del ranking; mínimo 100."
    )

    args = parser.parse_args()

    if args.depth < 100:
        parser.error("La profundidad debe ser >= 100.")

    if not INDEX_PATH.exists():
        parser.error(
            "No existe el índice. Ejecuta construir_indice.py."
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/4] Cargando índice y datasets...")

    index = InvertedIndex.load(INDEX_PATH)
    retriever = JaccardRetriever(index)

    queries = load_from_disk(
        str(RAW_DIR / "queries")
    )

    qrels = load_from_disk(
        str(RAW_DIR / "qrels")
    )["validation"]

    # ID de consulta -> texto original
    query_lookup = {
        str(row["_id"]): row["text"]
        for row in queries
    }

    # ID de consulta -> conjunto de documentos relevantes
    relevant_by_query = defaultdict(set)

    for row in qrels:
        query_id = str(row["query-id"])
        doc_id = str(row["corpus-id"])

        # Registrar la consulta aunque no tenga positivos.
        relevant_by_query.setdefault(query_id, set())

        if int(row["score"]) > 0:
            relevant_by_query[query_id].add(doc_id)

    missing = set(relevant_by_query) - set(query_lookup)
    if missing:
        raise ValueError(
            f"Hay {len(missing)} consultas inexistentes."
        )

    print(
        f"Consultas a evaluar: {len(relevant_by_query)}"
    )
    print(f"Profundidad: {args.depth}")

    print("[2/4] Ejecutando consultas...")

    run_path = (
        RESULTS_DIR /
        f"jaccard_validation_top{args.depth}.trec"
    )

    per_query = {}
    start = perf_counter()

    query_ids = sorted(relevant_by_query)

    with run_path.open(
        "w", encoding="utf-8"
    ) as run_file:

        for number, query_id in enumerate(
            query_ids, start=1
        ):
            text = query_lookup[query_id]

            results = retriever.search(
                text, top_k=args.depth
            )

            ranked_ids = [
                result.doc_id for result in results
            ]

            per_query[query_id] = evaluate_query(
                ranked_ids,
                relevant_by_query[query_id],
                depth=args.depth
            )

            # Formato TREC:
            # query_id Q0 doc_id rank score run_name
            for rank, result in enumerate(
                results, start=1
            ):
                run_file.write(
                    f"{query_id} Q0 {result.doc_id} "
                    f"{rank} {result.score:.17g} jaccard\n"
                )

            if number % 100 == 0:
                print(
                    f"    Evaluadas {number}/"
                    f"{len(query_ids)} consultas"
                )

    elapsed = perf_counter() - start

    print("[3/4] Calculando métricas globales...")

    aggregate = aggregate_metrics(per_query)

    print("\n=== RESULTADOS JACCARD / VALIDATION ===")

    for metric, value in aggregate.items():
        print(f"{metric:15s}: {value:.6f}")

    print(f"\nTiempo total: {elapsed:.2f} s")

    # Guardar los qrels originales en formato TREC.
    qrels_path = (
        RESULTS_DIR / "qrels_validation.trec"
    )

    with qrels_path.open(
        "w", encoding="utf-8"
    ) as qrels_file:
        for row in qrels:
            qrels_file.write(
                f"{row['query-id']} 0 "
                f"{row['corpus-id']} "
                f"{int(row['score'])}\n"
            )

    print("[4/4] Guardando resultados...")

    report = {
        "model": "jaccard_binary",
        "dataset": "BeIR/fiqa",
        "split": "validation",
        "queries_evaluated": len(query_ids),
        "retrieval_depth": args.depth,
        "preprocessing": asdict(
            index.preprocessor.config
        ),
        "execution_seconds": elapsed,
        "aggregate": aggregate,
        "per_query": per_query,
    }

    output_path = (
        RESULTS_DIR /
        "jaccard_validation_metrics.json"
    )

    with output_path.open(
        "w", encoding="utf-8"
    ) as output:
        json.dump(
            report, output,
            indent=2, ensure_ascii=False
        )

    print(f"Métricas: {output_path}")
    print(f"Ranking TREC: {run_path}")
    print(f"Qrels TREC: {qrels_path}")

    # Identificar consultas difíciles.
    ap_key = f"AP@{args.depth}"

    worst = sorted(
        per_query.items(),
        key=lambda item: (
            item[1][ap_key], item[0]
        )
    )[:5]

    print("\n=== CINCO CONSULTAS CON MENOR AP ===")

    for query_id, metrics in worst:
        print(
            f"Consulta {query_id}: "
            f"AP={metrics[ap_key]:.4f}"
        )
        print(f"  {query_lookup[query_id]}")


if __name__ == "__main__":
    main()
