"""Immutable human exact-form overrides of a frozen inventory baseline; no scorer I/O."""

from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from .dataset import _lexeme, _read_csv, _sha256, _write_csv
from .form_evidence_audit import _check_export
from .judge_comparison import _indexed, _level
from .wordfreq_baseline import _model

POLICY = dict(
    version="conservative-exact-form-export-v1",
    priority="Consistent explicit human working_level for the exact form; frozen baseline otherwise. Models are diagnostics only.",
    normalization="NFC, cedilla-to-comma, casefold; no accent removal, lemma or inflection transfer",
    conflicts="All nonzero baseline-human and model-candidate gaps, once per form/observation; severe means absolute gap>=2, not independently proven error.",
    status="human_reviewed marks a user reference, not population validation; all remaining scores are provisional_baseline",
    mode="offline_candidate_no_upload",
)
BASE_FIELDS = {"word_id", "word", "type", "rarity_level", "frequency", "route", "model_version"}
CONFLICT_FIELDS = [
    "provenance_id",
    "word",
    "kind",
    "observation_key",
    "observed_level",
    "candidate_level",
    "signed_difference",
    "absolute_gap",
    "severe",
]
REFERENCE_FIELDS = ["reference_key", "source_id", "word_id", "word", "level", "reference_kind"]
OBSERVATION_FIELDS = [
    "observation_key",
    "source_id",
    "word_id",
    "word",
    "status",
    "level",
    "candidate_level",
]


def _sources(catalog, kind, inventory):
    """Read source files themselves; a caller cannot substitute projected scores."""
    sources, entries = [], []
    seen = set()
    for source in _read_csv(catalog, {"source_id", "path", "sha256"}):
        sid = source["source_id"]
        if (
            set(source) != {"source_id", "path", "sha256"}
            or not re.fullmatch(r"[a-zA-Z0-9_-]+", sid)
            or sid in seen
            or sid == "baseline"
        ):
            raise ValueError("Invalid or duplicate source identity/schema")
        seen.add(sid)
        path = Path(source["path"])
        if not path.is_absolute():
            path = catalog.parent / path
        path = path.resolve()
        if not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]) or _sha256(path) != source["sha256"]:
            raise ValueError("Source hash mismatch")
        required = (
            {"word", "working_level", "reference_kind"}
            if kind == "human"
            else {"word", "status", "rarity_level"}
        )
        rows = _indexed(path, required)
        for wid, row in rows.items():
            if wid not in inventory or _lexeme(row["word"]) != _lexeme(inventory[wid]["word"]):
                raise ValueError("Source/inventory exact identity mismatch")
            if kind == "human":
                level = _level(row["working_level"])
                if not row["reference_kind"].strip():
                    raise ValueError("Missing human reference provenance")
                entry = dict(
                    reference_key=f"{sid}:{wid}",
                    source_id=sid,
                    word_id=wid,
                    word=row["word"],
                    level=level,
                    reference_kind=row["reference_kind"],
                )
            else:
                if row["status"] == "scored":
                    level = _level(row["rarity_level"])
                elif row["status"] == "failed" and row["rarity_level"] == "":
                    level = ""
                else:
                    raise ValueError("Invalid model status/level")
                entry = dict(
                    observation_key=f"{sid}:{wid}",
                    source_id=sid,
                    word_id=wid,
                    word=row["word"],
                    status=row["status"],
                    level=level,
                )
            entries.append(entry)
        sources.append(dict(source_id=sid, kind=kind, path=str(path), sha256=source["sha256"]))
    return sources, entries


def export_conservative_inventory(
    inventory_csv, baseline_dir, reference_sources_csv, observation_sources_csv, output_dir
):
    """Publish complete candidate, per-form provenance, references and separate conflicts."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    inventory = _indexed(inventory_csv, {"word", "type"})
    baseline_manifest = _check_export(baseline_dir, {"scores.csv", "model.json"})
    if not baseline_manifest.get("implementation"):
        raise ValueError("Missing baseline implementation provenance")
    model = _model(baseline_dir / "model.json")
    baseline = _indexed(baseline_dir / "scores.csv", BASE_FIELDS - {"word_id"})
    if set(inventory) != set(baseline):
        raise ValueError("Baseline must cover exact inventory")
    forms = defaultdict(list)
    for wid, row in inventory.items():
        b = baseline[wid]
        if (
            set(b) != BASE_FIELDS
            or any(row[k] != b[k] for k in ("word", "type"))
            or not row["word"].strip()
            or not row["type"].strip()
            or b["model_version"] != model["model_version"]
        ):
            raise ValueError("Baseline inventory/schema/version mismatch")
        _level(b["rarity_level"])
        forms[_lexeme(row["word"])].append(wid)
    for ids in forms.values():
        if (
            len(
                {tuple(baseline[i][k] for k in ("rarity_level", "frequency", "route")) for i in ids}
            )
            != 1
        ):
            raise ValueError("Baseline differs across exact-form POS rows")
    human_sources, references = _sources(reference_sources_csv, "human", inventory)
    model_sources, observations = _sources(observation_sources_csv, "model", inventory)
    if {s["source_id"] for s in human_sources} & {s["source_id"] for s in model_sources}:
        raise ValueError("Human/model source identities must differ")
    humans, models = defaultdict(list), defaultdict(list)
    for row in references:
        humans[_lexeme(row["word"])].append(row)
    for form, refs in humans.items():
        if len({r["level"] for r in refs}) != 1:
            raise ValueError(f"Conflicting human levels for exact form: {form}")
    for row in observations:
        models[_lexeme(row["word"])].append(row)
    candidate, provenance, conflicts = [], [], []

    def conflict(pid, word, kind, key, observed, final):
        if observed == final:
            return
        gap = observed - final
        conflicts.append(
            dict(
                provenance_id=pid,
                word=word,
                kind=kind,
                observation_key=key,
                observed_level=observed,
                candidate_level=final,
                signed_difference=gap,
                absolute_gap=abs(gap),
                severe=abs(gap) >= 2,
            )
        )

    for form, ids in sorted(forms.items(), key=lambda pair: min(map(int, pair[1]))):
        ids.sort(key=int)
        representative = ids[0]
        pid = "form:" + representative
        refs = humans.get(form, [])
        b = baseline[representative]
        base = _level(b["rarity_level"])
        final = refs[0]["level"] if refs else base
        for wid in ids:
            r = inventory[wid]
            candidate.append(
                dict(
                    word_id=wid,
                    word=r["word"],
                    type=r["type"],
                    final_level=final,
                    baseline_level=_level(baseline[wid]["rarity_level"]),
                    decision_source="human" if refs else "baseline",
                    status="human_reviewed" if refs else "provisional_baseline",
                    exact_form=form,
                    provenance_id=pid,
                )
            )
        provenance.append(
            dict(
                provenance_id=pid,
                exact_form=form,
                inventory_ids_json=json.dumps(list(map(int, ids))),
                inventory_types_json=json.dumps(sorted({inventory[i]["type"] for i in ids})),
                baseline_level=base,
                baseline_frequency=b["frequency"],
                baseline_route=b["route"],
                baseline_model_version=b["model_version"],
                human_level=final if refs else "",
                human_reference_keys_json=json.dumps(sorted(r["reference_key"] for r in refs)),
                observation_keys_json=json.dumps(
                    sorted(r["observation_key"] for r in models.get(form, []))
                ),
            )
        )
        if refs:
            conflict(pid, form, "baseline_vs_human", "baseline:" + representative, base, final)
        for obs in models.get(form, []):
            obs["candidate_level"] = final
            if obs["status"] == "scored":
                conflict(
                    pid, form, "model_vs_candidate", obs["observation_key"], obs["level"], final
                )
    candidate.sort(key=lambda r: int(r["word_id"]))
    references.sort(key=lambda r: r["reference_key"])
    observations.sort(key=lambda r: r["observation_key"])
    summary = dict(
        inventory_rows=len(candidate),
        exact_forms=len(forms),
        human_forms=len(humans),
        human_rows=sum(r["decision_source"] == "human" for r in candidate),
        baseline_rows=sum(r["decision_source"] == "baseline" for r in candidate),
        changed_rows=sum(r["final_level"] != r["baseline_level"] for r in candidate),
        changed_forms=sum(
            bool(humans.get(form))
            and humans[form][0]["level"] != _level(baseline[ids[0]]["rarity_level"])
            for form, ids in forms.items()
        ),
        human_references=len(references),
        model_observations=len(observations),
        model_failed=sum(r["status"] == "failed" for r in observations),
        conflicts=dict(Counter(r["kind"] for r in conflicts)),
        severe_conflicts=dict(Counter(r["kind"] for r in conflicts if r["severe"])),
        conflicted_forms=len({r["provenance_id"] for r in conflicts}),
        levels=dict(sorted(Counter(str(r["final_level"]) for r in candidate).items())),
        mode=POLICY["mode"],
        model_requests=0,
        database_writes=0,
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".conservative-export-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        for name, fields, rows in [
            ("candidate.csv", list(candidate[0]), candidate),
            ("provenance.csv", list(provenance[0]), provenance),
            ("references.csv", REFERENCE_FIELDS, references),
            ("observations.csv", OBSERVATION_FIELDS, observations),
            ("conflicts.csv", CONFLICT_FIELDS, conflicts),
        ]:
            _write_csv(staged / name, fields, rows)
        sources = [
            dict(
                source_id="baseline",
                kind="baseline",
                path=str((baseline_dir / "manifest.json").resolve()),
                sha256=_sha256(baseline_dir / "manifest.json"),
            ),
            *human_sources,
            *model_sources,
        ]
        _write_csv(staged / "sources.csv", ["source_id", "kind", "path", "sha256"], sources)
        (staged / "baseline-model.json").write_bytes((baseline_dir / "model.json").read_bytes())
        (staged / "policy.json").write_text(json.dumps(POLICY, indent=2) + "\n")
        (staged / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        inputs = [
            inventory_csv,
            reference_sources_csv,
            observation_sources_csv,
            baseline_dir / "manifest.json",
            baseline_dir / "scores.csv",
            baseline_dir / "model.json",
            *(Path(s["path"]) for s in human_sources + model_sources),
        ]
        receipt = dict(
            policy=POLICY["version"],
            inputs={str(p.resolve()): _sha256(p) for p in inputs},
            implementation={
                str(p.resolve()): _sha256(p)
                for p in (
                    Path(__file__),
                    Path(__file__).with_name("dataset.py"),
                    Path(__file__).with_name("form_evidence_audit.py"),
                    Path(__file__).with_name("wordfreq_baseline.py"),
                )
            },
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
        )
        (staged / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
        staged.rename(output_dir)
    return summary
