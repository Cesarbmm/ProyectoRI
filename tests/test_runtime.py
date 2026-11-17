
import json
import tempfile
import unittest

from pathlib import Path

from ri_fiqa.embedding_models import MODEL_SPECS
from ri_fiqa.runtime import inspect_assets


class TestRuntime(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        corpus = self.root / "data/raw/corpus"
        processed = self.root / "data/processed"
        semantic = processed / "semantic_bge"

        corpus.mkdir(parents=True)
        semantic.mkdir(parents=True)

        (processed / "inverted_index_stopwords.json.gz"
         ).write_bytes(b"test")

        (semantic / "index.faiss").write_bytes(b"test")
        (semantic / "doc_ids.json").write_text(
            '["d1", "d2"]',
            encoding="utf-8",
        )

        spec = MODEL_SPECS["bge"]

        self.metadata = {
            "original_corpus_size": 3,
            "processed_documents": 3,
            "indexed_documents": 2,
            "excluded_empty_documents": 1,
            "model_id": spec.model_id,
            "query_prompt": spec.query_prompt,
            "document_prompt": spec.document_prompt,
            "dimension": 768,
            "normalization": "L2",
            "faiss_index": "IndexFlatIP",
        }

        self.metadata_path = (
            semantic / "metadata.json"
        )

        self.save_metadata()

    def tearDown(self):
        self.temp.cleanup()

    def save_metadata(self):
        self.metadata_path.write_text(
            json.dumps(self.metadata),
            encoding="utf-8",
        )

    def test_all_assets_ready(self):
        status = inspect_assets(self.root)

        self.assertEqual(status["status"], "ready")
        self.assertTrue(
            all(status["components"].values())
        )

    def test_missing_faiss_index(self):
        (
            self.root
            / "data/processed/semantic_bge/index.faiss"
        ).unlink()

        status = inspect_assets(self.root)

        self.assertEqual(
            status["status"], "not_ready"
        )
        self.assertFalse(
            status["components"]["faiss_index"]
        )

    def test_incomplete_metadata(self):
        self.metadata["processed_documents"] = 2
        self.save_metadata()

        status = inspect_assets(self.root)

        self.assertEqual(
            status["status"], "not_ready"
        )
        self.assertFalse(
            status["components"]["metadata_consistent"]
        )


if __name__ == "__main__":
    unittest.main()
