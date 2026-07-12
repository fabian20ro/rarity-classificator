import tempfile
import unittest
from pathlib import Path

from classificator.run_csv_repository import RunCsvRepository
from classificator.csv_codec import CsvFormatError


class RunCsvRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.repo = RunCsvRepository()

    def test_load_final_levels_prefers_final_level(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "levels.csv"
            self.repo.write_rows(
                path,
                ["word_id", "word", "type", "rarity_level", "final_level"],
                [
                    ["1", "om", "N", "5", "1"],
                    ["2", "casă", "N", "4", "2"],
                ],
            )
            levels = self.repo.load_final_levels(path)
            self.assertEqual(levels, {1: 1, 2: 2})

    def test_load_run_rows_accepts_distinct_word_ids(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.csv"
            self.repo.write_rows(
                path,
                [
                    "word_id",
                    "word",
                    "type",
                    "rarity_level",
                    "tag",
                    "confidence",
                    "scored_at",
                    "model",
                    "run_slug",
                ],
                [
                    ["1", "om", "N", "3", "uncertain", "0.3", "t", "m", "r"],
                    ["2", "casă", "N", "1", "common", "0.9", "t2", "m", "r"],
                ],
            )
            rows = self.repo.load_run_rows(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].word_id, 1)
            self.assertAlmostEqual(rows[0].confidence, 0.3)
            self.assertEqual(rows[1].word_id, 2)

    def test_load_run_rows_rejects_duplicate_word_ids(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.csv"
            self.repo.write_rows(
                path,
                [
                    "word_id",
                    "word",
                    "type",
                    "rarity_level",
                    "tag",
                    "confidence",
                    "scored_at",
                    "model",
                    "run_slug",
                ],
                [
                    ["1", "om", "N", "3", "uncertain", "0.3", "t", "m", "r"],
                    ["1", "om", "N", "1", "common", "0.9", "t2", "m", "r"],
                ],
            )
            with self.assertRaises(CsvFormatError):
                self.repo.load_run_rows(path)


if __name__ == "__main__":
    unittest.main()
