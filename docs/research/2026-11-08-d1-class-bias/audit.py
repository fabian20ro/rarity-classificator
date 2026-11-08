"""Independent numerical/provenance/leakage audit; run with the offline guard."""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp, softmax

from classificator.evaluation.d1_class_bias import evaluate_d1_class_bias

run, repo = map(Path,sys.argv[1:3])
old = repo/'docs/research/2026-11-08-d1-temperature'
pack = repo/'docs/research/2026-11-08-d1-score-v3'
inputs=pack/'inputs'

def read(path):
    with path.open() as f:
        return list(csv.DictReader(f))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

rows=read(run/'predictions.csv')
by_id={r['word_id']:r for r in rows}
fits=json.loads((run/'fits.json').read_text())
report=json.loads((run/'report.json').read_text())
protocol=json.loads((run/'protocol.json').read_text())
sources=json.loads((pack/'protocol.json').read_text())['sources']
for path,digest in {**sources,**protocol['inputs']}.items():
    assert sha(Path(path))==digest,path
for name,digest in protocol['implementation'].items():
    assert sha(repo/'src/classificator/evaluation'/name)==digest,name
for name,digest in json.loads((run/'manifest.json').read_text())['artifacts'].items():
    assert sha(run/name)==digest,name
for name in ['predictions.csv','fits.json','report.json']:
    assert (run/'comparators'/name).read_bytes()==(old/name).read_bytes(),name
assert len(rows)==len(by_id)==200
refs={r['word_id']:r for r in read(inputs/'references.csv')}
assert all(r['human_level']==refs[r['word_id']]['human_level'] and r['word']==refs[r['word_id']]['word'] for r in rows)
assert [sum(r['cohort']==c for r in rows) for c in ['150','50']]==[150,50]

numeric_count=0
max_difference=0.
max_gradient=0.

def arrays(ids):
    selected=[by_id[i] for i in ids]
    z=np.log(np.maximum([[float(r[f'p_L{k}']) for k in range(1,6)] for r in selected],1e-12))
    y=np.array([int(r['human_level'])-1 for r in selected])
    return z,y

def loss(z,y,b):
    logits=z+b
    return float(np.mean(logsumexp(logits,axis=1)-logits[np.arange(len(y)),y]))

def audit_fit(fit,ids,penalty):
    global numeric_count,max_difference,max_gradient
    assert fit['train_ids']==ids
    assert fit['train_groups']==sorted({by_id[i]['group'] for i in ids})
    assert fit['lambda_']==penalty
    z,y=arrays(ids); b=np.array(fit['bias'])
    assert abs(sum(b))<1e-12
    assert abs(loss(z,y,b)-fit['training_nll'])<1e-12
    if penalty is None:
        assert list(b)==[0]*5
        return
    def objective(b):
        return loss(z,y,b)+penalty/2*float(b@b)
    def jac(b):
        return np.mean(softmax(z+b,axis=1)-np.eye(5)[y],axis=0)+penalty*b
    solution=minimize(objective,np.zeros(5),jac=jac,method='BFGS',options={'gtol':1e-10,'maxiter':2000})
    # BFGS may report precision loss at machine accuracy; check residual and objective directly.
    assert max(abs(jac(solution.x)))<1e-7
    difference=float(max(abs(solution.x-b)))
    assert difference<1e-6
    assert abs(objective(b)-fit['penalized_objective'])<1e-12
    residual=float(max(abs(jac(b))))
    assert residual<=1.01e-9
    max_difference=max(max_difference,difference);max_gradient=max(max_gradient,residual)
    numeric_count+=1

selections={}
for name,model in fits.items():
    outer=[r for r in rows if r['cohort']=='150' and (name=='full150' or r['fold']!=name.split(':')[1])]
    train_ids=[r['word_id'] for r in outer]
    held_folds=sorted({r['fold'] for r in outer})
    candidates=[]
    for candidate in model['candidates']:
        penalty=candidate['lambda_']; total=0.; covered=[]
        assert set(candidate['splits'])==set(held_folds)
        for fold,split in candidate['splits'].items():
            training=[r['word_id'] for r in outer if r['fold']!=fold]
            validation=[r['word_id'] for r in outer if r['fold']==fold]
            assert split['validation_ids']==validation
            assert set(training).isdisjoint(validation)
            audit_fit(split['fit'],training,penalty)
            z,y=arrays(validation)
            nll=loss(z,y,np.array(split['fit']['bias']))
            assert abs(nll-split['validation_nll'])<1e-12
            total+=nll*len(validation); covered+=validation
        assert sorted(covered)==sorted(train_ids)
        pooled=total/len(train_ids)
        assert abs(pooled-candidate['inner_nll'])<1e-12
        candidates.append((penalty,pooled))
    assert [c[0] for c in candidates]==[None,10,1,.1,.01]
    best=min(c[1] for c in candidates)
    selected=next(p for p,nll in candidates if nll<=best+1e-10)
    assert selected==model['selected_lambda']
    audit_fit(model['fit'],train_ids,selected)
    selections[name]=selected

for r in rows:
    key='outer:'+r['fold'] if r['cohort']=='150' else 'full150'
    b=np.array(fits[key]['fit']['bias']);z,y=arrays([r['word_id']])
    p=softmax(z[0]+b)
    assert np.allclose(p,[float(r[f'bias_p_L{k}']) for k in range(1,6)],atol=1e-14,rtol=0)
    assert int(r['d1_class_bias'])==int(np.searchsorted(np.cumsum(p),.5)+1)
    assert abs(loss(z,y,b)-float(r['bias_nll']))<1e-12

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
    for control,subsets in report['paired'][cohort].items():
        for subset,m in subsets.items():
            sub=[r for r in group if subset=='all' or (subset.startswith('true') and r['human_level']==subset[4:]) or (subset=='wordfreq_missing' and (not r['wordfreq'] or float(r['wordfreq'])==0))]
            pairs=[(abs(int(r[control])-int(r['human_level']))>=2,abs(int(r['d1_class_bias'])-int(r['human_level']))>=2) for r in sub]
            assert m==dict(severe_avoided=sum(a and not b for a,b in pairs),severe_introduced=sum(b and not a for a,b in pairs))
    q=np.array([[float(r[f'bias_p_L{k}']) for k in range(1,6)] for r in group])
    y=np.array([int(r['human_level'])-1 for r in group])
    metrics=report['probability_metrics'][cohort]['class_bias']
    assert math.isclose(float(np.mean(-np.log(q[np.arange(len(y)),y]))),metrics['nll'],abs_tol=1e-12)
    assert math.isclose(float(np.mean(np.sum((q-np.eye(5)[y])**2,axis=1))),metrics['brier'],abs_tol=1e-12)

checks={};better=False
for c,methods in report['cohorts'].items():
    for subset in ['all','true1','true4','true5']:
        a,b=methods['d1_class_bias'][subset],methods['baseline'][subset]
        for metric in ['severe','excess_error_total']:
            checks[f'{c}:{subset}:{metric}']=a[metric]<=b[metric] if a['n'] else None
            better |= subset=='all' and a[metric]<b[metric]
assert report['decisions']['baseline_gate']==dict(passes=all(v is not False for v in checks.values()) and better,strict_improvement=better,no_regression_checks=checks)

def pred(path,ids):
    return {r['word_id']:{k:v for k,v in r.items() if k not in {'human_level','bias_nll'}} for r in read(path/'predictions.csv') if r['word_id'] in ids}

with TemporaryDirectory(prefix='bias-audit-') as temporary:
    tmp=Path(temporary)
    evaluate_d1_class_bias(inputs,inputs/'references.csv',tmp/'replay')
    for name in ['predictions.csv','fits.json','report.json','severe-cases.csv']:
        assert (tmp/'replay'/name).read_bytes()==(run/name).read_bytes(),name
    original=read(inputs/'references.csv')
    for fold in ['0','1','2','3','4','50']:
        ids={r['word_id'] for r in rows if (r['cohort']=='50' if fold=='50' else r['cohort']=='150' and r['fold']==fold)}
        changed=[dict(r,human_level=1+int(r['human_level'])%5) if r['word_id'] in ids else r for r in original]
        dump(tmp/'references.csv',changed)
        out=tmp/fold
        evaluate_d1_class_bias(inputs,tmp/'references.csv',out)
        updated=json.loads((out/'fits.json').read_text())
        if fold=='50':
            assert fits==updated
            ids=set(by_id)
        else:
            assert fits['outer:'+fold]==updated['outer:'+fold]
        assert pred(run,ids)==pred(out,ids),fold
for path,digest in {**sources,**protocol['inputs']}.items():
    assert sha(Path(path))==digest
result=dict(status='PASS',rows=200,protected_original_sources=len(sources),
    independent_regularized_fits=numeric_count,max_coefficient_difference=max_difference,
    max_gradient_residual=max_gradient,selected_lambdas=selections,all_inner_splits_and_pooled_selection_verified=True,
    independent_distributions_medians_metrics_and_gates=True,unchanged_comparators=True,
    byte_identical_replay=True,real_label_isolation_checks=6,network_db_guard='sitecustomize offline guard',
    audit_script_sha256=sha(Path(__file__)))
(run/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
