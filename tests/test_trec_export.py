
import unittest
from io import StringIO

from ri_fiqa.evaluation import write_trec_ranking
from ri_fiqa.retrieval.common import SearchResult


class TestTrecExport(unittest.TestCase):

    def test_tied_scores_keep_ranking_order(self):
        results = [
            SearchResult("d2", 0.5),
            SearchResult("d1", 0.5),
            SearchResult("d3", 0.2),
        ]

        output = StringIO()

        write_trec_ranking(
            output, "q1", results, "test"
        )

        lines = [
            line.split()
            for line in output.getvalue().splitlines()
        ]

        self.assertEqual(
            [line[2] for line in lines],
            ["d2", "d1", "d3"]
        )

        self.assertEqual(
            [float(line[4]) for line in lines],
            [3.0, 2.0, 1.0]
        )

        # Los scores originales no se alteran.
        self.assertEqual(results[0].score, 0.5)
        self.assertEqual(results[1].score, 0.5)


if __name__ == "__main__":
    unittest.main()
