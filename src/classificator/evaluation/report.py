"""Offline, CSV-first evaluation. Missing predictions remain part of the gold population."""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path


def _read_rows(path: Path, required: set[str]) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)):
            raise ValueError(f"{path}: duplicate column names")
        if not required.issubset(columns):
            raise ValueError(f"{path}: missing required columns: {sorted(required - set(columns))}")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path}:{reader.line_num}: incorrect column count")
            rows.append({key: value.strip() for key, value in row.items()})
        return columns, rows


def _positive_integer(value: str, field: str) -> int:
    if not value.isascii() or not value.isdecimal() or int(value) <= 0:
        raise ValueError(f"{field} must be a positive integer, got {value!r}")
    return int(value)


def _level(value: str, field: str) -> int:
    level = _positive_integer(value, field)
    if level > 5:
        raise ValueError(f"{field} must be between 1 and 5, got {value!r}")
    return level


def _read_labels(path: Path) -> list[dict]:
    labels = []
    seen = set()
    group_splits = {}
    _, rows = _read_rows(path, {"word_id", "level", "group", "split"})
    for row in rows:
        word_id = _positive_integer(row["word_id"], "word_id")
        if word_id in seen:
            raise ValueError(f"{path}: duplicate word_id {word_id}")
        seen.add(word_id)
        for field in ("group", "split"):
            if not row[field]:
                raise ValueError(f"{path}: empty {field} for word_id {word_id}")
        previous_split = group_splits.setdefault(row["group"], row["split"])
        if previous_split != row["split"]:
            raise ValueError(f"{path}: group {row['group']!r} occurs in multiple splits")
        labels.append({**row, "word_id": word_id, "level": _level(row["level"], "level")})
    return labels


def _read_predictions(path: Path, known_ids: set[int]) -> dict[int, dict]:
    predictions = {}
    columns, rows = _read_rows(path, {"word_id", "rarity_level"})
    probability_columns = {f"p_L{level}" for level in range(1, 6)}
    present_columns = probability_columns.intersection(columns)
    if present_columns and present_columns != probability_columns:
        raise ValueError(f"{path}: partial probability columns")
    for row in rows:
        row.setdefault("status", "scored")
        word_id = _positive_integer(row["word_id"], "word_id")
        if word_id in predictions:
            raise ValueError(f"{path}: duplicate word_id {word_id}")
        if word_id not in known_ids:
            raise ValueError(f"{path}: unknown word_id {word_id}")
        status = row["status"]
        if status not in {"scored", "failed", "unresolved"}:
            raise ValueError(f"{path}: invalid status {status!r} for word_id {word_id}")
        if status == "failed" and row["rarity_level"]:
            raise ValueError(f"{path}: {status} row has rarity_level for word_id {word_id}")
        predictions[word_id] = {
            "status": status,
            "rarity_level": (
                _level(row["rarity_level"], "rarity_level")
                if status == "scored" or row["rarity_level"]
                else None
            ),
            "probabilities": _probabilities(row, path),
        }
    return predictions


def _probabilities(row: dict[str, str], path: Path) -> list[float] | None:
    values = [row.get(f"p_L{level}", "") for level in range(1, 6)]
    if not any(values):
        return None
    if not all(values):
        raise ValueError(f"{path}: partial probability vector for word_id {row['word_id']}")
    if row["status"] == "failed":
        raise ValueError(f"{path}: {row['status']} row has probabilities")
    try:
        probabilities = [float(value) for value in values]
    except ValueError as exc:
        raise ValueError(f"{path}: non-numeric probability") from exc
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities):
        raise ValueError(f"{path}: probabilities must be finite and between 0 and 1")
    if not math.isclose(sum(probabilities), 1.0, rel_tol=0, abs_tol=1e-6):
        raise ValueError(f"{path}: probabilities must sum to 1")
    return probabilities


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _probability_metrics(labels: list[dict], predictions: dict[int, dict]) -> dict:
    briers, losses, ranked_scores = [], [], []
    zero_gold_count = scored_count = 0
    for label in labels:
        prediction = predictions.get(label["word_id"])
        if prediction is None or prediction["status"] != "scored":
            continue
        scored_count += 1
        probabilities = prediction["probabilities"]
        if probabilities is None:
            continue
        gold_index = label["level"] - 1
        briers.append(
            sum((p - (index == gold_index)) ** 2 for index, p in enumerate(probabilities))
        )
        zero_gold_count += probabilities[gold_index] == 0
        losses.append(-math.log(max(probabilities[gold_index], 1e-15)))
        cumulative = 0.0
        ranked_score = 0.0
        for index, probability in enumerate(probabilities[:-1]):
            cumulative += probability
            ranked_score += (cumulative - (gold_index <= index)) ** 2
        ranked_scores.append(ranked_score / 4)
    return {
        "count": len(briers),
        "coverage": _ratio(len(briers), len(labels)),
        "scored_coverage": _ratio(len(briers), scored_count),
        "brier": _ratio(sum(briers), len(briers)),
        "log_loss": _ratio(sum(losses), len(losses)),
        "log_loss_probability_floor": 1e-15,
        "zero_gold_probability_count": zero_gold_count,
        "ranked_probability_score": _ratio(sum(ranked_scores), len(ranked_scores)),
    }


def _metrics(
    labels: list[dict],
    predictions: dict[int, dict],
    macro_labels: list[str] | None = None,
) -> dict:
    classes = range(1, 6)
    confusion = {
        str(actual): {str(predicted): 0 for predicted in (*classes, "missing")}
        for actual in classes
    }
    status_counts = dict.fromkeys(("scored", "failed", "unresolved", "missing"), 0)
    errors = []
    rare_total = rare_correct = severe = 0
    for label in labels:
        actual = label["level"]
        prediction = predictions.get(label["word_id"])
        status = prediction["status"] if prediction else "missing"
        status_counts[status] += 1
        predicted = prediction["rarity_level"] if status == "scored" else None
        confusion[str(actual)][str(predicted) if predicted is not None else "missing"] += 1
        if predicted is not None:
            errors.append(abs(actual - predicted))
        if actual >= 4:
            rare_total += 1
            rare_correct += predicted is not None and predicted >= 4
            severe += predicted is not None and predicted <= 2
    per_class = {}
    for level in classes:
        key = str(level)
        true_positive = confusion[key][key]
        support = sum(confusion[key].values())
        predicted_count = sum(row[key] for row in confusion.values())
        per_class[key] = {
            "support": support,
            "predicted_count": predicted_count,
            "precision": _ratio(true_positive, predicted_count),
            "recall": _ratio(true_positive, support),
            "f1": _ratio(2 * true_positive, support + predicted_count),
        }
    f1_labels = (
        macro_labels
        if macro_labels is not None
        else [level for level, counts in per_class.items() if counts["support"]]
    )
    return {
        "gold_count": len(labels),
        "scored_count": len(errors),
        "missing_count": len(labels) - len(errors),
        "status_counts": status_counts,
        "coverage": _ratio(len(errors), len(labels)),
        "conditional_mae": _ratio(sum(errors), len(errors)),
        "macro_f1": _ratio(sum(per_class[level]["f1"] or 0 for level in f1_labels), len(f1_labels)),
        "macro_f1_labels": f1_labels,
        "per_class": per_class,
        "l1_precision": per_class["1"]["precision"],
        "l1_recall": per_class["1"]["recall"],
        "rare_recall": _ratio(rare_correct, rare_total),
        "severe_rare_to_common": severe,
        "confusion": confusion,
    }


def _paired_difference(
    labels: list[dict],
    predictions: dict[int, dict],
    baseline: dict[int, dict],
    macro_labels: list[str] | None = None,
) -> dict:
    candidate_metrics = _metrics(labels, predictions, macro_labels)
    baseline_metrics = _metrics(labels, baseline, macro_labels)
    differences = []
    for label in labels:
        word_id = label["word_id"]
        candidate = predictions.get(word_id)
        reference = baseline.get(word_id)
        if (
            candidate is None
            or candidate["status"] != "scored"
            or reference is None
            or reference["status"] != "scored"
        ):
            continue
        differences.append(
            abs(label["level"] - candidate["rarity_level"])
            - abs(label["level"] - reference["rarity_level"])
        )
    return {
        "coverage_delta": candidate_metrics["coverage"] - baseline_metrics["coverage"],
        "macro_f1_delta": candidate_metrics["macro_f1"] - baseline_metrics["macro_f1"],
        "paired_scored_count": len(differences),
        "paired_coverage": _ratio(len(differences), len(labels)),
        "paired_mae_delta": _ratio(sum(differences), len(differences)),
    }


def _percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _bootstrap(
    labels: list[dict],
    predictions: dict[int, dict],
    baseline: dict[int, dict],
    samples: int,
    seed: int,
) -> dict:
    groups: dict[str, list[dict]] = {}
    for label in sorted(labels, key=lambda item: item["word_id"]):
        groups.setdefault(label["group"], []).append(label)
    group_ids = sorted(groups)
    values: dict[str, list[float]] = {
        "coverage_delta": [],
        "macro_f1_delta": [],
        "paired_mae_delta": [],
    }
    rng = random.Random(seed)
    macro_labels = sorted({str(label["level"]) for label in labels})
    for _ in range(samples if len(groups) >= 2 else 0):
        sampled_labels = [
            label for group in rng.choices(group_ids, k=len(group_ids)) for label in groups[group]
        ]
        differences = _paired_difference(sampled_labels, predictions, baseline, macro_labels)
        for metric, observations in values.items():
            if differences[metric] is not None:
                observations.append(differences[metric])
    return {
        "method": "paired_group_percentile",
        "confidence": 0.95,
        "samples": samples,
        "seed": seed,
        "group_count": len(groups),
        "reason": "At least two gold groups required" if len(groups) < 2 else None,
        "intervals": {
            metric: {
                "lower": _percentile(observations, 0.025),
                "upper": _percentile(observations, 0.975),
                "valid_samples": len(observations),
            }
            for metric, observations in values.items()
        },
    }


def evaluate_predictions(
    labels_csv: Path,
    predictions_csv: Path,
    *,
    split: str = "test",
    baseline_csv: Path | None = None,
    bootstrap_samples: int = 200,
    seed: int = 0,
) -> dict:
    """Evaluate validated CSVs without network calls or model inference.

    Unweighted metrics describe the supplied gold sample, not population prevalence.
    Legacy run CSVs may omit status; all such rows must have valid rarity_level.
    Macro F1 uses classes present in the selected gold split; missing/failed/unresolved
    predictions count as false negatives. MAE and proper scores are conditional on
    their explicitly reported coverage. Brier is the sum over five outcomes; RPS is
    divided by four. Log loss clips gold probability at 1e-15 (reported in output).

    Baseline coverage and F1 use exactly the same gold population and class set.
    Paired MAE uses only words scored by both systems. Bootstrap resamples entire
    gold groups, fixes the original class set, and reports valid draws per metric.
    Confidence intervals are unavailable with fewer than two groups.
    """
    if (
        isinstance(bootstrap_samples, bool)
        or not isinstance(bootstrap_samples, int)
        or bootstrap_samples < 0
    ):
        raise ValueError("bootstrap_samples must be a nonnegative integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    labels = _read_labels(labels_csv)
    predictions = _read_predictions(predictions_csv, {label["word_id"] for label in labels})
    selected = [label for label in labels if label["split"] == split]
    if not selected:
        raise ValueError(f"No gold labels for split {split!r}")
    report = {
        "schema_version": 1,
        "split": split,
        "weighting": "unweighted_gold_sample",
        "macro_f1_class_policy": "classes_present_in_selected_gold",
        **_metrics(selected, predictions),
        "probability_metrics": _probability_metrics(selected, predictions),
    }
    if baseline_csv is not None:
        baseline = _read_predictions(baseline_csv, {label["word_id"] for label in labels})
        report["comparison"] = {
            "baseline": _metrics(selected, baseline),
            **_paired_difference(selected, predictions, baseline),
            "bootstrap": _bootstrap(selected, predictions, baseline, bootstrap_samples, seed),
        }
    return report
