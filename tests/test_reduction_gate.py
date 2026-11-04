"""Frozen CSV inputs → complete offline proposals; no reference labels at this seam."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from classificator.evaluation.reduction_gate import export_reduction_gate
from tests.test_exact_form import write_csv
from tests.test_local_evidence import read
from tests import test_fineweb_fallback as fw_fixtures
from tests import test_corola_fallback as co_fixtures


class ReductionGateTests(unittest.TestCase):
    def inputs(self, root):
        words = ["ata", "ață", "otel", "oțel", "ceruit", "lipsă"]
        vocabulary = [dict(word_id=i, word=w, type="N") for i, w in enumerate(words, 1)]
        for corpus in ("fineweb", "corola"):
            (root / corpus).mkdir()
            write_csv(root / corpus / "vocabulary.csv", vocabulary)
        fineweb = [
            dict(
                r,
                count=5 if r["word_id"] in (1, 4, 5) else 4,
                document_count=3,
                host_count=2,
                token_total=100000,
                frequency=(5 if r["word_id"] in (1, 4, 5) else 4) / 100000,
                status="observed",
            )
            for r in vocabulary
        ]
        corola = [
            dict(
                r,
                count=5 if r["word_id"] == 2 else 4,
                token_total=100000,
                frequency=(5 if r["word_id"] == 2 else 4) / 100000,
                status="observed",
            )
            for r in vocabulary
        ]
        fw_fixtures.FineWebFallbackTests().evidence(root / "fineweb", fineweb)
        co_fixtures.CoRoLaFallbackTests().evidence(root / "corola", corola)
        baseline = write_csv(
            root / "baseline.csv",
            [dict(word_id=r["word_id"], word=r["word"], baseline_level=4) for r in vocabulary],
        )
        predictions = write_csv(
            root / "gpt.csv",
            [
                dict(
                    word_id=r["word_id"],
                    word=r["word"],
                    status="scored" if r["word_id"] != 6 else "failed",
                    rarity_level=2 if r["word_id"] <= 4 else 3 if r["word_id"] == 5 else "",
                )
                for r in vocabulary
            ],
        )
        sense = dict(
            pos="substantiv neutru",
            definition="Sens documentat.",
            number_restriction="",
            grammar=[],
            context=[],
            context_incomplete=False,
        )
        lexical = write_csv(
            root / "lexical.csv",
            [
                dict(
                    word_id=r["word_id"],
                    word=r["word"],
                    evidence_json=json.dumps(
                        dict(
                            coverage="source_bounded_not_exhaustive",
                            valid_pos=["substantiv neutru"]
                            + (["adjectiv"] if r["word_id"] == 4 else []),
                            senses=[sense],
                        )
                    ),
                )
                for r in vocabulary
            ],
        )
        return baseline, lexical, predictions, root / "fineweb", root / "corola"

    def test_accepts_only_large_reductions_with_pos_and_exact_corpus_support(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            with (
                patch(
                    "requests.adapters.HTTPAdapter.send",
                    side_effect=AssertionError("Network forbidden"),
                ),
                patch("subprocess.run", side_effect=AssertionError("LLM forbidden")),
                patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
            ):
                export_reduction_gate(*args, root / "out")
            rows = read(root / "out/decisions.csv")
            self.assertEqual([r["candidate_level"] for r in rows], ["2", "2", "4", "4", "4", "4"])
            self.assertEqual(
                [r["reason"] for r in rows],
                [
                    "accepted",
                    "accepted",
                    "missing_corpus_support",
                    "missing_lexical_support",
                    "not_large_reduction",
                    "gpt_failed",
                ],
            )
            self.assertEqual([r["baseline_level"] for r in rows], ["4"] * 6)
            self.assertEqual(rows[-1]["gpt_level"], "")
            with self.assertRaises(FileExistsError):
                export_reduction_gate(*args, root / "out")

    def test_support_thresholds_do_not_authorize_increases_or_small_changes(self):
        for defect in ("documents", "hosts", "increase"):
            with self.subTest(defect=defect), TemporaryDirectory() as temp:
                root = Path(temp)
                args = self.inputs(root)
                if defect == "increase":
                    base = read(args[0])
                    base[0]["baseline_level"] = "1"
                    write_csv(args[0], base)
                else:
                    rows = read(root / "fineweb/frequencies.csv")
                    rows[0]["document_count" if defect == "documents" else "host_count"] = (
                        "2" if defect == "documents" else "1"
                    )
                    fw_fixtures.FineWebFallbackTests().evidence(root / "fineweb", rows)
                export_reduction_gate(*args, root / "out")
                row = read(root / "out/decisions.csv")[0]
                self.assertEqual(row["candidate_level"], "1" if defect == "increase" else "4")

    def test_invalid_identity_gold_and_provenance_fail_before_any_output(self):
        for defect in (
            "gold",
            "missing_gpt",
            "spelling",
            "duplicate",
            "source_hash",
            "missing_corpus",
            "failed_with_score",
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as temp:
                root = Path(temp)
                args = self.inputs(root)
                if defect == "gold":
                    rows = read(args[0])
                    rows = [dict(r, human_level=5) for r in rows]
                    write_csv(args[0], rows)
                elif defect in ("missing_gpt", "spelling", "duplicate", "failed_with_score"):
                    rows = read(args[2])
                    if defect == "missing_gpt":
                        rows = rows[:-1]
                    elif defect == "spelling":
                        rows[2]["word"] = "oțel"
                    elif defect == "duplicate":
                        rows.append(rows[0])
                    else:
                        rows[-1]["rarity_level"] = "2"
                    write_csv(args[2], rows)
                elif defect == "source_hash":
                    with (root / "corola/frequencies.csv").open("a") as stream:
                        stream.write("\n")
                else:
                    rows = read(root / "corola/frequencies.csv")[:-1]
                    write_csv(
                        root / "corola/vocabulary.csv",
                        [{k: r[k] for k in ("word_id", "word", "type")} for r in rows],
                    )
                    co_fixtures.CoRoLaFallbackTests().evidence(root / "corola", rows)
                with self.assertRaises(ValueError):
                    export_reduction_gate(*args, root / "out")
                self.assertFalse((root / "out").exists())

    def test_replay_is_byte_identical_and_never_treats_zero_counts_as_missing_rows(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            for corpus in ("fineweb", "corola"):
                rows = read(root / corpus / "frequencies.csv")
                rows[0].update(count="0", frequency="0", status="unobserved")
                if corpus == "fineweb":
                    rows[0].update(document_count="0", host_count="0")
                    fw_fixtures.FineWebFallbackTests().evidence(root / corpus, rows)
                else:
                    co_fixtures.CoRoLaFallbackTests().evidence(root / corpus, rows)
            export_reduction_gate(*args, root / "out")
            export_reduction_gate(*args, root / "replay")
            self.assertEqual(
                read(root / "out/decisions.csv")[0]["reason"], "missing_corpus_support"
            )
            for path in (root / "out").iterdir():
                self.assertEqual(path.read_bytes(), (root / "replay" / path.name).read_bytes())
