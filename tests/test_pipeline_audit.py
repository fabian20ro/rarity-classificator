"""Audit actual producer CSVs, including stale original level columns."""
from unittest.mock import MagicMock

from classificator.models import LmApiFlavor, ResolvedEndpoint, RunCsvRow, Step3MergeStrategy
from classificator.run_csv_repository import RunCsvRepository
from classificator.steps.step3_compare import Step3Options, run_step3
from classificator.steps.step5_rebalance import Step5Options, run_step5
from classificator.tools.quality_audit import run_quality_audit
from classificator.transitions import LevelTransition


def test_comparison_and_rebalance_outputs_pass_real_semantic_audit(tmp_path):
    repo = RunCsvRepository()
    base, run_a, run_b, comparison, rebalanced, reference = [
        tmp_path / name for name in ["base.csv", "a.csv", "b.csv", "comparison.csv", "rebalanced.csv", "reference.csv"]
    ]
    repo.write_rows(base, ["word_id", "word", "type"], [["1", "om", "N"], ["2", "casă", "N"]])
    for path, levels in [(run_a, [1, 3]), (run_b, [2, 3])]:
        repo.append_run_rows(path, [
            RunCsvRow(wid, word, "N", level, "common", .9, "2026-10-15", "model", "audit")
            for wid, word, level in zip([1, 2], ["om", "casă"], levels)
        ])
    run_step3(Step3Options(
        run_a, run_b, None, comparison, tmp_path / "outliers.csv", base,
        merge_strategy=Step3MergeStrategy.ANY_EXTREMES,
    ), repo=repo)
    repo.write_rows(reference, ["word_id", "word", "final_level"], [["1", "om", "1"], ["2", "casă", "3"]])
    anchors = tmp_path / "anchors.txt"
    anchors.write_text("om\n", encoding="utf-8")

    def audit(path):
        result = run_quality_audit(
            candidate_csv=path, reference_csv=reference, anchor_l1_file=anchors,
            min_l1_jaccard=1, min_anchor_l1_precision=1, min_anchor_l1_recall=1, repo=repo,
        )
        assert result.passed
        assert result.level_column == "final_level"
        return result

    assert audit(comparison).distribution == {1: 1, 2: 0, 3: 1, 4: 0, 5: 0}
    lm = MagicMock()
    lm.resolve_endpoint.return_value = ResolvedEndpoint("http://offline.invalid", None, LmApiFlavor.OPENAI_COMPAT, "test")
    run_step5(Step5Options(
        "audit", "model", comparison, rebalanced, lower_ratio=1,
        transitions=[LevelTransition(3, 2)], skip_preflight=True,
    ), repo=repo, lm_client=lm, output_dir=tmp_path)
    assert audit(rebalanced).distribution == {1: 1, 2: 1, 3: 0, 4: 0, 5: 0}
