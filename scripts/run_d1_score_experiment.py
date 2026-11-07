"""Run a frozen local Score protocol, sequentially, with RAM gates and checkpoints.

Usage: PYTHONPATH=src python scripts/run_d1_score_experiment.py RUN_DIRECTORY
The directory supplies protocol.json, input CSVs and native question JSONs.
No human references enter this runner. Model management is explicit and local.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from unittest.mock import patch

import requests

from classificator.evaluation.d1_score import collect_d1_score_csv

LMS = '/Users/fabian/.lmstudio/bin/lms'
URL = 'http://127.0.0.1:1234'


def main(out):
    out = Path(out).resolve()
    protocol = json.loads((out / 'protocol.json').read_text())
    model = protocol['model']

    def sha(path):
        with Path(path).open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()

    def append(name, value):
        with (out / name).open('a') as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + '\n')

    def save(name, value):
        (out / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

    for name, digest in protocol['inputs'].items():
        assert sha(out / name) == digest, name
    for name, digest in protocol['implementation'].items():
        assert sha(name) == digest, name
    assert sha(protocol['model_file']) == protocol['model_file_sha256']
    protected = json.loads((out / 'protected-inputs.json').read_text())

    def check_protected():
        for name, digest in protected.items():
            assert sha(name) == digest, name

    plain = requests.Session()
    plain.trust_env = False

    def models():
        result = plain.get(URL + '/api/v1/models', timeout=30)
        result.raise_for_status()
        return result.json()

    def generator_idle():
        result = plain.get('http://127.0.0.1:8000/api/status', timeout=5)
        result.raise_for_status()
        state = result.json()
        if state.get('current_task') or state.get('queue_length') or state.get('pending_count'):
            raise RuntimeError('Competing generator active; wait, do not interrupt')

    def remove_qwen():
        inventory = models()
        for entry in inventory['models']:
            if entry['key'] == 'qwen3.8-27b-splash':
                for instance in entry.get('loaded_instances', []):
                    subprocess.run([LMS, 'unload', instance['id']], check=True, capture_output=True)
                    append('qwen-unloads.jsonl', dict(at=time.time(), instance=instance['id']))
                    time.sleep(3)  # unload acknowledgement precedes memory release
        return models()

    def memory(stage):
        raw = subprocess.check_output(['/usr/bin/vm_stat'], text=True)
        size = int(re.search(r'page size of (\d+)', raw)[1])
        pages = {k: int(v) for k, v in re.findall(r'^(Pages [^:]+):\s+(\d+)\.', raw, re.M)}
        pressure = subprocess.check_output(['/usr/bin/memory_pressure', '-Q'], text=True)
        total = int(re.search(r'system has (\d+)', pressure)[1])
        pct = int(re.search(r'free percentage: (\d+)%', pressure)[1])
        value = dict(at=time.time(), stage=stage, available_proxy_bytes=sum(
            pages[k] for k in ['Pages free', 'Pages inactive', 'Pages speculative']) * size,
            os_free_percentage=pct, os_free_proxy_bytes=total * pct / 100)
        append('memory.jsonl', value)
        return value

    count = 0
    owned = None
    pinned = None

    class GuardedSession(requests.Session):
        def request(self, method, url, **kwargs):
            nonlocal count, pinned
            if not url.startswith(URL + '/'):
                raise RuntimeError('Only local LM Studio permitted')
            if method.upper() == 'POST':
                assert url == URL + '/v1/systemone'
                generator_idle()
                inventory = remove_qwen()
                active = [(m, i) for m in inventory['models'] for i in m.get('loaded_instances', [])]
                if len(active) != 1 or active[0][0]['key'] != model or active[0][1]['id'] != owned:
                    raise RuntimeError('Model evicted or another model loaded; checkpoint retained')
                identity = json.dumps(active[0][0], sort_keys=True)
                if pinned is not None and identity != pinned:
                    raise RuntimeError('Model identity/config changed during experiment')
                pinned = identity
                mem = memory('before-request')
                if mem['available_proxy_bytes'] < 2 * 2**30 or mem['os_free_percentage'] < 10:
                    raise RuntimeError('RAM reserve below gate; no inference')
                existing = out / 'transfers.jsonl'
                sent = sum(1 for _ in existing.open()) if existing.exists() else 0
                if sent >= protocol['max_requests']:
                    raise RuntimeError('Frozen request budget exhausted')
                count += 1
                start = time.time()
                # Intent journal counts failed transports too; never exceeds frozen budget.
                append('transfers.jsonl', dict(at=start, word=kwargs['json']['state']['word']))
                result = super().request(method, url, **kwargs)
                append('completed-transfers.jsonl', dict(start=start, finish=time.time(), status=result.status_code))
                if count == 1 or count % 25 == 0:
                    print(f'Sequential requests this run: {count}; RAM {mem["available_proxy_bytes"]/2**30:.2f} GiB', flush=True)
                return result
            return super().request(method, url, **kwargs)

    from classificator.evaluation.lexical_evidence import read_lexical_evidence
    from classificator.evaluation.dataset import _vocabulary
    from classificator.models import BaseWordRow
    for cohort, arm in protocol['schedule']:
        inputs = out / 'inputs' / cohort
        items = [BaseWordRow(int(r['word_id']), r['word'], r['type']) for r in _vocabulary(inputs / 'vocabulary.csv')]
        read_lexical_evidence(inputs / ('historical.csv' if arm == 'A' else 'corrected.csv'), items,
                              allow_historical_incomplete=(arm == 'A'))
    check_protected()
    generator_idle()
    try:
        initial = remove_qwen()
        if any(m.get('loaded_instances') for m in initial['models']):
            raise RuntimeError('Another model already loaded; no ownership assumed')
        pre = memory('before-load')
        save('pre-load.json', dict(models=initial, memory=pre))
        if pre['available_proxy_bytes'] < 12 * 2**30 or pre['os_free_proxy_bytes'] < 13.32 * 2**30:
            raise RuntimeError('Insufficient pre-load RAM reserve')
        response = plain.post(URL + '/api/v1/models/load', json=dict(model=model,
            **protocol['runtime'], echo_load_config=True), timeout=180)
        (out / 'load.json').write_text(response.text)
        response.raise_for_status()
        owned = response.json()['instance_id']
        assert all(response.json()['load_config'][k] == v for k, v in protocol['runtime'].items())
        runtime = dict(protocol_sha256=sha(out / 'protocol.json'), runner_sha256=sha(__file__),
            runtime_inventory=subprocess.check_output([LMS, 'runtime', 'ls'], text=True),
            model_file_sha256=protocol['model_file_sha256'], load_config=protocol['runtime'])
        session = GuardedSession()
        session.trust_env = False
        with patch('psycopg.connect', side_effect=AssertionError('DB forbidden')):
            for cohort, arm in protocol['schedule']:
                inputs = out / 'inputs' / cohort
                print(f'Start cohort={cohort} arm={arm}', flush=True)
                collect_d1_score_csv(inputs / 'vocabulary.csv', inputs / ('historical.csv' if arm == 'A' else 'corrected.csv'),
                    out / 'campaigns' / cohort / arm, model=model,
                    question=json.loads((out / 'questions' / f'{arm}.json').read_text()),
                    http=session, runtime=runtime, allow_historical_incomplete=(arm == 'A'))
        print('COMPLETE', flush=True)
    finally:
        if owned and any(i['id'] == owned for m in models()['models'] for i in m.get('loaded_instances', [])):
            subprocess.run([LMS, 'unload', owned], check=True, capture_output=True)
        check_protected()
        save('post-run.json', dict(models=models(), memory=memory('after-unload'),
            requests_this_invocation=count, protected_inputs_unchanged=len(protected)))
        print('Protected inputs verified; owned D1 unloaded.', flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
