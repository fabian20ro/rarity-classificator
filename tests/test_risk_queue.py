"""Frozen conflict policy through CSV exports; no reference labels accepted."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.risk_queue import export_risk_csv
from tests.test_exact_form import write_csv
from tests.test_local_evidence import read


class RiskQueueTests(unittest.TestCase):
    def inputs(self, root):
        base, evidence, gpt = [], [], []
        for wid, (word, b, g, context) in enumerate(
            [
                ("ata", 2, 5, True),
                ("ață", 4, 1, False),
                ("tehnic", 4, 5, True),
                ("necunoscut", 4, None, False),
            ],
            1,
        ):
            base.append(dict(word_id=wid, word=word, baseline_level=b, wordfreq=""))
            sense = dict(
                pos="N",
                definition="Sens verificat.",
                grammar=[],
                context=[],
                number_restriction="",
                context_incomplete=False,
            )
            evidence.append(
                dict(
                    word_id=wid,
                    word=word,
                    evidence_json=json.dumps(
                        dict(
                            coverage="source_bounded_not_exhaustive",
                            valid_pos=["N"],
                            senses=[sense] if context else [],
                        )
                    ),
                )
            )
            gpt.append(
                dict(
                    word_id=wid, word=word, status="scored" if g else "failed", rarity_level=g or ""
                )
            )
        return tuple(
            write_csv(root / name, rows)
            for name, rows in [("base.csv", base), ("evidence.csv", evidence), ("gpt.csv", gpt)]
        )

    def test_routes_only_supported_large_conflicts_and_never_fills_review_budget(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            export_risk_csv(*self.inputs(root), root / "out", review_budget=50)
            self.assertEqual([r["word_id"] for r in read(root / "out/qwen-route.csv")], ["1"])
            queue = read(root / "out/review-queue.csv")
            self.assertEqual({r["word_id"] for r in queue}, {"1", "2", "4"})
            self.assertEqual(queue[0]["word_id"], "4")
            decisions = {r["word_id"]: r for r in read(root / "out/decisions.csv")}
            self.assertEqual(decisions["1"]["operational_level"], "2")
            self.assertEqual(decisions["1"]["proposed_level"], "5")
            self.assertEqual(decisions["4"]["proposed_level"], "4")
            self.assertEqual(decisions["4"]["proposed_route"], "baseline_after_gpt_failure")
            self.assertEqual(decisions["3"]["risk_band"], "unknown")

    def test_qwen_disagreement_prioritizes_but_agreement_never_vetoes_initial_conflict(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            qwen = write_csv(
                root / "qwen.csv", [dict(word_id=1, word="ata", status="scored", rarity_level=2)]
            )
            export_risk_csv(*args, root / "out", qwen_csv=qwen, review_budget=2)
            queue = read(root / "out/review-queue.csv")
            self.assertEqual([r["word_id"] for r in queue], ["4", "1"])
            self.assertEqual(queue[1]["proposed_level"], "5")
            self.assertEqual(queue[1]["qwen_gpt_conflict"], "True")
            write_csv(qwen, [dict(word_id=1, word="ata", status="scored", rarity_level=5)])
            export_risk_csv(*args, root / "agree", qwen_csv=qwen)
            self.assertEqual(
                {r["word_id"] for r in read(root / "agree/review-queue.csv")}, {"1", "2", "4"}
            )

    def test_empty_qwen_route_can_complete_without_any_calls(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.inputs(root)
            rows = read(args[2])
            rows[0]["rarity_level"] = "2"
            write_csv(args[2], rows)
            qwen = root / "qwen.csv"
            qwen.write_text("word_id,word,status,rarity_level\n")
            result = export_risk_csv(*args, root / "out", qwen_csv=qwen)
            self.assertTrue(result["qwen_complete"])
            self.assertEqual(result["qwen_routed"], 0)

    def test_rejects_duplicate_forms_labels_and_partial_or_unrouted_judgments_atomically(self):
        for defect in [
            "duplicate_form",
            "gold_column",
            "partial_gpt",
            "unrouted_qwen",
            "invalid_score",
        ]:
            with self.subTest(defect=defect), TemporaryDirectory() as temp:
                root = Path(temp)
                args = self.inputs(root)
                qwen = None
                if defect == "duplicate_form":
                    for p in args:
                        rows = read(p)
                        rows[1]["word"] = rows[0]["word"]
                        write_csv(p, rows)
                elif defect == "gold_column":
                    rows = read(args[0])
                    for r in rows:
                        r["human_level"] = "1"
                    write_csv(args[0], rows)
                elif defect == "partial_gpt":
                    write_csv(args[2], read(args[2])[:-1])
                elif defect == "unrouted_qwen":
                    qwen = write_csv(
                        root / "qwen.csv",
                        [dict(word_id=2, word="ață", status="scored", rarity_level=1)],
                    )
                else:
                    rows = read(args[2])
                    rows[0]["rarity_level"] = "2.0"
                    write_csv(args[2], rows)
                with self.assertRaises(ValueError):
                    export_risk_csv(*args, root / "out", qwen_csv=qwen)
                self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main()
