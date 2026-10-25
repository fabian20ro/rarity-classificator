import csv
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.local_evidence import export_local_evidence
from tests.test_exact_form import write_csv


def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def heading(word, pos):
    return f'<h3 class="tree-heading"><div>{word}<span class="tree-pos-info">{pos}</span></div></h3>'


def meaning(sense_id, text, tags="", children=""):
    return (
        f'<li class="type-meaning"><div id="meaning{sense_id}" class="meaningContainer">'
        f'<span class="meaning-tags">{tags}</span><span class="tree-def">{text}</span>'
        f"</div>{children}</li>"
    )


def body(senses):
    return f'<div class="tree-body"><ul class="meaningTree">{senses}</ul></div>'


class LocalEvidenceTests(unittest.TestCase):
    def inputs(self, root, html, word="izotop", loc="izotop A1\nizotop N1\n"):
        vocabulary = write_csv(
            root / "vocabulary.csv", [dict(word_id=1, word=word, type="N")]
        )
        loc_file = root / "loc.txt"
        loc_file.write_text(loc)
        source = root / "source.html"
        source.write_text(html)
        sources = write_csv(
            root / "sources.csv",
            [
                dict(
                    word=word,
                    path=str(source),
                    sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    format="html",
                )
            ],
        )
        mentions = write_csv(
            root / "mentions.csv",
            [
                dict(
                    word_id=1,
                    word=word,
                    other_definition_count=3,
                )
            ],
        )
        return vocabulary, loc_file, sources, mentions

    def test_exports_exact_senses_for_every_pos_with_source_provenance(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            html = (
                heading("izotop", "adjectiv")
                + body(meaning("10", "Cu același număr atomic."))
                + heading("izotop", "substantiv neutru")
                + body(meaning("11", "Specie atomică."))
            )
            inputs = self.inputs(root, html)
            export_local_evidence(*inputs, root / "out")
            senses = read(root / "out/senses.csv")
            self.assertEqual(
                [(s["sense_id"], s["pos"], s["definition"]) for s in senses],
                [
                    ("meaning10", "A", "Cu același număr atomic."),
                    ("meaning11", "N", "Specie atomică."),
                ],
            )
            self.assertTrue(all(s["alignment"] == "exact" for s in senses))
            self.assertTrue(
                all(s["source_sha256"] == read(inputs[2])[0]["sha256"] for s in senses)
            )
            feature = read(root / "out/evidence.csv")[0]
            self.assertEqual(feature["loc_pos"], "A|N")
            self.assertEqual(feature["aligned_pos"], "A|N")
            self.assertEqual(feature["alignment"], "source_bounded")
            self.assertEqual(feature["other_definition_count"], "3")
            manifest = json.loads((root / "out/manifest.json").read_text())
            self.assertEqual(
                manifest["artifacts"]["evidence.csv"],
                hashlib.sha256((root / "out/evidence.csv").read_bytes()).hexdigest(),
            )

    def test_scopes_tags_to_senses_inherits_parent_and_keeps_unrestricted_alternative(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            child = "<ul>" + meaning("12", "Sens derivat.") + "</ul>"
            html = (
                '<nav><span class="meaning-tags">învechit</span></nav>'
                + heading("izotop", "adjectiv")
                + body(
                    meaning("10", "Sens restrâns.", "regional", child)
                    + meaning("13", "Sens curent.")
                )
                + heading("izotop", "substantiv neutru")
                + body(
                    meaning("11", "Sens specializat.", "chimie")
                    + '<li class="type-etymology"><div class="meaningContainer" id="bad">'
                    '<span class="meaning-tags">rar</span><span class="tree-def">Origine</span></div></li>'
                    + '<li class="type-example"><div class="meaningContainer" id="example">'
                    '<span class="tree-def">Exemplu</span></div></li>'
                )
            )
            inputs = self.inputs(root, html)
            export_local_evidence(*inputs, root / "out")
            senses = {s["sense_id"]: s for s in read(root / "out/senses.csv")}
            self.assertEqual(
                set(senses), {"meaning10", "meaning11", "meaning12", "meaning13"}
            )
            self.assertEqual(json.loads(senses["meaning12"]["tags"]), ["regional"])
            self.assertEqual(senses["meaning12"]["parent_sense_id"], "meaning10")
            self.assertEqual(json.loads(senses["meaning13"]["tags"]), [])
            feature = read(root / "out/evidence.csv")[0]
            self.assertEqual(feature["all_restricted"], "0")
            self.assertEqual(feature["all_specialist"], "0")
            # Every eligible meaning restricted: page menus still play no role.
            inputs = self.inputs(
                root,
                heading("izotop", "adjectiv")
                + body(meaning("10", "Sens rar.", "rar", child)),
                loc="izotop A1\n",
            )
            export_local_evidence(*inputs, root / "restricted")
            self.assertEqual(
                read(root / "restricted/evidence.csv")[0]["all_restricted"], "1"
            )

    def test_literal_inflections_multiple_heading_blocks_and_nonmatching_lemmas(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            html = (
                '<h3 class="tree-heading"><div>boraci<span class="tree-pos-info">substantiv neutru</span></div>'
                '<div>borac<span class="tree-inflected-form">, boraci</span>'
                '<span class="tree-pos-info">substantiv masculin</span></div></h3>'
                + body(meaning("1", "Vas.", "tehnică"))
            )
            inputs = self.inputs(root, html, word="boraci", loc="boraci N1\n")
            export_local_evidence(*inputs, root / "out")
            feature = read(root / "out/evidence.csv")[0]
            self.assertEqual(feature["alignment"], "source_bounded")
            self.assertEqual(feature["all_specialist"], "1")
            self.assertEqual(len(read(root / "out/senses.csv")), 2)
            self.assertTrue(
                all(r["alignment"] == "exact" for r in read(root / "out/senses.csv"))
            )
            for word, head in [
                ("micșurat", "micșorat"),
                ("ata", "ața"),
                ("cioare", "cioarec"),
            ]:
                with self.subTest(word=word):
                    inputs = self.inputs(
                        root,
                        heading(head, "adjectiv") + body(meaning("2", "Sens.", "rar")),
                        word=word,
                        loc=f"{word} A1\n",
                    )
                    export_local_evidence(*inputs, root / word)
                    row = read(root / word / "evidence.csv")[0]
                    self.assertEqual(row["alignment"], "unresolved")
                    self.assertEqual(row["aligned_senses"], "0")
                    self.assertEqual(row["all_restricted"], "0")
            inputs = self.inputs(
                root,
                heading(
                    'ci<span class="tonic-accent">o</span>arec'
                    '<span class="tree-inflected-form">, cioareci</span>',
                    "substantiv masculin",
                )
                + body(meaning("3", "Pantaloni.")),
                word="cioareci",
                loc="cioareci M1\n",
            )
            export_local_evidence(*inputs, root / "plural")
            self.assertEqual(
                read(root / "plural/evidence.csv")[0]["alignment"], "source_bounded"
            )

    def test_missing_pos_and_raw_only_pages_remain_unresolved(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = self.inputs(
                root, heading("izotop", "adjectiv") + body(meaning("1", "Sens."))
            )
            export_local_evidence(*inputs, root / "missing-pos")
            self.assertEqual(
                read(root / "missing-pos/evidence.csv")[0]["alignment"], "unresolved"
            )
            inputs = self.inputs(
                root,
                '<div class="defWrapper"><span class="def">izotop rar</span></div>',
            )
            export_local_evidence(*inputs, root / "raw")
            self.assertEqual(
                read(root / "raw/evidence.csv")[0]["alignment"], "unresolved"
            )

    def test_cache_json_hashes_identity_and_mentions_fail_fast_without_partial_outputs(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            html = heading("izotop", "adjectiv") + body(meaning("1", "Sens."))
            inputs = self.inputs(root, html, loc="izotop A1\n")
            cache = root / "cache.json"
            cache.write_text(
                json.dumps(dict(original="izotop", status="ok", html=html))
            )
            sources = [
                dict(
                    word="izotop",
                    path=str(cache),
                    format="cache_json",
                    sha256=hashlib.sha256(cache.read_bytes()).hexdigest(),
                )
            ]
            write_csv(inputs[2], sources)
            export_local_evidence(*inputs, root / "out")
            self.assertEqual(
                read(root / "out/evidence.csv")[0]["alignment"], "source_bounded"
            )
            with self.assertRaises(FileExistsError):
                export_local_evidence(*inputs, root / "out")
            cache.write_text(cache.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "hash"):
                export_local_evidence(*inputs, root / "bad-hash")
            self.assertFalse((root / "bad-hash").exists())
            sources[0]["sha256"] = hashlib.sha256(cache.read_bytes()).hexdigest()
            sources[0]["word"] = "alt"
            write_csv(inputs[2], sources)
            with self.assertRaisesRegex(ValueError, "source|Source"):
                export_local_evidence(*inputs, root / "bad-identity")
            sources[0]["word"] = "izotop"
            write_csv(inputs[2], sources)
            for changes in [
                dict(word="izotóp"),
                dict(other_definition_count="-1"),
                dict(other_definition_count="nan"),
                dict(human_level="5"),
            ]:
                row = dict(word_id=1, word="izotop", other_definition_count=3, **{})
                row.update(changes)
                write_csv(inputs[3], [row])
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    export_local_evidence(*inputs, root / "bad-mentions")
                self.assertFalse((root / "bad-mentions").exists())
            write_csv(
                inputs[3], [dict(word_id=2, word="izotop", other_definition_count=0)]
            )
            with self.assertRaises(ValueError):
                export_local_evidence(*inputs, root / "missing-mentions")

    def test_loc_gender_and_transitive_codes_do_not_hide_valid_pos_or_duplicate_ids(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = self.inputs(
                root,
                heading("clevetitor", "substantiv masculin")
                + body(meaning("1", "Persoană.")),
                word="clevetitor",
                loc="clevetit'or MF 1\n",
            )
            vocabulary = read(inputs[0])
            vocabulary.append(dict(word_id="2", word="clevetitor", type="A"))
            write_csv(inputs[0], vocabulary)
            write_csv(
                inputs[3],
                [
                    dict(word_id=i, word="clevetitor", other_definition_count=2)
                    for i in [1, 2]
                ],
            )
            export_local_evidence(*inputs, root / "out")
            rows = read(root / "out/evidence.csv")
            self.assertEqual([r["word_id"] for r in rows], ["1", "2"])
            self.assertTrue(
                all(
                    r["loc_pos"] == "N" and r["alignment"] == "source_bounded"
                    for r in rows
                )
            )
            inputs = self.inputs(
                root,
                heading("descoperi", "verb") + body(meaning("2", "A afla.")),
                word="descoperi",
                loc="descoper'i VT 1\n",
            )
            export_local_evidence(*inputs, root / "verb")
            self.assertEqual(read(root / "verb/evidence.csv")[0]["loc_pos"], "V")
            self.assertEqual(
                read(root / "verb/evidence.csv")[0]["alignment"], "source_bounded"
            )

    @unittest.skipUnless(
        importlib.util.find_spec("sklearn"), "Install evaluation extra"
    )
    def test_cli_exports_and_compares_without_network_or_database(self):
        from contextlib import redirect_stdout
        import io
        from unittest.mock import patch
        from classificator.cli import main

        with TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = self.inputs(
                root, heading("izotop", "adjectiv") + body(meaning("1", "Sens."))
            )
            vocab = [
                dict(word_id=i, word=w, type="N")
                for i, w in enumerate(["izotop", "rara", "comun"], 1)
            ]
            write_csv(inputs[0], vocab)
            write_csv(
                inputs[3],
                [
                    dict(word_id=r["word_id"], word=r["word"], other_definition_count=0)
                    for r in vocab
                ],
            )
            ref = write_csv(
                root / "ref.csv",
                [
                    dict(
                        word_id=r["word_id"],
                        word=r["word"],
                        working_level=4,
                        initial_level=4,
                        reference_kind="initial_opaque_form_pos",
                    )
                    for r in vocab
                ],
            )
            freq = write_csv(
                root / "freq.csv",
                [
                    dict(word_id=r["word_id"], word=r["word"], wordfreq="", rebus="")
                    for r in vocab
                ],
            )
            first = write_csv(
                root / "first.csv",
                [dict(word_id=r["word_id"], word=r["word"], level=4) for r in vocab],
            )
            groups = write_csv(
                root / "groups.csv",
                [
                    dict(word_id=r["word_id"], word=r["word"], group=str(r["word_id"]))
                    for r in vocab
                ],
            )
            with (
                patch(
                    "requests.sessions.Session.request",
                    side_effect=AssertionError("HTTP forbidden"),
                ),
                patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(
                    main(
                        [
                            "evaluation-local-evidence",
                            "--vocabulary-csv",
                            str(inputs[0]),
                            "--loc-file",
                            str(inputs[1]),
                            "--sources-csv",
                            str(inputs[2]),
                            "--mentions-csv",
                            str(inputs[3]),
                            "--campaign-dir",
                            str(root / "evidence"),
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    main(
                        [
                            "evaluation-local-fallback",
                            "--reference-csv",
                            str(ref),
                            "--features-csv",
                            str(freq),
                            "--evidence-dir",
                            str(root / "evidence"),
                            "--first-independent-csv",
                            str(first),
                            "--groups-csv",
                            str(groups),
                            "--campaign-dir",
                            str(root / "comparison"),
                        ]
                    ),
                    0,
                )
            self.assertEqual(
                len(read(root / "comparison/revised_working/predictions.csv")), 3
            )
