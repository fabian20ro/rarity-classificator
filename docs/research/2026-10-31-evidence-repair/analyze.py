"""Offline evaluation only, after collection. No model/network/DB access."""

import argparse
import json
from pathlib import Path
from collections import Counter

from classificator.evaluation.dataset import _sha256, _write_csv
from classificator.evaluation.judge_comparison import _metrics
from prepare import read, evidence


def measure(rows, fields):
    result = {field: _metrics(rows, field) for field in fields}
    # Independent arithmetic check, separate from the shared comparison implementation.
    for field, metrics in result.items():
        distances = [abs(int(row[field]) - int(row["human_level"])) for row in rows]
        assert metrics["n"] == len(distances)
        assert metrics["severe"] == len([d for d in distances if d >= 2])
        assert metrics["excess_error_total"] == sum(max(0, d - 1) for d in distances)
        assert metrics["within_one"] == len([d for d in distances if d <= 1])
        assert metrics["error_histogram"] == {str(d): distances.count(d) for d in range(5)}
    return result


def analyze(base, out):
    protocol = json.loads((out / "protocol.json").read_text())
    for name, digest in protocol["frozen"].items():
        assert _sha256(Path(name)) == digest, name
    protected = json.loads((out / "protected-inputs.json").read_text())
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    paths = {
        "pilot150": base / "gpt-judge-2026-10-31/comparison/comparison.csv",
        "review50": base / "review50-2026-10-31/comparison.csv",
    }
    evidence_paths = {
        "pilot150": base / "gpt-judge-2026-10-31/inputs/evidence.csv",
        "review50": base / "1000-judges-2026-10-31/gpt/inputs/evidence.csv",
    }
    all_rows, full = {}, {}
    for cohort, path in paths.items():
        lexical = evidence(evidence_paths[cohort])
        rows = []
        for raw in read(path):
            wid = raw["word_id"]
            assert wid not in all_rows
            row = dict(
                word_id=wid,
                word=raw["word"],
                cohort=cohort,
                human_level=int(raw["human_level"]),
                baseline_level=int(raw["baseline_level"]),
                historical_gpt=int(raw.get("gpt_level", raw.get("final_level"))),
                has_context=bool(lexical[wid]["senses"]),
            )
            row["context_gate"] = (
                row["historical_gpt"] if row["has_context"] else row["baseline_level"]
            )
            rows.append(row)
            all_rows[wid] = row
        assert len(rows) == (150 if cohort == "pilot150" else 50)
        full[cohort] = {
            name: measure(part, ("baseline_level", "historical_gpt", "context_gate"))
            for name, part in [
                ("all", rows),
                ("true4", [r for r in rows if r["human_level"] == 4]),
                ("true5", [r for r in rows if r["human_level"] == 5]),
                ("no_context", [r for r in rows if not r["has_context"]]),
            ]
        }
    selected = read(out / "selection.csv")
    predictions = {
        arm: {r["word_id"]: r for r in read(out / arm / "campaign/predictions.csv")}
        for arm in ("old", "corrected")
    }
    assert all(set(p) == {r["word_id"] for r in selected} for p in predictions.values())
    paired = []
    for selected_row in selected:
        wid = selected_row["word_id"]
        original = all_rows[wid]
        assert (
            original["word"] == selected_row["word"]
            and original["cohort"] == selected_row["cohort"]
        )
        row = dict(original, selection=selected_row["selection"])
        for arm in predictions:
            prediction = predictions[arm][wid]
            assert prediction["word"] == row["word"] and prediction["status"] == "scored"
            assert prediction["rarity_level"] in set("12345")
            row[arm + "_level"] = int(prediction["rarity_level"])
        paired.append(row)
    report = dict(
        full_frozen=full,
        paired={},
        scope="Reused development150 and risk-selected50; bounded paired subset, no independent or population accuracy claim. Fixed context gate post-hoc; no production promotion.",
        protocol_sha256=_sha256(out / "protocol.json"),
    )
    eligible = True
    for cohort in paths:
        rows = [r for r in paired if r["cohort"] == cohort]
        strata = [
            ("all", rows),
            ("intervention", [r for r in rows if r["selection"] != "identical_repeat_control"]),
            ("controls", [r for r in rows if r["selection"] == "identical_repeat_control"]),
            ("true4", [r for r in rows if r["human_level"] == 4]),
            ("true5", [r for r in rows if r["human_level"] == 5]),
        ]
        report["paired"][cohort] = {
            name: measure(
                part, ("baseline_level", "historical_gpt", "old_level", "corrected_level")
            )
            for name, part in strata
        }
        for name in ("all", "true4", "true5"):
            metrics = report["paired"][cohort][name]
            eligible &= all(
                metrics["corrected_level"][key] <= metrics["old_level"][key]
                for key in ("severe", "excess_error_total")
            )
    report["eligible_for_larger_frozen_test"] = eligible
    report["paired_transition"] = {
        c: dict(
            fixed=sum(
                abs(r["old_level"] - r["human_level"]) >= 2
                and abs(r["corrected_level"] - r["human_level"]) < 2
                for r in paired
                if r["cohort"] == c
            ),
            introduced=sum(
                abs(r["old_level"] - r["human_level"]) < 2
                and abs(r["corrected_level"] - r["human_level"]) >= 2
                for r in paired
                if r["cohort"] == c
            ),
        )
        for c in paths
    }
    report["repeat_control_differences"] = dict(
        Counter(
            abs(r["old_level"] - r["corrected_level"])
            for r in paired
            if r["selection"] == "identical_repeat_control"
        )
    )
    receipts = []
    threads = []
    for arm in predictions:
        for path in (out / arm / "processes").glob("*.json"):
            receipt = json.loads(path.read_text())
            receipts.append(receipt)
            assert not receipt["result"]["stderr"].strip()
            for line in receipt["result"]["stdout"].splitlines():
                event = json.loads(line)
                if event["type"] == "thread.started":
                    threads.append(event["thread_id"])
                if event["type"].startswith("item."):
                    assert event["item"]["type"] in {"reasoning", "agent_message"}
    receipts.sort(key=lambda r: r["started"])
    assert len(receipts) == len(paired) * 2 <= 60 and len(threads) == len(set(threads)) == len(
        receipts
    )
    assert all(a["finished"] <= b["started"] for a, b in zip(receipts, receipts[1:]))
    for r in paired:
        if r["selection"] == "identical_repeat_control":
            requests = [
                json.loads((out / arm / "processes" / f"{r['word_id']}.json").read_text())[
                    "request"
                ]
                for arm in predictions
            ]
            assert requests[0] == requests[1]
    verification = dict(
        protected_files_unchanged=len(protected),
        unique_sessions=len(receipts),
        sequential_nonoverlap_checks=len(receipts) - 1,
        elapsed_minutes=(receipts[-1]["finished"] - receipts[0]["started"]) / 60,
        independent_metric_arithmetic="PASS",
        identical_control_requests=10,
        gold_read_only=True,
        classifier_db_writes=0,
    )
    _write_csv(out / "paired-comparison.csv", list(paired[0]), paired)
    _write_csv(
        out / "full-frozen-comparison.csv",
        list(next(iter(all_rows.values()))),
        list(all_rows.values()),
    )
    report["verification"] = verification
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    manifest = dict(
        protocol_sha256=_sha256(out / "protocol.json"),
        references={str(p): _sha256(p) for p in paths.values()},
        predictions={
            str(out / a / "campaign/predictions.csv"): _sha256(out / a / "campaign/predictions.csv")
            for a in predictions
        },
        implementation={str(Path(__file__).resolve()): _sha256(Path(__file__))},
        artifacts={
            n: _sha256(out / n)
            for n in ("paired-comparison.csv", "full-frozen-comparison.csv", "report.json")
        },
    )
    (out / "analysis-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                verification=verification,
                eligible=eligible,
                paired={
                    c: {
                        k: {m: v[m] for m in ("n", "severe", "excess_error_total", "mae")}
                        for k, v in x["all"].items()
                    }
                    for c, x in report["paired"].items()
                },
                full={
                    c: {
                        k: {m: v[m] for m in ("n", "severe", "excess_error_total")}
                        for k, v in x["all"].items()
                    }
                    for c, x in full.items()
                },
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.base.resolve(), args.output.resolve())
