"""Provider-neutral comparison: explicit fallback, severe loss and honest coverage."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.judge_comparison import compare_judge_csv
from tests.test_exact_form import write_csv
from tests.test_local_evidence import read


class JudgeComparisonTests(unittest.TestCase):
    def inputs(self, root):
        words = ["rar", "comun", "tehnic", "mediu"]
        gold = [5, 1, 4, 2]
        baseline = [4, 3, 4, 1]
        judge = [2, None, 3, 4]
        ref = write_csv(
            root / "reference.csv",
            [
                dict(
                    word_id=i,
                    word=w,
                    working_level=g,
                    reference_kind="initial_opaque_form_pos" if i == 1 else "audited",
                )
                for i, (w, g) in enumerate(zip(words, gold), 1)
            ],
        )
        base = write_csv(
            root / "baseline.csv",
            [
                dict(word_id=i, word=w, baseline_level=b, wordfreq="" if i < 3 else "0.001")
                for i, (w, b) in enumerate(zip(words, baseline), 1)
            ],
        )
        pred = write_csv(
            root / "predictions.csv",
            [
                dict(
                    word_id=i,
                    word=w,
                    status="failed" if p is None else "scored",
                    rarity_level="" if p is None else p,
                )
                for i, (w, p) in enumerate(zip(words, judge), 1)
            ],
        )
        evidence = write_csv(
            root / "evidence.csv",
            [
                dict(
                    word_id=i,
                    word=w,
                    evidence_json=json.dumps(
                        dict(
                            valid_pos=["N"],
                            senses=[] if i < 3 else [dict(definition="Definiție.")],
                            coverage="source_bounded_not_exhaustive",
                        )
                    ),
                )
                for i, w in enumerate(words, 1)
            ],
        )
        folds = write_csv(
            root / "folds.csv", [dict(word_id=i, group=f"g{i}", fold=i % 2) for i in range(1, 5)]
        )
        return pred, ref, base, evidence, folds

    def test_reports_complete_coverage_fallback_and_severity_beyond_tolerance(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            result = compare_judge_csv(*self.inputs(root), root / "out", review_budget=1)
            self.assertEqual(
                result["coverage"],
                dict(total=4, native_scored=3, native_failed=1, fallback=1, final_scored=4),
            )
            base = result["metrics"]["baseline"]["all"]
            judge = result["metrics"]["judge_with_fallback"]["all"]
            self.assertEqual((base["severe"], base["excess_error_total"], base["mae"]), (1, 1, 1))
            self.assertEqual(
                (judge["severe"], judge["excess_error_total"], judge["mae"]), (3, 4, 2)
            )
            self.assertEqual(judge["error_histogram"], {"0": 0, "1": 1, "2": 2, "3": 1, "4": 0})
            self.assertEqual(result["metrics"]["judge_with_fallback"]["true4_or5"]["severe"], 1)
            rows = read(root / "out/comparison.csv")
            self.assertEqual(rows[1]["route"], "baseline_after_failure")
            self.assertEqual(rows[1]["judge_level"], "")
            self.assertFalse(result["promotion"]["scorer_gate_pass"])

    def test_refuses_incomplete_duplicate_or_mismatched_comparison_inputs(self):
        for defect in (
            "missing",
            "duplicate",
            "spelling",
            "level",
            "failed_with_score",
            "fold_split",
            "baseline_reference",
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as temp:
                root = Path(temp)
                args = self.inputs(root)
                if defect == "fold_split":
                    rows = read(args[4])
                    rows[1]["group"] = rows[0]["group"]
                    write_csv(args[4], rows)
                elif defect == "baseline_reference":
                    rows = read(args[2])
                    for r in rows:
                        r["human_level"] = "3"
                    write_csv(args[2], rows)
                else:
                    rows = read(args[0])
                    if defect == "missing":
                        rows.pop()
                    elif defect == "duplicate":
                        rows.append(rows[0])
                    elif defect == "spelling":
                        rows[0]["word"] = "altă"
                    elif defect == "level":
                        rows[0]["rarity_level"] = "6"
                    else:
                        rows[1]["rarity_level"] = "3"
                    write_csv(args[0], rows)
                with self.assertRaises(ValueError):
                    compare_judge_csv(*args, root / "out")
                self.assertFalse((root / "out").exists())

    def test_diagnostic_selection_uses_disagreement_not_human_labels(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            first = compare_judge_csv(*args, root / "first", review_budget=1)
            assisted = first["diagnostic"]["primary"]["judge_assisted"]
            self.assertEqual(assisted["selected_ids"], ["4"])
            self.assertEqual(
                (assisted["recovered_baseline_severe"], assisted["false_alarms"]), (0, 1)
            )
            labels = read(args[1])
            for row in labels:
                row["working_level"] = "3"
            write_csv(args[1], labels)
            second = compare_judge_csv(*args, root / "second", review_budget=1)
            self.assertEqual(
                second["diagnostic"]["primary"]["judge_assisted"]["selected_ids"], ["4"]
            )
            self.assertEqual(
                first["diagnostic"]["primary"]["evidence_only"]["selected_ids"],
                second["diagnostic"]["primary"]["evidence_only"]["selected_ids"],
            )

    def test_distinguishes_tolerated_four_five_confusion_from_large_rare_errors(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            predictions = read(args[0])
            predictions[0]["rarity_level"] = "4"
            predictions[2]["rarity_level"] = "5"
            write_csv(args[0], predictions)
            result = compare_judge_csv(*args, root / "out")
            rare = result["metrics"]["judge_with_fallback"]["true4_or5"]
            self.assertEqual(rare["severe"], 0)
            self.assertEqual(rare["within_one"], 2)
            self.assertEqual(rare["per_level"]["5"]["support"], 1)
            self.assertEqual(rare["per_level"]["5"]["correct"], 0)
            self.assertEqual(rare["per_level"]["5"]["predicted"], 1)

    def test_overall_improvement_cannot_hide_more_costly_rare_word_errors(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            baseline = read(args[2])
            predictions = read(args[0])
            for row, level in zip(baseline, [3, 4, 4, 4]):
                row["baseline_level"] = str(level)
            for row, level in zip(predictions, [1, 1, 4, 2]):
                row.update(status="scored", rarity_level=str(level))
            write_csv(args[2], baseline)
            write_csv(args[0], predictions)
            result = compare_judge_csv(*args, root / "out")
            self.assertLess(
                result["metrics"]["judge_with_fallback"]["all"]["severe"],
                result["metrics"]["baseline"]["all"]["severe"],
            )
            self.assertFalse(result["promotion"]["scorer_gate_pass"])
