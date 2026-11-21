"""La comprobación final exige una selección íntegra antes de leer test."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ri_fiqa.config import SELECTED_CONFIG


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
try:
    spec = importlib.util.spec_from_file_location("experiment_cli", SCRIPTS / "experimentar_preprocesamiento.py")
    experiment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(experiment)
    cache_spec = importlib.util.spec_from_file_location("cache_cli", SCRIPTS / "regenerar_cache_bge.py")
    cache = importlib.util.module_from_spec(cache_spec)
    cache_spec.loader.exec_module(cache)
finally:
    sys.path.remove(str(SCRIPTS))


class TestSplitIsolation(unittest.TestCase):
    def test_service_defaults_match_frozen_validation_selection(self):
        freeze = json.loads((SCRIPTS.parent / "results/preprocessing_v1/selection_frozen.json").read_text(encoding="utf-8"))
        self.assertEqual(freeze["selection_split"], "validation")
        self.assertFalse(freeze["test_used_for_selection"])
        self.assertEqual(SELECTED_CONFIG.morphology, freeze["winner"])
        self.assertEqual(SELECTED_CONFIG.bm25_k1, freeze["bm25"]["k1"])
        self.assertEqual(SELECTED_CONFIG.bm25_b, freeze["bm25"]["b"])

    def test_validation_does_not_open_test_qrels(self):
        calls = []

        class Rows(list):
            _fingerprint = "fixture"

        def fake_load(path):
            calls.append(Path(path).as_posix())
            if Path(path).name == "queries":
                return Rows({"_id": str(q), "text": "banks"} for q in range(500))
            return Rows({"query-id": str(q), "corpus-id": "d", "score": 1} for q in range(500))

        with patch.object(experiment, "load_from_disk", side_effect=fake_load):
            ids, _, _, _ = experiment.split_data("validation")
        self.assertEqual(len(ids), 500)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0].endswith("qrels/validation"))
        self.assertFalse(any("test" in path for path in calls))

    def test_final_requires_freeze_before_opening_test(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(experiment, "split_data") as split:
                with self.assertRaises(FileNotFoundError):
                    experiment.final_check(Path(temp))
                split.assert_not_called()

    def test_final_rejects_altered_validation_before_opening_test(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "protocol.json").write_text("changed", encoding="utf-8")
            (root / "selection_frozen.json").write_text(json.dumps({
                "selection_split": "validation", "test_used_for_selection": False,
                "validation_artifacts_sha256": {"protocol.json": "original-hash"},
            }), encoding="utf-8")
            with patch.object(experiment, "split_data") as split:
                with self.assertRaisesRegex(ValueError, "modificado"):
                    experiment.final_check(root)
                split.assert_not_called()

    def test_completed_final_cannot_be_rerun(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "final_test").mkdir()
            (root / "selection_frozen.json").write_text(json.dumps({
                "selection_split": "validation", "test_used_for_selection": False,
            }), encoding="utf-8")
            with patch.object(experiment, "split_data") as split:
                with self.assertRaises(FileExistsError):
                    experiment.final_check(root)
                split.assert_not_called()


class TestCacheRegeneration(unittest.TestCase):
    def test_existing_historical_ranking_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "results").mkdir()
            ranking = root / "results/service_bge_validation_top1000.trec"
            ranking.write_bytes(b"historical")
            with patch.object(cache, "ROOT", root), patch.object(cache, "split_data") as split:
                with self.assertRaises(FileExistsError):
                    cache.regenerate("validation")
                split.assert_not_called()
            self.assertEqual(ranking.read_bytes(), b"historical")

    def test_test_cache_requires_freeze_before_reading_qrels(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(cache, "ROOT", Path(temp)), patch.object(cache, "semantic_hashes", return_value={}):
                with patch.object(cache, "split_data") as split:
                    with self.assertRaisesRegex(ValueError, "selección congelada"):
                        cache.regenerate("test")
                    split.assert_not_called()


if __name__ == "__main__":
    unittest.main()
