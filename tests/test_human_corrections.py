"""Immutable migration CSVs → human-only corrections, guarded rollback and checks."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.conservative_export import export_conservative_inventory
from classificator.evaluation.migration_dry_run import plan_migration
from classificator.evaluation.human_corrections import prepare_human_corrections
from tests import test_conservative_export as fixtures
from tests.test_exact_form import write_csv
from tests.test_local_evidence import read


class HumanCorrectionTests(unittest.TestCase):
    def inputs(self, root):
        args = fixtures.ConservativeExportTests().inputs(root)
        export = root / "export"
        export_conservative_inventory(*args, export)
        live = write_csv(
            root / "live.csv",
            [
                dict(word_id=i, word=w, type=p, rarity_level=n)
                for i, w, p, n in [
                    (100, "ata", "N", 4),
                    (101, "ata", "V", 5),
                    (102, "ață", "N", 3),
                    (103, "otel", "N", 1),
                    (104, "oțel", "N", 4),
                ]
            ],
        )
        plan = root / "plan"
        plan_migration(export / "candidate.csv", live, plan)
        return plan, export, live

    def test_only_changed_human_rows_have_inverse_rollback_and_unchanged_human_guards(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, export, live = self.inputs(root)
            report = prepare_human_corrections(plan, export, root / "package")
            corrections = read(root / "package/corrections.csv")
            self.assertEqual(
                [(r["live_word_id"], r["expected_level"], r["target_level"]) for r in corrections],
                [("100", "4", "5"), ("102", "3", "1")],
            )
            rollback = read(root / "package/rollback.csv")
            self.assertEqual(
                [(r["live_word_id"], r["expected_level"], r["restore_level"]) for r in rollback],
                [("100", "5", "4"), ("102", "1", "3")],
            )
            guards = read(root / "package/preconditions.csv")
            self.assertEqual({r["live_word_id"] for r in guards}, {"100", "101", "102"})
            self.assertEqual(report["correction_rows"], 2)
            self.assertEqual(report["unchanged_human_rows"], 1)
            policy = json.loads((root / "package/policy.json").read_text())
            self.assertFalse(policy["upload_authorized"])
            self.assertFalse(policy["rollback_authorized"])
            self.assertTrue(policy["rollback_requires_confirmed_apply_receipt"])
            self.assertNotIn("word_id", corrections[0])

    def test_resealed_plan_or_reference_changes_cannot_invent_or_omit_human_corrections(self):
        for defect in (
            "wrong_level",
            "missing_guard",
            "baseline_promoted",
            "invented_reference",
            "missing_reference",
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as tmp:
                root = Path(tmp)
                plan, export, live = self.inputs(root)
                directory = export if defect.endswith("reference") else plan
                filename = "references.csv" if directory == export else "plan.csv"
                rows = read(directory / filename)
                if defect == "wrong_level":
                    rows[0]["proposed_level"] = "2"
                elif defect == "missing_guard":
                    rows = [r for r in rows if r["live_word_id"] != "101"]
                elif defect == "baseline_promoted":
                    rows[3]["decision_source"] = "human"
                elif defect == "invented_reference":
                    rows[0]["level"] = "4"
                else:
                    rows.pop()
                write_csv(directory / filename, rows)
                receipt = json.loads((directory / "manifest.json").read_text())
                receipt["artifacts"][filename] = fixtures.sha(directory / filename)
                (directory / "manifest.json").write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):
                    prepare_human_corrections(plan, export, root / "package")
                self.assertFalse((root / "package").exists())

    def test_snapshot_preconditions_detect_stale_levels_identity_and_new_reviewed_members(self):
        from classificator.evaluation.human_corrections import verify_correction_snapshot

        for defect in (
            "unchanged_human_level",
            "identity",
            "new_pos",
            "missing_row",
            "unrelated_level",
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as tmp:
                root = Path(tmp)
                plan, export, live = self.inputs(root)
                package = root / "package"
                prepare_human_corrections(plan, export, package)
                rows = read(live)
                if defect == "unchanged_human_level":
                    rows[1]["rarity_level"] = "2"
                elif defect == "identity":
                    rows[0]["word"] = "ață"
                elif defect == "new_pos":
                    rows.append(dict(word_id="105", word="ata", type="A", rarity_level="5"))
                elif defect == "missing_row":
                    rows = rows[1:]
                else:
                    rows[3]["rarity_level"] = "2"
                fresh = write_csv(root / "fresh.csv", rows)
                report = verify_correction_snapshot(package, fresh, root / "check", phase="before")
                self.assertEqual(report["conditions_satisfied"], defect == "unrelated_level")
                self.assertFalse(report["upload_authorized"])
                self.assertFalse(report["freshness_verified"])
                codes = {r["code"] for r in read(root / "check/issues.csv")}
                expected = {
                    "unchanged_human_level": "LEVEL_CHANGED",
                    "identity": "IDENTITY_CHANGED",
                    "new_pos": "MEMBERSHIP_CHANGED",
                    "missing_row": "MISSING_ROW",
                }
                if defect in expected:
                    self.assertIn(expected[defect], codes)

    def test_offline_forward_inverse_restores_snapshot_but_never_proves_execution(self):
        from classificator.evaluation.human_corrections import verify_correction_snapshot
        from unittest.mock import patch

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, export, live = self.inputs(root)
            originals = {p: fixtures.sha(p) for p in root.rglob("*") if p.is_file()}
            with (
                patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
                patch("subprocess.Popen", side_effect=AssertionError("LLM forbidden")),
            ):
                prepare_human_corrections(plan, export, root / "package")
                before = verify_correction_snapshot(
                    root / "package", live, root / "before", phase="before"
                )
                self.assertTrue(before["conditions_satisfied"])
                self.assertFalse(
                    verify_correction_snapshot(
                        root / "package", live, root / "not_after", phase="after"
                    )["conditions_satisfied"]
                )
                rows = read(live)
                index = {r["word_id"]: r for r in rows}
                for change in read(root / "package/corrections.csv"):
                    row = index[change["live_word_id"]]
                    self.assertEqual(row["rarity_level"], change["expected_level"])
                    row["rarity_level"] = change["target_level"]
                simulated = write_csv(root / "simulated.csv", rows)
                after = verify_correction_snapshot(
                    root / "package", simulated, root / "after", phase="after"
                )
                self.assertTrue(after["conditions_satisfied"])
                self.assertFalse(after["apply_receipt_verified"])
                self.assertFalse(after["rollback_authorized"])
                for inverse in read(root / "package/rollback.csv"):
                    row = index[inverse["live_word_id"]]
                    self.assertEqual(row["rarity_level"], inverse["expected_level"])
                    row["rarity_level"] = inverse["restore_level"]
                restored = write_csv(root / "restored.csv", rows)
                self.assertEqual(restored.read_bytes(), live.read_bytes())
                self.assertTrue(
                    verify_correction_snapshot(
                        root / "package", restored, root / "restored_check", phase="before"
                    )["conditions_satisfied"]
                )
                with self.assertRaises(ValueError):
                    verify_correction_snapshot(
                        root / "package", simulated, root / "rollback_auth", phase="rollback"
                    )
                prepare_human_corrections(plan, export, root / "replay")
            for p in (root / "package").iterdir():
                self.assertEqual(p.read_bytes(), (root / "replay" / p.name).read_bytes())
            self.assertTrue(all(fixtures.sha(p) == h for p, h in originals.items()))
            with self.assertRaises(FileExistsError):
                prepare_human_corrections(plan, export, root / "package")

    def test_already_correct_human_forms_do_not_select_baseline_differences(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, export, live = self.inputs(root)
            rows = read(live)
            for row in rows:
                if row["word"] == "ata":
                    row["rarity_level"] = "5"
                elif row["word"] == "ață":
                    row["rarity_level"] = "1"
            after = write_csv(root / "human_correct.csv", rows)
            plan_migration(export / "candidate.csv", after, root / "new_plan")
            report = prepare_human_corrections(root / "new_plan", export, root / "package")
            self.assertEqual(report["correction_rows"], 0)
            self.assertEqual(report["unchanged_human_rows"], 3)
            self.assertEqual(read(root / "package/corrections.csv"), [])
            self.assertEqual(read(root / "package/rollback.csv"), [])
            self.assertFalse(report["upload_authorized"])
