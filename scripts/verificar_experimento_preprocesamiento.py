"""Contrasta métricas por consulta de las corridas nuevas con ir-measures."""

import argparse
from pathlib import Path

import ir_measures
from ir_measures import AP, R, RR, nDCG

from experimentar_preprocesamiento import ROOT, dump, load, sha256


def verify(output, include_final=False):
    pairs = [(output, "validation")]
    if include_final:
        if not (output / "final_test/completed.json").is_file():
            raise ValueError("La comprobación test todavía no está completa.")
        pairs.append((output / "final_test", "test"))
    measures = {AP @ 1000: "AP@1000", nDCG @ 10: "NDCG@10", RR @ 10: "RR@10", R @ 100: "Recall@100"}
    checked = []
    for directory, split in pairs:
        qrels_path = ROOT / f"results/qrels_{split}.trec"
        qrels = list(ir_measures.read_trec_qrels(str(qrels_path)))
        seen = set()
        for report_path in sorted(directory.glob(f"*_{split}.json")):
            report = load(report_path)
            if "variant" not in report or "per_query" not in report:
                continue
            run = directory / f"{report['variant']}_{report['model']}_{split}.trec"
            if run in seen:
                continue
            seen.add(run)
            if sha256(run) != report["ranking_sha256"]:
                raise ValueError(f"Ranking modificado: {run}")
            maximum = 0.0
            count = 0
            for metric in ir_measures.iter_calc(list(measures), qrels, ir_measures.read_trec_run(str(run))):
                own = report["per_query"][metric.query_id][measures[metric.measure]]
                maximum = max(maximum, abs(metric.value - own))
                count += 1
            if maximum > 1e-9 or count != 4 * len(report["per_query"]):
                raise ValueError(f"Discrepancias con ir-measures: {run}: {maximum}, {count}")
            checked.append({"run": run.relative_to(ROOT).as_posix(), "split": split,
                            "queries": len(report["per_query"]), "metric_values_checked": count,
                            "max_absolute_difference": maximum})
            print(f"OK {run.name}, delta max={maximum:.3g}", flush=True)
    if not checked:
        raise ValueError("No hay corridas para verificar.")
    destination = output / ("verification_with_final.json" if include_final else "verification_validation.json")
    dump(destination, {"provider": "ir-measures", "tolerance": 1e-9, "runs": checked})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/preprocessing_v1")
    parser.add_argument("--include-final", action="store_true")
    args = parser.parse_args()
    verify(args.output.resolve(), args.include_final)


if __name__ == "__main__":
    main()
