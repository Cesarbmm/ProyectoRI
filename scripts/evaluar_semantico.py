
"""Evalúa recuperación semántica sobre FiQA validation."""

import argparse
from importlib.metadata import metadata
import json

from collections import defaultdict
from pathlib import Path
from time import perf_counter

import faiss
import torch

from datasets import load_from_disk
from sentence_transformers import SentenceTransformer

from ri_fiqa.evaluation import (
    evaluate_query,
    aggregate_metrics,
    write_trec_ranking,
)
from ri_fiqa.retrieval.semantic import SemanticRetriever

from ri_fiqa.embedding_models import configure_encoder

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
RESULTS_DIR = BASE_DIR / "results"


def main():
    parser = argparse.ArgumentParser(
        description="Evalúa FAISS + SentenceTransformers."
    )

    parser.add_argument(
        "--name", default="semantic_minilm"
    )
    parser.add_argument(
        "--depth", type=int, default=1000
    )
    parser.add_argument(
        "--batch-size", type=int, default=32
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto"
    )

    parser.add_argument(
        "--query-prompt-mode",
        choices=["saved", "none"],
        default="saved",
        help=(
            "saved: utiliza la instrucción guardada; "
            "none: desactiva la instrucción de consulta BGE."
        ),
    )

    args = parser.parse_args()

    if args.depth < 100 or args.batch_size <= 0:
        parser.error("Parámetros de evaluación inválidos.")

    if not args.name.replace("_", "").isalnum():
        parser.error("Nombre de índice inválido.")

    index_dir = PROCESSED_DIR / args.name

    print("[1/4] Cargando índice FAISS...")

    with (
        index_dir / "metadata.json"
    ).open(encoding="utf-8") as file:
        metadata = json.load(file)

    if (
        args.query_prompt_mode == "none"
        and metadata.get("encoder_profile") != "bge"
    ):
        parser.error(
            "El experimento sin instrucción está "
            "habilitado únicamente para BGE."
        )
    
    query_prompt = metadata.get("query_prompt")
    
    if args.query_prompt_mode == "none":
        query_prompt = ""    

    # Evitar evaluar un piloto como corpus completo.
    if (
        metadata["processed_documents"]
        != metadata["original_corpus_size"]
    ):
        parser.error(
            "El índice contiene solo parte del corpus."
        )

    index = faiss.read_index(
        str(index_dir / "index.faiss")
    )

    with (
        index_dir / "doc_ids.json"
    ).open(encoding="utf-8") as file:
        doc_ids = json.load(file)

    device = args.device
    if device == "auto":
        device = (
            "cuda" if torch.cuda.is_available()
            else "cpu"
        )

    print("[2/4] Cargando encoder...")

    started = perf_counter()

    # encoder = SentenceTransformer(
    #     metadata["model_id"],
    #     device=device
    # )

    # if (
    #     encoder.get_sentence_embedding_dimension()
    #     != index.d
    # ):
    #     raise ValueError(
    #         "Dimensión del modelo incompatible con FAISS."
    #     )

    # retriever = SemanticRetriever(
    #     encoder, index, doc_ids
    # )

    model = SentenceTransformer(
        metadata["model_id"],
        device=device,
    )

    if model.get_sentence_embedding_dimension() != index.d:
        raise ValueError(
            "Dimensión del encoder incompatible con FAISS."
        )

    encoder = configure_encoder(
        model,
        query_prompt=query_prompt,
        document_prompt=metadata.get("document_prompt"),
    )

    retriever = SemanticRetriever(
        encoder,
        index,
        doc_ids,
    )

    preparation_seconds = perf_counter() - started

    queries = load_from_disk(
        str(RAW_DIR / "queries")
    )

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
        raise ValueError("Hay consultas inexistentes.")

    texts = [
        query_lookup[qid] for qid in query_ids
    ]

    print("[3/4] Ejecutando búsquedas semánticas...")
    print("Consultas:", len(texts))
    print("Dispositivo:", device)

    started = perf_counter()

    rankings = retriever.search_many(
        texts,
        top_k=args.depth,
        batch_size=args.batch_size
    )

    search_seconds = perf_counter() - started

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    experiment_name = args.name

    if args.query_prompt_mode == "none":
        experiment_name += "_noprompt"

    run_path = RESULTS_DIR / (
        f"{experiment_name}_validation_top{args.depth}.trec"
    )

    per_query = {}

    with run_path.open(
        "w", encoding="utf-8"
    ) as file:

        for qid, results in zip(
            query_ids, rankings
        ):
            ranked_ids = [
                result.doc_id for result in results
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
                run_name=args.name
            )

    print("[4/4] Calculando y guardando métricas...")

    aggregate = aggregate_metrics(per_query)

    report = {
        "model": experiment_name,
        "source_index": args.name,
        "query_prompt_mode": args.query_prompt_mode,
        "query_prompt": query_prompt,
        "document_prompt": metadata.get("document_prompt"),
        "dataset": "BeIR/fiqa",
        "split": "validation",
        "queries_evaluated": len(query_ids),
        "retrieval_depth": args.depth,
        "encoder": metadata["model_id"],
        "indexed_documents": index.ntotal,
        "preparation_seconds": preparation_seconds,
        "search_seconds": search_seconds,
        "trec_score_policy": "ordinal_rank_descending",
        "aggregate": aggregate,
        "per_query": per_query,
    }

    output_path = RESULTS_DIR / (
        f"{experiment_name}_validation_metrics.json"
    )

    with output_path.open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(report, file, indent=2)

    print("\n=== SEMANTIC / VALIDATION ===")

    for metric, value in aggregate.items():
        print(f"{metric:15s}: {value:.6f}")

    print(
        f"\nCarga del modelo: {preparation_seconds:.2f} s"
    )
    print(
        f"Codificación y búsqueda: {search_seconds:.2f} s"
    )

    print("Métricas:", output_path)
    print("Ranking:", run_path)


if __name__ == "__main__":
    main()
