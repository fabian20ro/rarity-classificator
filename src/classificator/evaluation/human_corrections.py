"""Prepare human-only correction/rollback CSVs. No execution or upload authority."""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _lexeme, _read_csv, _sha256, _write_csv
from .form_evidence_audit import _check_export
from .judge_comparison import _indexed, _level
from .migration_dry_run import plan_migration

POLICY = dict(
    version="human-corrections-package-v1",
    mode="prepared_only",
    upload_authorized=False,
    rollback_authorized=False,
    requires_fresh_snapshot_before_apply=True,
    requires_existing_upload_gate=True,
    execution_contract="Recheck complete reviewed-form membership, literal ID/word/POS and all guarded levels under one transaction; all corrections or none; exact affected-row count and durable apply receipt required.",
    rollback_requires_confirmed_apply_receipt=True,
    rollback_contract="Only IDs confirmed changed by this package may be restored; verify post-apply identity and levels, refuse conflicts. Expected values alone cannot detect ABA or prove this package ran. No rollback before confirmed apply.",
)
BASE_FIELDS = [
    "live_word_id",
    "word",
    "type",
    "exact_form",
    "reference_keys_json",
    "source_word_ids_json",
]
GUARD_FIELDS = [*BASE_FIELDS, "before_level", "after_level", "will_change"]
CORRECTION_FIELDS = [*BASE_FIELDS, "expected_level", "target_level"]
ROLLBACK_FIELDS = [*BASE_FIELDS, "expected_level", "restore_level"]


def _validated_inputs(plan_dir, human_export_dir):
    plan_receipt = _check_export(plan_dir, {"plan.csv", "summary.json"})
    human_receipt = _check_export(
        human_export_dir, {"references.csv", "candidate.csv", "sources.csv"}
    )
    candidate = human_export_dir / "candidate.csv"
    if (
        plan_receipt["inputs"].get(str(candidate.resolve())) != _sha256(candidate)
        or len(plan_receipt["inputs"]) != 2
    ):
        raise ValueError("Plan does not reference this frozen candidate")
    snapshot = next(
        Path(p) for p in plan_receipt["inputs"] if Path(p).resolve() != candidate.resolve()
    )
    with TemporaryDirectory() as temp:
        replay = Path(temp) / "plan"
        summary = plan_migration(candidate, snapshot, replay)
        if not summary["mapping_complete"]:
            raise ValueError("Incomplete identity mapping")
        replay_receipt = json.loads((replay / "manifest.json").read_text())
        if replay_receipt["artifacts"] != plan_receipt["artifacts"]:
            raise ValueError("Plan does not replay from its pinned inputs")
    references = _read_csv(
        human_export_dir / "references.csv",
        {"reference_key", "source_id", "word_id", "word", "level", "reference_kind"},
    )
    actual = {
        r["reference_key"]: (
            r["source_id"],
            r["word_id"],
            r["word"],
            _level(r["level"]),
            r["reference_kind"],
        )
        for r in references
    }
    if len(actual) != len(references):
        raise ValueError("Duplicate reference identity")
    original = {}
    for source in _read_csv(
        human_export_dir / "sources.csv", {"source_id", "kind", "path", "sha256"}
    ):
        if source["kind"] != "human":
            continue
        path = Path(source["path"])
        if (
            human_receipt["inputs"].get(str(path.resolve())) != source["sha256"]
            or _sha256(path) != source["sha256"]
        ):
            raise ValueError("Unpinned human source")
        for wid, row in _indexed(path, {"word", "working_level", "reference_kind"}).items():
            key = source["source_id"] + ":" + wid
            if key in original:
                raise ValueError("Duplicate human source")
            original[key] = (
                source["source_id"],
                wid,
                row["word"],
                _level(row["working_level"]),
                row["reference_kind"],
            )
    if not original or actual != original:
        raise ValueError("References do not match original human responses")
    protected = {}
    for directory, receipt in ((plan_dir, plan_receipt), (human_export_dir, human_receipt)):
        protected.update(receipt["inputs"])
        protected[str((directory / "manifest.json").resolve())] = _sha256(
            directory / "manifest.json"
        )
        protected.update(
            {
                str((directory / name).resolve()): digest
                for name, digest in receipt["artifacts"].items()
            }
        )
    return references, protected


def prepare_human_corrections(plan_dir: Path, human_export_dir: Path, output_dir: Path):
    """Prepare only explicit human differences and guard every reviewed form/POS row."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    references, protected = _validated_inputs(plan_dir, human_export_dir)
    by_form = defaultdict(list)
    for r in references:
        by_form[_lexeme(r["word"])].append(r)
    plan = _read_csv(
        plan_dir / "plan.csv",
        {
            "live_word_id",
            "word",
            "type",
            "current_level",
            "proposed_level",
            "decision_source",
            "source_word_ids_json",
        },
    )
    for refs in by_form.values():
        if len({_level(r["level"]) for r in refs}) != 1:
            raise ValueError("Contradictory human form levels")
    guards, corrections, rollback = [], [], []
    for p in plan:
        form = _lexeme(p["word"])
        if (p["decision_source"] == "human") != (form in by_form):
            raise ValueError("Human source flag/reference coverage mismatch")
        if p["decision_source"] != "human":
            continue
        if _level(p["proposed_level"]) != _level(by_form[form][0]["level"]):
            raise ValueError("Proposed correction differs from original human score")
        base = dict(
            live_word_id=p["live_word_id"],
            word=p["word"],
            type=p["type"],
            exact_form=form,
            reference_keys_json=json.dumps(sorted(r["reference_key"] for r in by_form[form])),
            source_word_ids_json=p["source_word_ids_json"],
        )
        before, after = int(p["current_level"]), int(p["proposed_level"])
        guards.append(
            dict(base, before_level=before, after_level=after, will_change=before != after)
        )
        if before != after:
            corrections.append(dict(base, expected_level=before, target_level=after))
            rollback.append(dict(base, expected_level=after, restore_level=before))
    if {r["exact_form"] for r in guards} != set(by_form):
        raise ValueError("Human forms missing from migration plan")
    summary = dict(
        human_references=len(references),
        reviewed_forms=len(by_form),
        guard_rows=len(guards),
        correction_rows=len(corrections),
        rollback_rows=len(rollback),
        changed_forms=len({r["exact_form"] for r in corrections}),
        unchanged_human_rows=len(guards) - len(corrections),
        large_difference_rows=sum(
            abs(r["expected_level"] - r["target_level"]) >= 2 for r in corrections
        ),
        transitions=dict(
            sorted(
                Counter(f"{r['expected_level']}->{r['target_level']}" for r in corrections).items()
            )
        ),
        upload_authorized=False,
        rollback_authorized=False,
    )
    inputs = [plan_dir / "manifest.json", human_export_dir / "manifest.json"]
    package_id = hashlib.sha256(
        (POLICY["version"] + "".join(_sha256(p) for p in inputs)).encode()
    ).hexdigest()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".human-corrections-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        for name, fields, rows in [
            ("preconditions.csv", GUARD_FIELDS, guards),
            ("corrections.csv", CORRECTION_FIELDS, corrections),
            ("rollback.csv", ROLLBACK_FIELDS, rollback),
        ]:
            _write_csv(staged / name, fields, rows)
        (staged / "references.csv").write_bytes((human_export_dir / "references.csv").read_bytes())
        (staged / "policy.json").write_text(
            json.dumps(dict(POLICY, package_id=package_id), indent=2) + "\n"
        )
        (staged / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        for name, digest in protected.items():
            if _sha256(Path(name)) != digest:
                raise ValueError("Source changed during preparation")
        manifest = dict(
            inputs=protected,
            implementation={
                str(p.resolve()): _sha256(p)
                for p in (
                    Path(__file__),
                    Path(__file__).with_name("migration_dry_run.py"),
                    Path(__file__).with_name("dataset.py"),
                    Path(__file__).with_name("judge_comparison.py"),
                    Path(__file__).with_name("form_evidence_audit.py"),
                )
            },
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return summary


def verify_correction_snapshot(
    package_dir: Path, snapshot_csv: Path, output_dir: Path, *, phase: str
):
    """Check before/after state offline. A match is neither freshness nor execution proof."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    if phase not in {"before", "after"}:
        raise ValueError("Only before/after state checks are supported; no rollback authorization")
    _check_export(
        package_dir, {"preconditions.csv", "corrections.csv", "rollback.csv", "policy.json"}
    )
    policy = json.loads((package_dir / "policy.json").read_text())
    if policy != dict(POLICY, package_id=policy.get("package_id")):
        raise ValueError("Unsupported package policy")
    guards = _read_csv(package_dir / "preconditions.csv", set(GUARD_FIELDS))
    expected = {r["live_word_id"]: r for r in guards}
    if len(expected) != len(guards):
        raise ValueError("Duplicate guard identity")
    snapshot = _indexed(snapshot_csv, {"word", "type", "rarity_level"})
    inputs = {
        str((package_dir / "manifest.json").resolve()): _sha256(package_dir / "manifest.json"),
        str(snapshot_csv.resolve()): _sha256(snapshot_csv),
    }
    by_form = defaultdict(set)
    observed = defaultdict(set)
    for r in guards:
        by_form[r["exact_form"]].add(r["live_word_id"])
    for wid, row in snapshot.items():
        _level(row["rarity_level"])
        if _lexeme(row["word"]) in by_form:
            observed[_lexeme(row["word"])].add(wid)
    issues = []
    for wid, guard in expected.items():
        row = snapshot.get(wid)
        if row is None:
            issues.append(
                dict(code="MISSING_ROW", live_word_id=wid, expected=guard["word"], observed="")
            )
            continue
        if (row["word"], row["type"]) != (guard["word"], guard["type"]):
            issues.append(
                dict(
                    code="IDENTITY_CHANGED",
                    live_word_id=wid,
                    expected=json.dumps([guard["word"], guard["type"]]),
                    observed=json.dumps([row["word"], row["type"]]),
                )
            )
        level = guard[phase + "_level"]
        if _level(row["rarity_level"]) != _level(level):
            issues.append(
                dict(
                    code="LEVEL_CHANGED",
                    live_word_id=wid,
                    expected=level,
                    observed=row["rarity_level"],
                )
            )
    for form, ids in sorted(by_form.items()):
        if ids != observed[form]:
            issues.append(
                dict(
                    code="MEMBERSHIP_CHANGED",
                    live_word_id="",
                    expected=json.dumps(dict(form=form, ids=sorted(ids, key=int))),
                    observed=json.dumps(sorted(observed[form], key=int)),
                )
            )
    report = dict(
        package_id=policy["package_id"],
        phase=phase,
        conditions_satisfied=not issues,
        guard_rows=len(guards),
        reviewed_forms=len(by_form),
        issue_count=len(issues),
        freshness_verified=False,
        apply_receipt_verified=False,
        upload_authorized=False,
        rollback_authorized=False,
        scope="Only reviewed forms and all their IDs/POS; unrelated rows are outside this check. Recheck transactionally before any separately authorized execution.",
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".correction-check-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        _write_csv(staged / "issues.csv", ["code", "live_word_id", "expected", "observed"], issues)
        (staged / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        for p, h in inputs.items():
            if _sha256(Path(p)) != h:
                raise ValueError("Check input changed")
        manifest = dict(
            inputs=inputs,
            implementation={str(Path(__file__).resolve()): _sha256(Path(__file__))},
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return report
