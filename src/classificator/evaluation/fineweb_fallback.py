"""Grouped evaluation of one supported exact-form FineWeb2 fallback; offline only."""

import json
import math
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _sha256, _write_csv, _vocabulary
from .full_pilot_baselines import _indexed, _level
from .frequency_calibration import _fit
from .local_fallback import VIEWS, _view_summary
from .form_frequency_report import REFERENCE_KINDS

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
    if (
        manifest.get("schema") != 1
        or manifest.get("policy") != "fineweb-exact-forms-v1"
    ):
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
    vocabulary = {
        int(r["word_id"]): r for r in _vocabulary(directory / "vocabulary.csv")
    }
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
        if not 0 <= hosts <= docs <= count <= total or (
            count > 0 and (docs == 0 or hosts == 0)
        ):
            raise ValueError("Inconsistent evidence counts")
        if row["status"] != ("observed" if count else "unobserved"):
            raise ValueError("Inconsistent observation status")
        value = float(row["frequency"]) if row["frequency"] else 0.0
        expected = count / total if total else 0.0
        if not math.isfinite(value) or not math.isclose(
            value, expected, rel_tol=1e-12, abs_tol=0
        ):
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
    ref = _indexed(reference_csv, {"initial_level", "working_level", "reference_kind"})
    first = _indexed(first_independent_csv, {"level"})
    frequency = _indexed(frequency_features_csv, {"wordfreq", "rebus"})
    groups = _indexed(groups_csv, {"group"})
    evidence, balanced_sample = _evidence(evidence_dir)
    if len(ref) < 3 or len(first) < 3 or not first.keys() <= ref.keys():
        raise ValueError(
            "At least three labels and valid first-response subset required"
        )
    if (
        groups.keys() != ref.keys()
        or not ref.keys() <= frequency.keys()
        or not ref.keys() <= evidence.keys()
    ):
        raise ValueError("Missing or inconsistent pilot identities")
    for collection in (first, frequency, groups, evidence):
        if any(i in ref and r["word"] != ref[i]["word"] for i, r in collection.items()):
            raise ValueError("Input spelling mismatch")
    for row in ref.values():
        if row["reference_kind"] not in REFERENCE_KINDS | {"initial_opaque_form_pos"}:
            raise ValueError("Unknown reference kind")
    for row in frequency.values():
        if set(row) != {"word_id", "word", "wordfreq", "rebus"}:
            raise ValueError("Unexpected frequency fields")
        for source in ("wordfreq", "rebus"):
            value = float(row[source]) if row[source] else None
            if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError("Invalid frequency")
            row[source] = value or None
    for row in groups.values():
        if set(row) != {"word_id", "word", "group"} or not row["group"].strip():
            raise ValueError("Invalid groups contract")
        row["group"] = row["group"].strip()
    for ids in (ref, first):
        if len({groups[i]["group"] for i in ids}) < 2:
            raise ValueError("At least two groups per label view required")
    supported = {
        i
        for i, r in evidence.items()
        if int(r["count"]) >= 5
        and int(r["document_count"]) >= 3
        and int(r["host_count"]) >= 2
    }
    views = {
        name: {i: _level(r[field]) for i, r in ref.items()}
        for name, field in VIEWS.items()
    }
    views["first_independent"] = {i: _level(r["level"]) for i, r in first.items()}
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        dir=output_dir.parent, prefix=".fineweb-comparison-"
    ) as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
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
        (staged / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
        result = dict(protocol=protocol, views={})
        for view, labels in views.items():
            directory = staged / view
            (directory / "folds").mkdir(parents=True)
            rows = []
            for i in sorted(labels):
                train_ids = [
                    j
                    for j in sorted(labels)
                    if groups[j]["group"] != groups[i]["group"]
                ]
                corpus_ids = [
                    j
                    for j in train_ids
                    if not frequency[j]["wordfreq"] and j in supported
                ]
                observed_ids = [j for j in train_ids if frequency[j]["wordfreq"]]
                direct_model = (
                    _fit(
                        [
                            (float(frequency[j]["wordfreq"]), labels[j])
                            for j in observed_ids
                        ]
                    )
                    if observed_ids
                    else None
                )
                if direct_model:
                    direct_model["observed_train_ids"] = observed_ids
                    direct_model["objective"] = (
                        "minimum ordinal MAE on observed training labels of declared view"
                    )
                value = (
                    float(frequency[i]["wordfreq"])
                    if frequency[i]["wordfreq"]
                    else None
                )
                direct = (
                    1 + sum(value < t for t in direct_model["thresholds"])
                    if value and direct_model
                    else None
                )
                corpus_model = None
                level, route = 4, "unsupported_four"
                if direct is not None:
                    level, route = direct, "wordfreq_thresholds"
                elif value:
                    route = "no_wordfreq_model_four"
                elif not balanced_sample:
                    route = "insufficient_sample_four"
                elif i in supported:
                    route = "insufficient_training_four"
                    if (
                        len(corpus_ids) >= 10
                        and len({labels[j] for j in corpus_ids}) >= 2
                    ):
                        corpus_model = _fit(
                            [
                                (float(evidence[j]["frequency"]), labels[j])
                                for j in corpus_ids
                            ]
                        )
                        corpus_model["observed_train_ids"] = corpus_ids
                        corpus_model["objective"] = (
                            "minimum ordinal MAE on supported missing-wordfreq training labels of declared view"
                        )
                        level = 1 + sum(
                            float(evidence[i]["frequency"]) < t
                            for t in corpus_model["thresholds"]
                        )
                        route = "fineweb_thresholds"
                fold = dict(
                    train_ids=train_ids,
                    held_out_ids=[
                        j
                        for j in sorted(labels)
                        if groups[j]["group"] == groups[i]["group"]
                    ],
                    wordfreq=direct_model,
                    fineweb=corpus_model,
                    fineweb_train_ids=corpus_ids,
                    candidate_route=route,
                )
                (directory / "folds" / f"{i}.json").write_text(
                    json.dumps(fold, indent=2) + "\n"
                )
                rows.append(
                    dict(
                        word_id=i,
                        word=ref[i]["word"],
                        human_level=labels[i],
                        reference_kind=ref[i]["reference_kind"],
                        group=groups[i]["group"],
                        group_size=sum(
                            groups[i]["group"] == groups[j]["group"] for j in labels
                        ),
                        wordfreq=value,
                        baseline_level=direct if direct is not None else 4,
                        fineweb_frequency=evidence[i]["frequency"],
                        fineweb_count=evidence[i]["count"],
                        fineweb_documents=evidence[i]["document_count"],
                        fineweb_hosts=evidence[i]["host_count"],
                        fineweb_supported=i in supported,
                        candidate_level=level,
                        candidate_route=route,
                    )
                )
            _write_csv(directory / "predictions.csv", list(rows[0]), rows)
            result["views"][view] = _view_summary(rows)
            result["views"][view]["evidence"] = dict(
                observed=sum(evidence[i]["count"] > 0 for i in labels),
                supported=sum(i in supported for i in labels),
                wordfreq_missing_observed=sum(
                    not frequency[i]["wordfreq"] and evidence[i]["count"] > 0
                    for i in labels
                ),
                wordfreq_missing_supported=sum(
                    not frequency[i]["wordfreq"] and i in supported for i in labels
                ),
                candidate_changed=sum(
                    r["baseline_level"] != r["candidate_level"] for r in rows
                ),
                routes=dict(Counter(r["candidate_route"] for r in rows)),
            )
        (staged / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
        (staged / "manifest.json").write_text(
            json.dumps(
                dict(
                    inputs={
                        str(p.resolve()): _sha256(p)
                        for p in (
                            reference_csv,
                            frequency_features_csv,
                            evidence_dir / "manifest.json",
                            evidence_dir / "frequencies.csv",
                            evidence_dir / "vocabulary.csv",
                            first_independent_csv,
                            groups_csv,
                        )
                    },
                    implementation={
                        name: _sha256(Path(__file__).with_name(name))
                        for name in (
                            "fineweb_fallback.py",
                            "frequency_calibration.py",
                            "local_fallback.py",
                            "frequency_cross_validation.py",
                            "form_frequency_report.py",
                            "full_pilot_baselines.py",
                            "dataset.py",
                        )
                    },
                    artifacts={
                        str(p.relative_to(staged)): _sha256(p)
                        for p in staged.rglob("*")
                        if p.is_file()
                    },
                ),
                indent=2,
            )
            + "\n"
        )
        staged.rename(output_dir)
    return result
