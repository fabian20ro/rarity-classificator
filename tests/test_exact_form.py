import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from classificator.evaluation.exact_form import prepare_exact_forms, load_form_contract


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


class ExactFormTests(unittest.TestCase):
    def test_freezes_all_loc_pos_and_curated_same_surface_contexts_without_gold(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            vocabulary = write_csv(
                root / "vocabulary.csv",
                [
                    dict(word_id=1, word="tău", type="N"),
                    dict(word_id=2, word="masa", type="V"),
                ],
            )
            loc = root / "words.txt"
            loc.write_text("t'ău N 52\nt'ău P 92\nmas'a V 1\nm'asă F 1\n")
            contexts = write_csv(
                root / "contexts.csv",
                [
                    dict(
                        word_id=2,
                        word="masa",
                        context_id="2:meal",
                        pos="substantiv feminin articulat",
                        meaning="Mobila sau mâncarea servită",
                        example="masa de prânz",
                        source="reviewed:dictionary",
                    )
                ],
            )
            result = prepare_exact_forms(vocabulary, loc, contexts, root / "output")
            forms = load_form_contract(result["forms"], {1: "tău", 2: "masa"})
            self.assertEqual([e["pos"] for e in forms[1]["loc_entries"]], ["N", "P"])
            self.assertEqual(forms[2]["word"], "masa")
            self.assertEqual(forms[2]["contexts"][0]["pos"], "substantiv feminin articulat")
            self.assertEqual(forms[2]["inventory_type"], "V")
            self.assertEqual(forms[2]["coverage"], "source_bounded_not_exhaustive")
            self.assertEqual(forms[1]["rubric"], "exact-form-most-familiar-valid-sense-v1")
            self.assertNotIn("level", json.dumps(forms))
            with self.assertRaises(FileExistsError):
                prepare_exact_forms(vocabulary, loc, contexts, root / "output")

    def test_contract_rejects_nested_labels_and_wrong_surface_before_scoring(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "forms.csv"
            valid = dict(
                word_id=1,
                word="micșurat",
                inventory_type="A",
                rubric="exact-form-most-familiar-valid-sense-v1",
                coverage="source_bounded_not_exhaustive",
                loc_entries=json.dumps(
                    [dict(pos="A", morphology="1", line=1, entry="micșurat A 1")]
                ),
                contexts=json.dumps(
                    [
                        dict(
                            context_id="1:reduced",
                            pos="adjectiv",
                            meaning="Redus",
                            example="un lucru micșurat",
                            source="dictionary",
                        )
                    ]
                ),
            )
            for field, value in [
                ("word", "micșorat"),
                ("loc_entries", "[]"),
                (
                    "contexts",
                    json.dumps(
                        [
                            dict(
                                context_id="1:reduced",
                                pos="adjectiv",
                                meaning="Redus",
                                example="un lucru micșurat",
                                source="dictionary",
                                level=5,
                            )
                        ]
                    ),
                ),
                ("contexts", "{}"),
            ]:
                with self.subTest(field=field, value=value):
                    write_csv(path, [dict(valid, **{field: value})])
                    with self.assertRaises(ValueError):
                        load_form_contract(path, {1: "micșurat"})

    def test_no_lemma_inflection_or_diacritic_substitution_in_loc_matching(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            loc = root / "loc.txt"
            loc.write_text("micșorat A 1\nsesiza V 1\nițari M 1\nața F 1\nșarpe M 1\n")
            contexts = root / "contexts.csv"
            contexts.write_text("word_id,word,context_id,pos,meaning,example,source\n")
            for word in ["micșurat", "sezisa", "ițar", "ata"]:
                with self.subTest(word=word):
                    vocab = write_csv(root / "words.csv", [dict(word_id=1, word=word, type="N")])
                    with self.assertRaisesRegex(ValueError, "No exact LOC entry"):
                        prepare_exact_forms(vocab, loc, contexts, root / "result")
                    self.assertFalse((root / "result").exists())
            vocab = write_csv(root / "words.csv", [dict(word_id=1, word="şarpe", type="N")])
            result = prepare_exact_forms(vocab, loc, contexts, root / "result")
            self.assertEqual(load_form_contract(result["forms"], {1: "şarpe"})[1]["word"], "şarpe")


if __name__ == "__main__":
    unittest.main()
