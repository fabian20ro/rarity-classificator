import csv
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from src.classificator.lm.client import LmStudioClient
from src.classificator.run_csv_repository import RunCsvRepository
from src.classificator.tools.chain_rebalance_target_dist import ChainOptions, run_chain_rebalance
from src.classificator.tools.quality_audit import run_quality_audit


class TestChainQualityGate(unittest.TestCase):
    """Exercise the real CSV audit; replace only the network-backed LM step."""

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.input_csv = self.root / "input.csv"
        self.reference_csv = self.root / "reference.csv"
        self.anchors = self.root / "anchors.txt"
        self.prompt = self.root / "prompt.txt"
        self.prompt.write_text("test prompt", encoding="utf-8")
        # The campaign's fixed targets require >55,000 rows. Each source pool
        # must also satisfy its real minimum-count and ratio validations.
        with self.input_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["word_id", "word", "type", "final_level"])
            for word_id in range(60200):
                writer.writerow([word_id + 1, f"word{word_id}", "noun", word_id % 5 + 1])
        copyfile(self.input_csv, self.reference_csv)
        self.anchors.write_text(
            "\n".join(f"word{word_id}" for word_id in range(0, 60200, 5)),
            encoding="utf-8",
        )
        self.repo = RunCsvRepository()
        self.options = ChainOptions(
            input_csv=self.input_csv, model="unused", run_base="quality-gate",
            runs_dir=self.root / "runs", state_file=self.root / "state.json",
            resume=False, final_output_csv=None, batch_size=50, max_tokens=100,
            timeout_seconds=10, max_retries=0, system_prompt_file=self.prompt,
            user_template_file=self.prompt, reference_csv=self.reference_csv,
            anchor_l1_file=self.anchors, min_l1_jaccard=0.8,
            min_anchor_l1_precision=0.9, min_anchor_l1_recall=0.9,
            endpoint_option=None, base_url_option=None,
        )

    def run_chain(self):
        def finish_step(options, **kwargs):
            copyfile(options.input_csv_path, options.output_csv_path)

        with patch(
            "src.classificator.tools.chain_rebalance_target_dist.run_step5",
            side_effect=finish_step,
        ) as step, patch(
            "src.classificator.tools.chain_rebalance_target_dist.run_quality_audit",
            wraps=run_quality_audit,
        ) as audit:
            try:
                return run_chain_rebalance(
                    options=self.options, repo=self.repo,
                    lm_client=Mock(spec=LmStudioClient), output_dir=self.root,
                )
            finally:
                self.assertEqual(step.call_count, 8)
                audit.assert_called_once_with(
                    candidate_csv=self.options.runs_dir / "quality-gate_step8.csv",
                    reference_csv=self.reference_csv, anchor_l1_file=self.anchors,
                    min_l1_jaccard=0.8, min_anchor_l1_precision=0.9,
                    min_anchor_l1_recall=0.9, repo=self.repo,
                )

    def test_passing_audit_returns_final_csv(self):
        result = self.run_chain()
        self.assertEqual(result, self.options.runs_dir / "quality-gate_step8.csv")
        self.assertEqual(result.read_bytes(), self.input_csv.read_bytes())

    def test_failed_jaccard_blocks_result_despite_passing_anchors(self):
        self.reference_csv.write_text(
            "word_id,word,final_level\n999999,absent,1\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(RuntimeError, "Quality audit failed"):
            self.run_chain()

    def test_failed_anchors_block_result_despite_matching_reference(self):
        self.anchors.write_text("absent\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Quality audit failed"):
            self.run_chain()
