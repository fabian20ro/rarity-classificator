"""Versioned source manifest + immutable CSVs → audit-only reports."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.validation_contract import audit_validation_contract
from tests.test_exact_form import write_csv


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")
    return path


class ValidationContractTests(unittest.TestCase):
    def inputs(self, root):
        inventory = write_csv(
            root / "inventory.csv",
            [
                dict(word_id=i, word=w, type=p)
                for i, w, p in [
                    (1, "ata", "N"),
                    (2, "ata", "V"),
                    (3, "ață", "N"),
                    (4, "rar", "A"),
                    (5, "obscur", "N"),
                    (6, "comun", "A"),
                ]
            ],
        )
        import csv

        rows = list(csv.DictReader(inventory.open()))
        scores = write_csv(
            root / "scores.csv",
            [dict(r, final_level=n) for r, n in zip(rows, [1, 1, 1, 4, 1, 2], strict=True)],
        )
        historical = write_csv(
            root / "historical.csv",
            [dict(r, rarity_level=n) for r, n in zip(rows, [5, 2, 3, 4, 5, 1], strict=True)],
        )
        humans = write_csv(
            root / "human.csv",
            [
                dict(word_id=i, word=w, working_level=n)
                for i, w, n in [(1, "ata", 5), (3, "ață", 1), (4, "rar", 4), (5, "obscur", 5)]
            ],
        )
        seeds = root / "seed.txt"
        seeds.write_text("# Positive examples only\nață\nață\n")

        def source(sid, role, unit, path, **extra):
            return dict(
                id=sid,
                role=role,
                unit=unit,
                path=path.name,
                sha256=sha(path),
                universe_sha256=sha(inventory),
                recorded_on="2026-01-01",
                provenance="Saved fixture source; not live",
                **extra,
            )

        contract = dict(
            schema="rarity-validation-audit-v1",
            mode="audit",
            as_of="2026-11-02",
            inventory=dict(path=inventory.name, sha256=sha(inventory)),
            legacy_thresholds=dict(l1_jaccard=0.7, anchor_precision=0.8, anchor_recall=0.8),
            references=[
                source(
                    "old",
                    "historical_snapshot",
                    "inventory_id",
                    historical,
                    level_column="rarity_level",
                ),
                source("seed", "positive_seed", "exact_form", seeds),
                source(
                    "human",
                    "human_labels",
                    "exact_form",
                    humans,
                    level_column="working_level",
                    selection="development",
                ),
            ],
            candidates=[
                source(
                    "baseline",
                    "candidate",
                    "exact_form",
                    scores,
                    level_column="final_level",
                    label_use={"human": "none"},
                )
            ],
        )
        return save(root / "contract.json", contract)

    def test_roles_separate_historical_drift_and_positive_seed_without_upload_authority(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = self.inputs(root)
            audit_validation_contract(contract, root / "audit")
            report = json.loads((root / "audit/report.json").read_text())
            self.assertEqual(report["schema"], "rarity-validation-audit-v1")
            self.assertEqual(report["status"], "audit_only")
            self.assertFalse(report["upload_authorized"])
            self.assertNotIn("passed", report)
            drift = report["candidates"]["baseline"]["historical"]["old"]
            self.assertEqual(
                (drift["l1_ids"], drift["reference_l1_ids"], drift["intersection"]), (4, 1, 0)
            )
            self.assertEqual(drift["maximum_jaccard"], 0.25)
            seed = report["candidates"]["baseline"]["seeds"]["seed"]
            self.assertEqual((seed["n"], seed["hits"], seed["recall"]), (1, 1, 1.0))
            self.assertIsNone(seed["semantic_precision"])
            self.assertAlmostEqual(seed["maximum_membership_ratio"], 1 / 3)
            codes = {x["code"] for x in report["findings"]}
            self.assertTrue(
                {
                    "HISTORICAL_REFERENCE_NOT_TRUTH",
                    "POSITIVE_SEED_NOT_PRECISION_DENOMINATOR",
                    "L1_JACCARD_THRESHOLD_INFEASIBLE",
                    "ANCHOR_MEMBERSHIP_THRESHOLD_INFEASIBLE",
                }
                <= codes
            )

    def test_human_metrics_use_exact_forms_and_keep_unlabelled_population_unknown(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = self.inputs(root)
            audit_validation_contract(contract, root / "audit")
            report = json.loads((root / "audit/report.json").read_text())
            human = report["candidates"]["baseline"]["humans"]["human"]
            self.assertEqual(human["metrics"]["n"], 4)  # ata counted once across its two POS IDs
            self.assertEqual(human["metrics"]["severe"], 2)
            self.assertEqual(human["metrics"]["excess_error_total"], 6)
            self.assertEqual(human["metrics"]["per_level"]["4"]["severe"], 0)
            self.assertEqual(human["metrics"]["per_level"]["5"]["severe"], 2)
            self.assertAlmostEqual(human["l1_precision_on_labelled_forms"], 1 / 3)
            self.assertEqual(human["l1_recall_on_labelled_forms"], 1)
            self.assertEqual(human["unknown_forms"], 1)
            self.assertEqual(human["labelled_form_coverage"], 0.8)
            self.assertEqual(human["selection"], "development")
            self.assertEqual(human["declared_label_use"], "none")
            self.assertIsNone(human["population_precision"])
            self.assertIsNone(report["population_accuracy"])
            import csv

            rows = list(csv.DictReader((root / "audit/human-comparison.csv").open()))
            self.assertEqual(
                {r["word"]: r["human_level"] for r in rows},
                {"ata": "5", "ață": "1", "rar": "4", "obscur": "5"},
            )

    def test_incompatible_or_unverifiable_manifest_fails_before_publishing(self):
        changes = {
            "unknown_version": lambda c: c.update(schema="rarity-validation-audit-v99"),
            "upload_mode": lambda c: c.update(mode="upload"),
            "positive_seed_id_unit": lambda c: c["references"][1].update(unit="inventory_id"),
            "unknown_role": lambda c: c["references"][0].update(role="ground_truth"),
            "missing_provenance": lambda c: c["references"][0].pop("provenance"),
            "future_reference": lambda c: c["references"][0].update(recorded_on="2027-01-01"),
            "different_universe": lambda c: c["references"][0].update(universe_sha256="f" * 64),
            "source_hash_changed": lambda c: c["references"][0].update(sha256="f" * 64),
            "implicit_label_reuse": lambda c: c["candidates"][0].update(label_use={}),
            "duplicate_source_id": lambda c: c["references"][1].update(id="old"),
            "nonfinite_threshold": lambda c: c["legacy_thresholds"].update(l1_jaccard=float("nan")),
        }
        for name, change in changes.items():
            with self.subTest(name=name), TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = self.inputs(root)
                contract = json.loads(path.read_text())
                change(contract)
                save(path, contract)
                with self.assertRaises(ValueError):
                    audit_validation_contract(path, root / "audit")
                self.assertFalse((root / "audit").exists())

    def test_incompatible_csv_identity_pos_or_human_labels_fail_closed(self):
        for defect in (
            "shifted_ids",
            "human_spelling",
            "human_conflict",
            "different_pos_scores",
            "partial_candidate",
            "history_pos",
            "seed_outside_inventory",
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as tmp:
                import csv

                root = Path(tmp)
                path = self.inputs(root)
                c = json.loads(path.read_text())
                sid = (
                    "old"
                    if defect in ("shifted_ids", "history_pos")
                    else "human"
                    if defect.startswith("human")
                    else "seed"
                    if defect == "seed_outside_inventory"
                    else "baseline"
                )
                spec = next(s for s in c["references"] + c["candidates"] if s["id"] == sid)
                target = root / spec["path"]
                if defect == "seed_outside_inventory":
                    target.write_text("necunoscut\n")
                else:
                    rows = list(csv.DictReader(target.open()))
                    if defect == "shifted_ids":
                        for r in rows:
                            r["word_id"] = str(int(r["word_id"]) + 6)
                    elif defect == "human_spelling":
                        rows[0]["word"] = "ață"
                    elif defect == "human_conflict":
                        rows.append(dict(word_id="2", word="ata", working_level="4"))
                    elif defect == "different_pos_scores":
                        rows[1]["final_level"] = "4"
                    elif defect == "partial_candidate":
                        rows.pop()
                    else:
                        rows[0]["type"] = "A"
                    write_csv(target, rows)
                spec["sha256"] = sha(target)
                save(path, c)
                with self.assertRaises(ValueError):
                    audit_validation_contract(path, root / "audit")
                self.assertFalse((root / "audit").exists())

    def test_provenance_warnings_expose_unknown_dates_pos_conflicts_and_label_reuse(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.inputs(root)
            c = json.loads(path.read_text())
            c["references"][1]["recorded_on"] = None
            c["candidates"][0]["label_use"]["human"] = "fit"
            c["candidates"].append(
                dict(c["candidates"][0], id="override", label_use={"human": "override"})
            )
            save(path, c)
            report = audit_validation_contract(path, root / "audit")
            codes = {r["code"] for r in report["findings"]}
            self.assertTrue(
                {
                    "SOURCE_DATE_UNKNOWN",
                    "HISTORICAL_FORM_LEVEL_CONFLICT",
                    "LABELS_REUSED_FOR_FIT",
                    "HUMAN_OVERRIDE_NOT_PRESERVED",
                }
                <= codes
            )
            h = report["candidates"]["override"]["humans"]["human"]
            self.assertFalse(h["override_preserved"])
            self.assertEqual(h["interpretation"], "integrity_only_not_accuracy")
            self.assertEqual(
                report["candidates"]["baseline"]["humans"]["human"]["interpretation"],
                "training_fit_not_validation",
            )
            self.assertFalse(report["upload_authorized"])

    def test_empty_l1_is_undefined_and_never_a_perfect_score(self):
        with TemporaryDirectory() as tmp:
            import csv

            root = Path(tmp)
            path = self.inputs(root)
            c = json.loads(path.read_text())
            for spec in [c["candidates"][0], c["references"][0]]:
                target = root / spec["path"]
                rows = list(csv.DictReader(target.open()))
                for r in rows:
                    r[spec["level_column"]] = "4"
                write_csv(target, rows)
                spec["sha256"] = sha(target)
            save(path, c)
            report = audit_validation_contract(path, root / "audit")
            result = report["candidates"]["baseline"]
            self.assertIsNone(result["historical"]["old"]["jaccard"])
            self.assertIsNone(result["seeds"]["seed"]["membership_ratio"])
            self.assertIsNone(result["humans"]["human"]["l1_precision_on_labelled_forms"])
            self.assertIn("NO_L1_PREDICTIONS", {f["code"] for f in report["findings"]})
            self.assertIn(
                "SEED_RECALL_BELOW_LEGACY_THRESHOLD", {f["code"] for f in report["findings"]}
            )
            self.assertFalse(report["upload_authorized"])

    def test_perfect_metrics_are_audit_only_with_csv_findings_and_immutable_replay(self):
        with TemporaryDirectory() as tmp:
            import csv
            from unittest.mock import patch

            root = Path(tmp)
            path = self.inputs(root)
            c = json.loads(path.read_text())
            c["candidates"][0]["label_use"]["human"] = "override"
            for spec in c["references"] + c["candidates"]:
                target = root / spec["path"]
                if spec["role"] == "positive_seed":
                    target.write_text("ata\nață\nrar\nobscur\ncomun\n")
                else:
                    rows = list(csv.DictReader(target.open()))
                    for row in rows:
                        row[spec["level_column"]] = "1"
                    write_csv(target, rows)
                spec["sha256"] = sha(target)
            save(path, c)
            originals = {p: sha(p) for p in root.iterdir()}
            with (
                patch("subprocess.Popen", side_effect=AssertionError("LLM forbidden")),
                patch("socket.create_connection", side_effect=AssertionError("Network forbidden")),
                patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
            ):
                report = audit_validation_contract(path, root / "audit")
                audit_validation_contract(path, root / "replay")
            result = report["candidates"]["baseline"]
            self.assertEqual(result["historical"]["old"]["jaccard"], 1)
            self.assertEqual(result["seeds"]["seed"]["membership_ratio"], 1)
            self.assertTrue(result["humans"]["human"]["override_preserved"])
            self.assertFalse(report["upload_authorized"])
            self.assertIsNone(report["population_accuracy"])
            findings = list(csv.DictReader((root / "audit/findings.csv").open()))
            self.assertIn("HUMAN_OVERRIDE_PRESERVED", {f["code"] for f in findings})
            for p in (root / "audit").iterdir():
                self.assertEqual(p.read_bytes(), (root / "replay" / p.name).read_bytes())
            self.assertTrue(all(sha(p) == digest for p, digest in originals.items()))
            with self.assertRaises(FileExistsError):
                audit_validation_contract(path, root / "audit")
