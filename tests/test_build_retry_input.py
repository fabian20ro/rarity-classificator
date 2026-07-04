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

    def test_build_retry_input_deduplicates_base_word_ids(self):
        """Regression: duplicate word_id in base CSV must not produce duplicates in output."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            failed.write_text('{"word_id": 2}\n', encoding="utf-8")
            self.repo.write_rows(
                base,
                ["word_id", "word", "type"],
                [
                    ["1", "one", "N"],
                    ["2", "two_a", "N"],
                    ["2", "two_b", "N"],  # duplicate word_id=2
                    ["3", "three", "N"],
                ],
            )

            count = build_retry_input(
                failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
            )
            self.assertEqual(count, 1)

            table = self.repo.read_table(out)
            ids = [int(rec.values[0]) for rec in table.records]
            self.assertEqual(ids, [2])

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

    def test_build_retry_input_rejects_float_like_base_word_ids(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            failed.write_text('{"word_id": 1}\n', encoding="utf-8")
            # Float-like strings in base CSV (simulates Excel-imported integer column)
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["1.0", "one"], ["2.0", "two"]],
            )

            with self.assertRaises(ValueError):
                build_retry_input(
                    failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
                )

    def test_build_retry_input_includes_record_number_on_invalid_base_word_id(self):
        """Regression: invalid word_id in base CSV must include record number."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            failed.write_text('{"word_id": 1}\n', encoding="utf-8")
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["abc", "one"]],
            )

            with self.assertRaises(ValueError) as ctx:
                build_retry_input(
                    failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
                )
            self.assertIn("record 1", str(ctx.exception))
            self.assertIn("'abc'", str(ctx.exception))

    def test_build_retry_input_rejects_boolean_word_ids(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            rows = [
                {"word_id": 1, "error": "ok"},
                {"word_id": True},
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

    def test_build_retry_input_no_matching_ids_writes_headers_only(self):
        """Regression: when failed JSONL ids are absent from base CSV, output must still be valid."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            # word_ids 99 and 100 never appear in base (which has 1,2,3)
            rows = [
                {"word_id": 99},
                {"word_id": 100},
            ]
            failed.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
            )
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["1", "one"], ["2", "two"], ["3", "three"]],
            )

            count = build_retry_input(
                failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
            )
            self.assertEqual(count, 0)
            table = self.repo.read_table(out)
            self.assertEqual(table.headers, ["word_id", "word"])
            self.assertEqual(len(table.records), 0)

    def test_build_retry_input_raises_on_structurally_corrupted_word_ids(self):
        """Regression: list/dict word_id values must raise, not be silently dropped.

        Previously these were skipped at the JSONL parse stage, producing empty output
        that masked upstream data corruption. Now we fail fast with actionable context.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            rows = [
                {"word_id": 3, "error": "ok"},
                {"word_id": [1, 2]},       # list instead of scalar
                {"word_id": {"nested": 1}}, # dict instead of scalar
                {
                    "word_id": None,        # missing/None — still skipped silently (existing contract)
                    "error": "ok",
                },
            ]
            failed.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
            )
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["1", "one"], ["2", "two"]],
            )

            with self.assertRaises(ValueError) as ctx:
                build_retry_input(
                    failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
                )
            exc_str = str(ctx.exception)
            # Must identify the offending type and content for debugging
            self.assertIn("Unsupported", exc_str)
            self.assertIn("[1, 2]", exc_str)

    def test_build_retry_input_raises_when_files_missing(self):
        """Regression: missing input paths must raise FileNotFoundError with path in message."""
        root = Path("/tmp/word_rarity_test_no_access")

        with self.assertRaises(FileNotFoundError) as ctx:
            build_retry_input(
                failed_jsonl=root / "does_not_exist.jsonl",
                base_csv=root / "base.csv",
                output_csv=Path("/tmp/out.csv"),
                repo=self.repo,
            )
        self.assertIn("does_not_exist.jsonl", str(ctx.exception))

    def test_build_retry_input_dedup_uses_word_id_column_not_position_zero(self):
        """Regression: dedup must use the word_id column index, not row[0].

        When word_id is not column 0 (e.g. headers reordered), the previous code
        crashed with ValueError because it tried int(row[0]) on a non-integer field.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            failed.write_text(
                json.dumps({"word_id": 2}) + "\n", encoding="utf-8"
            )
            # word_id is the LAST column, not the first — simulates reordered headers
            self.repo.write_rows(
                base,
                ["word", "type", "word_id"],
                [
                    ["one", "N", "1"],
                    ["two_a", "N", "2"],
                    ["two_b", "N", "2"],  # duplicate word_id=2
                    ["three", "N", "3"],
                ],
            )

            count = build_retry_input(
                failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
            )
            self.assertEqual(count, 1)

            table = self.repo.read_table(out)
            ids = [int(rec.values[-1]) for rec in table.records]
            self.assertEqual(ids, [2])

    if __name__ == "__main__":
        unittest.main()


if __name__ == "__main__":
    unittest.main()
