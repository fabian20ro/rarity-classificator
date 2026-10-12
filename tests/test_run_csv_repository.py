import tempfile
import unittest
from pathlib import Path

from classificator.run_csv_repository import RunCsvRepository
from classificator.csv_codec import CsvFormatError
from classificator.models import RunBaseline, RunCsvRow


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
            with self.assertRaisesRegex(
                CsvFormatError, r"Duplicate word_id=1 at .*:3"
            ):
                self.repo.load_run_rows(path)

    def test_load_run_rows_rejects_blank_word(self):
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
                    ["1", "", "N", "3", "uncertain", "0.3", "t", "m", "r"],
                ],
            )
            with self.assertRaises(CsvFormatError):
                self.repo.load_run_rows(path)

    def test_load_run_rows_rejects_invalid_int_word_id(self):
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
                    ["abc", "om", "N", "3", "uncertain", "0.3", "t", "m", "r"],
                ],
            )
            with self.assertRaises(CsvFormatError):
                self.repo.load_run_rows(path)

    def test_load_run_rows_rejects_rarity_out_of_range(self):
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
                    ["2", "casă", "N", "6", "common", "0.9", "t2", "m", "r"],
                ],
            )
            with self.assertRaisesRegex(
                CsvFormatError, r"rarity_level out of range at .*:3"
            ):
                self.repo.load_run_rows(path)

    def test_load_final_levels_falls_back_to_rarity_level(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "levels.csv"
            self.repo.write_rows(
                path,
                ["word_id", "word", "type", "rarity_level"],
                [
                    ["1", "om", "N", "5"],
                    ["2", "casă", "N", "3"],
                ],
            )
            levels = self.repo.load_final_levels(path)
            self.assertEqual(levels, {1: 5, 2: 3})

    def test_load_final_levels_raises_when_no_level_column(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "levels.csv"
            self.repo.write_rows(
                path,
                ["word_id", "word", "type"],
                [
                    ["1", "om", "N"],
                ],
            )
            with self.assertRaises(CsvFormatError):
                self.repo.load_final_levels(path)

    def test_load_final_levels_rejects_level_out_of_range(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "levels.csv"
            self.repo.write_rows(
                path,
                ["word_id", "word", "type", "final_level"],
                [
                    ["1", "om", "N", "6"],
                ],
            )
            with self.assertRaisesRegex(
                CsvFormatError, r"final_level out of range at .*:2"
            ):
                self.repo.load_final_levels(path)


    def test_merge_and_rewrite_atomic_updates_existing_and_adds_new(self):
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
            baseline = self.repo.compute_baseline(self.repo.load_run_rows(path))
            merged = self.repo.merge_and_rewrite_atomic(
                path,
                [
                    _row(1, "om", "N", 5, "updated", 0.8, "t3", "m", "r"),
                    _row(3, "noe", "N", 2, "common", 0.7, "t3", "m", "r"),
                ],
                baseline,
            )
            self.assertIsNone(merged)
            rows = self.repo.load_run_rows(path)
            self.assertEqual([r.word_id for r in rows], [1, 2, 3])
            self.assertEqual(rows[0].rarity_level, 5)
            self.assertEqual(rows[0].tag, "updated")
            self.assertEqual(rows[1].rarity_level, 1)
            self.assertEqual(rows[2].rarity_level, 2)

    def test_merge_and_rewrite_atomic_aborts_on_shrunk_merge(self):
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
                ],
            )
            original_text = path.read_text(encoding="utf-8")
            baseline = RunBaseline(count=2, min_id=1, max_id=2)
            with self.assertRaisesRegex(RuntimeError, "Guarded rewrite aborted"):
                self.repo.merge_and_rewrite_atomic(
                    path,
                    [_row(1, "om", "N", 3, "uncertain", 0.3, "t", "m", "r")],
                    baseline,
                )
            self.assertEqual(path.read_text(encoding="utf-8"), original_text)


def _row(word_id: int, word: str, type_: str, rarity: int, tag: str, confidence: float, scored_at: str, model: str, run_slug: str) -> RunCsvRow:
    return RunCsvRow(
        word_id=word_id,
        word=word,
        type=type_,
        rarity_level=rarity,
        tag=tag,
        confidence=confidence,
        scored_at=scored_at,
        model=model,
        run_slug=run_slug,
    )


if __name__ == "__main__":
    unittest.main()
