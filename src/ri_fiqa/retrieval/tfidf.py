
"""Modelo TF-IDF propio con similitud de coseno."""

from collections import Counter, defaultdict
from math import log, sqrt

from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.retrieval.common import SearchResult


class TfidfRetriever:
    """Calcula TF-IDF a partir del índice invertido."""

    def __init__(self, index: InvertedIndex):
        self.index = index

        if index.num_documents == 0:
            raise ValueError("El índice está vacío.")

        self.idf: dict[str, float] = {}
        self.doc_norms: dict[str, float] = {}

        self._prepare()

    def _prepare(self) -> None:
        """Calcula IDF y normas L2 documentales."""

        n = self.index.num_documents
        squared_norms = defaultdict(float)

        for term, postings in self.index.postings.items():
            df = len(postings)

            # IDF suavizado, compatible con scikit-learn.
            idf = log((n + 1) / (df + 1)) + 1.0
            self.idf[term] = idf

            for doc_id, tf in postings.items():
                weight = tf * idf
                squared_norms[doc_id] += weight ** 2

        self.doc_norms = {
            doc_id: sqrt(value)
            for doc_id, value in squared_norms.items()
        }

    def search(
        self,
        query: str,
        top_k: int = 10
    ) -> list[SearchResult]:
        """Recupera documentos usando coseno TF-IDF."""

        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or top_k <= 0
        ):
            raise ValueError(
                "top_k debe ser un entero positivo."
            )

        tokens = self.index.preprocessor.process(query)
        query_tf = Counter(tokens)

        # Ignorar términos que no están en el vocabulario.
        query_weights = {
            term: tf * self.idf[term]
            for term, tf in query_tf.items()
            if term in self.idf
        }

        if not query_weights:
            return []

        # Norma L2 del vector de consulta.
        query_norm = sqrt(
            sum(w ** 2 for w in query_weights.values())
        )

        # Producto punto, calculado solo sobre candidatos
        # que comparten algún término con la consulta.
        dot_products = defaultdict(float)

        for term, query_weight in query_weights.items():
            idf = self.idf[term]

            for doc_id, doc_tf in (
                self.index.get_postings(term).items()
            ):
                doc_weight = doc_tf * idf

                dot_products[doc_id] += (
                    query_weight * doc_weight
                )

        results = []

        for doc_id, dot_product in dot_products.items():
            doc_norm = self.doc_norms[doc_id]

            if dot_product <= 0 or doc_norm == 0:
                continue

            similarity = (
                dot_product / (query_norm * doc_norm)
            )

            results.append(
                SearchResult(
                    doc_id=doc_id,
                    score=similarity
                )
            )

        # Mismo criterio de desempate para los modelos.
        results.sort(
            key=lambda result: (
                result.score,
                result.doc_id
            ),
            reverse=True
        )

        return results[:top_k]
