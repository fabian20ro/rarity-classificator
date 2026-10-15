import json
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from src.classificator.csv_codec import CsvFormatError
from src.classificator.lm.client import LmStudioClient
from src.classificator.models import LmApiFlavor, ResolvedEndpoint, RunCsvRow, ScoreResult
from src.classificator.run_csv_repository import RunCsvRepository
from src.classificator.steps.step2_score import Step2Options, run_step2


@pytest.fixture
def scoring_run(tmp_path):
    repo = RunCsvRepository()
    base = tmp_path / "base.csv"
    output = tmp_path / "run.csv"
    repo.write_rows(base, ["word_id", "word", "type"], [
        [str(i), f"word-{i}", "noun"] for i in range(1, 11)
    ])
    existing = [
        RunCsvRow(i, f"word-{i}", "noun", 1 if i <= 10 else 3,
                  "old-tag", 0.5, "old-time", "old-model", "old-run")
        for i in range(1, 12)
    ]
    repo.rewrite_run_rows_atomic(output, existing)
    options = Step2Options("rescore", "new-model", base, output, batch_size=5, force=True)
    client = MagicMock(spec=LmStudioClient)
    client.metrics = None
    client.resolve_endpoint.return_value = ResolvedEndpoint(
        "http://unused.invalid/v1/chat/completions", None, LmApiFlavor.OPENAI_COMPAT, "test"
    )
    return repo, options, client, tmp_path, existing


def _new_scores(batch, context):
    return [ScoreResult(row.word_id, row.word, row.type, 2, "new-tag", 0.9) for row in batch]


def test_force_replaces_scores_without_duplicate_ids_or_distribution_counts(scoring_run, capsys):
    repo, options, client, output_dir, existing = scoring_run
    client.score_batch_resilient.side_effect = _new_scores

    run_step2(options, repo=repo, lm_client=client, output_dir=output_dir)

    actual = repo.load_run_rows(options.output_csv_path)
    assert len(actual) == len({row.word_id for row in actual}) == 11
    for row in actual[:10]:
        assert (row.rarity_level, row.tag, row.confidence, row.model, row.run_slug) == (
            2, "new-tag", 0.9, "new-model", "rescore"
        )
        assert row.scored_at != "old-time"
    assert actual[10] == existing[10]
    assert "distribution=[1:0(0.0%) 2:10(90.9%) 3:1(9.1%)" in capsys.readouterr().out


@pytest.mark.parametrize("interruption", [None, RuntimeError("LM unavailable"), KeyboardInterrupt()])
def test_force_partial_progress_keeps_failed_unprocessed_and_unrelated_rows_resumable(scoring_run, interruption):
    repo, options, client, output_dir, existing = scoring_run
    calls = 0

    def score_or_interrupt(batch, context):
        nonlocal calls
        calls += 1
        if calls == 1:
            # Partial salvage: only two of the first five words received scores.
            return _new_scores([row for row in batch if row.word_id in {1, 3}], context)
        if interruption is not None:
            raise interruption
        return []

    client.score_batch_resilient.side_effect = score_or_interrupt
    if interruption is None:
        run_step2(options, repo=repo, lm_client=client, output_dir=output_dir)
        state = json.loads((output_dir / "runs" / "rescore.state.json").read_text())
        assert (state["scored"], state["failed"], state["pending"]) == (2, 8, 8)
    else:
        with pytest.raises(type(interruption)):
            run_step2(options, repo=repo, lm_client=client, output_dir=output_dir)

    persisted = repo.load_run_rows(options.output_csv_path)
    assert len(persisted) == 11
    assert {row.word_id for row in persisted if row.rarity_level == 2} == {1, 3}
    assert [row for row in persisted if row.word_id not in {1, 3}] == [
        row for row in existing if row.word_id not in {1, 3}
    ]

    client.score_batch_resilient.side_effect = _new_scores
    run_step2(options, repo=repo, lm_client=client, output_dir=output_dir)
    resumed = repo.load_run_rows(options.output_csv_path)
    assert [row.rarity_level for row in resumed] == [2] * 10 + [3]
    assert resumed[-1] == existing[-1]


@pytest.mark.parametrize("failed_replace", [1, 2])
def test_force_atomic_replace_failure_preserves_last_complete_csv(scoring_run, monkeypatch, failed_replace):
    from src.classificator import csv_codec

    repo, options, client, output_dir, existing = scoring_run
    client.score_batch_resilient.side_effect = _new_scores
    original_bytes = options.output_csv_path.read_bytes()
    real_replace = csv_codec.os.replace
    replacements = 0

    def failing_replace(source, destination):
        nonlocal replacements
        replacements += 1
        if replacements == failed_replace:
            raise OSError("atomic replacement failed")
        real_replace(source, destination)

    monkeypatch.setattr(csv_codec.os, "replace", failing_replace)
    with pytest.raises(OSError, match="atomic replacement failed"):
        run_step2(options, repo=repo, lm_client=client, output_dir=output_dir)

    persisted = repo.load_run_rows(options.output_csv_path)
    if failed_replace == 1:
        assert options.output_csv_path.read_bytes() == original_bytes
        assert persisted == existing
    else:
        assert [row.rarity_level for row in persisted] == [2] * 5 + [1] * 5 + [3]
        assert persisted[5:] == existing[5:]

    monkeypatch.setattr(csv_codec.os, "replace", real_replace)
    run_step2(options, repo=repo, lm_client=client, output_dir=output_dir)
    assert [row.rarity_level for row in repo.load_run_rows(options.output_csv_path)] == [2] * 10 + [3]


def test_normal_scoring_only_appends_pending_ids(scoring_run):
    repo, options, client, output_dir, existing = scoring_run
    repo.rewrite_run_rows_atomic(options.output_csv_path, [existing[0], existing[-1]])
    client.score_batch_resilient.side_effect = _new_scores

    run_step2(replace(options, force=False), repo=repo, lm_client=client, output_dir=output_dir)

    actual = repo.load_run_rows(options.output_csv_path)
    assert actual[0] == existing[0]
    assert actual[-1] == existing[-1]
    assert [row.rarity_level for row in actual] == [1] + [2] * 9 + [3]


def test_force_keeps_strict_duplicate_validation(scoring_run):
    repo, options, client, output_dir, existing = scoring_run
    repo.append_run_rows(options.output_csv_path, [existing[0]])

    with pytest.raises(CsvFormatError, match="Duplicate word_id=1"):
        run_step2(options, repo=repo, lm_client=client, output_dir=output_dir)

    client.score_batch_resilient.assert_not_called()
