"""Fixed label-free routing and review export. Agreement is never a gold label."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ..models import BaseWordRow
from .chat_judge import _evidence
from .dataset import _read_csv, _sha256, _write_csv
from .judge_comparison import _indexed, _level

POLICY = {
    "version": "exact-form-conflicts-v1",
    "qwen": "GPT scored AND abs(GPT-baseline)>=2 AND usable lexical context",
    "review": "GPT failed OR initial abs(GPT-baseline)>=2; Qwen never vetoes",
    "rank": [
        "gpt_failed",
        "qwen_failed",
        "qwen_gpt_gap>=2",
        "span_desc",
        "initial_gap_desc",
        "missing_context",
        "multiple_pos",
        "seeded_id",
    ],
    "seed": "qwen-pilot-v1",
    "scores": "Operational baseline unchanged; proposed GPT with explicit failure fallback; no blend",
    "risk": "Ordinal conflict/technical/unknown flags, not calibrated probabilities",
}


def export_risk_csv(
    baseline_csv, evidence_csv, gpt_csv, output_dir, *, qwen_csv=None, review_budget=50
):
    """Export deterministic routes/queue; Qwen CSV must cover exactly the frozen route."""
    if type(review_budget) is not int or not 1 <= review_budget <= 50:
        raise ValueError("Review budget must be 1..50")
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    base = _indexed(baseline_csv, {"word", "baseline_level", "wordfreq"})
    gpt = _indexed(gpt_csv, {"word", "status", "rarity_level"})
    if set(base) != set(gpt):
        raise ValueError("Predictions must cover every baseline ID")
    if len({row["word"] for row in base.values()}) != len(base):
        raise ValueError("Each exact form requires one representative ID")
    for rows, fields in [
        (base, {"word_id", "word", "baseline_level", "wordfreq"}),
        (gpt, {"word_id", "word", "status", "rarity_level"}),
    ]:
        for row in rows.values():
            if set(row) != fields:
                raise ValueError("Only label-free projected CSV columns allowed")
    evidence = _evidence(
        evidence_csv, [BaseWordRow(int(wid), row["word"], "") for wid, row in base.items()]
    )
    decisions = []
    for wid in sorted(base, key=int):
        row, pred = base[wid], gpt[wid]
        if not row["word"].strip() or row["word"] != pred["word"]:
            raise ValueError("Exact spelling mismatch")
        b = _level(row["baseline_level"])
        if pred["status"] == "scored":
            g = _level(pred["rarity_level"])
        elif pred["status"] == "failed" and pred["rarity_level"] == "":
            g = None
        else:
            raise ValueError("Invalid native prediction status/score")
        e = evidence[int(wid)]
        gap = abs(g - b) if g is not None else 0
        has_context = bool(e["senses"])
        route = g is not None and gap >= 2 and has_context
        decisions.append(
            dict(
                word_id=wid,
                word=row["word"],
                operational_level=b,
                proposed_level=g if g is not None else b,
                proposed_route="gpt" if g is not None else "baseline_after_gpt_failure",
                gpt_level=g if g is not None else "",
                gpt_status=pred["status"],
                qwen_level="",
                qwen_status="pending" if route else "not_routed",
                qwen_route=route,
                initial_gap=gap,
                has_context=has_context,
                has_wordfreq=bool(row["wordfreq"]),
                multiple_pos=len(e["valid_pos"]) > 1,
                risk_band="technical" if g is None else "conflict" if gap >= 2 else "unknown",
                review_eligible=g is None or gap >= 2,
            )
        )
    route_ids = {r["word_id"] for r in decisions if r["qwen_route"]}
    if qwen_csv is not None:
        qwen_rows = _read_csv(qwen_csv, {"word_id", "word", "status", "rarity_level"})
        qwen = _indexed(qwen_csv, {"word", "status", "rarity_level"}) if qwen_rows else {}
        if set(qwen) != route_ids:
            raise ValueError("Qwen results must cover exactly the frozen route")
        for r in decisions:
            if not r["qwen_route"]:
                continue
            q = qwen[r["word_id"]]
            if set(q) != {"word_id", "word", "status", "rarity_level"} or q["word"] != r["word"]:
                raise ValueError("Invalid Qwen schema/spelling")
            if q["status"] == "scored":
                r["qwen_level"] = _level(q["rarity_level"])
            elif q["status"] != "failed" or q["rarity_level"]:
                raise ValueError("Invalid Qwen status/score")
            r["qwen_status"] = q["status"]
    for r in decisions:
        scores = [r["operational_level"], r["proposed_level"]]
        if r["qwen_status"] == "scored":
            scores.append(r["qwen_level"])
        r["span"] = max(scores) - min(scores)
        r["qwen_gpt_conflict"] = (
            r["qwen_status"] == "scored" and abs(r["qwen_level"] - r["proposed_level"]) >= 2
        )
        r["reason_flags"] = "|".join(
            name
            for name, present in [
                ("gpt_failed", r["gpt_status"] == "failed"),
                ("qwen_failed", r["qwen_status"] == "failed"),
                ("gpt_baseline_conflict", r["initial_gap"] >= 2),
                ("qwen_gpt_conflict", r["qwen_gpt_conflict"]),
                ("missing_context", not r["has_context"]),
                ("missing_wordfreq", not r["has_wordfreq"]),
                ("multiple_pos", r["multiple_pos"]),
            ]
            if present
        )

    def priority(r):
        return tuple(
            -int(x)
            for x in [
                r["gpt_status"] == "failed",
                r["qwen_status"] == "failed",
                r["qwen_gpt_conflict"],
                r["span"],
                r["initial_gap"],
                not r["has_context"],
                r["multiple_pos"],
            ]
        ) + (hashlib.sha256((POLICY["seed"] + ":" + r["word_id"]).encode()).hexdigest(),)

    eligible = sorted((r for r in decisions if r["review_eligible"]), key=priority)
    summary = dict(
        total=len(decisions),
        qwen_routed=len(route_ids),
        review_eligible=len(eligible),
        review_selected=min(len(eligible), review_budget),
        review_budget=review_budget,
        qwen_complete=qwen_csv is not None or not route_ids,
        policy=POLICY,
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".risk-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        fields = list(decisions[0])
        for name, rows in [
            ("decisions.csv", decisions),
            ("qwen-route.csv", [r for r in decisions if r["qwen_route"]]),
            ("review-queue.csv", eligible[:review_budget]),
        ]:
            _write_csv(staged / name, fields, rows)
        (staged / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        inputs = [baseline_csv, evidence_csv, gpt_csv] + ([qwen_csv] if qwen_csv else [])
        manifest = dict(
            policy=POLICY,
            review_budget=review_budget,
            code_sha256=_sha256(Path(__file__)),
            inputs={str(p): _sha256(p) for p in inputs},
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return summary
