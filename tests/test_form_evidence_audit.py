"""Public CSV audit: preserve identities and expose lexical coverage gaps."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.form_evidence_audit import audit_form_evidence
from classificator.evaluation.exact_form import CONTEXT_FIELDS, prepare_exact_forms
from classificator.evaluation.local_evidence import export_local_evidence
from tests.test_exact_form import write_csv
from tests import test_local_evidence as fixtures
from tests.test_local_evidence import body, heading, meaning, read
from tests.test_local_mentions import write_metadata


class FormEvidenceAuditTests(unittest.TestCase):
    def inputs(self, root, html=None, no_sources=False):
        vocabulary, loc, sources, mentions = fixtures.LocalEvidenceTests().inputs(
            root,
            html or heading("izotop", "adjectiv") + body(meaning("10", "Cu același număr atomic.")),
            loc="izotopA 1\nizotopN 1\n",
        )
        inventory = write_csv(
            root / "inventory.csv",
            [
                dict(word_id=1, word="izotop", type="A"),
                dict(word_id=2, word="izotop", type="N"),
            ],
        )
        write_csv(
            mentions, [dict(word_id=i, word="izotop", other_definition_count=3) for i in (1, 2)]
        )
        write_metadata(inventory, mentions)
        if no_sources:
            sources.write_text("word,path,sha256,format\n")
        export_local_evidence(inventory, loc, sources, mentions, root / "lexical")
        contexts = root / "empty-contexts.csv"
        contexts.write_text(",".join(sorted(CONTEXT_FIELDS)) + "\n")
        prepare_exact_forms(vocabulary, loc, contexts, root / "contract")
        forms = write_csv(
            root / "forms.csv",
            [
                dict(
                    form_id=1,
                    word="izotop",
                    group="family1",
                    inventory_ids_json="[1, 2]",
                    inventory_types_json='["A", "N"]',
                    loc_pos_json='["A", "N"]',
                    selection_slice="general",
                    selection_reason="fixture",
                )
            ],
        )
        return forms, inventory, root / "lexical", root / "contract"

    def test_preserves_all_inventory_ids_and_reports_missing_pos_without_claiming_completeness(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            result = audit_form_evidence(*self.inputs(root), root / "audit")
            self.assertEqual((result["forms"], result["inventory_rows"]), (1, 2))
            row = read(root / "audit/form-evidence-audit.csv")[0]
            self.assertEqual(row["missing_pos"], "N")
            self.assertEqual(row["aligned_pos"], "A")
            self.assertEqual(row["coverage"], "partial_pos")
            self.assertEqual(
                [r["word_id"] for r in read(root / "audit/membership.csv")], ["1", "2"]
            )
            context = read(root / "audit/contexts.csv")[0]
            self.assertEqual(context["context_status"], "usable_source_bounded")
            self.assertEqual(context["definition"], "Cu același număr atomic.")
            self.assertEqual(context["pos"], "A")
            self.assertTrue(context["source_sha256"])

    def test_absent_sources_preserve_forms_and_mark_unknown_not_obscure(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            audit_form_evidence(*self.inputs(root, no_sources=True), root / "audit")
            row = read(root / "audit/form-evidence-audit.csv")[0]
            self.assertEqual(row["coverage"], "no_source")
            self.assertEqual(row["missing_pos"], "A|N")
            self.assertEqual(read(root / "audit/contexts.csv"), [])
            self.assertNotIn("score", row)

    def test_rejects_lost_ids_wrong_spelling_pos_or_duplicate_forms_before_export(self):
        for change in (
            {"inventory_ids_json": "[1]"},
            {"inventory_ids_json": "[1, 1, 2]"},
            {"word": "izotóp"},
            {"inventory_types_json": '["A"]'},
            {"loc_pos_json": '["A"]'},
            {"form_id": "3"},
            {"inventory_ids_json": "[true, 2]"},
            {"duplicate": True},
        ):
            with self.subTest(change=change), TemporaryDirectory() as temp:
                root = Path(temp)
                args = self.inputs(root)
                rows = read(args[0])
                if change.get("duplicate"):
                    rows.append(dict(rows[0]))
                else:
                    rows[0].update(change)
                write_csv(args[0], rows)
                with self.assertRaises(ValueError):
                    audit_form_evidence(*args, root / "audit")
                self.assertFalse((root / "audit").exists())

    def test_rejects_changed_artifacts_sources_or_contract_inputs_before_export(self):
        for name in ("lexical/senses.csv", "contract/forms.csv", "source.html", "loc.txt"):
            with self.subTest(name=name), TemporaryDirectory() as temp:
                root = Path(temp)
                args = self.inputs(root)
                with (root / name).open("a") as stream:
                    stream.write("\n")
                with self.assertRaisesRegex(ValueError, "hash"):
                    audit_form_evidence(*args, root / "audit")
                self.assertFalse((root / "audit").exists())

    def test_context_parents_are_scoped_to_source_heading_and_pos(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            html = (
                heading("izotop", "adjectiv")
                + body(
                    meaning(
                        "10",
                        "Proprietate atomică.",
                        children="<ul>" + meaning("11", "Acest sens adjectival.") + "</ul>",
                    )
                )
                + heading("izotop", "substantiv neutru")
                + body(
                    meaning(
                        "10",
                        "Specie atomică.",
                        children="<ul>" + meaning("12", "Acest sens nominal.") + "</ul>",
                    )
                )
            )
            audit_form_evidence(*self.inputs(root, html), root / "audit")
            contexts = read(root / "audit/contexts.csv")
            noun = next(c for c in contexts if c["sense_id"] == "meaning12")
            self.assertEqual(noun["context_text"], "Specie atomică. — Acest sens nominal.")
            self.assertNotIn("adjectival", noun["context_text"])
            self.assertEqual(noun["context_status"], "usable_source_bounded")

    def test_incomplete_parent_does_not_count_as_usable_pos_coverage(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            # Parent without a definition is absent from the lexical CSV; its child remains.
            parent = (
                '<li class="type-meaning"><div id="meaning10" class="meaningContainer">'
                "</div><ul>" + meaning("11", "Sens dependent.") + "</ul></li>"
            )
            html = heading("izotop", "adjectiv") + body(parent)
            audit_form_evidence(*self.inputs(root, html), root / "audit")
            row = read(root / "audit/form-evidence-audit.csv")[0]
            self.assertEqual(row["usable_pos"], "")
            self.assertEqual(row["coverage"], "no_usable_contexts")
            context = read(root / "audit/contexts.csv")[0]
            self.assertEqual(context["context_status"], "incomplete_parent")
            self.assertEqual(context["context_text"], "")

    def test_rejects_incomplete_lexical_membership_even_with_matching_artifact_hash(self):
        import hashlib

        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            path = root / "lexical/evidence.csv"
            write_csv(path, read(path)[:1])
            manifest_path = root / "lexical/manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["artifacts"]["evidence.csv"] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "membership"):
                audit_form_evidence(*args, root / "audit")
            self.assertFalse((root / "audit").exists())

    def test_rejects_noncanonical_ids_and_malformed_pos_lists(self):
        for change in (
            {"form_id": "01"},
            {"loc_pos_json": '[{"pos": "A"}]'},
            {"inventory_types_json": "[null]"},
            {"loc_pos_json": '["A", "A", "N"]'},
        ):
            with self.subTest(change=change), TemporaryDirectory() as temp:
                root = Path(temp)
                args = self.inputs(root)
                rows = read(args[0])
                rows[0].update(change)
                write_csv(args[0], rows)
                with self.assertRaises(ValueError):
                    audit_form_evidence(*args, root / "audit")
                self.assertFalse((root / "audit").exists())

    def test_replay_is_identical_and_existing_outputs_are_never_overwritten(self):
        from unittest.mock import patch

        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            with patch("socket.create_connection", side_effect=AssertionError("network forbidden")):
                audit_form_evidence(*args, root / "first")
                audit_form_evidence(*args, root / "second")
            for name in (
                "contexts.csv",
                "membership.csv",
                "form-evidence-audit.csv",
                "summary.json",
                "manifest.json",
            ):
                self.assertEqual(
                    (root / "first" / name).read_bytes(), (root / "second" / name).read_bytes()
                )
            with self.assertRaises(FileExistsError):
                audit_form_evidence(*args, root / "first")

    def test_rejects_missing_provenance_or_unsupported_lexical_revision(self):
        for directory, field, value in (
            ("lexical", "inputs", None),
            ("contract", "inputs", None),
            ("lexical", "implementation", {}),
            ("lexical", "extraction_revision", "old"),
            ("lexical", "senses_schema", 1),
        ):
            with self.subTest(directory=directory, field=field), TemporaryDirectory() as temp:
                root = Path(temp)
                args = self.inputs(root)
                path = root / directory / "manifest.json"
                manifest = json.loads(path.read_text())
                if value is None:
                    del manifest[field]
                else:
                    manifest[field] = value
                path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    audit_form_evidence(*args, root / "audit")
                self.assertFalse((root / "audit").exists())
