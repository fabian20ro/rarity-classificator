import unittest
from pathlib import Path
from unittest.mock import MagicMock
from src.classificator.steps.step1_export import run_step1, Step1Options
from src.classificator.run_csv_repository import RunCsvRepository
from src.classificator.word_store import WordStore
from dataclasses import dataclass

@dataclass
class MockWord:
    word_id: int
    word: str
    type: str

class MockWordStore(WordStore):
    def __init__(self, words):
        self.words = words
    def fetch_all_words(self):
        return self.words

class TestStep1Export(unittest.TestCase):
    def setUp(self):
        self.output_csv = Path("test_output.csv")
        if self.output_csv.exists():
            self.output_csv.unlink()
        
        self.mock_repo = MagicMock(spec=RunCsvRepository)
        
        self.words = [
            MockWord(1, "apple", "fruit"),
            MockWord(2, "banana", "fruit"),
        ]
        self.mock_word_store = MockWordStore(self.words)

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
        with self.assertRaises(PermissionError, msg="write error must propagate"):
            run_step1(options, word_store=self.mock_word_store, repo=self.mock_repo)
        # write_rows was invoked once with correct args before failing — fetch succeeded, data reached write phase
        self.mock_repo.write_rows.assert_called_once()
        args, _ = self.mock_repo.write_rows.call_args
        self.assertEqual(args[0], self.output_csv)
    def test_run_step1_success(self):
        options = Step1Options(output_csv_path=self.output_csv)
        result_path = run_step1(options, word_store=self.mock_word_store, repo=self.mock_repo)

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
        empty_store = MockWordStore([])
        options = Step1Options(output_csv_path=self.output_csv)
        result_path = run_step1(options, word_store=empty_store, repo=self.mock_repo)

        self.assertEqual(result_path, self.output_csv)
        args, _ = self.mock_repo.write_rows.call_args
        headers, rows = args[1], args[2]
        self.assertEqual(headers, ["word_id", "word", "type"])
        self.assertEqual(rows, [])

    def test_run_step1_dry_run_skips_write(self):
        options = Step1Options(output_csv_path=self.output_csv, dry_run=True)
        result_path = run_step1(options, word_store=self.mock_word_store, repo=self.mock_repo)

        self.assertIsNone(result_path)
        self.assertFalse(self.output_csv.exists())
        self.mock_repo.write_rows.assert_not_called()

    def test_run_step1_sorts_by_word_id_not_other(self):
        # Deliberately invert word ordering vs. word_id so sorting by any field
        # other than attrgetter("word_id") produces a clearly wrong row order.
        inverted_words = [
            MockWord(20, "apple", "fruit"),   # id=20 but alphabetically first
            MockWord(1,  "banana", "fruit"),   # id=1  but alphabetically second
            MockWord(5,  "cherry", "fruit"),
        ]
        store = MockWordStore(inverted_words)
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
            MockWord(20, "pear", "fruit"),
            MockWord(10, "grape", "fruit"),
            MockWord(2, "banana", "fruit"),
            MockWord(1, "apple", "fruit"),
        ]
        store = MockWordStore(unsorted_words)
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


if __name__ == "__main__":
    unittest.main()
