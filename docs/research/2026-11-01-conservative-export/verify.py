"""Reconcile the export against original rows and replay with external I/O forbidden."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unicodedata
from unittest.mock import patch
from collections import defaultdict

from classificator.evaluation.conservative_export import export_conservative_inventory


def read(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def form(word):
    return unicodedata.normalize("NFC", word).translate(str.maketrans("şţŞŢ", "șțȘȚ")).casefold()


def verify(out):
    protocol = json.loads((out / "protocol.json").read_text())
    exported = out / "export"
    manifest = json.loads((exported / "manifest.json").read_text())
    protected = json.loads((out / "protected-inputs.json").read_text())
    for name, digest in {
        **protected,
        **protocol["inputs"],
        **protocol["implementation"],
        **manifest["inputs"],
        **manifest["implementation"],
    }.items():
        assert sha(Path(name)) == digest, name
    for name, digest in manifest["artifacts"].items():
        assert sha(exported / name) == digest, name
    inventory = read(Path(protocol["inventory"]))
    base = read(Path(protocol["baseline"]) / "scores.csv")
    candidate = read(exported / "candidate.csv")
    inv = {r["word_id"]: r for r in inventory}
    old = {r["word_id"]: r for r in base}
    new = {r["word_id"]: r for r in candidate}
    assert (
        len(inv) == len(old) == len(new) == len(candidate) == 77698
        and inv.keys() == old.keys() == new.keys()
    )
    groups = defaultdict(list)
    for r in inventory:
        groups[form(r["word"])].append(r["word_id"])
    refs = {}
    byform = defaultdict(list)
    for source in read(out / "reference-sources.csv"):
        assert sha(Path(source["path"])) == source["sha256"]
        for row in read(Path(source["path"])):
            key = source["source_id"] + ":" + row["word_id"]
            assert key not in refs
            refs[key] = (source["source_id"], row)
            byform[form(row["word"])].append(key)
    assert len(refs) == len(byform) == 200
    for wid, r in new.items():
        assert (
            (r["word"], r["type"])
            == (inv[wid]["word"], inv[wid]["type"])
            == (old[wid]["word"], old[wid]["type"])
        )
        key = form(r["word"])
        levels = {refs[k][1]["working_level"] for k in byform.get(key, [])}
        assert len(levels) <= 1
        expected = next(iter(levels)) if levels else old[wid]["rarity_level"]
        assert r["final_level"] == expected and r["baseline_level"] == old[wid]["rarity_level"]
        assert r["status"] == ("human_reviewed" if levels else "provisional_baseline")
        assert r["decision_source"] == ("human" if levels else "baseline")
        assert r["exact_form"] == key and r["provenance_id"] == "form:" + str(
            min(map(int, groups[key]))
        )
    actual_refs = {r["reference_key"]: r for r in read(exported / "references.csv")}
    assert actual_refs.keys() == refs.keys()
    for key, (sid, r) in refs.items():
        a = actual_refs[key]
        assert (a["source_id"], a["word_id"], a["word"], a["level"], a["reference_kind"]) == (
            sid,
            r["word_id"],
            r["word"],
            r["working_level"],
            r["reference_kind"],
        )
    raw_observations = {}
    for source in read(out / "observation-sources.csv"):
        assert sha(Path(source["path"])) == source["sha256"]
        for r in read(Path(source["path"])):
            key = source["source_id"] + ":" + r["word_id"]
            assert key not in raw_observations
            raw_observations[key] = (source["source_id"], r)
    observed = {r["observation_key"]: r for r in read(exported / "observations.csv")}
    assert observed.keys() == raw_observations.keys()
    modelkeys = defaultdict(list)
    expected_conflicts = set()
    for key, (sid, r) in raw_observations.items():
        a = observed[key]
        c = new[r["word_id"]]
        assert (
            a["source_id"],
            a["word_id"],
            a["word"],
            a["status"],
            a["level"],
            a["candidate_level"],
        ) == (sid, r["word_id"], r["word"], r["status"], r["rarity_level"], c["final_level"])
        modelkeys[form(r["word"])].append(key)
        if r["status"] == "scored" and r["rarity_level"] != c["final_level"]:
            expected_conflicts.add(
                ("model_vs_candidate", c["provenance_id"], key, r["rarity_level"], c["final_level"])
            )
    prov = read(exported / "provenance.csv")
    assert len(prov) == len(groups) == 75147
    for row in prov:
        key = row["exact_form"]
        ids = groups[key]
        wid = str(min(map(int, ids)))
        c = new[wid]
        assert row["provenance_id"] == c["provenance_id"]
        assert json.loads(row["inventory_ids_json"]) == sorted(map(int, ids))
        assert json.loads(row["inventory_types_json"]) == sorted({inv[i]["type"] for i in ids})
        assert json.loads(row["human_reference_keys_json"]) == sorted(byform.get(key, []))
        assert json.loads(row["observation_keys_json"]) == sorted(modelkeys[key])
        assert row["baseline_level"] == old[wid]["rarity_level"]
        assert (
            row["baseline_frequency"] == old[wid]["frequency"]
            and row["baseline_route"] == old[wid]["route"]
        )
        assert row["human_level"] == (c["final_level"] if byform.get(key, []) else "")
        if byform.get(key, []) and old[wid]["rarity_level"] != c["final_level"]:
            expected_conflicts.add(
                (
                    "baseline_vs_human",
                    c["provenance_id"],
                    "baseline:" + wid,
                    old[wid]["rarity_level"],
                    c["final_level"],
                )
            )
    conflicts = read(exported / "conflicts.csv")
    actual_conflicts = {
        (
            r["kind"],
            r["provenance_id"],
            r["observation_key"],
            r["observed_level"],
            r["candidate_level"],
        )
        for r in conflicts
    }
    assert actual_conflicts == expected_conflicts and len(conflicts) == len(actual_conflicts)
    for r in conflicts:
        delta = int(r["observed_level"]) - int(r["candidate_level"])
        assert int(r["signed_difference"]) == delta and int(r["absolute_gap"]) == abs(delta)
        assert r["severe"] == str(abs(delta) >= 2)
    snapshot = read(Path(protocol["quality"]["reference_snapshot"]))
    snap = {r["word_id"]: r for r in snapshot}
    assert len(snap) == len(snapshot) == len(inv) and snap.keys() == inv.keys()
    assert all(snap[i]["word"] == inv[i]["word"] and snap[i]["type"] == inv[i]["type"] for i in inv)
    anchors = {
        x.strip().lower()
        for x in Path(protocol["quality"]["anchors"]).read_text().splitlines()
        if x.strip() and not x.strip().startswith("#")
    }
    qa = json.loads((out / "quality.json").read_text())
    for name, rows, column in [
        ("candidate", candidate, "final_level"),
        ("baseline", base, "rarity_level"),
    ]:
        ids = {r["word_id"] for r in rows if r[column] == "1"}
        reference_ids = {r["word_id"] for r in snapshot if r["rarity_level"] == "1"}
        words = {r["word"].lower() for r in rows if r[column] == "1"}
        assert qa[name]["l1_jaccard"] == len(ids & reference_ids) / len(ids | reference_ids)
        assert qa[name]["anchor_precision"] == len(words & anchors) / len(words)
        assert qa[name]["anchor_recall"] == len(words & anchors) / len(anchors)
    with (
        patch("subprocess.run", side_effect=AssertionError("LLM/process forbidden")),
        patch("subprocess.Popen", side_effect=AssertionError("LLM/process forbidden")),
        patch(
            "requests.adapters.HTTPAdapter.send", side_effect=AssertionError("Network forbidden")
        ),
        patch("socket.create_connection", side_effect=AssertionError("Network forbidden")),
        patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
        TemporaryDirectory(dir=out) as temp,
    ):
        replay = Path(temp) / "export"
        export_conservative_inventory(
            Path(protocol["inventory"]),
            Path(protocol["baseline"]),
            out / "reference-sources.csv",
            out / "observation-sources.csv",
            replay,
        )
        assert {p.name for p in replay.iterdir()} == {p.name for p in exported.iterdir()}
        for path in replay.iterdir():
            assert path.read_bytes() == (exported / path.name).read_bytes(), path.name
    for name, digest in protected.items():
        assert sha(Path(name)) == digest, name
    result = dict(
        inventory_ids_checked=len(inv),
        exact_forms_checked=len(groups),
        human_forms_checked=len(byform),
        human_rows_checked=sum(r["status"] == "human_reviewed" for r in candidate),
        baseline_rows_unchanged=sum(r["status"] == "provisional_baseline" for r in candidate),
        observations_reconciled=len(observed),
        conflicts_reconciled=len(conflicts),
        source_hashes="PASS",
        independent_scores_and_provenance="PASS",
        snapshot_identity="PASS",
        quality_arithmetic="PASS",
        anchor_seed_words=len(anchors),
        replay="PASS",
        byte_identical_artifacts=len(list(exported.iterdir())),
        protected_files_unchanged=len(protected),
        model_calls=0,
        database_writes=0,
    )
    (out / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    verify(parser.parse_args().output.resolve())
