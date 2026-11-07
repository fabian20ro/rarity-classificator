"""Lexical CSV -> sequential native Score receipts and resumable predictions.

The caller owns model loading, resource checks and the frozen runtime identity.
No references, calibration examples, database or model lifecycle operations.
"""

from pathlib import Path

from ..models import BaseWordRow
from ..scoring.d1 import D1Scorer
from .campaign import run_campaign
from .dataset import _sha256, _vocabulary
from .lexical_evidence import read_lexical_evidence


def collect_d1_score_csv(
    vocabulary_csv, evidence_csv, output_dir, *, model, question,
    base_url="http://127.0.0.1:1234", http=None, runtime=None, retry_failed=False,
    allow_historical_incomplete=False,
):
    items = [BaseWordRow(int(r["word_id"]), r["word"], r["type"])
             for r in _vocabulary(vocabulary_csv)]
    evidence = read_lexical_evidence(evidence_csv, items,
        allow_historical_incomplete=allow_historical_incomplete)
    scorer = D1Scorer(model=model, question=question, evidence=evidence,
                      base_url=base_url, http=http)
    config = dict(
        model=model, base_url=base_url, question=question,
        decoder="lower-median-strict-survival-gt-0.5-v1",
        runtime=runtime or {}, vocabulary_sha256=_sha256(vocabulary_csv),
        evidence_sha256=_sha256(evidence_csv),
        collector_sha256=_sha256(Path(__file__)),
        lexical_schema_sha256=_sha256(Path(__file__).with_name("lexical_evidence.py")),
        stop_on_failure=True, allow_historical_incomplete=allow_historical_incomplete,
    )
    return run_campaign(items, scorer, output_dir, config=config,
                        retry_failed=retry_failed, stop_on_failure=True)
