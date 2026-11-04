"""Offline audit only: immutable sources → diagnostics, never replacement scores."""

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import csv
import hashlib
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unicodedata
from unittest.mock import patch

from classificator.run_csv_repository import RunCsvRepository
from classificator.tools.quality_audit import run_quality_audit


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows
    return rows


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(word):
    return unicodedata.normalize("NFC", word).translate(str.maketrans("şţŞŢ", "șțȘȚ")).casefold()


def write(path, rows):
    assert rows
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def indexed(path):
    rows = read(path)
    result = {r["word_id"]: r for r in rows}
    assert len(result) == len(rows)
    return result


def ratio(a, b):
    return len(a & b) / len(a | b)


def generate(base, code, out):
    export = base / "conservative-export-2026-11-01/export"
    paths = dict(
        inventory=base.parent / "rarity/step1_words.csv",
        snapshot=base.parent / "rarity/reference/current_db_levels.csv",
        baseline=base / "offline-wordfreq-2026-10-24/export/scores.csv",
        model=base / "offline-wordfreq-2026-10-24/export/model.json",
        candidate=export / "candidate.csv",
        references=export / "references.csv",
        anchors=code / "docs/rarity-anchor-l1-ro.txt",
        previous_quality=export.parent / "quality.json",
        legacy_initial=base.parent / "rarity/runs/initial_20260215_034523.csv",
        legacy_rebalanced=base.parent / "rarity/runs/rb_l4split25k_20260215_134927.csv",
        legacy_remapped=base.parent / "rarity/runs/rb_l4split25k_20260215_134927.idshift77698.csv",
    )
    inventory, snapshot, baseline, candidate = (
        indexed(paths[n]) for n in ("inventory", "snapshot", "baseline", "candidate")
    )
    assert len(inventory) == 77698
    groups = defaultdict(list)
    for wid, row in inventory.items():
        groups[exact(row["word"])].append(wid)
    for source in (snapshot, baseline, candidate):
        assert source.keys() == inventory.keys()
        assert all(
            (source[i]["word"], source[i]["type"]) == (r["word"], r["type"])
            for i, r in inventory.items()
        )
    for source, column in ((baseline, "rarity_level"), (candidate, "final_level")):
        assert all(len({source[i][column] for i in ids}) == 1 for ids in groups.values())
    anchor_lines = [
        x.strip().lower()
        for x in paths["anchors"].read_text().splitlines()
        if x.strip() and not x.strip().startswith("#")
    ]
    anchors = set(anchor_lines)
    assert anchors <= groups.keys()
    old_quality = json.loads(paths["previous_quality"].read_text())
    model = json.loads(paths["model"].read_text())
    refs = read(paths["references"])
    human = {exact(r["word"]): r for r in refs}
    assert len(human) == len(refs) == 200
    for word, ref in human.items():
        assert all(candidate[i]["final_level"] == ref["level"] for i in groups[word])
    out.mkdir()
    reports, membership = {}, []
    snapshot_l1 = {i for i, r in snapshot.items() if r["rarity_level"] == "1"}
    snapshot_forms = {exact(snapshot[i]["word"]) for i in snapshot_l1}
    for name, source, column in (
        ("baseline", baseline, "rarity_level"),
        ("candidate", candidate, "final_level"),
        ("snapshot", snapshot, "rarity_level"),
    ):
        ids = {i for i, r in source.items() if r[column] == "1"}
        words = {r["word"].lower() for i, r in source.items() if i in ids}
        forms = {exact(w) for w in words}
        inter = ids & snapshot_l1
        qa = asdict(
            run_quality_audit(
                candidate_csv=paths[name],
                reference_csv=paths["snapshot"],
                anchor_l1_file=paths["anchors"],
                min_l1_jaccard=0.7,
                min_anchor_l1_precision=0.8,
                min_anchor_l1_recall=0.8,
                repo=RunCsvRepository(),
            )
        )
        # Independent arithmetic, including self-comparison of the old reference.
        assert qa["l1_jaccard"] == ratio(ids, snapshot_l1)
        assert qa["anchor_precision"] == len(words & anchors) / len(words)
        assert qa["anchor_recall"] == len(words & anchors) / len(anchors)
        if name in old_quality:
            previous = old_quality[name]
            assert all(qa[k] == previous[k] for k in qa if k != "distribution")
            assert {str(k): v for k, v in qa["distribution"].items()} == previous["distribution"]
        reports[name] = dict(
            quality=qa,
            l1_ids=len(ids),
            l1_forms=len(forms),
            shared_ids=len(inter),
            candidate_only_ids=len(ids - snapshot_l1),
            reference_only_ids=len(snapshot_l1 - ids),
            form_jaccard=ratio(forms, snapshot_forms),
            normalization_changed_l1_forms=len(words.symmetric_difference(forms)),
            maximum_jaccard_at_fixed_counts=min(len(ids), len(snapshot_l1))
            / max(len(ids), len(snapshot_l1)),
            maximum_anchor_precision=min(len(anchors), len(words)) / len(words),
            anchor_hits=len(words & anchors),
            anchor_hits_needed_for_precision=math.ceil(0.8 * len(words)),
            extra_matching_anchors_needed=math.ceil(0.8 * len(words)) - len(words & anchors),
            maximum_precision_with_400_anchors=min(400 / len(words), 1),
            reference_l1_to_levels=dict(
                sorted(Counter(source[i][column] for i in snapshot_l1).items())
            ),
            l1_to_reference_levels=dict(
                sorted(Counter(snapshot[i]["rarity_level"] for i in ids).items())
            ),
        )
        if name != "snapshot":
            for i in sorted(ids | snapshot_l1, key=int):
                membership.append(
                    dict(
                        method=name,
                        word_id=i,
                        word=inventory[i]["word"],
                        type=inventory[i]["type"],
                        candidate_level=source[i][column],
                        reference_level=snapshot[i]["rarity_level"],
                        relation="shared"
                        if i in inter
                        else "candidate_only"
                        if i in ids
                        else "reference_only",
                        frequency=baseline[i]["frequency"],
                        route=baseline[i]["route"],
                        human_level=human.get(exact(inventory[i]["word"]), {}).get("level", ""),
                    )
                )
    write(out / "l1-membership.csv", membership)
    anchor_rows = []
    for word in sorted(anchors):
        ids = groups[word]
        i = ids[0]
        b, c = baseline[i]["rarity_level"], candidate[i]["final_level"]
        reason = (
            "L1"
            if b == "1"
            else "missing_frequency"
            if not baseline[i]["frequency"]
            else "observed_below_L1_threshold"
        )
        anchor_rows.append(
            dict(
                word=word,
                inventory_ids_json=json.dumps(ids),
                types_json=json.dumps(sorted({inventory[i]["type"] for i in ids})),
                baseline_level=b,
                candidate_level=c,
                baseline_reason=reason,
                frequency=baseline[i]["frequency"],
                route=baseline[i]["route"],
                snapshot_levels_json=json.dumps(sorted({snapshot[i]["rarity_level"] for i in ids})),
                human_level=human.get(word, {}).get("level", ""),
            )
        )
    write(out / "anchors.csv", anchor_rows)
    pos_conflicts = [
        dict(
            word=word,
            inventory_ids_json=json.dumps(ids),
            types_json=json.dumps([inventory[i]["type"] for i in ids]),
            snapshot_levels_json=json.dumps([snapshot[i]["rarity_level"] for i in ids]),
        )
        for word, ids in sorted(groups.items())
        if len({snapshot[i]["rarity_level"] for i in ids}) > 1
    ]
    write(out / "snapshot-form-conflicts.csv", pos_conflicts)
    human_rows = []
    for r in refs:
        word = exact(r["word"])
        levels = [int(snapshot[i]["rarity_level"]) for i in groups[word]]
        human_rows.append(
            dict(
                source=r["source_id"],
                word_id=r["word_id"],
                word=r["word"],
                human_level=r["level"],
                baseline_level=baseline[r["word_id"]]["rarity_level"],
                snapshot_level=snapshot[r["word_id"]]["rarity_level"],
                snapshot_most_familiar_level=min(levels),
                candidate_level=candidate[r["word_id"]]["final_level"],
            )
        )
    write(out / "existing-human-comparison.csv", human_rows)
    human_metrics = {}
    for sid in sorted({r["source"] for r in human_rows}):
        rows = [r for r in human_rows if r["source"] == sid]
        human_metrics[sid] = {}
        for col in (
            "baseline_level",
            "snapshot_level",
            "snapshot_most_familiar_level",
            "candidate_level",
        ):
            human_metrics[sid][col] = {}
            for subset, rs in [
                ("all", rows),
                *[
                    ("human" + str(n), [r for r in rows if r["human_level"] == str(n)])
                    for n in (1, 4, 5)
                ],
            ]:
                gaps = [abs(int(r[col]) - int(r["human_level"])) for r in rs]
                human_metrics[sid][col][subset] = dict(
                    n=len(rs),
                    exact=gaps.count(0),
                    severe=sum(g >= 2 for g in gaps),
                    excess=sum(max(0, g - 1) for g in gaps),
                )
    legacy = {}
    for name, col, shift in (
        ("legacy_initial", "rarity_level", 0),
        ("legacy_rebalanced", "final_level", 0),
        ("legacy_remapped", "final_level", 77698),
    ):
        source = indexed(paths[name])
        mapped = {str(int(i) - shift): r for i, r in source.items()}
        assert mapped.keys() == inventory.keys()
        assert all(
            (r["word"], r["type"]) == (inventory[i]["word"], inventory[i]["type"])
            for i, r in mapped.items()
        )
        levels = {i: r[col] for i, r in mapped.items()}
        if name == "legacy_rebalanced":
            rebalance_levels = levels
        if shift:
            assert levels == rebalance_levels
        legacy[name] = dict(
            rows=len(source),
            id_shift=shift,
            identity_checked=True,
            levels=dict(sorted(Counter(levels.values()).items())),
            different_from_snapshot=sum(
                levels[i] != snapshot[i]["rarity_level"] for i in inventory
            ),
            l1_jaccard_after_id_alignment=ratio(
                {i for i in levels if levels[i] == "1"}, snapshot_l1
            ),
            saved_upload_status=dict(Counter(r.get("upload_status", "") for r in source.values())),
            note="Historical saved receipts only; no live DB verification or new ID remapping authorized",
        )
    report = dict(
        inventory_rows=len(inventory),
        exact_forms=len(groups),
        identity_mismatches=0,
        groups_with_multiple_ids=sum(len(ids) > 1 for ids in groups.values()),
        snapshot_inconsistent_forms=len(pos_conflicts),
        anchor_lines=len(anchor_lines),
        unique_anchors=len(anchors),
        duplicate_anchors={k: n for k, n in Counter(anchor_lines).items() if n > 1},
        missing_inventory_anchors=0,
        anchor_baseline_levels=dict(
            sorted(Counter(r["baseline_level"] for r in anchor_rows).items())
        ),
        anchor_candidate_levels=dict(
            sorted(Counter(r["candidate_level"] for r in anchor_rows).items())
        ),
        anchor_baseline_reasons=dict(Counter(r["baseline_reason"] for r in anchor_rows)),
        l1_frequency_threshold=model["threshold_fit"]["thresholds"][0],
        minimum_l1_ids_for_jaccard_07=math.ceil(len(snapshot_l1) * 0.7),
        methods=reports,
        human_comparison=human_metrics,
        legacy=legacy,
        caveats=[
            "Existing references are reused development data, review50 risk-selected",
            "Candidate agreement is by construction, not accuracy",
            "Historical snapshot is not independent ground truth or current DB state",
            "Unlisted seed words are unlabelled, not negative anchors",
            "No changed gates, scores, thresholds, anchor list, models or DB",
        ],
        model_calls=0,
        database_writes=0,
    )
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    manifest = dict(
        inputs={str(p): sha(p) for p in paths.values()},
        implementation={
            str(p): sha(p)
            for p in (
                Path(__file__).resolve(),
                code / "src/classificator/tools/quality_audit.py",
                code / "src/classificator/run_csv_repository.py",
            )
        },
        artifacts={p.name: sha(p) for p in sorted(out.iterdir())},
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return report


def main(base, code, out):
    assert not out.exists()
    previous = base / "conservative-export-2026-11-01"
    protected = json.loads((previous / "protected-inputs.json").read_text())
    protected.update({str(p): sha(p) for p in previous.rglob("*") if p.is_file()})
    for name, digest in protected.items():
        assert sha(Path(name)) == digest, name
    with (
        patch("subprocess.run", side_effect=AssertionError("Processes forbidden")),
        patch("subprocess.Popen", side_effect=AssertionError("Processes forbidden")),
        patch("requests.adapters.HTTPAdapter.send", side_effect=AssertionError("HTTP forbidden")),
        patch("socket.create_connection", side_effect=AssertionError("Network forbidden")),
        patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
    ):
        report = generate(base, code, out)
        with TemporaryDirectory(dir=out.parent) as tmp:
            replay = Path(tmp) / "replay"
            assert generate(base, code, replay) == report
            assert {p.name for p in out.iterdir()} == {p.name for p in replay.iterdir()}
            for p in replay.iterdir():
                assert p.read_bytes() == (out / p.name).read_bytes(), p.name
    for name, digest in protected.items():
        assert sha(Path(name)) == digest, name
    manifest = json.loads((out / "manifest.json").read_text())
    for name, digest in manifest["inputs"].items():
        assert sha(Path(name)) == digest, name
    result = dict(
        protected_files_unchanged=len(protected),
        replay_byte_identical_artifacts=6,
        independent_quality_arithmetic="PASS",
        previous_quality_reproduced="PASS",
        identity_and_human_scores="PASS",
        legacy_id_shift_verified=77698,
        model_calls=0,
        database_writes=0,
    )
    (out / "protected-inputs.json").write_text(json.dumps(protected, indent=2) + "\n")
    (out / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.base.resolve(), Path(__file__).resolve().parents[3], args.output.resolve())
