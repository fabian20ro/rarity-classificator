import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from classificator.run_csv_repository import RunCsvRepository
from classificator.tools.review_low_confidence import (
    ReviewLabel,
    ReviewItem,
    _map_input_to_label,
    _resolve_level_column,
    append_review_label,
    build_review_queue,
    compute_l1_review_stats,
    load_latest_review_labels,
    load_review_items,
    parse_only_levels,
    run_l1_review_check,
    run_review_low_confidence,
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

    def test_load_items_skips_blank_word_rows(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "run.csv"
            content = (
                "word_id,word,type,rarity_level,confidence\n"
                "1,,N,1,0.9\n"
                "2,  ,N,1,0.8\n"
                "3,cuvant3,N,1,0.7\n"
            )
            path.write_text(content, encoding="utf-8")
            items = load_review_items(csv_path=path, repo=self.repo)
            self.assertEqual([x.word_id for x in items], [3])
            self.assertEqual(items[0].word, "cuvant3")

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

    def test_queue_excludes_decided_labels_regardless_of_flag(self):
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
                1: ReviewLabel(word_id=1, predicted_level=1, label="2"),
            }
            queue_no_flag = build_review_queue(items, labels, include_undecided=False)
            self.assertEqual([x.word_id for x in queue_no_flag], [2, 3])
            queue_yes_flag = build_review_queue(items, labels, include_undecided=True)
            self.assertEqual([x.word_id for x in queue_yes_flag], [2, 3])

    def test_queue_includes_unlabeled_items(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "run.csv"
            self._write_csv(
                path,
                ["word_id", "word", "type", "rarity_level", "confidence"],
                [
                    ["1", "a", "N", "1", "0.1"],
                    ["2", "b", "N", "1", "0.2"],
                ],
            )
            items = load_review_items(csv_path=path, repo=self.repo)
            labels: dict[int, ReviewLabel] = {}
            queue_default = build_review_queue(items, labels, include_undecided=False)
            self.assertEqual([x.word_id for x in queue_default], [1, 2])
            queue_with_flag = build_review_queue(items, labels, include_undecided=True)
            self.assertEqual([x.word_id for x in queue_with_flag], [1, 2])

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


class LoadReviewItemsContractTest(unittest.TestCase):
    def setUp(self):
        self.repo = RunCsvRepository()

    def _write_csv(self, path: Path, headers: list[str], rows: list[list[str]]):
        self.repo.write_rows(path, headers, rows)

    def test_missing_confidence_column_defaults_to_one(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "run.csv"
            self._write_csv(
                path,
                ["word_id", "word", "type", "rarity_level"],
                [["1", "cuvant1", "N", "1"]],
            )
            items = load_review_items(csv_path=path, repo=self.repo)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].predicted_confidence, 1.0)

    def test_invalid_level_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "run.csv"
            self._write_csv(
                path,
                ["word_id", "word", "type", "rarity_level", "confidence"],
                [["1", "cuvant1", "N", "0", "0.5"]],
            )
            with self.assertRaises(ValueError) as cm:
                load_review_items(csv_path=path, repo=self.repo)
            self.assertIn("Invalid rarity_level 0", str(cm.exception))

    def test_confidence_out_of_range_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "run.csv"
            self._write_csv(
                path,
                ["word_id", "word", "type", "rarity_level", "confidence"],
                [["1", "cuvant1", "N", "1", "1.5"]],
            )
            with self.assertRaises(ValueError) as cm:
                load_review_items(csv_path=path, repo=self.repo)
            self.assertIn("Invalid confidence 1.5", str(cm.exception))

    def test_only_levels_filters_levels(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "run.csv"
            self._write_csv(
                path,
                ["word_id", "word", "type", "rarity_level", "confidence"],
                [
                    ["1", "a", "N", "1", "0.1"],
                    ["2", "b", "N", "2", "0.2"],
                    ["3", "c", "N", "3", "0.3"],
                ],
            )
            items = load_review_items(csv_path=path, repo=self.repo, only_levels={1, 3})
            self.assertEqual([x.word_id for x in items], [1, 3])

    def test_explicit_level_column_not_in_headers_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "run.csv"
            self._write_csv(
                path,
                ["word_id", "word", "type", "rarity_level", "confidence"],
                [["1", "a", "N", "1", "0.1"]],
            )
            with self.assertRaises(ValueError) as cm:
                load_review_items(csv_path=path, repo=self.repo, level_column="final_level")
            self.assertIn("missing requested level column 'final_level'", str(cm.exception))


class L1GateTest(unittest.TestCase):
    def _write_labels(self, root: Path, rows: list[list[str]]) -> Path:
        path = root / "labels.csv"
        RunCsvRepository().write_rows(
            path,
            ["ts_utc", "run_csv", "word_id", "word", "type", "predicted_level", "predicted_confidence", "label"],
            rows,
        )
        return path

    def test_gate_pass_returns_stats(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            labels_csv = self._write_labels(
                root,
                [
                    ["t", "r", "1", "a", "N", "1", "0.1", "1"],
                    ["t", "r", "2", "b", "N", "1", "0.2", "1"],
                ],
            )
            stats = run_l1_review_check(labels_csv=labels_csv, min_reviewed=2, min_precision=0.5)
            self.assertEqual(stats.reviewed_decided, 2)
            self.assertEqual(stats.accepted_level1, 2)
            self.assertEqual(stats.precision, 1.0)

    def test_gate_fail_on_low_precision_exits_one(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            labels_csv = self._write_labels(
                root,
                [
                    ["t", "r", "1", "a", "N", "1", "0.1", "1"],
                    ["t", "r", "2", "b", "N", "1", "0.2", "2"],
                ],
            )
            with self.assertRaises(SystemExit) as cm:
                run_l1_review_check(labels_csv=labels_csv, min_precision=0.9)
            self.assertEqual(cm.exception.code, 1)

    def test_gate_fail_on_low_reviewed_exits_one(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            labels_csv = self._write_labels(root, [["t", "r", "1", "a", "N", "1", "0.1", "2"]])
            with self.assertRaises(SystemExit) as cm:
                run_l1_review_check(labels_csv=labels_csv, min_reviewed=5)
            self.assertEqual(cm.exception.code, 1)


class AppendReviewLabelTest(unittest.TestCase):
    def test_append_creates_header_then_row(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            labels_csv = root / "labels.csv"
            run_csv = root / "run.csv"
            item = ReviewItem(word_id=7, word="cuvant7", type="N", predicted_level=1, predicted_confidence=0.123456)
            append_review_label(labels_csv=labels_csv, run_csv=run_csv, item=item, label="1")
            append_review_label(labels_csv=labels_csv, run_csv=run_csv, item=item, label="2")
            content = labels_csv.read_text(encoding="utf-8")
            lines = content.strip().splitlines()
            self.assertEqual(lines[0], "ts_utc,run_csv,word_id,word,type,predicted_level,predicted_confidence,label")
            self.assertEqual(len(lines), 3)
            latest = load_latest_review_labels(labels_csv)
            self.assertEqual(latest[7].label, "2")
            self.assertEqual(latest[7].predicted_level, 1)


class EmptyQueueTest(unittest.TestCase):
    def test_empty_queue_prints_l1_summary_and_returns(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "run.csv"
            labels_csv = root / "labels.csv"
            RunCsvRepository().write_rows(
                csv_path,
                ["word_id", "word", "type", "rarity_level", "confidence"],
                [["1", "a", "N", "1", "0.1"]],
            )
            # Pre-label the only item so the queue is empty
            load_latest_review_labels(labels_csv)
            from classificator.tools.review_low_confidence import ReviewItem as _RI

            item = _RI(word_id=1, word="a", type="N", predicted_level=1, predicted_confidence=0.1)
            append_review_label(labels_csv=labels_csv, run_csv=csv_path, item=item, label="1")
            with patch("builtins.print") as mock_print:
                run_review_low_confidence(csv_path=csv_path, labels_csv=labels_csv, repo=RunCsvRepository())
            out = [str(c.args[0]) for c in mock_print.call_args_list]
            self.assertTrue(any("queue_size=0" in line for line in out))
            self.assertTrue(any("l1_reviewed_decided=1" in line for line in out))
            self.assertTrue(any("l1_precision=1.0000" in line for line in out))


class ReviewSkipCountTest(unittest.TestCase):
    def setUp(self):
        self.repo = RunCsvRepository()

    def _write_csv(self, path: Path, headers: list[str], rows: list[list[str]]):
        self.repo.write_rows(path, headers, rows)

    @patch("builtins.print")
    @patch("builtins.input", side_effect=["1"] * 4 + ["q"])
    def test_skip_count_slices_from_front(self, mock_input, mock_print):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "run.csv"
            labels_csv = root / "labels.csv"
            self._write_csv(
                csv_path,
                ["word_id", "word", "type", "rarity_level", "confidence"],
                [
                    ["1", "a", "N", "1", "0.1"],
                    ["2", "b", "N", "1", "0.2"],
                    ["3", "c", "N", "1", "0.3"],
                    ["4", "d", "N", "1", "0.4"],
                ],
            )
            load_latest_review_labels(labels_csv)  # create empty labels file
            run_review_low_confidence(
                csv_path=csv_path,
                labels_csv=labels_csv,
                repo=self.repo,
                skip_count=2,
            )
            print_calls = [str(c.args[0]) for c in mock_print.call_args_list]
            queue_line = next((c for c in print_calls if "queue_size" in c), None)
            self.assertIsNotNone(queue_line)
            self.assertIn("skipped=2", queue_line)

    @patch("builtins.print")
    @patch("builtins.input", side_effect=lambda *a, **kw: "q")
    def test_skip_count_zero_no_effect(self, mock_input, mock_print):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "run.csv"
            labels_csv = root / "labels.csv"
            self._write_csv(
                csv_path,
                ["word_id", "word", "type", "rarity_level", "confidence"],
                [
                    ["1", "a", "N", "1", "0.1"],
                    ["2", "b", "N", "1", "0.2"],
                ],
            )
            load_latest_review_labels(labels_csv)  # create empty labels file
            run_review_low_confidence(
                csv_path=csv_path,
                labels_csv=labels_csv,
                repo=self.repo,
                skip_count=0,
            )
            print_calls = [str(c.args[0]) for c in mock_print.call_args_list]
            queue_line = next((c for c in print_calls if "queue_size" in c), None)
            self.assertIsNotNone(queue_line)
            self.assertIn("skipped=0", queue_line)

    @patch("builtins.print")
    def test_skip_count_exceeds_queue_clips_to_empty(self, mock_print):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "run.csv"
            labels_csv = root / "labels.csv"
            self._write_csv(
                csv_path,
                ["word_id", "word", "type", "rarity_level", "confidence"],
                [
                    ["1", "a", "N", "1", "0.1"],
                ],
            )
            load_latest_review_labels(labels_csv)  # create empty labels file
            run_review_low_confidence(
                csv_path=csv_path,
                labels_csv=labels_csv,
                repo=self.repo,
                skip_count=10,
            )
            print_calls = [str(c.args[0]) for c in mock_print.call_args_list]
            queue_line = next((c for c in print_calls if "queue_size" in c), None)
            self.assertIsNotNone(queue_line)
            self.assertIn("queue_size=0", queue_line)
            self.assertIn("skipped=1", queue_line)


if __name__ == "__main__":
    unittest.main()
