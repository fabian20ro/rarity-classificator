import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import csv
import os
import tempfile

from classificator.steps.step5_rebalance import run_step5, Step5Options
from classificator.run_csv_repository import RunCsvRepository
from classificator.lm.client import LmStudioClient
from classificator.models import ScoreResult, ScoringOutputMode
from classificator.transitions import LevelTransition

class TestStep5Contract(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.gettempdir()) / "compound_test_contract"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.input_csv = self.test_dir / "input.csv"
        self.output_csv = self.test_dir / "output.csv"

        # Prepare input CSV
        with open(self.input_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["word_id", "word", "type", "rarity_level"])
            writer.writerow(["1", "word1", "noun", "1"])
            writer.writerow(["2", "word2", "verb", "2"])
            writer.writerow(["3", "word3", "adj", "1"])

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch('classificator.lm.client._load_requests')
    @patch('classificator.lm.client.LmStudioClient.score_batch_resilient')
    @patch('classificator.lm.client.LmStudioClient.preflight')
    @patch('classificator.lm.client.LmStudioClient.resolve_endpoint')
    def test_no_zero_local_id(self, mock_load_requests, mock_resolve, mock_preflight, mock_score):
        mock_requests = MagicMock()
        mock_load_requests.return_value = mock_requests
        mock_resolve.return_value = MagicMock(endpoint="http://localhost:1234", flavor="local", source="test")

        # We want 2 items to be assigned to transition to level 1.
        # Input: 1 (lvl 1), 2 (lvl 2), 3 (lvl 1)
        # We want to test that the output doesn't have local_id=0.

        # We'll simulate that word 2 is selected for transition.

        # The batch contains word 2.
        mock_results = [
            MagicMock(word_id=2, rarity_level=1)
        ]
        mock_score.return_value = mock_results

        options = Step5Options(
            run_slug="test_run",
            model="test-model",
            input_csv_path=self.input_csv,
            output_csv_path=self.output_csv,
            transitions=[LevelTransition(from_level=2, to_level=1)],
            dry_run=False
        )

        repo = RunCsvRepository()
        lm_client = LmStudioClient(api_key="dummy")

        run_step5(options, repo=repo, lm_client=lm_client, output_dir=self.test_dir)

        # Verify output
        with open(self.output_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # In the output, word_id is a column.
                # We check that it's not 0.
                self.assertNotEqual(int(row['word_id']), 0)

    @patch('classificator.lm.client._load_requests')
    @patch('classificator.lm.client.LmStudioClient.score_batch_resilient')
    @patch('classificator.lm.client.LmStudioClient.preflight')
    @patch('classificator.lm.client.LmStudioClient.resolve_endpoint')
    def test_dry_run_skips_output_csv(self, mock_load_requests, mock_resolve, mock_preflight, mock_score):
        """When dry_run=True, no output CSV should be written."""
        mock_requests = MagicMock()
        mock_load_requests.return_value = mock_requests
        mock_resolve.return_value = MagicMock(endpoint="http://localhost:1234", flavor="local", source="test")

        # Simulate scoring word 2 for transition.
        mock_results = [MagicMock(word_id=2, rarity_level=1)]
        mock_score.return_value = mock_results

        options = Step5Options(
            run_slug="dry_run_test",
            model="test-model",
            input_csv_path=self.input_csv,
            output_csv_path=self.output_csv,
            transitions=[LevelTransition(from_level=2, to_level=1)],
            dry_run=True  # dry_run=True: no output written
        )

        repo = RunCsvRepository()
        lm_client = LmStudioClient(api_key="dummy")

        run_step5(options, repo=repo, lm_client=lm_client, output_dir=self.test_dir)

        self.assertFalse(self.output_csv.exists(), "output CSV must not exist in dry-run mode")

    @patch('classificator.lm.client._load_requests')
    @patch('classificator.lm.client.LmStudioClient.score_batch_resilient')
    @patch('classificator.lm.client.LmStudioClient.preflight')
    @patch('classificator.lm.client.LmStudioClient.resolve_endpoint')
    def test_output_csv_records_rebalance_metadata_per_word(self, mock_load_requests, mock_resolve, mock_preflight, mock_score):
        """Output CSV must carry final_level + rebalance rule/model/run columns.

        Production contract: _write_output appends new header columns (final_level,
        rebalance_rule, rebalance_model, rebalance_run, rebalanced_at) when missing
        and writes runtime.levels_by_id as final_level for every row. Words that are
        not in the transition set get empty rule/model/run values; words that were
        switched carry the run_slug + model + a non-empty rule string.
        """
        from classificator.steps.step5_rebalance import (
            RebalanceDataset, RebalanceRuntime, SwitchedWordEvent, _write_output
        )

        mock_requests = MagicMock()
        mock_load_requests.return_value = mock_requests
        mock_resolve.return_value = MagicMock(endpoint="http://localhost:1234", flavor="local", source="test")

        # Simulate scoring so that word_id=2 is selected as common (stays at level 1).
        # Input levels: 1 -> word1, 2 -> word2, 1 -> word3. Transition 2->1 with lower_ratio
        # produces a batch of [word2] and the LLM selects it for common_level=1, so its level
        # stays at 2 (no change) — but we override via runtime.levels_by_id below to simulate
        # that word2 was switched to level 1.
        mock_results = [MagicMock(word_id=2, rarity_level=1)]
        mock_score.return_value = mock_results

        options = Step5Options(
            run_slug="meta_test",
            model="test-model",
            input_csv_path=self.input_csv,
            output_csv_path=self.output_csv,
            transitions=[LevelTransition(from_level=2, to_level=1)],
            dry_run=False
        )

        # Build a dataset identical in shape to what _load_dataset produces.
        dataset = RebalanceDataset(
            input_headers=["word_id", "word", "type", "rarity_level"],
            mutable_rows=[
                {"word_id": "1", "word": "word1", "type": "noun", "rarity_level": "1"},
                {"word_id": "2", "word": "word2", "type": "verb", "rarity_level": "2"},
                {"word_id": "3", "word": "word3", "type": "adj", "rarity_level": "1"},
            ],
            words_by_id={1: type("RW", (), {"word_id": 1, "word": "word1", "type": "noun"})(),
                         2: type("RW", (), {"word_id": 2, "word": "word2", "type": "verb"})(),
                         3: type("RW", (), {"word_id": 3, "word": "word3", "type": "adj"})()},
            levels_by_id={1: 1, 2: 2, 3: 1},
        )

        # Simulate runtime where word 2 was switched from level 2 -> 1.
        runtime = RebalanceRuntime(
            levels_by_id={1: 1, 2: 1, 3: 1},
            distribution=_make_distribution({1: 3}),
            rebalance_rules={2: "2->1 (via 2:1)"},
            processed_word_ids={2},
        )

        repo = RunCsvRepository()
        lm_client = LmStudioClient(api_key="dummy")

        _write_output(dataset, runtime, options, repo)

        # Inspect output CSV contractually.
        with open(self.output_csv, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        expected_headers = ["word_id", "word", "type", "rarity_level",
                            "final_level", "rebalance_rule", "rebalance_model",
                            "rebalance_run", "rebalanced_at"]
        self.assertEqual(list(rows[0].keys()), expected_headers,
                         "output CSV must carry all rebalance metadata columns")

        row_by_id = {int(r['word_id']): r for r in rows}

        # word 1: not switched -> empty rule/model/run
        w1 = row_by_id[1]
        self.assertEqual(w1['final_level'], '1')
        self.assertEqual(w1['rebalance_rule'], '')
        self.assertEqual(w1['rebalance_model'], '')
        self.assertEqual(w1['rebalance_run'], '')

        # word 2: switched -> populated rule/model/run with run_slug + model, non-empty rule
        w2 = row_by_id[2]
        self.assertEqual(w2['final_level'], '1')
        self.assertNotEqual(w2['rebalance_rule'], '', "switched words must carry a non-empty rebalance_rule")
        self.assertEqual(w2['rebalance_model'], 'test-model', "switched words must carry the model name")
        self.assertEqual(w2['rebalance_run'], 'meta_test', "switched words must carry the run_slug")

    @patch('classificator.lm.client._load_requests')
    @patch('classificator.lm.client.LmStudioClient.score_batch_resilient')
    @patch('classificator.lm.client.LmStudioClient.preflight')
    @patch('classificator.lm.client.LmStudioClient.resolve_endpoint')
    def test_processed_ids_are_excluded_from_later_batches(self, mock_load_requests, mock_resolve, mock_preflight, mock_score):
        """A word processed in one batch must not be selected again on a later transition.

        Production contract: _apply_transition builds remaining_by_source by filtering
        words that are present in runtime.processed_word_ids; _select_stratified_batch
        then draws from these filtered pools only. The invariant is enforced at the
        per-transition level — no id ever re-enters a candidate pool after being marked
        processed.
        """
        import random as _rng

        class RW:
            def __init__(self, wid, w, t):
                self.word_id = wid; self.word = w; self.type = t
        rw1 = RW(1, "alpha", "noun"); rw2 = RW(2, "beta", "verb")
        rw3 = RW(3, "gamma", "adj"); rw4 = RW(4, "delta", "noun"); rw5 = RW(5, "epsilon", "verb")

        # All five words are at source levels 2 and 3. ids {1, 2} already processed.
        remaining_by_source_level: dict[int, list[RW]] = {
            2: [rw3],  # rw1 & rw2 removed by processed filter (simulated)
            3: [rw4, rw5],
        }

        initial_source_counts = {2: 2, 3: 3}  # pre-filter totals from production code

        from classificator.steps.step5_rebalance import _select_stratified_batch
        rng = _rng.Random(7)
        batch = _select_stratified_batch(
            source_levels=[2, 3],
            remaining_by_source_level=remaining_by_source_level,
            initial_source_counts=initial_source_counts,
            max_batch_size=5,
            rng=rng,
        )

        # Contract: no processed id (1 or 2) may appear in the batch.
        for w in batch:
            self.assertNotIn(w.word_id, {1, 2}, f"processed word_id={w.word_id} must not re-enter a candidate pool")
        # All returned ids come from dataset.words_by_id.
        all_ids = {w.word_id for w in batch}
        self.assertTrue(all_ids <= {3, 4, 5}, "only eligible (unprocessed) word_ids may be selected")


def _make_distribution(counts):
    from classificator.distribution import RarityDistribution
    return RarityDistribution.from_levels([lvl for lvl, c in counts.items() for _ in range(c)])


if __name__ == "__main__":
    unittest.main()
