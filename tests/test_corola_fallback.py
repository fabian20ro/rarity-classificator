import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.corola_fallback import evaluate_corola_fallback


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


class CoRoLaFallbackTests(unittest.TestCase):
    def inputs(self, root, labels=(3, 4, 5, 5)):
        reference = write_csv(
            root / "reference.csv",
            [
                dict(
                    word_id=i,
                    word=f"word{i}",
                    initial_level=y,
                    working_level=y,
                    reference_kind="initial_opaque_form_pos",
                )
                for i, y in enumerate(labels, 1)
            ],
        )
        frequency = write_csv(
            root / "frequency.csv",
            [
                dict(word_id=i, word=f"word{i}", wordfreq="", rebus="")
                for i in range(1, len(labels) + 1)
            ],
        )
        first = write_csv(
            root / "first.csv",
            [dict(word_id=i, word=f"word{i}", level=y) for i, y in enumerate(labels, 1)],
        )
        groups = write_csv(
            root / "groups.csv",
            [dict(word_id=i, word=f"word{i}", group=f"g{i}") for i in range(1, len(labels) + 1)],
        )
        evidence = root / "evidence"
        evidence.mkdir()
        write_csv(
            evidence / "vocabulary.csv",
            [dict(word_id=i, word=f"word{i}", type="N") for i in range(1, len(labels) + 2)],
        )
        self.evidence(
            evidence,
            [
                dict(
                    word_id=i,
                    word=f"word{i}",
                    type="N",
                    count=0,
                    token_total=100000,
                    frequency=0,
                    status="unobserved",
                )
                for i in range(1, len(labels) + 2)
            ],
        )
        return reference, frequency, evidence, first, groups

    def evidence(self, directory, rows):
        write_csv(directory / "frequencies.csv", rows)
        digest = lambda name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        manifest = dict(
            schema=1,
            policy="corola-exact-forms-v1",
            source=dict(
                record="7091535",
                member="corola_word_freq_all_lowercase.tsv",
                license="cc-by-nc-nd-4.0",
                source_sha256="a" * 64,
                archive_md5="0034d61d1825b38386dfa0bc2606a314",
            ),
            vocabulary_sha256=digest("vocabulary.csv"),
            token_total=100000,
            artifacts={name: digest(name) for name in ["vocabulary.csv", "frequencies.csv"]},
        )
        (directory / "manifest.json").write_text(json.dumps(manifest))

    def test_unobserved_keeps_complete_scores_and_three_view_rare_diagnostics(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root)
            result = evaluate_corola_fallback(*paths, root / "out")
            for view in ("revised_working", "original_round_final", "first_independent"):
                rows = read_csv(root / f"out/{view}/predictions.csv")
                self.assertEqual([r["candidate_level"] for r in rows], ["4"] * 4)
                metric = result["views"][view]["all"]["candidate"]
                self.assertEqual(metric["covered"], 4)
                self.assertEqual(metric["mae"], 0.75)
                self.assertEqual(
                    metric["four_five"]["human_rows_4_5_prediction_columns_1_2_3_4_5"],
                    [[0, 0, 0, 1, 0], [0, 0, 0, 2, 0]],
                )

    def test_corrupt_or_wrong_source_evidence_never_publishes_comparison(self):
        for change in (
            "hash",
            "source",
            "subset",
            "denominator",
            "count",
            "frequency",
            "status",
            "pos",
            "path",
        ):
            with self.subTest(change=change), TemporaryDirectory() as temp:
                root = Path(temp)
                paths = self.inputs(root)
                directory = paths[2]
                rows = read_csv(directory / "frequencies.csv")
                if change == "subset":
                    self.evidence(directory, rows[:-1])
                elif change in ("denominator", "count", "frequency", "status", "pos"):
                    field, value = {
                        "denominator": ("token_total", 99999),
                        "count": ("count", -1),
                        "frequency": ("frequency", "nan"),
                        "status": ("status", "observed"),
                        "pos": ("type", "V"),
                    }[change]
                    rows[0][field] = value
                    self.evidence(directory, rows)
                elif change == "hash":
                    (directory / "frequencies.csv").write_text("broken")
                else:
                    path = directory / "manifest.json"
                    manifest = json.loads(path.read_text())
                    if change == "source":
                        manifest["source"]["member"] = "corola_lemma_freq_all_lowercase.tsv"
                    else:
                        manifest["artifacts"]["../reference.csv"] = "a" * 64
                    path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    evaluate_corola_fallback(*paths, root / "out")
                self.assertFalse((root / "out").exists())

    def test_supported_tail_uses_fold_fitted_thresholds_and_unseen_stays_four(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root, [3] * 6 + [5] * 6 + [1])
            rows = read_csv(paths[2] / "frequencies.csv")
            for row in rows[:12]:
                count = 1000 if int(row["word_id"]) <= 6 else 5
                row.update(
                    count=count,
                    frequency=count / 100000,
                    status="observed",
                )
            self.evidence(paths[2], rows)
            result = evaluate_corola_fallback(*paths, root / "out")
            predicted = read_csv(root / "out/revised_working/predictions.csv")
            self.assertEqual(
                [int(r["candidate_level"]) for r in predicted], [3] * 6 + [5] * 6 + [4]
            )
            self.assertEqual(predicted[-1]["candidate_route"], "unsupported_four")
            self.assertEqual(predicted[0]["candidate_route"], "corola_thresholds")
            metric = result["views"]["revised_working"]["all"]["candidate"]
            self.assertEqual(metric["precision5"], 1)
            self.assertEqual(metric["recall5"], 1)
            self.assertEqual(metric["severe_errors"], 1)
            fold = json.loads((root / "out/revised_working/folds/7.json").read_text())
            self.assertNotIn(7, fold["corola"]["observed_train_ids"])
            self.assertNotIn(13, fold["corola"]["observed_train_ids"])
            self.assertEqual(len(fold["corola"]["observed_train_ids"]), 11)

    def test_direct_path_is_shared_and_group_labels_do_not_enter_either_fit(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root, [3] * 6 + [5] * 6 + [1, 2, 3])
            frequencies = read_csv(paths[1])
            for row, value in zip(frequencies[-3:], [0.1, 0.01, 0.001]):
                row["wordfreq"] = value
            write_csv(paths[1], frequencies)
            evidence = read_csv(paths[2] / "frequencies.csv")
            for row in evidence[:12]:
                count = 1000 if int(row["word_id"]) <= 6 else 5
                row.update(
                    count=count,
                    frequency=count / 100000,
                    status="observed",
                )
            self.evidence(paths[2], evidence)
            groups = read_csv(paths[4])
            groups[1]["group"] = "g1"
            write_csv(paths[4], groups)
            evaluate_corola_fallback(*paths, root / "before")
            predictions = read_csv(root / "before/revised_working/predictions.csv")
            for row in predictions[-3:]:
                self.assertEqual(row["baseline_level"], row["candidate_level"])
                self.assertEqual(row["candidate_route"], "wordfreq_thresholds")
            fold = json.loads((root / "before/revised_working/folds/13.json").read_text())
            self.assertEqual(fold["wordfreq"]["observed_train_ids"], [14, 15])
            for path, fields in [
                (paths[0], ["initial_level", "working_level"]),
                (paths[3], ["level"]),
            ]:
                rows = read_csv(path)
                for row in rows[:2]:
                    row.update({field: 1 for field in fields})
                write_csv(path, rows)
            evaluate_corola_fallback(*paths, root / "after")
            for view in (
                "revised_working",
                "original_round_final",
                "first_independent",
            ):
                for i in (1, 2):
                    before = json.loads((root / f"before/{view}/folds/{i}.json").read_text())
                    after = json.loads((root / f"after/{view}/folds/{i}.json").read_text())
                    self.assertEqual(before, after)
                    self.assertIsNotNone(before["corola"])
                    self.assertNotIn(1, before["corola"]["observed_train_ids"])
                    self.assertNotIn(2, before["corola"]["observed_train_ids"])

    def test_insufficient_or_single_class_training_retains_four_and_records_support(
        self,
    ):
        for labels in ([3] * 5 + [5] * 5, [5] * 12):
            with self.subTest(labels=labels), TemporaryDirectory() as temp:
                root = Path(temp)
                paths = self.inputs(root, labels)
                rows = read_csv(paths[2] / "frequencies.csv")
                for row in rows[:-1]:
                    row.update(
                        count=5,
                        frequency=0.00005,
                        status="observed",
                    )
                self.evidence(paths[2], rows)
                evaluate_corola_fallback(*paths, root / "out")
                predictions = read_csv(root / "out/revised_working/predictions.csv")
                self.assertEqual([r["candidate_level"] for r in predictions], ["4"] * len(labels))
                self.assertEqual(
                    {r["candidate_route"] for r in predictions},
                    {"insufficient_training_four"},
                )
                fold = json.loads((root / "out/revised_working/folds/1.json").read_text())
                self.assertEqual(fold["corola_train_ids"], list(range(2, len(labels) + 1)))
                self.assertIsNone(fold["corola"])
                self.assertEqual(fold["candidate_route"], "insufficient_training_four")

    def test_low_positive_count_is_coverage_but_not_fallback_support(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root, [3] * 6 + [5] * 6 + [5])
            rows = read_csv(paths[2] / "frequencies.csv")
            for row in rows[:13]:
                count = 1000 if int(row["word_id"]) <= 6 else 5
                row.update(count=count, frequency=count / 100000, status="observed")
            rows[12].update(count=4, frequency=0.00004)
            self.evidence(paths[2], rows)
            result = evaluate_corola_fallback(*paths, root / "out")
            predictions = read_csv(root / "out/revised_working/predictions.csv")
            self.assertEqual(predictions[-1]["candidate_level"], "4")
            self.assertEqual(predictions[-1]["candidate_route"], "unsupported_four")
            evidence = result["views"]["revised_working"]["evidence"]
            self.assertEqual((evidence["observed"], evidence["supported"]), (13, 12))
            self.assertEqual(result["views"]["revised_working"]["all"]["candidate"]["covered"], 13)

    def test_conflicting_counts_for_identical_form_pos_rows_are_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root)
            vocabulary = read_csv(paths[2] / "vocabulary.csv")
            vocabulary[-1].update(word="word1", type="V")
            write_csv(paths[2] / "vocabulary.csv", vocabulary)
            rows = read_csv(paths[2] / "frequencies.csv")
            rows[-1].update(word="word1", type="V", count=5, frequency=0.00005, status="observed")
            self.evidence(paths[2], rows)
            with self.assertRaisesRegex(ValueError, "across inventory POS"):
                evaluate_corola_fallback(*paths, root / "out")
            self.assertFalse((root / "out").exists())

    def test_replay_records_source_inputs_and_never_overwrites(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root)
            for name in ("one", "two"):
                evaluate_corola_fallback(*paths, root / name)
            manifest = json.loads((root / "one/manifest.json").read_text())
            self.assertEqual(
                manifest["inputs"][str((paths[2] / "manifest.json").resolve())],
                hashlib.sha256((paths[2] / "manifest.json").read_bytes()).hexdigest(),
            )
            protocol = json.loads((root / "one/protocol.json").read_text())
            self.assertEqual(protocol["support"], {"count": 5})
            self.assertFalse(protocol["parameter_search"])
            for path in (root / "one").rglob("*"):
                if path.is_file():
                    self.assertEqual(
                        path.read_bytes(),
                        (root / "two" / path.relative_to(root / "one")).read_bytes(),
                    )
            with self.assertRaises(FileExistsError):
                evaluate_corola_fallback(*paths, root / "one")
