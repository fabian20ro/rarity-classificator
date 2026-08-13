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

    def test_quality_audit_zero_jaccard(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            reference = root / "reference.csv"
            headers = ["word_id", "word", "type", "final_level"]
            cand_rows = [["1", "om", "N", "1"], ["2", "casă", "N", "1"]]
            ref_rows = [["1", "uncommon", "A", "5"], ["2", "rarity", "A", "5"]]
            
            self.repo.write_rows(candidate, headers, cand_rows)
            self.repo.write_rows(reference, headers, ref_rows)

            result = run_quality_audit(
                candidate_csv=candidate,
                reference_csv=reference,
                repo=self.repo,
            )
            
            self.assertTrue(result.passed)
            self.assertEqual(result.l1_jaccard, 0.0)
            self.assertEqual(result.l1_intersection, 0)
            self.assertEqual(result.l1_candidate_size, 2)
            self.assertEqual(result.l1_reference_size, 0)

    def test_invalid_level_below_one_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            headers = ["word_id", "word", "type", "final_level"]
            self._write_csv(candidate, headers, [["1", "om", "N", "0"]])

            with self.assertRaises(ValueError):
                run_quality_audit(
                    candidate_csv=candidate,
                    repo=self.repo,
                )

    def test_invalid_level_above_five_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            headers = ["word_id", "word", "type", "final_level"]
            self._write_csv(candidate, headers, [["1", "om", "N", "6"]])

            with self.assertRaises(ValueError):
                run_quality_audit(
                    candidate_csv=candidate,
                    repo=self.repo,
                )

    def test_non_numeric_word_id_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            headers = ["word_id", "word", "type", "final_level"]
            self._write_csv(candidate, headers, [["abc", "om", "N", "1"]])

            with self.assertRaises(ValueError) as ctx:
                run_quality_audit(
                    candidate_csv=candidate,
                    repo=self.repo,
                )
            msg = str(ctx.exception)
            self.assertIn("word_id", msg)

    def test_missing_level_column_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            headers = ["word_id", "word", "type"]
            self._write_csv(candidate, headers, [["1", "om", "N"]])

            with self.assertRaises(ValueError):
                run_quality_audit(
                    candidate_csv=candidate,
                    repo=self.repo,
                )

    def test_rarity_level_column_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            headers = ["word_id", "word", "type", "rarity_level"]
            cand_rows = [
                ["1", "om", "N", "1"],
                ["2", "casă", "N", "3"],
                ["3", "rarissim", "A", "5"],
            ]
            self._write_csv(candidate, headers, cand_rows)

            result = run_quality_audit(
                candidate_csv=candidate,
                repo=self.repo,
            )
            self.assertTrue(result.passed)
            self.assertEqual(result.level_column, "rarity_level")
            self.assertEqual(result.total_rows, 3)
            self.assertEqual(result.distribution[1], 1)
            self.assertEqual(result.distribution[3], 1)
            self.assertEqual(result.distribution[5], 1)

    def test_blank_row_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            headers = ["word_id", "word", "type", "final_level"]
            cand_rows = [
                ["1", "om", "N", "1"],
                ["", "", "", ""],
                ["2", "casă", "N", "2"],
            ]
            self._write_csv(candidate, headers, cand_rows)

            result = run_quality_audit(
                candidate_csv=candidate,
                repo=self.repo,
            )
            self.assertTrue(result.passed)
            self.assertEqual(result.total_rows, 2)
            self.assertEqual(result.distribution[1], 1)
            self.assertEqual(result.distribution[2], 1)

    def test_ambiguous_level_columns_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"

            headers = ["word_id", "word", "type", "final_level", "rarity_level"]
            cand_rows = [
                ["1", "om", "N", "1", ""],
                ["2", "casă", "N", "3", ""],
            ]
            self._write_csv(candidate, headers, cand_rows)

            with self.assertRaises(ValueError) as ctx:
                run_quality_audit(
                    candidate_csv=candidate,
                    repo=self.repo,
                )
            self.assertIn("ambiguous level columns", str(ctx.exception))
            self.assertIn("final_level", str(ctx.exception))
            self.assertIn("rarity_level", str(ctx.exception))

    def test_median_level_column_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            headers = ["word_id", "word", "type", "median_level"]
            cand_rows = [
                ["1", "om", "N", "1"],
                ["2", "casă", "N", "3"],
                ["3", "rarissim", "A", "5"],
            ]
            self._write_csv(candidate, headers, cand_rows)

            result = run_quality_audit(
                candidate_csv=candidate,
                repo=self.repo,
            )
            self.assertTrue(result.passed)
            self.assertEqual(result.level_column, "median_level")
            self.assertEqual(result.total_rows, 3)
            self.assertEqual(result.distribution[1], 1)
            self.assertEqual(result.distribution[3], 1)
            self.assertEqual(result.distribution[5], 1)

    def test_case_insensitive_l1_anchor_matching(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            reference = root / "reference.csv"
            anchor = root / "anchor.txt"

            headers = ["word_id", "word", "type", "final_level"]
            cand_rows = [
                ["1", "OM", "N", "1"],
                ["2", "Casă", "N", "1"],
            ]
            ref_rows = [
                ["3", "om", "N", "1"],
                ["4", "casă", "N", "1"],
            ]

            self._write_csv(candidate, headers, cand_rows)
            self._write_csv(reference, headers, ref_rows)
            anchor.write_text("om\ncasă\n", encoding="utf-8")

            result = run_quality_audit(
                candidate_csv=candidate,
                reference_csv=reference,
                anchor_l1_file=anchor,
                repo=self.repo,
            )
            # Different word_ids → Jaccard 0; but case-insensitive L1 match is perfect.
            self.assertEqual(result.l1_jaccard, 0.0)
            self.assertEqual(result.anchor_precision, 1.0)
            self.assertEqual(result.anchor_recall, 1.0)

    def test_anchor_with_only_whitespace_raises_value_error(self):
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
            anchor.write_text("   \n\t\n  ", encoding="utf-8")

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

    def test_missing_anchor_file_propagates_filenotfounderror(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            anchor = root / "anchor.txt"

            headers = ["word_id", "word", "type", "final_level"]
            cand_rows = [["1", "om", "N", "1"]]
            self._write_csv(candidate, headers, cand_rows)

            with self.assertRaises(FileNotFoundError):
                run_quality_audit(
                    candidate_csv=candidate,
                    anchor_l1_file=anchor / "does_not_exist.txt",
                    repo=self.repo,
                )

    def test_non_l1_words_excluded_from_anchor_matching(self):
        """Non-L1 words in anchors must not affect precision/recall — only L1 rows count."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"
            reference = root / "reference.csv"
            anchor = root / "anchor.txt"

            headers = ["word_id", "word", "type", "final_level"]
            cand_rows = [
                # L1 words (level 1) — these participate in anchor matching
                ["1", "mâncare", "N", "1"],
                ["2", "casă", "N", "1"],
                # Non-L1 words (level 3) — must NOT affect anchor precision/recall
                ["3", "obscurantism", "N", "3"],
                ["4", "quiddity", "A", "5"],
            ]
            ref_rows = [
                ["10", "mâncare", "N", "2"],
                ["11", "casă", "N", "2"],
                ["12", "obscurantism", "N", "3"],
                ["13", "quiddity", "A", "5"],
            ]

            self._write_csv(candidate, headers, cand_rows)
            self._write_csv(reference, headers, ref_rows)
            # Anchor file contains both L1 and non-L1 words.
            # Anchor intersection uses candidate["l1_words"] (line 58 of quality_audit.py),
            # so only "mâncare" and "casă" participate in the match.
            anchor.write_text("mâncare\ncasă\nobscurantism\nquiddity", encoding="utf-8")

            result = run_quality_audit(
                candidate_csv=candidate,
                reference_csv=reference,
                anchor_l1_file=anchor,
                repo=self.repo,
            )

            # Jaccard uses l1_word_ids (int IDs) — different word_ids → 0.
            self.assertEqual(result.l1_jaccard, 0.0)
            self.assertEqual(result.l1_intersection, 0)

            # Anchor matching: candidate["l1_words"] = {"mâncare", "casă"}
            # anchor words = {"mâncare", "casă", "obscurantism", "quiddity"}
            # intersection = {"mâncare", "casă"}, size 2
            # precision = 2 / len(candidate["l1_words"]) = 2 / 2 = 1.0
            self.assertEqual(result.anchor_precision, 1.0)
            # recall = 2 / len(anchors) = 2 / 4 = 0.5
            self.assertAlmostEqual(result.anchor_recall, 0.5)

    def test_distribution_counts_exact_for_multi_level_dataset(self):
        """Distribution dict must count each level precisely; total_rows excludes blanks."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"

            headers = ["word_id", "word", "type", "final_level"]
            cand_rows = [
                # 3 words at level 1, 2 at level 2, 1 at level 3, none at 4 or 5.
                ["1", "om", "N", "1"],
                ["2", "casă", "N", "1"],
                ["3", "apă", "N", "1"],
                ["4", "muncă", "A", "2"],
                ["5", "timp", "N", "2"],
                ["6", "rarissim", "A", "3"],
            ]
            self._write_csv(candidate, headers, cand_rows)

            result = run_quality_audit(
                candidate_csv=candidate,
                repo=self.repo,
            )

            self.assertTrue(result.passed)
            # total_rows must count all non-blank rows exactly.
            self.assertEqual(result.total_rows, 6)
            # Distribution dict must be exact for every level.
            expected = {1: 3, 2: 2, 3: 1, 4: 0, 5: 0}
            self.assertEqual(result.distribution, expected)

    def test_non_numeric_level_value_raises_value_error(self):
        """A non-numeric value in the level column must raise ValueError during audit."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / "candidate.csv"

            headers = ["word_id", "word", "type", "final_level"]
            self._write_csv(
                candidate,
                headers,
                [["1", "om", "N", "abc"]],
            )

            with self.assertRaises(ValueError):
                run_quality_audit(
                    candidate_csv=candidate,
                    repo=self.repo,
                )

    def test_l1_words_excludes_empty_word_from_anchor_matching(self):
        """An empty word at level 1 must not participate in anchor intersection."""
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
            ref_rows = [["4", "om", "N", "1"], ["5", "casă", "N", "1"]]

            self._write_csv(candidate, headers, cand_rows)
            self._write_csv(reference, headers, ref_rows)
            # Anchor contains only one valid L1 word — the empty entry must be ignored.
            anchor.write_text("om\n", encoding="utf-8")

            result = run_quality_audit(
                candidate_csv=candidate,
                reference_csv=reference,
                anchor_l1_file=anchor,
                repo=self.repo,
            )

            # Candidate l1_words = {"om", "casă"} (empty string excluded by line 124 guard).
            # Anchor words = {"om"}.
            self.assertEqual(result.l1_candidate_size, 2)
            # precision = |{om} ∩ {om, casă}| / |{om, casă}| = 1/2.
            self.assertAlmostEqual(result.anchor_precision, 0.5)
            # recall = |{om} ∩ {om, casă}| / |{"om"}| = 1/1.
            self.assertEqual(result.anchor_recall, 1.0)


if __name__ == "__main__":
    unittest.main()
