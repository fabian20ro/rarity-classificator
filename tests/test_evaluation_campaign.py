import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from classificator.models import BaseWordRow
from classificator.scoring.d1 import D1Scorer
from classificator.evaluation.campaign import run_campaign
from tests.test_d1_scorer import response, models, answer


class CampaignTests(unittest.TestCase):
    def test_csv_campaign_resumes_completed_ids_without_another_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            http = Mock()
            http.get.return_value = response(models())
            http.post.return_value = response(answer())
            scorer = D1Scorer(model="d1-3b", http=http)
            items = [BaseWordRow(1, "casă", "noun"), BaseWordRow(2, "ac", "noun")]
            config = {"model": "d1-3b", "artifact_sha256": "a" * 64}
            result = run_campaign(items, scorer, path, config=config)
            with result.open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual([r["word_id"] for r in rows], ["1", "2"])
            self.assertEqual(rows[0]["p_L4"], "0.7")
            run_campaign(items, scorer, path, config=config)
            self.assertEqual(http.post.call_count, 2)
            self.assertTrue((path / "manifest.json").exists())
            self.assertTrue((path / "run.csv").exists())

    def test_refuses_invalid_inventory_before_any_request_or_output(self):
        for items in [
            [BaseWordRow(1, "ac", ""), BaseWordRow(1, "ac", "")],
            [BaseWordRow(0, "ac", "")],
            [],
            [BaseWordRow(1, "", "")],
        ]:
            with self.subTest(items=items), tempfile.TemporaryDirectory() as tmp:
                http = Mock()
                path = Path(tmp) / "run"
                with self.assertRaises(ValueError):
                    run_campaign(items, D1Scorer(model="d1-3b", http=http), path, config={})
                self.assertFalse(path.exists())
                http.post.assert_not_called()

    def test_interrupted_campaign_recovers_and_refuses_changed_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            items = [BaseWordRow(1, "ac", ""), BaseWordRow(2, "casă", "")]
            http = Mock()
            http.get.return_value = response(models())
            http.post.side_effect = [response(answer()), KeyboardInterrupt()]
            scorer = D1Scorer(model="d1-3b", http=http)
            with self.assertRaises(KeyboardInterrupt):
                run_campaign(items, scorer, path, config={"model": "d1"})
            http.post.side_effect = None
            http.post.return_value = response(answer())
            run_campaign(items, scorer, path, config={"model": "d1"})
            self.assertEqual(http.post.call_count, 3)
            before = (path / "predictions.csv").read_bytes()
            with self.assertRaisesRegex(ValueError, "changed"):
                run_campaign(items, scorer, path, config={"model": "different"})
            self.assertEqual((path / "predictions.csv").read_bytes(), before)

    def test_corrupt_checkpoint_fails_before_resuming(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            items = [BaseWordRow(1, "ac", "")]
            http = Mock()
            http.get.return_value = response(models())
            http.post.return_value = response(answer())
            scorer = D1Scorer(model="d1-3b", http=http)
            run_campaign(items, scorer, path, config={})
            checkpoint = path / "records/1.json"
            record = json.loads(checkpoint.read_text())
            record["word_id"] = 999
            checkpoint.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "checkpoint"):
                run_campaign(items, scorer, path, config={})

    def test_failure_is_visible_and_only_explicit_retry_reissues_it(self):
        import requests

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            http = Mock()
            http.get.return_value = response(models())
            http.post.side_effect = requests.Timeout("offline")
            scorer = D1Scorer(model="d1-3b", http=http)
            items = [BaseWordRow(1, "ac", "")]
            run_campaign(items, scorer, path, config={})
            self.assertIn("failed", (path / "failures.csv").read_text())
            http.post.side_effect = None
            http.post.return_value = response(answer())
            run_campaign(items, scorer, path, config={})
            self.assertEqual(http.post.call_count, 1)
            run_campaign(items, scorer, path, config={}, retry_failed=True)
            self.assertEqual(http.post.call_count, 2)
            self.assertNotIn("offline", (path / "predictions.csv").read_text())

    def test_orphan_records_are_not_adopted_as_a_new_campaign(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            (path / "records").mkdir(parents=True)
            (path / "records/1.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "manifest"):
                run_campaign(
                    [BaseWordRow(1, "ac", "")], D1Scorer(model="d1", http=Mock()), path, config={}
                )
            self.assertFalse((path / "manifest.json").exists())

    def test_invalid_checkpoint_level_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            http = Mock()
            http.get.return_value = response(models())
            http.post.return_value = response(answer())
            scorer = D1Scorer(model="d1-3b", http=http)
            items = [BaseWordRow(1, "ac", "")]
            run_campaign(items, scorer, path, config={})
            record_path = path / "records/1.json"
            record = json.loads(record_path.read_text())
            record["rarity_level"] = 0
            record_path.write_text(json.dumps(record))
            previous = (path / "predictions.csv").read_bytes()
            with self.assertRaisesRegex(ValueError, "checkpoint"):
                run_campaign(items, scorer, path, config={})

            self.assertEqual((path / "predictions.csv").read_bytes(), previous)

    def test_summary_exposes_partial_coverage_and_request_timing(self):
        import requests

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            http = Mock()
            http.get.return_value = response(models())
            http.post.side_effect = [response(answer()), requests.Timeout("offline")]
            run_campaign(
                [BaseWordRow(1, "ac", ""), BaseWordRow(2, "casă", "")],
                D1Scorer(model="d1-3b", http=http),
                path,
                config={},
            )
            summary = json.loads((path / "summary.json").read_text())
            self.assertEqual((summary["scored"], summary["failed"], summary["pending"]), (1, 1, 0))
            self.assertGreaterEqual(summary["total_seconds"], 0)
