import contextlib
import csv
import io
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from src.classificator.steps.step1_export import run_step1, Step1Options
from src.classificator.run_csv_repository import RunCsvRepository
from src.classificator.word_store import WordStore
from src.classificator.constants import BASE_CSV_HEADERS


class TestStep1Export(unittest.TestCase):
    def test_dry_run_quotes_csv_special_characters_without_writing(self):
        for word in ['comma,word', 'quoted"word', 'multi\nline']:
            with self.subTest(word=word):
                store = MagicMock(spec=WordStore)
                store.fetch_all_words.return_value = [(1, word, 'noun')]
                repo = MagicMock(spec=RunCsvRepository)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    run_step1(Step1Options(Path('never-written.csv'), dry_run=True),
                              word_store=store, repo=repo)
                preview = output.getvalue().split('\n', 1)[1]
                rows = list(csv.reader(io.StringIO(preview)))
                self.assertEqual(rows, [list(BASE_CSV_HEADERS), ['1', word, 'noun']])
                repo.write_rows.assert_not_called()

    def setUp(self):
        self.output_csv = Path("test_output.csv")
        if self.output_csv.exists():
            self.output_csv.unlink()

        self.mock_repo = MagicMock(spec=RunCsvRepository)

        # fetch_all_words returns tuples: (id, word, type)
        self.words = [
            (1, "apple", "fruit"),
            (2, "banana", "fruit"),
        ]

    def tearDown(self):
        if self.output_csv.exists():
            self.output_csv.unlink()

    def test_fetch_all_words_raises_propagates(self):
        store = MagicMock(spec=WordStore)
        store.fetch_all_words.side_effect = RuntimeError("db down")
        options = Step1Options(output_csv_path=self.output_csv)
        with self.assertRaises(RuntimeError, msg="fetch error must propagate"):
            run_step1(options, word_store=store, repo=self.mock_repo)
        # write_rows must not be called before the fetch failure occurs
        self.mock_repo.write_rows.assert_not_called()

    def test_write_rows_raises_propagates(self):
        options = Step1Options(output_csv_path=self.output_csv)
        self.mock_repo.write_rows.side_effect = PermissionError("denied")
        store = MagicMock(spec=WordStore)
        store.fetch_all_words.return_value = self.words
        with self.assertRaises(PermissionError, msg="write error must propagate"):
            run_step1(options, word_store=store, repo=self.mock_repo)
        # write_rows was invoked once with correct args before failing — fetch succeeded, data reached write phase
        self.mock_repo.write_rows.assert_called_once()
        args, _ = self.mock_repo.write_rows.call_args
        self.assertEqual(args[0], self.output_csv)
    def test_run_step1_success(self):
        options = Step1Options(output_csv_path=self.output_csv)
        store = MagicMock(spec=WordStore)
        store.fetch_all_words.return_value = self.words
        result_path = run_step1(options, word_store=store, repo=self.mock_repo)

        self.assertEqual(result_path, self.output_csv)
        self.mock_repo.write_rows.assert_called_once()
        # Check output path, headers and data
        args, _ = self.mock_repo.write_rows.call_args
        self.assertEqual(args[0], self.output_csv)
        headers = args[1]
        rows = args[2]
        self.assertEqual(headers, ["word_id", "word", "type"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], ["1", "apple", "fruit"])
        self.assertEqual(rows[1], ["2", "banana", "fruit"])

    def test_run_step1_empty_input(self):
        store = MagicMock(spec=WordStore)
        store.fetch_all_words.return_value = []
        options = Step1Options(output_csv_path=self.output_csv)
        result_path = run_step1(options, word_store=store, repo=self.mock_repo)

        self.assertEqual(result_path, self.output_csv)
        args, _ = self.mock_repo.write_rows.call_args
        headers, rows = args[1], args[2]
        self.assertEqual(headers, ["word_id", "word", "type"])
        self.assertEqual(rows, [])

    def test_run_step1_dry_run_skips_write(self):
        options = Step1Options(output_csv_path=self.output_csv, dry_run=True)
        store = MagicMock(spec=WordStore)
        store.fetch_all_words.return_value = self.words
        result_path = run_step1(options, word_store=store, repo=self.mock_repo)

        self.assertIsNone(result_path)
        self.assertFalse(self.output_csv.exists())
        # fetch_all_words is invoked before the dry_run branch — verifies the
        # contract that dry-run still materialises row count for its status message.
        store.fetch_all_words.assert_called_once()
        self.mock_repo.write_rows.assert_not_called()

    def test_dry_run_prints_sample_rows(self):
        # 3+ words: header line followed by exactly 3 sample data rows.
        words = [
            (3, "cherry", "fruit"),
            (1, "apple", "fruit"),
            (2, "banana", "fruit"),
            (4, "date", "fruit"),
        ]
        store = MagicMock(spec=WordStore)
        store.fetch_all_words.return_value = words
        options = Step1Options(output_csv_path=self.output_csv, dry_run=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result_path = run_step1(options, word_store=store, repo=self.mock_repo)

        self.assertIsNone(result_path)
        self.mock_repo.write_rows.assert_not_called()
        lines = buf.getvalue().splitlines()
        # First line is the existing count message, then header, then <=3 rows.
        self.assertIn("4 words", lines[0])
        header_line = ",".join(BASE_CSV_HEADERS)
        self.assertEqual(lines[1], header_line)
        sample_lines = lines[2:]
        self.assertEqual(len(sample_lines), 3)
        self.assertEqual(sample_lines[0], "1,apple,fruit")
        self.assertEqual(sample_lines[1], "2,banana,fruit")
        self.assertEqual(sample_lines[2], "3,cherry,fruit")
        self.assertNotIn("4,date,fruit", "\n".join(lines))

    def test_dry_run_fewer_than_three_rows_prints_all(self):
        # Fewer than 3 words: every row is printed, no padding.
        store = MagicMock(spec=WordStore)
        store.fetch_all_words.return_value = [(7, "fig", "fruit")]
        options = Step1Options(output_csv_path=self.output_csv, dry_run=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run_step1(options, word_store=store, repo=self.mock_repo)

        lines = buf.getvalue().splitlines()
        self.assertEqual(lines[1], ",".join(BASE_CSV_HEADERS))
        self.assertEqual(lines[2:], ["7,fig,fruit"])

    def test_dry_run_empty_prints_count_only(self):
        # Empty word list: only the count message — no header, no rows.
        store = MagicMock(spec=WordStore)
        store.fetch_all_words.return_value = []
        options = Step1Options(output_csv_path=self.output_csv, dry_run=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result_path = run_step1(options, word_store=store, repo=self.mock_repo)

        self.assertIsNone(result_path)
        lines = buf.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("0 words", lines[0])
        self.assertNotIn(",".join(BASE_CSV_HEADERS), buf.getvalue())

    def test_run_step1_single_word(self):
        # Minimal boundary: exactly one word — verifies sorted() with single-element
        # list and write_rows invocation at the lower bound of input cardinality.
        store = MagicMock(spec=WordStore)
        store.fetch_all_words.return_value = [(42, "zebra", "animal")]
        options = Step1Options(output_csv_path=self.output_csv)
        result_path = run_step1(options, word_store=store, repo=self.mock_repo)

        self.assertEqual(result_path, self.output_csv)
        args, _ = self.mock_repo.write_rows.call_args
        headers, rows = args[1], args[2]
        self.assertEqual(headers, ["word_id", "word", "type"])
        self.assertEqual(rows, [["42", "zebra", "animal"]])

    def test_run_step1_sorts_by_word_id_not_other(self):
        # Deliberately invert word ordering vs. word_id so sorting by any field
        # other than itemgetter(0) produces a clearly wrong row order.
        inverted_words = [
            (20, "apple", "fruit"),   # id=20 but alphabetically first
            (1,  "banana", "fruit"),   # id=1  but alphabetically second
            (5,  "cherry", "fruit"),
        ]
        store = MagicMock(spec=WordStore)
        store.fetch_all_words.return_value = inverted_words
        options = Step1Options(output_csv_path=self.output_csv)
        result_path = run_step1(options, word_store=store, repo=self.mock_repo)

        self.assertEqual(result_path, self.output_csv)
        args, _ = self.mock_repo.write_rows.call_args
        rows = args[2]
        # Failure-specific: if sorted by "word" or any other attr, the first row would be apple (alphabetical).
        # Only attrgetter("word_id") puts banana (id=1) first despite being alphabetically later.
        self.assertEqual(rows[0], ["1", "banana", "fruit"], msg="sort key must be word_id, not word/type/other")
        self.assertEqual(rows[1], ["5", "cherry", "fruit"])
        self.assertEqual(rows[2], ["20", "apple", "fruit"])
        # Monotonic ascending invariant — catches any ordering regression.
        word_ids = [int(r[0]) for r in rows]
        self.assertEqual(word_ids, sorted(word_ids), msg="words must be sorted by word_id ascending")

    def test_run_step1_sorts_by_word_id(self):
        # Multi-digit IDs: string sort would give 1,10,2,20; int sort gives 1,2,10,20.
        unsorted_words = [
            (20, "pear", "fruit"),
            (10, "grape", "fruit"),
            (2, "banana", "fruit"),
            (1, "apple", "fruit"),
        ]
        store = MagicMock(spec=WordStore)
        store.fetch_all_words.return_value = unsorted_words
        options = Step1Options(output_csv_path=self.output_csv)
        result_path = run_step1(options, word_store=store, repo=self.mock_repo)

        self.assertEqual(result_path, self.output_csv)
        args, _ = self.mock_repo.write_rows.call_args
        headers = args[1]
        rows = args[2]
        self.assertEqual(headers, ["word_id", "word", "type"])
        self.assertEqual(len(rows), 4)
        # Verify sorted by word_id ascending (attrgetter contract)
        self.assertEqual(rows[0], ["1", "apple", "fruit"])
        self.assertEqual(rows[1], ["2", "banana", "fruit"])
        self.assertEqual(rows[2], ["10", "grape", "fruit"])
        self.assertEqual(rows[3], ["20", "pear", "fruit"])
        # Explicit ascending invariant — catches any ordering regression, not just content coincidence.
        word_ids = [int(r[0]) for r in rows]
        self.assertEqual(word_ids, sorted(word_ids), msg="words must be sorted by word_id ascending")

    def test_run_step1_sorts_by_word_id_mixed_sign(self):
        # Mixed-sign IDs: negative/zero/positive. A string sort would put '-'
        # before digits (wrong ordering). Only int-sort via itemgetter(0) gives
        # the mathematically correct ascending order.
        mixed_words = [
            (1,   "zebra",  "animal"),  # id=1   positive
            (-5,  "alpha",  "letter"),  # id=-5  negative
            (0,   "middle", "symbol"),   # id=0   zero
        ]
        store = MagicMock(spec=WordStore)
        store.fetch_all_words.return_value = mixed_words
        options = Step1Options(output_csv_path=self.output_csv)
        result_path = run_step1(options, word_store=store, repo=self.mock_repo)

        self.assertEqual(result_path, self.output_csv)
        args, _ = self.mock_repo.write_rows.call_args
        rows = args[2]
        # Expected order by int-sort: -5, 0, 1
        self.assertEqual(rows[0], ["-5", "alpha", "letter"])
        self.assertEqual(rows[1], ["0", "middle", "symbol"])
        self.assertEqual(rows[2], ["1", "zebra", "animal"])
        # Monotonic ascending invariant — catches any ordering regression,
        # including string-based sort that would break on negative signs.
        word_ids = [int(r[0]) for r in rows]
        self.assertEqual(word_ids, sorted(word_ids), msg="words must be sorted by word_id ascending (mixed-sign)")


if __name__ == "__main__":
    unittest.main()
