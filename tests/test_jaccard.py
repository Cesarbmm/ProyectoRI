
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.retrieval.jaccard import JaccardRetriever


class TestJaccardRetriever(unittest.TestCase):

    def setUp(self):
        self.index = InvertedIndex()

        self.index.build([
            {"_id": "d1", "text": "bank bank"},
            {"_id": "d2", "text": "bank loans"},
            {"_id": "d3", "text": ""},
            {"_id": "d4", "text": "loans loans"},
            {"_id": "d5", "text": "bank"},
        ])

        self.retriever = JaccardRetriever(self.index)

    def test_jaccard_binary_scores(self):
        results = self.retriever.search(
            "bank loans", top_k=10
        )

        self.assertEqual(
            [r.doc_id for r in results],
            ["d2", "d5", "d4", "d1"]
        )

        self.assertAlmostEqual(results[0].score, 1.0)
        self.assertAlmostEqual(results[1].score, 0.5)

        # El documento vacío no participa.
        self.assertNotIn(
            "d3", [r.doc_id for r in results]
        )

    def test_repeated_query_terms(self):
        original = self.retriever.search("bank loans")
        repeated = self.retriever.search(
            "bank bank loans"
        )

        self.assertEqual(original, repeated)

    def test_ties_and_top_k(self):
        results = self.retriever.search(
            "bank", top_k=2
        )

        self.assertEqual(
            [r.doc_id for r in results],
            ["d5", "d1"]
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].score, 1.0)
        self.assertEqual(results[1].score, 1.0)

    def test_unknown_terms(self):
        results = self.retriever.search("unicorn")
        self.assertEqual(results, [])

    def test_stopwords_only(self):
        results = self.retriever.search("the and")
        self.assertEqual(results, [])

    def test_invalid_top_k(self):
        for value in (0, -1, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.retriever.search(
                        "bank", top_k=value
                    )

    def test_persistence(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "index.json.gz"

            self.index.save(path)
            restored = InvertedIndex.load(path)

            other = JaccardRetriever(restored)

            self.assertEqual(
                self.retriever.search("bank loans"),
                other.search("bank loans")
            )


if __name__ == "__main__":
    unittest.main()
