
import unittest

from ri_fiqa.retrieval.fusion import weighted_rrf


class TestWeightedRRF(unittest.TestCase):

    def test_weighted_ranking(self):
        results = weighted_rrf(
            bm25_ids=["a", "b"],
            semantic_ids=["b", "c"],
            k=1,
            semantic_weight=0.75
        )

        self.assertEqual(
            [r.doc_id for r in results],
            ["b", "c", "a"]
        )

        self.assertAlmostEqual(
            results[0].score,
            0.25 / 3 + 0.75 / 2
        )

    def test_tie_break(self):
        results = weighted_rrf(
            ["d1", "d2"],
            ["d2", "d1"],
            semantic_weight=0.5
        )

        self.assertEqual(
            [r.doc_id for r in results],
            ["d2", "d1"]
        )

    def test_documents_from_both_models(self):
        results = weighted_rrf(
            ["a"], ["b"]
        )

        self.assertEqual(
            {r.doc_id for r in results},
            {"a", "b"}
        )

    def test_top_k(self):
        results = weighted_rrf(
            ["a", "b", "c"],
            ["b", "c", "d"],
            top_k=2
        )

        self.assertEqual(len(results), 2)

    def test_invalid_parameters(self):
        for k in (0, -1, True):
            with self.subTest(k=k):
                with self.assertRaises(ValueError):
                    weighted_rrf(["a"], ["b"], k=k)

        for weight in (-0.1, 0, 1, 1.1, float("nan")):
            with self.subTest(weight=weight):
                with self.assertRaises(ValueError):
                    weighted_rrf(
                        ["a"], ["b"],
                        semantic_weight=weight
                    )

    def test_duplicate_documents(self):
        with self.assertRaises(ValueError):
            weighted_rrf(
                ["a", "a"], ["b"]
            )

    def test_empty_rankings(self):
        self.assertEqual(
            weighted_rrf([], []), []
        )


if __name__ == "__main__":
    unittest.main()
