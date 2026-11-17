
import unittest

from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.retrieval.common import SearchResult
from ri_fiqa.search_service import SearchService


class FakeSemanticRetriever:
    """Simula resultados semánticos sin cargar BGE."""

    def __init__(self):
        self.calls = []

    def search(self, query, top_k=10):
        self.calls.append((query, top_k))

        return [
            SearchResult("d2", 0.9),
            SearchResult("d1", 0.8),
        ][:top_k]

    def search_many(
        self,
        queries,
        top_k=10,
        batch_size=32,
    ):
        return [
            self.search(query, top_k=top_k)
            for query in queries
        ]


class TestSearchService(unittest.TestCase):

    def setUp(self):
        texts = {
            "d1": "bank interest",
            "d2": "retirement savings",
            "d3": "bank loans",
        }

        index = InvertedIndex()

        index.build([
            {"_id": doc_id, "text": text}
            for doc_id, text in texts.items()
        ])

        self.semantic = FakeSemanticRetriever()

        self.service = SearchService(
            inverted_index=index,
            semantic_retriever=self.semantic,
            document_texts=texts,
        )

    def test_lexical_models(self):
        for model in ("jaccard", "tfidf", "bm25"):
            with self.subTest(model=model):
                hits = self.service.search(
                    "bank interest",
                    model=model,
                    top_k=2,
                )

                self.assertEqual(len(hits), 2)
                self.assertEqual(hits[0].rank, 1)
                self.assertEqual(hits[0].doc_id, "d1")

    def test_semantic_search(self):
        hits = self.service.search(
            "retirement",
            model="bge",
            top_k=2,
        )

        self.assertEqual(hits[0].doc_id, "d2")
        self.assertEqual(
            hits[0].text,
            "retirement savings"
        )

    def test_hybrid_search(self):
        hits = self.service.search(
            "bank interest",
            model="hybrid",
            top_k=2,
        )

        self.assertEqual(len(hits), 2)

        # La fusión siempre solicita 1000 candidatos.
        self.assertEqual(
            self.semantic.calls[-1],
            ("bank interest", 1000)
        )

    def test_selected_bm25_configuration(self):
        bm25 = self.service._get_lexical("bm25")

        self.assertEqual(bm25.config.k1, 1.2)
        self.assertEqual(bm25.config.b, 0.5)

    def test_model_caching(self):
        first = self.service._get_lexical("tfidf")
        second = self.service._get_lexical("tfidf")

        self.assertIs(first, second)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            self.service.search(
                "", model="bge"
            )

        with self.assertRaises(ValueError):
            self.service.search(
                "bank", model="unknown"
            )

        with self.assertRaises(ValueError):
            self.service.search(
                "bank", top_k=0
            )

    def test_batch_semantic_search(self):
        rankings = self.service.rank_many(
            ["retirement", "savings"],
            model="bge",
            top_k=2,
        )
    
        self.assertEqual(len(rankings), 2)
        self.assertEqual(rankings[0][0].doc_id, "d2")
        self.assertEqual(rankings[1][0].doc_id, "d2")
    
    
    def test_batch_hybrid_search(self):
        rankings = self.service.rank_many(
            ["bank", "retirement"],
            model="hybrid",
            top_k=2,
        )
    
        self.assertEqual(len(rankings), 2)
        self.assertTrue(all(len(r) <= 2 for r in rankings))
        self.assertEqual(self.semantic.calls[-1][1], 1000)


if __name__ == "__main__":
    unittest.main()
