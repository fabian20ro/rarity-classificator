"""Public matching APIs share the original normalized edit-distance contract."""
import json

import pytest

from classificator.fuzzy_word_matcher import matches, matches_with_distance
from classificator.lm.response_parser import LmStudioResponseParser
from classificator.models import BaseWordRow
from classificator.step2_metrics import Step2Metrics


@pytest.mark.parametrize("expected,actual,distance", [
    ("abcdef", "abxyzw", 4),
    ("abcde", "abxyz", 3),
    ("ăăă", "b", 3),
    ("ab", "cd", 2),
    ("ăn", "AN", 0),
    ("", "abc", 3),
])
def test_public_matchers_agree_on_full_normalized_distance(expected, actual, distance):
    for left, right in [(expected, actual), (actual, expected)]:
        assert matches_with_distance(left, right) == (distance <= 2, distance)
        assert matches(left, right) is (distance <= 2)


def test_score_parser_does_not_assign_distant_same_prefix_word_to_pending_row():
    row = BaseWordRow(word_id=101, word="abcdef", type="N")
    body = json.dumps({"choices": [{"message": {"content": json.dumps([{
        "word_id": 999, "word": "abxyzw", "type": "N", "rarity_level": 1,
        "confidence": 0.9,
    }])}}]})
    with pytest.raises(RuntimeError, match="No valid results parsed"):
        LmStudioResponseParser().parse(batch=[row], response_body=body)


def test_score_parser_retains_single_edit_recovery_for_wrong_id():
    row = BaseWordRow(word_id=101, word="abcdef", type="N")
    body = json.dumps({"choices": [{"message": {"content": json.dumps([{
        "word_id": 999, "word": "abcdex", "type": "N", "rarity_level": 2,
        "confidence": 0.9,
    }])}}]})
    result = LmStudioResponseParser().parse(batch=[row], response_body=body)
    assert [(score.word_id, score.word, score.rarity_level) for score in result.scores] == [
        (101, "abcdef", 2),
    ]
    assert result.unresolved == []


def test_score_parser_counts_fuzzy_recovery_metric_only_for_fuzzy_matches():
    metrics = Step2Metrics()
    parser = LmStudioResponseParser(metrics=metrics)

    # An exact word_id match never routes through the fuzzy matcher.
    exact_row = BaseWordRow(word_id=101, word="abcdef", type="N")
    exact_body = json.dumps({"choices": [{"message": {"content": json.dumps([
        {"word_id": 101, "word": "abcdef", "type": "N",
         "rarity_level": 1, "confidence": 0.9},
    ])}}]})
    parser.parse(batch=[exact_row], response_body=exact_body)
    assert metrics.fuzzy_match_count == 0

    # A wrong word_id recovered within two edits is a counted fuzzy match.
    fuzzy_row = BaseWordRow(word_id=101, word="abcdef", type="N")
    fuzzy_body = json.dumps({"choices": [{"message": {"content": json.dumps([
        {"word_id": 999, "word": "abcdex", "type": "N",
         "rarity_level": 2, "confidence": 0.9},
    ])}}]})
    result = parser.parse(batch=[fuzzy_row], response_body=fuzzy_body)
    assert metrics.fuzzy_match_count == 1
    assert [score.word_id for score in result.scores] == [101]
    assert result.unresolved == []


def test_score_parser_reuses_row_across_type_when_fuzzy_match_hits():
    # Batch row type is "N"; LM returns the word with type "V". Same-type
    # fuzzy fails, but the cross-type fallback still matches within two
    # edits, so the word is not silently dropped.
    row = BaseWordRow(word_id=101, word="abcdef", type="N")
    body = json.dumps({"choices": [{"message": {"content": json.dumps([{
        "word_id": 999, "word": "abcdex", "type": "V", "rarity_level": 3,
        "confidence": 0.9,
    }])}}]})
    result = LmStudioResponseParser().parse(batch=[row], response_body=body)
    assert [(score.word_id, score.word, score.rarity_level) for score in result.scores] == [
        (101, "abcdef", 3),
    ]
    assert result.unresolved == []
