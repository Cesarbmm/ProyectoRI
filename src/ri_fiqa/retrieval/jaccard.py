
"""Recuperación mediante similitud de Jaccard binaria."""

from collections import Counter

from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.retrieval.common import SearchResult


class JaccardRetriever:
    """Recupera documentos utilizando conjuntos de términos."""

    def __init__(self, index: InvertedIndex):
        self.index = index

    def search(
        self,
        query: str,
        top_k: int = 10
    ) -> list[SearchResult]:
        """Devuelve los documentos con mayor Jaccard."""

        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or top_k <= 0
        ):
            raise ValueError(
                "top_k debe ser un entero positivo."
            )

        # Jaccard binario: no considera repeticiones.
        query_terms = set(
            self.index.preprocessor.process(query)
        )

        if not query_terms:
            return []

        query_size = len(query_terms)

        # documento -> términos que comparte con la consulta
        intersections = Counter()

        # Solo revisamos documentos que contienen
        # algún término de la consulta.
        for term in query_terms:
            postings = self.index.get_postings(term)

            for doc_id in postings:
                intersections[doc_id] += 1

        results = []

        for doc_id, intersection_size in intersections.items():

            doc_size = self.index.doc_unique_terms[doc_id]

            # |Q unión D| = |Q| + |D| - |Q intersección D|
            union_size = (
                query_size
                + doc_size
                - intersection_size
            )

            score = intersection_size / union_size

            results.append(
                SearchResult(
                    doc_id=doc_id,
                    score=score
                )
            )

        # Mayor similitud primero, y en caso de empate id documental descendente. compatible con el criterio de trec_eval.
        results.sort(
            key=lambda result: (
                result.score,
                result.doc_id
            ),
            reverse=True
        )

        return results[:top_k]
