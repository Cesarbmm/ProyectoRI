
"""Comparación estadística pareada de modelos de RI."""

import numpy as np


def paired_comparison(
    baseline_scores,
    candidate_scores,
    repetitions=10000,
    seed=20261115,
):
    """Bootstrap e hipótesis de permutación pareada."""

    baseline = np.asarray(
        baseline_scores, dtype=np.float64
    )
    candidate = np.asarray(
        candidate_scores, dtype=np.float64
    )

    if (
        baseline.ndim != 1
        or baseline.shape != candidate.shape
        or baseline.size == 0
    ):
        raise ValueError("Los datos pareados son inválidos.")

    if not (
        np.isfinite(baseline).all()
        and np.isfinite(candidate).all()
    ):
        raise ValueError("Las métricas deben ser finitas.")

    if repetitions < 100:
        raise ValueError("Usa al menos 100 repeticiones.")

    differences = candidate - baseline
    observed = float(differences.mean())
    n = len(differences)

    rng = np.random.default_rng(seed)

    # Bootstrap: remuestrear consultas completas.
    bootstrap = np.empty(repetitions)

    for start in range(0, repetitions, 256):
        size = min(256, repetitions - start)

        indices = rng.integers(
            0, n, size=(size, n)
        )

        bootstrap[start:start + size] = (
            differences[indices].mean(axis=1)
        )

    ci_low, ci_high = np.quantile(
        bootstrap, [0.025, 0.975]
    )

    # Prueba de permutación bilateral:
    # intercambiar aleatoriamente el signo de
    # cada diferencia entre sistemas pareados.
    extreme = 0

    for start in range(0, repetitions, 256):
        size = min(256, repetitions - start)

        signs = (
            rng.integers(
                0, 2,
                size=(size, n),
                dtype=np.int8
            ) * 2 - 1
        )

        simulated = (
            signs * differences
        ).mean(axis=1)

        extreme += np.count_nonzero(
            np.abs(simulated) >= abs(observed) - 1e-12
        )

    p_value = (extreme + 1) / (repetitions + 1)

    baseline_mean = float(baseline.mean())
    candidate_mean = float(candidate.mean())

    return {
        "queries": n,
        "baseline_mean": baseline_mean,
        "candidate_mean": candidate_mean,
        "delta_absolute": observed,
        "delta_relative_percent": (
            100 * observed / baseline_mean
            if baseline_mean != 0 else None
        ),
        "ci95_low": float(ci_low),
        "ci95_high": float(ci_high),
        "p_permutation_two_sided": float(p_value),
        "improved_queries": int(
            np.count_nonzero(differences > 1e-12)
        ),
        "worsened_queries": int(
            np.count_nonzero(differences < -1e-12)
        ),
        "unchanged_queries": int(
            np.count_nonzero(
                np.abs(differences) <= 1e-12
            )
        ),
        "repetitions": repetitions,
        "seed": seed,
    }
