"""Protocolo de selección de morfología; no accede a datos de test."""

from statistics import fmean

from ri_fiqa.statistics import paired_comparison


VARIANTS = ("baseline", "stemming", "lemmatization")
MODELS = ("jaccard", "tfidf", "bm25", "hybrid")
METRICS = {
    "MAP@1000": "AP@1000",
    "NDCG@10": "NDCG@10",
    "MRR@10": "RR@10",
    "Recall@100": "Recall@100",
}
K1_GRID = (0.8, 1.2, 1.6)
B_GRID = (0.5, 0.75, 0.9)
PROTOCOL = {
    "selection_split": "validation",
    "expected_queries": 500,
    "depth": 1000,
    "variants": VARIANTS,
    "models": MODELS,
    "bm25_grid": {"k1": K1_GRID, "b": B_GRID},
    "bm25_objective": "MAP@1000; ties: lower k1 then lower b",
    "rrf": {"k": 10, "semantic_weight": 0.9},
    "primary": "equal mean MAP@1000 over four affected models",
    "paired_unit": "query; mean AP@1000 over four models per query",
    "repetitions": 10000,
    "seed": 20261120,
    "alpha": 0.05,
    "guardrail_max_relative_loss": 0.02,
    "selection_rule": (
        "positive primary delta, Holm p<0.05 for two comparisons vs baseline; "
        "no model/metric loses >2% relative to baseline; choose highest primary "
        "MAP among eligible variants, else baseline; ties retain baseline"
    ),
    "secondary_statistics": (
        "32 two-sided tests (2 variants x 4 models x 4 metrics), "
        "separate Holm family; exploratory after validation tuning"
    ),
    "lemmatization": "NLTK WordNet 3.0, pos=n (no contextual POS tagging)",
    "stemming": "NLTK SnowballStemmer english",
}


def holm_adjust(p_values):
    """Holm step-down, conservando el orden de entrada."""
    adjusted = [0.0] * len(p_values)
    previous = 0.0
    for rank, index in enumerate(sorted(range(len(p_values)), key=p_values.__getitem__)):
        previous = max(previous, min(1.0, (len(p_values) - rank) * p_values[index]))
        adjusted[index] = previous
    return adjusted


def validate_reports(reports):
    """Exige exactamente las mismas 500 consultas y solo validation."""
    reference = None
    for variant in VARIANTS:
        for model in MODELS:
            report = reports[variant][model]
            ids = set(report["per_query"])
            if report["split"] != "validation" or len(ids) != 500:
                raise ValueError("La selección requiere 500 consultas de validation.")
            if reference is not None and ids != reference:
                raise ValueError("Las consultas de las corridas no coinciden.")
            reference = ids
    return sorted(reference)


def select_configuration(reports):
    """Selecciona con reglas fijadas antes de ver los resultados."""
    ids = validate_reports(reports)
    global_scores = {
        variant: [
            fmean(reports[variant][model]["per_query"][qid]["AP@1000"] for model in MODELS)
            for qid in ids
        ] for variant in VARIANTS
    }
    primary = {}
    secondary = []
    for variant in VARIANTS[1:]:
        primary[variant] = paired_comparison(
            global_scores["baseline"], global_scores[variant],
            repetitions=PROTOCOL["repetitions"], seed=PROTOCOL["seed"],
        )
        for model in MODELS:
            for aggregate, per_query in METRICS.items():
                comparison = paired_comparison(
                    [reports["baseline"][model]["per_query"][qid][per_query] for qid in ids],
                    [reports[variant][model]["per_query"][qid][per_query] for qid in ids],
                    repetitions=PROTOCOL["repetitions"], seed=PROTOCOL["seed"],
                )
                secondary.append({"variant": variant, "model": model, "metric": aggregate, **comparison})

    adjusted = holm_adjust([primary[v]["p_permutation_two_sided"] for v in VARIANTS[1:]])
    for variant, p_value in zip(VARIANTS[1:], adjusted):
        comparison = primary[variant]
        comparison["p_holm"] = p_value
        losses = []
        for row in secondary:
            if row["variant"] == variant and row["baseline_mean"] > 0:
                if row["delta_relative_percent"] < -100 * PROTOCOL["guardrail_max_relative_loss"]:
                    losses.append({"model": row["model"], "metric": row["metric"],
                                   "relative_percent": row["delta_relative_percent"]})
        comparison["guardrail_violations"] = losses
        comparison["eligible"] = (
            comparison["delta_absolute"] > 0
            and p_value < PROTOCOL["alpha"] and not losses
        )
    adjusted = holm_adjust([row["p_permutation_two_sided"] for row in secondary])
    for row, p_value in zip(secondary, adjusted):
        row["p_holm"] = p_value

    eligible = [v for v in VARIANTS[1:] if primary[v]["eligible"]]
    winner = max(eligible, key=lambda v: fmean(global_scores[v])) if eligible else "baseline"
    return {
        "winner": winner,
        "global_map": {v: fmean(scores) for v, scores in global_scores.items()},
        "primary_comparisons": primary,
        "secondary_comparisons": secondary,
        "stemming_vs_lemmatization_exploratory": paired_comparison(
            global_scores["stemming"], global_scores["lemmatization"],
            repetitions=PROTOCOL["repetitions"], seed=PROTOCOL["seed"],
        ),
        "inference_limit": (
            "Exploratory: BM25 tuning and comparisons share validation; "
            "bootstrap/permutation intervals are conditional on selected parameters. "
            "Test is a final descriptive check, never a selection input."
        ),
    }
