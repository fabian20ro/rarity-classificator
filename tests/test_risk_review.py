"""Public risk-review artifacts: bounded, lexical-only, honest about missing senses."""

import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.evaluation.blind_review import build_risk_review


class RiskReviewTests(unittest.TestCase):
    def forms(self):
        return [
            dict(
                word_id="1",
                word="ata",
                valid_pos=["substantiv feminin"],
                contexts=[
                    dict(
                        context_id="1:atu",
                        pos="substantiv feminin",
                        meaning="Atu.",
                        restrictions=["variantă lexicală", "regional"],
                        source="https://dexonline.ro/definitie/ata",
                    )
                ],
            ),
            dict(word_id="2", word="necunoscut", valid_pos=["adjectiv", "substantiv"], contexts=[]),
        ]

    def test_exports_missing_senses_explicitly_without_estimates_or_fabricated_contexts(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "forms.json"
            source.write_text(json.dumps(dict(forms=self.forms())))
            result = build_risk_review(source, root / "public", version="risk-fixture-v1", seed=23)
            pack = json.loads((root / "public/cases.json").read_text())
            self.assertEqual(pack["mode"], "risk")
            self.assertEqual(sorted(pack["forms"], key=lambda f: f["word_id"]), self.forms())
            self.assertEqual(result["count"], 2)
            self.assertEqual(result["without_context"], 1)
            self.assertIn("maximum 50", (root / "public/index.html").read_text())
            with self.assertRaises(FileExistsError):
                build_risk_review(source, root / "public", version="risk-fixture-v1", seed=23)

    def test_refuses_estimates_unverifiable_sources_identity_errors_and_budget_overflow(self):
        for defect in [
            "score",
            "frequency",
            "context_score",
            "source",
            "missing_pos",
            "duplicate_id",
            "duplicate_spelling",
            "invalid_id",
            "restrictions",
            "51",
        ]:
            with self.subTest(defect=defect), TemporaryDirectory() as temp:
                root = Path(temp)
                forms = self.forms()
                if defect in {"score", "frequency"}:
                    forms[0][defect] = 4
                elif defect == "context_score":
                    forms[0]["contexts"][0]["estimate"] = 4
                elif defect == "source":
                    forms[0]["contexts"][0]["source"] = "javascript:alert(1)"
                elif defect == "missing_pos":
                    forms[1]["valid_pos"] = []
                elif defect == "duplicate_id":
                    forms[1]["word_id"] = "1"
                elif defect == "duplicate_spelling":
                    forms[1]["word"] = "ata"
                elif defect == "invalid_id":
                    forms[1]["word_id"] = "02"
                elif defect == "restrictions":
                    forms[0]["contexts"][0]["restrictions"] = [""]
                else:
                    forms = [
                        dict(word_id=str(i), word=f"w{i}", valid_pos=["N"], contexts=[])
                        for i in range(1, 52)
                    ]
                source = root / "forms.json"
                source.write_text(json.dumps(dict(forms=forms)))
                with self.assertRaises(ValueError):
                    build_risk_review(source, root / "public", version="risk-fixture-v1", seed=23)
                self.assertFalse((root / "public").exists())

    @unittest.skipUnless(shutil.which("node"), "Node required for browser-state regression")
    def test_missing_context_rating_reload_and_exports_preserve_old_rounds(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(
            [
                shutil.which("node"),
                str(root / "tests/risk_review_ui.cjs"),
                str(root / "src/classificator/evaluation/assets/blind.js"),
            ],
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
