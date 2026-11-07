import json
from unittest.mock import Mock

import pytest

from classificator.evaluation.d1_score import collect_d1_score_csv
from tests.test_exact_form import write_csv
from tests.test_chat_judge import read
from tests.test_d1_scorer import models, response
from tests.test_d1_score_mode import QUESTION, native


def inputs(root):
    vocab = root / 'vocabulary.csv'
    evidence = root / 'evidence.csv'
    write_csv(vocab, [dict(word_id=i, word=w, type='N') for i, w in [(1, 'ata'), (2, 'ac')]])
    value = dict(coverage='source_bounded_not_exhaustive', valid_pos=['substantiv'], senses=[], missing_definition_pos=['substantiv'])
    write_csv(evidence, [dict(word_id=i, word=w, evidence_json=json.dumps(value)) for i, w in [(1, 'ata'), (2, 'ac')]])
    return vocab, evidence, root / 'out'


def test_csv_sequential_durable_failure_resume_archive_and_pin(tmp_path):
    args = inputs(tmp_path)
    http = Mock()
    http.get.return_value = response(models())
    http.post.side_effect = [response({}), response(native()), response(native())]
    kw = dict(model='d1-3b', question=QUESTION, http=http, runtime={'hash':'frozen'})
    with pytest.raises(RuntimeError, match='failed'):
        collect_d1_score_csv(*args, **kw)
    assert http.post.call_count == 1
    assert read(args[2] / 'predictions.csv')[0]['status'] == 'failed'
    old = (args[2] / 'records/1.json').read_bytes()
    collect_d1_score_csv(*args, **kw, retry_failed=True)
    assert [r['rarity_level'] for r in read(args[2] / 'predictions.csv')] == ['3', '3']
    assert list((args[2] / 'attempts').rglob('1.json'))[0].read_bytes() == old
    assert http.post.call_count == 3
    collect_d1_score_csv(*args, **kw)
    assert http.post.call_count == 3
    with pytest.raises(ValueError, match='changed'):
        collect_d1_score_csv(*args, **dict(kw, question=dict(QUESTION, instructions='changed')))
    assert http.post.call_count == 3
    record = json.loads((args[2] / 'records/1.json').read_text())
    assert record['request']['state']['evidence']['missing_definition_pos'] == ['substantiv']


@pytest.mark.parametrize('defect', ['label', 'identity', 'pos'])
def test_csv_invalid_evidence_fails_before_http(tmp_path, defect):
    args = inputs(tmp_path)
    rows = read(args[1]); value = json.loads(rows[0]['evidence_json'])
    if defect == 'label':
        value['human_level'] = 5
    elif defect == 'identity':
        rows[0]['word'] = 'ață'
    else:
        value['missing_definition_pos'] = []
    rows[0]['evidence_json'] = json.dumps(value); write_csv(args[1], rows)
    http = Mock()
    with pytest.raises(ValueError):
        collect_d1_score_csv(*args, model='d1-3b', question=QUESTION, http=http)
    http.get.assert_not_called(); http.post.assert_not_called()


def test_historical_incomplete_context_requires_explicit_frozen_opt_in(tmp_path):
    args = inputs(tmp_path)
    rows = read(args[1]); value = json.loads(rows[0]['evidence_json'])
    value['senses'] = [dict(pos='substantiv', definition='Trimitere incompletă.', number_restriction='', grammar=[], context=[], context_incomplete=True)]
    value['missing_definition_pos'] = []
    rows[0]['evidence_json'] = json.dumps(value); write_csv(args[1], rows)
    http = Mock(); http.get.return_value = response(models()); http.post.return_value = response(native())
    kw = dict(model='d1-3b', question=QUESTION, http=http)
    with pytest.raises(ValueError): collect_d1_score_csv(*args, **kw)
    http.post.assert_not_called()
    collect_d1_score_csv(*args, **kw, allow_historical_incomplete=True)
    receipt = json.loads((args[2] / 'records/1.json').read_text())
    assert receipt['request']['state']['evidence']['senses'][0]['context_incomplete'] is True
    assert json.loads((args[2] / 'manifest.json').read_text())['config']['allow_historical_incomplete'] is True


def test_existing_failure_blocks_implicit_resume_before_any_new_request(tmp_path):
    args = inputs(tmp_path)
    http = Mock(); http.get.return_value = response(models()); http.post.return_value = response({})
    kw = dict(model='d1-3b', question=QUESTION, http=http)
    with pytest.raises(RuntimeError): collect_d1_score_csv(*args, **kw)
    http.reset_mock(); http.post.return_value = response(native())
    with pytest.raises(RuntimeError, match='failed'):
        collect_d1_score_csv(*args, **kw)
    http.post.assert_not_called(); http.get.assert_not_called()
    assert len(read(args[2] / 'predictions.csv')) == 1
