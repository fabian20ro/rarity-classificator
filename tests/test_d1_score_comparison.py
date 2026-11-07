import json
import hashlib
import pytest
from tests.test_exact_form import write_csv
from scripts.compare_d1_score_experiment import compare


def fixture(root):
    refs = root / 'reference.csv'
    write_csv(refs, [dict(cohort=c, word_id=i, word=w, human_level=h, baseline_level=b)
        for c, i, w, h, b in [('150',1,'ac',1,1), ('150',2,'rar',5,4), ('50',3,'alt',5,4)]])
    for c, ids in [('150',[(1,'ac'),(2,'rar')]),('50',[(3,'alt')])]:
        for arm in 'ABCD':
            path=root/'campaigns'/c/arm/'predictions.csv';path.parent.mkdir(parents=True)
            write_csv(path, [dict(word_id=i, word=w, status='scored', rarity_level=(3 if arm=='A' else 4)) for i,w in ids])
    inputs = {}
    for c, ids in [('150',[(1,'ac'),(2,'rar')]),('50',[(3,'alt')])]:
        for name in ['vocabulary', 'historical', 'corrected']:
            path = root/'inputs'/c/(name+'.csv'); path.parent.mkdir(parents=True, exist_ok=True)
            write_csv(path, [dict(word_id=i,word=w,type='N') for i,w in ids])
            inputs[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (root/'protocol.json').write_text(json.dumps(dict(inputs=inputs)))
    return refs


def test_reports_separate_cohorts_and_protected_levels_without_hiding_regression(tmp_path):
    refs=fixture(tmp_path)
    report=compare(tmp_path, refs, tmp_path/'comparison')
    assert report['cohorts']['150']['A']['all']['severe']==2
    assert report['cohorts']['150']['B']['all']['excess_error_total']==2
    assert report['cohorts']['150']['B']['true5']['severe']==0
    assert report['cohorts']['50']['A']['true5']['severe']==1
    assert report['cohorts']['50']['B']['true5']['severe']==0
    assert report['decisions']['B']['passes_against_A'] is True
    assert report['cohorts']['150']['B']['all']['error_histogram']['3']==1
    assert json.loads((tmp_path/'comparison/report.json').read_text()) == report


@pytest.mark.parametrize('defect',['missing','failed','word','duplicate','range'])
def test_incomplete_or_mismatched_results_never_get_success_only_comparison(tmp_path,defect):
    refs=fixture(tmp_path)
    row=dict(word_id=3,word='alt',status='scored',rarity_level=4)
    if defect=='failed':row['status']='failed'
    if defect=='word':row['word']='altă'
    if defect=='range':row['rarity_level']=6
    rows=[row,row] if defect=='duplicate' else [row]
    if defect=='missing':rows=[dict(row,word_id=4)]
    write_csv(tmp_path/'campaigns/50/D/predictions.csv',rows)
    with pytest.raises(ValueError):compare(tmp_path,refs,tmp_path/'comparison')
    assert not (tmp_path/'comparison/report.json').exists()


def test_consistently_truncated_references_and_predictions_cannot_pass(tmp_path):
    refs=fixture(tmp_path)
    from tests.test_chat_judge import read
    write_csv(refs,[r for r in read(refs) if r['word_id']!='2'])
    for arm in 'ABCD':
        path=tmp_path/'campaigns/150'/arm/'predictions.csv'
        write_csv(path,[r for r in read(path) if r['word_id']!='2'])
    with pytest.raises(ValueError,match='frozen'):
        compare(tmp_path,refs,tmp_path/'comparison')
    assert not (tmp_path/'comparison/report.json').exists()
