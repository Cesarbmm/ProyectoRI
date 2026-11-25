
"""Configuración seleccionada mediante FiQA validation."""

from dataclasses import dataclass

from ri_fiqa.preprocessing import PreprocessConfig


@dataclass(frozen=True)
class RetrievalConfig:
    morphology: str = "baseline"

    # Parámetros del baseline histórico; la selección final se fija abajo.
    bm25_k1: float = 1.2
    bm25_b: float = 0.5

    # BGE con la instrucción guardada en metadata.json.
    semantic_index: str = "semantic_bge"

    # Mejor RRF observado en validation.
    rrf_k: int = 10
    rrf_semantic_weight: float = 0.9

    # Profundidad de candidatos de los experimentos.
    candidate_depth: int = 1000

    def __post_init__(self):
        PreprocessConfig(morphology=self.morphology)

    @property
    def lexical_index(self) -> str:
        if self.morphology == "baseline":
            return "inverted_index_stopwords.json.gz"
        return f"inverted_index_{self.morphology}.json.gz"


# results/preprocessing_v1/selection_frozen.json; solo validation, sin reajustes test.
SELECTED_CONFIG = RetrievalConfig(morphology="stemming", bm25_k1=0.8, bm25_b=0.75)

# Posible mejora (NO ACTIVA): explorar otros k1/b SOLO en validation.
# Modificar SELECTED_CONFIG alteraría los rankings congelados; no hacerlo en la entrega.
