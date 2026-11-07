"""Strict offline four-arm comparison; references never enter the inference runner."""
import json
from pathlib import Path
import sys

from classificator.evaluation.dataset import _read_csv, _sha256, _write_csv
from classificator.evaluation.judge_comparison import _indexed, _level, _metrics


def compare(run_dir, reference_csv, output_dir):
    run_dir, output_dir = Path(run_dir), Path(output_dir)
    protocol = json.loads((run_dir / 'protocol.json').read_text())
    for name, digest in protocol['inputs'].items():
        if _sha256(run_dir / name) != digest:
            raise ValueError('Changed frozen experimental input: ' + name)
    references = _read_csv(Path(reference_csv), {'cohort', 'word_id', 'word', 'human_level', 'baseline_level'})
    if set(r['cohort'] for r in references) != {'150', '50'}:
        raise ValueError('Require both independent cohort identities')
    identities = [r['word_id'] for r in references]
    if len(identities) != len(set(identities)):
        raise ValueError('References must have unique IDs across cohorts')
    report = dict(cohorts={}, decisions={}, effects={})
    output = []
    hashes = {str(reference_csv): _sha256(Path(reference_csv))}
    for cohort in ['150', '50']:
        rows = [dict(r) for r in references if r['cohort'] == cohort]
        ids = {r['word_id'] for r in rows}
        vocabulary = _indexed(run_dir / 'inputs' / cohort / 'vocabulary.csv', {'word', 'type'})
        if ids != set(vocabulary) or any(vocabulary[r['word_id']]['word'] != r['word'] for r in rows):
            raise ValueError('References differ from frozen vocabulary; incomplete comparison')
        for row in rows:
            row['human_level'] = _level(row['human_level'])
            row['baseline_level'] = _level(row['baseline_level'])
            row['constant3'] = 3
        for arm in 'ABCD':
            path = run_dir / 'campaigns' / cohort / arm / 'predictions.csv'
            values = _indexed(path, {'word', 'status', 'rarity_level'})
            if set(values) != ids:
                raise ValueError('Prediction/reference IDs differ; incomplete experiment')
            for row in rows:
                value = values[row['word_id']]
                if value['status'] != 'scored' or value['word'] != row['word']:
                    raise ValueError('Incomplete prediction or exact-form identity mismatch')
                row[arm] = _level(value['rarity_level'])
            hashes[str(path)] = _sha256(path)
        subsets = dict(all=rows, true4=[r for r in rows if r['human_level'] == 4],
                       true5=[r for r in rows if r['human_level'] == 5])
        report['cohorts'][cohort] = {method: {name: _metrics(group, method) for name, group in subsets.items()}
            for method in ['baseline_level', 'constant3', *'ABCD']}
        report['effects'][cohort] = {}
        for before, after in [('A', 'B'), ('B', 'C'), ('C', 'D')]:
            report['effects'][cohort][after + '-' + before] = dict(
                changed=sum(r[before] != r[after] for r in rows),
                severe_avoided=sum(abs(r[before]-r['human_level']) >= 2 and abs(r[after]-r['human_level']) < 2 for r in rows),
                severe_introduced=sum(abs(r[before]-r['human_level']) < 2 and abs(r[after]-r['human_level']) >= 2 for r in rows))
        output.extend(rows)
    for arm in 'BCD':
        checks = {}
        improvement = False
        for cohort, methods in report['cohorts'].items():
            for subset in ['all', 'true4', 'true5']:
                for metric in ['severe', 'excess_error_total']:
                    a, b = methods['A'][subset][metric], methods[arm][subset][metric]
                    checks[f'{cohort}:{subset}:{metric}'] = b <= a
                    if subset == 'all' and b < a:
                        improvement = True
        report['decisions'][arm] = dict(passes_against_A=all(checks.values()) and improvement,
            strict_improvement=improvement, no_regression_checks=checks,
            automatic_promotion=False)
    report['limitations'] = ['Reused development references; no independent accuracy estimate',
        '50 risk-selected, not population-representative', 'Corrected evidence partly human-curated',
        'B-A evidence; C-B instruction package; D-C rubric; no attribution to individual sentences',
        'No DB changes or automatic promotion']
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir/'comparison.csv', list(output[0]), output)
    (output_dir/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    (output_dir/'manifest.json').write_text(json.dumps(dict(inputs=hashes,
        implementation_sha256=_sha256(Path(__file__))), indent=2)+'\n')
    return report


if __name__ == '__main__':
    compare(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
