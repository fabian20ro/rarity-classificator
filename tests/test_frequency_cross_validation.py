import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests.test_exact_form import write_csv
from classificator.evaluation.frequency_cross_validation import cross_validate_frequencies


class FrequencyCrossValidationTests(unittest.TestCase):
    def test_out_of_fold_predictions_exclude_own_label_and_keep_rubrics_separate(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            pilot = write_csv(
                root / "pilot.csv",
                [dict(word_id=i, word=w, type="N") for i, w in enumerate("abcde", 1)],
            )
            labels = [
                dict(
                    word_id=i,
                    word=w,
                    working_level=y,
                    reference_kind="shortlist_form_review" if i < 5 else "initial_opaque_form_pos",
                    coverage_status="fixture",
                    witness="fixture",
                )
                for i, w, y in [(1, "a", 1), (2, "b", 1), (3, "c", 5), (4, "d", 1), (5, "e", 2)]
            ]
            reference = write_csv(root / "reference.csv", labels)
            features = write_csv(
                root / "features.csv",
                [
                    dict(
                        word_id=i,
                        word=w,
                        wordfreq="" if i == 4 else 0.01,
                        rebus="" if i in (2, 4) else 0.01,
                    )
                    for i, w in enumerate("abcde", 1)
                ],
            )
            result = cross_validate_frequencies(pilot, reference, features, root / "out")
            primary = result["clarified_loocv"]
            self.assertEqual(primary["total"], 4)
            self.assertEqual(primary["wordfreq"]["covered"], 3)
            self.assertEqual(primary["wordfreq"]["mae"], 4)
            self.assertEqual(primary["rebus"]["covered"], 2)
            self.assertEqual(primary["paired"]["total"], 2)
            self.assertEqual(primary["paired"]["wordfreq"]["mae"], 4)
            self.assertEqual(primary["paired"]["median"]["mae"], 2)
            self.assertEqual(primary["wordfreq_median"]["mae"], 4 / 3)
            self.assertEqual(primary["paired"]["wordfreq_median"]["mae"], 2)
            self.assertEqual(primary["paired"]["rebus_median"]["mae"], 4)
            self.assertEqual(primary["wordfreq"]["rare"]["severe_underestimate"], 1)
            self.assertEqual(result["historical_diagnostic"]["total"], 1)
            self.assertEqual(result["historical_diagnostic"]["wordfreq"]["mae"], 1)
            rows = list(csv.DictReader((root / "out/comparison.csv").open()))
            self.assertEqual(len(rows), 5)
            self.assertEqual(next(r for r in rows if r["word_id"] == "4")["wordfreq_level"], "")
            fold = json.loads((root / "out/folds/3/model/thresholds.json").read_text())
            self.assertEqual(fold["fit_ids"], [1, 2, 4])
            self.assertEqual(
                fold["rebus"]["l5_boundary"], "convention_min_observed_div10_not_identified"
            )
            # Perturbing the omitted truth must not change its prediction or model.
            labels[2]["working_level"] = 2
            write_csv(reference, labels)
            other = cross_validate_frequencies(pilot, reference, features, root / "other")
            second = json.loads((root / "other/folds/3/model/thresholds.json").read_text())
            self.assertEqual(fold["wordfreq"], second["wordfreq"])
            self.assertEqual(fold["rebus"], second["rebus"])
            changed = list(csv.DictReader((root / "other/comparison.csv").open()))
            self.assertEqual(next(r for r in changed if r["word_id"] == "3")["wordfreq_level"], "1")
            self.assertEqual(other["clarified_loocv"]["total"], 4)
            original_heldout = next(r for r in rows if r["word_id"] == "3")
            changed_heldout = next(r for r in changed if r["word_id"] == "3")
            for source in ["median", "wordfreq_median", "rebus_median"]:
                self.assertEqual(
                    original_heldout[source + "_level"], changed_heldout[source + "_level"]
                )
            labels[4]["working_level"] = 5
            write_csv(reference, labels)
            opaque_changed = cross_validate_frequencies(pilot, reference, features, root / "opaque")
            self.assertEqual(opaque_changed["clarified_loocv"], other["clarified_loocv"])
            with self.assertRaises(FileExistsError):
                cross_validate_frequencies(pilot, reference, features, root / "out")
