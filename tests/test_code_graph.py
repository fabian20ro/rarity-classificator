"""Exercise the local graph CLI against a tracked toy repository."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/code_graph.py"


class CodeGraphTests(unittest.TestCase):
    def test_tracked_scope_relative_imports_definitions_impact_and_staleness(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            sources = {
                "src/pkg/__init__.py": "from . import core\n",
                "src/pkg/core.py": "class Engine:\n    def run(self):\n        pass\n",
                "src/pkg/sub/__init__.py": "",
                "src/pkg/sub/job.py": "from .. import core\nfrom . import helper\nimport json\n",
                "src/pkg/sub/helper.py": "def help_job():\n    pass\n",
                "tests/test_job.py": "import pkg.sub.job\n",
                "scripts/run.py": "from pkg.core import Engine\n",
            }
            for name, content in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            (root / "src/pkg/untracked.py").write_text("invalid Python !!!")
            (root / "build").mkdir()
            (root / "build/ignored.py").write_text("invalid Python !!!")
            subprocess.run(["git", "add", "build/ignored.py"], cwd=root, check=True)

            def run(*args):
                return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args], capture_output=True, text=True)

            self.assertEqual(run().returncode, 0)
            output = root / "docs/code-graph/graph.json"
            before = output.read_bytes()
            graph = json.loads(before)
            self.assertEqual(len(graph["nodes"]), len(sources))
            edges = {(e["source"], e["target"]) for e in graph["edges"]}
            self.assertIn(("pkg", "pkg.core"), edges)
            self.assertIn(("pkg.sub.job", "pkg.core"), edges)
            self.assertIn(("pkg.sub.job", "pkg.sub.helper"), edges)
            self.assertIn(("scripts.run", "pkg.core"), edges)
            core = next(n for n in graph["nodes"] if n["module"] == "pkg.core")
            self.assertEqual([d["name"] for d in core["definitions"]], ["Engine", "Engine.run"])
            imports = json.loads(run("--impact", "pkg.core").stdout)
            self.assertEqual(imports, ["pkg", "pkg.sub.job", "scripts.run", "tests.test_job"])
            self.assertEqual(run().returncode, 0)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(run("--check").returncode, 0)
            (root / "src/pkg/core.py").write_text("class Changed:\n    pass\n")
            self.assertEqual(run("--check").returncode, 1)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(run().returncode, 0)
            self.assertNotEqual(output.read_bytes(), before)
            self.assertNotEqual(run("--impact", "missing").returncode, 0)
