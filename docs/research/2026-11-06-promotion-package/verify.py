"""Independent stdlib reconciliation of the audit package, not a database rehearsal."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import unicodedata


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open() as stream:
        data = list(csv.DictReader(stream))
    result = {r["word_id"]: r for r in data}
    assert len(result) == len(data), "Duplicate IDs"
    return result


def form(word):
    return (
        unicodedata.normalize("NFC", word)
        .translate(str.maketrans("şţŞŢ", "șțȘȚ"))
        .casefold()
    )


def verify(package):
    manifest = json.loads((package / "manifest.json").read_text())
    for name, digest in manifest["artifacts"].items():
        assert sha(package / name) == digest, name
    contract = json.loads((package / "contract.json").read_text())
    paths = {k: Path(v["path"]) for k, v in contract["inputs"].items()}
    for key, path in paths.items():
        assert sha(path) == contract["inputs"][key]["sha256"], key
    before, after = read(paths["snapshot"]), read(package / "candidate.csv")
    baseline = read(paths["baseline"])
    source_groups = defaultdict(list)
    for wid, row in baseline.items():
        source_groups[form(row["word"]), row["type"]].append(wid)
    labels = {}
    for key in ("human_pilot150", "human_review50"):
        for row in read(paths[key]).values():
            label = int(row["working_level"])
            f = form(row["word"])
            assert f not in labels or labels[f] == label
            labels[f] = label
    assert len(labels) == 200
    assert before.keys() == after.keys() and len(after) == 77698
    expected_routes, expected_humans = defaultdict(set), set()
    for wid, row in before.items():
        proposal = after[wid]
        assert (row["word"], row["type"]) == (proposal["word"], proposal["type"])
        f = form(row["word"])
        if f in labels:
            assert (
                int(row["rarity_level"]) == int(proposal["rarity_level"]) == labels[f]
            )
            expected_humans.add(wid)
            continue
        source_ids = source_groups[f, row["type"]]
        values = {
            (baseline[i]["rarity_level"], baseline[i]["route"]) for i in source_ids
        }
        assert len(values) == 1
        score, route = values.pop()
        assert proposal["rarity_level"] == score
        if row["rarity_level"] != score:
            expected_routes[
                {
                    "frequency_thresholds": "wordfreq",
                    "missing_group_median": "fallback",
                }[route]
            ].add(wid)
    guards = read(package / "human-guards.csv")
    assert set(guards) == expected_humans and len(guards) == 233
    for wid, row in guards.items():
        assert row["expected_level"] == before[wid]["rarity_level"]
        assert row["snapshot_version"] == before[wid]["version"]
    simulated = {wid: row["rarity_level"] for wid, row in before.items()}
    deltas, rollbacks = {}, {}
    for route in ("wordfreq", "fallback"):
        delta = read(package / f"{route}-changes.csv")
        inverse = read(package / f"{route}-rollback.csv")
        assert delta.keys() == inverse.keys() == expected_routes[route]
        assert not deltas.keys() & delta.keys()
        for wid, row in delta.items():
            assert row["expected_level"] == simulated[wid]
            assert row["snapshot_version"] == before[wid]["version"]
            assert (row["word"], row["type"]) == (
                before[wid]["word"],
                before[wid]["type"],
            )
            assert row["proposed_level"] == after[wid]["rarity_level"]
            assert row["route"] == route
            assert set(map(str, json.loads(row["source_word_ids_json"]))) == set(
                source_groups[form(row["word"]), row["type"]]
            )
            simulated[wid] = row["proposed_level"]
            back = inverse[wid]
            assert back["expected_level"] == row["proposed_level"]
            assert back["restore_level"] == row["expected_level"]
            assert (back["word"], back["type"], back["route"]) == (
                row["word"],
                row["type"],
                route,
            )
            assert back["version_source"] == "committed_apply_receipt_required"
        deltas.update(delta)
        rollbacks.update(inverse)
    assert simulated == {wid: row["rarity_level"] for wid, row in after.items()}
    assert len(deltas) == 50724 and not deltas.keys() & guards.keys()
    for wid, row in rollbacks.items():
        assert simulated[wid] == row["expected_level"]
        simulated[wid] = row["restore_level"]
    assert simulated == {wid: row["rarity_level"] for wid, row in before.items()}
    report = json.loads((package / "report.json").read_text())
    assert not report["ready_to_apply"] and not report["upload_authorized"]
    assert report["changed_rows"] == len(deltas)
    assert not report["operational_gate"]["passed"]
    for route, ids in expected_routes.items():
        assert report["routes"][route]["changed_rows"] == len(ids)
    return dict(
        verified_rows=len(after),
        human_forms=len(labels),
        protected_rows=len(guards),
        changed_rows=len(deltas),
        routes={k: len(v) for k, v in expected_routes.items()},
        in_memory_apply_matches_candidate=True,
        in_memory_inverse_restores_snapshot=True,
        db_access=False,
        model_calls=False,
        verifier_sha256=sha(Path(__file__)),
        package_manifest_sha256=sha(package / "manifest.json"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.package), indent=2))
