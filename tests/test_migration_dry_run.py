"""Frozen scores + fresh snapshot → exact-form/POS migration diagnostics, no upload."""

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.migration_dry_run import plan_migration
from tests.test_exact_form import write_csv


def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


class MigrationDryRunTests(unittest.TestCase):
    def inputs(self, root):
        candidate = write_csv(
            root / "candidate.csv",
            [
                dict(
                    word_id=i,
                    word=w,
                    type=p,
                    final_level=n,
                    decision_source=source,
                    provenance_id=prov,
                )
                for i, w, p, n, source, prov in [
                    (1, "ata", "N", 5, "human", "form:1"),
                    (2, "ata", "N", 5, "human", "form:1"),
                    (3, "ata", "V", 5, "human", "form:1"),
                    (4, "ață", "N", 1, "baseline", "form:4"),
                ]
            ],
        )
        live = write_csv(
            root / "snapshot.csv",
            [
                dict(word_id=i, word=w, type=p, rarity_level=n)
                for i, w, p, n in [
                    (100, "ata", "N", 4),
                    (101, "ata", "N", 3),
                    (205, "ata", "V", 1),
                    (1, "ață", "N", 2),
                ]
            ],
        )
        return candidate, live

    def test_exact_form_pos_mapping_ignores_reused_ids_and_preserves_duplicate_group_scores(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = self.inputs(root)
            report = plan_migration(*inputs, root / "out")
            rows = {r["live_word_id"]: r for r in read(root / "out/plan.csv")}
            self.assertEqual(
                {i: r["proposed_level"] for i, r in rows.items()},
                {"100": "5", "101": "5", "205": "5", "1": "1"},
            )
            self.assertEqual(json.loads(rows["100"]["source_word_ids_json"]), [1, 2])
            self.assertEqual(rows["100"]["mapping_kind"], "equivalent_duplicate_group")
            self.assertEqual(json.loads(rows["1"]["source_word_ids_json"]), [4])
            self.assertEqual(report["changed_rows"], 4)
            self.assertEqual(report["large_difference_rows"], 2)
            self.assertEqual(report["mapped_rows"], 4)
            self.assertFalse(report["upload_authorized"])
            self.assertEqual(len(read(root / "out/level-conflicts.csv")), 2)

    def test_missing_pos_and_duplicate_cardinality_changes_are_quarantined(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, live = self.inputs(root)
            rows = read(live)[1:]
            rows[-1]["type"] = "V"
            write_csv(live, rows)
            report = plan_migration(source, live, root / "out")
            self.assertEqual([r["live_word_id"] for r in read(root / "out/plan.csv")], ["205"])
            issues = read(root / "out/identity-issues.csv")
            self.assertEqual(
                {r["reason"] for r in issues}, {"cardinality_mismatch", "source_only", "live_only"}
            )
            self.assertEqual(report["unmapped_source_rows"], 3)
            self.assertEqual(report["unmapped_live_rows"], 2)
            self.assertFalse(report["mapping_complete"])
            self.assertFalse(report["upload_authorized"])

    def test_inconsistent_exact_form_scores_or_invalid_source_metadata_fail_closed(self):
        for defect in (
            "duplicate_levels",
            "pos_levels",
            "unknown_source",
            "empty_word",
            "invalid_live_level",
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as tmp:
                root = Path(tmp)
                source, live = self.inputs(root)
                target = live if defect == "invalid_live_level" else source
                rows = read(target)
                if defect == "duplicate_levels":
                    rows[1]["final_level"] = "4"
                elif defect == "pos_levels":
                    rows[2]["final_level"] = "4"
                elif defect == "unknown_source":
                    rows[0]["decision_source"] = "model"
                elif defect == "empty_word":
                    rows[0]["word"] = ""
                else:
                    rows[0]["rarity_level"] = "0"
                write_csv(target, rows)
                with self.assertRaises(ValueError):
                    plan_migration(source, live, root / "out")
                self.assertFalse((root / "out").exists())

    def test_unchanged_plan_replays_without_overwrite_or_upload_payload(self):
        with TemporaryDirectory() as tmp:
            import hashlib
            from unittest.mock import patch

            root = Path(tmp)
            source, live = self.inputs(root)
            rows = read(live)
            for r in rows:
                r["rarity_level"] = "1" if r["word"] == "ață" else "5"
            write_csv(live, rows)
            digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            originals = {p: digest(p) for p in (source, live)}
            with (
                patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
                patch("subprocess.Popen", side_effect=AssertionError("LLM forbidden")),
            ):
                report = plan_migration(source, live, root / "out")
                plan_migration(source, live, root / "replay")
            self.assertEqual(report["changed_rows"], 0)
            self.assertEqual(report["unchanged_rows"], 4)
            self.assertFalse(report["upload_authorized"])
            self.assertEqual(read(root / "out/level-conflicts.csv"), [])
            self.assertNotIn("word_id", read(root / "out/plan.csv")[0])
            for p in (root / "out").iterdir():
                self.assertEqual(p.read_bytes(), (root / "replay" / p.name).read_bytes())
            self.assertTrue(all(digest(p) == h for p, h in originals.items()))
            with self.assertRaises(FileExistsError):
                plan_migration(source, live, root / "out")
