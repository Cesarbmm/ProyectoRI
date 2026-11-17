
"""Localiza diferencias entre nuestra MRR y ir-measures."""

import json
from pathlib import Path

import ir_measures
from ir_measures import RR


BASE_DIR = Path(__file__).resolve().parents[1]
RESULTS = BASE_DIR / "results"

with (
    RESULTS / "jaccard_validation_metrics.json"
).open(encoding="utf-8") as file:
    report = json.load(file)

qrels = list(ir_measures.read_trec_qrels(
    str(RESULTS / "qrels_validation.trec")
))

run = list(ir_measures.read_trec_run(
    str(RESULTS / "jaccard_validation_top1000.trec")
))

reference = {
    metric.query_id: metric.value
    for metric in ir_measures.iter_calc(
        [RR @ 10], qrels, run
    )
}

differences = []

for qid, metrics in report["per_query"].items():
    own = metrics["RR@10"]
    external = reference.get(qid, 0.0)

    delta = abs(own - external)

    if delta > 1e-9:
        differences.append(
            (qid, own, external, delta)
        )

differences.sort(
    key=lambda row: row[3],
    reverse=True
)

print("=== DIAGNÓSTICO MRR@10 ===")
print("Consultas con discrepancias:", len(differences))

for qid, own, external, delta in differences[:10]:
    print(
        f"QID={qid} | "
        f"Propia={own:.6f} | "
        f"Referencia={external:.6f} | "
        f"Diferencia={delta:.6f}"
    )

print("\n=== RANKINGS DE CONSULTAS DISCREPANTES ===")

relevant_by_query = {}

for qrel in qrels:
    if qrel.relevance > 0:
        relevant_by_query.setdefault(
            qrel.query_id, set()
        ).add(qrel.doc_id)

for qid, _, _, _ in differences[:3]:
    print(f"\nConsulta: {qid}")

    relevant = relevant_by_query.get(qid, set())

    ranked = [
        doc for doc in run
        if doc.query_id == qid
    ]

    for rank, doc in enumerate(ranked[:10], start=1):
        is_relevant = doc.doc_id in relevant
        print(
            f"{rank:2d}. ID={doc.doc_id} "
            f"score={doc.score:.8f} "
            f"relevante={is_relevant}"
        )
