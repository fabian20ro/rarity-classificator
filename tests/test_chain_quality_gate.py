import csv
from dataclasses import replace
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

    def run_chain(self, *, expect_audit=True):
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
                if expect_audit:
                    audit.assert_called_once_with(
                        candidate_csv=self.options.runs_dir / "quality-gate_step8.csv",
                        reference_csv=self.reference_csv,
                        anchor_l1_file=self.anchors,
                        min_l1_jaccard=0.8, min_anchor_l1_precision=0.9,
                        min_anchor_l1_recall=0.9, repo=self.repo,
                    )
                else:
                    audit.assert_not_called()

    def test_passing_audit_returns_final_csv(self):
        result = self.run_chain()
        self.assertEqual(result, self.options.runs_dir / "quality-gate_step8.csv")
        self.assertEqual(result.read_bytes(), self.input_csv.read_bytes())

    def test_no_reference_no_anchor_skips_audit_and_returns_final_csv(self):
        """Audit is opt-in: with no reference and no anchors, the chain skips run_quality_audit.

        The audit-present cases above pin the gate call; this pins the other
        branch. run_chain_rebalance only calls run_quality_audit when
        options.reference_csv or options.anchor_l1_file is set, so a regression
        that audits unconditionally would raise or block here, and one that
        drops the skip result would return no csv at all.
        """
        self.options = replace(
            self.options,
            reference_csv=None,
            anchor_l1_file=None,
            min_l1_jaccard=None,
            min_anchor_l1_precision=None,
            min_anchor_l1_recall=None,
        )
        result = self.run_chain(expect_audit=False)
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

    def test_failed_precision_blocks_despite_passing_recall(self):
        """Anchor precision and recall are independent gates; precision alone blocks.

        test_failed_anchors_block_result couples both metrics: a single absent
        anchor zeroes precision and recall together. This case isolates the
        precision branch — the candidate retains every seeded anchor (recall
        stays 1.0 >= 0.9) but also emits extra level-1 words the anchor set does
        not cover, so precision drops below the floor. A regression that removes
        or swaps the precision check would let this candidate pass on recall
        alone; asserting on the QualityAuditResult return values distinguishes it
        in a way the chain's opaque RuntimeError cannot.
        """
        candidate_csv = self.root / "candidate.csv"
        with candidate_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["word_id", "word", "final_level"])
            for word_id in range(1, 9):
                writer.writerow([word_id, f"keep{word_id}", 1])
            writer.writerow([9, "extra", 3])
        anchors = self.root / "anchors.txt"
        anchors.write_text("keep1\nkeep2\n", encoding="utf-8")

        result = run_quality_audit(
            candidate_csv=candidate_csv,
            anchor_l1_file=anchors,
            min_anchor_l1_precision=0.9,
            min_anchor_l1_recall=0.9,
            repo=self.repo,
        )

        self.assertFalse(result.passed)
        self.assertIsNone(result.l1_jaccard)
        self.assertLess(result.anchor_precision, 0.9)
        self.assertGreaterEqual(result.anchor_recall, 0.9)
        self.assertEqual(len(result.failures), 1)
        self.assertRegex(result.failures[0], "anchor_l1_precision")

    def test_failed_recall_blocks_despite_passing_precision(self):
        """Anchor precision and recall are independent gates; recall alone blocks.

        test_failed_precision_blocks_despite_passing_recall isolates the
        precision branch; this case isolates the recall branch. The candidate
        retains one of the eight seeded anchors (recall = 1/8 = 0.125 < 0.9)
        while its extra level-1 word keeps precision at 0.5 as well — both
        gates fail, but the recall assertion is the distinguishing one: a
        regression that removes or swaps the min_anchor_l1_recall check would
        still trip the precision gate and raise the chain's opaque RuntimeError,
        so only asserting on the QualityAuditResult return values catches it.
        """
        candidate_csv = self.root / "candidate.csv"
        with candidate_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["word_id", "word", "final_level"])
            writer.writerow([1, "keep1", 1])
            writer.writerow([2, "keep2", 1])
            writer.writerow([3, "extra", 1])
        anchors = self.root / "anchors.txt"
        anchors.write_text(
            "\n".join(f"keep{i}" for i in range(1, 9)), encoding="utf-8"
        )

        result = run_quality_audit(
            candidate_csv=candidate_csv,
            anchor_l1_file=anchors,
            min_anchor_l1_precision=0.9,
            min_anchor_l1_recall=0.9,
            repo=self.repo,
        )

        self.assertFalse(result.passed)
        self.assertLess(result.anchor_recall, 0.9)
        self.assertLess(result.anchor_precision, 0.9)
        self.assertEqual(len(result.failures), 2)
        self.assertTrue(
            any("anchor_l1_recall" in failure for failure in result.failures)
        )
