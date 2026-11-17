
import unittest

from sklearn.feature_extraction.text import TfidfVectorizer

from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.retrieval.tfidf import TfidfRetriever


class TestTfidfRetriever(unittest.TestCase):

    def setUp(self):
        self.documents = [
            {"_id": "d1", "text": "bank bank interest"},
            {"_id": "d2", "text": "bank loans"},
            {"_id": "d3", "text": "interest"},
            {"_id": "d4", "text": ""},
        ]

        self.index = InvertedIndex()
        self.index.build(self.documents)

        self.retriever = TfidfRetriever(self.index)

    def test_scores_match_sklearn(self):
        """Nuestros scores deben coincidir con scikit-learn."""

        vectorizer = TfidfVectorizer(
            analyzer=self.index.preprocessor.process,
            norm="l2",
            use_idf=True,
            smooth_idf=True,
            sublinear_tf=False
        )

        texts = [
            doc["text"] for doc in self.documents
        ]

        doc_matrix = vectorizer.fit_transform(texts)

        query = "bank interest"
        query_vector = vectorizer.transform([query])

        reference = (
            doc_matrix @ query_vector.T
        ).toarray().ravel()

        expected = {
            doc["_id"]: float(score)
            for doc, score in zip(self.documents, reference)
            if score > 0
        }

        results = self.retriever.search(
            query, top_k=10
        )

        actual = {
            result.doc_id: result.score
            for result in results
        }

        self.assertEqual(
            set(actual),
            set(expected)
        )

        for doc_id in expected:
            self.assertAlmostEqual(
                actual[doc_id],
                expected[doc_id],
                places=10
            )

    def test_ranking(self):
        results = self.retriever.search(
            "bank interest"
        )

        self.assertEqual(results[0].doc_id, "d1")

        self.assertGreater(
            results[0].score,
            results[1].score
        )

    def test_no_results(self):
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

    def test_invalid_top_k(self):
        for value in (0, -1, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.retriever.search(
                        "bank", top_k=value
                    )


if __name__ == "__main__":
    unittest.main()
