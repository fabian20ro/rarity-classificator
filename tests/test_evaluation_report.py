import csv
import tempfile
import unittest
from pathlib import Path

from classificator.evaluation.report import evaluate_predictions


class EvaluationReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.labels = self.root / "labels.csv"
        self.predictions = self.root / "predictions.csv"

    def write_csv(self, path, columns, rows):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            writer.writerows(rows)

    def write_labels(self, rows):
        self.write_csv(self.labels, ["word_id", "level", "group", "split"], rows)

    def write_predictions(self, rows, path=None, probabilities=False):
        columns = ["word_id", "status", "rarity_level"]
        if probabilities:
            columns += [f"p_L{level}" for level in range(1, 6)]
        self.write_csv(path or self.predictions, columns, rows)

    def test_missing_predictions_remain_in_recall_and_f1_denominators(self):
        self.write_labels(
            [
                [1, 1, "om", "test"],
                [2, 2, "casa", "test"],
                [3, 3, "albie", "test"],
                [4, 4, "regional", "test"],
                [5, 5, "arhaic", "test"],
                [6, 5, "arhaic", "test"],
            ]
        )
        self.write_predictions(
            [
                [1, "scored", 1],
                [2, "scored", 1],
                [3, "failed", ""],
                [4, "scored", 5],
                [5, "scored", 2],
            ]
        )

        report = evaluate_predictions(self.labels, self.predictions)

        self.assertEqual(report["gold_count"], 6)
        self.assertEqual(report["scored_count"], 4)
        self.assertEqual(report["missing_count"], 2)
        self.assertEqual(
            report["status_counts"],
            {
                "scored": 4,
                "failed": 1,
                "unresolved": 0,
                "missing": 1,
            },
        )
        self.assertAlmostEqual(report["coverage"], 2 / 3)
        self.assertEqual(report["conditional_mae"], 1.25)
        self.assertAlmostEqual(report["macro_f1"], 2 / 15)
        self.assertEqual(report["l1_precision"], 0.5)
        self.assertEqual(report["l1_recall"], 1.0)
        self.assertAlmostEqual(report["rare_recall"], 1 / 3)
        self.assertEqual(report["severe_rare_to_common"], 1)
        self.assertEqual(report["confusion"]["3"]["missing"], 1)
        self.assertEqual(report["confusion"]["5"]["missing"], 1)
        self.assertEqual(report["confusion"]["4"]["5"], 1)
        self.assertEqual(report["per_class"]["3"]["f1"], 0.0)

    def test_rejects_invalid_gold_and_prediction_identity_or_levels(self):
        cases = [
            (
                "duplicate gold",
                [[1, 1, "om", "test"], ["01", 2, "casa", "test"]],
                [[1, "scored", 1]],
                "duplicate",
            ),
            (
                "duplicate prediction",
                [[1, 1, "om", "test"]],
                [[1, "scored", 1], ["01", "failed", ""]],
                "duplicate",
            ),
            ("unknown prediction", [[1, 1, "om", "test"]], [[2, "scored", 1]], "unknown"),
            ("invalid gold level", [[1, 6, "om", "test"]], [[1, "scored", 1]], "level"),
            (
                "invalid prediction level",
                [[1, 1, "om", "test"]],
                [[1, "scored", 0]],
                "rarity_level",
            ),
            (
                "fractional prediction level",
                [[1, 1, "om", "test"]],
                [[1, "scored", "1.5"]],
                "rarity_level",
            ),
            (
                "nonfinite prediction level",
                [[1, 1, "om", "test"]],
                [[1, "scored", "NaN"]],
                "rarity_level",
            ),
            (
                "empty scored prediction",
                [[1, 1, "om", "test"]],
                [[1, "scored", ""]],
                "rarity_level",
            ),
            ("negative ID", [[-1, 1, "om", "test"]], [[-1, "scored", 1]], "word_id"),
            ("zero prediction ID", [[1, 1, "om", "test"]], [[0, "scored", 1]], "word_id"),
            ("unknown status", [[1, 1, "om", "test"]], [[1, "success", 1]], "status"),
            ("contradictory failure", [[1, 1, "om", "test"]], [[1, "failed", 1]], "failed"),
            ("missing group", [[1, 1, "", "test"]], [[1, "scored", 1]], "group"),
            ("missing split", [[1, 1, "om", ""]], [[1, "scored", 1]], "split"),
        ]
        for name, labels, predictions, error in cases:
            with self.subTest(name=name):
                self.write_labels(labels)
                self.write_predictions(predictions)
                with self.assertRaisesRegex(ValueError, error):
                    evaluate_predictions(self.labels, self.predictions)

    def test_rejects_missing_duplicate_or_malformed_csv_columns(self):
        self.write_labels([[1, 1, "om", "test"]])
        for columns, rows in [
            (["word_id", "status"], [[1, "scored"]]),
            (["word_id", "status", "rarity_level", "status"], [[1, "scored", 1, "failed"]]),
            (["word_id", "status", "rarity_level"], [[1, "scored", 1, "unexpected"]]),
            (["word_id", "status", "rarity_level"], [[1, "failed"]]),
        ]:
            with self.subTest(columns=columns, rows=rows):
                self.write_csv(self.predictions, columns, rows)
                with self.assertRaisesRegex(ValueError, "column"):
                    evaluate_predictions(self.labels, self.predictions)

    def test_selected_split_requires_gold_and_excludes_other_splits(self):
        self.write_labels([[1, 1, "om", "test"], [2, 5, "arhaic", "calibration"]])
        self.write_predictions([[1, "scored", 1], [2, "scored", 1]])
        report = evaluate_predictions(self.labels, self.predictions)
        self.assertEqual(report["gold_count"], 1)
        self.assertEqual(report["macro_f1"], 1.0)
        self.assertEqual(report["macro_f1_labels"], ["1"])
        self.assertIsNone(report["rare_recall"])
        self.assertIsNone(report["per_class"]["5"]["f1"])
        with self.assertRaisesRegex(ValueError, "gold"):
            evaluate_predictions(self.labels, self.predictions, split="development")

    def test_all_unscored_keeps_gold_and_uses_null_for_empty_denominators(self):
        self.write_labels([[1, 1, "om", "test"], [2, 5, "arhaic", "test"]])
        self.write_predictions([[1, "unresolved", ""], [2, "failed", ""]])
        report = evaluate_predictions(self.labels, self.predictions)
        self.assertEqual(report["coverage"], 0.0)
        self.assertEqual(report["macro_f1"], 0.0)
        self.assertEqual(report["l1_recall"], 0.0)
        self.assertEqual(report["rare_recall"], 0.0)
        self.assertIsNone(report["l1_precision"])
        self.assertIsNone(report["conditional_mae"])

    def test_probability_scores_use_only_complete_vectors_and_report_coverage(self):
        self.write_labels(
            [
                [1, 1, "om", "test"],
                [2, 5, "arhaic", "test"],
                [3, 3, "albie", "test"],
                [4, 4, "regional", "test"],
            ]
        )
        self.write_predictions(
            [
                [1, "scored", 1, 0.5, 0.5, 0, 0, 0],
                [2, "scored", 5, 0, 0, 0, 0.25, 0.75],
                [3, "scored", 2, "", "", "", "", ""],
                [4, "failed", "", "", "", "", "", ""],
            ],
            probabilities=True,
        )

        report = evaluate_predictions(self.labels, self.predictions)
        metrics = report["probability_metrics"]

        self.assertEqual(metrics["count"], 2)
        self.assertEqual(metrics["coverage"], 0.5)
        self.assertAlmostEqual(metrics["scored_coverage"], 2 / 3)
        self.assertEqual(metrics["brier"], 0.3125)
        self.assertAlmostEqual(metrics["log_loss"], 0.4904146265058631)
        self.assertEqual(metrics["ranked_probability_score"], 0.0390625)
        self.assertEqual(metrics["zero_gold_probability_count"], 0)

        self.write_predictions([[1, "scored", 1]])
        legacy = evaluate_predictions(self.labels, self.predictions)["probability_metrics"]
        self.assertEqual(legacy["count"], 0)
        self.assertEqual(legacy["coverage"], 0)
        self.assertIsNone(legacy["brier"])
        self.assertIsNone(legacy["log_loss"])
        self.assertIsNone(legacy["ranked_probability_score"])

    def test_rejects_partial_nonfinite_or_unnormalized_probability_vectors(self):
        self.write_labels([[1, 1, "om", "test"]])
        for status, level, probabilities in [
            ("scored", 1, ["", 1, 0, 0, 0]),
            ("scored", 1, [1, "", 0, 0, 0]),
            ("scored", 1, ["NaN", 0, 0, 0, 0]),
            ("scored", 1, ["inf", 0, 0, 0, 0]),
            ("scored", 1, [-0.1, 0.1, 0, 0, 1]),
            ("scored", 1, [1.1, 0, 0, 0, 0]),
            ("scored", 1, [0.1, 0.1, 0.1, 0.1, 0.1]),
            ("failed", "", [1, 0, 0, 0, 0]),
        ]:
            with self.subTest(status=status, probabilities=probabilities):
                self.write_predictions([[1, status, level, *probabilities]], probabilities=True)
                with self.assertRaisesRegex(ValueError, "probabilit"):
                    evaluate_predictions(self.labels, self.predictions)

        self.write_csv(
            self.predictions, ["word_id", "status", "rarity_level", "p_L1"], [[1, "scored", 1, 1]]
        )
        with self.assertRaisesRegex(ValueError, "probabilit"):
            evaluate_predictions(self.labels, self.predictions)

    def test_unresolved_can_preserve_raw_prediction_without_receiving_scored_credit(self):
        self.write_labels([[1, 1, "om", "test"], [2, 5, "arhaic", "test"]])
        self.write_predictions(
            [
                [1, "scored", 1, 1, 0, 0, 0, 0],
                [2, "unresolved", 5, 0, 0, 0, 0.5, 0.5],
            ],
            probabilities=True,
        )
        report = evaluate_predictions(self.labels, self.predictions)
        self.assertEqual(report["coverage"], 0.5)
        self.assertEqual(report["rare_recall"], 0.0)
        self.assertEqual(report["confusion"]["5"]["missing"], 1)
        self.assertEqual(report["probability_metrics"]["count"], 1)
        self.assertEqual(report["probability_metrics"]["brier"], 0.0)

    def test_paired_comparison_preserves_gold_population_and_compares_mae_on_shared_rows(self):
        self.write_labels(
            [
                [1, 1, "om", "test"],
                [2, 5, "arhaic", "test"],
                [3, 4, "regional", "test"],
                [4, 3, "albie", "test"],
            ]
        )
        self.write_predictions(
            [
                [1, "scored", 1],
                [2, "failed", ""],
                [3, "scored", 4],
                [4, "scored", 3],
            ]
        )
        baseline = self.root / "baseline.csv"
        self.write_predictions(
            [
                [1, "scored", 1],
                [2, "scored", 5],
                [3, "scored", 2],
                [4, "failed", ""],
            ],
            path=baseline,
        )

        report = evaluate_predictions(
            self.labels, self.predictions, baseline_csv=baseline, bootstrap_samples=0
        )
        comparison = report["comparison"]
        self.assertEqual(comparison["baseline"]["gold_count"], 4)
        self.assertEqual(report["macro_f1_labels"], ["1", "3", "4", "5"])
        self.assertEqual(comparison["baseline"]["macro_f1_labels"], ["1", "3", "4", "5"])
        self.assertEqual(report["macro_f1"], 0.75)
        self.assertEqual(comparison["baseline"]["macro_f1"], 0.5)
        self.assertEqual(comparison["coverage_delta"], 0.0)
        self.assertEqual(comparison["macro_f1_delta"], 0.25)
        self.assertEqual(comparison["paired_scored_count"], 2)
        self.assertEqual(comparison["paired_coverage"], 0.5)
        self.assertEqual(comparison["paired_mae_delta"], -1.0)

    def test_bootstrap_resamples_whole_groups_deterministically(self):
        labels = [
            [word_id, 1, "first" if word_id <= 10 else "second", "test"] for word_id in range(1, 21)
        ]
        self.write_labels(labels)
        self.write_predictions([[word_id, "scored", 1] for word_id in range(1, 21)])
        baseline = self.root / "baseline.csv"
        self.write_predictions(
            [[word_id, "scored", 1 if word_id <= 10 else 2] for word_id in range(1, 21)],
            path=baseline,
        )
        report = evaluate_predictions(
            self.labels, self.predictions, baseline_csv=baseline, bootstrap_samples=200, seed=17
        )
        bootstrap = report["comparison"]["bootstrap"]
        self.assertEqual(bootstrap["method"], "paired_group_percentile")
        self.assertEqual(bootstrap["group_count"], 2)
        self.assertEqual(bootstrap["confidence"], 0.95)
        self.assertEqual(
            bootstrap["intervals"]["paired_mae_delta"],
            {
                "lower": -1.0,
                "upper": 0.0,
                "valid_samples": 200,
            },
        )
        self.assertEqual(
            bootstrap["intervals"]["macro_f1_delta"],
            {
                "lower": 0.0,
                "upper": 1.0,
                "valid_samples": 200,
            },
        )
        self.assertEqual(bootstrap["intervals"]["coverage_delta"]["lower"], 0.0)
        self.assertEqual(bootstrap["intervals"]["coverage_delta"]["upper"], 0.0)

        self.write_labels(list(reversed(labels)))
        repeated = evaluate_predictions(
            self.labels, self.predictions, baseline_csv=baseline, bootstrap_samples=200, seed=17
        )
        self.assertEqual(bootstrap, repeated["comparison"]["bootstrap"])

    def test_bootstrap_keeps_original_gold_classes_when_a_group_is_not_sampled(self):
        self.write_labels([[1, 1, "common", "test"], [2, 5, "rare", "test"]])
        self.write_predictions([[1, "scored", 1], [2, "scored", 5]])
        baseline = self.root / "baseline.csv"
        self.write_predictions([[1, "scored", 1], [2, "scored", 4]], path=baseline)
        report = evaluate_predictions(
            self.labels, self.predictions, baseline_csv=baseline, bootstrap_samples=200, seed=17
        )
        interval = report["comparison"]["bootstrap"]["intervals"]["macro_f1_delta"]
        self.assertEqual(interval["lower"], 0.0)
        self.assertEqual(interval["upper"], 0.5)

    def test_bootstrap_does_not_invent_mae_or_intervals_without_enough_evidence(self):
        self.write_labels([[1, 1, "first", "test"], [2, 5, "second", "test"]])
        self.write_predictions([[1, "scored", 1]])
        baseline = self.root / "baseline.csv"
        self.write_predictions([[2, "scored", 5]], path=baseline)
        report = evaluate_predictions(
            self.labels, self.predictions, baseline_csv=baseline, bootstrap_samples=50
        )
        comparison = report["comparison"]
        self.assertEqual(comparison["paired_coverage"], 0.0)
        self.assertIsNone(comparison["paired_mae_delta"])
        self.assertEqual(
            comparison["bootstrap"]["intervals"]["paired_mae_delta"],
            {
                "lower": None,
                "upper": None,
                "valid_samples": 0,
            },
        )

        self.write_labels([[1, 1, "same", "test"], [2, 5, "same", "test"]])
        report = evaluate_predictions(self.labels, self.predictions, baseline_csv=baseline)
        bootstrap = report["comparison"]["bootstrap"]
        self.assertEqual(bootstrap["reason"], "At least two gold groups required")
        self.assertIsNone(bootstrap["intervals"]["coverage_delta"]["lower"])

    def test_rejects_cross_split_groups_and_invalid_resampling_controls(self):
        self.write_labels([[1, 1, "same", "test"], [2, 5, "same", "dev"]])
        self.write_predictions([[1, "scored", 1]])
        with self.assertRaisesRegex(ValueError, "group.*split"):
            evaluate_predictions(self.labels, self.predictions)

        self.write_labels([[1, 1, "same", "test"]])
        for controls in [
            {"bootstrap_samples": -1},
            {"bootstrap_samples": 1.5},
            {"bootstrap_samples": True},
            {"seed": 1.5},
            {"seed": True},
        ]:
            with self.subTest(controls=controls):
                with self.assertRaises(ValueError):
                    evaluate_predictions(self.labels, self.predictions, **controls)

    def test_existing_run_csv_is_a_scored_legacy_baseline_without_probabilities(self):
        self.write_labels([[1, 1, "om", "test"], [2, 5, "arhaic", "test"]])
        self.write_predictions([[1, "scored", 1], [2, "scored", 5]])
        baseline = self.root / "run.csv"
        self.write_csv(
            baseline,
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
                [1, "om", "N", 1, "unclassified", 0.9, "2026-10-16T00:00:00Z", "legacy", "old"],
                [2, "arhaic", "A", 4, "unclassified", 0.8, "2026-10-16T00:00:00Z", "legacy", "old"],
            ],
        )
        report = evaluate_predictions(
            self.labels, self.predictions, baseline_csv=baseline, bootstrap_samples=0
        )
        self.assertEqual(report["comparison"]["baseline"]["coverage"], 1.0)
        self.assertEqual(report["comparison"]["paired_mae_delta"], -0.5)

        self.write_csv(baseline, ["word_id", "rarity_level"], [[1, ""]])
        with self.assertRaisesRegex(ValueError, "rarity_level"):
            evaluate_predictions(self.labels, self.predictions, baseline_csv=baseline)


if __name__ == "__main__":
    unittest.main()
