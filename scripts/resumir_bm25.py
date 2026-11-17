
"""Compara configuraciones BM25 sobre FiQA validation."""

import csv
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = BASE_DIR / "results"

archivos = list(
    RESULTS_DIR.glob(
        "bm25_k1-*_b-*_validation_metrics.json"
    )
)

if not archivos:
    raise SystemExit(
        "No hay experimentos BM25 para comparar."
    )

experimentos = []

for archivo in archivos:
    with archivo.open(encoding="utf-8") as f:
        reporte = json.load(f)

    if (
        reporte["split"] != "validation"
        or reporte["retrieval_depth"] != 1000
    ):
        continue

    params = reporte["model_parameters"]
    metrics = reporte["aggregate"]

    experimentos.append({
        "k1": params["k1"],
        "b": params["b"],
        "MAP@1000": metrics["MAP@1000"],
        "MRR@10": metrics["MRR@10"],
        "NDCG@10": metrics["NDCG@10"],
        "Recall@100": metrics["Recall@100"],
        "P@10": metrics["P@10"],
        "search_seconds": reporte["search_seconds"],
    })

if not experimentos:
    raise SystemExit("No hay experimentos válidos.")

# Prioridad principal: MAP.
# Desempate: NDCG@10 y Recall@100.
experimentos.sort(
    key=lambda row: (
        row["MAP@1000"],
        row["NDCG@10"],
        row["Recall@100"],
    ),
    reverse=True
)

print("\n=== COMPARACIÓN BM25 / VALIDATION ===")
print(
    f"{'k1':>5} {'b':>5} {'MAP':>10} "
    f"{'MRR@10':>10} {'NDCG@10':>10} "
    f"{'R@100':>10}"
)

for e in experimentos:
    print(
        f"{e['k1']:5.2f} "
        f"{e['b']:5.2f} "
        f"{e['MAP@1000']:10.6f} "
        f"{e['MRR@10']:10.6f} "
        f"{e['NDCG@10']:10.6f} "
        f"{e['Recall@100']:10.6f}"
    )

mejor = experimentos[0]

print("\n=== MEJOR CONFIGURACIÓN EN VALIDATION ===")
print(f"k1: {mejor['k1']}")
print(f"b:  {mejor['b']}")
print(f"MAP@1000: {mejor['MAP@1000']:.6f}")
print(f"NDCG@10:  {mejor['NDCG@10']:.6f}")

# Exportar un CSV para el informe académico.
destino = RESULTS_DIR / "bm25_validation_grid.csv"

with destino.open(
    "w", newline="", encoding="utf-8"
) as file:
    writer = csv.DictWriter(
        file,
        fieldnames=list(experimentos[0])
    )

    writer.writeheader()
    writer.writerows(experimentos)

print(f"\nResultados guardados: {destino}")
