"""Offline migration diagnostics by exact form/POS, never executable updates."""

from collections import Counter, defaultdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _lexeme, _sha256, _write_csv
from .judge_comparison import _indexed, _level

POLICY = "exact-form-pos-migration-dry-run-v1"
PLAN_FIELDS = [
    "live_word_id",
    "word",
    "type",
    "current_level",
    "proposed_level",
    "change",
    "absolute_gap",
    "decision_source",
    "mapping_kind",
    "source_word_ids_json",
    "source_provenance_ids_json",
]
MAPPING_FIELDS = ["word", "type", "source_word_ids_json", "live_word_ids_json", "mapping_kind"]
ISSUE_FIELDS = ["word", "type", "reason", "source_word_ids_json", "live_word_ids_json"]


def _groups(rows):
    groups = defaultdict(list)
    for i, r in rows.items():
        groups[(_lexeme(r["word"]), r["type"])].append(i)
    return groups


def plan_migration(candidate_csv: Path, snapshot_csv: Path, output_dir: Path):
    """Preserve source scores; map score-equivalent groups without guessing row identities."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    before = {str(p.resolve()): _sha256(p) for p in (candidate_csv, snapshot_csv)}
    source = _indexed(
        candidate_csv, {"word", "type", "final_level", "decision_source", "provenance_id"}
    )
    live = _indexed(snapshot_csv, {"word", "type", "rarity_level"})
    forms = defaultdict(set)
    for rows, column in ((source, "final_level"), (live, "rarity_level")):
        for row in rows.values():
            if not row["word"].strip() or not row["type"].strip():
                raise ValueError("Missing word/POS")
            _level(row[column])
    for row in source.values():
        if row["decision_source"] not in {"human", "baseline"} or not row["provenance_id"].strip():
            raise ValueError("Invalid source provenance")
        forms[_lexeme(row["word"])].add((row["final_level"], row["decision_source"]))
    if any(len(values) != 1 for values in forms.values()):
        raise ValueError("Inconsistent exact-form score/source across POS")
    old_groups, live_groups = _groups(source), _groups(live)
    plan, mapping, issues = [], [], []
    for key in sorted(old_groups.keys() | live_groups.keys()):
        old_ids, live_ids = (
            sorted(old_groups.get(key, []), key=int),
            sorted(live_groups.get(key, []), key=int),
        )
        reason = (
            "live_only"
            if not old_ids
            else "source_only"
            if not live_ids
            else "cardinality_mismatch"
            if len(old_ids) != len(live_ids)
            else ""
        )
        if reason:
            issues.append(
                dict(
                    word=key[0],
                    type=key[1],
                    reason=reason,
                    source_word_ids_json=json.dumps(list(map(int, old_ids))),
                    live_word_ids_json=json.dumps(list(map(int, live_ids))),
                )
            )
            continue
        row = source[old_ids[0]]
        level = _level(row["final_level"])
        kind = "unique_exact_form_pos" if len(old_ids) == 1 else "equivalent_duplicate_group"
        source_ids = json.dumps(list(map(int, old_ids)))
        mapping.append(
            dict(
                word=key[0],
                type=key[1],
                source_word_ids_json=source_ids,
                live_word_ids_json=json.dumps(list(map(int, live_ids))),
                mapping_kind=kind,
            )
        )
        for wid in live_ids:
            current = _level(live[wid]["rarity_level"])
            plan.append(
                dict(
                    live_word_id=wid,
                    word=live[wid]["word"],
                    type=live[wid]["type"],
                    current_level=current,
                    proposed_level=level,
                    change=level - current,
                    absolute_gap=abs(level - current),
                    decision_source=row["decision_source"],
                    mapping_kind=kind,
                    source_word_ids_json=source_ids,
                    source_provenance_ids_json=json.dumps(
                        sorted({source[i]["provenance_id"] for i in old_ids})
                    ),
                )
            )
    plan.sort(key=lambda r: int(r["live_word_id"]))
    large = [r for r in plan if r["absolute_gap"] >= 2]
    summary = dict(
        policy=POLICY,
        mode="dry_run",
        upload_authorized=False,
        source_rows=len(source),
        live_rows=len(live),
        mapped_rows=len(plan),
        changed_rows=sum(r["change"] != 0 for r in plan),
        unchanged_rows=sum(r["change"] == 0 for r in plan),
        large_difference_rows=len(large),
        mapping_kinds=dict(Counter(r["mapping_kind"] for r in plan)),
        identity_issues=len(issues),
        unmapped_source_rows=len(source) - len(plan),
        unmapped_live_rows=len(live) - len(plan),
        mapping_complete=not issues,
        current_levels=dict(sorted(Counter(str(r["current_level"]) for r in plan).items())),
        proposed_levels=dict(sorted(Counter(str(r["proposed_level"]) for r in plan).items())),
        transitions=dict(
            sorted(Counter(f"{r['current_level']}->{r['proposed_level']}" for r in plan).items())
        ),
        human_rows=sum(r["decision_source"] == "human" for r in plan),
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".migration-dry-run-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        for name, fields, rows in [
            ("plan.csv", PLAN_FIELDS, plan),
            ("level-conflicts.csv", PLAN_FIELDS, large),
            ("mapping.csv", MAPPING_FIELDS, mapping),
            ("identity-issues.csv", ISSUE_FIELDS, issues),
        ]:
            _write_csv(staged / name, fields, rows)
        (staged / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        for p, h in before.items():
            if _sha256(Path(p)) != h:
                raise ValueError("Source changed during planning")
        manifest = dict(
            inputs=before,
            implementation={
                str(p.resolve()): _sha256(p)
                for p in (
                    Path(__file__),
                    Path(__file__).with_name("dataset.py"),
                    Path(__file__).with_name("judge_comparison.py"),
                )
            },
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return summary
