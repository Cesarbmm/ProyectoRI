
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.preprocessing import (
    TextPreprocessor,
    PreprocessConfig,
)


class TestInvertedIndex(unittest.TestCase):

    def setUp(self):
        self.index = InvertedIndex()

        self.index.build([
            {"_id": "d1", "text": "The bank and bank"},
            {"_id": "d2", "text": "Bank loans"},
            {"_id": "d3", "text": ""},
        ])

    def test_counts_and_empty_documents(self):
        self.assertEqual(self.index.num_documents, 3)
        self.assertEqual(self.index.doc_lengths["d3"], 0)
        self.assertEqual(self.index.total_tokens, 4)
        self.assertEqual(self.index.vocabulary_size, 2)

        self.assertAlmostEqual(
            self.index.average_document_length,
            4 / 3
        )

        self.assertEqual(
            self.index.doc_unique_terms,{"d1": 1, "d2": 2, "d3": 0}
        )

    def test_postings_frequencies_and_df(self):
        self.assertEqual(
            dict(self.index.get_postings("bank")),
            {"d1": 2, "d2": 1}
        )

        self.assertEqual(
            self.index.document_frequency("bank"), 2
        )

        self.assertEqual(
            self.index.term_frequency("bank", "d1"), 2
        )

        self.assertEqual(
            self.index.document_frequency("unknown"), 0
        )

        self.assertEqual(
            dict(self.index.get_postings("unknown")), {}
        )

    def test_duplicate_id(self):
        with self.assertRaises(ValueError):
            self.index.add_document(
                "d1", "Another text"
            )

    def test_save_and_load(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "indice.json.gz"

            self.index.save(path)
            restored = InvertedIndex.load(path)

            self.assertEqual(
                restored.postings,
                self.index.postings
            )
            self.assertEqual(
                restored.doc_lengths,
                self.index.doc_lengths
            )
            self.assertEqual(
                restored.total_tokens,
                self.index.total_tokens
            )
            self.assertEqual(
                restored.total_postings,
                self.index.total_postings
            )
            self.assertEqual(
                restored.doc_unique_terms,
                self.index.doc_unique_terms
            )

    def test_preprocessing_config_persisted(self):
        index = InvertedIndex(
            TextPreprocessor(
                PreprocessConfig(
                    remove_stopwords=False
                )
            )
        )

        index.add_document("a", "the bank")

        with TemporaryDirectory() as temp:
            path = Path(temp) / "indice.json.gz"
            index.save(path)

            restored = InvertedIndex.load(path)

            self.assertFalse(
                restored.preprocessor.config.remove_stopwords
            )
            self.assertEqual(
                restored.doc_lengths["a"], 2
            )


if __name__ == "__main__":
    unittest.main()
