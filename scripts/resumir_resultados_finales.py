
"""Compara resultados finales de FiQA validation y test."""

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

MODELS = (
    "jaccard",
    "tfidf",
    "bm25",
    "bge",
    "hybrid",
)

METRICS = (
    "MAP@1000",
    "P@5",
    "P@10",
    "Recall@10",
    "Recall@100",
    "MRR@10",
    "NDCG@10",
)


def read_report(model, split):
    path = RESULTS / (
        f"service_{model}_{split}_metrics.json"
    )

    if not path.is_file():
        raise FileNotFoundError(path)

    with path.open(encoding="utf-8") as file:
        report = json.load(file)

    expected_queries = (
        500 if split == "validation" else 648
    )

    if report["split"] != split:
        raise ValueError(
            f"Partición incorrecta: {path.name}"
        )

    if report["queries_evaluated"] != expected_queries:
        raise ValueError(
            f"Cantidad de consultas incorrecta: {path.name}"
        )

    if report["retrieval_depth"] != 1000:
        raise ValueError(
            f"Profundidad incorrecta: {path.name}"
        )

    return report


def main():
    rows = []

    for model in MODELS:
        validation = read_report(model, "validation")
        test = read_report(model, "test")

        row = {"model": model}

        for metric in METRICS:
            val = validation["aggregate"][metric]
            tst = test["aggregate"][metric]

            row[f"{metric}_validation"] = val
            row[f"{metric}_test"] = tst
            row[f"{metric}_difference"] = tst - val

        rows.append(row)

    print("\n=== FIQA: VALIDATION VS TEST ===")

    print(
        f"{'Modelo':<10} "
        f"{'MAP val':>10} "
        f"{'MAP test':>10} "
        f"{'Delta MAP':>12} "
        f"{'NDCG test':>12} "
        f"{'R@100 test':>12}"
    )

    for row in rows:
        print(
            f"{row['model']:<10} "
            f"{row['MAP@1000_validation']:>10.6f} "
            f"{row['MAP@1000_test']:>10.6f} "
            f"{row['MAP@1000_difference']:>+12.6f} "
            f"{row['NDCG@10_test']:>12.6f} "
            f"{row['Recall@100_test']:>12.6f}"
        )

    output = RESULTS / "comparacion_final_fiqa.csv"

    with output.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0]),
        )

        writer.writeheader()
        writer.writerows(rows)

    print("\nReporte CSV:", output)


if __name__ == "__main__":
    main()
