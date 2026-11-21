"""Regenera solo rankings BGE faltantes, sin reconstruir ni modificar FAISS."""

import argparse
from pathlib import Path

from ri_fiqa.evaluation import write_trec_ranking
from ri_fiqa.search_service import SearchService

from experimentar_preprocesamiento import (
    ROOT, dump, load, semantic_hashes, sha256, split_data, score_rankings,
)


def regenerate(split, selection=None):
    path = ROOT / f"results/service_bge_{split}_top1000.trec"
    if path.exists():
        raise FileExistsError(f"El ranking ya existe y no se sobrescribirá: {path}")
    before = semantic_hashes()
    if split == "test":
        if selection is None:
            raise ValueError("Para test se exige --selection con una selección congelada.")
        freeze = load(selection)
        if (freeze["selection_split"] != "validation" or freeze["test_used_for_selection"]
                or freeze["bge_sha256"] != before):
            raise ValueError("Selección o BGE incompatibles.")
    ids, lookup, relevant, _ = split_data(split)
    service = SearchService()
    results = service.rank_many([lookup[qid] for qid in ids], model="bge", top_k=1000)
    rankings = {qid: [hit.doc_id for hit in ranking] for qid, ranking in zip(ids, results)}
    # No crea métricas históricas nuevas ni reemplaza las existentes.
    reference = load(ROOT / f"results/service_bge_{split}_metrics.json")
    if score_rankings(rankings, relevant) != reference["per_query"]:
        raise ValueError("Los rankings nuevos no reproducen las métricas BGE históricas; "
                         "se requiere el caché original para una reproducción exacta.")
    if before != semantic_hashes():
        raise ValueError("Los archivos BGE cambiaron.")
    with path.open("x", encoding="utf-8") as stream:
        for qid, ranking in zip(ids, results):
            write_trec_ranking(stream, qid, ranking, "bge")
    dump(path.with_suffix(".provenance.json"), {
        "split": split, "ranking_sha256": sha256(path), "bge_sha256": before,
        "selection_sha256": sha256(selection) if selection else None,
        "historical_metrics_reproduced": True,
    })
    print(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("split", choices=("validation", "test"))
    parser.add_argument("--selection", type=Path)
    args = parser.parse_args()
    regenerate(args.split, args.selection)


if __name__ == "__main__":
    main()
