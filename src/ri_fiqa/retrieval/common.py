
"""Estructuras comunes para modelos de recuperación."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Resultado individual de una búsqueda."""

    doc_id: str
    score: float
