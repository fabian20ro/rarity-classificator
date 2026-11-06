"""Simulate route promotion from pinned local CSVs. Run from the checkout with PYTHONPATH=src."""

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from classificator.evaluation.dataset import _lexeme, _read_csv, _sha256, _write_csv
from classificator.evaluation.judge_comparison import _indexed, _level, _metrics
from classificator.run_csv_repository import RunCsvRepository
from classificator.tools.quality_audit import run_quality_audit

HERE = Path(__file__).resolve().parent
ROUTES = {"frequency_thresholds": "wordfreq", "missing_group_median": "fallback"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_inventory(paths):
    scores = _indexed(
        paths["baseline"], {"word", "type", "rarity_level", "frequency", "route"}
    )
    before = _indexed(paths["before"], {"word", "type", "rarity_level", "version"})
    after = _indexed(paths["after"], {"word", "type", "rarity_level", "version"})
    mapping = _read_csv(
        paths["mapping"], {"live_word_id", "source_word_ids_json", "decision_source"}
    )
    require(
        set(before) == set(after) == {r["live_word_id"] for r in mapping},
        "Different IDs",
    )
    require(len(before) == len(mapping) == len(scores) == 77698, "Incomplete mapping")
    groups = defaultdict(set)
    for wid, row in scores.items():
        groups[_lexeme(row["word"]), row["type"]].add(wid)
    inventory = []
    old_levels = defaultdict(list)
    for row in mapping:
        wid = row["live_word_id"]
        old, now = before[wid], after[wid]
        word, pos = now["word"], now["type"]
        require(
            (word, pos, old["rarity_level"])
            == (row["word"], row["type"], row["current_level"]),
            "Mapping drift",
        )
        require((old["word"], old["type"]) == (word, pos), "Identity drift")
        ids = {str(i) for i in json.loads(row["source_word_ids_json"])}
        form = _lexeme(word)
        require(ids == groups[form, pos], "Invalid source group")
        values = {
            (scores[i]["route"], scores[i]["rarity_level"], scores[i]["frequency"])
            for i in ids
        }
        require(len(values) == 1, "Ambiguous baseline for group")
        route_key, raw, frequency = values.pop()
        route = ROUTES[route_key]
        require(
            (route == "wordfreq" and float(frequency or 0) > 0)
            or (route == "fallback" and not frequency and raw == "4"),
            "Invalid scoring route",
        )
        old_levels[form].append(_level(old["rarity_level"]))
        human = row["decision_source"] == "human"
        require(row["decision_source"] in {"human", "baseline"}, "Unknown source")
        require(
            (
                now["rarity_level"] == row["proposed_level"]
                if human
                else (now == old and raw == row["proposed_level"])
            ),
            "Unexpected post-apply state",
        )
        inventory.append(
            dict(
                word_id=wid,
                word=word,
                type=pos,
                form=form,
                human=human,
                route=route,
                current=_level(now["rarity_level"]),
                raw=_level(raw),
            )
        )
    return inventory, scores, old_levels


def get_evaluations(paths, scores, old_levels):
    oof = _indexed(
        paths["oof"],
        {"word", "human_level", "wordfreq_complete_level", "wordfreq_frequency"},
    )
    rows = []
    labels = {}
    for cohort, count in (("human_pilot150", 150), ("human_review50", 50)):
        gold = _indexed(paths[cohort], {"word", "working_level"})
        require(len(gold) == count, "Wrong cohort size")
        pilot = count == 150
        if pilot:
            require(gold.keys() == oof.keys(), "OOF IDs differ")
        for wid, ref in gold.items():
            raw = scores[wid]
            form = _lexeme(ref["word"])
            require(
                ref["word"] == raw["word"] and form not in labels,
                "Overlapping form or wrong identity",
            )
            labels[form] = level = _level(ref["working_level"])
            route = ROUTES[raw["route"]]
            fitted = _level(raw["rarity_level"])
            prediction = fitted
            if pilot:
                fold = oof[wid]
                require(
                    (fold["word"], _level(fold["human_level"])) == (ref["word"], level),
                    "OOF identity drift",
                )
                require(
                    float(fold["wordfreq_frequency"] or 0)
                    == float(raw["frequency"] or 0),
                    "OOF frequency drift",
                )
                prediction = _level(fold["wordfreq_complete_level"])
            rows.append(
                dict(
                    cohort=cohort,
                    route=route,
                    word_id=wid,
                    word=ref["word"],
                    human_level=level,
                    prediction=prediction,
                    frozen=fitted,
                    previous=min(old_levels[form]),
                )
            )
    return rows, labels


def screen(rows, policy):
    table, decisions = [], {}
    for route in ROUTES.values():
        reasons = []
        for cohort in ("human_pilot150", "human_review50"):
            subset = [r for r in rows if (r["route"], r["cohort"]) == (route, cohort)]
            metrics = {
                field: _metrics(subset, field)
                for field in ("prediction", "frozen", "previous")
            }
            tested, previous = metrics["prediction"], metrics["previous"]
            failures = []
            if len(subset) < policy["min_forms_per_route_per_cohort"]:
                failures.append("insufficient_support")
            if subset and tested["severe"] > len(subset) * policy["max_severe_rate"]:
                failures.append("severe_rate")
            comparisons = {
                k: (tested[k], previous[k]) for k in ("severe", "excess_error_total")
            }
            for level in ("4", "5"):
                comparisons["severe_at_true_" + level] = tuple(
                    m["per_level"][level]["severe"] for m in (tested, previous)
                )
            require(
                set(comparisons) == set(policy["non_regression"]), "Unsupported screen"
            )
            failures.extend(k for k, (a, b) in comparisons.items() if a > b)
            reasons.extend(f"{cohort}/{f}" for f in failures)
            table.append(
                dict(route=route, cohort=cohort, metrics=metrics, failures=failures)
            )
        decisions[route] = dict(
            status="hold" if reasons else "eligible_for_further_review", reasons=reasons
        )
    return table, decisions


def simulate_inventory(inventory, labels, paths, anchors, policy, out):
    protected = [r for r in inventory if r["human"]]
    require(
        {r["form"] for r in protected} == set(labels) and len(protected) == 233,
        "Human scope differs",
    )
    require(
        all(r["human"] == (r["form"] in labels) for r in inventory),
        "Incomplete human POS coverage",
    )
    require(
        all(r["current"] == labels[r["form"]] for r in protected), "Human score differs"
    )
    results = {}
    for scenario in policy["scenarios"]:
        candidate, changes = [], Counter()
        forms_changed, levels = set(), defaultdict(set)
        for r in inventory:
            take = not r["human"] and scenario in ("both", r["route"])
            value = r["raw"] if take else r["current"]
            candidate.append(
                dict(
                    word_id=r["word_id"],
                    word=r["word"],
                    type=r["type"],
                    rarity_level=value,
                )
            )
            levels[r["form"]].add(value)
            if value != r["current"]:
                forms_changed.add(r["form"])
                changes[r["current"], value] += 1
        path = out / f"{scenario}.csv"
        _write_csv(path, list(candidate[0]), candidate)
        thresholds = policy["operational_thresholds"]
        quality = run_quality_audit(
            candidate_csv=path,
            reference_csv=paths["after"],
            anchor_l1_file=anchors,
            min_l1_jaccard=thresholds["l1_jaccard"],
            min_anchor_l1_precision=thresholds["anchor_precision"],
            min_anchor_l1_recall=thresholds["anchor_recall"],
            repo=RunCsvRepository(),
        )
        results[scenario] = dict(
            changed_rows=sum(changes.values()),
            changed_forms=len(forms_changed),
            changes_ge2=sum(n for (a, b), n in changes.items() if abs(a - b) >= 2),
            transitions={f"{a}->{b}": n for (a, b), n in sorted(changes.items())},
            mixed_pos_scores=sum(len(v) > 1 for v in levels.values()),
            gate=asdict(quality),
        )
    require(
        results["both"]["changed_rows"]
        == 50724
        == sum(results[r]["changed_rows"] for r in ROUTES.values()),
        "Automatic delta differs from recorded scope",
    )
    return results


def run(base, out):
    policy_path = HERE / "policy.json"
    policy = json.loads(policy_path.read_text())
    paths = {k: base / v["path"] for k, v in policy["inputs"].items()}
    anchors = HERE.parents[1] / "rarity-anchor-l1-ro.txt"
    hashes = {path: policy["inputs"][k]["sha256"] for k, path in paths.items()}
    hashes[anchors] = policy["anchors_sha256"]
    hashes[policy_path] = _sha256(policy_path)

    def verify():
        for path, digest in hashes.items():
            require(_sha256(path) == digest, f"Changed source {path.name}")

    verify()
    out.mkdir(parents=True, exist_ok=False)
    inventory, scores, old_levels = load_inventory(paths)
    rows, labels = get_evaluations(paths, scores, old_levels)
    _write_csv(out / "evaluations.csv", list(rows[0]), rows)
    table, decisions = screen(rows, policy["screen"])
    scenarios = simulate_inventory(inventory, labels, paths, anchors, policy, out)
    report = dict(
        policy=policy["version"],
        policy_sha256=hashes[policy_path],
        upload_authorized=False,
        evaluation=table,
        decisions=decisions,
        scenarios=scenarios,
        protected_human_rows=233,
        route_counts=dict(Counter(r["route"] for r in inventory)),
        automatic_rows=dict(Counter(r["route"] for r in inventory if not r["human"])),
    )
    verify()
    (out / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    manifest = dict(
        inputs={k: _sha256(p) for k, p in paths.items()},
        anchors=_sha256(anchors),
        policy=_sha256(policy_path),
        runner=_sha256(Path(__file__)),
        artifacts={p.name: _sha256(p) for p in sorted(out.iterdir())},
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.base, args.output)
