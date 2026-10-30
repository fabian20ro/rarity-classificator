"""Merge existing curated exact-form senses without their ratings or examples."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.exact_form import prepare_exact_forms
from classificator.evaluation.judge_evidence import merge_judge_evidence
from tests.test_exact_form import write_csv
from tests.test_local_evidence import read


class JudgeEvidenceTests(unittest.TestCase):
    def test_preserves_existing_senses_and_adds_every_curated_pos_without_scores(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            vocabulary = write_csv(
                root / "vocabulary.csv", [dict(word_id=1, word="literare", type="N")]
            )
            loc = root / "loc.txt"
            loc.write_text("literareF 113\n")
            contexts = write_csv(
                root / "contexts.csv",
                [
                    dict(
                        word_id=1,
                        word="literare",
                        context_id="literary",
                        pos="adjectiv plural",
                        meaning="Care ține de literatură.",
                        example="opere literare",
                        source="dictionary witness",
                    )
                ],
            )
            prepare_exact_forms(vocabulary, loc, contexts, root / "contract")
            evidence = write_csv(
                root / "evidence.csv",
                [
                    dict(
                        word_id=1,
                        word="literare",
                        evidence_json=json.dumps(
                            dict(
                                coverage="source_bounded_not_exhaustive",
                                valid_pos=["substantiv feminin"],
                                senses=[
                                    dict(
                                        pos="substantiv feminin",
                                        definition="Comunicarea literelor.",
                                        number_restriction="",
                                        grammar=[],
                                        context=[],
                                        context_incomplete=False,
                                        usage_labels=[],
                                    )
                                ],
                            )
                        ),
                    )
                ],
            )
            result = merge_judge_evidence(evidence, root / "contract", root / "out")
            value = json.loads(read(root / "out/evidence.csv")[0]["evidence_json"])
            self.assertEqual(value["valid_pos"], ["adjectiv plural", "substantiv feminin"])
            self.assertEqual(
                [r["definition"] for r in value["senses"]],
                ["Comunicarea literelor.", "Care ține de literatură."],
            )
            self.assertEqual(value["senses"][1]["context"], [])
            self.assertNotIn("opere literare", json.dumps(value))
            self.assertEqual(result["curated_contexts"], 1)
            self.assertEqual(read(root / "out/provenance.csv")[0]["context_id"], "literary")

    def test_rejects_changed_sources_and_hidden_labels_before_export(self):
        for corruption in ("source_hash", "artifact_hash", "extra_label", "spelling"):
            with self.subTest(corruption=corruption), TemporaryDirectory() as temp:
                root = Path(temp)
                vocabulary = write_csv(root / "v.csv", [dict(word_id=1, word="ata", type="N")])
                loc = root / "loc.txt"
                loc.write_text("ataF 113\n")
                contexts = write_csv(
                    root / "c.csv",
                    [
                        dict(
                            word_id=1,
                            word="ata",
                            context_id="c1",
                            pos="substantiv feminin",
                            meaning="Atu.",
                            example="exemplu ilustrativ",
                            source="martor",
                        )
                    ],
                )
                prepare_exact_forms(vocabulary, loc, contexts, root / "contract")
                evidence = write_csv(
                    root / "e.csv",
                    [
                        dict(
                            word_id=1,
                            word="ata",
                            evidence_json=json.dumps(
                                dict(
                                    coverage="source_bounded_not_exhaustive",
                                    valid_pos=["substantiv feminin"],
                                    senses=[],
                                )
                            ),
                        )
                    ],
                )
                if corruption == "source_hash":
                    contexts.write_text(contexts.read_text() + "\n")
                else:
                    rows = read(root / "contract/forms.csv")
                    if corruption == "extra_label":
                        value = json.loads(rows[0]["contexts"])
                        value[0]["human_level"] = 5
                        rows[0]["contexts"] = json.dumps(value)
                    else:
                        rows[0]["word"] = "ață"
                    write_csv(root / "contract/forms.csv", rows)
                    if corruption != "artifact_hash":
                        from hashlib import sha256

                        manifest_path = root / "contract/manifest.json"
                        manifest = json.loads(manifest_path.read_text())
                        manifest["artifacts"]["forms.csv"] = sha256(
                            (root / "contract/forms.csv").read_bytes()
                        ).hexdigest()
                        manifest_path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    merge_judge_evidence(evidence, root / "contract", root / "out")
                self.assertFalse((root / "out").exists())

    def test_audited_projection_removes_review_prose_and_pins_original(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            vocabulary = write_csv(root / "v.csv", [dict(word_id=1, word="tău", type="N")])
            loc = root / "loc.txt"
            loc.write_text("tăuF 113\n")
            original = "Denumire regională pentru noroi; bălțile și lacurile sunt deja evaluate."
            contexts = write_csv(
                root / "c.csv",
                [
                    dict(
                        word_id=1,
                        word="tău",
                        context_id="mud",
                        pos="substantiv regional",
                        meaning=original,
                        example="exemplu",
                        source="martor",
                    )
                ],
            )
            prepare_exact_forms(vocabulary, loc, contexts, root / "contract")
            evidence = write_csv(
                root / "e.csv",
                [
                    dict(
                        word_id=1,
                        word="tău",
                        evidence_json=json.dumps(
                            dict(
                                coverage="source_bounded_not_exhaustive",
                                valid_pos=["substantiv"],
                                senses=[],
                            )
                        ),
                    )
                ],
            )
            projection_row = dict(
                word_id=1,
                word="tău",
                context_id="mud",
                pos="substantiv regional",
                original_meaning=original,
                definition="Denumire regională pentru noroi.",
            )
            projection = write_csv(root / "projection.csv", [projection_row])
            result = merge_judge_evidence(
                evidence, root / "contract", root / "out", projection_csv=projection
            )
            self.assertEqual(result["projected_contexts_changed"], 1)
            payload = json.loads(read(root / "out/evidence.csv")[0]["evidence_json"])
            self.assertEqual(payload["senses"][0]["definition"], "Denumire regională pentru noroi.")
            self.assertNotIn("evaluate", json.dumps(payload))
            self.assertEqual(read(root / "out/provenance.csv")[0]["original_meaning"], original)
            for mutation in ("missing", "duplicate", "identity", "meaning", "pos", "label"):
                with self.subTest(mutation=mutation):
                    rows = [projection_row.copy()]
                    if mutation == "missing":
                        rows[0]["context_id"] = "absent"
                    elif mutation == "duplicate":
                        rows.append(rows[0].copy())
                    elif mutation == "identity":
                        rows[0]["word"] = "tau"
                    elif mutation == "meaning":
                        rows[0]["original_meaning"] = "different"
                    elif mutation == "pos":
                        rows[0]["pos"] = "verb"
                    else:
                        rows[0]["human_level"] = 5
                    write_csv(projection, rows)
                    with self.assertRaises(ValueError):
                        merge_judge_evidence(
                            evidence, root / "contract", root / "bad", projection_csv=projection
                        )
                    self.assertFalse((root / "bad").exists())
