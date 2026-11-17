
import unittest

from ri_fiqa.statistics import paired_comparison


class TestPairedComparison(unittest.TestCase):

    def test_identical_models(self):
        scores = [0.1, 0.2, 0.3, 0.4]

        result = paired_comparison(
            scores, scores, repetitions=1000
        )

        self.assertAlmostEqual(
            result["delta_absolute"], 0.0
        )
        self.assertAlmostEqual(
            result["p_permutation_two_sided"], 1.0
        )
        self.assertEqual(
            result["unchanged_queries"], 4
        )

    def test_consistent_improvement(self):
        baseline = [0.2] * 20
        candidate = [0.5] * 20

        result = paired_comparison(
            baseline, candidate, repetitions=1000
        )

        self.assertAlmostEqual(
            result["delta_absolute"], 0.3
        )
        self.assertLess(
            result["p_permutation_two_sided"], 0.05
        )
        self.assertEqual(
            result["improved_queries"], 20
        )

    def test_mismatched_samples(self):
        with self.assertRaises(ValueError):
            paired_comparison(
                [0.1, 0.2], [0.3]
            )


if __name__ == "__main__":
    unittest.main()
