
"""Compara reportes de modelos sobre las mismas consultas."""

import argparse
import json
from pathlib import Path

from ri_fiqa.statistics import paired_comparison


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def load_report(filename):
    path = RESULTS / filename

    with path.open(encoding="utf-8") as file:
        report = json.load(file)

    if report.get("split") != "validation":
        raise ValueError("Solo se admite validation.")

    if report.get("retrieval_depth") != 1000:
        raise ValueError("Se requiere profundidad 1000.")

    return report


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument(
        "--metric", default="AP@1000",
        choices=[
            "AP@1000",
            "RR@10",
            "NDCG@10",
            "Recall@100",
        ],
    )
    parser.add_argument(
        "--output",
        default="comparacion_estadistica.json"
    )

    args = parser.parse_args()

    baseline = load_report(args.baseline)
    candidate = load_report(args.candidate)

    baseline_queries = baseline["per_query"]
    candidate_queries = candidate["per_query"]

    if set(baseline_queries) != set(candidate_queries):
        raise ValueError(
            "Ambos modelos deben evaluar "
            "exactamente las mismas consultas."
        )

    query_ids = sorted(baseline_queries)

    if len(query_ids) != 500:
        raise ValueError(
            f"Se esperaban 500 consultas, "
            f"se encontraron {len(query_ids)}."
        )

    baseline_scores = [
        baseline_queries[qid][args.metric]
        for qid in query_ids
    ]

    candidate_scores = [
        candidate_queries[qid][args.metric]
        for qid in query_ids
    ]

    stats = paired_comparison(
        baseline_scores,
        candidate_scores,
    )

    report = {
        "split": "validation",
        "metric": args.metric,
        "baseline": args.baseline,
        "candidate": args.candidate,
        "statistics": stats,
    }

    output = RESULTS / Path(args.output).name

    with output.open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(report, file, indent=2)

    print("\n=== COMPARACIÓN PAREADA ===")
    print("Métrica:", args.metric)
    print(f"Consultas: {stats['queries']}")
    print(
        f"Baseline: {stats['baseline_mean']:.6f}"
    )
    print(
        f"Candidato: {stats['candidate_mean']:.6f}"
    )
    print(
        f"Diferencia: {stats['delta_absolute']:+.6f}"
    )
    print(
        "Cambio relativo:",
        f"{stats['delta_relative_percent']:+.2f}%"
    )
    print(
        "IC 95%:",
        f"[{stats['ci95_low']:+.6f}, "
        f"{stats['ci95_high']:+.6f}]"
    )
    print(
        "p bilateral:",
        f"{stats['p_permutation_two_sided']:.6f}"
    )
    print(
        "Mejoran / empeoran / iguales:",
        stats["improved_queries"],
        stats["worsened_queries"],
        stats["unchanged_queries"],
    )
    print("\nReporte:", output)


if __name__ == "__main__":
    main()
