"""Noncommercial research comparison of published CoRoLa exact-form counts."""

import json
import math
import re
from pathlib import Path

from .corpus_fallback import CorpusEvidence, _evaluate_corpus_fallback
from .full_pilot_baselines import _indexed
from .dataset import _lexeme, _sha256, _vocabulary


EVIDENCE_FIELDS = {"word_id", "word", "type", "count", "token_total", "frequency", "status"}


def _evidence(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("schema") != 1 or manifest.get("policy") != "corola-exact-forms-v1":
        raise ValueError("Unknown CoRoLa evidence schema/policy")
    source = manifest.get("source", {})
    expected = dict(
        record="7091535",
        member="corola_word_freq_all_lowercase.tsv",
        license="cc-by-nc-nd-4.0",
        archive_md5="0034d61d1825b38386dfa0bc2606a314",
    )
    if any(source.get(k) != value for k, value in expected.items()) or not re.fullmatch(
        r"[0-9a-f]{64}", str(source.get("source_sha256", ""))
    ):
        raise ValueError("CoRoLa source identity mismatch")
    artifacts = manifest.get("artifacts")
    if (
        not isinstance(artifacts, dict)
        or not {"vocabulary.csv", "frequencies.csv"} <= artifacts.keys()
    ):
        raise ValueError("Missing evidence artifact hashes")
    for name, digest in artifacts.items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or not (directory / path).is_file():
            raise ValueError("Invalid evidence artifact path")
        if _sha256(directory / path) != digest:
            raise ValueError("Evidence artifact hash mismatch")
    if manifest.get("vocabulary_sha256") != artifacts["vocabulary.csv"]:
        raise ValueError("Inventory hash mismatch")
    total = manifest.get("token_total")
    if type(total) is not int or total <= 0:
        raise ValueError("Invalid corpus denominator")
    vocabulary = {int(row["word_id"]): row for row in _vocabulary(directory / "vocabulary.csv")}
    evidence = _indexed(directory / "frequencies.csv", EVIDENCE_FIELDS)
    if vocabulary.keys() != evidence.keys():
        raise ValueError("Evidence must cover complete inventory")
    by_form = {}
    for i, row in evidence.items():
        if set(row) != EVIDENCE_FIELDS:
            raise ValueError("Unexpected evidence fields")
        for field in ("count", "token_total"):
            if not row[field].isascii() or not row[field].isdigit():
                raise ValueError("Evidence counts must be nonnegative integers")
            row[field] = int(row[field])
        count = row["count"]
        if not 0 <= count <= total or row["token_total"] != total:
            raise ValueError("Inconsistent corpus denominator/count")
        if row["status"] != ("observed" if count else "unobserved"):
            raise ValueError("Inconsistent observation status")
        value = float(row["frequency"])
        if not math.isfinite(value) or not math.isclose(
            value, count / total, rel_tol=1e-12, abs_tol=0
        ):
            raise ValueError("Frequency/count denominator mismatch")
        row["frequency"] = value
        if any(row[k] != vocabulary[i][k] for k in ("word", "type")):
            raise ValueError("Evidence/inventory identity mismatch")
        form = _lexeme(row["word"])
        if form in by_form and by_form[form] != count:
            raise ValueError("Exact form counts disagree across inventory POS rows")
        by_form[form] = count
    return evidence


def evaluate_corola_fallback(
    reference_csv: Path,
    frequency_features_csv: Path,
    evidence_dir: Path,
    first_independent_csv: Path,
    groups_csv: Path,
    output_dir: Path,
):
    """Export complete grouped predictions and rare-class diagnostics, offline only."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    evidence = _evidence(evidence_dir)
    protocol = dict(
        schema=1,
        experiment="corola-fallback-v1",
        source_record="7091535",
        license="cc-by-nc-nd-4.0",
        support=dict(count=5),
        candidate_training_minimum=dict(rows=10, distinct_levels=2),
        folds="leave-one-group-out",
        parameter_search=False,
        baseline="fold-fitted wordfreq thresholds; missing or unfitted =>4",
        candidate="shared direct path; supported missing forms use fold-fitted monotone CoRoLa thresholds; otherwise4",
        training="only supported wordfreq-missing forms outside held-out group; all label views fitted separately",
        limitations=[
            "Noncommercial research only; no redistribution of derived source data authorized.",
            "Exploratory internal validation on previously inspected labels, not independent gold.",
            "Surface counts pool all senses/POS/names; no sense validation or document diversity available.",
            "Corpus frequency denominator contains letter-only tokens in the published list.",
            "Missing from list is not evidence for5; no production promotion, database or D1 access.",
        ],
    )
    corpus = CorpusEvidence(
        name="corola",
        rows=evidence,
        supported={i for i, row in evidence.items() if row["count"] >= 5},
        protocol=protocol,
        columns=(("frequency", "frequency"), ("count", "count")),
    )
    return _evaluate_corpus_fallback(
        reference_csv,
        frequency_features_csv,
        evidence_dir,
        first_independent_csv,
        groups_csv,
        output_dir,
        corpus,
    )
