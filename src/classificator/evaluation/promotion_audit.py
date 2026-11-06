"""Pinned CSVs → reversible automatic-score proposal. No executor or approval mode."""

import argparse
from collections import Counter
from dataclasses import asdict
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _lexeme, _read_csv, _sha256, _write_csv
from .judge_comparison import _indexed, _level
from .migration_dry_run import plan_migration
from ..run_csv_repository import RunCsvRepository
from ..tools.quality_audit import run_quality_audit

SCHEMA = "automatic-promotion-audit-v1"
ROUTES = {"frequency_thresholds": "wordfreq", "missing_group_median": "fallback"}
CHANGE_FIELDS = [
    "word_id",
    "word",
    "type",
    "expected_level",
    "proposed_level",
    "snapshot_version",
    "route",
    "source_word_ids_json",
    "source_provenance_ids_json",
]
ROLLBACK_FIELDS = [
    "word_id",
    "word",
    "type",
    "expected_level",
    "restore_level",
    "version_source",
    "route",
]
GUARD_FIELDS = ["word_id", "word", "type", "expected_level", "snapshot_version"]


def prepare_promotion_audit(contract_path: Path, output_dir: Path):
    """Build an audit-only package from a frozen overlay and archived snapshot."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    contract_hash = _sha256(contract_path)
    contract = json.loads(contract_path.read_text())
    if (
        set(contract) != {"schema", "mode", "upload_authorized", "acceptance", "inputs"}
        or contract["schema"] != SCHEMA
        or contract["mode"] != "audit"
        or contract["upload_authorized"] is not False
        or contract["acceptance"] != "pending"
    ):
        raise ValueError("Only a pending audit contract is supported")
    if set(contract["inputs"]) != {
        "baseline",
        "snapshot",
        "candidate",
        "human_pilot150",
        "human_review50",
        "anchors",
    }:
        raise ValueError("Incomplete audit sources")
    paths = {
        k: (contract_path.parent / v["path"]).resolve()
        for k, v in contract["inputs"].items()
    }

    def verify_sources():
        if _sha256(contract_path) != contract_hash:
            raise ValueError("Contract changed during audit")
        for key, path in paths.items():
            if _sha256(path) != contract["inputs"][key]["sha256"]:
                raise ValueError(f"Source hash mismatch: {key}")

    verify_sources()
    source = _indexed(
        paths["baseline"], {"word", "type", "rarity_level", "route", "frequency"}
    )
    snapshot = _indexed(paths["snapshot"], {"word", "type", "rarity_level", "version"})
    if any({"final_level", "median_level"} & row.keys() for row in snapshot.values()):
        raise ValueError(
            "Competing snapshot score columns would change quality audit semantics"
        )
    overlay = _indexed(
        paths["candidate"],
        {"word", "type", "final_level", "decision_source", "provenance_id"},
    )
    if source.keys() != overlay.keys():
        raise ValueError("Baseline and overlay IDs differ")
    labels = {}
    for key in ("human_pilot150", "human_review50"):
        for wid, row in _indexed(paths[key], {"word", "working_level"}).items():
            if wid not in source or _lexeme(row["word"]) != _lexeme(
                source[wid]["word"]
            ):
                raise ValueError("Human source identity mismatch")
            form, level = _lexeme(row["word"]), _level(row["working_level"])
            if form in labels and labels[form] != level:
                raise ValueError("Conflicting human labels")
            labels[form] = level
    for wid, row in overlay.items():
        raw = source[wid]
        if (row["word"], row["type"]) != (raw["word"], raw["type"]):
            raise ValueError("Baseline/overlay spelling or POS mismatch")
        raw_level = _level(raw["rarity_level"])
        frequency = float(raw["frequency"] or 0)
        valid_route = (
            raw["route"] == "frequency_thresholds"
            and math.isfinite(frequency)
            and frequency > 0
            or raw["route"] == "missing_group_median"
            and not raw["frequency"]
            and raw_level == 4
        )
        if not valid_route:
            raise ValueError("Invalid frozen scoring route")
        form = _lexeme(row["word"])
        human = form in labels
        if row["decision_source"] != ("human" if human else "baseline") or _level(
            row["final_level"]
        ) != (labels[form] if human else raw_level):
            raise ValueError(
                "Overlay does not preserve human priority and frozen baseline"
            )
    for row in snapshot.values():
        if not row["version"].isdigit() or int(row["version"]) <= 0:
            raise ValueError("Invalid snapshot revision")
        form = _lexeme(row["word"])
        if form in labels and _level(row["rarity_level"]) != labels[form]:
            raise ValueError("Human snapshot differs from accepted labels")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".promotion-audit-") as temp:
        staged = Path(temp) / "package"
        staged.mkdir()
        migration = plan_migration(
            paths["candidate"], paths["snapshot"], staged / "mapping"
        )
        if not migration["mapping_complete"]:
            raise ValueError("Incomplete exact-form/POS mapping")
        plan = _read_csv(staged / "mapping" / "plan.csv", set())
        candidate, guards = [], []
        changes = {r: [] for r in ROUTES.values()}
        route_rows = Counter()
        for row in plan:
            wid = row["live_word_id"]
            old, new = _level(row["current_level"]), _level(row["proposed_level"])
            identity = dict(word_id=wid, word=row["word"], type=row["type"])
            candidate.append(dict(identity, rarity_level=new))
            if row["decision_source"] == "human":
                guards.append(
                    dict(
                        identity,
                        expected_level=old,
                        snapshot_version=snapshot[wid]["version"],
                    )
                )
                continue
            ids = json.loads(row["source_word_ids_json"])
            routes = {ROUTES[source[str(i)]["route"]] for i in ids}
            if len(routes) != 1:
                raise ValueError("Ambiguous scoring route")
            route = routes.pop()
            route_rows[route] += 1
            if new != old:
                changes[route].append(
                    dict(
                        identity,
                        expected_level=old,
                        proposed_level=new,
                        snapshot_version=snapshot[wid]["version"],
                        route=route,
                        source_word_ids_json=row["source_word_ids_json"],
                        source_provenance_ids_json=row["source_provenance_ids_json"],
                    )
                )
        _write_csv(
            staged / "candidate.csv",
            ["word_id", "word", "type", "rarity_level"],
            candidate,
        )
        _write_csv(staged / "human-guards.csv", GUARD_FIELDS, guards)
        for route, delta in changes.items():
            _write_csv(staged / f"{route}-changes.csv", CHANGE_FIELDS, delta)
            rollback = [
                dict(
                    word_id=r["word_id"],
                    word=r["word"],
                    type=r["type"],
                    expected_level=r["proposed_level"],
                    restore_level=r["expected_level"],
                    version_source="committed_apply_receipt_required",
                    route=route,
                )
                for r in delta
            ]
            _write_csv(staged / f"{route}-rollback.csv", ROLLBACK_FIELDS, rollback)
        quality = run_quality_audit(
            candidate_csv=staged / "candidate.csv",
            reference_csv=paths["snapshot"],
            anchor_l1_file=paths["anchors"],
            min_l1_jaccard=0.7,
            min_anchor_l1_precision=0.8,
            min_anchor_l1_recall=0.8,
            repo=RunCsvRepository(),
        )
        report = dict(
            schema=SCHEMA,
            mode="audit",
            acceptance="pending",
            upload_authorized=False,
            ready_to_apply=False,
            inventory_rows=len(candidate),
            inventory_forms=len({_lexeme(r["word"]) for r in candidate}),
            protected_human_rows=len(guards),
            changed_rows=sum(map(len, changes.values())),
            routes={
                route: dict(
                    automatic_rows=route_rows[route],
                    changed_rows=len(delta),
                    changed_forms=len({_lexeme(r["word"]) for r in delta}),
                    changes_ge2=sum(
                        abs(r["proposed_level"] - r["expected_level"]) >= 2
                        for r in delta
                    ),
                    transitions=dict(
                        sorted(
                            Counter(
                                f"{r['expected_level']}->{r['proposed_level']}"
                                for r in delta
                            ).items()
                        )
                    ),
                )
                for route, delta in changes.items()
            },
            operational_gate=asdict(quality),
            blockers=[
                "automatic_policy_not_approved",
                "live_state_not_verified",
                "automatic_executor_not_implemented",
            ],
            rollback="Inverse proposal only; committed apply receipt and post-write revisions required",
        )
        if not quality.passed:
            report["blockers"].append("legacy_quality_gate_failed")
        (staged / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        replay_contract = dict(
            contract,
            inputs={
                k: dict(v, path=str(paths[k])) for k, v in contract["inputs"].items()
            },
        )
        (staged / "contract.json").write_text(
            json.dumps(replay_contract, indent=2) + "\n"
        )
        manifest = dict(
            schema=SCHEMA,
            contract_sha256=_sha256(contract_path),
            inputs=contract["inputs"],
            implementation_sha256=_sha256(Path(__file__)),
            artifacts={
                str(p.relative_to(staged)): _sha256(p)
                for p in sorted(staged.rglob("*"))
                if p.is_file()
            },
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        verify_sources()
        staged.rename(output_dir)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare_promotion_audit(args.contract, args.output)
