import copy
import json
from unittest.mock import Mock

import pytest

from classificator.models import BaseWordRow
from classificator.scoring.d1 import D1Scorer
from tests.test_d1_scorer import models, response

QUESTION = dict(type='score', instructions='Exact form.', criteria=['one', 'two', 'three', 'four', 'five'])


def native(probabilities=(0, 0, .5, 0, .5)):
    return dict(answers=dict(rarity=dict(type='score', score=99, legend=dict(enumerate(QUESTION['criteria'])), probabilities=dict(enumerate(probabilities)))))


def test_score_lower_median_tie_not_native_scalar_or_mode_and_question_frozen():
    http = Mock()
    http.get.return_value = response(models())
    http.post.return_value = response(native())
    question = copy.deepcopy(QUESTION)
    scorer = D1Scorer(model='d1-3b', http=http, question=question)
    question['criteria'][0] = 'mutated'
    outcomes = scorer.score_batch([BaseWordRow(1, 'ata', ''), BaseWordRow(2, 'ată', '')])
    assert [o.rarity_level for o in outcomes] == [3, 3]
    assert [o.request['state']['word'] for o in outcomes] == ['ata', 'ată']
    assert outcomes[0].request['questions']['rarity'] == QUESTION
    assert json.loads(outcomes[0].response) == json.loads(json.dumps(native()))
    assert [c[0] for c in http.mock_calls if c[0] in {'get', 'post'}] == ['get', 'post', 'get', 'post']


@pytest.mark.parametrize('change', ['legend', 'type', 'keys', 'nan', 'total', 'bool'])
def test_score_rejects_malformed_native_receipt(change):
    body = json.loads(json.dumps(native()))
    a = body['answers']['rarity']
    if change == 'legend':
        a['legend']['0'] = 'wrong'
    elif change == 'type':
        a['type'] = 'choice'
    elif change == 'keys':
        a['probabilities']['5'] = a['probabilities'].pop('0')
    elif change == 'nan':
        a['probabilities']['0'] = float('nan')
    elif change == 'bool':
        a['probabilities']['0'] = False
    else:
        a['probabilities']['0'] = .2
    http = Mock()
    http.get.return_value = response(models())
    http.post.return_value = response(body)
    o = D1Scorer(model='d1-3b', http=http, question=QUESTION).score_batch([BaseWordRow(1, 'ata', '')])[0]
    assert o.status == 'failed'
    assert o.rarity_level is None
    assert o.response == http.post.return_value.text


@pytest.mark.parametrize('question', [dict(QUESTION, criteria=['one'] * 5), dict(QUESTION, type='noul'), dict(QUESTION, instructions=''), dict(QUESTION, human=5)])
def test_invalid_question_fails_before_http(question):
    http = Mock()
    with pytest.raises(ValueError):
        D1Scorer(model='d1-3b', http=http, question=question)
    http.assert_not_called()
