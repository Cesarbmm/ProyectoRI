
"""Recuperación semántica mediante embeddings y FAISS."""

import faiss
import numpy as np

from ri_fiqa.retrieval.common import SearchResult


class SemanticRetriever:
    """Recuperador basado en similitud de coseno."""

    def __init__(self, encoder, vector_index, doc_ids):
        self.encoder = encoder
        self.index = vector_index
        self.doc_ids = list(doc_ids)

        if self.index.ntotal != len(self.doc_ids):
            raise ValueError(
                "El número de vectores no coincide "
                "con la cantidad de IDs documentales."
            )

        if len(self.doc_ids) != len(set(self.doc_ids)):
            raise ValueError(
                "Existen IDs documentales duplicados."
            )

    def search_many(
        self,
        queries: list[str],
        top_k: int = 10,
        batch_size: int = 32,
    ) -> list[list[SearchResult]]:
        """Busca varias consultas en una operación."""

        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or top_k <= 0
        ):
            raise ValueError(
                "top_k debe ser un entero positivo."
            )

        if batch_size <= 0:
            raise ValueError(
                "batch_size debe ser positivo."
            )

        if not queries:
            return []

        if not all(isinstance(q, str) for q in queries):
            raise TypeError(
                "Todas las consultas deben ser cadenas."
            )

        # Mantener las posiciones originales.
        resultados = [[] for _ in queries]

        posiciones_validas = [
            i for i, query in enumerate(queries)
            if query.strip()
        ]

        if not posiciones_validas or self.index.ntotal == 0:
            return resultados

        textos = [
            queries[i] for i in posiciones_validas
        ]

        embeddings = self.encoder.encode_query(
            textos,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        vectors = np.ascontiguousarray(
            embeddings, dtype=np.float32
        )

        if (
            vectors.ndim != 2
            or vectors.shape[1] != self.index.d
        ):
            raise ValueError(
                "Dimensiones incompatibles entre "
                "el encoder y el índice FAISS."
            )

        # Coseno = producto interno de vectores unitarios.
        faiss.normalize_L2(vectors)

        k = min(top_k, self.index.ntotal)

        scores, positions = self.index.search(vectors, k)

        for original_position, row_scores, row_ids in zip(
            posiciones_validas, scores, positions
        ):
            encontrados = []

            for score, vector_position in zip(
                row_scores, row_ids
            ):
                if vector_position < 0:
                    continue

                encontrados.append(
                    SearchResult(
                        doc_id=self.doc_ids[
                            int(vector_position)
                        ],
                        score=float(score),
                    )
                )

            encontrados.sort(
                key=lambda result: (
                    result.score,
                    result.doc_id
                ),
                reverse=True,
            )

            resultados[original_position] = encontrados

        return resultados

    def search(
        self,
        query: str,
        top_k: int = 10
    ) -> list[SearchResult]:
        """Busca una única consulta."""
        return self.search_many([query], top_k)[0]
