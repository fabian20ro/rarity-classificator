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
    return (
        f'<h3 class="tree-heading"><div>{word}<span class="tree-pos-info">{pos}</span></div></h3>'
    )


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
        vocabulary = write_csv(root / "vocabulary.csv", [dict(word_id=1, word=word, type="N")])
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
        from tests.test_local_mentions import write_metadata

        write_metadata(vocabulary, mentions)
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
            self.assertTrue(all(s["source_sha256"] == read(inputs[2])[0]["sha256"] for s in senses))
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
            self.assertEqual(set(senses), {"meaning10", "meaning11", "meaning12", "meaning13"})
            self.assertEqual(json.loads(senses["meaning12"]["tags"]), ["regional"])
            self.assertEqual(senses["meaning12"]["parent_sense_id"], "meaning10")
            self.assertEqual(json.loads(senses["meaning13"]["tags"]), [])
            feature = read(root / "out/evidence.csv")[0]
            self.assertEqual(feature["all_restricted"], "0")
            self.assertEqual(feature["all_specialist"], "0")
            # Every eligible meaning restricted: page menus still play no role.
            inputs = self.inputs(
                root,
                heading("izotop", "adjectiv") + body(meaning("10", "Sens rar.", "rar", child)),
                loc="izotop A1\n",
            )
            export_local_evidence(*inputs, root / "restricted")
            self.assertEqual(read(root / "restricted/evidence.csv")[0]["all_restricted"], "1")

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
            self.assertTrue(all(r["alignment"] == "exact" for r in read(root / "out/senses.csv")))
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
            self.assertEqual(read(root / "plural/evidence.csv")[0]["alignment"], "source_bounded")

    def test_missing_pos_and_raw_only_pages_remain_unresolved(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = self.inputs(root, heading("izotop", "adjectiv") + body(meaning("1", "Sens.")))
            export_local_evidence(*inputs, root / "missing-pos")
            self.assertEqual(read(root / "missing-pos/evidence.csv")[0]["alignment"], "unresolved")
            inputs = self.inputs(
                root,
                '<div class="defWrapper"><span class="def">izotop rar</span></div>',
            )
            export_local_evidence(*inputs, root / "raw")
            self.assertEqual(read(root / "raw/evidence.csv")[0]["alignment"], "unresolved")

    def test_cache_json_hashes_identity_and_mentions_fail_fast_without_partial_outputs(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            html = heading("izotop", "adjectiv") + body(meaning("1", "Sens."))
            inputs = self.inputs(root, html, loc="izotop A1\n")
            cache = root / "cache.json"
            cache.write_text(json.dumps(dict(original="izotop", status="ok", html=html)))
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
            self.assertEqual(read(root / "out/evidence.csv")[0]["alignment"], "source_bounded")
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
            write_csv(inputs[3], [dict(word_id=2, word="izotop", other_definition_count=0)])
            with self.assertRaises(ValueError):
                export_local_evidence(*inputs, root / "missing-mentions")

    def test_loc_gender_and_transitive_codes_do_not_hide_valid_pos_or_duplicate_ids(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = self.inputs(
                root,
                heading("clevetitor", "substantiv masculin") + body(meaning("1", "Persoană.")),
                word="clevetitor",
                loc="clevetit'or MF 1\n",
            )
            vocabulary = read(inputs[0])
            vocabulary.append(dict(word_id="2", word="clevetitor", type="A"))
            write_csv(inputs[0], vocabulary)
            write_csv(
                inputs[3],
                [dict(word_id=i, word="clevetitor", other_definition_count=2) for i in [1, 2]],
            )
            from tests.test_local_mentions import write_metadata

            write_metadata(inputs[0], inputs[3])
            export_local_evidence(*inputs, root / "out")
            rows = read(root / "out/evidence.csv")
            self.assertEqual([r["word_id"] for r in rows], ["1", "2"])
            self.assertTrue(
                all(r["loc_pos"] == "N" and r["alignment"] == "source_bounded" for r in rows)
            )
            inputs = self.inputs(
                root,
                heading("descoperi", "verb") + body(meaning("2", "A afla.")),
                word="descoperi",
                loc="descoper'i VT 1\n",
            )
            export_local_evidence(*inputs, root / "verb")
            self.assertEqual(read(root / "verb/evidence.csv")[0]["loc_pos"], "V")
            self.assertEqual(read(root / "verb/evidence.csv")[0]["alignment"], "source_bounded")

    @unittest.skipUnless(importlib.util.find_spec("sklearn"), "Install evaluation extra")
    def test_cli_exports_and_compares_without_network_or_database(self):
        from contextlib import redirect_stdout
        import io
        from unittest.mock import patch
        from classificator.cli import main

        with TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = self.inputs(root, heading("izotop", "adjectiv") + body(meaning("1", "Sens.")))
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
                [dict(word_id=r["word_id"], word=r["word"], wordfreq="", rebus="") for r in vocab],
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
            from tests.test_local_mentions import write_metadata

            write_metadata(inputs[0], inputs[3])
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
            self.assertEqual(len(read(root / "comparison/revised_working/predictions.csv")), 3)

    def test_number_restrictions_exclude_singular_but_allow_plural_and_child_override(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            html = heading(
                'ițar<span class="tree-inflected-form">, ițari</span>',
                "substantiv masculin",
            ) + body(
                meaning("1", "Pantaloni.", "(numai) plural") + meaning("2", "Dispozitiv de țesut.")
            )
            inputs = self.inputs(root, html, word="ițar", loc="ițar M1\n")
            export_local_evidence(*inputs, root / "singular")
            senses = {s["sense_id"]: s for s in read(root / "singular/senses.csv")}
            self.assertEqual(senses["meaning1"]["alignment"], "unresolved")
            self.assertEqual(senses["meaning2"]["alignment"], "exact")
            self.assertEqual(read(root / "singular/evidence.csv")[0]["aligned_senses"], "1")
            inputs = self.inputs(root, html, word="ițari", loc="ițari M1\n")
            export_local_evidence(*inputs, root / "plural-number")
            self.assertEqual(read(root / "plural-number/senses.csv")[0]["alignment"], "exact")
            html = heading(
                'briofită<span class="tree-inflected-form">, briofite</span>',
                "substantiv feminin",
            ) + body(
                meaning(
                    "3",
                    "Grupă de plante.",
                    "(la) plural",
                    "<ul>" + meaning("4", "O plantă din grupă.", "(la) singular") + "</ul>",
                )
                + meaning("5", "Sens neexclusiv.", "mai ales la plural")
            )
            inputs = self.inputs(root, html, word="briofită", loc="briofită F1\n")
            export_local_evidence(*inputs, root / "override")
            senses = {s["sense_id"]: s for s in read(root / "override/senses.csv")}
            self.assertEqual(
                [senses[f"meaning{i}"]["alignment"] for i in [3, 4, 5]],
                ["unresolved", "exact", "exact"],
            )
            html = heading(
                'abietacee<span class="tree-inflected-form">, abietacee</span>',
                "substantiv feminin",
            ) + body(meaning("6", "Familie de plante.", "(la) plural"))
            inputs = self.inputs(root, html, word="abietacee", loc="abietacee F1\n")
            export_local_evidence(*inputs, root / "invariant")
            self.assertEqual(
                read(root / "invariant/evidence.csv")[0]["alignment"], "source_bounded"
            )

    def test_explicit_variant_joins_only_same_dictionary_with_own_pos_and_receipt(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            raw = '<div class="defWrapper"><span class="def"><b>ANTERIU,</b> <abbr data-bs-content="substantiv neutru">s. n.</abbr> Haină. [<abbr data-bs-content="variantă">Var.</abbr>: <b>antereu</b> <abbr data-bs-content="substantiv neutru">s. n.</abbr>]</span><a class="ref" href="/sursa/dex09" title="DEX 2009">DEX</a><a href="/definitie/anteriu/123">permalink</a></div>'
            definition = meaning("1", "Haină preoțească.").replace(
                "</div></li>", '<span class="badge-source" title="DEX 2009">DEX</span></div></li>'
            )
            inputs = self.inputs(
                root,
                raw + heading("anteriu", "substantiv neutru") + body(definition),
                word="antereu",
                loc="antereu N1\n",
            )
            export_local_evidence(*inputs, root / "out")
            senses = read(root / "out/senses.csv")
            aligned = [r for r in senses if r["alignment"] == "exact"]
            self.assertEqual(
                [(r["definition"], r["pos"], r["pos_detail"]) for r in aligned],
                [("Haină preoțească.", "N", "substantiv neutru")],
            )
            self.assertEqual(aligned[0]["source_entry_id"], "/definitie/anteriu/123")
            self.assertEqual(aligned[0]["source_dictionary"], "DEX 2009")
            witness = read(root / "out/variants.csv")[0]
            self.assertEqual(witness["variant"], "antereu")
            self.assertEqual(witness["base_heading"], "anteriu")
            self.assertEqual(witness["status"], "supported")
            self.assertEqual(witness["source_sha256"], read(inputs[2])[0]["sha256"])

    def test_source_scoped_mda_variant_preserves_gender_usage_and_numbered_meanings(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            html = '<div class="defWrapper"><span class="def"><b>atu</b> <abbr data-bs-content="substantiv neutru">sn</abbr> [<abbr data-bs-content="variantă, variante(le)">V:</abbr> (<abbr data-bs-content="învechit și rar">îvr</abbr>) <b>ata</b> <abbr data-bs-content="substantiv feminin">sf</abbr> / <abbr data-bs-content="etimologie">E:</abbr> fr atout] <b>1</b> Carte de joc. <b>2</b> (<abbr data-bs-content="figurat">Fig</abbr>) Avantaj.</span><a class="ref" href="/sursa/mda2" title="MDA 2010">MDA</a><a href="/definitie/atu/9">permalink</a></div>'
            # Different dictionary/sense: cannot inherit this synthesized definition.
            foreign = meaning("3", "Bani.").replace(
                "</div></li>", '<span class="badge-source" title="DER">DER</span></div></li>'
            )
            inputs = self.inputs(
                root,
                html + heading("atu", "substantiv neutru") + body(foreign),
                word="ata",
                loc="ata F1\n",
            )
            export_local_evidence(*inputs, root / "out")
            rows = [r for r in read(root / "out/senses.csv") if r["alignment"] == "exact"]
            self.assertEqual([r["definition"] for r in rows], ["Carte de joc.", "Avantaj."])
            self.assertTrue(all(r["pos_detail"] == "substantiv feminin" for r in rows))
            self.assertEqual(json.loads(rows[0]["tags"]), ["învechit și rar"])
            self.assertEqual(set(json.loads(rows[1]["tags"])), {"învechit și rar", "figurat"})
            self.assertEqual(
                [r["sense_id"] for r in rows],
                ["/definitie/atu/9#meaning-1", "/definitie/atu/9#meaning-2"],
            )
            self.assertEqual(read(root / "out/evidence.csv")[0]["alignment"], "source_bounded")

    def test_variant_verb_conjugation_is_not_a_second_variant_or_pos(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            html = '<div class="defWrapper"><span class="def"><b>SESIZA</b> <i>vb. I. tr.</i> [<abbr data-bs-content="variantă, variante">Var.</abbr> <i>sezisa</i> <abbr data-bs-content="verb">vb.</abbr> I. / după fr saisir].</span><a class="ref" href="/sursa/dn" title="DN">DN</a><a href="/definitie/sesiza/8">permalink</a></div>'
            definition = meaning("1", "A observa.").replace(
                "</div></li>", '<span class="badge-source" title="DN">DN</span></div></li>'
            )
            inputs = self.inputs(
                root,
                html + heading("sesiza", "verb") + body(definition),
                word="sezisa",
                loc="sezisa VT1\n",
            )
            export_local_evidence(*inputs, root / "out")
            aligned = [r for r in read(root / "out/senses.csv") if r["alignment"] == "exact"]
            self.assertEqual([(r["definition"], r["pos"]) for r in aligned], [("A observa.", "V")])

    def test_variant_scope_rejects_wrong_pos_homographs_and_unknown_number(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            prefix = '<div class="defWrapper"><span class="def"><b>unu</b> <abbr data-bs-content="substantiv neutru">sn</abbr> [<abbr data-bs-content="variantă">Var.</abbr> '
            suffix = ' <b>varianta</b> <abbr data-bs-content="substantiv feminin">sf</abbr>]</span><a class="ref" href="/sursa/a" title="A">A</a><a href="/definitie/unu/3">permalink</a></div>'
            m = meaning("1", "Sens.").replace(
                "</div></li>", '<span class="badge-source" title="A">A</span></div></li>'
            )
            for key, html in [
                ("wrong-pos", prefix + suffix + heading("unu", "verb") + body(m)),
                (
                    "homographs",
                    prefix
                    + suffix
                    + heading("unu", "substantiv neutru")
                    + body(m)
                    + heading("unu", "substantiv neutru")
                    + body(m.replace("meaning1", "meaning2")),
                ),
                (
                    "unknown-number",
                    prefix
                    + '<abbr data-bs-content="singular sau plural">?</abbr>'
                    + suffix
                    + heading("unu", "substantiv neutru")
                    + body(m),
                ),
            ]:
                with self.subTest(key=key):
                    inputs = self.inputs(root, html, word="varianta", loc="varianta F1\n")
                    export_local_evidence(*inputs, root / key)
                    self.assertEqual(
                        read(root / key / "evidence.csv")[0]["alignment"], "unresolved"
                    )

    def test_variant_number_and_usage_are_scoped_and_do_not_override_sense_number(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            raw = '<div class="defWrapper"><span class="def"><b>forme</b> <abbr data-bs-content="substantiv feminin">sf</abbr> [<abbr data-bs-content="variantă">Var.</abbr> (<abbr data-bs-content="regional">reg.</abbr>) <b>variante</b> <abbr data-bs-content="substantiv feminin plural">sf pl.</abbr>]</span><a class="ref" href="/sursa/a" title="A">A</a><a href="/definitie/forme/4">permalink</a></div>'

            def sourced(text):
                return text.replace(
                    "</div></li>", '<span class="badge-source" title="A">A</span></div></li>'
                )

            html = (
                raw
                + heading("forme", "substantiv feminin")
                + body(
                    sourced(meaning("1", "Mulțime.", "numai plural"))
                    + sourced(meaning("2", "Un element.", "numai singular"))
                )
            )
            inputs = self.inputs(root, html, word="variante", loc="variante F1\n")
            export_local_evidence(*inputs, root / "out")
            variant_rows = [r for r in read(root / "out/senses.csv") if r["variant_id"]]
            self.assertEqual(
                [(r["sense_id"], r["alignment"]) for r in variant_rows],
                [("meaning1", "exact"), ("meaning2", "unresolved")],
            )
            self.assertTrue(all(r["variant_number_restriction"] == "plural" for r in variant_rows))
            self.assertIn("regional", json.loads(variant_rows[0]["tags"]))

    def test_ambiguous_or_nonentry_variant_mentions_never_supply_senses(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            marker = '<abbr data-bs-content="variantă">Var.</abbr>'
            pos = '<abbr data-bs-content="substantiv feminin">sf</abbr>'
            metadata = '<a class="ref" href="/sursa/a" title="A">A</a><a href="/definitie/unu/3">permalink</a>'
            definition = meaning("1", "Sens.").replace(
                "</div></li>", '<span class="badge-source" title="A">A</span></div></li>'
            )
            tree = heading("unu", "substantiv neutru") + body(definition)

            def raw(clause):
                return (
                    '<div class="defWrapper"><span class="def"><b>unu</b> <abbr data-bs-content="substantiv neutru">sn</abbr> ['
                    + clause
                    + "]</span>"
                    + metadata
                    + "</div>"
                )

            cases = {
                "example": '<div class="type-example">'
                + raw(marker + " varianta " + pos)
                + "</div>",
                "etymology": raw(
                    '<abbr data-bs-content="etimologie">E:</abbr> ' + marker + " varianta " + pos
                ),
                "see": raw('<abbr data-bs-content="vezi">V.</abbr> varianta ' + pos),
                "missing-pos": raw(marker + " varianta"),
                "neighbor": raw(
                    marker
                    + " varianta "
                    + pos
                    + ', <abbr data-bs-content="regional">reg.</abbr> alta '
                    + pos
                ),
                "restricted-meaning": raw(marker + " (1) varianta " + pos),
            }
            for name, html in cases.items():
                with self.subTest(name=name):
                    inputs = self.inputs(root, html + tree, word="varianta", loc="varianta F1\n")
                    export_local_evidence(*inputs, root / name)
                    self.assertEqual(
                        read(root / name / "evidence.csv")[0]["alignment"], "unresolved"
                    )
                    if name == "missing-pos":
                        self.assertEqual(
                            read(root / name / "variants.csv")[0]["reason"], "missing_variant_pos"
                        )

    def test_variant_receipt_stops_before_following_etymological_prose(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            raw = '<div class="defWrapper"><span class="def"><b>aici</b> <abbr data-bs-content="adverb">adv.</abbr> <abbr data-bs-content="variantă">Var.</abbr> <b>ai</b> (<abbr data-bs-content="Maramureș">Maram.</abbr>) reprezintă <abbr data-bs-content="latin(ă)">lat.</abbr> ad hic. <abbr data-bs-content="confer">Cf.</abbr> aci.</span><a class="ref" href="/sursa/der" title="DER">DER</a><a href="/definitie/aici/1">permalink</a></div>'
            inputs = self.inputs(root, raw, word="ai", loc="ai D1\n")
            export_local_evidence(*inputs, root / "out")
            row = read(root / "out/variants.csv")[0]
            self.assertEqual(json.loads(row["tags"]), ["Maramureș"])
            self.assertNotIn("lat.", row["witness_text"])
            self.assertEqual(row["status"], "unresolved")

    def test_variant_closing_bracket_bounds_prose_in_the_same_text_node(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            raw = '<div class="defWrapper"><span class="def"><b>ANTERIU,</b> <i>anterie,</i> <abbr data-bs-content="substantiv neutru">s. n.</abbr> Haină. [<abbr data-bs-content="variantă">Var.</abbr>: <b>antereu</b> <abbr data-bs-content="substantiv neutru">s. n.</abbr>] – Din <abbr data-bs-content="limba turcă">tc.</abbr> anteri.</span><a class="ref" href="/sursa/dex09" title="DEX09">DEX09</a><a href="/definitie/anteriu/1">permalink</a></div>'
            sourced = meaning("1", "Haină preoțească.").replace(
                "</div></li>", '<span class="badge-source" title="DEX09">DEX09</span></div></li>'
            )
            inputs = self.inputs(
                root,
                raw + heading("anteriu", "substantiv neutru") + body(sourced),
                word="antereu",
                loc="antereu N1\n",
            )
            export_local_evidence(*inputs, root / "out")
            self.assertEqual(read(root / "out/evidence.csv")[0]["alignment"], "source_bounded")
            witness = read(root / "out/variants.csv")[0]
            self.assertNotIn("Din", witness["witness_text"])
            self.assertEqual(json.loads(witness["tags"]), [])
