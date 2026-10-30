"""Provider-neutral offline metrics; human references never enter inference."""

from collections import Counter
import json
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _read_csv, _sha256, _write_csv


def _indexed(path, fields):
    rows = _read_csv(path, fields | {"word_id"})
    result = {}
    for row in rows:
        wid = row["word_id"]
        if (
            not wid.isascii()
            or not wid.isdigit()
            or int(wid) <= 0
            or str(int(wid)) != wid
            or wid in result
        ):
            raise ValueError("Invalid or duplicate identity")
        result[wid] = row
    if not result:
        raise ValueError("Empty comparison input")
    return result


def _level(value):
    if value not in {"1", "2", "3", "4", "5"}:
        raise ValueError("Level must be 1..5")
    return int(value)


def _metrics(rows, field):
    errors = Counter(abs(int(r[field]) - int(r["human_level"])) for r in rows)
    confusion = [[0] * 5 for _ in range(5)]
    for r in rows:
        confusion[int(r["human_level"]) - 1][int(r[field]) - 1] += 1
    per_level = {}
    for level in range(1, 6):
        support = sum(confusion[level - 1])
        predicted = sum(row[level - 1] for row in confusion)
        correct = confusion[level - 1][level - 1]
        per_level[str(level)] = dict(
            support=support,
            predicted=predicted,
            correct=correct,
            precision=correct / predicted if predicted else None,
            recall=correct / support if support else None,
            severe=sum(
                confusion[level - 1][other - 1] for other in range(1, 6) if abs(level - other) >= 2
            ),
        )
    return dict(
        per_level=per_level,
        n=len(rows),
        exact=errors[0],
        within_one=errors[0] + errors[1],
        severe=sum(errors[k] for k in (2, 3, 4)),
        excess_error_total=sum((k - 1) * errors[k] for k in (2, 3, 4)),
        mae=sum(k * v for k, v in errors.items()) / len(rows) if rows else None,
        error_histogram={str(k): errors[k] for k in range(5)},
        confusion=confusion,
        predicted_counts={str(k): sum(r[k - 1] for r in confusion) for k in range(1, 6)},
    )


def _diagnostic(rows, budget):
    severe = {r["word_id"] for r in rows if abs(r["baseline_level"] - r["human_level"]) >= 2}

    def key(row, assisted):
        gap = abs(row["final_level"] - row["baseline_level"])
        evidence = (not row["has_context"], row["multiple_pos"])
        # Negative keys put high discrepancy/missingness first. No gold in ranking.
        return (
            ((-int(gap >= 2), -gap) if assisted else ())
            + tuple(-int(x) for x in evidence)
            + (hashlib.sha256(("qwen-pilot-v1:" + row["word_id"]).encode()).hexdigest(),)
        )

    def measure(selected):
        ids = [r["word_id"] for r in selected]
        found = len(set(ids) & severe)
        return dict(
            selected_ids=ids,
            budget=len(ids),
            review_fraction=len(ids) / len(rows),
            recovered_baseline_severe=found,
            baseline_severe=len(severe),
            precision=found / len(ids) if ids else None,
            recall=found / len(severe) if severe else None,
            false_alarms=len(ids) - found,
        )

    result = dict(primary={}, secondary_top5_per_fold={})
    for name, assisted in [("evidence_only", False), ("judge_assisted", True)]:
        ordered = sorted(rows, key=lambda row: key(row, assisted))
        result["primary"][name] = measure(ordered[:budget])
        selected = []
        for fold in sorted({r["fold"] for r in rows}):
            selected.extend([r for r in ordered if r["fold"] == fold][:5])
        result["secondary_top5_per_fold"][name] = measure(selected)
    result["interpretation"] = (
        "Deterministic exploratory triage; secondary25/150 review rate does not match deployment50/1000. No fitted weights or population confidence."
    )
    return result


def compare_judge_csv(
    predictions_csv,
    reference_csv,
    baseline_csv,
    evidence_csv,
    folds_csv,
    output_dir,
    *,
    review_budget=8,
):
    """Compare all forms, recording a baseline fallback for each native failure."""
    if type(review_budget) is not int or review_budget <= 0:
        raise ValueError("Review budget must be positive")
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    reference = _indexed(reference_csv, {"word", "working_level", "reference_kind"})
    predictions = _indexed(predictions_csv, {"word", "status", "rarity_level"})
    baseline = _indexed(baseline_csv, {"word", "baseline_level", "wordfreq"})
    source_evidence = _indexed(evidence_csv, {"word", "evidence_json"})
    folds = _indexed(folds_csv, {"group", "fold"})
    if any(set(part) != set(reference) for part in (predictions, baseline, source_evidence, folds)):
        raise ValueError("Comparison inputs must cover identical IDs")
    groups = {}
    evidence = {}
    for wid, ref in reference.items():
        if not ref["word"].strip() or any(
            part[wid]["word"] != ref["word"] for part in (predictions, baseline, source_evidence)
        ):
            raise ValueError("Exact spelling mismatch")
        _level(ref["working_level"])
        _level(baseline[wid]["baseline_level"])
        if "human_level" in baseline[wid] and baseline[wid]["human_level"] != ref["working_level"]:
            raise ValueError("Baseline reference differs from current reference")
        pred = predictions[wid]
        if pred["status"] == "scored":
            _level(pred["rarity_level"])
        elif pred["status"] != "failed" or pred["rarity_level"]:
            raise ValueError("Failed predictions must have no native score")
        fold = folds[wid]
        if (
            not fold["group"]
            or not fold["fold"]
            or groups.setdefault(fold["group"], fold["fold"]) != fold["fold"]
        ):
            raise ValueError("Group split across folds")
        evidence[wid] = json.loads(source_evidence[wid]["evidence_json"])
        if (
            not isinstance(evidence[wid], dict)
            or not isinstance(evidence[wid].get("senses"), list)
            or not isinstance(evidence[wid].get("valid_pos"), list)
        ):
            raise ValueError("Invalid lexical evidence")
    rows = []
    for ref in sorted(reference.values(), key=lambda r: int(r["word_id"])):
        wid = ref["word_id"]
        pred = predictions[wid]
        base = baseline[wid]
        native = pred["status"] == "scored"
        rows.append(
            dict(
                word_id=wid,
                word=ref["word"],
                human_level=int(ref["working_level"]),
                baseline_level=int(base["baseline_level"]),
                judge_level=pred["rarity_level"],
                final_level=int(pred["rarity_level"]) if native else int(base["baseline_level"]),
                native_status=pred["status"],
                route="judge" if native else "baseline_after_failure",
                has_context=bool(evidence[wid]["senses"]),
                has_wordfreq=bool(base["wordfreq"]),
                reference_kind=ref["reference_kind"],
                fold=folds[wid]["fold"],
                group=folds[wid]["group"],
                multiple_pos=len(evidence[wid]["valid_pos"]) > 1,
            )
        )
    subsets = dict(
        all=rows,
        true4_or5=[r for r in rows if r["human_level"] >= 4],
        wordfreq_missing=[r for r in rows if not r["has_wordfreq"]],
        with_context=[r for r in rows if r["has_context"]],
        without_context=[r for r in rows if not r["has_context"]],
        clarified=[r for r in rows if r["reference_kind"] != "initial_opaque_form_pos"],
        opaque=[r for r in rows if r["reference_kind"] == "initial_opaque_form_pos"],
    )
    metrics = {
        method: {name: _metrics(part, field) for name, part in subsets.items()}
        for method, field in [
            ("baseline", "baseline_level"),
            ("judge_with_fallback", "final_level"),
        ]
    }
    base = metrics["baseline"]
    judge = metrics["judge_with_fallback"]
    gate = (
        judge["all"]["severe"] < base["all"]["severe"]
        and judge["all"]["excess_error_total"] <= base["all"]["excess_error_total"]
        and all(judge[s]["severe"] <= base[s]["severe"] for s in ("wordfreq_missing", "true4_or5"))
    )
    protected_cost_gate = all(
        judge[subset]["excess_error_total"] <= base[subset]["excess_error_total"]
        for subset in ("wordfreq_missing", "true4_or5")
    )
    native = sum(r["native_status"] == "scored" for r in rows)
    result = dict(
        coverage=dict(
            total=len(rows),
            native_scored=native,
            native_failed=len(rows) - native,
            fallback=len(rows) - native,
            final_scored=len(rows),
        ),
        metrics=metrics,
        promotion=dict(
            scorer_gate_pass=gate and protected_cost_gate,
            predeclared_count_gate_pass=gate,
            protected_excess_gate_pass=protected_cost_gate,
            scope="Exploratory reused pilot, not production authorization",
        ),
        diagnostic=_diagnostic(rows, review_budget),
    )
    primary = result["diagnostic"]["primary"]
    result["promotion"]["diagnostic_gate_pass"] = (
        primary["judge_assisted"]["recovered_baseline_severe"]
        > primary["evidence_only"]["recovered_baseline_severe"]
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".judge-comparison-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        _write_csv(staged / "comparison.csv", list(rows[0]), rows)
        (staged / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        manifest = dict(
            policy="fixed-judge-comparison-v1",
            review_budget=review_budget,
            inputs={
                str(p.resolve()): _sha256(p)
                for p in (predictions_csv, reference_csv, baseline_csv, evidence_csv, folds_csv)
            },
            implementation_sha256=_sha256(Path(__file__)),
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return result
