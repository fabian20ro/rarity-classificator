import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from classificator.evaluation.form_frequency_report import compare_form_frequencies
from tests.test_exact_form import write_csv


class FormFrequencyReportTests(unittest.TestCase):
    def test_compares_only_clarified_forms_on_common_coverage_without_filling_absences(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            reference = write_csv(
                root / "reference.csv",
                [
                    dict(
                        word_id=i,
                        word=w,
                        working_level=level,
                        reference_kind=kind,
                        coverage_status="provisional",
                        witness="",
                    )
                    for i, w, level, kind in [
                        (1, "a", 1, "shortlist_form_review"),
                        (2, "b", 2, "audited_context_minimum"),
                        (3, "c", 3, "shortlist_form_review"),
                        (4, "d", 1, "shortlist_form_review"),
                        (5, "e", 5, "initial_opaque_form_pos"),
                    ]
                ],
            )
            forms = write_csv(
                root / "forms.csv",
                [
                    dict(
                        word_id=i,
                        word=w,
                        inventory_type="N",
                        rubric="exact-form-most-familiar-valid-sense-v1",
                        coverage="source_bounded_not_exhaustive",
                        loc_entries=json.dumps(
                            [dict(pos="N", morphology="1", line=i, entry=w + " N 1")]
                        ),
                        contexts="[]",
                    )
                    for i, w in enumerate("abcde", 1)
                ],
            )
            wordfreq = write_csv(
                root / "wordfreq.csv",
                [
                    dict(word=w, frequency=f)
                    for w, f in [("a", 0.3), ("b", 0.2), ("d", 0.3), ("e", 0.1)]
                ],
            )
            wordfreq.with_suffix(".csv.metadata.json").write_text(
                json.dumps(
                    dict(
                        frequencies_sha256=hashlib.sha256(wordfreq.read_bytes()).hexdigest(),
                        package_version="fixture",
                        schema_version=1,
                        package="wordfreq",
                        language="ro",
                        wordlist="best",
                    )
                )
            )
            rebus = write_csv(
                root / "rebus.csv",
                [
                    dict(
                        word_id=i,
                        word=w,
                        count=c,
                        document_count=1,
                        token_total=10,
                        frequency=c / 10,
                        status="observed",
                    )
                    for i, w, c in [(1, "a", 1), (2, "b", 2), (3, "c", 3), (4, "d", 1), (5, "e", 1)]
                ],
            )
            ledger = root / "source-files.csv"
            ledger.write_text("file,sha256,disposition\nfixture.json,abc,used\n")
            (root / "manifest.json").write_text(
                json.dumps(
                    dict(
                        schema=1,
                        policy="rebus-definition-tokens-exclude-pilot-pages-v1",
                        artifacts={
                            "source-files.csv": hashlib.sha256(ledger.read_bytes()).hexdigest(),
                            "rebus.csv": hashlib.sha256(rebus.read_bytes()).hexdigest(),
                        },
                    )
                )
            )
            result = compare_form_frequencies(reference, forms, wordfreq, rebus, root / "report")
            self.assertEqual(result["reference_count"], 4)
            self.assertEqual(result["excluded_opaque_count"], 1)
            self.assertEqual(result["wordfreq"]["covered"], 3)
            self.assertEqual(result["wordfreq"]["spearman_familiarity"], 1)
            self.assertEqual(result["rebus"]["spearman_familiarity"], -1)
            self.assertEqual(result["paired"]["count"], 3)
            self.assertEqual(result["paired"]["wordfreq_spearman"], 1)
            self.assertEqual(result["paired"]["rebus_spearman"], -1)
            self.assertEqual(result["wordfreq"]["coverage_by_level"]["3"], dict(total=1, covered=0))
            self.assertNotIn("accuracy", result)
            self.assertEqual(result["split"], "dev")
            with self.assertRaises(FileExistsError):
                compare_form_frequencies(reference, forms, wordfreq, rebus, root / "report")
            for path, key, bad_value in [
                (wordfreq.with_suffix(".csv.metadata.json"), "language", "en"),
                (root / "manifest.json", "policy", "include-self-pages"),
            ]:
                with self.subTest(key=key):
                    original = path.read_text()
                    data = json.loads(original)
                    data[key] = bad_value
                    path.write_text(json.dumps(data))
                    with self.assertRaises(ValueError):
                        compare_form_frequencies(
                            reference, forms, wordfreq, rebus, root / ("wrong-" + key)
                        )
                    path.write_text(original)
            ledger.write_text(ledger.read_text() + "changed\n")
            with self.assertRaisesRegex(ValueError, "hash"):
                compare_form_frequencies(reference, forms, wordfreq, rebus, root / "ledger-changed")
            wordfreq.write_text(wordfreq.read_text() + "z,0.4\n")
            with self.assertRaisesRegex(ValueError, "hash"):
                compare_form_frequencies(reference, forms, wordfreq, rebus, root / "changed")
