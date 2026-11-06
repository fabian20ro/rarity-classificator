"""Explicit provisional-risk acceptance, isolated from legacy and human upload flows."""

import json
import re
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .evaluation.dataset import _sha256, _read_csv, _write_csv
from .evaluation.judge_comparison import _indexed, _level
from .evaluation.promotion_audit import prepare_promotion_audit
from .run_csv_repository import RunCsvRepository
from .tools.quality_audit import run_quality_audit

POLICY = "automatic-provisional-acceptance-v1"
VERSION = "automatic-promotion-flow-v1"
ROUTES = ["wordfreq", "fallback"]


def _json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def run_automatic_promotion(
    approval_path: Path,
    package: Path,
    output_dir: Path,
    *,
    action="dry-run",
    store=None,
    confirm_package=None,
    expected_epoch=None,
):
    """Replay accepted CSVs; explicit execution requires a separate store and confirmation."""
    approval_hash = _sha256(approval_path)
    approval = json.loads(approval_path.read_text())
    package_id = _sha256(package / "manifest.json")
    required = {
        "version",
        "approved_on",
        "package_id",
        "candidate_sha256",
        "routes",
        "legacy_gate_role",
        "population_accuracy",
        "human_priority",
    }
    if (
        set(approval) != required
        or approval["version"] != POLICY
        or approval["package_id"] != package_id
        or approval["candidate_sha256"] != _sha256(package / "candidate.csv")
        or approval["routes"] != ROUTES
        or approval["legacy_gate_role"] != "diagnostic"
        or approval["population_accuracy"] != "unknown"
        or approval["human_priority"] is not True
    ):
        raise ValueError("Missing or incompatible automatic policy acceptance")
    date.fromisoformat(approval["approved_on"])
    if action not in {"dry-run", "apply", "rollback"}:
        raise ValueError("Unknown automatic action")
    if action != "dry-run" and (
        store is None or confirm_package != package_id or not expected_epoch
    ):
        raise ValueError(
            "Execution requires store, exact package confirmation and expected epoch"
        )
    manifest = json.loads((package / "manifest.json").read_text())
    protected = {
        str(approval_path.resolve()): approval_hash,
        str((package / "manifest.json").resolve()): package_id,
    }
    for name, digest in manifest["artifacts"].items():
        path = (package / name).resolve()
        if not path.is_relative_to(package.resolve()):
            raise ValueError("Package artifact escapes its directory")
        protected[str(path)] = digest
    _unchanged(protected)
    output_dir.mkdir(parents=True, exist_ok=False)
    audit = prepare_promotion_audit(package / "contract.json", output_dir / "audit")
    replay = output_dir / "audit"
    expected_artifacts = json.loads((replay / "manifest.json").read_text())["artifacts"]
    if set(manifest["artifacts"]) != set(expected_artifacts):
        raise ValueError("Incomplete package artifact manifest")
    for name in manifest["artifacts"]:
        if (
            not (replay / name).is_file()
            or _sha256(replay / name) != manifest["artifacts"][name]
        ):
            raise ValueError("Package differs from original-source replay")
    replay_contract = json.loads((replay / "contract.json").read_text())
    for item in replay_contract["inputs"].values():
        protected[str(Path(item["path"]).resolve())] = item["sha256"]
    changes = {
        route: _read_csv(package / f"{route}-changes.csv", set()) for route in ROUTES
    }
    result = dict(
        status="dry_run",
        applied=False,
        policy_accepted=True,
        package_id=package_id,
        quality=audit["operational_gate"],
        route_changes={route: len(rows) for route, rows in changes.items()},
    )
    _unchanged(protected)
    _json(output_dir / "acceptance.json", approval)
    if action != "dry-run":
        result.update(
            _execute(
                approval_path,
                approval,
                package,
                output_dir,
                action,
                store,
                expected_epoch,
                replay_contract,
                changes,
                protected,
            )
        )
    _json(output_dir / "result.json", result)
    _json(
        output_dir / "manifest.json",
        dict(
            inputs=protected,
            implementation_sha256=_sha256(Path(__file__)),
            artifacts={
                str(p.relative_to(output_dir)): _sha256(p)
                for p in output_dir.rglob("*")
                if p.is_file()
            },
        ),
    )
    return result


LIVE_FIELDS = [
    "word_id",
    "word",
    "type",
    "rarity_level",
    "version",
    "other_columns_sha256",
]


def _snapshot(tx, path):
    _write_csv(path, LIVE_FIELDS, tx.snapshot())
    rows = _indexed(path, set(LIVE_FIELDS))
    for row in rows.values():
        _level(row["rarity_level"])
        if (
            not row["word"]
            or not row["type"]
            or not re.fullmatch(r"[1-9][0-9]*", row["version"])
            or not re.fullmatch(r"[a-f0-9]{64}", row["other_columns_sha256"])
        ):
            raise ValueError("Malformed live identity, revision or content fingerprint")
    return rows


def _execute(
    approval_path,
    approval,
    package,
    out,
    action,
    store,
    expected_epoch,
    contract,
    changes,
    protected,
):
    package_id = approval["package_id"]
    approval_sha = _sha256(approval_path)
    original = _indexed(
        Path(contract["inputs"]["snapshot"]["path"]),
        {"word", "type", "rarity_level", "version"},
    )
    guards = _indexed(package / "human-guards.csv", {"word", "type", "expected_level"})
    forward = [
        dict(
            live_word_id=r["word_id"],
            word=r["word"],
            type=r["type"],
            expected_level=r["expected_level"],
            target_level=r["proposed_level"],
            expected_version=r["snapshot_version"],
            route=route,
        )
        for route in ROUTES
        for r in changes[route]
    ]
    ids = [r["live_word_id"] for r in forward]
    epoch = dict(kind="sequence-v1", epoch=expected_epoch)
    _json(
        out / "attempt.json",
        dict(action=action, package_id=package_id, state="unconfirmed"),
    )
    with store.transaction() as tx:
        if getattr(tx, "version_contract", None) != epoch:
            raise ValueError("Unexpected revision installation epoch")
        receipt = tx.receipt(package_id)
        if receipt is not None:
            _validate_receipt(receipt, package_id, approval_sha, epoch, forward)
            if action == "apply" and receipt["state"] != "applied":
                raise ValueError("Rolled-back package cannot be applied again")
        if receipt is not None and (
            action == "apply" or receipt["state"] == "rolled_back"
        ):
            status = "already_applied" if action == "apply" else "already_rolled_back"
        else:
            if action == "rollback" and receipt is None:
                raise ValueError("Rollback requires committed apply receipt")
            before = _snapshot(tx, out / "live-before.csv")
            if before.keys() != original.keys() or any(
                (r["word"], r["type"]) != (original[i]["word"], original[i]["type"])
                for i, r in before.items()
            ):
                raise ValueError("Inventory identity or membership drift")
            for wid, guard in guards.items():
                if before[wid]["rarity_level"] != guard["expected_level"]:
                    raise ValueError("Protected human score changed")
            if action == "apply":
                if any(
                    (r["rarity_level"], r["version"])
                    != (original[i]["rarity_level"], original[i]["version"])
                    for i, r in before.items()
                ):
                    raise ValueError("Archived score/revision preconditions failed")
                updates = forward
            else:
                updates = [
                    dict(
                        r,
                        expected_level=r["target_level"],
                        target_level=r["expected_level"],
                        expected_version=receipt["post_versions"][r["live_word_id"]],
                    )
                    for r in forward
                ]
                for r in updates:
                    current = before[r["live_word_id"]]
                    if (current["rarity_level"], current["version"]) != (
                        r["expected_level"],
                        r["expected_version"],
                    ):
                        raise ValueError("Rollback score/revision conflict")
            projected = {i: dict(r) for i, r in before.items()}
            for row in updates:
                projected[row["live_word_id"]]["rarity_level"] = row["target_level"]
            _write_csv(
                out / "live-candidate.csv", LIVE_FIELDS, list(projected.values())
            )
            quality = {}
            for name, reference in (
                ("original", Path(contract["inputs"]["snapshot"]["path"])),
                ("current", out / "live-before.csv"),
            ):
                quality[name] = asdict(
                    run_quality_audit(
                        candidate_csv=out / "live-candidate.csv",
                        reference_csv=reference,
                        anchor_l1_file=Path(contract["inputs"]["anchors"]["path"]),
                        min_l1_jaccard=0.7,
                        min_anchor_l1_precision=0.8,
                        min_anchor_l1_recall=0.8,
                        repo=RunCsvRepository(),
                    )
                )
            quality = json.loads(json.dumps(quality))
            _json(out / "live-quality.json", quality)
            _unchanged(protected)
            affected = tx.update(updates)
            if sorted(affected) != sorted(ids):
                raise ValueError("Wrong affected-row identity/count")
            after = _snapshot(tx, out / "live-after.csv")
            for wid in ids:
                if wid not in after or after[wid]["version"] == before[wid]["version"]:
                    raise ValueError("Missing new row revision")
                projected[wid]["version"] = after[wid]["version"]
            if after != projected:
                raise ValueError("Unexpected inventory side effect")
            if action == "apply":
                receipt = dict(
                    version=VERSION,
                    package_id=package_id,
                    approval_sha256=approval_sha,
                    state="applied",
                    apply_txid=tx.txid,
                    changes=forward,
                    row_version_contract=epoch,
                    quality=quality,
                    post_versions={i: after[i]["version"] for i in ids},
                )
            else:
                receipt = dict(
                    receipt,
                    state="rolled_back",
                    rollback_txid=tx.txid,
                    rollback_quality=quality,
                )
            tx.save_receipt(package_id, receipt, replace=action == "rollback")
            if (
                _snapshot(tx, out / "live-final.csv") != after
                or tx.receipt(package_id) != receipt
            ):
                raise ValueError("Receipt write changed inventory or receipt")
            status = "applied" if action == "apply" else "rolled_back"
        if getattr(tx, "version_contract", None) != epoch:
            raise ValueError("Revision installation changed during transaction")
        _unchanged(protected)
    _json(out / "receipt.json", receipt)
    return dict(
        status=status,
        applied=status == "applied",
        rolled_back=status == "rolled_back",
        current_state_verified=status in {"applied", "rolled_back"},
    )


def _validate_receipt(receipt, package_id, approval_sha, epoch, forward):
    ids = {r["live_word_id"] for r in forward}
    if (
        not isinstance(receipt, dict)
        or receipt.get("version") != VERSION
        or receipt.get("package_id") != package_id
        or receipt.get("approval_sha256") != approval_sha
        or receipt.get("state") not in {"applied", "rolled_back"}
        or receipt.get("row_version_contract") != epoch
        or receipt.get("changes") != forward
        or type(receipt.get("apply_txid")) is not int
        or receipt["apply_txid"] <= 0
        or not isinstance(receipt.get("post_versions"), dict)
        or set(receipt["post_versions"]) != ids
        or any(
            not isinstance(v, str) or not re.fullmatch(r"[1-9][0-9]*", v)
            for v in receipt["post_versions"].values()
        )
    ):
        raise ValueError("Receipt does not identify exact accepted automatic package")


def _unchanged(protected):
    for path, digest in protected.items():
        if _sha256(Path(path)) != digest:
            raise ValueError("Frozen automatic input changed")


def main(argv=None):
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="Accepted automatic promotion; offline preview by default."
    )
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--action", choices=("dry-run", "apply", "rollback"), default="dry-run"
    )
    parser.add_argument("--confirm-package")
    parser.add_argument("--expected-epoch")
    parser.add_argument("--dsn-env", default="AUTOMATIC_PROMOTION_DSN")
    args = parser.parse_args(argv)
    store = None
    if args.action != "dry-run":
        from .automatic_promotion_postgres import PostgresAutomaticStore

        if not args.confirm_package or not args.expected_epoch:
            parser.error("Execution requires --confirm-package and --expected-epoch")
        dsn = os.environ.get(args.dsn_env)
        if not dsn:
            parser.error("Dedicated explicit DSN environment variable is required")
        store = PostgresAutomaticStore(dsn)
    result = run_automatic_promotion(
        args.acceptance,
        args.package,
        args.output,
        action=args.action,
        store=store,
        confirm_package=args.confirm_package,
        expected_epoch=args.expected_epoch,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
