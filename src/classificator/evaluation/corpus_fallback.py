"""Shared fold-local comparison for validated frequency evidence; no source I/O."""

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _sha256, _write_csv
from .full_pilot_baselines import _indexed, _level
from .frequency_calibration import _fit
from .local_fallback import VIEWS, _view_summary
from .form_frequency_report import REFERENCE_KINDS


@dataclass
class CorpusEvidence:
    name: str
    rows: dict
    supported: set
    protocol: dict
    columns: tuple
    enabled: bool = True


def _evaluate_corpus_fallback(
    reference_csv: Path,
    frequency_features_csv: Path,
    evidence_dir: Path,
    first_independent_csv: Path,
    groups_csv: Path,
    output_dir: Path,
    corpus: CorpusEvidence,
):
    """Write complete grouped predictions, three label views and 4/5 diagnostics."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    ref = _indexed(reference_csv, {"initial_level", "working_level", "reference_kind"})
    first = _indexed(first_independent_csv, {"level"})
    frequency = _indexed(frequency_features_csv, {"wordfreq", "rebus"})
    groups = _indexed(groups_csv, {"group"})
    evidence, supported = corpus.rows, corpus.supported
    if len(ref) < 3 or len(first) < 3 or not first.keys() <= ref.keys():
        raise ValueError("At least three labels and valid first-response subset required")
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
    views = {name: {i: _level(r[field]) for i, r in ref.items()} for name, field in VIEWS.items()}
    views["first_independent"] = {i: _level(r["level"]) for i, r in first.items()}
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".corpus-comparison-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        protocol = corpus.protocol
        (staged / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
        result = dict(protocol=protocol, views={})
        for view, labels in views.items():
            directory = staged / view
            (directory / "folds").mkdir(parents=True)
            rows = []
            for i in sorted(labels):
                train_ids = [j for j in sorted(labels) if groups[j]["group"] != groups[i]["group"]]
                corpus_ids = [
                    j for j in train_ids if not frequency[j]["wordfreq"] and j in supported
                ]
                observed_ids = [j for j in train_ids if frequency[j]["wordfreq"]]
                direct_model = (
                    _fit([(float(frequency[j]["wordfreq"]), labels[j]) for j in observed_ids])
                    if observed_ids
                    else None
                )
                if direct_model:
                    direct_model["observed_train_ids"] = observed_ids
                    direct_model["objective"] = (
                        "minimum ordinal MAE on observed training labels of declared view"
                    )
                value = float(frequency[i]["wordfreq"]) if frequency[i]["wordfreq"] else None
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
                elif not corpus.enabled:
                    route = "insufficient_sample_four"
                elif i in supported:
                    route = "insufficient_training_four"
                    if len(corpus_ids) >= 10 and len({labels[j] for j in corpus_ids}) >= 2:
                        corpus_model = _fit(
                            [(float(evidence[j]["frequency"]), labels[j]) for j in corpus_ids]
                        )
                        corpus_model["observed_train_ids"] = corpus_ids
                        corpus_model["objective"] = (
                            "minimum ordinal MAE on supported missing-wordfreq training labels of declared view"
                        )
                        level = 1 + sum(
                            float(evidence[i]["frequency"]) < t for t in corpus_model["thresholds"]
                        )
                        route = corpus.name + "_thresholds"
                fold = dict(
                    train_ids=train_ids,
                    held_out_ids=[
                        j for j in sorted(labels) if groups[j]["group"] == groups[i]["group"]
                    ],
                    wordfreq=direct_model,
                    **{corpus.name: corpus_model, corpus.name + "_train_ids": corpus_ids},
                    candidate_route=route,
                )
                (directory / "folds" / f"{i}.json").write_text(json.dumps(fold, indent=2) + "\n")
                rows.append(
                    dict(
                        word_id=i,
                        word=ref[i]["word"],
                        human_level=labels[i],
                        reference_kind=ref[i]["reference_kind"],
                        group=groups[i]["group"],
                        group_size=sum(groups[i]["group"] == groups[j]["group"] for j in labels),
                        wordfreq=value,
                        baseline_level=direct if direct is not None else 4,
                        **{
                            corpus.name + "_" + output: evidence[i][field]
                            for output, field in corpus.columns
                        },
                        **{corpus.name + "_supported": i in supported},
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
                    not frequency[i]["wordfreq"] and evidence[i]["count"] > 0 for i in labels
                ),
                wordfreq_missing_supported=sum(
                    not frequency[i]["wordfreq"] and i in supported for i in labels
                ),
                candidate_changed=sum(r["baseline_level"] != r["candidate_level"] for r in rows),
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
                            corpus.name + "_fallback.py",
                            "corpus_fallback.py",
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
