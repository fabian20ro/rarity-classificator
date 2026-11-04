"""Grouped evaluation of one supported exact-form FineWeb2 fallback; offline only."""

import json
import math
from pathlib import Path

from .dataset import _sha256, _vocabulary
from .full_pilot_baselines import _indexed
from .corpus_fallback import CorpusEvidence, _evaluate_corpus_fallback

REVISION = "af9c13333eb981300149d5ca60a8e9d659b276b9"
SUPPORT = dict(count=5, documents=3, hosts=2)
EVIDENCE_FIELDS = {
    "word_id",
    "word",
    "type",
    "count",
    "document_count",
    "host_count",
    "token_total",
    "frequency",
    "status",
}


def _evidence(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("schema") != 1 or manifest.get("policy") != "fineweb-exact-forms-v1":
        raise ValueError("Unknown FineWeb evidence schema/policy")
    protocol = manifest.get("protocol", {})
    if (
        protocol.get("revision") != REVISION
        or protocol.get("primary_years") != [2020, 2021, 2022, 2023, 2024]
        or protocol.get("support") != SUPPORT
    ):
        raise ValueError("FineWeb evidence protocol mismatch")
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
    vocabulary = {int(r["word_id"]): r for r in _vocabulary(directory / "vocabulary.csv")}
    evidence = _indexed(
        directory / "frequencies.csv",
        {"count", "document_count", "host_count", "frequency", "type"},
    )
    if vocabulary.keys() != evidence.keys():
        raise ValueError("Evidence must cover complete inventory")
    denominators = set()
    for i, row in evidence.items():
        if set(row) != EVIDENCE_FIELDS:
            raise ValueError("Unexpected evidence fields")
        for field in ("count", "document_count", "host_count", "token_total"):
            if not row[field].isdigit():
                raise ValueError("Evidence counts must be nonnegative integers")
            row[field] = int(row[field])
        count, docs, hosts, total = (
            row[k] for k in ("count", "document_count", "host_count", "token_total")
        )
        denominators.add(total)
        if not 0 <= hosts <= docs <= count <= total or (count > 0 and (docs == 0 or hosts == 0)):
            raise ValueError("Inconsistent evidence counts")
        if row["status"] != ("observed" if count else "unobserved"):
            raise ValueError("Inconsistent observation status")
        value = float(row["frequency"]) if row["frequency"] else 0.0
        expected = count / total if total else 0.0
        if not math.isfinite(value) or not math.isclose(value, expected, rel_tol=1e-12, abs_tol=0):
            raise ValueError("Frequency/count denominator mismatch")
        row["frequency"] = value
        if any(row[k] != vocabulary[i][k] for k in ("word", "type")):
            raise ValueError("Evidence/inventory identity mismatch")
    if len(denominators) != 1:
        raise ValueError("Mixed corpus denominators")
    balanced_sample = manifest.get("counts", {}).get("balanced_sample")
    if not isinstance(balanced_sample, bool):
        raise ValueError("Missing or invalid balanced-sample declaration")
    return evidence, balanced_sample


def evaluate_fineweb_fallback(
    reference_csv: Path,
    frequency_features_csv: Path,
    evidence_dir: Path,
    first_independent_csv: Path,
    groups_csv: Path,
    output_dir: Path,
):
    """Write complete grouped predictions, three label views and 4/5 diagnostics."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    evidence, balanced_sample = _evidence(evidence_dir)
    supported = {
        i
        for i, row in evidence.items()
        if row["count"] >= 5 and row["document_count"] >= 3 and row["host_count"] >= 2
    }
    protocol = dict(
        schema=1,
        experiment="fineweb-fallback-v1",
        source_revision=REVISION,
        balanced_sample=balanced_sample,
        primary_years=[2020, 2021, 2022, 2023, 2024],
        support=SUPPORT,
        candidate_training_minimum=dict(rows=10, distinct_levels=2),
        folds="leave-one-group-out",
        parameter_search=False,
        baseline="fold-fitted wordfreq thresholds; missing or unfitted =>4",
        candidate="shared direct path; supported missing forms use fold-fitted monotone FineWeb thresholds; otherwise4",
        training="only supported wordfreq-missing forms outside held-out group; all label views fitted separately",
        limitations=[
            "Exploratory internal validation on previously inspected labels, not independent gold.",
            "Corpus counts describe observed surface uses, not sense/POS validity.",
            "Frequencies describe selected sample only; Common Crawl can overlap wordfreq.",
            "Missing in sample is not evidence for5; no production promotion or database access.",
        ],
    )
    corpus = CorpusEvidence(
        name="fineweb",
        rows=evidence,
        supported=supported,
        protocol=protocol,
        columns=(
            ("frequency", "frequency"),
            ("count", "count"),
            ("documents", "document_count"),
            ("hosts", "host_count"),
        ),
        enabled=balanced_sample,
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
