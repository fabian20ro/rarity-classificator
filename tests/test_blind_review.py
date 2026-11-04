import json
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from classificator.evaluation.blind_review import build_blind_review


class BlindReviewTests(unittest.TestCase):
    def test_public_pack_contains_only_lexical_fields_and_refuses_estimate_leakage(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            form = dict(
                word_id="9",
                word="vară",
                contexts=[
                    dict(
                        context_id="9:1",
                        pos="substantiv feminin",
                        meaning="Anotimp.",
                        example="o vară caldă",
                        source="https://dexonline.ro/definitie/vară",
                    )
                ],
            )
            source = root / "forms.json"
            source.write_text(json.dumps(dict(forms=[form])))
            result = build_blind_review(source, root / "public", version="blind-fixture", seed=12)
            data = json.loads((root / "public/cases.json").read_text())
            self.assertEqual(data["forms"], [form])
            self.assertEqual(data["version"], "blind-fixture")
            self.assertEqual(
                set(p.name for p in (root / "public").iterdir()),
                {"index.html", "app.js", "style.css", "cases.json", "manifest.json"},
            )
            self.assertNotIn('type="number"', (root / "public/index.html").read_text())
            self.assertNotIn("ai-box", (root / "public/index.html").read_text())
            self.assertEqual(result["count"], 1)
            with self.assertRaises(FileExistsError):
                build_blind_review(source, root / "public", version="blind-fixture", seed=12)
            for field in ["estimate", "frequency", "stratum", "initial_level"]:
                source.write_text(json.dumps(dict(forms=[dict(form, **{field: 3})])))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    build_blind_review(source, root / field, version="blind-fixture", seed=12)
                self.assertFalse((root / field).exists())

    @unittest.skipUnless(shutil.which("node"), "Node required for browser-state regression")
    def test_rating_reload_and_exports_preserve_annotation_history(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(
            [
                shutil.which("node"),
                str(root / "tests/blind_review_ui.cjs"),
                str(root / "src/classificator/evaluation/assets/blind.js"),
            ],
            check=True,
        )
