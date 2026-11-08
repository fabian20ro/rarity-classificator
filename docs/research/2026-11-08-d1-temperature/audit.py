"""Independent audit: requires installed scipy/numpy, never installs or connects."""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp, softmax

from classificator.evaluation.d1_temperature import evaluate_d1_temperature

run, repo = map(Path, sys.argv[1:3])
pack = repo / 'docs/research/2026-11-08-d1-score-v3'
inputs = pack / 'inputs'

def read(path):
    with path.open() as f:
        return list(csv.DictReader(f))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, rows):
    with path.open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

rows = read(run / 'predictions.csv')
fits = json.loads((run / 'fits.json').read_text())
report = json.loads((run / 'report.json').read_text())
protocol = json.loads((run / 'protocol.json').read_text())
sources = json.loads((pack / 'protocol.json').read_text())['sources']
for path, digest in {**sources, **protocol['inputs']}.items():
    assert sha(Path(path)) == digest, path
for name, digest in protocol['implementation'].items():
    assert sha(repo / 'src/classificator/evaluation' / name) == digest, name
for name, digest in json.loads((run / 'manifest.json').read_text())['artifacts'].items():
    assert sha(run / name) == digest, name
for name in ['predictions.csv', 'fits.json', 'report.json']:
    assert (run / 'comparators' / name).read_bytes() == (pack / name).read_bytes(), name
assert len(rows) == len({r['word_id'] for r in rows}) == 200
assert [sum(r['cohort'] == c for r in rows) for c in ['150', '50']] == [150, 50]
refs = {r['word_id']:r for r in read(inputs / 'references.csv')}
assert all(refs[r['word_id']]['human_level'] == r['human_level'] and refs[r['word_id']]['word'] == r['word'] for r in rows)
solver = {}
for name, fit in fits.items():
    train = [r for r in rows if r['cohort'] == '150' and (name == 'full150' or r['fold'] != name.split(':')[1])]
    assert fit['train_ids'] == [r['word_id'] for r in train]
    assert fit['train_groups'] == sorted({r['group'] for r in train})
    logs = np.log(np.maximum([[float(r[f'p_L{k}']) for k in range(1,6)] for r in train], 1e-12))
    y = np.array([int(r['human_level'])-1 for r in train])
    def objective(beta):
        z = logs * beta
        return float(np.mean(logsumexp(z, axis=1) - z[np.arange(len(y)),y]))
    fit2 = minimize_scalar(objective, bounds=(.05,20), method='bounded', options={'xatol':1e-12})
    assert fit2.success
    assert abs(fit2.x - fit['inverse_temperature']) < 1e-5
    assert abs(objective(fit['inverse_temperature']) - fit['training_nll']) < 1e-12
    solver[name] = {'scipy_beta':float(fit2.x), 'beta_difference':abs(fit2.x-fit['inverse_temperature'])}
for r in rows:
    p = np.array([float(r[f'p_L{k}']) for k in range(1,6)])
    q = softmax(np.log(np.maximum(p,1e-12))/float(r['temperature']))
    assert np.allclose(q,[float(r[f'q_L{k}']) for k in range(1,6)],atol=1e-14,rtol=0)
    assert int(r['d1_temperature']) == int(np.searchsorted(np.cumsum(q),.5)+1)
    assert int(np.argmax(p)) == int(np.argmax(q))
for cohort, methods in report['cohorts'].items():
    group = [r for r in rows if r['cohort']==cohort]
    for method, subsets in methods.items():
        for subset, metrics in subsets.items():
            sub = [r for r in group if subset == 'all' or (subset.startswith('true') and r['human_level'] == subset[4:]) or (subset=='wordfreq_missing' and (not r['wordfreq'] or float(r['wordfreq'])==0))]
            errors = [abs(int(r[method])-int(r['human_level'])) for r in sub]
            assert metrics['n'] == len(errors)
            assert metrics['severe'] == sum(e>=2 for e in errors)
            assert metrics['excess_error_total'] == sum(max(e-1,0) for e in errors)
            assert metrics['mae'] == (sum(errors)/len(errors) if errors else None)
            assert metrics['exact'] == sum(e==0 for e in errors)
    for name in ['native','temperature']:
        pp = np.array([[float(r[f'p_L{k}']) for k in range(1,6)] for r in group])
        z = np.log(np.maximum(pp,1e-12))
        if name=='temperature':
            z /= np.array([float(r['temperature']) for r in group])[:,None]
        y=np.array([int(r['human_level'])-1 for r in group])
        nll=float(np.mean(logsumexp(z,axis=1)-z[np.arange(len(y)),y]))
        brier=float(np.mean(np.sum((softmax(z,axis=1)-np.eye(5)[y])**2,axis=1)))
        assert math.isclose(nll,report['probability_metrics'][cohort][name]['nll'],abs_tol=1e-12)
        assert math.isclose(brier,report['probability_metrics'][cohort][name]['brier'],abs_tol=1e-12)
    for control, subsets in report['paired'][cohort].items():
        for subset, metrics in subsets.items():
            sub = [r for r in group if subset == 'all' or (subset.startswith('true') and r['human_level'] == subset[4:]) or (subset=='wordfreq_missing' and (not r['wordfreq'] or float(r['wordfreq'])==0))]
            pairs=[(abs(int(r[control])-int(r['human_level']))>=2,abs(int(r['d1_temperature'])-int(r['human_level']))>=2) for r in sub]
            assert metrics==dict(severe_avoided=sum(a and not b for a,b in pairs),severe_introduced=sum(b and not a for a,b in pairs))

def pred(path, ids):
    return {r['word_id']:{k:v for k,v in r.items() if k!='human_level'} for r in read(path/'predictions.csv') if r['word_id'] in ids}

with TemporaryDirectory(prefix='temperature-audit-') as temporary:
    tmp=Path(temporary)
    evaluate_d1_temperature(inputs,inputs/'references.csv',tmp/'replay')
    for name in ['predictions.csv','fits.json','report.json','severe-cases.csv']:
        assert (tmp/'replay'/name).read_bytes()==(run/name).read_bytes(),name
    original=read(inputs/'references.csv')
    for fold in ['0','1','2','3','4','50']:
        ids={r['word_id'] for r in rows if (r['cohort']=='50' if fold=='50' else r['cohort']=='150' and r['fold']==fold)}
        changed=[dict(r,human_level=1+int(r['human_level'])%5) if r['word_id'] in ids else r for r in original]
        dump(tmp/'references.csv',changed)
        out=tmp/fold
        evaluate_d1_temperature(inputs,tmp/'references.csv',out)
        changed_fit=json.loads((out/'fits.json').read_text())
        if fold=='50':
            assert fits==changed_fit
            ids={r['word_id'] for r in rows}
        else:
            assert fits['outer:'+fold]==changed_fit['outer:'+fold]
        assert pred(run,ids)==pred(out,ids), fold
for path,digest in {**sources,**protocol['inputs']}.items():
    assert sha(Path(path))==digest
result=dict(status='PASS',rows=200,protected_original_sources=len(sources),solver=solver,
            independent_probabilities_medians_metrics=True,paired_errors_verified=True,
            unchanged_v3_comparators=True,byte_identical_replay=True,real_label_isolation_checks=6,
            network_db_guard='sitecustomize offline guard; no inference',
            audit_script_sha256=sha(Path(__file__)))
(run/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
