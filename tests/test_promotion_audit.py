"""Agreed seam: pinned CSV sources → audit package, never DB application."""

import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.promotion_audit import prepare_promotion_audit
from tests.test_exact_form import write_csv


def rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PromotionAuditTests(unittest.TestCase):
    def fixture(self, root):
        # IDs differ between source and snapshot. ata is human-protected across POS.
        items = [
            (1, "ata", "N", 5, 2),
            (2, "ata", "V", 5, 2),
            (3, "ață", "N", 4, 1),
            (4, "caftan", "N", 1, 4),
            (5, "rar", "A", 4, 4),
        ]
        write_csv(
            root / "snapshot.csv",
            [
                dict(word_id=i + 100, word=w, type=p, rarity_level=old, version=i + 200)
                for i, w, p, old, new in items
            ],
        )
        write_csv(
            root / "baseline.csv",
            [
                dict(
                    word_id=i,
                    word=w,
                    type=p,
                    rarity_level=new,
                    route="frequency_thresholds" if i <= 3 else "missing_group_median",
                    frequency="0.1" if i <= 3 else "",
                )
                for i, w, p, old, new in items
            ],
        )
        write_csv(
            root / "candidate.csv",
            [
                dict(
                    word_id=i,
                    word=w,
                    type=p,
                    final_level=old if i <= 2 else new,
                    decision_source="human" if i <= 2 else "baseline",
                    provenance_id=f"form:{i}",
                )
                for i, w, p, old, new in items
            ],
        )
        write_csv(root / "pilot.csv", [dict(word_id=1, word="ata", working_level=5)])
        write_csv(root / "review.csv", [dict(word_id=1, word="ata", working_level=5)])
        (root / "anchors.txt").write_text("ață\n")
        sources = {
            k: dict(path=p, sha256=digest(root / p))
            for k, p in {
                "snapshot": "snapshot.csv",
                "baseline": "baseline.csv",
                "candidate": "candidate.csv",
                "human_pilot150": "pilot.csv",
                "human_review50": "review.csv",
                "anchors": "anchors.txt",
            }.items()
        }
        contract = dict(
            schema="automatic-promotion-audit-v1",
            mode="audit",
            upload_authorized=False,
            acceptance="pending",
            inputs=sources,
        )
        path = root / "contract.json"
        path.write_text(json.dumps(contract))
        return path

    def test_package_preserves_humans_and_reverses_disjoint_route_deltas(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            contract = self.fixture(root)
            report = prepare_promotion_audit(contract, root / "out")
            out = root / "out"
            self.assertEqual(report["changed_rows"], 2)
            self.assertEqual(report["protected_human_rows"], 2)
            self.assertFalse(report["upload_authorized"])
            self.assertFalse(report["ready_to_apply"])
            self.assertEqual(
                [r["word_id"] for r in rows(out / "human-guards.csv")], ["101", "102"]
            )
            self.assertEqual(
                [
                    (r["word_id"], r["rarity_level"])
                    for r in rows(out / "candidate.csv")
                ],
                [("101", "5"), ("102", "5"), ("103", "1"), ("104", "4"), ("105", "4")],
            )
            change = rows(out / "fallback-changes.csv")
            self.assertEqual(
                [
                    (
                        r["word_id"],
                        r["expected_level"],
                        r["proposed_level"],
                        r["snapshot_version"],
                    )
                    for r in change
                ],
                [("104", "1", "4", "204")],
            )
            rollback = rows(out / "fallback-rollback.csv")
            self.assertEqual(
                [
                    (r["word_id"], r["expected_level"], r["restore_level"])
                    for r in rollback
                ],
                [("104", "4", "1")],
            )
            self.assertEqual(
                rollback[0]["version_source"], "committed_apply_receipt_required"
            )
            self.assertEqual(
                [r["word_id"] for r in rows(out / "wordfreq-changes.csv")], ["103"]
            )

    def test_changed_source_or_approval_flag_cannot_produce_a_package(self):
        for mutation in ("source", "mode", "upload_authorized", "acceptance"):
            with self.subTest(mutation=mutation), TemporaryDirectory() as temp:
                root = Path(temp)
                contract = self.fixture(root)
                if mutation == "source":
                    with (root / "candidate.csv").open("a") as stream:
                        stream.write("\n")
                else:
                    data = json.loads(contract.read_text())
                    data[mutation] = {
                        "mode": "apply",
                        "upload_authorized": True,
                        "acceptance": "approved",
                    }[mutation]
                    contract.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    prepare_promotion_audit(contract, root / "out")
                self.assertFalse((root / "out").exists())

    def test_resealed_inputs_cannot_change_human_or_frozen_baseline_decisions(self):
        mutations = [
            ("candidate", 0, "final_level", "4"),
            ("candidate", 1, "decision_source", "baseline"),
            ("snapshot", 0, "rarity_level", "4"),
            ("candidate", 3, "final_level", "2"),
            ("baseline", 2, "word", "ata"),
            ("baseline", 3, "frequency", "0.2"),
            ("snapshot", 3, "version", "0"),
            ("human_review50", 0, "working_level", "4"),
        ]
        for key, index, field, value in mutations:
            with self.subTest(key=key, field=field), TemporaryDirectory() as temp:
                root = Path(temp)
                contract = self.fixture(root)
                data = json.loads(contract.read_text())
                path = root / data["inputs"][key]["path"]
                content = rows(path)
                content[index][field] = value
                write_csv(path, content)
                data["inputs"][key]["sha256"] = digest(path)
                contract.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    prepare_promotion_audit(contract, root / "out")
                self.assertFalse((root / "out").exists())

    def test_failed_gate_is_explicit_and_replay_preserves_sources_and_existing_output(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            contract = self.fixture(root)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            report = prepare_promotion_audit(contract, root / "first")
            self.assertIn("legacy_quality_gate_failed", report["blockers"])
            prepare_promotion_audit(contract, root / "second")
            first = {
                str(p.relative_to(root / "first")): p.read_bytes()
                for p in (root / "first").rglob("*")
                if p.is_file()
            }
            second = {
                str(p.relative_to(root / "second")): p.read_bytes()
                for p in (root / "second").rglob("*")
                if p.is_file()
            }
            self.assertEqual(first, second)
            with self.assertRaises(FileExistsError):
                prepare_promotion_audit(contract, root / "first")
            for name, data in before.items():
                self.assertEqual((root / name).read_bytes(), data)

    def test_unmapped_inventory_cannot_publish_partial_package(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            contract = self.fixture(root)
            path = root / "snapshot.csv"
            write_csv(path, rows(path)[:-1])
            data = json.loads(contract.read_text())
            data["inputs"]["snapshot"]["sha256"] = digest(path)
            contract.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                prepare_promotion_audit(contract, root / "out")
            self.assertFalse((root / "out").exists())

    def test_snapshot_cannot_supply_a_competing_score_for_quality_audit(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            contract = self.fixture(root)
            path = root / "snapshot.csv"
            write_csv(path, [dict(r, final_level=1) for r in rows(path)])
            data = json.loads(contract.read_text())
            data["inputs"]["snapshot"]["sha256"] = digest(path)
            contract.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                prepare_promotion_audit(contract, root / "out")
            self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main()
