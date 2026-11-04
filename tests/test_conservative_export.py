"""Inventory/baseline plus immutable human references → offline candidate CSVs."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from classificator.evaluation.conservative_export import export_conservative_inventory
from tests.test_exact_form import write_csv
from tests.test_local_evidence import read


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ConservativeExportTests(unittest.TestCase):
    def inputs(self, root):
        inventory = write_csv(
            root / "inventory.csv",
            [
                dict(word_id=i, word=w, type=t)
                for i, w, t in [
                    (1, "ata", "N"),
                    (2, "ata", "V"),
                    (3, "ață", "N"),
                    (4, "otel", "N"),
                    (5, "oțel", "N"),
                ]
            ],
        )
        baseline = root / "baseline"
        baseline.mkdir()
        model = dict(
            schema=1,
            policy="wordfreq-exact-form-complete-v1",
            threshold_fit=None,
            fallback=dict(missing_level=4, global_level=4, missing_basis="missing_group_median"),
        )
        model["model_version"] = hashlib.sha256(
            json.dumps(model, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
        ).hexdigest()
        (baseline / "model.json").write_text(json.dumps(model))
        write_csv(
            baseline / "scores.csv",
            [
                dict(
                    r,
                    rarity_level=4,
                    frequency="",
                    route="missing_group_median",
                    model_version=model["model_version"],
                )
                for r in read(inventory)
            ],
        )
        (baseline / "manifest.json").write_text(
            json.dumps(
                dict(
                    inputs={str(inventory): sha(inventory)},
                    implementation={str(Path(__file__)): sha(Path(__file__))},
                    artifacts={n: sha(baseline / n) for n in ("scores.csv", "model.json")},
                )
            )
        )
        refs = write_csv(
            root / "human.csv",
            [
                dict(word_id=1, word="ata", working_level=5, reference_kind="form_review"),
                dict(word_id=3, word="ață", working_level=1, reference_kind="form_review"),
            ],
        )
        models = write_csv(
            root / "model.csv",
            [
                dict(word_id=1, word="ata", status="scored", rarity_level=1),
                dict(word_id=4, word="otel", status="scored", rarity_level=2),
                dict(word_id=5, word="oțel", status="failed", rarity_level=""),
            ],
        )
        references = write_csv(
            root / "references.csv", [dict(source_id="human", path=str(refs), sha256=sha(refs))]
        )
        observations = write_csv(
            root / "observations.csv",
            [dict(source_id="gpt_original", path=str(models), sha256=sha(models))],
        )
        return inventory, baseline, references, observations

    def test_human_priority_propagates_only_exact_form_and_models_remain_diagnostics(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            with (
                patch("subprocess.Popen", side_effect=AssertionError("LLM forbidden")),
                patch(
                    "requests.adapters.HTTPAdapter.send",
                    side_effect=AssertionError("Network forbidden"),
                ),
                patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
            ):
                summary = export_conservative_inventory(*args, root / "out")
            rows = read(root / "out/candidate.csv")
            self.assertEqual([r["final_level"] for r in rows], ["5", "5", "1", "4", "4"])
            self.assertEqual(
                [r["status"] for r in rows], ["human_reviewed"] * 3 + ["provisional_baseline"] * 2
            )
            self.assertEqual(rows[0]["provenance_id"], rows[1]["provenance_id"])
            self.assertNotEqual(rows[1]["provenance_id"], rows[2]["provenance_id"])
            self.assertEqual(
                (
                    summary["inventory_rows"],
                    summary["human_forms"],
                    summary["human_rows"],
                    summary["baseline_rows"],
                ),
                (5, 2, 3, 2),
            )
            conflicts = read(root / "out/conflicts.csv")
            self.assertEqual(len(conflicts), 4)
            self.assertEqual(
                {r["kind"] for r in conflicts}, {"baseline_vs_human", "model_vs_candidate"}
            )
            observations = read(root / "out/observations.csv")
            self.assertEqual(len(observations), 3)
            self.assertEqual(observations[-1]["level"], "")
            self.assertEqual(observations[-1]["status"], "failed")
            provenance = read(root / "out/provenance.csv")
            self.assertEqual(json.loads(provenance[0]["inventory_ids_json"]), [1, 2])
            self.assertEqual(json.loads(provenance[0]["human_reference_keys_json"]), ["human:1"])
            with self.assertRaises(FileExistsError):
                export_conservative_inventory(*args, root / "out")

    def test_conflicting_human_sources_are_not_averaged_or_silently_prioritized(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            other = write_csv(
                root / "other.csv",
                [dict(word_id=2, word="ata", working_level=4, reference_kind="another_review")],
            )
            write_csv(
                args[2],
                [*read(args[2]), dict(source_id="other", path=str(other), sha256=sha(other))],
            )
            with self.assertRaisesRegex(ValueError, "Conflicting human"):
                export_conservative_inventory(*args, root / "out")
            self.assertFalse((root / "out").exists())

    def test_source_and_inventory_defects_fail_without_partial_export(self):
        for defect in (
            "wrong_reference_spelling",
            "unknown_reference_id",
            "invalid_level",
            "source_hash",
            "missing_baseline_id",
            "different_pos_scores",
            "baseline_spelling",
            "duplicate_source",
            "failed_model_score",
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as temp:
                root = Path(temp)
                args = self.inputs(root)
                if defect.startswith("wrong_reference") or defect in (
                    "unknown_reference_id",
                    "invalid_level",
                    "source_hash",
                ):
                    source = root / "human.csv"
                    rows = read(source)
                    if defect == "wrong_reference_spelling":
                        rows[0]["word"] = "ață"
                    elif defect == "unknown_reference_id":
                        rows[0]["word_id"] = "99"
                    else:
                        rows[0]["working_level"] = "0"
                    write_csv(source, rows)
                    if defect != "source_hash":
                        catalog = read(args[2])
                        catalog[0]["sha256"] = sha(source)
                        write_csv(args[2], catalog)
                elif defect in ("missing_baseline_id", "different_pos_scores", "baseline_spelling"):
                    source = root / "baseline/scores.csv"
                    rows = read(source)
                    if defect == "missing_baseline_id":
                        rows = rows[:-1]
                    elif defect == "different_pos_scores":
                        rows[1]["rarity_level"] = "3"
                    else:
                        rows[0]["word"] = "ață"
                    write_csv(source, rows)
                    manifest = json.loads((root / "baseline/manifest.json").read_text())
                    manifest["artifacts"]["scores.csv"] = sha(source)
                    (root / "baseline/manifest.json").write_text(json.dumps(manifest))
                elif defect == "duplicate_source":
                    rows = read(args[2])
                    write_csv(args[2], rows + rows)
                else:
                    source = root / "model.csv"
                    rows = read(source)
                    rows[-1]["rarity_level"] = "1"
                    write_csv(source, rows)
                    catalog = read(args[3])
                    catalog[0]["sha256"] = sha(source)
                    write_csv(args[3], catalog)
                with self.assertRaises(ValueError):
                    export_conservative_inventory(*args, root / "out")
                self.assertFalse((root / "out").exists())

    def test_equal_human_rating_is_still_reviewed_and_replay_preserves_originals(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            source = root / "human.csv"
            rows = read(source)
            rows.append(dict(word_id=5, word="oțel", working_level=4, reference_kind="form_review"))
            write_csv(source, rows)
            catalog = read(args[2])
            catalog[0]["sha256"] = sha(source)
            write_csv(args[2], catalog)
            original = {p: sha(p) for p in root.rglob("*") if p.is_file()}
            export_conservative_inventory(*args, root / "out")
            export_conservative_inventory(*args, root / "replay")
            self.assertEqual(read(root / "out/candidate.csv")[-1]["status"], "human_reviewed")
            for path in (root / "out").iterdir():
                self.assertEqual(path.read_bytes(), (root / "replay" / path.name).read_bytes())
            self.assertTrue(all(sha(p) == digest for p, digest in original.items()))
