import json
import tempfile
import unittest
from pathlib import Path

from classificator.run_csv_repository import RunCsvRepository
from classificator.tools.build_retry_input import build_retry_input


class BuildRetryInputTest(unittest.TestCase):
    def setUp(self):
        self.repo = RunCsvRepository()

    def test_build_retry_input_selects_failed_word_ids(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            rows = [
                {"word_id": 2, "error": "x"},
                {"word_id": 4, "error": "y"},
                {"word_id": 2, "error": "dup"},
                {"word_id": "bad", "error": "bad"},
            ]
            failed.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

            self.repo.write_rows(
                base,
                ["word_id", "word", "type"],
                [
                    ["1", "unu", "N"],
                    ["2", "doi", "N"],
                    ["3", "trei", "N"],
                    ["4", "patru", "N"],
                ],
            )

            count = build_retry_input(failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo)
            self.assertEqual(count, 2)

            table = self.repo.read_table(out)
            self.assertEqual(table.headers, ["word_id", "word", "type"])
            ids = [int(rec.values[0]) for rec in table.records]
            self.assertEqual(ids, [2, 4])

    def test_build_retry_input_handles_none_in_base(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            failed.write_text('{"word_id": 1}\n', encoding="utf-8")
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [[None, "none_test"]],
            )

            count = build_retry_input(failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo)
            self.assertEqual(count, 0)

    def test_build_retry_input_raises_on_directory_instead_of_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed_dir"
            failed.mkdir()
            base = root / "base.csv"
            out = root / "retry.csv"

            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["1", "test"]],
            )

            with self.assertRaises(IsADirectoryError):
                build_retry_input(failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo)

    def test_build_retry_input_raises_on_output_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out_dir = root / "output_dir"
            out_dir.mkdir()

            failed.write_text('{"word_id": 1}\n', encoding="utf-8")
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["1", "test"]],
            )

            with self.assertRaises(IsADirectoryError):
                build_retry_input(failed_jsonl=failed, base_csv=base, output_csv=out_dir, repo=self.repo)

    def test_build_retry_input_creates_output_dir_when_empty(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out_dir = root / "new_subdir"
            out = out_dir / "retry.csv"

            failed.write_text("", encoding="utf-8")
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["1", "test"]],
            )

            count = build_retry_input(failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo)
            self.assertEqual(count, 0)
            self.assertTrue(out.exists())

    def test_build_retry_input_empty_failed_file_produces_headers_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            # zero-byte file — no content, no valid word_ids extracted
            failed.write_bytes(b"")
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["1", "test"]],
            )

            count = build_retry_input(failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo)
            self.assertEqual(count, 0)
            table = self.repo.read_table(out)
            # headers must survive so downstream consumers do not break
            self.assertEqual(table.headers, ["word_id", "word"])
            self.assertEqual(len(table.records), 0)

    def test_build_retry_input_all_invalid_lines_yields_zero_rows(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            # lines that look like JSON but carry no valid word_id
            rows = [
                {"word": "skip_me"},
                {},
                "not-json",
                {"word_id": None},
                {"word_id": "abc"},
            ]
            failed.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["1", "test"]],
            )

            count = build_retry_input(failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo)
            self.assertEqual(count, 0)
            table = self.repo.read_table(out)
            self.assertEqual(table.headers, ["word_id", "word"])

    def test_build_retry_input_rejects_float_word_ids(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            rows = [
                {"word_id": 7, "error": "ok"},
                {"word_id": -3.14},
                ["7", "seven"],
            ]
            failed.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["1", "test"]],
            )

            with self.assertRaises(ValueError):
                build_retry_input(
                    failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
                )

    def test_build_retry_input_rejects_non_positive_word_ids(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            rows = [
                {"word_id": 0},
                {"word_id": -1},
                {"word_id": 5, "error": "ok"},
            ]
            failed.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["1", "test"]],
            )

            with self.assertRaises(ValueError):
                build_retry_input(
                    failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
                )

    def test_build_retry_input_raises_when_base_csv_lacks_word_id_header(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            failed.write_text('{"word_id": 1}\n', encoding="utf-8")
            self.repo.write_rows(
                base,
                ["id", "word"],
                [["1", "test"]],
            )

            with self.assertRaises(ValueError) as ctx:
                build_retry_input(
                    failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
                )
            self.assertIn("word_id", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
