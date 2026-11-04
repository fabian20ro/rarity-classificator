"""Immutable offline import of the frozen risk-selected review; no inference/DB I/O.

Run with PYTHONPATH=src. Raw reviews and corpus signals remain local; only
aggregated report/receipts and this reproduction script belong in the PR.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from classificator.evaluation.judge_comparison import _metrics


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, key="word_id"):
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    indexed = {r[key]: r for r in rows}
    if len(rows) != len(indexed):
        raise ValueError(f"Duplicate IDs: {path}")
    return indexed


def write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def run(campaign, sample, export, pilot, output):
    if output.exists():
        raise FileExistsError(output)
    inputs = {
        "export": export, "pilot150": pilot,
        "pack": campaign / "review-public/cases.json",
        "queue": campaign / "final-routing/review-queue.csv",
        "baseline": campaign / "comparison-inputs/baseline.csv",
        "gpt": campaign / "comparison-inputs/gpt.csv",
        "qwen": campaign / "comparison-inputs/qwen.csv",
        "decisions": campaign / "final-routing/decisions.csv",
        "forms": sample / "forms.csv", "signals": sample / "signals.csv",
        "script": Path(__file__),
    }
    hashes = {name: sha(path) for name, path in inputs.items()}
    raw = json.loads(export.read_text())
    pack = json.loads(inputs["pack"].read_text())
    if raw.get("case_pack") != pack or any(raw.get(k) != pack[k] for k in ("version", "pack_sha256")):
        raise ValueError("Frozen pack mismatch")
    if raw.get("ai_exposure") is not False or raw.get("preserved_raw") is not None:
        raise ValueError("Unexpected exposure or unreconciled state")
    if raw.get("conflict_archive") or raw.get("conflict_resolutions"):
        raise ValueError("Conflict history requires explicit audit")
    forms = {f["word_id"]: f for f in pack["forms"]}
    queue = read(inputs["queue"])
    if len(forms) != 50 or len(pack["forms"]) != 50 or set(forms) != set(queue) or set(raw["answers"]) != set(forms):
        raise ValueError("Review membership must match all frozen 50 forms")
    pilot_rows = read(pilot)
    if len(pilot_rows) != 150 or set(pilot_rows) & set(forms):
        raise ValueError("Pilot/reference overlap")
    baseline, gpt, qwen = (read(inputs[k]) for k in ("baseline", "gpt", "qwen"))
    decisions = read(inputs["decisions"])
    sample_forms, signals = (read(inputs[k], "form_id") for k in ("forms", "signals"))
    events = raw["events"]
    if len({e["id"] for e in events}) != len(events) or any(e["word_id"] not in forms for e in events):
        raise ValueError("Invalid/duplicate event identity")
    responses, comparison, causes = [], [], []
    for wid, f in forms.items():
        a = raw["answers"][wid]
        if a["decision"] != "rated" or any(type(a[k]) is not int or a[k] not in range(1, 6) for k in ("level", "first_level")):
            raise ValueError("Every review response must have a valid explicit score")
        contexts = {c["context_id"] for c in f["contexts"]}
        for cid in (a["selected_context_id"], a["first_context_id"]):
            if cid not in contexts and not (cid == "unavailable" and not contexts) and not (cid == "other" and a["notes"].strip()):
                raise ValueError("Invalid selected context")
        rates = [e for e in events if e["word_id"] == wid and e["kind"] == "rate"]
        if not rates or rates[-1]["level"] != a["level"] or rates[0]["level"] != a["first_level"]:
            raise ValueError("Answer/history mismatch")
        for source in (queue, baseline, gpt, decisions, sample_forms, signals):
            if source[wid]["word"] != f["word"]:
                raise ValueError("Exact spelling mismatch")
        if gpt[wid]["status"] != "scored" or (wid in qwen and (qwen[wid]["word"] != f["word"] or qwen[wid]["status"] != "scored")):
            raise ValueError("Invalid native prediction")
        response = dict(word_id=wid, word=f["word"], working_level=a["level"], first_level=a["first_level"], reference_kind="risk_selected50_exact_form", selected_context_id=a["selected_context_id"], first_context_id=a["first_context_id"], notes=a["notes"], updated_at=a["updated_at"], event_count=sum(e["word_id"] == wid for e in events), pack_sha256=pack["pack_sha256"], source_sha256=hashes["export"])
        responses.append(response)
        r = dict(word_id=wid, word=f["word"], human_level=a["level"], baseline_level=int(baseline[wid]["baseline_level"]), gpt_level=int(gpt[wid]["rarity_level"]), qwen_level=int(qwen[wid]["rarity_level"]) if wid in qwen else "", qwen_observed=wid in qwen, selection_slice=sample_forms[wid]["selection_slice"], has_context=bool(contexts), has_wordfreq=bool(baseline[wid]["wordfreq"]), multiple_pos=decisions[wid]["multiple_pos"] == "True", multiple_spellings=signals[wid]["multiple_spellings"] == "1", reason_flags=decisions[wid]["reason_flags"])
        for method in ("baseline", "gpt", "qwen"):
            prediction = r[method + "_level"]
            if prediction == "":
                r.update({method + "_" + k: "" for k in ("signed_error", "absolute_error", "severe", "excess_loss")})
                continue
            if prediction not in range(1, 6):
                raise ValueError("Prediction outside 1..5")
            delta = prediction - a["level"]
            r.update({method + "_signed_error": delta, method + "_absolute_error": abs(delta), method + "_severe": abs(delta) >= 2, method + "_excess_loss": max(abs(delta) - 1, 0)})
            if abs(delta) >= 2:
                mechanism = "score_too_rare" if delta > 0 else "score_too_common"
                if method == "baseline" and not r["has_wordfreq"]:
                    mechanism = "missing_wordfreq_fallback4_too_rare"
                hypotheses = []
                if not contexts:
                    hypotheses.append("missing_lexical_context")
                if r["multiple_pos"]:
                    hypotheses.append("exact_form_or_pos_familiarity")
                if r["multiple_spellings"]:
                    hypotheses.append("orthographic_sense_substitution")
                if method == "baseline" and r["has_wordfreq"]:
                    hypotheses.append("frequency_familiarity_mismatch")
                causes.append(dict(word_id=wid, word=f["word"], method=method, human_level=a["level"], predicted_level=prediction, absolute_error=abs(delta), excess_loss=max(abs(delta)-1, 0), observed_failure=mechanism, hypotheses="|".join(hypotheses), evidence_status="prediction_error_confirmed; lexical_or_cognitive_cause_unproven", has_context=bool(contexts), has_wordfreq=r["has_wordfreq"], selected_context_id=a["selected_context_id"], reviewer_note=a["notes"]))
        comparison.append(r)
    subsets = {
        "review50": comparison,
        "qwen_paired12": [r for r in comparison if r["qwen_observed"]],
        "with_context": [r for r in comparison if r["has_context"]],
        "without_context": [r for r in comparison if not r["has_context"]],
        "without_wordfreq": [r for r in comparison if not r["has_wordfreq"]],
        "with_wordfreq": [r for r in comparison if r["has_wordfreq"]],
        "missing_both": [r for r in comparison if not r["has_wordfreq"] and not r["has_context"]],
        "human_4_or_5": [r for r in comparison if r["human_level"] >= 4],
        "general_selected": [r for r in comparison if r["selection_slice"] == "general600"],
        "stress_selected": [r for r in comparison if r["selection_slice"] != "general600"],
    }
    report = {"review_selection": "frozen risk-selected sample, not population accuracy", "human_references": 50, "prior_pilot_separate": 150, "unreviewed1000": 950, "qwen_observed_in_review": sum(r["qwen_observed"] for r in comparison), "metrics": {}, "paired": {}}
    for name, rows in subsets.items():
        report["metrics"][name] = {m: _metrics([r for r in rows if r[m + "_level"] != ""], m + "_level") for m in ("baseline", "gpt", "qwen")}
    for method in ("gpt", "qwen"):
        rows = [r for r in comparison if r[method + "_level"] != ""]
        report["paired"][method + "_vs_baseline"] = dict(n=len(rows), severe_fixed=sum(r["baseline_severe"] and not r[method + "_severe"] for r in rows), severe_introduced=sum(not r["baseline_severe"] and r[method + "_severe"] for r in rows), both_severe=sum(r["baseline_severe"] and r[method + "_severe"] for r in rows), neither_severe=sum(not r["baseline_severe"] and not r[method + "_severe"] for r in rows))
    report["review_yield"] = dict(at_least_one_gpt_baseline_severe=sum(r["baseline_severe"] or r["gpt_severe"] for r in comparison), no_gpt_baseline_severe=sum(not r["baseline_severe"] and not r["gpt_severe"] for r in comparison), interpretation="conditional review yield, not recall or unreviewed accuracy")
    report["cause_groups"] = {tag: {"method_errors": sum(c["observed_failure"] == tag for c in causes), "forms": len({c["word_id"] for c in causes if c["observed_failure"] == tag})} for tag in sorted({c["observed_failure"] for c in causes})}
    report["history"] = dict(events=len(events), notes=sum(bool(a["notes"].strip()) for a in raw["answers"].values()), net_revisions=sum(a["level"] != a["first_level"] for a in raw["answers"].values()), last_event=events[-1]["at"])
    if hashes != {name: sha(path) for name, path in inputs.items()}:
        raise ValueError("Input mutated during import")
    output.mkdir(parents=True)
    (output / "source-export.json").write_bytes(export.read_bytes())
    write(output / "review-responses.csv", responses)
    write(output / "comparison.csv", comparison)
    write(output / "cause-audit.csv", causes)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    manifest = dict(schema="review50-import-v1", pack_sha256=pack["pack_sha256"], source="private Sites synchronized browser export", inputs={name: {"path": str(path.resolve()), "sha256": hashes[name]} for name, path in inputs.items()}, outputs={p.name: sha(p) for p in sorted(output.iterdir())})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for flag in ("campaign", "sample", "export", "pilot", "output"):
        p.add_argument("--" + flag, type=Path, required=True)
    a = p.parse_args()
    r = run(a.campaign, a.sample, a.export, a.pilot, a.output)
    print(json.dumps({"paired": r["paired"], "all50": {k: {x: v[x] for x in ("n", "severe", "excess_error_total", "mae", "within_one")} for k, v in r["metrics"]["review50"].items()}}, indent=2))
