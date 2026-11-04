"""Offline decisions first, labels second. Every model/network/DB path forbidden."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from unittest.mock import patch

from classificator.evaluation.dataset import _read_csv, _sha256, _write_csv
from classificator.evaluation.judge_comparison import _metrics
from classificator.evaluation.reduction_gate import export_reduction_gate


def read(path):
    return _read_csv(path, set())


def metrics(rows, method):
    result = _metrics(rows, method)
    errors = [abs(int(r[method]) - int(r["human_level"])) for r in rows]
    assert result["severe"] == sum(d >= 2 for d in errors)
    assert result["excess_error_total"] == sum(max(0, d - 1) for d in errors)
    assert result["within_one"] == sum(d <= 1 for d in errors)
    assert result["error_histogram"] == {str(d): errors.count(d) for d in range(5)}
    return {
        k: result[k]
        for k in (
            "n",
            "severe",
            "excess_error_total",
            "within_one",
            "mae",
            "exact",
            "error_histogram",
        )
    }


def run(base, out):
    protocol = json.loads((out / "protocol.json").read_text())
    for name, digest in {**protocol["frozen"], **protocol["source_inputs"]}.items():
        assert _sha256(Path(name)) == digest, name
    protected = json.loads((out / "protected-inputs.json").read_text())
    for name, digest in protected.items():
        assert _sha256(Path(name)) == digest, name
    report = dict(
        policy=protocol["policy"],
        protocol_sha256=_sha256(out / "protocol.json"),
        cohorts={},
        scope="Reused development150 and risk-selected50 separately. No fitting/CV or population accuracy claim. Corpus attestation is not familiarity.",
    )
    methods = protocol["methods"]
    gate_summaries = {}
    with (
        patch("subprocess.run", side_effect=AssertionError("LLM/process forbidden")),
        patch("subprocess.Popen", side_effect=AssertionError("LLM/process forbidden")),
        patch("requests.adapters.HTTPAdapter.send", side_effect=AssertionError("HTTP forbidden")),
        patch("socket.create_connection", side_effect=AssertionError("Network forbidden")),
        patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
    ):
        for cohort in ("pilot150", "review50"):
            folder = out / cohort
            inputs = folder / "inputs"
            gate_summaries[cohort] = export_reduction_gate(
                inputs / "baseline.csv",
                inputs / "evidence.csv",
                inputs / "gpt.csv",
                base / "fineweb-2026-10-26/source",
                base / "corola-2026-10-28/source",
                folder / "gate",
            )
        # Only now open the reference labels; predictions already complete and immutable.
        references = {
            "pilot150": base / "gpt-judge-2026-10-31/inputs/reference.csv",
            "review50": base / "review50-2026-10-31/review-responses.csv",
        }
        family_sets = {}
        word_sets = {}
        promotion = True
        for cohort, path in references.items():
            refs = {r["word_id"]: r for r in read(path)}
            rows = read(out / cohort / "gate/decisions.csv")
            groups = {r["word_id"]: r for r in read(out / cohort / "inputs/groups.csv")}
            assert len(rows) == len(refs) == (150 if cohort == "pilot150" else 50)
            assert {r["word_id"] for r in rows} == set(refs) == set(groups)
            for r in rows:
                ref = refs[r["word_id"]]
                assert ref["word"] == r["word"] and ref["working_level"] in set("12345")
                r.update(
                    human_level=int(ref["working_level"]),
                    group=groups[r["word_id"]]["group"],
                    fold=groups[r["word_id"]]["fold"],
                )
                for method in methods:
                    r[method] = int(r[method])
                r["gpt_level"] = int(r["gpt_level"]) if r["gpt_level"] else None
                for k in (
                    "large_reduction",
                    "lexical_supported",
                    "fineweb_supported",
                    "corola_supported",
                    "corpus_supported",
                ):
                    assert r[k] in ("True", "False")
                    r[k] = r[k] == "True"
            strata = {
                "all": rows,
                "true4": [r for r in rows if r["human_level"] == 4],
                "true5": [r for r in rows if r["human_level"] == 5],
                "true45": [r for r in rows if r["human_level"] in (4, 5)],
                "large_reductions": [r for r in rows if r["large_reduction"]],
            }
            result = dict(
                gate=gate_summaries[cohort],
                reasons=dict(Counter(r["reason"] for r in rows)),
                strata={s: {m: metrics(part, m) for m in methods} for s, part in strata.items()},
            )
            severe = lambda r, m: abs(r[m] - r["human_level"]) >= 2
            result["transitions"] = dict(
                rescued=sum(
                    severe(r, "baseline_level") and not severe(r, "candidate_level") for r in rows
                ),
                introduced=sum(
                    not severe(r, "baseline_level") and severe(r, "candidate_level") for r in rows
                ),
                blocked_beneficial=sum(
                    r["large_reduction"]
                    and r["reason"] != "accepted"
                    and severe(r, "baseline_level")
                    and not severe(r, "ungated_reduction_level")
                    for r in rows
                ),
                blocked_harmful=sum(
                    r["large_reduction"]
                    and r["reason"] != "accepted"
                    and not severe(r, "baseline_level")
                    and severe(r, "ungated_reduction_level")
                    for r in rows
                ),
            )
            by_group = defaultdict(list)
            for r in rows:
                by_group[r["group"]].append(r)
            family_sets[cohort] = set(by_group)
            word_sets[cohort] = {r["word"] for r in rows}
            result["families"] = dict(
                count=len(by_group),
                largest=max(map(len, by_group.values())),
                methods={
                    m: dict(
                        families_with_severe=sum(
                            any(severe(r, m) for r in part) for part in by_group.values()
                        ),
                        macro_severe_rate=sum(
                            sum(severe(r, m) for r in part) / len(part)
                            for part in by_group.values()
                        )
                        / len(by_group),
                    )
                    for m in methods
                },
            )
            if cohort == "pilot150":
                result["existing_fold_diagnostics"] = {
                    fold: {
                        m: metrics([r for r in rows if r["fold"] == fold], m)
                        for m in ("baseline_level", "candidate_level")
                    }
                    for fold in sorted({r["fold"] for r in rows})
                }
                assert all(len({r["fold"] for r in part}) == 1 for part in by_group.values())
            checks = dict(
                severe_decreased=result["strata"]["all"]["candidate_level"]["severe"]
                < result["strata"]["all"]["baseline_level"]["severe"],
                excess_not_increased=result["strata"]["all"]["candidate_level"][
                    "excess_error_total"
                ]
                <= result["strata"]["all"]["baseline_level"]["excess_error_total"],
            )
            for level in ("true4", "true5"):
                checks[level + "_not_worse"] = all(
                    result["strata"][level]["candidate_level"][metric]
                    <= result["strata"][level]["baseline_level"][metric]
                    for metric in ("severe", "excess_error_total")
                )
            result["predeclared_checks"] = checks
            promotion &= all(checks.values())
            _write_csv(out / cohort / "comparison.csv", list(rows[0]), rows)
            report["cohorts"][cohort] = result
        report["cohort_overlap"] = dict(
            exact_words=len(word_sets["pilot150"] & word_sets["review50"]),
            group_ids=len(family_sets["pilot150"] & family_sets["review50"]),
        )
        assert report["cohort_overlap"]["exact_words"] == 0
        report["candidate_passes_predeclared_criteria"] = promotion
        report["reference_sha256"] = {str(p): _sha256(p) for p in references.values()}
        report["verification"] = dict(
            protected_files_unchanged=len(protected),
            model_calls=0,
            classifier_db_writes=0,
            new_downloads=0,
            full_coverage={"pilot150": 150, "review50": 50},
            metric_arithmetic="independently checked",
            fitting="none",
            source_inputs_verified=True,
        )
        for name, digest in protected.items():
            assert _sha256(Path(name)) == digest, name
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        manifest = dict(
            protocol_sha256=_sha256(out / "protocol.json"),
            implementation={str(Path(__file__).resolve()): _sha256(Path(__file__))},
            artifacts={
                str(p.relative_to(out)): _sha256(p)
                for p in [
                    out / "report.json",
                    *(out.glob("*/comparison.csv")),
                    *(out.glob("*/gate/manifest.json")),
                ]
            },
        )
        (out / "analysis-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                c: dict(
                    gate=r["gate"],
                    all={
                        m: {k: v[k] for k in ("n", "severe", "excess_error_total")}
                        for m, v in r["strata"]["all"].items()
                    },
                    checks=r["predeclared_checks"],
                )
                for c, r in report["cohorts"].items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.base.resolve(), args.output.resolve())
