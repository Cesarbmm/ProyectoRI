
"""Configuración seleccionada mediante FiQA validation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalConfig:
    # Mejor BM25 según MAP@1000 en validation.
    bm25_k1: float = 1.2
    bm25_b: float = 0.5

    # BGE con la instrucción guardada en metadata.json.
    semantic_index: str = "semantic_bge"

    # Mejor RRF observado en validation.
    rrf_k: int = 10
    rrf_semantic_weight: float = 0.9

    # Profundidad de candidatos de los experimentos.
    candidate_depth: int = 1000


SELECTED_CONFIG = RetrievalConfig()
