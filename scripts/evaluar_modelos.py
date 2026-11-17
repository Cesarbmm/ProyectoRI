
"""Evalúa recuperadores léxicos sobre FiQA validation."""

import argparse
from email import parser
from html import parser
import json

from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from datasets import load_from_disk

from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.evaluation import (
    evaluate_query,
    aggregate_metrics,
    write_trec_ranking,
)
from ri_fiqa.retrieval.jaccard import JaccardRetriever
from ri_fiqa.retrieval.tfidf import TfidfRetriever

from ri_fiqa.retrieval.bm25 import (
    BM25Config,
    BM25Retriever,
)

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
RESULTS_DIR = BASE_DIR / "results"

INDEX_PATH = (
    BASE_DIR / "data" / "processed"
    / "inverted_index_stopwords.json.gz"
)

MODELS = {
    "jaccard": JaccardRetriever,
    "tfidf": TfidfRetriever,
    "bm25": BM25Retriever,
}


def main():
    parser = argparse.ArgumentParser(
        description="Evaluación reproducible sobre FiQA."
    )

    parser.add_argument(
        "--model",
        choices=MODELS,
        required=True
    )

    parser.add_argument(
        "--depth",
        type=int,
        default=1000
    )

    parser.add_argument(
        "--k1", type=float, default=1.2
    )

    parser.add_argument(
        "--b", type=float, default=0.75
    )

    args = parser.parse_args()

    if args.depth < 100:
        parser.error("depth debe ser >= 100.")

    if not INDEX_PATH.exists():
        parser.error("No se encontró el índice invertido.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/4] Cargando datos e índice...")
    index = InvertedIndex.load(INDEX_PATH)

    queries = load_from_disk(str(RAW_DIR / "queries"))
    qrels = load_from_disk(
        str(RAW_DIR / "qrels")
    )["validation"]

    query_lookup = {
        str(row["_id"]): row["text"]
        for row in queries
    }

    relevant_by_query = defaultdict(set)

    for row in qrels:
        qid = str(row["query-id"])
        doc_id = str(row["corpus-id"])

        relevant_by_query.setdefault(qid, set())

        if int(row["score"]) > 0:
            relevant_by_query[qid].add(doc_id)

    query_ids = sorted(relevant_by_query)

    if not set(query_ids).issubset(query_lookup):
        raise ValueError(
            "Existen IDs de consulta no encontrados."
        )

    print("[2/4] Preparando recuperador...")
    start_prepare = perf_counter()

    if args.model == "bm25":
        config = BM25Config(k1=args.k1, b=args.b)
        retriever = BM25Retriever(index, config)
    else:
        retriever = MODELS[args.model](index)

    preparation_seconds = (
        perf_counter() - start_prepare
    )

    print(
        f"Modelo: {args.model}, "
        f"consultas: {len(query_ids)}"
    )

    print("[3/4] Ejecutando evaluación...")
    start_search = perf_counter()

    per_query = {}

    if args.model == "bm25":
        experiment_name = (
            f"bm25_k1-{args.k1:g}_b-{args.b:g}"
        )
    else:
        experiment_name = args.model

    run_path = RESULTS_DIR / (
        f"{experiment_name}_validation_top{args.depth}.trec"
    )

    with run_path.open("w", encoding="utf-8") as file:
        for number, qid in enumerate(query_ids, start=1):
            query_text = query_lookup[qid]

            results = retriever.search(
                query_text,
                top_k=args.depth
            )

            ranked_ids = [
                result.doc_id
                for result in results
            ]

            per_query[qid] = evaluate_query(
                ranked_ids,
                relevant_by_query[qid],
                depth=args.depth
            )

            write_trec_ranking(
                file=file,
                query_id=qid,
                results=results,
                run_name=args.model,
            )

            if number % 100 == 0:
                print(
                    f"    {number}/{len(query_ids)} consultas"
                )

    search_seconds = perf_counter() - start_search

    print("[4/4] Guardando métricas...")

    aggregate = aggregate_metrics(per_query)

    report = {
        "model": args.model,
        "dataset": "BeIR/fiqa",
        "split": "validation",
        "queries_evaluated": len(query_ids),
        "retrieval_depth": args.depth,
        "preprocessing": asdict(
            index.preprocessor.config
        ),
        "preparation_seconds": preparation_seconds,
        "search_seconds": search_seconds,
        "aggregate": aggregate,
        "per_query": per_query,
        "model_parameters": ({
            "k1": args.k1,
            "b": args.b
        } if args.model == "bm25" else {}),
        "trec_score_policy": "ordinal_rank_descending",
        "tie_break": "score_desc_then_document_id_desc",
    }

    output = RESULTS_DIR / (
        f"{experiment_name}_validation_metrics.json"
    )

    with output.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print(f"\n=== {args.model.upper()} / VALIDATION ===")

    for metric, value in aggregate.items():
        print(f"{metric:15s}: {value:.6f}")

    print(
        f"\nPreparación: {preparation_seconds:.2f} s"
    )
    print(f"Búsquedas:   {search_seconds:.2f} s")
    print(f"Métricas:    {output}")
    print(f"Ranking:     {run_path}")


if __name__ == "__main__":
    main()
