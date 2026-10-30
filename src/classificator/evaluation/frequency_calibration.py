"""Freeze ordinal thresholds from clarified development labels, before annotation."""

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _read_csv, _sha256, _vocabulary, _write_csv
from .form_frequency_report import REFERENCE_KINDS
from ..models import BaseWordRow
from ..scoring.frequency import FrequencyScorer


def _fit(observed):
    # Absolute ordinal error is the sum of four binary boundary errors.
    # A fixed logarithmic grid permits empty predicted classes without splitting ties.
    grid = {10 ** (exponent / 10) for exponent in range(-120, 1)}
    no_l5 = not any(level == 5 for _, level in observed)
    fixed_l5 = min(frequency for frequency, _ in observed) / 10 if no_l5 else None
    if fixed_l5 is not None:
        grid.add(fixed_l5)
    grid = sorted(grid, reverse=True)
    states = {}
    for boundary in range(1, 5):
        next_states = {}
        for index, threshold in enumerate(grid):
            if boundary == 4 and fixed_l5 is not None and threshold != fixed_l5:
                continue
            cost = sum(
                (frequency < threshold) != (level > boundary) for frequency, level in observed
            )
            candidates = [(0, ())] if boundary == 1 else [v for k, v in states.items() if k < index]
            if not candidates:
                continue
            prior_cost, prior = min(candidates, key=lambda v: (v[0], tuple(-t for t in v[1])))
            next_states[index] = (prior_cost + cost, prior + (threshold,))
        states = next_states
    if not states:
        raise ValueError("No feasible thresholds on frozen grid")
    cost, thresholds = min(states.values(), key=lambda v: (v[0], tuple(-t for t in v[1])))
    return dict(
        thresholds=list(thresholds),
        fit_mae=cost / len(observed),
        observed=len(observed),
        class_support={str(level): sum(y == level for _, y in observed) for level in range(1, 6)},
        boundary_support={
            str(k): dict(
                common=sum(y <= k for _, y in observed), rare=sum(y > k for _, y in observed)
            )
            for k in range(1, 5)
        },
        l5_boundary="convention_min_observed_div10_not_identified" if no_l5 else "fit_on_pilot",
        objective="minimum unweighted ordinal MAE on observed clarified pilot forms",
        tie_break="lexicographically largest descending thresholds (rarer predictions on ties)",
        grid="10**(k/10), integer k=-120..0; append fixed L5 convention if needed",
    )


def freeze_frequency_thresholds(
    pilot_csv: Path, reference_csv: Path, features_csv: Path, output_dir: Path
):
    """Fit on pilot only, then freeze predictions for every supplied feature row."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    pilot = {int(r["word_id"]): r["word"] for r in _vocabulary(pilot_csv)}
    labels = {}
    seen = set()
    for row in _read_csv(reference_csv, {"word_id", "word", "working_level", "reference_kind"}):
        word_id = int(row["word_id"])
        if word_id in seen or pilot.get(word_id) != row["word"]:
            raise ValueError("Reference must match pilot identities only")
        seen.add(word_id)
        if row["reference_kind"] not in REFERENCE_KINDS | {"initial_opaque_form_pos"}:
            raise ValueError("Unknown reference kind")
        level = int(row["working_level"])
        if not 1 <= level <= 5:
            raise ValueError("Invalid reference level")
        if row["reference_kind"] in REFERENCE_KINDS:
            labels[word_id] = level
    if seen != pilot.keys():
        raise ValueError("Reference must cover the complete pilot")
    features = {}
    for row in _read_csv(features_csv, {"word_id", "word", "wordfreq", "rebus"}):
        if set(row) != {"word_id", "word", "wordfreq", "rebus"}:
            raise ValueError("Feature CSV cannot contain labels, estimates or extra fields")
        word_id = int(row["word_id"])
        if word_id <= 0 or word_id in features or not row["word"].strip():
            raise ValueError("Invalid feature identity")
        if word_id in pilot and row["word"] != pilot[word_id]:
            raise ValueError("Feature/pilot spelling mismatch")
        for source in ("wordfreq", "rebus"):
            value = float(row[source]) if row[source] else None
            if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError("Invalid frequency")
            row[source] = value or None
        features[word_id] = row
    if not pilot.keys() <= features.keys():
        raise ValueError("Missing pilot feature rows")
    result = dict(
        schema=1,
        policy="pilot-only-monotone-mae-grid-v1",
        fit_ids=sorted(labels),
        inputs={str(p.resolve()): _sha256(p) for p in (pilot_csv, reference_csv, features_csv)},
        implementation_sha256=_sha256(Path(__file__)),
    )
    predictions = [
        dict(word_id=i, word=r["word"], split="dev" if i in pilot else "test")
        for i, r in sorted(features.items())
    ]
    for source in ("wordfreq", "rebus"):
        observed = [
            (features[i][source], level)
            for i, level in labels.items()
            if features[i][source] is not None
        ]
        if not observed:
            raise ValueError("No observed clarified pilot data: " + source)
        result[source] = _fit(observed)
        scorer = FrequencyScorer(
            {i: r[source] for i, r in features.items()},
            thresholds=tuple(result[source]["thresholds"]),
        )
        items = [BaseWordRow(r["word_id"], r["word"], "") for r in predictions]
        for row, outcome in zip(predictions, scorer.score_batch(items)):
            row[source + "_level"] = outcome.rarity_level
            row[source + "_status"] = outcome.status
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".thresholds-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        _write_csv(staged / "predictions.csv", list(predictions[0]), predictions)
        result["predictions_sha256"] = _sha256(staged / "predictions.csv")
        (staged / "thresholds.json").write_text(json.dumps(result, indent=2) + "\n")
        staged.rename(output_dir)
    return result
