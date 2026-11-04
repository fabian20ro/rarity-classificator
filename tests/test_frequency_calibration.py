import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from tests.test_exact_form import write_csv
from classificator.evaluation.frequency_calibration import freeze_frequency_thresholds


class FrequencyCalibrationTests(unittest.TestCase):
    def test_fit_uses_only_clarified_pilot_labels_and_freezes_missing_as_abstention(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            vocabulary = write_csv(
                root / "pilot.csv",
                [dict(word_id=i, word=w, type="N") for i, w in enumerate("abcdef", 1)],
            )
            reference = write_csv(
                root / "reference.csv",
                [
                    dict(word_id=i, word=w, working_level=i, reference_kind="shortlist_form_review")
                    for i, w in enumerate("abcde", 1)
                ]
                + [
                    dict(
                        word_id=6,
                        word="f",
                        working_level=5,
                        reference_kind="initial_opaque_form_pos",
                    )
                ],
            )
            features = write_csv(
                root / "features.csv",
                [
                    dict(word_id=i, word=w, wordfreq=f, rebus=f if i < 5 else "")
                    for i, w, f in [
                        (1, "a", 0.1),
                        (2, "b", 0.01),
                        (3, "c", 0.001),
                        (4, "d", 0.0001),
                        (5, "e", 0.00001),
                        (6, "f", 0.8),
                        (7, "g", 0.002),
                        (8, "h", ""),
                    ]
                ],
            )
            result = freeze_frequency_thresholds(vocabulary, reference, features, root / "output")
            self.assertEqual(result["wordfreq"]["thresholds"], [0.1, 0.01, 0.001, 0.0001])
            self.assertEqual(result["wordfreq"]["fit_mae"], 0)
            self.assertEqual(result["fit_ids"], [1, 2, 3, 4, 5])
            self.assertEqual(
                result["rebus"]["l5_boundary"], "convention_min_observed_div10_not_identified"
            )
            self.assertEqual(result["rebus"]["thresholds"][-1], 0.00001)
            with (root / "output/predictions.csv").open() as stream:
                predictions = list(csv.DictReader(stream))
            row = next(r for r in predictions if r["word_id"] == "8")
            self.assertEqual(row["wordfreq_level"], "")
            self.assertEqual(row["wordfreq_status"], "unresolved")
            with self.assertRaises(FileExistsError):
                freeze_frequency_thresholds(vocabulary, reference, features, root / "output")
            # A held-out feature changes its own prediction, never fitted thresholds.
            text = features.read_text().replace("7,g,0.002,", "7,g,0.9,")
            features.write_text(text)
            other = freeze_frequency_thresholds(vocabulary, reference, features, root / "other")
            self.assertEqual(other["wordfreq"]["thresholds"], result["wordfreq"]["thresholds"])
