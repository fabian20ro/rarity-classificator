import unittest
from pathlib import Path
from unittest.mock import MagicMock
import csv

from classificator.steps.step4_upload import run_step4, Step4Options
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

    def tearDown(self):
        self.temp_dir.cleanup()

if __name__ == "__main__":
    unittest.main()
