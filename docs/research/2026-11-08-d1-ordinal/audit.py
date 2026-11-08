"""Independent Decimal cost audit, frozen-input replay and label isolation; offline."""
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from decimal import Decimal, localcontext
from pathlib import Path
from tempfile import TemporaryDirectory

from classificator.evaluation.d1_ordinal import evaluate_d1_ordinal
from classificator.evaluation.d1_calibration import evaluate_d1_calibration

run,repo=map(Path,sys.argv[1:3])
pack=repo/'docs/research/2026-11-08-d1-score-v3'
inputs=pack/'inputs'
saved=repo/'docs/research/2026-11-08-d1-class-bias'

def read(path):
    with path.open() as f:
        return list(csv.DictReader(f))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

rows=read(run/'predictions.csv')
original=read(saved/'predictions.csv')
report=json.loads((run/'report.json').read_text())
protocol=json.loads((run/'protocol.json').read_text())
source_hashes=json.loads((pack/'protocol.json').read_text())['sources']
for path,digest in {**source_hashes,**protocol['inputs']}.items():
    assert sha(Path(path))==digest,path
for name,digest in protocol['implementation'].items():
    assert sha(repo/'src/classificator/evaluation'/name)==digest,name
for name,digest in json.loads((run/'manifest.json').read_text())['artifacts'].items():
    assert sha(run/name)==digest,name
assert len(rows)==len({r['word_id'] for r in rows})==200
assert [sum(r['cohort']==c for r in rows) for c in ['150','50']]==[150,50]
assert [{k:r[k] for k in original[0]} for r in rows]==original
refs={r['word_id']:r for r in read(inputs/'references.csv')}
assert all(refs[r['word_id']]['word']==r['word'] and refs[r['word_id']]['human_level']==r['human_level'] for r in rows)
# Literal loss matrix, independently calculated for action1..5 vs true class1..5.
matrix=[[0,0,1,2,3],[0,0,0,1,2],[1,0,0,0,1],[2,1,0,0,0],[3,2,1,0,0]]
max_risk_error=0.
with localcontext() as context:
    context.prec=50
    for row in rows:
        p=[Decimal(row[f'p_L{k}']) for k in range(1,6)]
        mass=sum(p)
        costs=[sum(weight*prob for weight,prob in zip(line,p))/mass for line in matrix]
        expected=min((k for k in range(1,6) if costs[k-1]<=min(costs)+Decimal('1e-12')),
                     key=lambda k:(abs(k-int(row['d1_native'])),k))
        assert int(row['d1_ordinal'])==expected
        for k,risk in enumerate(costs,1):
            difference=abs(float(risk)-float(row[f'ordinal_risk_L{k}']))
            assert difference<1e-14
            max_risk_error=max(max_risk_error,difference)
        assert costs[expected-1]<=costs[int(row['d1_native'])-1]+Decimal('1e-12')
        assert costs[expected-1]<=costs[2]+Decimal('1e-12')

for cohort,methods in report['cohorts'].items():
    group=[r for r in rows if r['cohort']==cohort]
    for method,subsets in methods.items():
        for subset,m in subsets.items():
            sub=[r for r in group if subset=='all' or (subset.startswith('true') and r['human_level']==subset[4:]) or (subset=='wordfreq_missing' and (not r['wordfreq'] or float(r['wordfreq'])==0))]
            errors=[abs(int(r[method])-int(r['human_level'])) for r in sub]
            assert m['n']==len(sub)
            assert m['severe']==sum(e>=2 for e in errors)
            assert m['excess_error_total']==sum(max(e-1,0) for e in errors)
            assert m['mae']==(sum(errors)/len(errors) if errors else None)
            assert m['predicted_counts']=={str(k):sum(int(r[method])==k for r in sub) for k in range(1,6)}
            for k in range(1,6):
                support=sum(int(r['human_level'])==k for r in sub)
                assert m['per_level'][str(k)]['support']==support
                assert m['per_level'][str(k)]['severe']==sum(int(r['human_level'])==k and abs(int(r[method])-k)>=2 for r in sub)
    for control,subsets in report['paired'][cohort].items():
        for subset,m in subsets.items():
            sub=[r for r in group if subset=='all' or (subset.startswith('true') and r['human_level']==subset[4:]) or (subset=='wordfreq_missing' and (not r['wordfreq'] or float(r['wordfreq'])==0))]
            pairs=[(abs(int(r[control])-int(r['human_level']))>=2,abs(int(r['d1_ordinal'])-int(r['human_level']))>=2) for r in sub]
            assert m==dict(severe_avoided=sum(a and not b for a,b in pairs),severe_introduced=sum(b and not a for a,b in pairs))
    for method,value in report['estimated_risk'][cohort].items():
        assert math.isclose(value,sum(float(r[f'ordinal_risk_L{r[method]}']) for r in group)/len(group),abs_tol=1e-14)
for fold,methods in report['by_fold'].items():
    group=[r for r in rows if r['cohort']=='150' and r['fold']==fold]
    for method,m in methods.items():
        assert m['severe']==sum(abs(int(r[method])-int(r['human_level']))>=2 for r in group)
        assert m['excess_error_total']==sum(max(abs(int(r[method])-int(r['human_level']))-1,0) for r in group)
for control in ['baseline','constant3']:
    checks={};better=False
    for cohort,methods in report['cohorts'].items():
        for subset in ['all','true1','true4','true5']:
            a,b=methods['d1_ordinal'][subset],methods[control][subset]
            for metric in ['severe','excess_error_total']:
                checks[f'{cohort}:{subset}:{metric}']=a[metric]<=b[metric] if a['n'] else None
                better |= subset=='all' and a[metric]<b[metric]
    assert report['decisions'][control+'_gate']==dict(passes=all(v is not False for v in checks.values()) and better,
        strict_improvement=better,no_regression_checks=checks)
assert report['fitted_parameters']==0 and report['automatic_promotion'] is False

def decisions(path):
    return [{k:v for k,v in r.items() if k=='word_id' or k=='d1_ordinal' or k.startswith('ordinal_risk_')} for r in read(path/'predictions.csv')]

with TemporaryDirectory(prefix='ordinal-audit-') as temporary:
    tmp=Path(temporary)
    evaluate_d1_ordinal(inputs,inputs/'references.csv',saved,tmp/'replay')
    for name in ['predictions.csv','report.json','severe-cases.csv']:
        assert (tmp/'replay'/name).read_bytes()==(run/name).read_bytes(),name
    evaluate_d1_calibration(inputs,inputs/'references.csv',tmp/'v3-replay')
    for name in ['predictions.csv','fits.json','report.json']:
        assert (tmp/'v3-replay'/name).read_bytes()==(pack/name).read_bytes(),name
    base_manifest=json.loads((saved/'manifest.json').read_text())
    reference_key=next(k for k in base_manifest['inputs'] if Path(k).name=='references.csv')
    for fold in ['0','1','2','3','4','50']:
        ids={r['word_id'] for r in rows if (r['cohort']=='50' if fold=='50' else r['cohort']=='150' and r['fold']==fold)}
        changed=[dict(r,human_level=str(1+int(r['human_level'])%5)) if r['word_id'] in ids else r for r in original]
        fixture=tmp/('input'+fold);fixture.mkdir()
        dump(fixture/'predictions.csv',changed)
        dump(fixture/'references.csv',[{k:r[k] for k in ['word_id','word','human_level']} for r in changed])
        m=json.loads(json.dumps(base_manifest))
        m['inputs'][reference_key]=sha(fixture/'references.csv')
        m['artifacts']['predictions.csv']=sha(fixture/'predictions.csv')
        (fixture/'manifest.json').write_text(json.dumps(m))
        evaluate_d1_ordinal(inputs,fixture/'references.csv',fixture,tmp/fold)
        assert decisions(run)==decisions(tmp/fold),fold
for path,digest in {**source_hashes,**protocol['inputs']}.items():
    assert sha(Path(path))==digest
result=dict(status='PASS',rows=200,fitted_parameters=0,protected_original_sources=len(source_hashes),
    unchanged_reference_and_comparator_columns=True,independent_decimal_loss_matrix=True,
    maximum_cost_difference=max_risk_error,independent_metrics_and_gates=True,
    v3_loader_extraction_replay_identical=True,byte_identical_replay=True,
    real_label_isolation_checks=6,network_db_guard='sitecustomize offline guard',
    audit_script_sha256=sha(Path(__file__)))
(run/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
