import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests.test_exact_form import write_csv
from tests.test_wordfreq_source import install_fake_wordfreq
from classificator.evaluation.wordfreq_source import export_wordfreq
from classificator.evaluation.wordfreq_baseline import (
    freeze_wordfreq_model,
    score_wordfreq_inventory,
)


class WordfreqBaselineTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        words = ["țară", "copac", "masă", "rar", "arhaic", "tara", "lipsă", "necunoscut"]
        self.vocab = write_csv(
            self.root / "pilot.csv",
            [dict(word_id=i, word=w, type="N") for i, w in enumerate(words, 1)],
        )
        self.ref = write_csv(
            self.root / "reference.csv",
            [
                dict(word_id=i, word=w, working_level=y, reference_kind="initial_opaque_form_pos")
                for i, (w, y) in enumerate(zip(words, [1, 2, 3, 4, 5, 2, 4, 5]), 1)
            ],
        )
        install_fake_wordfreq(self, dict(zip(words[:5], [0.1, 0.01, 0.001, 0.0001, 0.00001])))
        self.freq = self.root / "pilot-frequencies.csv"
        export_wordfreq(self.vocab, self.freq)

    def test_freeze_and_replay_complete_scores_preserve_exact_form_and_pos_rows(self):
        model = freeze_wordfreq_model(self.vocab, self.ref, self.freq, self.root / "model")
        self.assertEqual(model["threshold_fit"]["thresholds"], [0.1, 0.01, 0.001, 0.0001])
        self.assertEqual(model["fallback"]["missing_level"], 4)
        self.assertEqual(model["fallback"]["global_level"], 3)
        self.assertEqual(model["fallback"]["missing_train_ids"], [6, 7, 8])
        self.assertEqual(model["reference_kind_counts"], {"initial_opaque_form_pos": 8})
        inventory = write_csv(
            self.root / "full.csv",
            [*list(csv.DictReader(self.vocab.open())), dict(word_id=9, word="țară", type="A")],
        )
        frequency = self.root / "full-frequencies.csv"
        export_wordfreq(inventory, frequency)
        config = self.root / "model/model.json"
        result = score_wordfreq_inventory(inventory, frequency, config, self.root / "first")
        rows = list(csv.DictReader((self.root / "first/scores.csv").open()))
        self.assertEqual([int(r["rarity_level"]) for r in rows], [1, 2, 3, 4, 5, 4, 4, 4, 1])
        self.assertEqual(rows[0]["route"], "frequency_thresholds")
        self.assertEqual(rows[5]["route"], "missing_group_median")
        self.assertEqual(rows[8]["type"], "A")
        self.assertTrue(all(r["model_version"] == model["model_version"] for r in rows))
        self.assertEqual(result["total"], 9)
        self.assertEqual(result["unique_forms"], 8)
        self.assertEqual(result["routes"], {"frequency_thresholds": 6, "missing_group_median": 3})
        # Runtime requires neither calibration labels nor wordfreq package.
        self.ref.unlink()
        self.vocab.unlink()
        score_wordfreq_inventory(inventory, frequency, config, self.root / "replay")
        self.assertEqual(
            (self.root / "first/scores.csv").read_bytes(),
            (self.root / "replay/scores.csv").read_bytes(),
        )
        with self.assertRaises(FileExistsError):
            score_wordfreq_inventory(inventory, frequency, config, self.root / "first")

    def test_wrong_source_or_modified_model_fails_before_publication(self):
        freeze_wordfreq_model(self.vocab, self.ref, self.freq, self.root / "model")
        config = self.root / "model/model.json"
        metadata_path = self.freq.with_suffix(".csv.metadata.json")
        original_metadata = metadata_path.read_text()
        original_model = config.read_text()
        for field, value in [
            ("language", "en"),
            ("package_version", "different"),
            ("vocabulary_sha256", "0" * 64),
            ("frequencies_sha256", "0" * 64),
            ("inventory_count", 7),
            ("exported_count", 4),
            ("lookup_policy", "lemma"),
            ("corpus_sha256", "1" * 64),
        ]:
            with self.subTest(field=field):
                metadata = json.loads(original_metadata)
                metadata[field] = value
                metadata_path.write_text(json.dumps(metadata))
                with self.assertRaises(ValueError):
                    score_wordfreq_inventory(self.vocab, self.freq, config, self.root / "bad")
                self.assertFalse((self.root / "bad").exists())
        metadata_path.write_text(original_metadata)
        model = json.loads(original_model)
        model["fallback"]["missing_level"] = 1
        config.write_text(json.dumps(model))
        with self.assertRaises(ValueError):
            score_wordfreq_inventory(self.vocab, self.freq, config, self.root / "bad")
        self.assertFalse((self.root / "bad").exists())

    def test_no_missing_training_examples_and_no_observed_training_examples_are_explicit(self):
        pilot_rows = list(csv.DictReader(self.vocab.open()))
        ref_rows = list(csv.DictReader(self.ref.open()))
        for name, selection, expected, route in [
            ("observed", slice(0, 5), 3, "global_median"),
            ("missing", slice(5, 8), 4, "global_median_no_thresholds"),
        ]:
            with self.subTest(name=name):
                pilot = write_csv(self.root / f"{name}.csv", pilot_rows[selection])
                ref = write_csv(self.root / f"{name}-ref.csv", ref_rows[selection])
                freq = self.root / f"{name}-frequencies.csv"
                export_wordfreq(pilot, freq)
                freeze_wordfreq_model(pilot, ref, freq, self.root / name)
                score_wordfreq_inventory(
                    self.vocab,
                    self.freq,
                    self.root / name / "model.json",
                    self.root / f"{name}-out",
                )
                rows = list(csv.DictReader((self.root / f"{name}-out/scores.csv").open()))
                row = rows[5] if name == "observed" else rows[0]
                self.assertEqual(row["rarity_level"], str(expected))
                self.assertEqual(row["route"], route)
                self.assertEqual(len(rows), 8)

    def test_invalid_reference_and_duplicate_inventory_ids_do_not_create_model(self):
        originals = list(csv.DictReader(self.ref.open()))
        for name in ["duplicate", "missing", "spelling", "level", "kind"]:
            with self.subTest(name=name):
                rows = [dict(r) for r in originals]
                if name == "duplicate":
                    rows.append(rows[0])
                elif name == "missing":
                    rows.pop()
                elif name == "spelling":
                    rows[0]["word"] = "wrong"
                elif name == "level":
                    rows[0]["working_level"] = "6"
                else:
                    rows[0]["reference_kind"] = "fabricated"
                ref = write_csv(self.root / "invalid.csv", rows)
                with self.assertRaises(ValueError):
                    freeze_wordfreq_model(self.vocab, ref, self.freq, self.root / "bad")
                self.assertFalse((self.root / "bad").exists())
        rows = list(csv.DictReader(self.vocab.open()))
        write_csv(self.vocab, rows + [rows[0]])
        with self.assertRaises(ValueError):
            freeze_wordfreq_model(self.vocab, self.ref, self.freq, self.root / "bad")

    def test_cli_freeze_and_shadow_score_without_http_or_database(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from classificator.cli import main

        with (
            redirect_stdout(StringIO()),
            patch("requests.Session.request", side_effect=AssertionError("HTTP forbidden")),
            patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
        ):
            self.assertEqual(
                main(
                    [
                        "--output-dir",
                        str(self.root / "logs"),
                        "evaluation-freeze-wordfreq",
                        "--vocabulary-csv",
                        str(self.vocab),
                        "--reference-csv",
                        str(self.ref),
                        "--wordfreq-csv",
                        str(self.freq),
                        "--campaign-dir",
                        str(self.root / "frozen"),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "--output-dir",
                        str(self.root / "logs"),
                        "evaluation-score-wordfreq",
                        "--vocabulary-csv",
                        str(self.vocab),
                        "--wordfreq-csv",
                        str(self.freq),
                        "--model-json",
                        str(self.root / "frozen/model.json"),
                        "--campaign-dir",
                        str(self.root / "scored"),
                    ]
                ),
                0,
            )
        self.assertEqual(len(list(csv.DictReader((self.root / "scored/scores.csv").open()))), 8)

    def test_malformed_frequency_never_becomes_a_fallback_score(self):
        import hashlib

        freeze_wordfreq_model(self.vocab, self.ref, self.freq, self.root / "model")
        with self.assertRaises(FileExistsError):
            freeze_wordfreq_model(self.vocab, self.ref, self.freq, self.root / "model")
        rows = list(csv.DictReader(self.freq.open()))
        rows[0]["frequency"] = "nan"
        write_csv(self.freq, rows)
        metadata_path = self.freq.with_suffix(".csv.metadata.json")
        metadata = json.loads(metadata_path.read_text())
        metadata["frequencies_sha256"] = hashlib.sha256(self.freq.read_bytes()).hexdigest()
        metadata_path.write_text(json.dumps(metadata))
        with self.assertRaises(ValueError):
            score_wordfreq_inventory(
                self.vocab, self.freq, self.root / "model/model.json", self.root / "bad"
            )
        self.assertFalse((self.root / "bad").exists())
