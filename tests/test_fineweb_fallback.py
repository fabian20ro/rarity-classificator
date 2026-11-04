import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.fineweb_fallback import evaluate_fineweb_fallback

REVISION = "af9c13333eb981300149d5ca60a8e9d659b276b9"


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


class FineWebFallbackTests(unittest.TestCase):
    def inputs(self, root, labels=(3, 4, 5, 5)):
        reference = write_csv(
            root / "reference.csv",
            [
                dict(
                    word_id=i,
                    word=f"word{i}",
                    initial_level=y,
                    working_level=y,
                    reference_kind=(
                        "shortlist_form_review" if i == 1 else "initial_opaque_form_pos"
                    ),
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
            [
                dict(word_id=i, word=f"word{i}", level=y)
                for i, y in enumerate(labels, 1)
            ],
        )
        groups = write_csv(
            root / "groups.csv",
            [
                dict(word_id=i, word=f"word{i}", group=f"g{i}")
                for i in range(1, len(labels) + 1)
            ],
        )
        evidence = root / "evidence"
        evidence.mkdir()
        # Inventory includes an unlabelled form: never fit on it or drop pilot rows.
        write_csv(
            evidence / "vocabulary.csv",
            [
                dict(word_id=i, word=f"word{i}", type="N")
                for i in range(1, len(labels) + 2)
            ],
        )
        self.evidence(
            evidence,
            [
                dict(
                    word_id=i,
                    word=f"word{i}",
                    type="N",
                    count=0,
                    document_count=0,
                    host_count=0,
                    token_total=100000,
                    frequency="",
                    status="unobserved",
                )
                for i in range(1, len(labels) + 2)
            ],
        )
        return reference, frequency, evidence, first, groups

    def evidence(self, directory, rows):
        write_csv(directory / "frequencies.csv", rows)
        self.manifest(directory)

    def manifest(self, directory):
        digest = lambda name: hashlib.sha256(
            (directory / name).read_bytes()
        ).hexdigest()
        manifest = dict(
            schema=1,
            policy="fineweb-exact-forms-v1",
            vocabulary_sha256=digest("vocabulary.csv"),
            protocol=dict(
                revision=REVISION,
                primary_years=[2020, 2021, 2022, 2023, 2024],
                support=dict(count=5, documents=3, hosts=2),
            ),
            counts=dict(balanced_sample=True),
            artifacts={
                name: digest(name) for name in ["vocabulary.csv", "frequencies.csv"]
            },
        )
        (directory / "manifest.json").write_text(json.dumps(manifest))

    def test_unobserved_forms_keep_four_with_complete_three_view_and_four_five_reports(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root)
            result = evaluate_fineweb_fallback(*paths, root / "out")
            for view in (
                "revised_working",
                "original_round_final",
                "first_independent",
            ):
                rows = read_csv(root / f"out/{view}/predictions.csv")
                self.assertEqual([r["candidate_level"] for r in rows], ["4"] * 4)
                metric = result["views"][view]["all"]["candidate"]
                self.assertEqual(metric["covered"], 4)
                self.assertEqual(metric["missing"], 0)
                self.assertEqual(metric["mae"], 0.75)
                self.assertEqual(
                    metric["four_five"]["human_rows_4_5_prediction_columns_1_2_3_4_5"],
                    [[0, 0, 0, 1, 0], [0, 0, 0, 2, 0]],
                )
                self.assertIsNone(metric["precision5"])
            self.assertTrue((root / "out/manifest.json").exists())

    def test_supported_tail_uses_fold_fitted_thresholds_and_unseen_stays_four(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root, [3] * 6 + [5] * 6 + [1])
            rows = read_csv(paths[2] / "frequencies.csv")
            for row in rows[:12]:
                count = 1000 if int(row["word_id"]) <= 6 else 5
                row.update(
                    count=count,
                    document_count=3,
                    host_count=2,
                    frequency=count / 100000,
                    status="observed",
                )
            self.evidence(paths[2], rows)
            result = evaluate_fineweb_fallback(*paths, root / "out")
            predicted = read_csv(root / "out/revised_working/predictions.csv")
            self.assertEqual(
                [int(r["candidate_level"]) for r in predicted], [3] * 6 + [5] * 6 + [4]
            )
            self.assertEqual(predicted[-1]["candidate_route"], "unsupported_four")
            self.assertEqual(predicted[0]["candidate_route"], "fineweb_thresholds")
            metric = result["views"]["revised_working"]["all"]["candidate"]
            self.assertEqual(metric["precision5"], 1)
            self.assertEqual(metric["recall5"], 1)
            self.assertEqual(metric["severe_errors"], 1)
            fold = json.loads((root / "out/revised_working/folds/7.json").read_text())
            self.assertNotIn(7, fold["fineweb"]["observed_train_ids"])
            self.assertNotIn(13, fold["fineweb"]["observed_train_ids"])
            self.assertEqual(len(fold["fineweb"]["observed_train_ids"]), 11)

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
                    document_count=3,
                    host_count=2,
                    frequency=count / 100000,
                    status="observed",
                )
            self.evidence(paths[2], evidence)
            groups = read_csv(paths[4])
            groups[1]["group"] = "g1"
            write_csv(paths[4], groups)
            evaluate_fineweb_fallback(*paths, root / "before")
            predictions = read_csv(root / "before/revised_working/predictions.csv")
            for row in predictions[-3:]:
                self.assertEqual(row["baseline_level"], row["candidate_level"])
                self.assertEqual(row["candidate_route"], "wordfreq_thresholds")
            fold = json.loads(
                (root / "before/revised_working/folds/13.json").read_text()
            )
            self.assertEqual(fold["wordfreq"]["observed_train_ids"], [14, 15])
            for path, fields in [
                (paths[0], ["initial_level", "working_level"]),
                (paths[3], ["level"]),
            ]:
                rows = read_csv(path)
                for row in rows[:2]:
                    row.update({field: 1 for field in fields})
                write_csv(path, rows)
            evaluate_fineweb_fallback(*paths, root / "after")
            for view in (
                "revised_working",
                "original_round_final",
                "first_independent",
            ):
                for i in (1, 2):
                    before = json.loads(
                        (root / f"before/{view}/folds/{i}.json").read_text()
                    )
                    after = json.loads(
                        (root / f"after/{view}/folds/{i}.json").read_text()
                    )
                    self.assertEqual(before, after)
                    self.assertIsNotNone(before["fineweb"])
                    self.assertNotIn(1, before["fineweb"]["observed_train_ids"])
                    self.assertNotIn(2, before["fineweb"]["observed_train_ids"])

    def test_changed_counts_or_unbound_inventory_are_rejected_before_publication(self):
        for change in ("counts", "inventory", "subset", "protocol", "artifact_path"):
            with self.subTest(change=change), TemporaryDirectory() as temp:
                root = Path(temp)
                paths = self.inputs(root)
                directory = paths[2]
                if change in ("counts", "inventory"):
                    name = "frequencies.csv" if change == "counts" else "vocabulary.csv"
                    path = directory / name
                    path.write_text(path.read_text().replace("word1", "altered"))
                elif change == "subset":
                    self.evidence(
                        directory, read_csv(directory / "frequencies.csv")[:-1]
                    )
                else:
                    path = directory / "manifest.json"
                    manifest = json.loads(path.read_text())
                    if change == "protocol":
                        manifest["protocol"]["primary_years"] = [2013]
                    else:
                        manifest["artifacts"]["../reference.csv"] = "a" * 64
                    path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    evaluate_fineweb_fallback(*paths, root / "out")
                self.assertFalse((root / "out").exists())

    def test_inconsistent_counts_frequencies_or_label_identities_fail_fast(self):
        cases = [
            ("evidence", "count", "-1"),
            ("evidence", "count", "1.5"),
            ("evidence", "document_count", "1"),
            ("evidence", "host_count", "1"),
            ("evidence", "frequency", "0.1"),
            ("evidence", "frequency", "nan"),
            ("evidence", "status", "observed"),
            ("evidence", "token_total", "-1"),
            ("evidence", "token_total", "99999"),
            ("evidence", "assistant_estimate", "5"),
            ("frequency", "wordfreq", "nan"),
            ("frequency", "wordfreq", "-1"),
            ("frequency", "human_level", "5"),
            ("groups", "group", ""),
            ("first", "word", "wrong"),
            ("groups", "word", "wrong"),
            ("reference", "reference_kind", "invented"),
        ]
        for source, field, value in cases:
            with (
                self.subTest(source=source, field=field, value=value),
                TemporaryDirectory() as temp,
            ):
                root = Path(temp)
                paths = self.inputs(root)
                path = {
                    "evidence": paths[2] / "frequencies.csv",
                    "frequency": paths[1],
                    "reference": paths[0],
                    "first": paths[3],
                    "groups": paths[4],
                }[source]
                rows = read_csv(path)
                rows[0][field] = value
                if source == "evidence":
                    self.evidence(paths[2], rows)
                else:
                    write_csv(path, rows)
                with self.assertRaises(ValueError):
                    evaluate_fineweb_fallback(*paths, root / "out")
                self.assertFalse((root / "out").exists())

    def test_replay_pins_source_protocol_training_gate_and_input_hashes(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root)
            evaluate_fineweb_fallback(*paths, root / "one")
            evaluate_fineweb_fallback(*paths, root / "two")
            protocol = json.loads((root / "one/protocol.json").read_text())
            self.assertEqual(protocol["support"], dict(count=5, documents=3, hosts=2))
            self.assertEqual(
                protocol["candidate_training_minimum"], dict(rows=10, distinct_levels=2)
            )
            self.assertEqual(protocol["folds"], "leave-one-group-out")
            self.assertFalse(protocol["parameter_search"])
            manifest = json.loads((root / "one/manifest.json").read_text())
            self.assertEqual(
                manifest["inputs"][str(paths[0].resolve())],
                hashlib.sha256(paths[0].read_bytes()).hexdigest(),
            )
            self.assertIn(
                str((paths[2] / "manifest.json").resolve()), manifest["inputs"]
            )
            for path in (root / "one").rglob("*"):
                if path.is_file():
                    self.assertEqual(
                        path.read_bytes(),
                        (root / "two" / path.relative_to(root / "one")).read_bytes(),
                    )
            with self.assertRaises(FileExistsError):
                evaluate_fineweb_fallback(*paths, root / "one")

    def test_support_requires_each_floor_and_reports_coverage_separately_from_scores(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root, [3] * 6 + [5] * 9)
            rows = read_csv(paths[2] / "frequencies.csv")
            for row in rows[:15]:
                count = 1000 if int(row["word_id"]) <= 6 else 5
                row.update(
                    count=count,
                    document_count=3,
                    host_count=2,
                    frequency=count / 100000,
                    status="observed",
                )
            rows[12].update(count=4, frequency=0.00004)
            rows[13]["document_count"] = 2
            rows[14]["host_count"] = 1
            self.evidence(paths[2], rows)
            result = evaluate_fineweb_fallback(*paths, root / "out")
            saved = read_csv(root / "out/revised_working/predictions.csv")
            self.assertEqual(
                [r["candidate_route"] for r in saved[-3:]], ["unsupported_four"] * 3
            )
            coverage = result["views"]["revised_working"]["evidence"]
            self.assertEqual(coverage["observed"], 15)
            self.assertEqual(coverage["supported"], 12)
            self.assertEqual(coverage["wordfreq_missing_supported"], 12)
            self.assertEqual(coverage["candidate_changed"], 12)
            self.assertEqual(
                result["views"]["revised_working"]["all"]["candidate"]["covered"], 15
            )

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
                        document_count=3,
                        host_count=2,
                        frequency=0.00005,
                        status="observed",
                    )
                self.evidence(paths[2], rows)
                evaluate_fineweb_fallback(*paths, root / "out")
                predictions = read_csv(root / "out/revised_working/predictions.csv")
                self.assertEqual(
                    [r["candidate_level"] for r in predictions], ["4"] * len(labels)
                )
                self.assertEqual(
                    {r["candidate_route"] for r in predictions},
                    {"insufficient_training_four"},
                )
                fold = json.loads(
                    (root / "out/revised_working/folds/1.json").read_text()
                )
                self.assertEqual(
                    fold["fineweb_train_ids"], list(range(2, len(labels) + 1))
                )
                self.assertIsNone(fold["fineweb"])
                self.assertEqual(fold["candidate_route"], "insufficient_training_four")

    def test_incomplete_sample_keeps_missing_forms_four_even_with_training_support(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root, [3] * 6 + [5] * 6)
            rows = read_csv(paths[2] / "frequencies.csv")
            for row in rows[:-1]:
                count = 1000 if int(row["word_id"]) <= 6 else 5
                row.update(
                    count=count,
                    document_count=3,
                    host_count=2,
                    frequency=count / 100000,
                    status="observed",
                )
            self.evidence(paths[2], rows)
            manifest_path = paths[2] / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["counts"]["balanced_sample"] = False
            manifest_path.write_text(json.dumps(manifest))
            result = evaluate_fineweb_fallback(*paths, root / "out")
            predictions = read_csv(root / "out/revised_working/predictions.csv")
            self.assertEqual(
                {r["candidate_route"] for r in predictions},
                {"insufficient_sample_four"},
            )
            self.assertEqual([r["candidate_level"] for r in predictions], ["4"] * 12)
            self.assertFalse(result["protocol"]["balanced_sample"])

    def test_cli_compares_csv_artifacts_without_http_or_database_access(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from classificator.cli import main

        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root)
            with (
                patch(
                    "requests.Session.request",
                    side_effect=AssertionError("HTTP forbidden"),
                ),
                patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
                redirect_stdout(StringIO()),
            ):
                code = main(
                    [
                        "--output-dir",
                        str(root / "logs"),
                        "evaluation-fineweb-fallback",
                        "--reference-csv",
                        str(paths[0]),
                        "--features-csv",
                        str(paths[1]),
                        "--evidence-dir",
                        str(paths[2]),
                        "--first-independent-csv",
                        str(paths[3]),
                        "--groups-csv",
                        str(paths[4]),
                        "--campaign-dir",
                        str(root / "out"),
                    ]
                )
            self.assertEqual(code, 0)
            rows = read_csv(root / "out/revised_working/predictions.csv")
            self.assertEqual([r["candidate_level"] for r in rows], ["4"] * 4)
