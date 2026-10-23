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
