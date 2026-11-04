"""Provenance checks exercised through the confirmed local-evidence CSV boundary."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.local_evidence import export_local_evidence
from classificator.evaluation.definition_frequency import POLICY as CORPUS_POLICY
from tests.test_exact_form import write_csv
from tests import test_local_evidence as fixtures
from tests.test_local_evidence import body, heading, meaning, read


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_metadata(vocabulary, mentions):
    root = mentions.parent
    ledger = write_csv(
        root / "source-ledger.csv",
        [dict(file="page.json", sha256="a" * 64, disposition="used")],
    )
    corpus = root / "corpus-manifest.json"
    corpus.write_text(
        json.dumps(
            dict(policy=CORPUS_POLICY, artifacts={"source-files.csv": digest(ledger)})
        )
    )
    extractor = root / "mention-extractor.py"
    extractor.write_text("# frozen test extractor\n")
    derivation = write_csv(
        root / "derivation.csv",
        [
            dict(
                word_id=row["word_id"],
                word=row["word"],
                rebus_other_definition_count=row["other_definition_count"],
            )
            for row in read(mentions)
        ],
    )
    metadata = dict(
        schema=1,
        policy="exact-form-outside-own-page-definitions-v1",
        vocabulary_sha256=digest(vocabulary),
        mentions_sha256=digest(mentions),
        **{
            name: dict(path=path.name, sha256=digest(path))
            for name, path in (
                ("corpus_manifest", corpus),
                ("source_ledger", ledger),
                ("extractor", extractor),
                ("derivation", derivation),
            )
        },
    )
    sidecar = mentions.with_suffix(mentions.suffix + ".metadata.json")
    sidecar.write_text(json.dumps(metadata))
    return sidecar, metadata


class LocalMentionProvenanceTests(unittest.TestCase):
    def inputs(self, root):
        return fixtures.LocalEvidenceTests().inputs(
            root,
            heading("izotop", "adjectiv") + body(meaning("1", "Sens.")),
            loc="izotop A1\n",
        )

    def test_unprovenanced_mention_counts_are_rejected_before_publication(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = self.inputs(root)
            sidecar = inputs[3].with_suffix(inputs[3].suffix + ".metadata.json")
            if sidecar.exists():
                sidecar.unlink()
            with self.assertRaisesRegex(ValueError, "metadata|sidecar|provenance"):
                export_local_evidence(*inputs, root / "out")
            self.assertFalse((root / "out").exists())

    def test_verified_lineage_is_pinned_with_derived_counts(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = self.inputs(root)
            sidecar, metadata = write_metadata(inputs[0], inputs[3])
            export_local_evidence(*inputs, root / "out")
            row = read(root / "out/evidence.csv")[0]
            self.assertEqual(row["other_definition_count"], "3")
            manifest = json.loads((root / "out/manifest.json").read_text())
            for path in [
                sidecar,
                *(
                    root / metadata[name]["path"]
                    for name in (
                        "corpus_manifest",
                        "source_ledger",
                        "extractor",
                        "derivation",
                    )
                ),
            ]:
                self.assertEqual(manifest["inputs"][str(path.resolve())], digest(path))

    def test_metadata_and_referenced_hashes_are_validated_before_publication(self):
        for field, value in [
            ("schema", 2),
            ("schema", True),
            ("policy", "arbitrary-token-counts"),
            ("vocabulary_sha256", "0" * 64),
            ("mentions_sha256", "0" * 64),
            ("assistant_estimate", 5),
            ("extractor", {"path": "mention-extractor.py", "sha256": "0" * 64}),
            ("source_ledger", {"path": "source-ledger.csv", "sha256": "0" * 64}),
            ("derivation", {"path": "derivation.csv", "sha256": "0" * 64}),
            ("corpus_manifest", {"path": "corpus-manifest.json", "sha256": "0" * 64}),
        ]:
            with self.subTest(field=field, value=value), TemporaryDirectory() as temp:
                root = Path(temp)
                inputs = self.inputs(root)
                sidecar, metadata = write_metadata(inputs[0], inputs[3])
                metadata[field] = value
                sidecar.write_text(json.dumps(metadata))
                with self.assertRaises(ValueError):
                    export_local_evidence(*inputs, root / "out")
                self.assertFalse((root / "out").exists())

    def test_rehashed_sources_still_require_corpus_policy_ledger_and_exact_derivation(
        self,
    ):
        cases = [
            "corpus_policy",
            "corpus_ledger",
            "derivation_word",
            "derivation_count",
            "derivation_missing",
            "derivation_duplicate",
        ]
        for case in cases:
            with self.subTest(case=case), TemporaryDirectory() as temp:
                root = Path(temp)
                inputs = self.inputs(root)
                sidecar, metadata = write_metadata(inputs[0], inputs[3])
                name = "corpus_manifest" if case.startswith("corpus") else "derivation"
                path = root / metadata[name]["path"]
                if case.startswith("corpus"):
                    value = json.loads(path.read_text())
                    if case == "corpus_policy":
                        value["policy"] = "whole-html-including-menus"
                    else:
                        value["artifacts"]["source-files.csv"] = "0" * 64
                    path.write_text(json.dumps(value))
                else:
                    rows = read(path)
                    if case == "derivation_word":
                        rows[0]["word"] = "izotóp"
                    elif case == "derivation_count":
                        rows[0]["rebus_other_definition_count"] = 999
                    elif case == "derivation_missing":
                        rows[0]["word_id"] = 99
                    else:
                        rows.append(dict(rows[0]))
                    write_csv(path, rows)
                metadata[name]["sha256"] = digest(path)
                sidecar.write_text(json.dumps(metadata))
                with self.assertRaises(ValueError):
                    export_local_evidence(*inputs, root / "out")
                self.assertFalse((root / "out").exists())

    def test_derivation_may_cover_larger_inventory_but_selected_rows_match_exactly(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = self.inputs(root)
            sidecar, metadata = write_metadata(inputs[0], inputs[3])
            path = root / metadata["derivation"]["path"]
            rows = read(path)
            rows.append(dict(word_id=2, word="extra", rebus_other_definition_count=17))
            write_csv(path, rows)
            metadata["derivation"]["sha256"] = digest(path)
            sidecar.write_text(json.dumps(metadata))
            export_local_evidence(*inputs, root / "out")
            self.assertEqual(
                read(root / "out/evidence.csv")[0]["other_definition_count"], "3"
            )
