
import unittest
from math import log1p

from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.retrieval.bm25 import (
    BM25Config,
    BM25Retriever,
)


class TestBM25Retriever(unittest.TestCase):

    def setUp(self):
        self.index = InvertedIndex()

        self.index.build([
            {"_id": "d1", "text": "bank bank interest"},
            {"_id": "d2", "text": "bank loans"},
            {"_id": "d3", "text": "interest"},
            {"_id": "d4", "text": ""},
        ])

        self.retriever = BM25Retriever(self.index)

    def test_idf(self):
        n = 4
        df = 2

        expected = log1p(
            (n - df + 0.5) / (df + 0.5)
        )

        self.assertAlmostEqual(
            self.retriever.idf["bank"],
            expected
        )

    def test_manual_score(self):
        results = self.retriever.search("bank")

        scores = {
            result.doc_id: result.score
            for result in results
        }

        k1 = 1.2
        b = 0.75
        avgdl = 6 / 4
        tf = 2
        doc_length = 3

        idf = log1p((4 - 2 + 0.5) / (2 + 0.5))

        expected = idf * (
            tf * (k1 + 1)
        ) / (
            tf + k1 * (
                1 - b + b * doc_length / avgdl
            )
        )

        self.assertAlmostEqual(
            scores["d1"], expected
        )

        self.assertGreater(
            scores["d1"], scores["d2"]
        )

    def test_repeated_query_terms(self):
        simple = self.retriever.search("bank")
        repeated = self.retriever.search("bank bank")

        self.assertEqual(simple, repeated)

    def test_unknown_and_empty_queries(self):
        self.assertEqual(
            self.retriever.search("unicorn"), []
        )
        self.assertEqual(
            self.retriever.search("the and"), []
        )

    def test_empty_document_excluded(self):
        results = self.retriever.search("interest")

        self.assertNotIn(
            "d4",
            [result.doc_id for result in results]
        )

    def test_b_zero(self):
        index = InvertedIndex()

        index.build([
            {"_id": "a", "text": "bank"},
            {"_id": "b", "text": "bank loans savings"},
        ])

        retriever = BM25Retriever(
            index, BM25Config(b=0)
        )

        scores = {
            r.doc_id: r.score
            for r in retriever.search("bank")
        }

        # Sin normalización, TF idéntico produce
        # la misma puntuación aunque cambie la longitud.
        self.assertAlmostEqual(
            scores["a"], scores["b"]
        )

    def test_invalid_parameters(self):
        for config in [
            {"k1": 0},
            {"k1": -1},
            {"k1": float("inf")},
            {"b": -0.1},
            {"b": 1.1},
        ]:
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    BM25Config(**config)

        with self.assertRaises(ValueError):
            self.retriever.search("bank", top_k=0)


if __name__ == "__main__":
    unittest.main()
