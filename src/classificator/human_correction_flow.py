"""Separate, explicitly approved human correction flow. Offline preview by default."""

import json
from datetime import date
from dataclasses import asdict

from .evaluation.dataset import _sha256, _read_csv, _write_csv
from pathlib import Path

from .evaluation.human_acceptance import audit_human_acceptance
from .evaluation.human_corrections import verify_correction_snapshot
from .evaluation.judge_comparison import _indexed, _level
from .run_csv_repository import RunCsvRepository
from .tools.quality_audit import run_quality_audit

VERSION = "human-corrections-flow-v1"


def run_human_corrections(
    approval_path: Path,
    policy_path: Path,
    output_dir: Path,
    *,
    action="dry-run",
    store=None,
    confirm_package=None,
):
    """CSV entrypoint. No store access unless an execution action is explicit."""
    approval_hash = _sha256(approval_path)
    approval = json.loads(approval_path.read_text())
    if (
        not isinstance(approval, dict)
        or set(approval) != {"version", "approved_on", "policy_sha256", "package_id"}
        or approval["version"] != VERSION
        or approval["policy_sha256"] != _sha256(policy_path)
    ):
        raise ValueError("Missing or incompatible human-policy approval")
    date.fromisoformat(approval["approved_on"])
    policy = json.loads(policy_path.read_text())
    package = (policy_path.parent / policy["sources"]["package_manifest"]["path"]).resolve().parent
    package_id = json.loads((package / "policy.json").read_text())["package_id"]
    if approval["package_id"] != package_id:
        raise ValueError("Approval names another package")
    if action not in {"dry-run", "apply", "rollback"}:
        raise ValueError("Unknown human flow action")
    if action != "dry-run" and (confirm_package != package_id or store is None):
        raise ValueError("Execution requires store and explicit package confirmation")
    output_dir.mkdir(parents=True, exist_ok=False)
    report = audit_human_acceptance(policy_path, output_dir / "audit")
    audit_manifest = json.loads((output_dir / "audit/manifest.json").read_text())
    protected = dict(audit_manifest["inputs"])
    protected.update(audit_manifest["implementation"])
    protected[str(approval_path.resolve())] = approval_hash
    _unchanged(protected)
    (output_dir / "approval.json").write_bytes(approval_path.read_bytes())
    if not report["human_policy_satisfied"]:
        raise ValueError("Human acceptance policy failed")
    (output_dir / "changes.csv").write_bytes((output_dir / "audit/changes.csv").read_bytes())
    result = dict(
        status="dry_run",
        applied=False,
        human_policy_satisfied=True,
        legacy_gate=report["legacy_gate"],
    )
    if action == "apply":
        result = _apply(
            package, approval, policy, policy_path, report, output_dir, store, protected
        )
    elif action == "rollback":
        result = _rollback(
            package, approval, policy, policy_path, report, output_dir, store, protected
        )
    (output_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    _json(
        output_dir / "manifest.json",
        dict(
            inputs=protected,
            implementation={
                str(p.resolve()): _sha256(p)
                for p in (Path(__file__), Path(__file__).with_name("human_correction_postgres.py"))
            },
            artifacts={
                str(p.relative_to(output_dir)): _sha256(p)
                for p in output_dir.rglob("*")
                if p.is_file()
            },
        ),
    )
    return result


def _json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def _snapshot(tx, path):
    rows = tx.snapshot()
    _write_csv(path, ["word_id", "word", "type", "rarity_level", "version"], rows)
    indexed = _indexed(path, {"word", "type", "rarity_level", "version"})
    for row in indexed.values():
        _level(row["rarity_level"])
        if (
            not row["word"].strip()
            or not row["type"].strip()
            or not row["version"].isascii()
            or not row["version"].isdigit()
        ):
            raise ValueError("Malformed live row identity/version")
    return indexed


def _apply(package, approval, policy, policy_path, report, out, store, protected):
    package_id = approval["package_id"]
    changes = _read_csv(
        package / "corrections.csv", {"live_word_id", "expected_level", "target_level"}
    )
    _json(out / "attempt.json", dict(action="apply", package_id=package_id, state="unconfirmed"))
    with store.transaction() as tx:
        receipt = tx.receipt(package_id)
        if receipt is not None:
            _validate_receipt(receipt, approval, changes)
            if (
                receipt["policy_sha256"] != approval["policy_sha256"]
                or receipt["state"] != "applied"
            ):
                raise ValueError("Package receipt conflicts with this execution")
            status = "already_applied"
        else:
            before = _snapshot(tx, out / "live-before.csv")
            guards = verify_correction_snapshot(
                package, out / "live-before.csv", out / "live-guards", phase="before"
            )
            if not guards["conditions_satisfied"]:
                raise ValueError("Live human preconditions failed")
            projected = {i: dict(r) for i, r in before.items()}
            for c in changes:
                projected[c["live_word_id"]]["rarity_level"] = c["target_level"]
            _write_csv(
                out / "live-candidate.csv",
                ["word_id", "word", "type", "rarity_level"],
                list(projected.values()),
            )
            quality = _quality(policy, policy_path, out)
            updates = [
                dict(c, expected_version=before[c["live_word_id"]]["version"]) for c in changes
            ]
            _unchanged(protected)
            ids = tx.update(updates)
            if sorted(ids) != sorted(c["live_word_id"] for c in changes):
                raise ValueError("Wrong affected row count or identity")
            after = _snapshot(tx, out / "live-after.csv")
            expected = {i: dict(r) for i, r in projected.items()}
            for i in ids:
                if i not in after or after[i]["version"] == before[i]["version"]:
                    raise ValueError("Missing post-update row version")
                expected[i]["version"] = after[i]["version"]
            if after != expected:
                raise ValueError("Post-state differs from exact human-only delta")
            receipt = dict(
                version=VERSION,
                package_id=package_id,
                policy_sha256=approval["policy_sha256"],
                state="applied",
                apply_txid=tx.txid,
                changed_ids=ids,
                changes=updates,
                quality=quality,
                post_versions={i: after[i]["version"] for i in ids},
            )
            tx.save_receipt(package_id, receipt)
            status = "applied"
        _unchanged(protected)
    _json(out / "receipt.json", receipt)
    return dict(
        status=status,
        applied=status == "applied",
        human_policy_satisfied=True,
        legacy_gate=report["legacy_gate"],
    )


def _quality(policy, policy_path, out):
    quality = {}
    for name, reference in (
        ("original", (policy_path.parent / policy["sources"]["snapshot"]["path"]).resolve()),
        ("current", out / "live-before.csv"),
    ):
        quality[name] = asdict(
            run_quality_audit(
                candidate_csv=out / "live-candidate.csv",
                reference_csv=reference,
                anchor_l1_file=(
                    policy_path.parent / policy["sources"]["anchors"]["path"]
                ).resolve(),
                min_l1_jaccard=0.7,
                min_anchor_l1_precision=0.8,
                min_anchor_l1_recall=0.8,
                repo=RunCsvRepository(),
            )
        )
    quality = json.loads(json.dumps(quality))
    _json(out / "live-quality.json", quality)
    if any(q["l1_jaccard"] < 0.7 for q in quality.values()):
        raise ValueError("Live or original-reference L1 stability failed")
    return quality


def _rollback(package, approval, policy, policy_path, report, out, store, protected):
    package_id = approval["package_id"]
    inverse = _read_csv(
        package / "rollback.csv", {"live_word_id", "expected_level", "restore_level"}
    )
    _json(out / "attempt.json", dict(action="rollback", package_id=package_id, state="unconfirmed"))
    with store.transaction() as tx:
        receipt = tx.receipt(package_id)
        if receipt is None:
            raise ValueError("Rollback requires this package confirmed apply receipt")
        _validate_receipt(receipt, approval, inverse)
        if receipt["state"] == "rolled_back":
            status = "already_rolled_back"
        elif receipt["state"] == "applied":
            if type(tx.txid) is not int or not 0 < tx.txid - receipt["apply_txid"] < 2**31:
                raise ValueError("Transaction age cannot safely identify post-apply row versions")
            before = _snapshot(tx, out / "live-before.csv")
            guards = verify_correction_snapshot(
                package, out / "live-before.csv", out / "live-guards", phase="after"
            )
            if not guards["conditions_satisfied"]:
                raise ValueError("Rollback post-apply preconditions failed")
            updates = [
                dict(
                    r,
                    target_level=r["restore_level"],
                    expected_version=receipt["post_versions"][r["live_word_id"]],
                )
                for r in inverse
            ]
            projected = {i: dict(r) for i, r in before.items()}
            for u in updates:
                projected[u["live_word_id"]]["rarity_level"] = u["target_level"]
            _write_csv(
                out / "live-candidate.csv",
                ["word_id", "word", "type", "rarity_level"],
                list(projected.values()),
            )
            quality = _quality(policy, policy_path, out)
            _unchanged(protected)
            ids = tx.update(updates)
            if sorted(ids) != sorted(r["live_word_id"] for r in inverse):
                raise ValueError("Rollback affected-row mismatch")
            after = _snapshot(tx, out / "live-after.csv")
            for i in ids:
                if i not in after or after[i]["version"] == before[i]["version"]:
                    raise ValueError("Missing rollback row version")
                projected[i]["version"] = after[i]["version"]
            if after != projected:
                raise ValueError("Unexpected rollback side effect")
            receipt = dict(
                receipt, state="rolled_back", rollback_txid=tx.txid, rollback_quality=quality
            )
            tx.save_receipt(package_id, receipt, replace=True)
            status = "rolled_back"
        else:
            raise ValueError("Invalid durable receipt state")
        _unchanged(protected)
    _json(out / "receipt.json", receipt)
    return dict(
        status=status,
        applied=False,
        rolled_back=status == "rolled_back",
        human_policy_satisfied=True,
        legacy_gate=report["legacy_gate"],
    )


def _validate_receipt(receipt, approval, changes):
    ids = sorted(c["live_word_id"] for c in changes)
    if (
        not isinstance(receipt, dict)
        or receipt.get("version") != VERSION
        or receipt.get("package_id") != approval["package_id"]
        or receipt.get("policy_sha256") != approval["policy_sha256"]
        or receipt.get("state") not in {"applied", "rolled_back"}
        or type(receipt.get("apply_txid")) is not int
        or receipt["apply_txid"] <= 0
        or not isinstance(receipt.get("changed_ids"), list)
        or sorted(receipt["changed_ids"]) != ids
        or not isinstance(receipt.get("post_versions"), dict)
        or set(receipt["post_versions"]) != set(ids)
        or any(
            not isinstance(v, str) or not v.isascii() or not v.isdigit()
            for v in receipt["post_versions"].values()
        )
    ):
        raise ValueError("Durable receipt does not identify this exact applied package")
    expected = {}
    for change in changes:
        row = dict(change)
        if "restore_level" in row:
            row["target_level"] = row["expected_level"]
            row["expected_level"] = row.pop("restore_level")
        expected[row["live_word_id"]] = row
    recorded = receipt.get("changes")
    if not isinstance(recorded, list) or len(recorded) != len(expected):
        raise ValueError("Missing exact applied values in receipt")
    actual = {}
    for row in recorded:
        if not isinstance(row, dict) or "expected_version" not in row:
            raise ValueError("Invalid applied-value receipt")
        value = {k: v for k, v in row.items() if k != "expected_version"}
        actual[value.get("live_word_id")] = value
    if actual != expected:
        raise ValueError("Receipt values differ from approved human package")


def _unchanged(protected):
    for name, digest in protected.items():
        if _sha256(Path(name)) != digest:
            raise ValueError("Frozen human flow input changed during execution")


def main(argv=None):
    """Separate CLI; preview never instantiates a database adapter."""
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="Approved human corrections; offline dry-run by default."
    )
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--action", choices=("dry-run", "apply", "rollback"), default="dry-run")
    parser.add_argument(
        "--confirm-package", help="Exact package ID; required separately for apply or rollback"
    )
    parser.add_argument(
        "--dsn-env",
        default="HUMAN_CORRECTIONS_DSN",
        help="Dedicated explicit DSN environment variable; never read by dry-run",
    )
    args = parser.parse_args(argv)
    store = None
    if args.action != "dry-run":
        from .human_correction_postgres import PostgresHumanStore

        if not args.confirm_package:
            parser.error("--confirm-package is required for execution")
        dsn = os.environ.get(args.dsn_env)
        if not dsn:
            parser.error("Explicit DSN environment variable is not set")
        store = PostgresHumanStore(dsn)
    result = run_human_corrections(
        args.approval,
        args.policy,
        args.output,
        action=args.action,
        store=store,
        confirm_package=args.confirm_package,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
