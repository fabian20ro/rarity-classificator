"""Public audited CSV → blinded lexical CSV boundary."""

import json
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.audit_judge_evidence import export_audit_judge_evidence
from classificator.evaluation.form_evidence_audit import audit_form_evidence
from tests import test_form_evidence_audit as fixtures
from tests.test_exact_form import write_csv
from tests.test_local_evidence import body, heading, meaning, read


class AuditJudgeEvidenceTests(unittest.TestCase):
    def inputs(self, root, **kwargs):
        args = fixtures.FormEvidenceAuditTests().inputs(root, **kwargs)
        audit_form_evidence(*args, root / "audit")
        vocabulary = write_csv(
            root / "judge-vocabulary.csv", [dict(word_id=1, word="izotop", type="A")]
        )
        return args[0], vocabulary, root / "audit"

    def test_projects_all_pos_and_usable_senses_with_separate_provenance(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            result = export_audit_judge_evidence(*args, root / "output")
            self.assertEqual((result["forms"], result["inventory_rows"]), (1, 2))
            row = read(root / "output/evidence.csv")[0]
            self.assertEqual((row["word_id"], row["word"]), ("1", "izotop"))
            evidence = json.loads(row["evidence_json"])
            self.assertEqual(evidence["valid_pos"], ["adjectiv", "substantiv neutru"])
            self.assertEqual(evidence["coverage"], "source_bounded_not_exhaustive")
            self.assertEqual(evidence["senses"][0]["definition"], "Cu același număr atomic.")
            self.assertFalse(evidence["senses"][0]["context_incomplete"])
            self.assertNotIn("source_path", row["evidence_json"])
            self.assertNotIn("level", row["evidence_json"])
            provenance = read(root / "output/provenance.csv")[0]
            self.assertEqual(provenance["sense_id"], "meaning10")
            self.assertTrue(provenance["source_sha256"])
            with self.assertRaises(FileExistsError):
                export_audit_judge_evidence(*args, root / "output")

    def test_rejects_identity_membership_and_source_drift_even_with_rehashed_artifacts(self):
        cases = [
            ("judge-vocabulary.csv", "word", "izotóp"),
            ("judge-vocabulary.csv", "type", "V"),
            ("audit/membership.csv", "word_id", "9"),
            ("audit/contexts.csv", "word", "izotóp"),
            ("audit/contexts.csv", "source_sha256", "0" * 64),
            ("audit/form-evidence-audit.csv", "usable_contexts", "9"),
            ("forms.csv", "inventory_ids_json", "[1]"),
            ("forms.csv", "word", "izotóp"),
            ("forms.csv", "form_id", "01"),
            ("forms.csv", "duplicate", ""),
        ]
        for filename, field, value in cases:
            with self.subTest(filename=filename, field=field), TemporaryDirectory() as temp:
                root = Path(temp)
                args = self.inputs(root)
                path = root / filename
                rows = read(path)
                if field == "duplicate":
                    rows.append(dict(rows[0]))
                else:
                    rows[0][field] = value
                write_csv(path, rows)
                manifest_path = root / "audit/manifest.json"
                manifest = json.loads(manifest_path.read_text())
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if filename.startswith("audit/"):
                    manifest["artifacts"][path.name] = digest
                if str(path.resolve()) in manifest["inputs"]:
                    manifest["inputs"][str(path.resolve())] = digest
                manifest_path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    export_audit_judge_evidence(*args, root / "output")
                self.assertFalse((root / "output").exists())

    def test_parent_context_and_qualifiers_keep_the_pilot_representation(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            html = heading("izotop", "adjectiv") + body(
                meaning(
                    "10",
                    "Sens restrâns.",
                    "regional; singular",
                    "<ul>" + meaning("11", "Sens derivat.") + "</ul>",
                )
                + meaning("12", "Sens curent.")
            )
            export_audit_judge_evidence(*self.inputs(root, html=html), root / "output")
            senses = json.loads(read(root / "output/evidence.csv")[0]["evidence_json"])["senses"]
            derived = next(s for s in senses if s["definition"] == "Sens derivat.")
            self.assertEqual(derived["context"], ["Sens restrâns."])
            self.assertEqual(derived["pos"], "adjectiv")
            self.assertEqual(derived["number_restriction"], "singular")
            self.assertEqual(derived["grammar"], ["singular"])
            self.assertEqual(derived["usage_labels"], ["regional; singular"])
            current = next(s for s in senses if s["definition"] == "Sens curent.")
            self.assertEqual(
                (current["usage_labels"], current["context"], current["number_restriction"]),
                ([], [], ""),
            )

    def test_missing_senses_are_explicit_and_replay_preserves_every_artifact(self):
        from unittest.mock import patch

        for no_sources in (True, False):
            with self.subTest(no_sources=no_sources), TemporaryDirectory() as temp:
                root = Path(temp)
                parent = (
                    '<li class="type-meaning"><div id="meaning10" class="meaningContainer"></div><ul>'
                    + meaning("11", "Sens dependent.")
                    + "</ul></li>"
                )
                args = self.inputs(
                    root, no_sources=no_sources, html=heading("izotop", "adjectiv") + body(parent)
                )
                with (
                    patch("socket.socket", side_effect=AssertionError("Network forbidden")),
                    patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
                ):
                    result = export_audit_judge_evidence(*args, root / "output")
                    export_audit_judge_evidence(*args, root / "replay")
                self.assertEqual((result["with_senses"], result["without_senses"]), (0, 1))
                value = json.loads(read(root / "output/evidence.csv")[0]["evidence_json"])
                self.assertEqual(value["senses"], [])
                self.assertEqual(value["valid_pos"], ["adjectiv", "substantiv neutru"])
                self.assertEqual(read(root / "output/provenance.csv"), [])
                for path in (root / "output").iterdir():
                    self.assertEqual(path.read_bytes(), (root / "replay" / path.name).read_bytes())

    def test_refuses_missing_implementation_provenance(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            path = root / "audit/manifest.json"
            manifest = json.loads(path.read_text())
            del manifest["implementation"]
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "provenance"):
                export_audit_judge_evidence(*args, root / "output")
            self.assertFalse((root / "output").exists())
