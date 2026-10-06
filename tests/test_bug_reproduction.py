

import json
import tempfile
import unittest
from pathlib import Path

from classificator.csv_codec import CsvFormatError
from classificator.run_csv_repository import RunCsvRepository
from classificator.tools.build_retry_input import build_retry_input


class BugReproductionTest(unittest.TestCase):
    """Regression tests for previously-uncovered failure modes."""

    def setUp(self):
        self.repo = RunCsvRepository()

    def test_float_string_word_id_in_jsonl_raises_not_skipped(
        self,
    ):
        """Float-string word_ids (e.g. "3.0") must raise — not be silently skipped.

        Previously the JSONL parser accepted strings like "3.0" because `int()` on a
        decimal string raises ValueError and we caught that exception for silent skip.
        The base-CSV path on line 86 explicitly rejects this pattern, so the JSONL
        side must match to avoid inconsistent failure modes between input sources.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "failed.jsonl"
            base = root / "base.csv"
            out = root / "retry.csv"

            rows = [
                {"word_id": 2, "error": "ok"},
                {"word_id": "3.0"},           # float-string — must raise
                {"word_id": -1},              # negative — already raises
                {
                    "word_id": True,          # boolean — already raises
                    "error": "ok",
                },
            ]
            failed.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
            )
            self.repo.write_rows(
                base,
                ["word_id", "word"],
                [["1", "test"]],
            )

            with self.assertRaises(ValueError) as ctx:
                build_retry_input(
                    failed_jsonl=failed,
                    base_csv=base,
                    output_csv=out,
                    repo=self.repo,
                )
            exc_str = str(ctx.exception)
            # Must name the offending value so the operator can spot it in logs
            self.assertIn("3.0", exc_str)
            # Must be the documented JSONL-side boundary that rejects it, not an
            # unrelated check that happens to name the value (which would make
            # the JSONL/base failure modes diverge).
            self.assertIn("String word_id in failed JSONL", exc_str)

    def test_run_csv_load_rejects_confidence_out_of_range(self):
        """Confidence outside [0,1] must raise CsvFormatError — not be silently accepted.

        load_run_rows enforces the confidence range (run_csv_repository.py).
        An LLM outputting "1.5" would otherwise parse as a valid float and
        propagate into downstream confidence gates.
        """
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
                    ["1", "om", "N", "3", "uncertain", "1.5", "t", "m", "r"],
                ],
            )
            with self.assertRaisesRegex(
                CsvFormatError, r"confidence out of range at .*:2"
            ):
                self.repo.load_run_rows(path)

    def test_run_csv_load_rejects_confidence_below_zero(self):
        """Confidence below 0 must raise CsvFormatError — not be silently accepted.

        Pins the lower bound of the same range check the test above pins for the
        upper bound (1.5). An LLM emitting a negative confidence ("-0.1") would
        otherwise parse as a valid float and propagate into downstream gates.
        """
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
                    ["1", "om", "N", "3", "uncertain", "-0.1", "t", "m", "r"],
                ],
            )
            with self.assertRaisesRegex(
                CsvFormatError, r"confidence out of range at .*:2"
            ):
                self.repo.load_run_rows(path)
