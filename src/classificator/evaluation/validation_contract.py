"""Typed reference semantics and diagnostics. This module cannot authorize upload."""

from collections import defaultdict
from datetime import date
import math
import re
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _lexeme, _sha256, _write_csv
from .judge_comparison import _indexed, _level, _metrics

SCHEMA = "rarity-validation-audit-v1"


def _ratio(n, d):
    return n / d if d else None


def _keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected.split()):
        raise ValueError("Invalid contract fields")


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Invalid reference date")
    return date.fromisoformat(value)


def _validate_contract(contract, path):
    _keys(contract, "schema mode as_of inventory legacy_thresholds references candidates")
    if contract["schema"] != SCHEMA or contract["mode"] != "audit":
        raise ValueError("Unsupported contract version or non-audit mode")
    as_of = _date(contract["as_of"])
    _keys(contract["inventory"], "path sha256")
    _keys(contract["legacy_thresholds"], "l1_jaccard anchor_precision anchor_recall")
    for value in contract["legacy_thresholds"].values():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 1
        ):
            raise ValueError("Invalid legacy threshold")
    for name in ("references", "candidates"):
        if not isinstance(contract[name], list) or not contract[name]:
            raise ValueError("Missing references/candidates")
    seen = set()
    roles = set()
    for source in contract["references"] + contract["candidates"]:
        if not isinstance(source, dict):
            raise ValueError("Invalid source")
        role = source.get("role")
        expected = {
            "historical_snapshot": "inventory_id",
            "positive_seed": "exact_form",
            "human_labels": "exact_form",
            "candidate": "exact_form",
        }
        if (
            not isinstance(role, str)
            or role not in expected
            or source.get("unit") != expected[role]
        ):
            raise ValueError("Incompatible source role/unit")
        extra = "" if role == "positive_seed" else " level_column"
        extra += (
            " selection" if role == "human_labels" else " label_use" if role == "candidate" else ""
        )
        _keys(source, "id role unit path sha256 universe_sha256 recorded_on provenance" + extra)
        sid = source["id"]
        if not isinstance(sid, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", sid) or sid in seen:
            raise ValueError("Invalid or duplicate source id")
        seen.add(sid)
        roles.add(role)
        if source["universe_sha256"] != contract["inventory"]["sha256"]:
            raise ValueError("Different inventory universe")
        if not isinstance(source["provenance"], str) or not source["provenance"].strip():
            raise ValueError("Missing source provenance")
        if source["recorded_on"] is not None and _date(source["recorded_on"]) > as_of:
            raise ValueError("Reference date is after audit date")
        if role != "positive_seed" and (
            not isinstance(source["level_column"], str) or not source["level_column"].strip()
        ):
            raise ValueError("Missing score column")
        if role == "human_labels" and source["selection"] not in (
            "development",
            "risk_selected",
            "unspecified",
        ):
            raise ValueError("Unsupported label selection")
    if roles != {"historical_snapshot", "positive_seed", "human_labels", "candidate"}:
        raise ValueError("Contract requires all three reference roles and a candidate")
    human_ids = {s["id"] for s in contract["references"] if s["role"] == "human_labels"}
    if any(s["role"] == "candidate" for s in contract["references"]):
        raise ValueError("Candidate cannot be a reference")
    for spec in contract["candidates"]:
        if (
            spec["role"] != "candidate"
            or not isinstance(spec["label_use"], dict)
            or set(spec["label_use"]) != human_ids
        ):
            raise ValueError("Each candidate must declare every human source's use")
        if any(v not in ("none", "fit", "override", "unknown") for v in spec["label_use"].values()):
            raise ValueError("Unknown label use")
    for source in [contract["inventory"], *contract["references"], *contract["candidates"]]:
        if not isinstance(source["path"], str) or not source["path"]:
            raise ValueError("Missing source path")
        if (
            not isinstance(source["sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", source["sha256"])
            or _sha256(path(source)) != source["sha256"]
        ):
            raise ValueError("Source hash mismatch")


def _align(rows, inventory, *, complete):
    if complete and set(rows) != set(inventory):
        raise ValueError("Incomplete or shifted inventory IDs")
    for wid, row in rows.items():
        if wid not in inventory or _lexeme(row["word"]) != _lexeme(inventory[wid]["word"]):
            raise ValueError("Exact-form ID/spelling mismatch")
        if complete and row.get("type") != inventory[wid]["type"]:
            raise ValueError("Inventory POS mismatch")


def audit_validation_contract(contract_path: Path, output_dir: Path):
    """Read pinned sources; write separate drift, seed and human diagnostics only."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    contract_bytes = contract_path.read_bytes()
    contract_hash = _sha256(contract_path)
    contract = json.loads(contract_bytes)

    def path(source):
        return (contract_path.parent / source["path"]).resolve()

    _validate_contract(contract, path)
    inventory = _indexed(path(contract["inventory"]), {"word", "type"})
    groups = defaultdict(list)
    for wid, row in inventory.items():
        if not row["word"].strip() or not row["type"].strip():
            raise ValueError("Missing inventory spelling/POS")
        groups[_lexeme(row["word"])].append(wid)
    references = {}
    all_humans = {}
    for source in contract["references"]:
        if source["role"] == "positive_seed":
            rows = {
                _lexeme(x.strip())
                for x in path(source).read_text().splitlines()
                if x.strip() and not x.strip().startswith("#")
            }
        else:
            rows = _indexed(path(source), {"word", source["level_column"]})
        if source["role"] == "positive_seed":
            if not rows or not rows <= groups.keys():
                raise ValueError("Empty seed or forms outside declared inventory")
        else:
            _align(rows, inventory, complete=source["role"] == "historical_snapshot")
            for row in rows.values():
                level = _level(row[source["level_column"]])
                if source["role"] == "human_labels":
                    word = _lexeme(row["word"])
                    if word in all_humans and all_humans[word] != level:
                        raise ValueError("Contradictory human labels for exact form")
                    all_humans[word] = level
        references[source["id"]] = (source, rows)
    report = dict(
        schema=SCHEMA,
        status="audit_only",
        upload_authorized=False,
        population_accuracy=None,
        inventory_rows=len(inventory),
        exact_forms=len(groups),
        human_forms=len(all_humans),
        unknown_forms=len(groups) - len(all_humans),
        candidates={},
        findings=[],
    )
    drift_rows, seed_rows, human_rows = [], [], []

    def finding(code, source, candidate="", **detail):
        report["findings"].append(
            dict(code=code, source=source, candidate=candidate, detail=detail)
        )

    for spec in contract["references"] + contract["candidates"]:
        if spec["recorded_on"] is None:
            finding("SOURCE_DATE_UNKNOWN", spec["id"])
    for sid, (source, rows) in references.items():
        if source["role"] == "historical_snapshot":
            finding("HISTORICAL_REFERENCE_NOT_TRUTH", sid)
            conflicts = sum(
                len({rows[i][source["level_column"]] for i in ids}) > 1 for ids in groups.values()
            )
            if conflicts:
                finding("HISTORICAL_FORM_LEVEL_CONFLICT", sid, forms=conflicts)
        elif source["role"] == "positive_seed":
            finding("POSITIVE_SEED_NOT_PRECISION_DENOMINATOR", sid)
    for spec in contract["candidates"]:
        cid = spec["id"]
        scored = _indexed(path(spec), {"word", "type", spec["level_column"]})
        _align(scored, inventory, complete=True)
        scores = {i: _level(r[spec["level_column"]]) for i, r in scored.items()}
        if any(len({scores[i] for i in ids}) != 1 for ids in groups.values()):
            raise ValueError("Candidate differs across exact-form POS rows")
        forms = {word: scores[ids[0]] for word, ids in groups.items()}
        l1_ids = {i for i, n in scores.items() if n == 1}
        l1_forms = {w for w, n in forms.items() if n == 1}
        if not l1_ids:
            finding("NO_L1_PREDICTIONS", cid, cid)
        result = dict(historical={}, seeds={}, humans={})
        for sid, (source, rows) in references.items():
            if source["role"] == "historical_snapshot":
                old = {i for i, r in rows.items() if _level(r[source["level_column"]]) == 1}
                inter = len(l1_ids & old)
                ceiling = _ratio(min(len(l1_ids), len(old)), max(len(l1_ids), len(old)))
                drift = dict(
                    l1_ids=len(l1_ids),
                    reference_l1_ids=len(old),
                    intersection=inter,
                    jaccard=_ratio(inter, len(l1_ids | old)),
                    maximum_jaccard=ceiling,
                )
                result["historical"][sid] = drift
                drift_rows.append(dict(candidate=cid, source=sid, **drift))
                if ceiling is not None and ceiling < contract["legacy_thresholds"]["l1_jaccard"]:
                    finding("L1_JACCARD_THRESHOLD_INFEASIBLE", sid, cid, ceiling=ceiling)
            elif source["role"] == "positive_seed":
                hits = len(rows & l1_forms)
                ceiling = _ratio(min(len(rows), len(l1_forms)), len(l1_forms))
                seed = dict(
                    n=len(rows),
                    hits=hits,
                    recall=_ratio(hits, len(rows)),
                    within_one=sum(forms[w] <= 2 for w in rows),
                    severe=sum(forms[w] >= 3 for w in rows),
                    semantic_precision=None,
                    membership_ratio=_ratio(hits, len(l1_forms)),
                    maximum_membership_ratio=ceiling,
                )
                if seed["recall"] < contract["legacy_thresholds"]["anchor_recall"]:
                    finding(
                        "SEED_RECALL_BELOW_LEGACY_THRESHOLD",
                        sid,
                        cid,
                        recall=seed["recall"],
                        threshold=contract["legacy_thresholds"]["anchor_recall"],
                    )
                result["seeds"][sid] = seed
                seed_rows.extend(
                    dict(
                        candidate=cid,
                        source=sid,
                        word=w,
                        seed_level=1,
                        candidate_level=forms[w],
                        gap=forms[w] - 1,
                    )
                    for w in sorted(rows)
                )
                if (
                    ceiling is not None
                    and ceiling < contract["legacy_thresholds"]["anchor_precision"]
                ):
                    finding("ANCHOR_MEMBERSHIP_THRESHOLD_INFEASIBLE", sid, cid, ceiling=ceiling)
            elif source["role"] == "human_labels":
                labels = {
                    _lexeme(r["word"]): _level(r[source["level_column"]]) for r in rows.values()
                }
                comparison = [
                    dict(candidate=cid, source=sid, word=w, human_level=n, candidate_level=forms[w])
                    for w, n in sorted(labels.items())
                ]
                human_rows.extend(comparison)
                labelled_l1 = {w for w in labels if forms[w] == 1}
                true_l1 = {w for w, n in labels.items() if n == 1}
                use = spec["label_use"][sid]
                interpretation = {
                    "fit": "training_fit_not_validation",
                    "override": "integrity_only_not_accuracy",
                    "none": "selected_cohort_not_population",
                    "unknown": "unknown_reuse_not_validation",
                }[use]
                preserved = all(r["candidate_level"] == r["human_level"] for r in comparison)
                if use == "fit":
                    finding("LABELS_REUSED_FOR_FIT", sid, cid)
                elif use == "override":
                    finding(
                        "HUMAN_OVERRIDE_PRESERVED" if preserved else "HUMAN_OVERRIDE_NOT_PRESERVED",
                        sid,
                        cid,
                    )
                elif use == "unknown":
                    finding("LABEL_USE_UNKNOWN", sid, cid)
                result["humans"][sid] = dict(
                    interpretation=interpretation,
                    override_preserved=preserved if use == "override" else None,
                    metrics=_metrics(comparison, "candidate_level"),
                    l1_precision_on_labelled_forms=_ratio(
                        len(labelled_l1 & true_l1), len(labelled_l1)
                    ),
                    l1_recall_on_labelled_forms=_ratio(len(labelled_l1 & true_l1), len(true_l1)),
                    labelled_predicted_l1=len(labelled_l1),
                    labelled_true_l1=len(true_l1),
                    predicted_l1_total=len(l1_forms),
                    predicted_l1_label_coverage=_ratio(len(labelled_l1), len(l1_forms)),
                    unknown_forms=len(forms) - len(labels),
                    labelled_form_coverage=len(labels) / len(forms),
                    selection=source["selection"],
                    declared_label_use=spec["label_use"][sid],
                    population_precision=None,
                )
                finding(
                    "SELECTED_LABELS_NOT_POPULATION_VALIDATION",
                    sid,
                    cid,
                    selection=source["selection"],
                )
        report["candidates"][cid] = result
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".validation-audit-") as tmp:
        staged = Path(tmp) / "output"
        staged.mkdir()
        _write_csv(
            staged / "drift.csv",
            [
                "candidate",
                "source",
                "l1_ids",
                "reference_l1_ids",
                "intersection",
                "jaccard",
                "maximum_jaccard",
            ],
            drift_rows,
        )
        _write_csv(
            staged / "seed-comparison.csv",
            ["candidate", "source", "word", "seed_level", "candidate_level", "gap"],
            seed_rows,
        )
        _write_csv(
            staged / "human-comparison.csv",
            ["candidate", "source", "word", "human_level", "candidate_level"],
            human_rows,
        )
        _write_csv(
            staged / "findings.csv",
            ["code", "source", "candidate", "detail_json"],
            [
                dict(
                    code=r["code"],
                    source=r["source"],
                    candidate=r["candidate"],
                    detail_json=json.dumps(r["detail"], sort_keys=True),
                )
                for r in report["findings"]
            ],
        )
        (staged / "contract.json").write_bytes(contract_bytes)
        (staged / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        if _sha256(contract_path) != contract_hash:
            raise ValueError("Contract changed during audit")
        for spec in [contract["inventory"], *contract["references"], *contract["candidates"]]:
            if _sha256(path(spec)) != spec["sha256"]:
                raise ValueError("Source changed during audit")
        receipt = dict(
            inputs={
                str(p): _sha256(p)
                for p in [
                    contract_path.resolve(),
                    path(contract["inventory"]),
                    *[path(s) for s in contract["references"] + contract["candidates"]],
                ]
            },
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
        (staged / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
        staged.rename(output_dir)
    return report
