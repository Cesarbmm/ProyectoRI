"""Experimento aislado: validation -> selección congelada -> comprobación test."""

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from datasets import load_from_disk

from ri_fiqa.evaluation import aggregate_metrics, evaluate_query, write_trec_ranking
from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.preprocessing import PreprocessConfig, TextPreprocessor
from ri_fiqa.preprocessing_experiment import (
    B_GRID, K1_GRID, METRICS, MODELS, PROTOCOL, VARIANTS, select_configuration,
)
from ri_fiqa.retrieval.bm25 import BM25Config, BM25Retriever
from ri_fiqa.retrieval.fusion import weighted_rrf
from ri_fiqa.retrieval.jaccard import JaccardRetriever
from ri_fiqa.retrieval.tfidf import TfidfRetriever

# Reutiliza el lector TREC ya validado del proyecto.
from evaluar_hibrido import read_run


ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump(path, value):
    # Las corridas y la selección nunca se sobrescriben.
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def relative(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def semantic_hashes():
    folder = ROOT / "data/processed/semantic_bge"
    return {relative(path): sha256(path) for path in sorted(folder.iterdir()) if path.is_file()}


def source_hashes():
    files = [Path(__file__), *sorted((ROOT / "src/ri_fiqa").glob("*.py")),
             *sorted((ROOT / "src/ri_fiqa/retrieval").glob("*.py"))]
    return {relative(path): sha256(path) for path in files}


def split_data(split):
    # En validation se abre exclusivamente el subdirectorio validation.
    qrels = load_from_disk(str(ROOT / "data/raw/qrels" / split))
    queries = load_from_disk(str(ROOT / "data/raw/queries"))
    lookup = {str(row["_id"]): row["text"] for row in queries}
    relevant = defaultdict(set)
    for row in qrels:
        qid = str(row["query-id"])
        relevant.setdefault(qid, set())
        if int(row["score"]) > 0:
            relevant[qid].add(str(row["corpus-id"]))
    expected = 500 if split == "validation" else 648
    if len(relevant) != expected or not set(relevant).issubset(lookup):
        raise ValueError(f"Se esperaban {expected} consultas completas en {split}.")
    ids = sorted(relevant)
    return ids, lookup, relevant, {"queries": queries._fingerprint, "qrels": qrels._fingerprint}


def score_rankings(rankings, relevant):
    if set(rankings) != set(relevant):
        raise ValueError("Los IDs de los rankings no coinciden con los qrels.")
    return {qid: evaluate_query(rankings[qid], relevant[qid], depth=1000) for qid in sorted(relevant)}


def semantic_rankings(split, relevant, corpus):
    """Reusa rankings BGE inmutables, comprobados contra métricas históricas."""
    run = ROOT / f"results/service_bge_{split}_top1000.trec"
    metrics = ROOT / f"results/service_bge_{split}_metrics.json"
    metadata = load(ROOT / "data/processed/semantic_bge/metadata.json")
    if metadata["corpus_fingerprint"] != corpus._fingerprint:
        raise ValueError("BGE y corpus no tienen el mismo fingerprint.")
    cached = read_run(run)
    ids = set(load(ROOT / "data/processed/semantic_bge/doc_ids.json"))
    if any(len(ranking) != 1000 or not set(ranking).issubset(ids) for ranking in cached.values()):
        raise ValueError("El ranking BGE no contiene 1000 documentos válidos por consulta.")
    per_query = score_rankings(cached, relevant)
    historical = load(metrics)
    if historical["split"] != split or historical["per_query"] != per_query:
        raise ValueError("Los rankings BGE no reproducen las métricas registradas.")
    provenance = {relative(path): sha256(path) for path in (run, metrics)}
    return cached, provenance


def evaluate(retriever, ids, lookup, relevant, output, variant, model, split, parameters):
    started = perf_counter()
    rankings = {}
    run_path = output / f"{variant}_{model}_{split}.trec"
    with run_path.open("x", encoding="utf-8") as stream:
        for qid in ids:
            results = retriever.search(lookup[qid], top_k=1000)
            rankings[qid] = [result.doc_id for result in results]
            write_trec_ranking(stream, qid, results, f"{variant}_{model}")
    per_query = score_rankings(rankings, relevant)
    report = {
        "variant": variant, "model": model, "split": split,
        "dataset": "BeIR/fiqa", "queries_evaluated": len(ids),
        "retrieval_depth": 1000, "parameters": parameters,
        "preprocessing": asdict(retriever.index.preprocessor.config),
        "search_seconds": perf_counter() - started,
        "aggregate": aggregate_metrics(per_query), "per_query": per_query,
        "ranking_sha256": sha256(run_path),
        "trec_score_policy": "ordinal_rank_descending",
        "tie_break": "score_desc_then_document_id_desc",
    }
    dump(output / f"{variant}_{model}_{split}.json", report)
    print(f"{variant}/{model}: MAP={report['aggregate']['MAP@1000']:.6f} "
          f"({report['search_seconds']:.1f}s)", flush=True)
    return report, rankings


def hybrid_report(lexical, semantic, relevant, output, variant, split, parameters):
    rankings = {}
    path = output / f"{variant}_hybrid_{split}.trec"
    with path.open("x", encoding="utf-8") as stream:
        for qid in sorted(relevant):
            results = weighted_rrf(lexical[qid], semantic[qid], top_k=1000, **PROTOCOL["rrf"])
            rankings[qid] = [result.doc_id for result in results]
            write_trec_ranking(stream, qid, results, f"{variant}_hybrid")
    per_query = score_rankings(rankings, relevant)
    report = {
        "variant": variant, "model": "hybrid", "split": split,
        "queries_evaluated": len(relevant), "retrieval_depth": 1000,
        "parameters": {"bm25": parameters, "rrf": PROTOCOL["rrf"]},
        "aggregate": aggregate_metrics(per_query), "per_query": per_query,
        "ranking_sha256": sha256(path),
    }
    dump(output / f"{variant}_hybrid_{split}.json", report)
    print(f"{variant}/hybrid: MAP={report['aggregate']['MAP@1000']:.6f}", flush=True)
    return report


def comparison_table(reports, output, split):
    rows = [{"configuration": variant, "model": model, **{
        metric: report["aggregate"][metric] for metric in METRICS
    }} for variant, models in reports.items() for model, report in models.items()]
    with (output / f"comparison_{split}.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["configuration", "model", *METRICS])
        writer.writeheader()
        writer.writerows(rows)
    text = "| Configuración | Modelo | MAP@1000 | NDCG@10 | MRR@10 | Recall@100 |\n"
    text += "|---|---|---:|---:|---:|---:|\n"
    for row in rows:
        text += f"| {row['configuration']} | {row['model']} | " + " | ".join(
            f"{row[metric]:.6f}" for metric in METRICS
        ) + " |\n"
    (output / f"comparison_{split}.md").write_text(text, encoding="utf-8")


def validation(output):
    # Falla ante una carpeta existente; nunca toca los resultados históricos.
    output.mkdir(parents=True, exist_ok=False)
    index_dir = ROOT / "data/processed" / output.name
    index_dir.mkdir(parents=True, exist_ok=False)
    corpus = load_from_disk(str(ROOT / "data/raw/corpus"))
    ids, lookup, relevant, fingerprints = split_data("validation")
    bge_before = semantic_hashes()
    semantic, semantic_provenance = semantic_rankings("validation", relevant, corpus)
    import nltk
    from nltk.corpus import wordnet
    wordnet.ensure_loaded()
    resource = Path(str(nltk.data.find("corpora/wordnet.zip")))
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "protocol": PROTOCOL, "source_sha256": source_hashes(),
        "python": platform.python_version(),
        "packages": {name: importlib.metadata.version(name) for name in
                     ("nltk", "numpy", "datasets", "scikit-learn", "ir-measures")},
        "wordnet_version": wordnet.get_version(), "wordnet_zip_sha256": sha256(resource),
        "corpus_fingerprint": corpus._fingerprint, "data_fingerprints": fingerprints,
        "query_ids": ids, "bge_sha256": bge_before,
        "semantic_cache_sha256": semantic_provenance,
    }
    dump(output / "protocol.json", manifest)
    reports = {}
    indices = {}
    best_parameters = {}
    for variant in VARIANTS:
        print(f"Construyendo índice {variant} ({len(corpus)} documentos)...", flush=True)
        started = perf_counter()
        index = InvertedIndex(TextPreprocessor(PreprocessConfig(morphology=variant)))
        index.build(corpus)
        path = index_dir / f"{variant}.json.gz"
        index.save(path)
        indices[variant] = {
            "path": relative(path), "sha256": sha256(path),
            "documents": index.num_documents, "vocabulary": index.vocabulary_size,
            "tokens": index.total_tokens, "postings": index.total_postings,
            "build_seconds": perf_counter() - started,
        }
        reports[variant] = {}
        for model, retriever_cls in (("jaccard", JaccardRetriever), ("tfidf", TfidfRetriever)):
            report, _ = evaluate(retriever_cls(index), ids, lookup, relevant, output, variant, model, "validation", {})
            reports[variant][model] = report
        grid = []
        best_report = best_rankings = None
        for k1 in K1_GRID:
            for b in B_GRID:
                parameters = {"k1": k1, "b": b}
                report, rankings = evaluate(
                    BM25Retriever(index, BM25Config(**parameters)), ids, lookup, relevant,
                    output, variant, f"bm25_k1-{k1}_b-{b}", "validation", parameters,
                )
                grid.append({**parameters, **report["aggregate"]})
                if best_report is None or report["aggregate"]["MAP@1000"] > best_report["aggregate"]["MAP@1000"]:
                    best_report, best_rankings = report, rankings
        dump(output / f"{variant}_bm25_grid.json", grid)
        best_parameters[variant] = best_report["parameters"]
        reports[variant]["bm25"] = best_report
        dump(output / f"{variant}_bm25_validation.json", best_report)
        reports[variant]["hybrid"] = hybrid_report(
            best_rankings, semantic, relevant, output, variant, "validation", best_report["parameters"],
        )
        del index

    # Control del baseline reconstruido frente a las cuatro corridas históricas.
    for model in MODELS:
        historical = load(ROOT / f"results/service_{model}_validation_metrics.json")
        if reports["baseline"][model]["per_query"] != historical["per_query"]:
            raise ValueError(f"El baseline reconstruido no reproduce {model} histórico.")
    if semantic_hashes() != bge_before:
        raise ValueError("Los artefactos BGE cambiaron durante la evaluación.")
    comparison_table(reports, output, "validation")
    selection = select_configuration(reports)
    dump(output / "statistics_validation.json", selection)
    winner = selection["winner"]
    freeze = {
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection_split": "validation", "winner": winner,
        "preprocessing": asdict(PreprocessConfig(morphology=winner)),
        "bm25": best_parameters[winner], "rrf": PROTOCOL["rrf"],
        "indices": indices, "bge_sha256": bge_before,
        "global_map": selection["global_map"],
        "protocol_sha256": sha256(output / "protocol.json"),
        "statistics_sha256": sha256(output / "statistics_validation.json"),
        "validation_artifacts_sha256": {
            path.name: sha256(path) for path in sorted(output.iterdir()) if path.is_file()
        },
        "test_used_for_selection": False,
    }
    dump(output / "selection_frozen.json", freeze)
    print(f"SELECCIÓN CONGELADA: {winner}, BM25={best_parameters[winner]}", flush=True)


def final_check(output):
    freeze_path = output / "selection_frozen.json"
    freeze = load(freeze_path)  # Obligatorio ANTES de abrir test.
    if freeze["selection_split"] != "validation" or freeze["test_used_for_selection"]:
        raise ValueError("La selección no procede exclusivamente de validation.")
    if (output / "final_test").exists():
        raise FileExistsError("La comprobación test ya existe; no se permiten reajustes.")
    for name, expected in freeze["validation_artifacts_sha256"].items():
        if sha256(output / name) != expected:
            raise ValueError(f"Artefacto validation modificado después de congelar: {name}")
    if semantic_hashes() != freeze["bge_sha256"]:
        raise ValueError("BGE cambió después de congelar.")
    variant = freeze["winner"]
    path = ROOT / freeze["indices"][variant]["path"]
    if sha256(path) != freeze["indices"][variant]["sha256"]:
        raise ValueError("El índice seleccionado cambió después de congelar.")
    index = InvertedIndex.load(path)
    if asdict(index.preprocessor.config) != freeze["preprocessing"]:
        raise ValueError("Preprocesamiento incompatible con la selección.")
    final_dir = output / "final_test"
    final_dir.mkdir()
    # Registra la selección y su hash antes de acceder a etiquetas test.
    dump(final_dir / "started.json", {"selection_sha256": sha256(freeze_path),
         "started_at_utc": datetime.now(timezone.utc).isoformat()})
    corpus = load_from_disk(str(ROOT / "data/raw/corpus"))
    ids, lookup, relevant, fingerprints = split_data("test")
    semantic, provenance = semantic_rankings("test", relevant, corpus)
    reports = {variant: {}}
    for model, retriever in (
        ("jaccard", JaccardRetriever(index)), ("tfidf", TfidfRetriever(index)),
        ("bm25", BM25Retriever(index, BM25Config(**freeze["bm25"]))),
    ):
        report, rankings = evaluate(retriever, ids, lookup, relevant, final_dir, variant, model,
                                    "test", freeze["bm25"] if model == "bm25" else {})
        reports[variant][model] = report
        if model == "bm25":
            reports[variant]["hybrid"] = hybrid_report(
                rankings, semantic, relevant, final_dir, variant, "test", freeze["bm25"],
            )
    per_query = score_rankings(semantic, relevant)
    dump(final_dir / "bge_unchanged_test.json", {"split": "test", "queries_evaluated": len(ids),
         "aggregate": aggregate_metrics(per_query), "per_query": per_query})
    comparison_table(reports, final_dir, "test")
    if semantic_hashes() != freeze["bge_sha256"]:
        raise ValueError("Los artefactos BGE cambiaron durante test.")
    dump(final_dir / "completed.json", {
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection_sha256": sha256(freeze_path), "winner": variant,
        "queries_evaluated": len(ids), "data_fingerprints": fingerprints,
        "semantic_cache_sha256": provenance, "bge_unchanged": True, "retuned": False,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("validation", "final"))
    parser.add_argument("--output", type=Path, default=ROOT / "results/preprocessing_v1")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "results") or output == ROOT / "results":
        parser.error("Usa una subcarpeta nueva de results dentro del repositorio.")
    if args.phase == "validation":
        validation(output)
    else:
        final_check(output)


if __name__ == "__main__":
    main()
