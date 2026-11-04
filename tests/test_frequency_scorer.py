import unittest

from classificator.models import BaseWordRow
from classificator.scoring.frequency import FrequencyScorer


class FrequencyScorerTest(unittest.TestCase):
    def test_explicit_thresholds_classify_exact_forms_without_claiming_confidence(self):
        scorer = FrequencyScorer(
            {10: 0.01, 20: 0.001, 30: 0.0001, 40: 0.00001, 50: 0.000001},
            thresholds=(0.01, 0.001, 0.0001, 0.00001),
        )
        words = [BaseWordRow(word_id, "forma", "N") for word_id in (10, 20, 30, 40, 50)]

        outcomes = scorer.score_batch(words)

        self.assertEqual([outcome.word_id for outcome in outcomes], [10, 20, 30, 40, 50])
        self.assertEqual([outcome.rarity_level for outcome in outcomes], [1, 2, 3, 4, 5])
        self.assertEqual([outcome.status for outcome in outcomes], ["scored"] * 5)
        for outcome in outcomes:
            self.assertEqual(outcome.probabilities, ())
            self.assertIsNone(outcome.confidence)
            self.assertIsNone(outcome.expected_level)
            self.assertEqual(outcome.tag, "unclassified")

    def test_absent_zero_and_missing_frequency_are_unresolved_not_rare(self):
        scorer = FrequencyScorer(
            {1: None, 2: 0, 4: 0.001}, thresholds=(0.01, 0.001, 0.0001, 0.00001)
        )
        outcomes = scorer.score_batch(
            [BaseWordRow(word_id, "forma", "N") for word_id in (1, 2, 3, 4)]
        )
        self.assertEqual(
            [outcome.status for outcome in outcomes],
            ["unresolved", "unresolved", "unresolved", "scored"],
        )
        self.assertEqual([outcome.rarity_level for outcome in outcomes], [None, None, None, 2])
        self.assertTrue(all(outcome.error for outcome in outcomes[:3]))
        self.assertEqual(scorer.score_batch([]), [])

    def test_invalid_frequency_data_or_thresholds_fail_before_scoring(self):
        valid = (0.01, 0.001, 0.0001, 0.00001)
        for frequencies, thresholds in [
            ({1: -0.1}, valid),
            ({1: float("nan")}, valid),
            ({1: float("inf")}, valid),
            ({1: 2.0}, valid),
            ({1: "0.1"}, valid),
            ({1: True}, valid),
            ({0: 0.1}, valid),
            ({True: 0.1}, valid),
            ({"1": 0.1}, valid),
            ({1: 0.1}, (0.1, 0.01, 0.001)),
            ({1: 0.1}, (0.01, 0.01, 0.001, 0.0001)),
            ({1: 0.1}, (0.01, 0.1, 0.001, 0.0001)),
            ({1: 0.1}, (0.1, 0.01, 0.001, 0)),
            ({1: 0.1}, (float("inf"), 0.01, 0.001, 0.0001)),
            ({1: 0.1}, (True, 0.01, 0.001, 0.0001)),
        ]:
            with self.subTest(frequencies=frequencies, thresholds=thresholds):
                with self.assertRaises(ValueError):
                    FrequencyScorer(frequencies, thresholds=thresholds)


if __name__ == "__main__":
    unittest.main()
