
"""Modelo probabilístico BM25 implementado sobre el índice invertido."""

from collections import defaultdict
from dataclasses import dataclass
from math import isfinite, log1p

from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.retrieval.common import SearchResult


@dataclass(frozen=True)
class BM25Config:
    """Hiperparámetros del modelo BM25."""

    k1: float = 1.2
    b: float = 0.75

    def __post_init__(self):
        if (
            isinstance(self.k1, bool)
            or not isinstance(self.k1, (int, float))
            or not isfinite(self.k1)
            or self.k1 <= 0
        ):
            raise ValueError("k1 debe ser positivo y finito.")

        if (
            isinstance(self.b, bool)
            or not isinstance(self.b, (int, float))
            or not isfinite(self.b)
            or not 0 <= self.b <= 1
        ):
            raise ValueError("b debe estar entre 0 y 1.")


class BM25Retriever:
    """Implementa BM25 con índice invertido y postings TF."""

    def __init__(
        self,
        index: InvertedIndex,
        config: BM25Config | None = None
    ):
        self.index = index
        self.config = config or BM25Config()

        self.n = index.num_documents
        self.avgdl = index.average_document_length

        if self.n == 0 or self.avgdl <= 0:
            raise ValueError(
                "El índice debe contener documentos con texto."
            )

        # IDF Robertson con transformación positiva.
        self.idf = {}

        for term, postings in index.postings.items():
            df = len(postings)

            self.idf[term] = log1p(
                (self.n - df + 0.5) / (df + 0.5)
            )

    def search(
        self,
        query: str,
        top_k: int = 10
    ) -> list[SearchResult]:
        """Recupera documentos según su puntuación BM25."""

        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or top_k <= 0
        ):
            raise ValueError(
                "top_k debe ser un entero positivo."
            )

        tokens = self.index.preprocessor.process(query)

        if not tokens:
            return []

        k1 = self.config.k1
        b = self.config.b

        scores = defaultdict(float)

        # Variante: cada término distinto de la consulta
        # aporta una vez al score.
        for term in sorted(set(tokens)):

            idf = self.idf.get(term)

            if idf is None:
                continue

            postings = self.index.get_postings(term)

            for doc_id, tf in postings.items():
                doc_length = self.index.doc_lengths[doc_id]

                length_norm = (
                    1 - b
                    + b * doc_length / self.avgdl
                )

                numerator = tf * (k1 + 1)
                denominator = tf + k1 * length_norm

                term_score = (
                    idf * numerator / denominator
                )

                scores[doc_id] += term_score

        results = [
            SearchResult(doc_id=doc_id, score=score)
            for doc_id, score in scores.items()
            if score > 0
        ]

        results.sort(
            key=lambda result: (
                result.score,
                result.doc_id
            ),
            reverse=True
        )

        return results[:top_k]
