
import unittest

from math import log2

from ri_fiqa.evaluation import (
    evaluate_query,
    aggregate_metrics,
)


class TestEvaluation(unittest.TestCase):

    def test_known_ranking(self):
        # Relevantes: A, B, C
        # Recuperados en posiciones 2, 4 y 5.
        ranked = ["X", "A", "Y", "B", "C"]
        relevant = {"A", "B", "C"}

        metrics = evaluate_query(ranked, relevant)

        expected_ap = (
            1 / 2 + 2 / 4 + 3 / 5
        ) / 3

        expected_dcg = (
            1 / log2(3)
            + 1 / log2(5)
            + 1 / log2(6)
        )

        expected_idcg = (
            1 + 1 / log2(3) + 1 / log2(4)
        )

        self.assertAlmostEqual(
            metrics["AP@1000"], expected_ap
        )
        self.assertAlmostEqual(metrics["P@5"], 0.6)
        self.assertAlmostEqual(metrics["P@10"], 0.3)
        self.assertAlmostEqual(
            metrics["Recall@10"], 1.0
        )
        self.assertAlmostEqual(
            metrics["Recall@100"], 1.0
        )
        self.assertAlmostEqual(
            metrics["RR@10"], 0.5
        )
        self.assertAlmostEqual(
            metrics["NDCG@10"],
            expected_dcg / expected_idcg
        )

    def test_perfect_ranking(self):
        metrics = evaluate_query(
            ["A", "B"], {"A", "B"}
        )

        self.assertEqual(metrics["AP@1000"], 1.0)
        self.assertEqual(metrics["P@5"], 0.4)
        self.assertEqual(metrics["Recall@10"], 1.0)
        self.assertEqual(metrics["RR@10"], 1.0)
        self.assertEqual(metrics["NDCG@10"], 1.0)

    def test_no_results(self):
        metrics = evaluate_query([], {"A", "B"})

        self.assertTrue(
            all(value == 0.0 for value in metrics.values())
        )

    def test_no_relevant_documents(self):
        metrics = evaluate_query(["A"], set())

        self.assertEqual(metrics["AP@1000"], 0.0)
        self.assertEqual(metrics["Recall@10"], 0.0)
        self.assertEqual(metrics["NDCG@10"], 0.0)

    def test_ap_cutoff(self):
        ranked = ["X", "A", "B", "C"]

        self.assertEqual(
            evaluate_query(
                ranked, {"C"}, depth=100
            )["AP@100"],
            0.25
        )

    def test_duplicate_results_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_query(
                ["A", "A"], {"A"}
            )

    def test_aggregation(self):
        per_query = {
            "q1": {
                "AP@1000": 1.0,
                "RR@10": 1.0
            },
            "q2": {
                "AP@1000": 0.5,
                "RR@10": 0.5
            },
        }

        result = aggregate_metrics(per_query)

        self.assertAlmostEqual(
            result["MAP@1000"], 0.75
        )
        self.assertAlmostEqual(
            result["MRR@10"], 0.75
        )


if __name__ == "__main__":
    unittest.main()
