"""Versioned human-correction acceptance policy, offline audit only; never a gate bypass."""

from dataclasses import asdict
from datetime import date
import re
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _lexeme, _read_csv, _sha256, _write_csv
from .human_corrections import prepare_human_corrections, verify_correction_snapshot
from .form_evidence_audit import _check_export
from .judge_comparison import _indexed, _level
from ..run_csv_repository import RunCsvRepository
from ..tools.quality_audit import run_quality_audit

VERSION = "human-corrections-acceptance-audit-v1"


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError("Invalid acceptance policy fields")


def _policy_paths(policy, policy_path):
    _keys(policy, "version mode as_of sources scope")
    if policy["version"] != VERSION or policy["mode"] != "audit":
        raise ValueError("Unsupported acceptance policy version/mode")
    if not isinstance(policy["as_of"], str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", policy["as_of"]
    ):
        raise ValueError("Invalid audit date")
    date.fromisoformat(policy["as_of"])
    _keys(policy["scope"], "correction_rows guard_rows human_references")
    if any(type(n) is not int or n <= 0 for n in policy["scope"].values()):
        raise ValueError("Scope counts must be positive integers")
    _keys(
        policy["sources"],
        "package_manifest plan_manifest human_export_manifest snapshot candidate anchors",
    )
    paths = {}
    for name, source in policy["sources"].items():
        _keys(source, "path sha256")
        if not isinstance(source["path"], str) or not source["path"].strip():
            raise ValueError("Missing source path")
        path = (policy_path.parent / source["path"]).resolve()
        if (
            not isinstance(source["sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", source["sha256"])
            or _sha256(path) != source["sha256"]
        ):
            raise ValueError("Pinned source hash mismatch")
        if name.endswith("_manifest") and path.name != "manifest.json":
            raise ValueError("Manifest must name the consumed manifest.json")
        paths[name] = path
    plan = json.loads(paths["plan_manifest"].read_text())
    if plan["inputs"].get(str(paths["snapshot"])) != policy["sources"]["snapshot"]["sha256"]:
        raise ValueError("Snapshot must be the original pinned migration baseline")
    return paths


def audit_human_acceptance(policy_path: Path, output_dir: Path):
    """Audit a pinned package and full shadow candidate; no live reads or execution."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    policy_bytes = policy_path.read_bytes()
    policy = json.loads(policy_bytes)
    paths = _policy_paths(policy, policy_path)
    protected = {str(paths[k]): s["sha256"] for k, s in policy["sources"].items()}
    protected[str(policy_path.resolve())] = _sha256(policy_path)
    package = paths["package_manifest"].parent
    receipt = _check_export(
        package,
        {
            "corrections.csv",
            "rollback.csv",
            "preconditions.csv",
            "references.csv",
            "summary.json",
            "policy.json",
        },
    )
    with TemporaryDirectory() as tmp:
        replay = Path(tmp) / "package"
        prepare_human_corrections(
            paths["plan_manifest"].parent, paths["human_export_manifest"].parent, replay
        )
        if json.loads((replay / "manifest.json").read_text()) != receipt:
            raise ValueError("Package does not replay from original human sources and pinned plan")
    protected.update(receipt["inputs"])
    protected.update({str(package / name): digest for name, digest in receipt["artifacts"].items()})
    summary = json.loads((package / "summary.json").read_text())
    scope = {k: summary[k] for k in ("correction_rows", "guard_rows", "human_references")}
    source = _indexed(paths["snapshot"], {"word", "type", "rarity_level"})
    candidate = _indexed(paths["candidate"], {"word", "type", "rarity_level"})
    for rows in (source, candidate):
        for row in rows.values():
            if set(row) != {"word_id", "word", "type", "rarity_level"}:
                raise ValueError("Snapshot/candidate require exactly one score column and identity")
            _level(row["rarity_level"])
            if not row["word"].strip() or not row["type"].strip():
                raise ValueError("Missing spelling or POS")
    corrections = _read_csv(
        package / "corrections.csv", {"live_word_id", "expected_level", "target_level"}
    )
    expected = {i: dict(r) for i, r in source.items()}
    for c in corrections:
        expected[c["live_word_id"]]["rarity_level"] = c["target_level"]
    differences = [
        dict(
            word_id=i,
            expected_json=json.dumps(expected.get(i), ensure_ascii=False),
            observed_json=json.dumps(candidate.get(i), ensure_ascii=False),
        )
        for i in sorted(expected.keys() | candidate.keys(), key=int)
        if expected.get(i) != candidate.get(i)
    ]
    restored = {i: dict(r) for i, r in candidate.items()}
    inverse_matches = True
    for inverse in _read_csv(
        package / "rollback.csv", {"live_word_id", "expected_level", "restore_level"}
    ):
        row = restored.get(inverse["live_word_id"])
        if row is None or row["rarity_level"] != inverse["expected_level"]:
            inverse_matches = False
        elif (row["word"], row["type"]) != (inverse["word"], inverse["type"]):
            inverse_matches = False
        else:
            row["rarity_level"] = inverse["restore_level"]
    inverse_restores = inverse_matches and restored == source
    quality = asdict(
        run_quality_audit(
            candidate_csv=paths["candidate"],
            reference_csv=paths["snapshot"],
            anchor_l1_file=paths["anchors"],
            min_l1_jaccard=0.7,
            min_anchor_l1_precision=0.8,
            min_anchor_l1_recall=0.8,
            repo=RunCsvRepository(),
        )
    )
    anchors = {
        _lexeme(s.strip())
        for s in paths["anchors"].read_text().splitlines()
        if s.strip() and not s.strip().startswith("#")
    }
    conflicts = [
        dict(word=r["word"], human_level=r["level"], reference_key=r["reference_key"])
        for r in _read_csv(package / "references.csv", {"word", "level", "reference_key"})
        if _lexeme(r["word"]) in anchors and r["level"] != "1"
    ]
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".human-acceptance-") as tmp:
        staged = Path(tmp) / "output"
        staged.mkdir()
        before = verify_correction_snapshot(
            package, paths["snapshot"], staged / "before", phase="before"
        )
        criteria = [
            dict(criterion="original_human_package_and_inverse", satisfied=True),
            dict(criterion="declared_scope", satisfied=scope == policy["scope"]),
            dict(criterion="all_reviewed_preconditions", satisfied=before["conditions_satisfied"]),
            dict(criterion="exact_full_candidate", satisfied=candidate == expected),
            dict(criterion="inverse_restores_snapshot", satisfied=inverse_restores),
            dict(criterion="full_inventory_l1_stability", satisfied=quality["l1_jaccard"] >= 0.7),
        ]
        report = dict(
            version=VERSION,
            mode="audit",
            as_of=policy["as_of"],
            scope=scope,
            human_policy_satisfied=all(r["satisfied"] for r in criteria),
            legacy_gate=quality,
            promotion_blocked=True,
            upload_authorized=False,
            rollback_authorized=False,
            freshness_verified=False,
            apply_receipt_verified=False,
            population_accuracy=None,
            seed_semantic_precision=None,
            unchanged_inventory_rows=sum(candidate.get(i) == r for i, r in source.items()),
            seed_human_conflicts=len(conflicts),
            inverse_restores_snapshot=inverse_restores,
        )
        _write_csv(
            staged / "candidate-issues.csv",
            ["word_id", "expected_json", "observed_json"],
            differences,
        )
        _write_csv(staged / "criteria.csv", ["criterion", "satisfied"], criteria)
        _write_csv(
            staged / "changes.csv",
            list(corrections[0])
            if corrections
            else ["live_word_id", "expected_level", "target_level"],
            corrections,
        )
        _write_csv(
            staged / "seed-conflicts.csv", ["word", "human_level", "reference_key"], conflicts
        )
        (staged / "policy.json").write_bytes(policy_bytes)
        (staged / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        for p, digest in protected.items():
            if _sha256(Path(p)) != digest:
                raise ValueError("Audit input hash mismatch")
        manifest = dict(
            inputs=protected,
            implementation={
                **receipt["implementation"],
                **{
                    str(p.resolve()): _sha256(p)
                    for p in (
                        Path(__file__),
                        Path(__file__).parents[1] / "tools/quality_audit.py",
                        Path(__file__).parents[1] / "run_csv_repository.py",
                    )
                },
            },
            artifacts={
                str(p.relative_to(staged)): _sha256(p) for p in staged.rglob("*") if p.is_file()
            },
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return report
