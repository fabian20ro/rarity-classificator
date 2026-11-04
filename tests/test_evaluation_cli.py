import tempfile
import unittest
from pathlib import Path

from classificator.cli import main


class EvaluationCliTests(unittest.TestCase):
    def test_prepare_command_produces_blind_labels_without_a_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vocabulary = root / "words.csv"
            vocabulary.write_text("word_id,word,type\n1,casă,noun\n2,ac,noun\n", encoding="utf-8")
            result = main(
                [
                    "--output-dir",
                    str(root / "logs"),
                    "evaluation-prepare",
                    "--vocabulary-csv",
                    str(vocabulary),
                    "--campaign-dir",
                    str(root / "dataset"),
                    "--source-version",
                    "test-inventory-v1",
                ]
            )
            self.assertEqual(result, 0)
            self.assertTrue((root / "dataset/labels.csv").exists())

    def test_exact_form_offline_commands_compare_without_any_http(self):
        import hashlib
        import json
        from unittest.mock import patch
        from tests.test_exact_form import write_csv

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vocab = write_csv(root / "words.csv", [dict(word_id=1, word="la", type="V")])
            loc = root / "loc.txt"
            loc.write_text("la V 1\nla P 1\n")
            contexts = write_csv(
                root / "contexts.csv",
                [
                    dict(
                        word_id=1,
                        word="la",
                        context_id="1:prep",
                        pos="prepoziție",
                        meaning="Relație de loc",
                        example="la școală",
                        source="dictionary",
                    )
                ],
            )
            cache = root / "cache"
            cache.mkdir()
            (cache / "CASA.json").write_text(
                json.dumps(
                    dict(
                        word="CASA",
                        original="casă",
                        status="ok",
                        html='<html><span class="tree-def">la școală</span></html>',
                    )
                )
            )
            reference = write_csv(
                root / "reference.csv",
                [
                    dict(
                        word_id=1,
                        word="la",
                        working_level=1,
                        reference_kind="audited_context_minimum",
                        coverage_status="source-bounded",
                        witness="1:prep",
                    )
                ],
            )
            wf = write_csv(root / "wf.csv", [dict(word="la", frequency=0.01)])
            wf.with_suffix(".csv.metadata.json").write_text(
                json.dumps(
                    dict(
                        frequencies_sha256=hashlib.sha256(wf.read_bytes()).hexdigest(),
                        package_version="fixture",
                        schema_version=1,
                        package="wordfreq",
                        language="ro",
                        wordlist="best",
                    )
                )
            )
            with patch("requests.sessions.Session.request", side_effect=AssertionError("No HTTP")):
                self.assertEqual(
                    main(
                        [
                            "evaluation-exact-forms",
                            "--vocabulary-csv",
                            str(vocab),
                            "--loc-file",
                            str(loc),
                            "--contexts-csv",
                            str(contexts),
                            "--campaign-dir",
                            str(root / "forms"),
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    main(
                        [
                            "evaluation-rebus",
                            "--vocabulary-csv",
                            str(vocab),
                            "--dex-cache",
                            str(cache),
                            "--campaign-dir",
                            str(root / "rebus"),
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    main(
                        [
                            "evaluation-form-report",
                            "--reference-csv",
                            str(reference),
                            "--form-contract-csv",
                            str(root / "forms/forms.csv"),
                            "--wordfreq-csv",
                            str(wf),
                            "--rebus-csv",
                            str(root / "rebus/frequencies.csv"),
                            "--campaign-dir",
                            str(root / "report"),
                        ]
                    ),
                    0,
                )
            report = json.loads((root / "report/summary.json").read_text())
            self.assertEqual(report["paired"]["count"], 1)
            self.assertIsNone(report["paired"]["wordfreq_spearman"])

    def test_d1_campaign_cli_produces_compatible_csv_and_offline_report(self):
        import json
        from tests.test_exact_form import write_csv
        from unittest.mock import Mock, patch
        from tests.test_d1_scorer import response, models, answer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vocab = root / "vocabulary.csv"
            vocab.write_text("word_id,word,type\n1,ac,noun\n")
            forms = write_csv(
                root / "forms.csv",
                [
                    dict(
                        word_id=1,
                        word="ac",
                        inventory_type="noun",
                        rubric="exact-form-most-familiar-valid-sense-v1",
                        coverage="source_bounded_not_exhaustive",
                        loc_entries=json.dumps(
                            [dict(pos="N", morphology="1", line=1, entry="ac N 1")]
                        ),
                        contexts="[]",
                    )
                ],
            )
            model_file = root / "model.gguf"
            model_file.write_bytes(b"fixture model")
            http = Mock()
            http.get.return_value = response(models())
            http.post.return_value = response(answer())
            with patch("classificator.scoring.d1.requests.Session", return_value=http):
                result = main(
                    [
                        "evaluation-run",
                        "--form-contract-csv",
                        str(forms),
                        "--vocabulary-csv",
                        str(vocab),
                        "--campaign-dir",
                        str(root / "run"),
                        "--model",
                        "d1-3b",
                        "--model-file",
                        str(model_file),
                        "--runtime-version",
                        "fixture-1",
                    ]
                )
            self.assertEqual(result, 0)
            record = json.loads((root / "run/records/1.json").read_text())
            self.assertEqual(record["request"]["state"]["form_contract"]["word"], "ac")
            manifest = json.loads((root / "run/manifest.json").read_text())
            self.assertEqual(len(manifest["config"]["form_contract_sha256"]), 64)
            self.assertIn("0.7", (root / "run/predictions.csv").read_text())
            from classificator.run_csv_repository import RunCsvRepository

            self.assertEqual(
                RunCsvRepository().load_run_rows(root / "run/run.csv")[0].rarity_level, 4
            )

    def test_step2_d1_is_explicit_and_writes_legacy_compatible_output(self):
        from unittest.mock import Mock, patch
        from tests.test_d1_scorer import response, models, answer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vocab = root / "vocabulary.csv"
            vocab.write_text("word_id,word,type\n1,ac,noun\n")
            model_file = root / "model.gguf"
            model_file.write_bytes(b"fixture model")
            http = Mock()
            http.get.return_value = response(models())
            http.post.return_value = response(answer())
            with patch("classificator.scoring.d1.requests.Session", return_value=http):
                result = main(
                    [
                        "--output-dir",
                        str(root / "logs"),
                        "step2-score",
                        "--backend",
                        "d1",
                        "--base-csv",
                        str(vocab),
                        "--output-csv",
                        str(root / "scores.csv"),
                        "--run",
                        "experiment",
                        "--model",
                        "d1-3b",
                        "--model-file",
                        str(model_file),
                        "--runtime-version",
                        "fixture-1",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertTrue((root / "scores.csv.campaign/predictions.csv").exists())
            from classificator.run_csv_repository import RunCsvRepository

            rows = RunCsvRepository().load_run_rows(root / "scores.csv")
            self.assertEqual(rows[0].rarity_level, 4)
            self.assertEqual(rows[0].run_slug, "experiment")

    def test_report_counts_missing_prediction_as_missing_not_success(self):
        import json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "labels.csv").write_text("word_id,level,group,split\n1,1,a,test\n2,5,b,test\n")
            (root / "predictions.csv").write_text("word_id,status,rarity_level\n1,scored,1\n")
            result = main(
                [
                    "evaluation-report",
                    "--labels-csv",
                    str(root / "labels.csv"),
                    "--predictions-csv",
                    str(root / "predictions.csv"),
                    "--report",
                    str(root / "report.json"),
                ]
            )
            self.assertEqual(result, 0)
            report = json.loads((root / "report.json").read_text())
            self.assertEqual(report["coverage"], 0.5)

    def test_frequency_baseline_is_offline_and_does_not_invent_tail_scores(self):
        import csv

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "vocab.csv").write_text("word_id,word,type\n1,ac,noun\n2,rar,noun\n")
            (root / "evidence.csv").write_text(
                "word_id,frequency,frequency_present\n1,0.01,true\n2,,false\n"
            )
            result = main(
                [
                    "evaluation-frequency",
                    "--vocabulary-csv",
                    str(root / "vocab.csv"),
                    "--evidence-csv",
                    str(root / "evidence.csv"),
                    "--campaign-dir",
                    str(root / "run"),
                    "--thresholds",
                    "0.001,0.0001,0.00001,0.000001",
                ]
            )
            self.assertEqual(result, 0)
            with (root / "run/predictions.csv").open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["rarity_level"], "1")
            self.assertEqual(rows[1]["status"], "unresolved")
            self.assertEqual(rows[1]["rarity_level"], "")
            self.assertEqual(
                main(
                    [
                        "evaluation-frequency",
                        "--vocabulary-csv",
                        str(root / "vocab.csv"),
                        "--evidence-csv",
                        str(root / "evidence.csv"),
                        "--campaign-dir",
                        str(root / "run"),
                        "--thresholds",
                        "0.001,0.0001,0.00001,0.000001",
                    ]
                ),
                0,
            )

    def test_wordfreq_export_command_uses_optional_local_corpus(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "vocab.csv").write_text("word_id,word,type\n1,casă,noun\n")
            corpus = SimpleNamespace(get_frequency_dict=lambda *a, **kw: {"casă": 0.01})
            with (
                patch.dict(sys.modules, {"wordfreq": corpus}),
                patch("importlib.metadata.version", return_value="fixture"),
            ):
                result = main(
                    [
                        "evaluation-wordfreq",
                        "--vocabulary-csv",
                        str(root / "vocab.csv"),
                        "--output-csv",
                        str(root / "frequency.csv"),
                    ]
                )
            self.assertEqual(result, 0)
            self.assertIn("casă", (root / "frequency.csv").read_text())

    def test_failed_campaign_returns_nonzero_and_keeps_diagnostics(self):
        import requests
        from unittest.mock import Mock, patch
        from tests.test_d1_scorer import response, models

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "vocab.csv").write_text("word_id,word,type\n1,ac,noun\n")
            (root / "model.gguf").write_bytes(b"fixture")
            http = Mock()
            http.get.return_value = response(models())
            http.post.side_effect = requests.Timeout("offline")
            with patch("classificator.scoring.d1.requests.Session", return_value=http):
                code = main(
                    [
                        "evaluation-run",
                        "--vocabulary-csv",
                        str(root / "vocab.csv"),
                        "--campaign-dir",
                        str(root / "run"),
                        "--model",
                        "d1-3b",
                        "--model-file",
                        str(root / "model.gguf"),
                        "--runtime-version",
                        "fixture",
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("offline", (root / "run/failures.csv").read_text())

    def test_evidence_cannot_leak_gold_labels_into_model_requests(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "vocab.csv").write_text("word_id,word,type\n1,ac,noun\n")
            (root / "evidence.csv").write_text("word_id,definition,level\n1,needle,1\n")
            (root / "model.gguf").write_bytes(b"fixture")
            with (
                patch("requests.Session") as session,
                self.assertRaisesRegex(ValueError, "evidence"),
            ):
                main(
                    [
                        "evaluation-run",
                        "--vocabulary-csv",
                        str(root / "vocab.csv"),
                        "--evidence-csv",
                        str(root / "evidence.csv"),
                        "--campaign-dir",
                        str(root / "run"),
                        "--model",
                        "d1",
                        "--model-file",
                        str(root / "model.gguf"),
                        "--runtime-version",
                        "fixture",
                    ]
                )
            session.assert_not_called()
