import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import csv
import hashlib
import importlib.metadata
import json
import sys
from types import SimpleNamespace
from classificator.evaluation.wordfreq_source import export_wordfreq


def write_vocabulary(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["word_id", "word", "type"])
        writer.writerows(rows)
    return path


def install_fake_wordfreq(test_case, frequencies):
    calls = []

    def get_frequency_dict(language, *, wordlist):
        calls.append((language, wordlist))
        return frequencies

    test_case.enterContext(
        patch.dict(
            sys.modules, {"wordfreq": SimpleNamespace(get_frequency_dict=get_frequency_dict)}
        )
    )
    test_case.enterContext(patch.object(importlib.metadata, "version", lambda name: "3.1.1"))
    return calls


class TestWordfreqSource(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp_path = Path(temporary.name)

    def test_exports_only_inventory_members_found_in_romanian_corpus(self):
        tmp_path = self.tmp_path
        source = write_vocabulary(
            tmp_path / "words.csv",
            [
                [3, "fată", "N"],
                [2, "fata", "N"],
                [1, "șarpe", "N"],
                [4, "absent", "A"],
                [5, "zero", "N"],
                [6, "ŞARPE", "N"],
            ],
        )
        calls = install_fake_wordfreq(
            self, {"şarpe": 0.0002, "fata": 0.003, "unrelated": 0.1, "zero": 0.0}
        )
        output = tmp_path / "frequencies.csv"
        result = export_wordfreq(source, output)
        with output.open(newline="", encoding="utf-8") as stream:
            self.assertEqual(
                list(csv.DictReader(stream)),
                [{"word": "șarpe", "frequency": "0.0002"}, {"word": "fata", "frequency": "0.003"}],
            )
        self.assertEqual(calls, [("ro", "best")])
        metadata_path = tmp_path / "frequencies.csv.metadata.json"
        metadata = json.loads(metadata_path.read_text())
        self.assertEqual(metadata["package_version"], "3.1.1")
        self.assertEqual(metadata["language"], "ro")
        self.assertEqual(metadata["exported_count"], 2)
        self.assertEqual(metadata["inventory_count"], 6)
        self.assertEqual(
            metadata["vocabulary_sha256"], hashlib.sha256(source.read_bytes()).hexdigest()
        )
        self.assertEqual(
            metadata["frequencies_sha256"], hashlib.sha256(output.read_bytes()).hexdigest()
        )
        self.assertIn("small", metadata["coverage_note"])
        self.assertIn("censored", metadata["coverage_note"])
        self.assertEqual(result["metadata_path"], metadata_path)

    def test_missing_optional_dependency_is_actionable_without_writing(self):
        tmp_path = self.tmp_path
        source = write_vocabulary(tmp_path / "words.csv", [[1, "casă", "N"]])
        self.enterContext(patch.dict(sys.modules, {"wordfreq": None}))
        with self.assertRaisesRegex(RuntimeError, "pip install wordfreq"):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_inventory_ids_are_nonempty_positive_and_unique_case_1(self):
        tmp_path = self.tmp_path
        rows = []
        source = write_vocabulary(tmp_path / "words.csv", rows)
        install_fake_wordfreq(self, {"casă": 0.001})
        with self.assertRaises(ValueError):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_inventory_ids_are_nonempty_positive_and_unique_case_2(self):
        tmp_path = self.tmp_path
        rows = [[0, "casă", "N"]]
        source = write_vocabulary(tmp_path / "words.csv", rows)
        install_fake_wordfreq(self, {"casă": 0.001})
        with self.assertRaises(ValueError):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_inventory_ids_are_nonempty_positive_and_unique_case_3(self):
        tmp_path = self.tmp_path
        rows = [[-1, "casă", "N"]]
        source = write_vocabulary(tmp_path / "words.csv", rows)
        install_fake_wordfreq(self, {"casă": 0.001})
        with self.assertRaises(ValueError):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_inventory_ids_are_nonempty_positive_and_unique_case_4(self):
        tmp_path = self.tmp_path
        rows = [[1, "casă", "N"], [1, "pom", "N"]]
        source = write_vocabulary(tmp_path / "words.csv", rows)
        install_fake_wordfreq(self, {"casă": 0.001})
        with self.assertRaises(ValueError):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_invalid_or_conflicting_corpus_values_are_rejected_case_1(self):
        tmp_path = self.tmp_path
        frequencies = {"casă": float("nan")}
        source = write_vocabulary(tmp_path / "words.csv", [[1, "casă", "N"]])
        install_fake_wordfreq(self, frequencies)
        with self.assertRaises(ValueError):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_invalid_or_conflicting_corpus_values_are_rejected_case_2(self):
        tmp_path = self.tmp_path
        frequencies = {"casă": float("inf")}
        source = write_vocabulary(tmp_path / "words.csv", [[1, "casă", "N"]])
        install_fake_wordfreq(self, frequencies)
        with self.assertRaises(ValueError):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_invalid_or_conflicting_corpus_values_are_rejected_case_3(self):
        tmp_path = self.tmp_path
        frequencies = {"casă": -0.1}
        source = write_vocabulary(tmp_path / "words.csv", [[1, "casă", "N"]])
        install_fake_wordfreq(self, frequencies)
        with self.assertRaises(ValueError):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_invalid_or_conflicting_corpus_values_are_rejected_case_4(self):
        tmp_path = self.tmp_path
        frequencies = {"casă": 1.1}
        source = write_vocabulary(tmp_path / "words.csv", [[1, "casă", "N"]])
        install_fake_wordfreq(self, frequencies)
        with self.assertRaises(ValueError):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_invalid_or_conflicting_corpus_values_are_rejected_case_5(self):
        tmp_path = self.tmp_path
        frequencies = {"casă": True}
        source = write_vocabulary(tmp_path / "words.csv", [[1, "casă", "N"]])
        install_fake_wordfreq(self, frequencies)
        with self.assertRaises(ValueError):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_invalid_or_conflicting_corpus_values_are_rejected_case_6(self):
        tmp_path = self.tmp_path
        frequencies = {"casă": "0.1"}
        source = write_vocabulary(tmp_path / "words.csv", [[1, "casă", "N"]])
        install_fake_wordfreq(self, frequencies)
        with self.assertRaises(ValueError):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_invalid_or_conflicting_corpus_values_are_rejected_case_7(self):
        tmp_path = self.tmp_path
        frequencies = {"casă": 0.1, "CASĂ": 0.2}
        source = write_vocabulary(tmp_path / "words.csv", [[1, "casă", "N"]])
        install_fake_wordfreq(self, frequencies)
        with self.assertRaises(ValueError):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_existing_export_or_metadata_is_never_overwritten_case_1(self):
        tmp_path = self.tmp_path
        existing_name = "frequencies.csv"
        existing = tmp_path / existing_name
        existing.write_text("preserve")
        with self.assertRaises(FileExistsError):
            export_wordfreq(tmp_path / "missing.csv", tmp_path / "frequencies.csv")
        self.assertEqual(existing.read_text(), "preserve")
        self.assertEqual(list(tmp_path.iterdir()), [existing])

    def test_existing_export_or_metadata_is_never_overwritten_case_2(self):
        tmp_path = self.tmp_path
        existing_name = "frequencies.csv.metadata.json"
        existing = tmp_path / existing_name
        existing.write_text("preserve")
        with self.assertRaises(FileExistsError):
            export_wordfreq(tmp_path / "missing.csv", tmp_path / "frequencies.csv")
        self.assertEqual(existing.read_text(), "preserve")
        self.assertEqual(list(tmp_path.iterdir()), [existing])

    def test_failed_metadata_write_leaves_no_partial_export(self):
        tmp_path = self.tmp_path
        from pathlib import Path

        source = write_vocabulary(tmp_path / "words.csv", [[1, "casă", "N"]])
        install_fake_wordfreq(self, {"casă": 0.001})
        original_write = Path.write_text

        def fail_metadata(path, *args, **kwargs):
            if path.name.endswith(".metadata.json"):
                raise OSError("disk full")
            return original_write(path, *args, **kwargs)

        self.enterContext(patch.object(Path, "write_text", fail_metadata))
        with self.assertRaisesRegex(OSError, "disk full"):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_publication_failure_rolls_back_only_this_exports_artifacts(self):
        tmp_path = self.tmp_path
        import os

        source = write_vocabulary(tmp_path / "words.csv", [[1, "casă", "N"]])
        install_fake_wordfreq(self, {"casă": 0.001})
        original_link = os.link

        def fail_csv(staged, target):
            if target.name == "frequencies.csv":
                raise OSError("publication failed")
            return original_link(staged, target)

        self.enterContext(patch.object(os, "link", fail_csv))
        with self.assertRaisesRegex(OSError, "publication failed"):
            export_wordfreq(source, tmp_path / "frequencies.csv")
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_exports_pin_corpus_and_lookup_policy_independently_of_inventory(self):
        root = self.tmp_path
        a = write_vocabulary(root / 'a.csv', [[1, 'tara', 'V']])
        b = write_vocabulary(root / 'b.csv', [[2, 'țară', 'N']])
        install_fake_wordfreq(self, {'tara': .01, 'țară': .1})
        first = export_wordfreq(a, root / 'first.csv')
        second = export_wordfreq(b, root / 'second.csv')
        self.assertEqual(first['lookup_policy'], 'exact-nfc-cedilla-casefold-v1')
        self.assertEqual(first['corpus_sha256'], second['corpus_sha256'])
        install_fake_wordfreq(self, {'tara': .02, 'țară': .1})
        changed = export_wordfreq(a, root / 'changed.csv')
        self.assertNotEqual(first['corpus_sha256'], changed['corpus_sha256'])
