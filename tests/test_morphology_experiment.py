"""Regresiones de morfología, aislamiento de splits y selección pareada."""

import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ri_fiqa.config import RetrievalConfig
from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.preprocessing import PreprocessConfig, TextPreprocessor
from ri_fiqa.preprocessing_experiment import (
    METRICS, MODELS, VARIANTS, holm_adjust, select_configuration, validate_reports,
)
from ri_fiqa.search_service import SearchService


class TestMorphology(unittest.TestCase):
    def test_optional_transforms_are_independent(self):
        expected = {
            "baseline": ["banks", "investments", "running"],
            "stemming": ["bank", "invest", "run"],
            "lemmatization": ["bank", "investment", "running"],
        }
        for morphology, tokens in expected.items():
            with self.subTest(morphology=morphology):
                processor = TextPreprocessor(PreprocessConfig(morphology=morphology))
                self.assertEqual(processor.process("The banks investments running"), tokens)

    def test_financial_tokens_negations_and_protected_terms(self):
        text = "401(k) 10.5% us no not nor never without bill amount interest will may"
        baseline = TextPreprocessor().process(text)
        for morphology in VARIANTS:
            processor = TextPreprocessor(PreprocessConfig(morphology=morphology))
            self.assertEqual(processor.process(text), baseline)
            self.assertEqual(processor.process(None), [])

    def test_stopwords_removed_before_stemming(self):
        processor = TextPreprocessor(PreprocessConfig(morphology="stemming"))
        self.assertEqual(processor.process("the banks and loans"), ["bank", "loan"])
        processor = TextPreprocessor(PreprocessConfig(remove_stopwords=False, morphology="stemming"))
        self.assertEqual(processor.process("the banks"), ["the", "bank"])

    def test_unknown_configuration_rejected(self):
        with self.assertRaises(ValueError):
            PreprocessConfig(morphology="both")

    def test_wordnet_failure_is_actionable_without_download(self):
        with patch("nltk.corpus.wordnet.ensure_loaded", side_effect=LookupError("missing")):
            with self.assertRaisesRegex(RuntimeError, "nltk.downloader wordnet"):
                TextPreprocessor(PreprocessConfig(morphology="lemmatization"))

    def test_persistence_and_query_document_symmetry(self):
        for morphology in VARIANTS:
            with self.subTest(morphology=morphology), tempfile.TemporaryDirectory() as temp:
                index = InvertedIndex(TextPreprocessor(PreprocessConfig(morphology=morphology)))
                index.add_document("d", "banks investments")
                path = Path(temp) / "index.json.gz"
                index.save(path)
                restored = InvertedIndex.load(path)
                self.assertEqual(restored.preprocessor.config, index.preprocessor.config)
                self.assertEqual(restored.postings, index.postings)
                service = SearchService(
                    config=RetrievalConfig(morphology=morphology), inverted_index=restored,
                    document_texts={"d": "banks investments"},
                )
                for model in ("jaccard", "tfidf", "bm25"):
                    query = "bank" if morphology != "baseline" else "banks"
                    self.assertEqual(service.search(query, model=model)[0].doc_id, "d")

    def test_legacy_index_keeps_baseline(self):
        index = InvertedIndex()
        index.add_document("d", "banks")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "legacy.json.gz"
            index.save(path)
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                payload = json.load(stream)
            del payload["preprocess_config"]["morphology"]
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                json.dump(payload, stream)
            restored = InvertedIndex.load(path)
            self.assertEqual(restored.preprocessor.config.morphology, "baseline")
            self.assertIn("banks", restored.postings)

    def test_service_rejects_mismatched_index(self):
        service = SearchService(inverted_index=InvertedIndex(), config=RetrievalConfig(morphology="stemming"))
        with self.assertRaisesRegex(RuntimeError, "no coincide"):
            service._get_index()


def synthetic_reports():
    return {variant: {model: {
        "split": "validation",
        "per_query": {str(q): {metric: 0.2 for metric in METRICS.values()} for q in range(500)},
    } for model in MODELS} for variant in VARIANTS}


class TestExperimentSelection(unittest.TestCase):
    def test_holm_adjustment_preserves_order(self):
        actual = holm_adjust([0.04, 0.001, 0.03])
        for a, b in zip(actual, [0.06, 0.003, 0.06]):
            self.assertAlmostEqual(a, b)

    def test_rejects_test_or_unpaired_queries(self):
        reports = synthetic_reports()
        reports["stemming"]["bm25"]["split"] = "test"
        with self.assertRaises(ValueError):
            validate_reports(reports)
        reports["stemming"]["bm25"]["split"] = "validation"
        scores = reports["stemming"]["bm25"]["per_query"]
        scores["other"] = scores.pop("0")
        with self.assertRaises(ValueError):
            validate_reports(reports)

    def test_no_gain_retains_baseline(self):
        result = select_configuration(synthetic_reports())
        self.assertEqual(result["winner"], "baseline")
        self.assertEqual(result["primary_comparisons"]["stemming"]["p_holm"], 1.0)

    def test_gain_selects_one_variant_but_losses_block_promotion(self):
        reports = synthetic_reports()
        for model in MODELS:
            for metrics in reports["stemming"][model]["per_query"].values():
                for metric in metrics:
                    metrics[metric] += 0.1
        result = select_configuration(reports)
        self.assertEqual(result["winner"], "stemming")
        degraded = copy.deepcopy(reports)
        for metrics in degraded["stemming"]["hybrid"]["per_query"].values():
            metrics["NDCG@10"] = 0.19
        result = select_configuration(degraded)
        self.assertEqual(result["winner"], "baseline")
        self.assertEqual(len(result["primary_comparisons"]["stemming"]["guardrail_violations"]), 1)


if __name__ == "__main__":
    unittest.main()
