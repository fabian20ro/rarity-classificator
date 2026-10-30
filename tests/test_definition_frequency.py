import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from classificator.evaluation.definition_frequency import export_rebus_frequencies
from tests.test_exact_form import write_csv


class DefinitionFrequencyTests(unittest.TestCase):
    def test_counts_exact_tokens_once_per_definition_excluding_target_pages_and_navigation(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            vocabulary = write_csv(
                root / "words.csv",
                [
                    dict(word_id=i, word=word, type="N")
                    for i, word in enumerate(
                        ["masa", "masă", "micșurat", "sezisa", "ițar", "ata", "șarpe"], 1
                    )
                ],
            )
            cache = root / "cache"
            cache.mkdir()
            body = "masa masa masă micșorat sesiza ițari ața ŞARPE"
            records = [
                (
                    "ALFA",
                    "alfa",
                    '<html><nav>masa masa masa</nav><span class="tree-def">'
                    + body
                    + '</span><div class="defWrapper"><span class="def">duplicate unwanted</span></div></html>',
                ),
                ("BETA", "beta", '<html><span class="tree-def">' + body + "</span></html>"),
                (
                    "MASA",
                    "masă",
                    '<html><span class="tree-def">masa micșurat sezisa ițar ata</span></html>',
                ),
                (
                    "GAMA",
                    "gama",
                    '<html><div class="defWrapper"><span class="def">masa</span></div></html>',
                ),
            ]
            for key, original, html in records:
                (cache / (key + ".json")).write_text(
                    json.dumps(dict(word=key, original=original, status="ok", html=html))
                )
            result = export_rebus_frequencies(vocabulary, cache, root / "output")
            with result["frequencies"].open() as stream:
                rows = {r["word"]: r for r in csv.DictReader(stream)}
            self.assertEqual(rows["masa"]["count"], "3")
            self.assertEqual(rows["masa"]["document_count"], "2")
            self.assertEqual(rows["masa"]["token_total"], "9")
            self.assertAlmostEqual(float(rows["masa"]["frequency"]), 1 / 3)
            self.assertEqual(rows["masă"]["count"], "1")
            self.assertEqual(rows["șarpe"]["count"], "1")
            for word in ["micșurat", "sezisa", "ițar", "ata"]:
                self.assertEqual(rows[word]["frequency"], "")
                self.assertEqual(rows[word]["status"], "unobserved")
            manifest = json.loads((root / "output/manifest.json").read_text())
            self.assertEqual(manifest["counts"]["excluded_target_pages"], 1)
            self.assertEqual(manifest["counts"]["duplicate_definitions"], 1)
            self.assertEqual(
                set(manifest["implementation"]), {"dataset.py", "definition_frequency.py"}
            )
            self.assertTrue(
                all(len(digest) == 64 for digest in manifest["implementation"].values())
            )
            with self.assertRaises(FileExistsError):
                export_rebus_frequencies(vocabulary, cache, root / "output")
