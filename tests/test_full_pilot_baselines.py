import csv
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests.test_exact_form import write_csv
from classificator.evaluation.full_pilot_baselines import evaluate_full_pilot


@unittest.skipUnless(importlib.util.find_spec("sklearn"), "Install evaluation extra for Ridge")
class FullPilotBaselineTests(unittest.TestCase):
    def test_saved_predictions_cover_all_forms_and_initial_and_revised_truth_stay_separate(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            ref = write_csv(
                root / "reference.csv",
                [
                    dict(word_id=i, word=w, initial_level=a, working_level=b, reference_kind=k)
                    for i, w, a, b, k in [
                        (1, "a", 1, 2, "shortlist_form_review"),
                        (2, "b", 2, 2, "initial_opaque_form_pos"),
                        (3, "c", 4, 4, "initial_opaque_form_pos"),
                        (4, "d", 5, 5, "audited_context_minimum"),
                    ]
                ],
            )
            features = write_csv(
                root / "features.csv",
                [
                    dict(word_id=i, word=w, wordfreq=f, rebus=g)
                    for i, w, f, g in [
                        (1, "a", 0.1, 0.02),
                        (2, "b", 0.01, ""),
                        (3, "c", "", 0.001),
                        (4, "d", "", ""),
                    ]
                ],
            )
            legacy = write_csv(
                root / "legacy.csv",
                [
                    dict(word_id=i, word=w, rarity_level=y)
                    for i, w, y in [(1, "a", 1), (2, "b", 3), (3, "c", 4), (4, "d", 5)]
                ],
            )
            assistant = write_csv(
                root / "assistant.csv",
                [
                    dict(word_id=i, word=w, rarity_level=y)
                    for i, w, y in [(1, "a", 2), (2, "b", 2), (3, "c", 4), (4, "d", 4)]
                ],
            )
            first = write_csv(
                root / "first.csv",
                [
                    dict(word_id=i, word=w, level=y)
                    for i, w, y in [(1, "a", 1), (2, "b", 2), (3, "c", 4)]
                ],
            )
            result = evaluate_full_pilot(ref, features, legacy, assistant, first, root / "out")
            self.assertEqual(result["views"]["original_round_final"]["all"]["legacy"]["mae"], 0.25)
            latest = result["views"]["revised_working"]["all"]
            self.assertEqual(latest["total"], 4)
            self.assertEqual(latest["legacy"]["mae"], 0.5)
            self.assertEqual(latest["assistant"]["mae"], 0.25)
            self.assertEqual(result["first_independent_saved"]["total"], 3)
            self.assertAlmostEqual(result["first_independent_saved"]["assistant"]["mae"], 1 / 3)
            self.assertEqual(latest["wordfreq"]["covered"], 2)
            self.assertEqual(latest["rebus"]["covered"], 2)
            self.assertEqual(latest["ridge"]["covered"], 4)
            self.assertEqual(result["views"]["first_independent"]["all"]["total"], 3)
            self.assertEqual(result["views"]["first_independent"]["all"]["ridge"]["covered"], 3)
            self.assertEqual(
                json.loads((root / "out/first_independent/folds/1.json").read_text())["train_ids"],
                [2, 3],
            )
            saved = list(csv.DictReader((root / "out/revised_working/predictions.csv").open()))
            self.assertEqual(len(saved), 4)
            absent = next(r for r in saved if r["word_id"] == "4")
            self.assertEqual(absent["evidence_group"], "neither")
            self.assertEqual(absent["wordfreq_level"], "")
            self.assertEqual(absent["rebus_level"], "")
            self.assertEqual(absent["ridge_basis"], "missingness_only")
            self.assertEqual(result["views"]["revised_working"]["clarified"]["total"], 2)
            self.assertEqual(result["views"]["revised_working"]["opaque"]["total"], 2)
            # Both targets must exclude the omitted label from every learned method.
            before = json.loads((root / "out/revised_working/folds/1.json").read_text())
            refs = list(csv.DictReader(ref.open()))
            refs[0]["working_level"] = "5"
            refs[0]["initial_level"] = "5"
            write_csv(ref, refs)
            evaluate_full_pilot(ref, features, legacy, assistant, first, root / "changed")
            after = json.loads((root / "changed/revised_working/folds/1.json").read_text())
            self.assertEqual(before, after)
            self.assertEqual(
                json.loads((root / "out/original_round_final/folds/1.json").read_text()),
                json.loads((root / "changed/original_round_final/folds/1.json").read_text()),
            )
            self.assertEqual(before["train_ids"], [2, 3, 4])
            # Train has only .01 in wordfreq and .001 in rebus; held-out .1/.02 never impute.
            self.assertEqual(before["ridge"]["log_imputation"], [-2.0, -3.0])
            self.assertEqual(before["ridge"]["scaler_mean"][:2], [-2.0, -3.0])
            self.assertEqual(before["median_level"], 4)
            self.assertEqual(before["majority_level"], 2)
            with self.assertRaises(FileExistsError):
                evaluate_full_pilot(ref, features, legacy, assistant, first, root / "out")

    def test_missing_source_gets_training_missing_group_median_and_full_coverage(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            ref, features, saved, first = self._coverage_inputs(root)
            result = evaluate_full_pilot(ref, features, saved, saved, first, root / "out")
            rows = {r["word_id"]: r for r in csv.DictReader(
                (root / "out/revised_working/predictions.csv").open()
            )}
            # Missing-group labels for word1 are [4,5], lower median4; global median1.
            self.assertEqual(rows["1"]["wordfreq_complete_level"], "4")
            self.assertEqual(rows["1"]["wordfreq_complete_basis"], "missing_group_median")
            self.assertEqual(rows["1"]["rebus_complete_level"], "4")
            # Retain direct frequency predictions for every observed form.
            self.assertEqual(rows["4"]["wordfreq_complete_level"], rows["4"]["wordfreq_level"])
            self.assertEqual(rows["4"]["wordfreq_complete_basis"], "frequency_thresholds")
            for view in result["views"].values():
                primary = view["operational"]
                for method in ("wordfreq_complete", "rebus_complete", "ridge"):
                    self.assertEqual(primary[method]["covered"], 6)
                    self.assertEqual(primary[method]["missing"], 0)
                self.assertNotIn("wordfreq", primary)
                self.assertNotIn("rebus", primary)
            fold = json.loads((root / "out/revised_working/folds/1.json").read_text())
            self.assertEqual(fold["wordfreq_fallback"]["train_ids"], [2, 3])
            self.assertEqual(fold["wordfreq_fallback"]["level"], 4)

    def _coverage_inputs(self, root):
        labels = [2, 4, 5, 1, 1, 1]
        ref = write_csv(root / "ref.csv", [
            dict(word_id=i, word=str(i), initial_level=y, working_level=y,
                 reference_kind="initial_opaque_form_pos")
            for i, y in enumerate(labels, 1)
        ])
        features = write_csv(root / "features.csv", [
            dict(word_id=i, word=str(i), wordfreq=f, rebus=f)
            for i, f in enumerate(["", "", "", 0.1, 0.1, 0.1], 1)
        ])
        saved = write_csv(root / "saved.csv", [
            dict(word_id=i, word=str(i), rarity_level=y)
            for i, y in enumerate(labels, 1)
        ])
        first = write_csv(root / "first.csv", [
            dict(word_id=i, word=str(i), level=y) for i, y in enumerate(labels, 1)
        ])
        return ref, features, saved, first

    def test_fallback_reports_all_errors_and_excludes_held_out_labels_in_every_view(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            ref, features, saved, first = self._coverage_inputs(root)
            before = evaluate_full_pilot(ref, features, saved, saved, first, root / "before")
            breakdown = before["views"]["revised_working"]["completion_routes"]["wordfreq"]
            # Missing forms have truth [2,4,5], predictions [4,2,2]: absolute errors2+2+3.
            self.assertEqual(breakdown["missing_group_median"]["covered"], 3)
            self.assertAlmostEqual(breakdown["missing_group_median"]["mae"], 7 / 3)
            self.assertAlmostEqual(
                before["views"]["revised_working"]["operational"]["wordfreq_complete"]["mae"],
                7 / 6,
            )
            refs = list(csv.DictReader(ref.open()))
            refs[0]["initial_level"] = refs[0]["working_level"] = "5"
            write_csv(ref, refs)
            independent = list(csv.DictReader(first.open()))
            independent[0]["level"] = "5"
            write_csv(first, independent)
            evaluate_full_pilot(ref, features, saved, saved, first, root / "after")
            for view in before["views"]:
                self.assertEqual(
                    json.loads((root / f"before/{view}/folds/1.json").read_text()),
                    json.loads((root / f"after/{view}/folds/1.json").read_text()),
                )

    def test_global_fallback_covers_unseen_missingness_and_absent_threshold_model(self):
        scenarios = [
            ([0, 0.1, 0.1, 0.1, 0.1, 0.1], "global_median", [2, 3, 4, 5, 6]),
            ([0.1, "", "", "", "", ""], "global_median", [2, 3, 4, 5, 6]),
            ([0, "", 0, "", 0, ""], "missing_group_median", [2, 3, 4, 5, 6]),
        ]
        for values, basis, support in scenarios:
            with self.subTest(values=values), TemporaryDirectory() as temp:
                root = Path(temp)
                ref, features, saved, first = self._coverage_inputs(root)
                write_csv(features, [
                    dict(word_id=i, word=str(i), wordfreq=f, rebus=f)
                    for i, f in enumerate(values, 1)
                ])
                result = evaluate_full_pilot(ref, features, saved, saved, first, root / "out")
                for view in result["views"]:
                    rows = list(csv.DictReader((root / f"out/{view}/predictions.csv").open()))
                    for source in ("wordfreq", "rebus"):
                        self.assertEqual(rows[0][source + "_complete_level"], "1")
                        self.assertEqual(rows[0][source + "_complete_basis"], basis)
                        self.assertEqual(
                            result["views"][view]["operational"][source + "_complete"]["covered"], 6
                        )
                        fold = json.loads((root / f"out/{view}/folds/1.json").read_text())
                        self.assertEqual(fold[source + "_fallback"]["train_ids"], support)
