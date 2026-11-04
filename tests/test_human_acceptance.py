"""Pinned package and full candidate CSV → audit-only acceptance decision."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.human_corrections import prepare_human_corrections
from classificator.evaluation.migration_dry_run import plan_migration
from tests import test_human_corrections as fixtures
from tests.test_exact_form import write_csv
from tests.test_local_evidence import read


class HumanAcceptanceTests(unittest.TestCase):
    def inputs(self, root, *, change_l1=False):
        plan, export, snapshot = fixtures.HumanCorrectionTests().inputs(root)
        if not change_l1:
            rows = read(snapshot)
            rows[2]["rarity_level"] = "1"
            snapshot = write_csv(root / "snapshot.csv", rows)
            plan = root / "pinned-plan"
            plan_migration(export / "candidate.csv", snapshot, plan)
        package = root / "package"
        summary = prepare_human_corrections(plan, export, package)
        rows = read(snapshot)
        targets = {r["live_word_id"]: r["target_level"] for r in read(package / "corrections.csv")}
        for r in rows:
            r["rarity_level"] = targets.get(r["word_id"], r["rarity_level"])
        candidate = write_csv(root / "candidate.csv", rows)
        anchors = root / "anchors.txt"
        anchors.write_text("  ata  \n")
        sources = dict(
            package_manifest=package / "manifest.json",
            plan_manifest=plan / "manifest.json",
            human_export_manifest=export / "manifest.json",
            snapshot=snapshot,
            candidate=candidate,
            anchors=anchors,
        )
        contract = dict(
            version="human-corrections-acceptance-audit-v1",
            mode="audit",
            as_of="2026-11-03",
            sources={
                k: dict(path=str(p), sha256=fixtures.fixtures.sha(p)) for k, p in sources.items()
            },
            scope={k: summary[k] for k in ("correction_rows", "guard_rows", "human_references")},
        )
        path = root / "policy.json"
        path.write_text(json.dumps(contract))
        return path

    def test_human_policy_can_pass_without_claiming_legacy_gate_or_upload_authority(self):
        from classificator.evaluation.human_acceptance import audit_human_acceptance

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = self.inputs(root)
            result = audit_human_acceptance(policy, root / "audit")
            self.assertTrue(result["human_policy_satisfied"])
            self.assertFalse(result["legacy_gate"]["passed"])
            self.assertEqual(
                result["scope"], dict(correction_rows=1, guard_rows=3, human_references=2)
            )
            self.assertEqual(result["unchanged_inventory_rows"], 4)
            self.assertTrue(result["inverse_restores_snapshot"])
            self.assertEqual(result["legacy_gate"]["l1_jaccard"], 1.0)
            self.assertFalse(result["upload_authorized"])
            self.assertFalse(result["rollback_authorized"])
            self.assertFalse(result["freshness_verified"])
            self.assertIsNone(result["population_accuracy"])
            self.assertIsNone(result["seed_semantic_precision"])
            self.assertTrue(result["promotion_blocked"])
            self.assertEqual(read(root / "audit/changes.csv")[0]["live_word_id"], "100")
            conflict = read(root / "audit/seed-conflicts.csv")[0]
            self.assertEqual((conflict["word"], conflict["human_level"]), ("ata", "5"))

    def test_resealed_package_cannot_change_scores_scope_rollback_or_lineage(self):
        from classificator.evaluation.human_acceptance import audit_human_acceptance

        for defect in ("target", "rollback", "guard", "reference", "summary", "lineage"):
            with self.subTest(defect=defect), TemporaryDirectory() as tmp:
                root = Path(tmp)
                policy_path = self.inputs(root)
                policy = json.loads(policy_path.read_text())
                manifest_path = Path(policy["sources"]["package_manifest"]["path"])
                package = manifest_path.parent
                manifest = json.loads(manifest_path.read_text())
                filename = {
                    "target": "corrections.csv",
                    "rollback": "rollback.csv",
                    "guard": "preconditions.csv",
                    "reference": "references.csv",
                    "summary": "summary.json",
                }.get(defect)
                if defect == "lineage":
                    manifest["inputs"] = {
                        str(root / "candidate.csv"): fixtures.fixtures.sha(root / "candidate.csv")
                    }
                elif defect == "summary":
                    summary = json.loads((package / filename).read_text())
                    summary["correction_rows"] = 100
                    (package / filename).write_text(json.dumps(summary))
                else:
                    rows = read(package / filename)
                    if defect == "target":
                        rows[0]["target_level"] = "2"
                    elif defect == "rollback":
                        rows[0]["restore_level"] = "1"
                    elif defect == "guard":
                        rows.pop(1)  # Already-correct human POS still needs protection.
                    else:
                        rows[0]["level"] = "2"
                    write_csv(package / filename, rows)
                if filename:
                    manifest["artifacts"][filename] = fixtures.fixtures.sha(package / filename)
                manifest_path.write_text(json.dumps(manifest))
                policy["sources"]["package_manifest"]["sha256"] = fixtures.fixtures.sha(
                    manifest_path
                )
                policy_path.write_text(json.dumps(policy))
                with self.assertRaises(ValueError):
                    audit_human_acceptance(policy_path, root / "audit")
                self.assertFalse((root / "audit").exists())

    def test_unknown_or_relaxed_policy_and_rebound_snapshot_fail_closed(self):
        from classificator.evaluation.human_acceptance import audit_human_acceptance

        for defect in (
            "version",
            "mode",
            "threshold",
            "scope_bool",
            "missing_scope",
            "date",
            "unhashed",
            "wrong_manifest_name",
            "rebound_snapshot",
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = self.inputs(root)
                policy = json.loads(path.read_text())
                if defect in ("version", "mode"):
                    policy[defect] = "execute"
                elif defect == "threshold":
                    policy["min_l1_jaccard"] = 0
                elif defect == "scope_bool":
                    policy["scope"]["correction_rows"] = True
                elif defect == "missing_scope":
                    del policy["scope"]["guard_rows"]
                elif defect == "date":
                    policy["as_of"] = "not-a-date"
                elif defect == "unhashed":
                    policy["sources"]["candidate"]["sha256"] = ""
                elif defect == "wrong_manifest_name":
                    src = Path(policy["sources"]["package_manifest"]["path"])
                    alias = src.with_name("alias.json")
                    alias.write_bytes(src.read_bytes())
                    policy["sources"]["package_manifest"]["path"] = str(alias)
                else:
                    rows = read(Path(policy["sources"]["snapshot"]["path"]))
                    rows[-1]["rarity_level"] = "3"  # Unreviewed, but not the pinned baseline.
                    fresh = write_csv(root / "other-snapshot.csv", rows)
                    policy["sources"]["snapshot"] = dict(
                        path=str(fresh), sha256=fixtures.fixtures.sha(fresh)
                    )
                path.write_text(json.dumps(policy))
                with self.assertRaises(ValueError):
                    audit_human_acceptance(path, root / "audit")
                self.assertFalse((root / "audit").exists())

    def test_candidate_has_one_unambiguous_score_column_and_canonical_ids(self):
        from classificator.evaluation.human_acceptance import audit_human_acceptance

        for defect in ("extra_score", "invalid_level", "duplicate_id"):
            with self.subTest(defect=defect), TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = self.inputs(root)
                policy = json.loads(path.read_text())
                candidate = Path(policy["sources"]["candidate"]["path"])
                rows = read(candidate)
                if defect == "extra_score":
                    for row in rows:
                        row["final_level"] = "1"
                elif defect == "invalid_level":
                    rows[0]["rarity_level"] = "01"
                else:
                    rows.append(dict(rows[0]))
                write_csv(candidate, rows)
                policy["sources"]["candidate"]["sha256"] = fixtures.fixtures.sha(candidate)
                path.write_text(json.dumps(policy))
                with self.assertRaises(ValueError):
                    audit_human_acceptance(path, root / "audit")
                self.assertFalse((root / "audit").exists())

    def test_valid_but_out_of_scope_candidate_is_rejected_with_row_diagnostics(self):
        from classificator.evaluation.human_acceptance import audit_human_acceptance

        for defect, bad_id in (
            ("wrong_human_score", "100"),
            ("baseline_change", "103"),
            ("unchanged_human", "101"),
            ("identity", "100"),
            ("missing_id", "104"),
            ("new_id", "105"),
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = self.inputs(root)
                policy = json.loads(path.read_text())
                candidate = Path(policy["sources"]["candidate"]["path"])
                rows = read(candidate)
                if defect == "wrong_human_score":
                    rows[0]["rarity_level"] = "4"
                elif defect == "baseline_change":
                    rows[3]["rarity_level"] = "4"
                elif defect == "unchanged_human":
                    rows[1]["rarity_level"] = "2"
                elif defect == "identity":
                    rows[0]["word"] = "ață"
                elif defect == "missing_id":
                    rows.pop()
                else:
                    rows.append(dict(word_id="105", word="ata", type="A", rarity_level="5"))
                write_csv(candidate, rows)
                policy["sources"]["candidate"]["sha256"] = fixtures.fixtures.sha(candidate)
                path.write_text(json.dumps(policy))
                result = audit_human_acceptance(path, root / "audit")
                self.assertFalse(result["human_policy_satisfied"])
                self.assertFalse(result["upload_authorized"])
                issues = read(root / "audit/candidate-issues.csv")
                self.assertEqual([r["word_id"] for r in issues], [bad_id])

    def test_scope_and_historical_stability_remain_mandatory_for_human_only_changes(self):
        from classificator.evaluation.human_acceptance import audit_human_acceptance

        for defect, criterion in (
            ("count", "declared_scope"),
            ("l1", "full_inventory_l1_stability"),
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = self.inputs(root, change_l1=defect == "l1")
                if defect == "count":
                    policy = json.loads(path.read_text())
                    policy["scope"]["correction_rows"] = 165
                    path.write_text(json.dumps(policy))
                result = audit_human_acceptance(path, root / "audit")
                self.assertFalse(result["human_policy_satisfied"])
                failed = {
                    r["criterion"]
                    for r in read(root / "audit/criteria.csv")
                    if r["satisfied"] == "False"
                }
                self.assertEqual(failed, {criterion})
                self.assertFalse(result["upload_authorized"])
                if defect == "l1":
                    self.assertEqual(result["legacy_gate"]["l1_jaccard"], 0.5)

    def test_perfect_metrics_stay_audit_only_with_immutable_offline_replay(self):
        from classificator.evaluation.human_acceptance import audit_human_acceptance
        from unittest.mock import patch

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.inputs(root)
            policy = json.loads(path.read_text())
            anchors = Path(policy["sources"]["anchors"]["path"])
            anchors.write_text("ață\notel\n")
            policy["sources"]["anchors"]["sha256"] = fixtures.fixtures.sha(anchors)
            path.write_text(json.dumps(policy))
            originals = {p: fixtures.fixtures.sha(p) for p in root.rglob("*") if p.is_file()}
            with (
                patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
                patch("subprocess.Popen", side_effect=AssertionError("Processes forbidden")),
                patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")),
            ):
                result = audit_human_acceptance(path, root / "audit")
                audit_human_acceptance(path, root / "replay")
            self.assertTrue(result["human_policy_satisfied"])
            self.assertTrue(result["legacy_gate"]["passed"])
            for key in (
                "upload_authorized",
                "rollback_authorized",
                "apply_receipt_verified",
                "freshness_verified",
            ):
                self.assertFalse(result[key])
            self.assertTrue(result["promotion_blocked"])
            for p in (root / "audit").rglob("*"):
                if p.is_file():
                    self.assertEqual(
                        p.read_bytes(),
                        (root / "replay" / p.relative_to(root / "audit")).read_bytes(),
                    )
            self.assertTrue(all(fixtures.fixtures.sha(p) == h for p, h in originals.items()))
            with self.assertRaises(FileExistsError):
                audit_human_acceptance(path, root / "audit")
