import tempfile
import unittest
from pathlib import Path

from classificator.run_csv_repository import RunCsvRepository
from classificator.tools.quality_audit import run_quality_audit


class QualityAuditTest(unittest.TestCase):
    def setUp(self):
        self.repo = RunCsvRepository()

    def _write_csv(self, path: Path, headers: list[str], rows: list[list[str]]):
        self.repo.write_rows(path, headers, rows)

    def test_quality_audit_computes_and_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            reference = root / "reference.csv"
            anchor = root / "anchor.txt"

            headers = ["word_id", "word", "type", "final_level"]
            cand_rows = [
                ["1", "om", "N", "1"],
                ["2", "casă", "N", "1"],
                ["3", "rarissim", "A", "5"],
            ]
            ref_rows = [
                ["1", "om", "N", "1"],
                ["2", "casă", "N", "2"],
                ["3", "rarissim", "A", "5"],
            ]

            self._write_csv(candidate, headers, cand_rows)
            self._write_csv(reference, headers, ref_rows)
            anchor.write_text("om\ncasă\n", encoding="utf-8")

            result = run_quality_audit(
                candidate_csv=candidate,
                reference_csv=reference,
                anchor_l1_file=anchor,
                min_l1_jaccard=0.1,
                min_anchor_l1_precision=0.4,
                min_anchor_l1_recall=0.4,
                repo=self.repo,
            )
            self.assertTrue(result.passed)
            self.assertIsNotNone(result.l1_jaccard)
            self.assertIsNotNone(result.anchor_precision)
            self.assertIsNotNone(result.anchor_recall)

    def test_empty_word_in_l1_does_not_add_to_l1_word_ids(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            reference = root / "reference.csv"
            anchor = root / "anchor.txt"

            headers = ["word_id", "word", "type", "final_level"]
            cand_rows = [
                ["1", "om", "N", "1"],
                ["2", "", "N", "1"],
                ["3", "casă", "N", "1"],
            ]
            ref_rows = [
                ["1", "om", "N", "1"],
                ["2", "casă", "N", "1"],
            ]
            self._write_csv(candidate, headers, cand_rows)
            self._write_csv(reference, headers, ref_rows)
            anchor.write_text("om\ncasă\n", encoding="utf-8")

            result = run_quality_audit(
                candidate_csv=candidate,
                reference_csv=reference,
                anchor_l1_file=anchor,
                min_l1_jaccard=0.1,
                min_anchor_l1_precision=0.4,
                min_anchor_l1_recall=0.4,
                repo=self.repo,
            )
            self.assertTrue(result.passed)
            self.assertEqual(result.l1_candidate_size, 2)
            self.assertEqual(result.l1_reference_size, 2)

    def test_empty_anchor_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            reference = root / "reference.csv"
            anchor = root / "anchor.txt"

            headers = ["word_id", "word", "type", "final_level"]
            cand_rows = [["1", "om", "N", "1"]]
            ref_rows = [["1", "om", "N", "1"]]
            self._write_csv(candidate, headers, cand_rows)
            self._write_csv(reference, headers, ref_rows)
            anchor.write_text("", encoding="utf-8")

            with self.assertRaises(ValueError):
                run_quality_audit(
                    candidate_csv=candidate,
                    reference_csv=reference,
                    anchor_l1_file=anchor,
                    min_l1_jaccard=0.1,
                    min_anchor_l1_precision=0.4,
                    min_anchor_l1_recall=0.4,
                    repo=self.repo,
                )

    def test_anchor_with_only_comments_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            reference = root / "reference.csv"
            anchor = root / "anchor.txt"

            headers = ["word_id", "word", "type", "final_level"]
            cand_rows = [["1", "om", "N", "1"]]
            ref_rows = [["1", "om", "N", "1"]]
            self._write_csv(candidate, headers, cand_rows)
            self._write_csv(reference, headers, ref_rows)
            anchor.write_text("# This is a comment\n\n# Another one", encoding="utf-8")

            with self.assertRaises(ValueError):
                run_quality_audit(
                    candidate_csv=candidate,
                    reference_csv=reference,
                    anchor_l1_file=anchor,
                    min_l1_jaccard=0.1,
                    min_anchor_l1_precision=0.4,
                    min_anchor_l1_recall=0.4,
                    repo=self.repo,
                )

    def test_quality_gate_fails_on_thresholds(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            reference = root / "reference.csv"
            anchor = root / "anchor.txt"

            headers = ["word_id", "word", "type", "final_level"]
            self._write_csv(
                candidate,
                headers,
                [["1", "rar", "N", "1"], ["2", "obscur", "A", "1"], ["3", "uzual", "A", "5"]],
            )
            self._write_csv(
                reference,
                headers,
                [["1", "uzual", "N", "1"], ["2", "comun", "A", "1"], ["3", "rar", "A", "5"]],
            )
            anchor.write_text("uzual\ncomun\n", encoding="utf-8")

            result = run_quality_audit(
                candidate_csv=candidate,
                reference_csv=reference,
                anchor_l1_file=anchor,
                min_l1_jaccard=0.9,
                min_anchor_l1_precision=0.9,
                min_anchor_l1_recall=0.9,
                repo=self.repo,
            )
            self.assertFalse(result.passed)
            self.assertGreaterEqual(len(result.failures), 1)


if __name__ == "__main__":
    unittest.main()
