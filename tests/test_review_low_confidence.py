import tempfile
import unittest
from pathlib import Path

from classificator.run_csv_repository import RunCsvRepository
from classificator.tools.review_low_confidence import (
    ReviewLabel,
    _map_input_to_label,
    _resolve_level_column,
    build_review_queue,
    compute_l1_review_stats,
    load_latest_review_labels,
    load_review_items,
    parse_only_levels,
)


class ReviewLowConfidenceTest(unittest.TestCase):
    def setUp(self):
        self.repo = RunCsvRepository()

    def _write_csv(self, path: Path, headers: list[str], rows: list[list[str]]):
        self.repo.write_rows(path, headers, rows)

    def test_parse_only_levels(self):
        self.assertIsNone(parse_only_levels(None))
        self.assertEqual(parse_only_levels("1,3,5"), {1, 3, 5})
        with self.assertRaises(ValueError):
            parse_only_levels("0")
        with self.assertRaises(ValueError):
            parse_only_levels("x")

    def test_load_items_sorted_by_confidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "run.csv"
            self._write_csv(
                path,
                ["word_id", "word", "type", "rarity_level", "confidence"],
                [
                    ["10", "cuvant10", "N", "1", "0.9"],
                    ["11", "cuvant11", "N", "1", "0.2"],
                    ["12", "cuvant12", "N", "4", "0.5"],
                ],
            )
            items = load_review_items(csv_path=path, repo=self.repo, only_levels={1})
            self.assertEqual([x.word_id for x in items], [11, 10])

    def test_queue_skips_labeled_unless_undecided_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "run.csv"
            self._write_csv(
                path,
                ["word_id", "word", "type", "rarity_level", "confidence"],
                [
                    ["1", "a", "N", "1", "0.1"],
                    ["2", "b", "N", "1", "0.2"],
                    ["3", "c", "N", "1", "0.3"],
                ],
            )
            items = load_review_items(csv_path=path, repo=self.repo)
            labels = {
                1: ReviewLabel(word_id=1, predicted_level=1, label="1"),
                2: ReviewLabel(word_id=2, predicted_level=1, label="undecided"),
            }
            queue_default = build_review_queue(items, labels, include_undecided=False)
            self.assertEqual([x.word_id for x in queue_default], [3])
            queue_with_undecided = build_review_queue(items, labels, include_undecided=True)
            self.assertEqual([x.word_id for x in queue_with_undecided], [2, 3])

    def test_l1_stats_precision(self):
        labels = {
            1: ReviewLabel(word_id=1, predicted_level=1, label="1"),
            2: ReviewLabel(word_id=2, predicted_level=1, label="2"),
            3: ReviewLabel(word_id=3, predicted_level=1, label="unknown_4_5"),
            4: ReviewLabel(word_id=4, predicted_level=1, label="undecided"),
            5: ReviewLabel(word_id=5, predicted_level=2, label="1"),
        }
        stats = compute_l1_review_stats(labels)
        self.assertEqual(stats.reviewed_decided, 3)
        self.assertEqual(stats.accepted_level1, 1)
        self.assertAlmostEqual(stats.precision, 1 / 3)

    def test_map_input_to_label_all_valid_inputs(self):
        self.assertEqual(_map_input_to_label("1"), "1")
        self.assertEqual(_map_input_to_label("2"), "2")
        self.assertEqual(_map_input_to_label("3"), "3")
        self.assertEqual(_map_input_to_label("u"), "unknown_4_5")
        self.assertEqual(_map_input_to_label("unknown"), "unknown_4_5")
        self.assertEqual(_map_input_to_label("d"), "undecided")
        self.assertEqual(_map_input_to_label("undecided"), "undecided")
        self.assertEqual(_map_input_to_label("s"), "skip")
        self.assertEqual(_map_input_to_label("q"), "quit")
        self.assertEqual(_map_input_to_label("quit"), "quit")
        self.assertEqual(_map_input_to_label("exit"), "quit")

    def test_map_input_to_label_invalid_returns_none(self):
        self.assertIsNone(_map_input_to_label(""))
        self.assertIsNone(_map_input_to_label("abc"))
        self.assertIsNone(_map_input_to_label("4"))
        self.assertIsNone(_map_input_to_label("u1"))

    def test_resolve_level_column_explicit_wins(self):
        headers = ["word_id", "rarity_level", "final_level"]
        result = _resolve_level_column(headers, level_column="final_level")
        self.assertEqual(result, "final_level")

    def test_resolve_level_column_fallback_to_first_match(self):
        headers = ["word_id", "median_level"]
        result = _resolve_level_column(headers, level_column=None)
        self.assertEqual(result, "median_level")

    def test_resolve_level_column_missing_raises(self):
        headers = ["word_id", "word"]
        with self.assertRaises(ValueError) as cm:
            _resolve_level_column(headers, level_column="rarity_level")
        self.assertIn("missing requested level column 'rarity_level'", str(cm.exception))

    def test_resolve_level_column_no_match_raises(self):
        headers = ["word_id", "custom_col"]
        with self.assertRaises(ValueError) as cm:
            _resolve_level_column(headers, level_column=None)
        self.assertIn("missing level column", str(cm.exception))

    def test_load_latest_review_labels_missing_file_returns_empty(self):
        labels_csv = Path("/nonexistent/path/labels.csv")
        result = load_latest_review_labels(labels_csv)
        self.assertEqual(result, {})

    def test_load_latest_review_labels_populated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "labels.csv"
            self._write_csv(
                csv_path,
                ["word_id", "predicted_level", "label"],
                [["10", "1", "1"], ["11", "2", "undecided"]],
            )
            result = load_latest_review_labels(csv_path)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[10].label, "1")
            self.assertEqual(result[10].predicted_level, 1)
            self.assertEqual(result[11].label, "undecided")

    def test_load_latest_review_labels_empty_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "labels.csv"
            self._write_csv(csv_path, ["word_id", "predicted_level", "label"], [])
            result = load_latest_review_labels(csv_path)
            self.assertEqual(result, {})

    def test_load_latest_review_labels_overwrites_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "labels.csv"
            self._write_csv(
                csv_path,
                ["word_id", "predicted_level", "label"],
                [
                    ["10", "1", "2"],
                    ["10", "2", "3"],
                ],
            )
            result = load_latest_review_labels(csv_path)
            self.assertEqual(result[10].label, "3")
            self.assertEqual(result[10].predicted_level, 2)

    def test_load_latest_review_labels_trims_whitespace(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "labels.csv"
            # Manually write CSV to add whitespace since _write_csv won't include it
            content = 'word_id,predicted_level,label\n10,1," 2 "\n'
            csv_path.write_text(content, encoding="utf-8")
            result = load_latest_review_labels(csv_path)
            self.assertEqual(result[10].label.strip(), "2".strip())


if __name__ == "__main__":
    unittest.main()
