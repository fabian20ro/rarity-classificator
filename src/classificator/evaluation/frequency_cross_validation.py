"""Offline leave-one-form-out validation, preserving incompatible label strata."""

import json
from pathlib import Path
from statistics import median_low

from .dataset import _read_csv, _sha256, _vocabulary, _write_csv
from .form_frequency_report import REFERENCE_KINDS, _spearman
from .frequency_calibration import freeze_frequency_thresholds

SOURCES = ("wordfreq", "rebus")
METHODS = (*SOURCES, "median", "wordfreq_median", "rebus_median")


def _metrics(rows, source):
    covered = [r for r in rows if r[source + "_level"] is not None]
    errors = [r[source + "_level"] - r["human_level"] for r in covered]
    rare = [r for r in rows if r["human_level"] >= 4]
    rare_covered = [r for r in rare if r[source + "_level"] is not None]
    confusion = [[0] * 5 for _ in range(5)]
    for row in covered:
        confusion[row["human_level"] - 1][row[source + "_level"] - 1] += 1
    return dict(
        covered=len(covered),
        missing=len(rows) - len(covered),
        mae=sum(abs(e) for e in errors) / len(errors) if errors else None,
        exact=sum(e == 0 for e in errors),
        within_one=sum(abs(e) <= 1 for e in errors),
        severe_errors=sum(abs(e) >= 2 for e in errors),
        signed_bias=sum(errors) / len(errors) if errors else None,
        spearman_levels=_spearman(
            [r["human_level"] for r in covered], [-r[source + "_level"] for r in covered]
        ),
        coverage_by_level={
            str(y): dict(
                total=sum(r["human_level"] == y for r in rows),
                covered=sum(r["human_level"] == y for r in covered),
            )
            for y in range(1, 6)
        },
        rare=dict(
            total=len(rare),
            covered=len(rare_covered),
            severe_underestimate=sum(
                r["human_level"] - r[source + "_level"] >= 2 for r in rare_covered
            ),
        ),
        confusion_human_rows_prediction_columns=confusion,
    )


def _summary(rows):
    paired = [r for r in rows if all(r[s + "_level"] is not None for s in SOURCES)]
    result = dict(total=len(rows), **{s: _metrics(rows, s) for s in METHODS})
    result["paired"] = dict(
        total=len(paired),
        word_ids=[r["word_id"] for r in paired],
        **{s: _metrics(paired, s) for s in METHODS},
    )
    result["median_on_source_coverage"] = {
        s: _metrics([r for r in rows if r[s + "_level"] is not None], "median") for s in SOURCES
    }
    differences = [
        abs(r["wordfreq_level"] - r["human_level"]) - abs(r["rebus_level"] - r["human_level"])
        for r in paired
    ]
    result["paired"]["error_comparison"] = dict(
        wordfreq_better=sum(d < 0 for d in differences),
        rebus_better=sum(d > 0 for d in differences),
        tied=sum(d == 0 for d in differences),
    )
    return result


def cross_validate_frequencies(
    pilot_csv: Path, reference_csv: Path, features_csv: Path, output_dir: Path
):
    """Produce37-style LOO and a separate opaque-label diagnostic, without model I/O.

    All artifacts are explicit; manifest.json is written only on successful completion.
    Existing/partial outputs are never overwritten: rerun to a new output directory.
    """
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    pilot = _vocabulary(pilot_csv)
    reference = _read_csv(reference_csv, {"word_id", "word", "working_level", "reference_kind"})
    clarified = [r for r in reference if r["reference_kind"] in REFERENCE_KINDS]
    if len(clarified) < 2:
        raise ValueError("At least two clarified forms required for leave-one-out")
    # Reuse production calibration and its strict identity/feature validation.
    full_model = freeze_frequency_thresholds(
        pilot_csv, reference_csv, features_csv, output_dir / "full-fit"
    )
    full_predictions = {
        int(r["word_id"]): r
        for r in _read_csv(output_dir / "full-fit/predictions.csv", {"word_id", "word"})
    }
    features = {int(r["word_id"]): r for r in _read_csv(features_csv, {"word_id", "word"})}
    folds, comparison = [], []
    for ref in sorted(reference, key=lambda r: int(r["word_id"])):
        word_id = int(ref["word_id"])
        is_clarified = ref["reference_kind"] in REFERENCE_KINDS
        train = [r for r in clarified if int(r["word_id"]) != word_id]
        if is_clarified:
            fold = output_dir / "folds" / str(word_id)
            fold.mkdir(parents=True)
            training_pilot = [r for r in pilot if int(r["word_id"]) != word_id]
            training_reference = [r for r in reference if int(r["word_id"]) != word_id]
            _write_csv(fold / "pilot.csv", list(training_pilot[0]), training_pilot)
            _write_csv(fold / "reference.csv", list(training_reference[0]), training_reference)
            model = freeze_frequency_thresholds(
                fold / "pilot.csv", fold / "reference.csv", features_csv, fold / "model"
            )
            prediction = next(
                r
                for r in _read_csv(fold / "model/predictions.csv", {"word_id"})
                if int(r["word_id"]) == word_id
            )
            folds.append(
                dict(
                    held_out_id=word_id,
                    train_ids=model["fit_ids"],
                    **{
                        s: dict(
                            model[s],
                            observed_train_ids=[
                                int(r["word_id"])
                                for r in train
                                if features[int(r["word_id"])][s]
                                and float(features[int(r["word_id"])][s]) > 0
                            ],
                        )
                        for s in SOURCES
                    },
                )
            )
        else:
            prediction = full_predictions[word_id]
        row = dict(
            word_id=word_id,
            word=ref["word"],
            human_level=int(ref["working_level"]),
            reference_kind=ref["reference_kind"],
            coverage_status=ref.get("coverage_status", ""),
            witness=ref.get("witness", ""),
            method="clarified_loocv" if is_clarified else "historical_diagnostic",
            train_label_count=len(train),
            median_level=int(median_low(int(r["working_level"]) for r in train)),
        )
        for source in SOURCES:
            value = prediction[source + "_level"]
            row[source + "_frequency"] = features[word_id][source]
            row[source + "_level"] = int(value) if value else None
            row[source + "_status"] = prediction[source + "_status"]
            observed_labels = [
                int(r["working_level"])
                for r in train
                if features[int(r["word_id"])][source]
                and float(features[int(r["word_id"])][source]) > 0
            ]
            row[source + "_median_level"] = int(median_low(observed_labels)) if value else None
            row[source + "_signed_error"] = int(value) - row["human_level"] if value else None
        comparison.append(row)
    summary = dict(
        schema=1,
        policy="clarified-leave-one-form-out-and-opaque-diagnostic-v1",
        clarified_loocv=_summary([r for r in comparison if r["method"] == "clarified_loocv"]),
        historical_diagnostic=_summary(
            [r for r in comparison if r["method"] == "historical_diagnostic"]
        ),
        fold_count=len(folds),
        full_fit={s: full_model[s] for s in SOURCES},
        limitations=[
            "Selected single-rater development data; prior AI exposure and protocol choices remain.",
            "LOO excludes the held-out label; not new independent or family-held-out validation.",
            "Historical labels are never fitted and have a different opaque form/POS target; not CV.",
            "Missing frequencies abstain; conditional metrics require per-level coverage.",
            "Rebus L5 boundary remains a training-fold convention when L5 is unobserved.",
            "Global median uses all training labels, lower median on ties, no frequency required.",
            "Source-matched medians use observed training labels and abstain with the source; no threshold fitting.",
        ],
    )
    _write_csv(output_dir / "comparison.csv", list(comparison[0]), comparison)
    (output_dir / "folds.json").write_text(json.dumps(folds, ensure_ascii=False, indent=2) + "\n")
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    implementation = [
        Path(__file__),
        Path(__file__).with_name("frequency_calibration.py"),
        Path(__file__).with_name("dataset.py"),
        Path(__file__).with_name("form_frequency_report.py"),
        Path(__file__).parents[1] / "scoring/frequency.py",
    ]
    manifest = dict(
        schema=1,
        inputs={str(p.resolve()): _sha256(p) for p in (pilot_csv, reference_csv, features_csv)},
        implementation={str(p.resolve()): _sha256(p) for p in implementation},
        artifacts={
            str(p.relative_to(output_dir)): _sha256(p) for p in output_dir.rglob("*") if p.is_file()
        },
    )
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return summary
