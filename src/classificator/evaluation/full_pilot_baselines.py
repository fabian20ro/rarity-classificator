"""Exploratory full-pilot baselines: fixed historical predictions and fold-local fits."""

from collections import Counter
from importlib.metadata import version
import json
import math
from pathlib import Path
from statistics import median, median_low

from .dataset import _read_csv, _sha256, _write_csv
from .form_frequency_report import REFERENCE_KINDS
from .frequency_calibration import _fit
from .frequency_cross_validation import _metrics

SOURCES = ("wordfreq", "rebus")
METHODS = (
    "legacy",
    "assistant",
    "median",
    "majority",
    "wordfreq",
    "rebus",
    "wordfreq_median",
    "rebus_median",
    "ridge",
    "wordfreq_complete",
    "rebus_complete",
)
OPERATIONAL_METHODS = (
    "legacy", "assistant", "median", "majority", "wordfreq_complete", "rebus_complete", "ridge"
)
VIEWS = {"original_round_final": "initial_level", "revised_working": "working_level"}


def _indexed(path, required):
    rows = _read_csv(path, set(required) | {"word_id", "word"})
    result = {}
    for row in rows:
        word_id = int(row["word_id"])
        if word_id <= 0 or word_id in result or not row["word"].strip():
            raise ValueError("Invalid or duplicate identity: " + str(path))
        result[word_id] = row
    if not result:
        raise ValueError("Empty input: " + str(path))
    return result


def _level(value):
    level = int(value)
    if level not in range(1, 6):
        raise ValueError("Level must be1..5")
    return level


def _ridge(train_ids, held_out, labels, features):
    # Optional dependency kept away from production and other evaluation paths.
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    imputation = []
    for source in SOURCES:
        logs = [math.log10(features[i][source]) for i in train_ids if features[i][source]]
        imputation.append(median(logs) if logs else 0.0)

    def vector(word_id):
        return [
            math.log10(features[word_id][s]) if features[word_id][s] else imputation[j]
            for j, s in enumerate(SOURCES)
        ] + [int(not features[word_id][s]) for s in SOURCES]

    scaler = StandardScaler()
    x = scaler.fit_transform([vector(i) for i in train_ids])
    model = Ridge(alpha=1.0, fit_intercept=True, solver="svd")
    model.fit(x, [labels[i] for i in train_ids])
    raw = float(model.predict(scaler.transform([vector(held_out)]))[0])
    return dict(
        raw_prediction=raw,
        level=max(1, min(5, math.floor(raw + 0.5))),
        alpha=1.0,
        solver="svd",
        log_imputation=imputation,
        scaler_mean=scaler.mean_.tolist(),
        scaler_scale=scaler.scale_.tolist(),
        coefficients=model.coef_.tolist(),
        intercept=float(model.intercept_),
    )


def _summary(rows, methods=METHODS):
    return dict(total=len(rows), **{m: _metrics(rows, m) for m in methods})


def _view_summary(rows):
    all_present = [r for r in rows if all(r[s + "_level"] is not None for s in SOURCES)]
    for row in rows:
        for method in OPERATIONAL_METHODS:
            level = row[method + "_level"]
            if type(level) is not int or level not in range(1, 6):
                raise ValueError(f"Incomplete operational method: {method}")
    return dict(
        operational=_summary(rows, OPERATIONAL_METHODS),
        completion_routes={
            s: {
                basis: _metrics(
                    [r for r in rows if r[s + "_complete_basis"] == basis], s + "_complete"
                )
                for basis in ("frequency_thresholds", "missing_group_median", "global_median")
            }
            for s in SOURCES
        },
        all=_summary(rows),
        clarified=_summary([r for r in rows if r["reference_kind"] in REFERENCE_KINDS]),
        opaque=_summary([r for r in rows if r["reference_kind"] == "initial_opaque_form_pos"]),
        common_frequency_coverage=dict(
            word_ids=[r["word_id"] for r in all_present], **_summary(all_present)
        ),
        on_source_coverage={
            s: _summary([r for r in rows if r[s + "_level"] is not None]) for s in SOURCES
        },
        by_evidence={
            g: _summary([r for r in rows if r["evidence_group"] == g])
            for g in ("both", "one", "neither")
        },
    )


def evaluate_full_pilot(
    reference_csv: Path,
    features_csv: Path,
    legacy_csv: Path,
    assistant_csv: Path,
    first_independent_csv: Path,
    output_dir: Path,
):
    """Use every pilot form, without pretending mixed labels are a homogeneous gold set.

    Existing output directories are refused; manifest.json marks a complete run.
    Every fold's training IDs, thresholds, preprocessing and coefficients are saved.
    """
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    ref = _indexed(reference_csv, {"initial_level", "working_level", "reference_kind"})
    if len(ref) < 3:
        raise ValueError("At least three pilot forms required")
    for row in ref.values():
        for field in VIEWS.values():
            row[field] = _level(row[field])
        if row["reference_kind"] not in REFERENCE_KINDS | {"initial_opaque_form_pos"}:
            raise ValueError("Unknown label provenance")
    features = _indexed(features_csv, SOURCES)
    if not ref.keys() <= features.keys():
        raise ValueError("Missing pilot features")
    for i, row in features.items():
        if set(row) != {"word_id", "word", *SOURCES}:
            raise ValueError("Features cannot contain labels or extra fields")
        if i in ref and row["word"] != ref[i]["word"]:
            raise ValueError("Feature spelling mismatch")
        for s in SOURCES:
            value = float(row[s]) if row[s] else None
            if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError("Invalid frequency")
            row[s] = value or None
    saved = {}
    for name, path in [("legacy", legacy_csv), ("assistant", assistant_csv)]:
        scores = _indexed(path, {"rarity_level"})
        if scores.keys() != ref.keys() or any(
            r["word"] != ref[i]["word"] for i, r in scores.items()
        ):
            raise ValueError("Saved predictions must exactly match pilot identities")
        saved[name] = {i: _level(r["rarity_level"]) for i, r in scores.items()}
    first = _indexed(first_independent_csv, {"level"})
    if not first.keys() <= ref.keys() or any(r["word"] != ref[i]["word"] for i, r in first.items()):
        raise ValueError("First-independent labels must match pilot subset")
    if len(first) < 3:
        raise ValueError("At least three first-independent labels required")
    for row in first.values():
        row["level"] = _level(row["level"])
    runtime = {p: version(p) for p in ("numpy", "scipy", "scikit-learn")}
    output_dir.mkdir(parents=True)
    policy = dict(
        schema=2,
        experiment="full-pilot-complete-coverage-loocv-v2",
        views=dict(VIEWS, first_independent="immutable first independent level, subset only"),
        folds="leave-one-form-out;149 training labels for150 views,148 for first-independent149",
        threshold_policy="shared monotone MAE log-grid fitter; no hyperparameter search",
        ridge=dict(
            alpha=1.0,
            solver="svd",
            features=["log10_wordfreq", "log10_rebus", "wordfreq_missing", "rebus_missing"],
            imputation="training median log frequency;0 if none",
            scaling="training mean/std ddof0; constant feature scale1",
            rounding="floor(raw+.5), then clip1..5; no confidence claims",
        ),
        constants="lower median; smallest majority class on ties",
        missing="raw frequency methods remain abstaining diagnostics; complete variants use explicit fallback",
        coverage_requirement="100% integer scores1..5 required for operational comparison",
        frequency_fallback=dict(
            missing_source="lower median of same-source-missing training labels; global training median if empty",
            missing_model="global training median when observed test frequency has no fitted threshold model",
            choice="fixed before this run; exploratory choice after prior pilot inspection, not an independent test",
        ),
        limitations=[
            "Latest150 mixes37 clarified and113 original form/POS labels.",
            "Original-round-final is not first-independent; report saved-prediction sensitivity separately.",
            "LOO is internal single-rater validation, not an independent or family-held-out test.",
            "Saved assistant/legacy are fixed historical predictions, not cross-validated fits.",
        ],
        runtime=runtime,
    )
    (output_dir / "protocol.json").write_text(json.dumps(policy, indent=2) + "\n")
    result = dict(protocol=policy, views={})
    label_views = {view: {i: r[field] for i, r in ref.items()} for view, field in VIEWS.items()}
    label_views["first_independent"] = {i: r["level"] for i, r in first.items()}
    for view, labels in label_views.items():
        ids = sorted(labels)
        directory = output_dir / view
        (directory / "folds").mkdir(parents=True)
        predictions = []
        for held_out in ids:
            train_ids = [i for i in ids if i != held_out]
            train_labels = [labels[i] for i in train_ids]
            counts = Counter(train_labels)
            fold = dict(
                held_out_id=held_out,
                train_ids=train_ids,
                median_level=int(median_low(train_labels)),
                majority_level=min(counts, key=lambda k: (-counts[k], k)),
            )
            observed_count = sum(bool(features[held_out][s]) for s in SOURCES)
            row = dict(
                word_id=held_out,
                word=ref[held_out]["word"],
                human_level=labels[held_out],
                reference_kind=ref[held_out]["reference_kind"],
                label_view=view,
                evidence_group={2: "both", 1: "one", 0: "neither"}[observed_count],
                legacy_level=saved["legacy"][held_out],
                assistant_level=saved["assistant"][held_out],
                median_level=fold["median_level"],
                majority_level=fold["majority_level"],
            )
            for source in SOURCES:
                observed = [
                    (features[i][source], labels[i]) for i in train_ids if features[i][source]
                ]
                model = _fit(observed) if observed else None
                if model:
                    model["objective"] = (
                        "minimum ordinal MAE on observed training labels of declared view"
                    )
                    model["observed_train_ids"] = [i for i in train_ids if features[i][source]]
                fold[source] = model
                value = features[held_out][source]
                level = 1 + sum(value < t for t in model["thresholds"]) if value and model else None
                row[source + "_level"] = level
                row[source + "_frequency"] = value
                row[source + "_median_level"] = (
                    int(median_low(y for _, y in observed)) if level else None
                )
                missing_ids = [i for i in train_ids if not features[i][source]]
                fallback_ids = missing_ids if not value and missing_ids else train_ids
                fallback = dict(
                    level=int(median_low(labels[i] for i in fallback_ids)),
                    train_ids=fallback_ids,
                    basis="missing_group_median" if not value and missing_ids else "global_median",
                )
                fold[source + "_fallback"] = fallback
                row[source + "_complete_level"] = level if level is not None else fallback["level"]
                row[source + "_complete_basis"] = (
                    "frequency_thresholds" if level is not None else fallback["basis"]
                )
            fold["ridge"] = _ridge(train_ids, held_out, labels, features)
            row["ridge_level"] = fold["ridge"]["level"]
            row["ridge_raw"] = fold["ridge"]["raw_prediction"]
            row["ridge_basis"] = (
                "missingness_only" if not observed_count else "observed_and_missing_features"
            )
            (directory / "folds" / f"{held_out}.json").write_text(json.dumps(fold, indent=2) + "\n")
            predictions.append(row)
        _write_csv(directory / "predictions.csv", list(predictions[0]), predictions)
        result["views"][view] = _view_summary(predictions)
    independent = [
        dict(
            word_id=i,
            word=r["word"],
            human_level=r["level"],
            **{name + "_level": scores[i] for name, scores in saved.items()},
        )
        for i, r in sorted(first.items())
    ]
    _write_csv(output_dir / "first-independent-saved.csv", list(independent[0]), independent)
    result["first_independent_saved"] = _summary(independent, ("legacy", "assistant"))
    (output_dir / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    inputs = [reference_csv, features_csv, legacy_csv, assistant_csv, first_independent_csv]
    code = [
        Path(__file__),
        Path(__file__).with_name("frequency_calibration.py"),
        Path(__file__).with_name("frequency_cross_validation.py"),
        Path(__file__).with_name("form_frequency_report.py"),
        Path(__file__).with_name("dataset.py"),
    ]
    manifest = dict(
        inputs={str(p.resolve()): _sha256(p) for p in inputs},
        implementation={str(p.resolve()): _sha256(p) for p in code},
        artifacts={
            str(p.relative_to(output_dir)): _sha256(p) for p in output_dir.rglob("*") if p.is_file()
        },
    )
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return result
