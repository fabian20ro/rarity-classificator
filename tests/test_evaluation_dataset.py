import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import csv
import hashlib
import json
from classificator.evaluation.dataset import prepare_dataset


def write_csv(path, headers, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
    return path


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


class TestEvaluationDataset(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp_path = Path(temporary.name)

    def test_preparation_preserves_only_authoritative_entries_and_blind_labels(self):
        tmp_path = self.tmp_path
        source = write_csv(
            tmp_path / "input.csv",
            ["word_id", "word", "type"],
            [[42, "şarpe", "N"], [9, "oțel", "N"]],
        )
        result = prepare_dataset(source, tmp_path / "dataset", source_version="scrabble-2026")
        vocabulary = read_csv(result["vocabulary"])
        self.assertEqual([row["word_id"] for row in vocabulary], ["9", "42"])
        self.assertEqual([row["word"] for row in vocabulary], ["oțel", "şarpe"])
        self.assertEqual([row["game_key"] for row in vocabulary], ["OTEL", "SARPE"])
        self.assertTrue(set((row["split"] for row in vocabulary)) <= {"dev", "calibration", "test"})
        labels = read_csv(result["labels"])
        self.assertTrue(all((row["level"] == "" for row in labels)))
        self.assertEqual(set(labels[0]), {"word_id", "word", "type", "group", "split", "level"})
        self.assertEqual(result["count"], 2)
        evidence = read_csv(result["evidence"])
        self.assertTrue(all((row["frequency_present"] == "false" for row in evidence)))
        self.assertTrue(all((row["frequency"] == "" for row in evidence)))
        manifest = json.loads(Path(result["manifest"]).read_text())
        self.assertEqual(manifest["source_version"], "scrabble-2026")
        self.assertEqual(
            manifest["inputs"]["vocabulary_sha256"], hashlib.sha256(source.read_bytes()).hexdigest()
        )
        self.assertEqual(
            manifest["artifacts"]["vocabulary.csv"],
            hashlib.sha256(Path(result["vocabulary"]).read_bytes()).hexdigest(),
        )

    def test_family_and_game_collisions_form_transitive_groups_independent_of_input_order(self):
        tmp_path = self.tmp_path
        entries = [
            [1, "fată", "N", "girl"],
            [2, "fata", "N", "other"],
            [3, "fete", "N", "girl"],
            [4, "fetei", "N", "other"],
            [5, "copac", "N", ""],
        ]
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type", "family"], entries)
        first = prepare_dataset(source, tmp_path / "first", source_version="v1", seed=123)
        write_csv(source, ["word_id", "word", "type", "family"], list(reversed(entries)))
        second = prepare_dataset(source, tmp_path / "second", source_version="v1", seed=123)
        rows = read_csv(first["vocabulary"])
        self.assertEqual(len({row["group"] for row in rows[:4]}), 1)
        self.assertEqual(len({row["split"] for row in rows[:4]}), 1)
        self.assertNotEqual(rows[4]["group"], rows[0]["group"])
        for artifact in ["vocabulary", "evidence", "labels"]:
            self.assertEqual(
                Path(first[artifact]).read_bytes(), Path(second[artifact]).read_bytes()
            )

    def test_frequency_exact_form_join_preserves_diacritics_and_censored_zero(self):
        tmp_path = self.tmp_path
        source = write_csv(
            tmp_path / "input.csv",
            ["word_id", "word", "type"],
            [[1, "șarpe", "N"], [2, "fată", "N"], [3, "fata", "N"], [4, "obscur", "A"]],
        )
        frequencies = write_csv(
            tmp_path / "frequencies.csv",
            ["word", "frequency"],
            [["ŞARPE", "0.0002"], ["fata", "0.03"], ["obscur", "0"], ["extra", "0.1"]],
        )
        result = prepare_dataset(
            source, tmp_path / "dataset", source_version="v1", frequencies_csv=frequencies
        )
        evidence = read_csv(result["evidence"])
        self.assertEqual(
            [(row["frequency"], row["frequency_present"]) for row in evidence],
            [("0.0002", "true"), ("", "false"), ("0.03", "true"), ("0.0", "true")],
        )
        manifest = json.loads(Path(result["manifest"]).read_text())
        self.assertEqual(
            manifest["inputs"]["frequencies_sha256"],
            hashlib.sha256(frequencies.read_bytes()).hexdigest(),
        )

    def test_dictionary_evidence_uses_original_form_and_strips_markup_without_fetching(self):
        tmp_path = self.tmp_path
        source = write_csv(
            tmp_path / "input.csv",
            ["word_id", "word", "type"],
            [
                [1, "șarpe", "N"],
                [2, "fată", "N"],
                [3, "fata", "N"],
                [4, "obscur", "A"],
                [5, "lipsă", "N"],
            ],
        )
        cache = tmp_path / "cache"
        cache.mkdir()
        payloads = {
            "SARPE.json": {
                "word": "SARPE",
                "original": "şarpe",
                "status": "ok",
                "html": "<p>Reptilă <b>lungă</b> &amp; fără picioare.</p><script>BAD</script><style>NO</style><p>Alt sens.</p>",
            },
            "FATA.json": {
                "word": "FATA",
                "original": "fată",
                "status": "ok",
                "html": "<p>Persoană de sex feminin.</p>",
            },
            "OBSCUR.json": {
                "word": "OBSCUR",
                "original": "obscur",
                "status": "not_found",
                "html": "",
            },
        }
        for name, payload in payloads.items():
            (cache / name).write_text(json.dumps(payload), encoding="utf-8")
        before = {p.name: p.read_bytes() for p in cache.iterdir()}
        result = prepare_dataset(source, tmp_path / "dataset", source_version="v1", dex_cache=cache)
        evidence = read_csv(result["evidence"])
        self.assertEqual(evidence[0]["definition"], "Reptilă lungă & fără picioare. Alt sens.")
        self.assertEqual(evidence[0]["definition_status"], "ok")
        self.assertEqual(evidence[1]["definition"], "Persoană de sex feminin.")
        self.assertEqual(evidence[2]["definition"], "")
        self.assertEqual(evidence[2]["definition_status"], "ambiguous")
        self.assertEqual(evidence[3]["definition_status"], "not_found")
        self.assertEqual(evidence[4]["definition_status"], "missing")
        self.assertEqual({p.name: p.read_bytes() for p in cache.iterdir()}, before)
        manifest = json.loads(Path(result["manifest"]).read_text())
        self.assertEqual(manifest["inputs"]["dex_file_count"], 3)
        self.assertEqual(len(manifest["inputs"]["dex_sha256"]), 64)

    def test_invalid_authoritative_vocabulary_fails_before_creating_artifacts_case_1(self):
        tmp_path = self.tmp_path
        headers = ["word_id", "word"]
        entries = [[1, "casă"]]
        source = write_csv(tmp_path / "input.csv", headers, entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1")
        self.assertFalse(output.exists())

    def test_invalid_authoritative_vocabulary_fails_before_creating_artifacts_case_2(self):
        tmp_path = self.tmp_path
        headers = ["word_id", "word", "type"]
        entries = []
        source = write_csv(tmp_path / "input.csv", headers, entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1")
        self.assertFalse(output.exists())

    def test_invalid_authoritative_vocabulary_fails_before_creating_artifacts_case_3(self):
        tmp_path = self.tmp_path
        headers = ["word_id", "word", "type"]
        entries = [[1, "casă", "N"], ["01", "pom", "N"]]
        source = write_csv(tmp_path / "input.csv", headers, entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1")
        self.assertFalse(output.exists())

    def test_invalid_authoritative_vocabulary_fails_before_creating_artifacts_case_4(self):
        tmp_path = self.tmp_path
        headers = ["word_id", "word", "type"]
        entries = [[0, "casă", "N"]]
        source = write_csv(tmp_path / "input.csv", headers, entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1")
        self.assertFalse(output.exists())

    def test_invalid_authoritative_vocabulary_fails_before_creating_artifacts_case_5(self):
        tmp_path = self.tmp_path
        headers = ["word_id", "word", "type"]
        entries = [[-1, "casă", "N"]]
        source = write_csv(tmp_path / "input.csv", headers, entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1")
        self.assertFalse(output.exists())

    def test_invalid_authoritative_vocabulary_fails_before_creating_artifacts_case_6(self):
        tmp_path = self.tmp_path
        headers = ["word_id", "word", "type"]
        entries = [["1.5", "casă", "N"]]
        source = write_csv(tmp_path / "input.csv", headers, entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1")
        self.assertFalse(output.exists())

    def test_invalid_authoritative_vocabulary_fails_before_creating_artifacts_case_7(self):
        tmp_path = self.tmp_path
        headers = ["word_id", "word", "type"]
        entries = [[1, "", "N"]]
        source = write_csv(tmp_path / "input.csv", headers, entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1")
        self.assertFalse(output.exists())

    def test_invalid_authoritative_vocabulary_fails_before_creating_artifacts_case_8(self):
        tmp_path = self.tmp_path
        headers = ["word_id", "word", "type"]
        entries = [[1, "casă", ""]]
        source = write_csv(tmp_path / "input.csv", headers, entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1")
        self.assertFalse(output.exists())

    def test_invalid_authoritative_vocabulary_fails_before_creating_artifacts_case_9(self):
        tmp_path = self.tmp_path
        headers = ["word_id", "word", "type", "word"]
        entries = [[1, "casă", "N", "pom"]]
        source = write_csv(tmp_path / "input.csv", headers, entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1")
        self.assertFalse(output.exists())

    def test_invalid_or_ambiguous_frequency_data_is_rejected_case_1(self):
        tmp_path = self.tmp_path
        entries = [["casă", "nan"]]
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        frequencies = write_csv(tmp_path / "frequency.csv", ["word", "frequency"], entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1", frequencies_csv=frequencies)
        self.assertFalse(output.exists())

    def test_invalid_or_ambiguous_frequency_data_is_rejected_case_2(self):
        tmp_path = self.tmp_path
        entries = [["casă", "inf"]]
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        frequencies = write_csv(tmp_path / "frequency.csv", ["word", "frequency"], entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1", frequencies_csv=frequencies)
        self.assertFalse(output.exists())

    def test_invalid_or_ambiguous_frequency_data_is_rejected_case_3(self):
        tmp_path = self.tmp_path
        entries = [["casă", "-0.1"]]
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        frequencies = write_csv(tmp_path / "frequency.csv", ["word", "frequency"], entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1", frequencies_csv=frequencies)
        self.assertFalse(output.exists())

    def test_invalid_or_ambiguous_frequency_data_is_rejected_case_4(self):
        tmp_path = self.tmp_path
        entries = [["casă", "1.1"]]
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        frequencies = write_csv(tmp_path / "frequency.csv", ["word", "frequency"], entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1", frequencies_csv=frequencies)
        self.assertFalse(output.exists())

    def test_invalid_or_ambiguous_frequency_data_is_rejected_case_5(self):
        tmp_path = self.tmp_path
        entries = [["casă", ""]]
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        frequencies = write_csv(tmp_path / "frequency.csv", ["word", "frequency"], entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1", frequencies_csv=frequencies)
        self.assertFalse(output.exists())

    def test_invalid_or_ambiguous_frequency_data_is_rejected_case_6(self):
        tmp_path = self.tmp_path
        entries = [["", "0.1"]]
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        frequencies = write_csv(tmp_path / "frequency.csv", ["word", "frequency"], entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1", frequencies_csv=frequencies)
        self.assertFalse(output.exists())

    def test_invalid_or_ambiguous_frequency_data_is_rejected_case_7(self):
        tmp_path = self.tmp_path
        entries = [["şarpe", "0.1"], ["șarpe", "0.2"]]
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        frequencies = write_csv(tmp_path / "frequency.csv", ["word", "frequency"], entries)
        output = tmp_path / "dataset"
        with self.assertRaises(ValueError):
            prepare_dataset(source, output, source_version="v1", frequencies_csv=frequencies)
        self.assertFalse(output.exists())

    def test_dataset_requires_versioned_source_and_integer_seed_case_1(self):
        tmp_path = self.tmp_path
        source_version = ""
        seed = 0
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        with self.assertRaises(ValueError):
            prepare_dataset(source, tmp_path / "dataset", source_version=source_version, seed=seed)
        self.assertFalse((tmp_path / "dataset").exists())

    def test_dataset_requires_versioned_source_and_integer_seed_case_2(self):
        tmp_path = self.tmp_path
        source_version = "  "
        seed = 0
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        with self.assertRaises(ValueError):
            prepare_dataset(source, tmp_path / "dataset", source_version=source_version, seed=seed)
        self.assertFalse((tmp_path / "dataset").exists())

    def test_dataset_requires_versioned_source_and_integer_seed_case_3(self):
        tmp_path = self.tmp_path
        source_version = "v1"
        seed = True
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        with self.assertRaises(ValueError):
            prepare_dataset(source, tmp_path / "dataset", source_version=source_version, seed=seed)
        self.assertFalse((tmp_path / "dataset").exists())

    def test_dataset_requires_versioned_source_and_integer_seed_case_4(self):
        tmp_path = self.tmp_path
        source_version = "v1"
        seed = 0.5
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        with self.assertRaises(ValueError):
            prepare_dataset(source, tmp_path / "dataset", source_version=source_version, seed=seed)
        self.assertFalse((tmp_path / "dataset").exists())

    def test_malformed_cache_fails_before_output_case_1(self):
        tmp_path = self.tmp_path
        payload = {}
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "CASA.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ValueError):
            prepare_dataset(source, tmp_path / "dataset", source_version="v1", dex_cache=cache)
        self.assertFalse((tmp_path / "dataset").exists())

    def test_malformed_cache_fails_before_output_case_2(self):
        tmp_path = self.tmp_path
        payload = []
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "CASA.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ValueError):
            prepare_dataset(source, tmp_path / "dataset", source_version="v1", dex_cache=cache)
        self.assertFalse((tmp_path / "dataset").exists())

    def test_malformed_cache_fails_before_output_case_3(self):
        tmp_path = self.tmp_path
        payload = {"original": "casă", "status": "ok", "html": None}
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "CASA.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ValueError):
            prepare_dataset(source, tmp_path / "dataset", source_version="v1", dex_cache=cache)
        self.assertFalse((tmp_path / "dataset").exists())

    def test_malformed_cache_fails_before_output_case_4(self):
        tmp_path = self.tmp_path
        payload = {"word": "POM", "original": "casă", "status": "ok", "html": "<p>Casă.</p>"}
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "CASA.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ValueError):
            prepare_dataset(source, tmp_path / "dataset", source_version="v1", dex_cache=cache)
        self.assertFalse((tmp_path / "dataset").exists())

    def test_full_dictionary_pages_extract_definition_spans_and_never_navigation(self):
        tmp_path = self.tmp_path
        source = write_csv(
            tmp_path / "input.csv",
            ["word_id", "word", "type"],
            [[1, "casă", "N"], [2, "pom", "N"], [3, "gol", "A"]],
        )
        cache = tmp_path / "cache"
        cache.mkdir()
        htmls = [
            (
                "CASA",
                "casă",
                '<html><body><nav>LOGIN</nav><span class="tree-def html">Clădire <b>de locuit</b>.</span><span class="tree-def">Locuință.</span><div class="defWrapper"><span class="def">Duplicate raw.</span></div><footer>CONTACT</footer></body></html>',
            ),
            (
                "POM",
                "pom",
                '<html><body><nav>LOGIN</nav><div class="defWrapper"><span class="def">Arbore<br>fructifer.</span></div></body></html>',
            ),
            (
                "GOL",
                "gol",
                "<html><body><nav>LOGIN</nav><p>Page with no definitions</p></body></html>",
            ),
        ]
        for key, word, html in htmls:
            (cache / f"{key}.json").write_text(
                json.dumps(dict(word=key, original=word, status="ok", html=html))
            )
        result = prepare_dataset(source, tmp_path / "dataset", source_version="v1", dex_cache=cache)
        evidence = read_csv(result["evidence"])
        self.assertEqual(
            [row["definition"] for row in evidence],
            ["Clădire de locuit. Locuință.", "Arbore fructifer.", ""],
        )
        self.assertEqual(evidence[2]["definition_status"], "empty")

    def test_existing_output_is_refused_before_reading_inputs(self):
        tmp_path = self.tmp_path
        output = tmp_path / "dataset"
        output.mkdir()
        marker = output / "keep.txt"
        marker.write_text("keep")
        with self.assertRaisesRegex(FileExistsError, "dataset"):
            prepare_dataset(tmp_path / "missing-input.csv", output, source_version="v1")
        self.assertEqual(list(output.iterdir()), [marker])
        self.assertEqual(marker.read_text(), "keep")

    def test_artifact_write_failure_does_not_publish_partial_dataset(self):
        tmp_path = self.tmp_path
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        output = tmp_path / "dataset"
        original_write = Path.write_text

        def fail_manifest(path, *args, **kwargs):
            if path.name == "manifest.json":
                raise OSError("disk full")
            return original_write(path, *args, **kwargs)

        self.enterContext(patch.object(Path, "write_text", fail_manifest))
        with self.assertRaisesRegex(OSError, "disk full"):
            prepare_dataset(source, output, source_version="v1")
        self.assertFalse(output.exists())
        self.assertEqual(list(tmp_path.iterdir()), [source])

    def test_duplicate_exact_dictionary_records_remain_ambiguous(self):
        tmp_path = self.tmp_path
        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        cache = tmp_path / "cache"
        cache.mkdir()
        for name, text in [("first", "Locuință."), ("second", "Instituție.")]:
            (cache / f"{name}.json").write_text(
                json.dumps(dict(word="CASA", original="casă", status="ok", html=f"<p>{text}</p>"))
            )
        result = prepare_dataset(source, tmp_path / "dataset", source_version="v1", dex_cache=cache)
        self.assertEqual(read_csv(result["evidence"])[0]["definition_status"], "ambiguous")
        self.assertEqual(read_csv(result["evidence"])[0]["definition"], "")

    def test_cache_html_is_processed_incrementally_without_retaining_unrelated_pages(self):
        tmp_path = self.tmp_path
        import tracemalloc

        source = write_csv(tmp_path / "input.csv", ["word_id", "word", "type"], [[1, "casă", "N"]])
        cache = tmp_path / "cache"
        cache.mkdir()
        for index in range(24):
            word = f"word{index}"
            (cache / f"{word}.json").write_text(
                json.dumps(dict(word=word.upper(), original=word, status="ok", html="x" * 262144))
            )
        tracemalloc.start()
        try:
            result = prepare_dataset(
                source, tmp_path / "dataset", source_version="v1", dex_cache=cache
            )
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(read_csv(result["evidence"])[0]["definition_status"], "missing")
        self.assertLess(peak, 4 * 1024 * 1024)
