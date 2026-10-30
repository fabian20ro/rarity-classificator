import csv
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.local_fallback import evaluate_local_fallback


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


@unittest.skipUnless(
    importlib.util.find_spec("sklearn"), "Install evaluation extra for lexical tree"
)
class LocalFallbackTests(unittest.TestCase):
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
        evidence = root / "evidence"
        evidence.mkdir()
        self.evidence(
            evidence,
            [
                dict(
                    word_id=i,
                    word=f"word{i}",
                    loc_pos="N",
                    aligned_pos="N",
                    alignment="source_bounded",
                    aligned_senses=1,
                    other_definition_count=0,
                    all_restricted=0,
                    all_specialist=0,
                )
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
        return reference, frequency, evidence, first, groups

    def evidence(self, directory, rows):
        path = write_csv(directory / "evidence.csv", rows)
        (directory / "manifest.json").write_text(
            json.dumps(
                dict(
                    policy="local-lexical-evidence-v1",
                    inputs={},
                    implementation={},
                    artifacts={
                        "evidence.csv": hashlib.sha256(path.read_bytes()).hexdigest()
                    },
                )
            )
        )

    def test_small_tail_keeps_four_and_reports_four_five_without_dropping_other_predictions(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root)
            result = evaluate_local_fallback(*paths, root / "out")
            latest = result["views"]["revised_working"]
            for method in ("baseline", "candidate"):
                all_scores = latest["all"][method]
                self.assertEqual(all_scores["covered"], 4)
                self.assertEqual(all_scores["missing"], 0)
                self.assertEqual(all_scores["mae"], 0.75)
                self.assertEqual(all_scores["exact"], 1)
                self.assertEqual(all_scores["severe_errors"], 0)
                rare = all_scores["four_five"]
                self.assertEqual(
                    rare["human_rows_4_5_prediction_columns_1_2_3_4_5"],
                    [[0, 0, 0, 1, 0], [0, 0, 0, 2, 0]],
                )
                self.assertIsNone(all_scores["precision5"])
                self.assertEqual(all_scores["recall5"], 0)
            self.assertEqual(latest["clarified"]["total"], 1)
            self.assertEqual(latest["opaque"]["total"], 3)
            self.assertEqual(latest["wordfreq_missing"]["total"], 4)
            saved = list(
                csv.DictReader((root / "out/revised_working/predictions.csv").open())
            )
            self.assertEqual([r["candidate_level"] for r in saved], ["4"] * 4)
            self.assertTrue((root / "out/manifest.json").exists())

    def test_supported_tail_uses_lower_median_tree_leaves_and_unknown_alignment_stays_four(
        self,
    ):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root, labels=[3] * 6 + [5] * 6 + [1])
            evidence = list(csv.DictReader((paths[2] / "evidence.csv").open()))
            for row in evidence:
                i = int(row["word_id"])
                row["other_definition_count"] = 100 if i <= 6 else 0
                row["all_restricted"] = int(7 <= i <= 12)
            evidence[-1].update(
                alignment="unresolved", aligned_pos="", aligned_senses=0
            )
            self.evidence(paths[2], evidence)
            result = evaluate_local_fallback(*paths, root / "out")
            saved = list(
                csv.DictReader((root / "out/revised_working/predictions.csv").open())
            )
            self.assertEqual(
                [int(r["candidate_level"]) for r in saved], [3] * 6 + [5] * 6 + [4]
            )
            self.assertEqual(saved[-1]["candidate_route"], "unresolved_four")
            metric = result["views"]["revised_working"]["all"]["candidate"]
            self.assertEqual(metric["precision5"], 1)
            self.assertEqual(metric["recall5"], 1)
            self.assertEqual(metric["severe_errors"], 1)
            self.assertEqual(metric["mae"], 3 / 13)
            fold = json.loads((root / "out/revised_working/folds/7.json").read_text())
            self.assertNotIn(7, fold["tree"]["train_ids"])
            self.assertNotIn(13, fold["tree"]["train_ids"])
            self.assertEqual(len(fold["tree"]["leaf_train_ids"]), 5)
            self.assertEqual(fold["tree"]["leaf_level"], 5)

    def test_group_labels_never_enter_fits_and_direct_frequency_route_is_shared(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root, labels=[3] * 6 + [5] * 6 + [1, 2, 3])
            frequencies = list(csv.DictReader(paths[1].open()))
            for row, frequency in zip(frequencies[-3:], [0.1, 0.01, 0.001]):
                row["wordfreq"] = frequency
            write_csv(paths[1], frequencies)
            groups = list(csv.DictReader(paths[4].open()))
            groups[1]["group"] = "g1"
            write_csv(paths[4], groups)
            evaluate_local_fallback(*paths, root / "before")
            predictions = list(
                csv.DictReader((root / "before/revised_working/predictions.csv").open())
            )
            for row in predictions[-3:]:
                self.assertEqual(row["baseline_level"], row["candidate_level"])
                self.assertEqual(row["candidate_route"], "frequency_thresholds")
            direct_fold = json.loads(
                (root / "before/revised_working/folds/13.json").read_text()
            )
            self.assertEqual(direct_fold["wordfreq"]["observed_train_ids"], [14, 15])
            self.assertEqual(direct_fold["tree"]["route"], "frequency_thresholds")
            refs = list(csv.DictReader(paths[0].open()))
            for row in refs[:2]:
                row["initial_level"] = row["working_level"] = 1
            write_csv(paths[0], refs)
            first = list(csv.DictReader(paths[3].open()))
            for row in first[:2]:
                row["level"] = 1
            write_csv(paths[3], first)
            evaluate_local_fallback(*paths, root / "after")
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
                    self.assertNotIn(1, before["train_ids"])
                    self.assertNotIn(2, before["train_ids"])
                    self.assertNotIn(1, before["tree"]["train_ids"])
                    self.assertNotIn(2, before["tree"]["train_ids"])

    def test_changed_evidence_is_rejected_before_output_publication(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root)
            path = paths[2] / "evidence.csv"
            path.write_text(path.read_text().replace("source_bounded", "unresolved"))
            with self.assertRaisesRegex(ValueError, "hash"):
                evaluate_local_fallback(*paths, root / "out")
            self.assertFalse((root / "out").exists())

    def test_invalid_contracts_fail_before_artifacts_are_published(self):
        cases = [
            ("evidence", "alignment", "guessed"),
            ("evidence", "all_restricted", "2"),
            ("evidence", "other_definition_count", "-1"),
            ("evidence", "aligned_senses", "0"),
            ("evidence", "loc_pos", "N|V"),
            ("evidence", "assistant_estimate", "5"),
            ("frequency", "wordfreq", "nan"),
            ("frequency", "wordfreq", "-1"),
            ("frequency", "human_level", "5"),
            ("groups", "group", ""),
            ("groups", "word", "wrong"),
            ("first", "word", "wrong"),
            ("reference", "reference_kind", "invented"),
        ]
        for source, field, value in cases:
            with self.subTest(source=source, field=field), TemporaryDirectory() as temp:
                root = Path(temp)
                paths = self.inputs(root)
                path = {
                    "reference": paths[0],
                    "frequency": paths[1],
                    "evidence": paths[2] / "evidence.csv",
                    "first": paths[3],
                    "groups": paths[4],
                }[source]
                rows = list(csv.DictReader(path.open()))
                rows[0][field] = value
                if source == "evidence":
                    self.evidence(paths[2], rows)
                else:
                    write_csv(path, rows)
                with self.assertRaises(ValueError):
                    evaluate_local_fallback(*paths, root / "out")
                self.assertFalse((root / "out").exists())

    def test_four_five_report_keeps_underestimates_and_lower_median_ties(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root, labels=[3] * 6 + [4] + [5] * 6)
            result = evaluate_local_fallback(*paths, root / "out")
            metric = result["views"]["revised_working"]["all"]["candidate"]
            self.assertEqual(metric["four_five"]["exact"], 0)
            self.assertEqual(
                metric["four_five"]["human_rows_4_5_prediction_columns_1_2_3_4_5"],
                [[0, 0, 1, 0, 0], [0, 0, 6, 0, 0]],
            )
            self.assertEqual(metric["precision4"], 0)
            self.assertEqual(metric["recall4"], 0)
            self.assertEqual(metric["severe_errors"], 6)
            fold = json.loads((root / "out/revised_working/folds/7.json").read_text())
            self.assertEqual(fold["tree"]["leaf_level"], 3)

    def test_false_fives_on_common_forms_are_explicit(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root, labels=[2, 4] + [5] * 13)
            result = evaluate_local_fallback(*paths, root / "out")
            metric = result["views"]["revised_working"]["all"]["candidate"]
            self.assertEqual(metric["predicted5"], 15)
            self.assertEqual(metric["true5"], 13)
            self.assertEqual(metric["precision5"], 13 / 15)
            self.assertEqual(metric["recall5"], 1)
            self.assertEqual(metric["false5_on_human1_to3"], 1)
            self.assertEqual(metric["false5_on_human4"], 1)
            self.assertEqual(metric["four_five"]["exact"], 13)

    def test_replay_is_deterministic_and_protocol_pins_the_single_candidate(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root)
            evaluate_local_fallback(*paths, root / "one")
            evaluate_local_fallback(*paths, root / "two")
            protocol = json.loads((root / "one/protocol.json").read_text())
            self.assertEqual(protocol["candidate"]["max_depth"], 2)
            self.assertEqual(protocol["candidate"]["min_samples_leaf"], 5)
            self.assertEqual(protocol["candidate"]["criterion"], "absolute_error")
            self.assertEqual(protocol["candidate"]["random_state"], 0)
            self.assertEqual(protocol["folds"], "leave-one-group-out")
            self.assertEqual(protocol["parameter_search"], False)
            for path in (root / "one").rglob("*"):
                if path.is_file():
                    self.assertEqual(
                        path.read_bytes(),
                        (root / "two" / path.relative_to(root / "one")).read_bytes(),
                    )
            with self.assertRaises(FileExistsError):
                evaluate_local_fallback(*paths, root / "one")
