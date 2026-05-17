import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from classificator.models import LmApiFlavor, ScoreResult, ScoringOutputMode
from classificator.run_csv_repository import RunCsvRepository
from classificator.steps.step5_rebalance import Step5Options, run_step5
from classificator.transitions import LevelTransition


class TestStep5Contract(unittest.TestCase):
    def setUp(self):
        self.repo = RunCsvRepository()
        self.td = tempfile.TemporaryDirectory()
        self.tmp_rag_dir = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    @patch("classificator.steps.step5_rebalance._prepare_logs")
    def test_rebalance_uses_selected_word_id_mode_with_exact_positive_local_id_count(self, mock_prepare_logs):
        input_csv = self.tmp_rag_dir / "input.csv"
        output_csv = self.tmp_rag_dir / "output.csv"
        log_dir = self.tmp_rag_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        headers = ["word_id", "word", "type", "rarity_level"]
        rows = [
            ["101", "test1", "noun", "3"],
            ["102", "test2", "verb", "3"],
            ["103", "test3", "adj", "3"],
        ]
        with input_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

        mock_logs = MagicMock()
        mock_logs.run_log_path = log_dir / "run.log"
        mock_logs.failed_log_path = log_dir / "failed.log"
        mock_logs.switched_words_log_path = log_dir / "switched.log"
        mock_logs.checkpoint_path = log_dir / "checkpoint"
        mock_logs.progress_log_path = log_dir / "progress.log"
        mock_prepare_logs.return_value = mock_logs

        mock_client = MagicMock()
        mock_client.resolve_endpoint.return_value = MagicMock(
            endpoint="http://localhost:1234",
            flavor=LmApiFlavor.OPENAI_COMPAT,
            source="manual",
        )

        selected_word_ids = []

        def score_batch(batch, context):
            self.assertEqual(context.output_mode, ScoringOutputMode.SELECTED_WORD_IDS)
            self.assertEqual(context.expected_json_items, 1)
            self.assertCountEqual([word.word_id for word in batch], [101, 102, 103])
            # Step5 asks the LM for one batch-local id in 1..N. The parser/client
            # layer maps that local id back to the selected word_id; returning the
            # first word exercises the rebalance path without introducing 0-based ids.
            selected_word_ids.append(batch[0].word_id)
            return [
                ScoreResult(
                    word_id=batch[0].word_id,
                    word=batch[0].word,
                    type=batch[0].type,
                    rarity_level=2,
                    tag="selected",
                    confidence=1.0,
                )
            ]

        mock_client.score_batch_resilient.side_effect = score_batch

        options = Step5Options(
            run_slug="test-run",
            model="gpt-4o",
            input_csv_path=input_csv,
            output_csv_path=output_csv,
            batch_size=10,
            lower_ratio=1 / 3,
            skip_preflight=True,
            seed=1,
            transitions=[LevelTransition(from_level=3, to_level=2)],
        )

        run_step5(options, repo=self.repo, lm_client=mock_client, output_dir=log_dir)

        mock_client.score_batch_resilient.assert_called_once()
        progress = json.loads(mock_logs.progress_log_path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(progress["batch_target"], 1)
        self.assertEqual(progress["selected_common_count"], 1)
        self.assertNotIn(0, progress["selected_common_word_ids"])

        table = self.repo.read_table(output_csv)
        rows_by_id = {int(rec.values[0]): dict(zip(table.headers, rec.values)) for rec in table.records}
        for word_id, row in rows_by_id.items():
            expected = "2" if word_id == selected_word_ids[0] else "3"
            self.assertEqual(row["final_level"], expected)


if __name__ == "__main__":
    unittest.main()
