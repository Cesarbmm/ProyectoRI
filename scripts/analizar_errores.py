
"""Análisis cualitativo de los rankings finales de FiQA."""

import argparse
import json

from collections import defaultdict
from pathlib import Path

from datasets import load_from_disk


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RAW = ROOT / "data" / "raw"

MODELS = ("bm25", "bge", "hybrid")


def read_metrics(model):
    path = RESULTS / (
        f"service_{model}_test_metrics.json"
    )

    with path.open(encoding="utf-8") as file:
        report = json.load(file)

    if report["split"] != "test":
        raise ValueError("El reporte no corresponde a test.")

    return report["per_query"]


def read_ranking(model):
    path = RESULTS / (
        f"service_{model}_test_top1000.trec"
    )

    rows = defaultdict(list)

    with path.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            qid, _, doc_id, rank, _, _ = line.split()
            rows[qid].append((int(rank), doc_id))

    return {
        qid: [
            doc_id
            for _, doc_id in sorted(items)
        ]
        for qid, items in rows.items()
    }


def clean(text, limit=240):
    text = " ".join((text or "").split())
    return (
        text[:limit] + "..."
        if len(text) > limit else text
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--examples", type=int, default=3)
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args()

    if args.examples <= 0 or args.top <= 0:
        parser.error("Los límites deben ser positivos.")

    metrics = {
        model: read_metrics(model)
        for model in MODELS
    }

    rankings = {
        model: read_ranking(model)
        for model in MODELS
    }

    queries = load_from_disk(str(RAW / "queries"))
    corpus = load_from_disk(str(RAW / "corpus"))
    qrels = load_from_disk(str(RAW / "qrels"))["test"]

    query_text = {
        str(row["_id"]): row["text"]
        for row in queries
    }

    documents = {
        str(row["_id"]): row["text"] or ""
        for row in corpus
    }

    relevant = defaultdict(set)

    for row in qrels:
        qid = str(row["query-id"])
        relevant.setdefault(qid, set())

        if int(row["score"]) > 0:
            relevant[qid].add(str(row["corpus-id"]))

    query_ids = set(relevant)

    for model in MODELS:
        if set(metrics[model]) != query_ids:
            raise ValueError(
                f"Consultas distintas en {model}."
            )

    groups = [
        ("BGE supera a BM25", "bge", "bm25"),
        ("BM25 supera a BGE", "bm25", "bge"),
        ("El híbrido mejora BGE", "hybrid", "bge"),
        ("El híbrido empeora BGE", "bge", "hybrid"),
    ]

    lines = [
        "# Análisis cualitativo — FiQA test",
        "",
        "Selección automática de consultas con mayor "
        "diferencia de AP@1000.",
        "",
        "Un documento marcado como «no etiquetado» "
        "no necesariamente es irrelevante.",
        "",
    ]

    for title, winner, loser in groups:
        differences = []

        for qid in query_ids:
            ap_winner = metrics[winner][qid]["AP@1000"]
            ap_loser = metrics[loser][qid]["AP@1000"]
            delta = ap_winner - ap_loser

            if delta > 1e-9:
                differences.append((delta, qid))

        differences.sort(
            key=lambda item: (-item[0], item[1])
        )

        lines.extend([
            f"## {title}",
            "",
            f"Consultas con mejora: {len(differences)}",
            "",
        ])

        print(
            f"{title}: {len(differences)} "
            "consultas con AP superior"
        )

        for delta, qid in differences[:args.examples]:
            lines.extend([
                f"### Consulta {qid}",
                "",
                f"**Pregunta:** {query_text[qid]}",
                "",
                f"**Diferencia de AP:** +{delta:.6f}",
                "",
                f"- {winner}: "
                f"{metrics[winner][qid]['AP@1000']:.6f}",
                f"- {loser}: "
                f"{metrics[loser][qid]['AP@1000']:.6f}",
                f"- Documentos relevantes anotados: "
                f"{len(relevant[qid])}",
                "",
            ])

            for model in (winner, loser):
                lines.extend([
                    f"**Top {args.top} — {model}**",
                    "",
                ])

                for rank, doc_id in enumerate(
                    rankings[model].get(qid, [])[:args.top],
                    start=1
                ):
                    label = (
                        "RELEVANTE"
                        if doc_id in relevant[qid]
                        else "NO ETIQUETADO"
                    )

                    lines.extend([
                        f"{rank}. Documento `{doc_id}` "
                        f"— **{label}**",
                        f"   {clean(documents[doc_id])}",
                        "",
                    ])

    output = RESULTS / "analisis_cualitativo_test.md"

    output.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("\nInforme generado:", output)


if __name__ == "__main__":
    main()
