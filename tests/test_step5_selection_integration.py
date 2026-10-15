import csv
import json
from pathlib import Path
from unittest.mock import create_autospec

import pytest

from classificator.lm.client import LmStudioClient
from classificator.models import LmApiFlavor, ResolvedEndpoint, ScoreResult, ScoringOutputMode
from classificator.run_csv_repository import RunCsvRepository
from classificator.steps.step5_rebalance import Step5Options, run_step5
from classificator.transitions import LevelTransition


@pytest.fixture
def selection_run(tmp_path):
    repo = RunCsvRepository()
    input_path = tmp_path / "input.csv"
    repo.write_table_atomic(
        input_path,
        ["word_id", "word", "type", "rarity_level"],
        [
            ["101", "alpha", "noun", "2"],
            ["207", "beta", "noun", "2"],
            ["311", "gamma", "verb", "2"],
            ["419", "delta", "verb", "2"],
            ["503", "epsilon", "noun", "5"],
        ],
    )
    options = Step5Options(
        run_slug="selection",
        model="test-model",
        input_csv_path=input_path,
        output_csv_path=tmp_path / "output.csv",
        batch_size=4,
        lower_ratio=0.5,
        seed=17,
        transitions=[LevelTransition(from_level=2, to_level=1)],
    )
    client = create_autospec(LmStudioClient, instance=True)
    client.resolve_endpoint.return_value = ResolvedEndpoint(
        endpoint="http://localhost:1234/v1/chat/completions",
        models_endpoint=None,
        flavor=LmApiFlavor.OPENAI_COMPAT,
        source="test",
    )
    return repo, options, client


def _score(word_id, level=1):
    return ScoreResult(
        word_id=word_id,
        word=f"word-{word_id}",
        type="noun",
        rarity_level=level,
        tag="",
        confidence=1.0,
    )


def _read_json_lines(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_scored_batch_writes_exact_assignments_and_checkpoint(selection_run, tmp_path):
    repo, options, client = selection_run
    client.score_batch_resilient.return_value = [_score(207), _score(419)]

    run_step5(options, repo=repo, lm_client=client, output_dir=tmp_path)

    client.score_batch_resilient.assert_called_once()
    batch, context = client.score_batch_resilient.call_args.args
    assert {row.word_id for row in batch} == {101, 207, 311, 419}
    assert context.output_mode == ScoringOutputMode.SELECTED_WORD_IDS
    assert context.expected_json_items == 2
    assert context.forced_rarity_level == 1
    with options.output_csv_path.open(newline="") as handle:
        rows = {int(row["word_id"]): row for row in csv.DictReader(handle)}
    assert {word_id: int(row["final_level"]) for word_id, row in rows.items()} == {
        101: 2, 207: 1, 311: 2, 419: 1, 503: 5,
    }
    assert {word_id for word_id, row in rows.items() if row["rebalance_rule"]} == {207, 419}
    for word_id in (207, 419):
        assert rows[word_id]["rebalance_model"] == options.model
        assert rows[word_id]["rebalance_run"] == options.run_slug
    checkpoints = _read_json_lines(
        tmp_path / "rebalance/checkpoints/selection.checkpoint.jsonl"
    )
    assert len(checkpoints) == 1
    assert set(checkpoints[0]["processed_word_ids"]) == {101, 207, 311, 419}
    assert {item["word_id"]: item["new_level"] for item in checkpoints[0]["switched"]} == {
        207: 1, 419: 1,
    }
    progress = _read_json_lines(tmp_path / "rebalance/progress/selection.progress.jsonl")
    assert len(progress) == 1
    assert progress[0]["selected_common_word_ids"] == [207, 419]
    assert progress[0]["target_assigned"] == 2


@pytest.mark.parametrize(
    "scored",
    [
        [],
        [_score(207)],
        [_score(101), _score(207), _score(419)],
        [_score(207), _score(207)],
        [_score(207), _score(503)],
        [_score(207), _score(0)],
        [_score(207), _score(-1)],
        [_score(207), _score(419, level=2)],
    ],
    ids=["empty", "short", "excess", "duplicate", "foreign", "zero", "negative", "wrong-level"],
)
def test_malformed_selection_fails_before_assignments_or_checkpoint(selection_run, tmp_path, scored):
    repo, options, client = selection_run
    input_before = options.input_csv_path.read_bytes()
    client.score_batch_resilient.return_value = scored

    with pytest.raises(ValueError, match="Step5 selection"):
        run_step5(options, repo=repo, lm_client=client, output_dir=tmp_path)

    client.score_batch_resilient.assert_called_once()
    assert options.input_csv_path.read_bytes() == input_before
    assert not options.output_csv_path.exists()
    for artifact in (
        "checkpoints/selection.checkpoint.jsonl",
        "switched_words/selection.switched.jsonl",
        "progress/selection.progress.jsonl",
    ):
        assert not (tmp_path / "rebalance" / artifact).exists()
