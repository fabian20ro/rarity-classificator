import unittest
from pathlib import Path
from unittest.mock import MagicMock
import csv

from classificator.steps.step4_upload import run_step4, Step4Options, _build_partial_plan, _build_full_fallback_plan
from classificator.models import UploadMode, WordLevel
from classificator.run_csv_repository import RunCsvRepository
from classificator.word_store import WordStore
from classificator.upload_marker_writer import UploadMarkerWriter
from classificator.csv_codec import CsvRecord, CsvTable

class TestStep4Upload(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        
        self.final_csv = self.test_dir / "final.csv"
        self.report_csv = self.test_dir / "report.csv"
        
        # Setup input CSV
        with open(self.final_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["word_id", "word", "type", "rarity_level"])
            writer.writerow(["1", "apple", "fruit", "2"])
            writer.writerow(["2", "banana", "fruit", "3"])

        self.mock_repo = MagicMock(spec=RunCsvRepository)
        self.mock_word_store = MagicMock(spec=WordStore)
        self.mock_marker_writer = MagicMock(spec=UploadMarkerWriter)
        
        # Mock DB levels
        self.mock_word_store.fetch_all_word_levels.return_value = [
            WordLevel(word_id=1, rarity_level=1),
            WordLevel(word_id=2, rarity_level=1)
        ]
        
        # Mock Repo behavior
        def mock_load_final(path):
            return {
                1: 2,
                2: 3,
            }
        self.mock_repo.load_final_levels.side_effect = mock_load_final
        
        def mock_write_rows(path, headers, rows):
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
        self.mock_repo.write_rows.side_effect = mock_write_rows
        
        self.mock_marker_writer.mark_uploaded_rows.return_value = MagicMock(marker_path=self.test_dir/"marker.json")

    def test_partial_upload(self):
        options = Step4Options(
            final_csv_path=self.final_csv,
            mode=UploadMode.PARTIAL,
            report_path=self.report_csv,
            upload_batch_id="test-batch"
        )
        
        run_step4(options, word_store=self.mock_word_store, repo=self.mock_repo, marker_writer=self.mock_marker_writer)
        
        self.mock_word_store.update_rarity_levels_chunked.assert_called()
        with open(self.report_csv, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['new_level'], '2')
            self.assertEqual(rows[1]['new_level'], '3')

    def test_full_upload(self):
        # Setup extra row in DB that isn't in final CSV to check fallback
        self.mock_word_store.fetch_all_word_levels.return_value = [
            WordLevel(word_id=1, rarity_level=1),
            WordLevel(word_id=2, rarity_level=1),
            WordLevel(word_id=3, rarity_level=1), # In DB but not in final CSV
        ]
        
        options = Step4Options(
            final_csv_path=self.final_csv,
            mode=UploadMode.FULL_FALLBACK,
            report_path=self.report_csv,
            upload_batch_id="test-batch"
        )
        
        run_step4(options, word_store=self.mock_word_store, repo=self.mock_repo, marker_writer=self.mock_marker_writer)
        
        self.mock_word_store.update_rarity_levels_chunked.assert_called()
        with open(self.report_csv, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            # word_id 3 should have fallback level 4
            found_3 = next(r for r in rows if r['word_id'] == '3')
            self.assertEqual(found_3['new_level'], '4')

    def test_partial_missing_db_word(self):
        # word_id 2 is in CSV but missing from db_levels → reported as missing_db_word, no update emitted
        self.mock_word_store.fetch_all_word_levels.return_value = [
            WordLevel(word_id=1, rarity_level=1),
        ]

        options = Step4Options(
            final_csv_path=self.final_csv,
            mode=UploadMode.PARTIAL,
            report_path=self.report_csv,
            upload_batch_id="test-batch",
        )

        run_step4(options, word_store=self.mock_word_store, repo=self.mock_repo, marker_writer=self.mock_marker_writer)

        # Only word 1 should be in updates; word 2 absent from DB
        self.assertEqual(set(self.mock_word_store.update_rarity_levels_chunked.call_args[0][0].keys()), {1})
        with open(self.report_csv, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            sources = [r["source"] for r in rows]
            self.assertIn("missing_db_word", sources)

    def test_partial_audit_gate_blocks_upload(self):
        # When reference_csv is provided and quality audit fails, run_step4 must raise RuntimeError
        options = Step4Options(
            final_csv_path=self.final_csv,
            mode=UploadMode.PARTIAL,
            report_path=self.report_csv,
            upload_batch_id="test-batch",
            reference_csv=self.test_dir / "ref.csv",
        )

        from unittest.mock import patch

        with patch("classificator.tools.quality_audit.run_quality_audit") as mock_audit:
            mock_result = MagicMock()
            mock_result.passed = False
            mock_result.failures = ["jaccard too low"]
            mock_audit.return_value = mock_result

            with self.assertRaises(RuntimeError) as ctx:
                run_step4(options, word_store=self.mock_word_store, repo=self.mock_repo, marker_writer=self.mock_marker_writer)
            self.assertIn("Quality audit failed", str(ctx.exception))
            # Upload must not have been executed before the gate raised
            self.assertFalse(self.mock_word_store.update_rarity_levels_chunked.called)

    def test_partial_audit_pass_allows_upload(self):
        # When reference_csv is provided and quality audit passes, run_step4 proceeds normally
        options = Step4Options(
            final_csv_path=self.final_csv,
            mode=UploadMode.PARTIAL,
            report_path=self.report_csv,
            upload_batch_id="test-batch",
            reference_csv=self.test_dir / "ref.csv",
        )

        from unittest.mock import patch

        with patch("classificator.tools.quality_audit.run_quality_audit") as mock_audit:
            mock_result = MagicMock()
            mock_result.passed = True
            mock_result.failures = []
            mock_audit.return_value = mock_result

            run_step4(options, word_store=self.mock_word_store, repo=self.mock_repo, marker_writer=self.mock_marker_writer)

            # Upload must have been executed after the gate passed
            self.assertTrue(self.mock_word_store.update_rarity_levels_chunked.called)
            with open(self.report_csv, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 2)

    def _build_full_fallback_plan(self, final_levels, db_levels):
        return _build_full_fallback_plan(final_levels, db_levels)

class TestBuildPartialPlan(unittest.TestCase):
    """Direct unit test for _build_partial_plan — verifying the equality guard contract."""

    def test_matching_levels_are_skipped_with_already_matched_status(self):
        # DB has words 1,2; final CSV also has 1,2 with matching levels → both should be already_matched, no updates
        final_levels = {1: 1, 2: 1}
        db_levels = {
            1: WordLevel(word_id=1, rarity_level=1),
            2: WordLevel(word_id=2, rarity_level=1),
        }

        updates, report_rows, status = _build_partial_plan(final_levels, db_levels)

        # No words should be in updates — all levels already match
        self.assertEqual(set(updates.keys()), set())

        # Status: both "already_matched"
        self.assertEqual(status[1], "already_matched")
        self.assertEqual(status[2], "already_matched")

        # Report rows: sorted by word_id, with correct source marker
        self.assertEqual(len(report_rows), 2)
        for i, wid in enumerate([1, 2]):
            row = report_rows[i]
            self.assertEqual(row[0], str(wid))  # word_id
            self.assertEqual(row[1], "1")  # old level (from db_levels)
            self.assertEqual(row[2], "1")  # new level (same as old)
            self.assertEqual(row[3], "already_matched")

    def test_mixed_matching_and_changing_levels(self):
        # DB has words 1,2; word 1 matches, word 2 changes → one already_matched, one uploaded
        final_levels = {1: 1, 2: 3}
        db_levels = {
            1: WordLevel(word_id=1, rarity_level=1),
            2: WordLevel(word_id=2, rarity_level=1),
        }

        updates, report_rows, status = _build_partial_plan(final_levels, db_levels)

        # Only word 2 should be in updates (level changes from 1→3)
        self.assertEqual(set(updates.keys()), {2})
        self.assertEqual(updates[2], 3)

        # Status: mixed statuses
        self.assertEqual(status[1], "already_matched")
        self.assertEqual(status[2], "uploaded")

        # Report rows: sorted by word_id, correct sources
        self.assertEqual(len(report_rows), 2)
        sources = [row[3] for row in report_rows]
        self.assertIn("already_matched", sources)
        self.assertIn("final_csv", sources)


class TestBuildFullFallbackPlan(unittest.TestCase):
    """Direct unit test for _build_full_fallback_plan — verifying the fallback contract independently."""

    def test_extra_db_words_get_fallback_level(self):
        # DB has words 1,2,3; final_csv only has words 1,2 → word 3 should get FALLBACK_RARITY_LEVEL (4)
        final_levels = {1: 2, 2: 3}
        db_levels = {
            1: WordLevel(word_id=1, rarity_level=1),
            2: WordLevel(word_id=2, rarity_level=1),
            3: WordLevel(word_id=3, rarity_level=1),
        }

        updates, report_rows, status = _build_full_fallback_plan(final_levels, db_levels)

        # All DB words should be in updates with their final or fallback level
        self.assertEqual(set(updates.keys()), {1, 2, 3})
        self.assertEqual(updates[1], 2)
        self.assertEqual(updates[2], 3)
        self.assertEqual(updates[3], 4)  # FALLBACK_RARITY_LEVEL

        # Status: all "uploaded"
        self.assertEqual(status[1], "uploaded")
        self.assertEqual(status[2], "uploaded")
        self.assertEqual(status[3], "uploaded")

        # Report rows: sorted by word_id, with correct source marker
        self.assertEqual(len(report_rows), 3)
        for i, wid in enumerate([1, 2, 3]):
            row = report_rows[i]
            self.assertEqual(row[0], str(wid))  # word_id
            self.assertEqual(row[1], "1")  # old level (from db_levels)
            if wid == 3:
                self.assertEqual(row[2], "4")  # fallback level
                self.assertEqual(row[3], "fallback_4")
            else:
                self.assertEqual(row[2], str(final_levels[wid]))
                self.assertEqual(row[3], "final_csv")

    def test_empty_final_levels_returns_all_fallback(self):
        final_levels = {}
        db_levels = {
            1: WordLevel(word_id=1, rarity_level=2),
            2: WordLevel(word_id=2, rarity_level=3),
        }

        updates, report_rows, status = _build_full_fallback_plan(final_levels, db_levels)

        # All DB words should get fallback level (4) since final_levels is empty
        self.assertEqual(set(updates.keys()), {1, 2})
        for wid in [1, 2]:
            self.assertEqual(updates[wid], 4)
            self.assertEqual(status[wid], "uploaded")

        # All rows should have fallback_4 as source
        sources = {row[3] for row in report_rows}
        self.assertEqual(sources, {"fallback_4"})


class TestStep4Upload(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
