
import unittest

import faiss
import numpy as np

from ri_fiqa.retrieval.semantic import SemanticRetriever


class FakeEncoder:
    """Encoder artificial para probar la búsqueda."""

    def encode_query(self, texts, **kwargs):
        vectors = {
            "retirement": [1.0, 0.0],
            "tax": [0.0, 1.0],
        }

        return np.array(
            [vectors[t] for t in texts],
            dtype=np.float32
        )


class TestSemanticRetriever(unittest.TestCase):

    def setUp(self):
        vectors = np.array([
            [1.0, 0.0],
            [0.0, 1.0],
            [0.6, 0.8],
        ], dtype=np.float32)

        faiss.normalize_L2(vectors)

        self.index = faiss.IndexFlatIP(2)
        self.index.add(vectors)

        self.retriever = SemanticRetriever(
            FakeEncoder(),
            self.index,
            ["d1", "d2", "d3"]
        )

    def test_exact_ranking(self):
        results = self.retriever.search(
            "retirement", top_k=3
        )

        self.assertEqual(
            [r.doc_id for r in results],
            ["d1", "d3", "d2"]
        )

        self.assertAlmostEqual(
            results[0].score, 1.0, places=5
        )

    def test_multiple_queries(self):
        results = self.retriever.search_many(
            ["retirement", "tax"], top_k=1
        )

        self.assertEqual(
            results[0][0].doc_id, "d1"
        )
        self.assertEqual(
            results[1][0].doc_id, "d2"
        )

    def test_empty_query(self):
        results = self.retriever.search_many(
            ["", "retirement", " "], top_k=1
        )

        self.assertEqual(results[0], [])
        self.assertEqual(
            results[1][0].doc_id, "d1"
        )
        self.assertEqual(results[2], [])

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            self.retriever.search(
                "retirement", top_k=0
            )

        with self.assertRaises(ValueError):
            self.retriever.search_many(
                ["retirement"], batch_size=0
            )

    def test_index_id_mismatch(self):
        with self.assertRaises(ValueError):
            SemanticRetriever(
                FakeEncoder(),
                self.index,
                ["d1"]
            )


if __name__ == "__main__":
    unittest.main()
