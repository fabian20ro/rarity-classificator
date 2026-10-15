"""Upload must validate actual semantic gates before touching the database."""
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from classificator.cli import main
from classificator.models import UploadMode, WordLevel
from classificator.run_csv_repository import RunCsvRepository
from classificator.steps.step4_upload import Step4Options, run_step4
from classificator.upload_marker_writer import UploadMarkerWriter
from classificator.word_store import WordStore


@pytest.fixture
def upload_case(tmp_path):
    repo = RunCsvRepository()
    candidate = tmp_path / "candidate.csv"
    reference = tmp_path / "reference.csv"
    anchors = tmp_path / "anchors.txt"
    headers = ["word_id", "word", "final_level"]
    rows = [["1", "om", "1"], ["2", "casă", "2"]]
    repo.write_rows(candidate, headers, rows)
    repo.write_rows(reference, headers, rows)
    anchors.write_text("om\n", encoding="utf-8")
    options = Step4Options(
        final_csv_path=candidate,
        mode=UploadMode.PARTIAL,
        report_path=tmp_path / "report.csv",
        upload_batch_id="gate-regression",
        reference_csv=reference,
        anchor_l1_file=anchors,
    )
    store = MagicMock(spec=WordStore)
    store.fetch_all_word_levels.return_value = [WordLevel(1, 2), WordLevel(2, 2)]
    return repo, options, store


@pytest.mark.parametrize("mode", list(UploadMode))
@pytest.mark.parametrize("missing", ["reference_csv", "anchor_l1_file"])
def test_missing_audit_inputs_block_before_any_db_access(upload_case, mode, missing):
    repo, options, store = upload_case
    options = replace(options, mode=mode, **{missing: None})
    with pytest.raises(ValueError, match=missing):
        run_step4(options, repo=repo, word_store=store, marker_writer=UploadMarkerWriter(repo))
    assert not store.mock_calls
    assert not options.report_path.exists()


@pytest.mark.parametrize("threshold", [
    "min_l1_jaccard", "min_anchor_l1_precision", "min_anchor_l1_recall",
])
@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), -.1, 1.1])
def test_missing_or_invalid_threshold_blocks_before_db_access(upload_case, threshold, invalid):
    repo, options, store = upload_case
    options = replace(options, **{threshold: invalid})
    with pytest.raises(ValueError, match=threshold):
        run_step4(options, repo=repo, word_store=store, marker_writer=UploadMarkerWriter(repo))
    assert not store.mock_calls


@pytest.mark.parametrize("failed_metric", ["jaccard", "precision", "recall"])
def test_each_real_quality_gate_independently_blocks_upload(upload_case, failed_metric):
    repo, options, store = upload_case
    headers = ["word_id", "word", "final_level"]
    if failed_metric == "jaccard":
        repo.write_rows(options.reference_csv, headers, [["1", "om", "2"], ["2", "casă", "1"]])
    elif failed_metric == "precision":
        repo.write_rows(options.final_csv_path, headers, [["1", "om", "1"], ["2", "casă", "1"]])
        repo.write_rows(options.reference_csv, headers, [["1", "om", "1"], ["2", "casă", "1"]])
    else:
        options.anchor_l1_file.write_text("om\ncasă\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Quality audit failed"):
        run_step4(options, repo=repo, word_store=store, marker_writer=UploadMarkerWriter(repo))
    assert not store.mock_calls
    assert not options.report_path.exists()


def test_passing_real_audit_uploads_and_marks_only_candidate_rows(upload_case):
    repo, options, store = upload_case
    store.fetch_all_word_levels.return_value.append(WordLevel(3, 5))
    run_step4(options, repo=repo, word_store=store, marker_writer=UploadMarkerWriter(repo))
    store.update_rarity_levels_chunked.assert_called_once_with({1: 1})
    table = repo.read_table(options.final_csv_path)
    rows = [dict(zip(table.headers, record.values)) for record in table.records]
    assert [row["upload_status"] for row in rows] == ["uploaded", "already_matched"]
    assert [row["word_id"] for row in rows] == ["1", "2"]


@pytest.mark.parametrize("command", ["step4-upload", "step4"])
@pytest.mark.parametrize("missing_flag", ["--reference-csv", "--anchor-l1-file"])
def test_upload_cli_requires_both_audit_inputs(upload_case, tmp_path, command, missing_flag):
    _, options, store = upload_case
    args = ["--output-dir", str(tmp_path), command, "--final-csv", str(options.final_csv_path)]
    for flag, value in [("--reference-csv", options.reference_csv), ("--anchor-l1-file", options.anchor_l1_file)]:
        if flag != missing_flag:
            args.extend([flag, str(value)])
    with patch("classificator.cli.WordStore", return_value=store):
        with pytest.raises(SystemExit) as exc:
            main(args)
    assert exc.value.code == 2
    assert not store.mock_calls


@pytest.mark.parametrize("command", ["step4-upload", "step4"])
def test_upload_cli_enforces_default_thresholds(upload_case, tmp_path, command):
    repo, options, store = upload_case
    repo.write_rows(options.reference_csv, ["word_id", "word", "final_level"], [["2", "casă", "1"]])
    with patch("classificator.cli.WordStore", return_value=store):
        with pytest.raises(RuntimeError, match="l1_jaccard"):
            main([
                "--output-dir", str(tmp_path), command,
                "--final-csv", str(options.final_csv_path),
                "--reference-csv", str(options.reference_csv),
                "--anchor-l1-file", str(options.anchor_l1_file),
            ])
    assert not store.mock_calls
