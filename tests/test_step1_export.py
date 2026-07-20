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

    def test_run_step1_success(self):
        options = Step1Options(output_csv_path=self.output_csv)
        result_path = run_step1(options, word_store=self.mock_word_store, repo=self.mock_repo)

        self.assertEqual(result_path, self.output_csv)
        self.mock_repo.write_rows.assert_called_once()
        # Check headers and data
        args, _ = self.mock_repo.write_rows.call_args
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

    def test_run_step1_sorts_by_word_id(self):
        # Multi-digit IDs: string sort would give 1,10,2,20; int sort gives 1,2,10,20.
        # This makes the check failure-specific to attrgetter("word_id").
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


if __name__ == "__main__":
    unittest.main()
