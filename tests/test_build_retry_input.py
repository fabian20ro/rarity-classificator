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

    def test_build_retry_input_refuses_to_overwrite_existing_output(self):
        """Regression: pre-existing output CSV must raise FileExistsError.

        Previously a stale output file was silently overwritten — masking
        accidental reruns and silent data loss when the failed JSONL or base
        changed between runs. Now we refuse to overwrite so the user sees the
        collision on purpose instead of getting a different result than expected.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            failed.write_text('{"word_id": 1}\n', encoding="utf-8")
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["1", "test"]],
            )
            # Pre-create output file so it exists before build_retry_input runs
            out.write_text("stale,data\n", encoding="utf-8")

            with self.assertRaises(FileExistsError) as ctx:
                build_retry_input(
                    failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
                )
            self.assertIn("retry.csv", str(ctx.exception))

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

            # lines that carry no valid word_id — all silently skipped (missing key, None)
            rows = [
                {"word": "skip_me"},
                {},
                {"word_id": None},
            ]
            failed.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
            )
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

    def test_build_retry_input_rejects_non_dict_valid_json_records(self):
        """Regression: valid-JSON lines that are arrays or bare strings must raise.

        Previously these were silently dropped — an array record like `[3,"x"]`
        parses fine as JSON but is not a dict, so the parser skipped it without
        any signal. That produces empty output and masks producer-side schema
        drift (e.g. a bug in the upstream writer that starts emitting arrays).
        Now we raise ValueError so pipeline breakage surfaces immediately with
        actionable context about what shape was found.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            rows = [
                {"word_id": 3, "error": "ok"},
                [1, 2],             # array instead of dict — valid JSON, wrong shape
                ["bare_string"],    # bare string record — also wrong shape
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
            # Must identify the offending shape and content for debugging
            self.assertIn("Non-dict", exc_str)
            self.assertIn("list", exc_str)

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

    def test_build_retry_input_output_row_count_matches_return_value(self):
        """Regression: output CSV row count must exactly match the return value.

        Previously a bug could silently produce fewer rows than reported —
        e.g. dedup logic changes or header-write short-circuit without body
        would let count and actual I/O diverge. This assertion locks both sides.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            rows = [
                {"word_id": 2, "error": "x"},
                {"word_id": 4, "error": "y"},
                {"word_id": 2, "error": "dup"},
                {"word_id": 5, "error": "z"},
            ]
            failed.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
            )

            self.repo.write_rows(
                base,
                ["word_id", "word", "type"],
                [
                    ["1", "unu", "N"],
                    ["2", "doi", "N"],
                    ["3", "trei", "N"],
                    ["4", "patru", "N"],
                    ["5", "cinci", "N"],
                    ["6", "sase", "N"],  # not in failed — excluded
                ],
            )

            count = build_retry_input(
                failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
            )
            self.assertEqual(count, 3)

            table = self.repo.read_table(out)
            self.assertEqual(len(table.records), count)
            self.assertEqual(table.headers, ["word_id", "word", "type"])
            ids = [int(rec.values[0]) for rec in table.records]
            self.assertEqual(sorted(ids), [2, 4, 5])

    def test_build_retry_input_headers_preserved_when_no_matches(self):
        """Regression: when no word_ids match, output CSV must still carry base headers.

        Previously the empty-filters path could write an empty file without headers —
        breaking downstream consumers that expect a valid CSV schema even on zero rows.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            # word_ids 9,10 never appear in base (which has 1-3)
            rows = [{"word_id": 9}, {"word_id": 10}]
            failed.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
            )

            self.repo.write_rows(
                base,
                ["word_id", "word", "type"],
                [["1", "unu", "N"], ["2", "doi", "N"], ["3", "trei", "N"]],
            )

            count = build_retry_input(
                failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
            )
            self.assertEqual(count, 0)

            table = self.repo.read_table(out)
            # Headers must match the base CSV schema exactly — not be empty or partial.
            self.assertEqual(table.headers, ["word_id", "word", "type"])
            self.assertEqual(len(table.records), 0)

    def test_build_retry_input_dedup_preserves_first_occurrence(self):
        """Dedup must keep first occurrence, not last — preserves base CSV row order."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            # Failed JSONL contains word_id=2 (valid positive int).
            failed.write_text('{"word_id": 2}\n', encoding="utf-8")

            # Base CSV: word_id=2 appears twice. First occurrence must survive dedup.
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [
                    ["1", "first_one"],
                    ["2", "first_two"],   # first occurrence of word_id=2
                    ["3", "three"],
                    ["2", "second_two"],  # duplicate — must be dropped
                ],
            )

            count = build_retry_input(
                failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
            )
            self.assertEqual(count, 1)

            table = self.repo.read_table(out)
            ids = [int(rec.values[0]) for rec in table.records]
            words = [rec.values[1] for rec in table.records]
            # Exactly one row, first occurrence preserved
            self.assertEqual(ids, [2])
            self.assertEqual(words, ["first_two"])

    def test_build_retry_input_matches_failed_ids_against_base_records(self):
        """Regression: output must contain exactly the records whose word_id appears in failed JSONL.

        Previously a bug could skip valid matches or include non-matching rows —
        for example if the wanted-ids set and base scan used different normalization,
        one record would slip through unfiltered or a matching record would be dropped.
        This assertion locks both sides: count AND content must match exactly.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            rows = [
                {"word_id": 2, "error": "x"},
                {"word_id": 5, "error": "y"},
            ]
            failed.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
            )

            self.repo.write_rows(
                base,
                ["word_id", "word", "type"],
                [
                    ["1", "unu", "N"],
                    ["2", "doi", "N"],
                    ["3", "trei", "N"],
                    ["4", "patru", "N"],
                    ["5", "cinci", "N"],
                    ["6", "sase", "N"],  # not in failed — excluded
                ],
            )

            count = build_retry_input(
                failed_jsonl=failed, base_csv=base, output_csv=out, repo=self.repo
            )
            self.assertEqual(count, 2)

            table = self.repo.read_table(out)
            self.assertEqual(len(table.records), 2)
            ids = sorted(int(rec.values[0]) for rec in table.records)
            words = [rec.values[1] for rec in table.records]
            # Exactly the matched records, preserving base CSV order
            self.assertEqual(ids, [2, 5])
            self.assertIn("doi", words)
            self.assertIn("cinci", words)

    if __name__ == "__main__":
        unittest.main()
