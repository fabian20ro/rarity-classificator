"""Deterministic, local AST inventory; module imports are not runtime call edges."""
import argparse
import ast
from collections import deque
import hashlib
import json
from pathlib import Path
import subprocess


SCHEMA = "python-module-graph-v1"
FOCUS = {
    "classificator.cli", "classificator.evaluation.cli",
    "classificator.scoring.d1", "classificator.scoring.base",
    "classificator.evaluation.campaign", "classificator.csv_codec", "classificator.models",
}


def module_name(path):
    parts = list(path.with_suffix("").parts)
    if parts[0] == "src":
        parts.pop(0)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def definitions(tree, prefix=""):
    result = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            name = f"{prefix}.{node.name}" if prefix else node.name
            result.append({"name": name, "kind": type(node).__name__, "line": node.lineno})
            result.extend(definitions(node, name))
        else:
            result.extend(definitions(node, prefix))
    return result


def build(root):
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--", ":(glob)src/**/*.py", ":(glob)tests/**/*.py", ":(glob)scripts/**/*.py"],
        cwd=root,
    ).decode().split("\0")
    nodes, trees = [], {}
    for name in sorted(filter(None, paths)):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Tracked Python source must be a regular file: {name}")
        content = path.read_bytes()
        tree = ast.parse(content, filename=name)
        module = module_name(Path(name))
        if module in trees:
            raise ValueError(f"Ambiguous module identity: {module}")
        trees[module] = (tree, Path(name).name == "__init__.py")
        nodes.append({"module": module, "path": name,
                      "sha256": hashlib.sha256(content).hexdigest(),
                      "definitions": definitions(tree)})
    edges, imports = [], []
    for module, (tree, package_file) in sorted(trees.items()):
        package = module.split(".") if package_file else module.split(".")[:-1]
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Import):
                candidates = [alias.name for alias in node.names]
                statement = "import " + ", ".join(candidates)
            else:
                base = node.module or ""
                if node.level:
                    if node.level > len(package):
                        raise ValueError(f"Relative import beyond package: {module}:{node.lineno}")
                    base = ".".join(package[:len(package) - node.level + 1] + ([base] if base else []))
                candidates = [base] + [f"{base}.{a.name}" for a in node.names if a.name != "*"]
                statement = "from " + "." * node.level + (node.module or "") + " import " + ", ".join(a.name for a in node.names)
            resolved = sorted(set(c for c in candidates if c in trees and c != module))
            imports.append({"source": module, "line": node.lineno,
                            "statement": statement, "resolved_modules": resolved})
            edges.extend({"source": module, "target": target, "line": node.lineno} for target in resolved)
    sources = "\n".join(n["path"] + ":" + n["sha256"] for n in nodes)
    return {"schema": SCHEMA, "scope": "git-tracked Python under src/, tests/, scripts/",
            "source_tree_sha256": hashlib.sha256(sources.encode()).hexdigest(),
            "nodes": nodes, "imports": sorted(imports, key=lambda i: (i["source"], i["line"], i["statement"])),
            "edges": sorted(edges, key=lambda e: (e["source"], e["target"], e["line"]))}


def render(graph):
    selected = sorted(n["module"] for n in graph["nodes"] if n["module"] in FOCUS)
    ids = {module: f"m{i}" for i, module in enumerate(selected)}
    lines = ["flowchart LR", "  %% Static module imports only; focused D1 view, not runtime calls."]
    lines.extend(f'  {ids[module]}["{module}"]' for module in selected)
    pairs = sorted({(e["source"], e["target"]) for e in graph["edges"] if e["source"] in ids and e["target"] in ids})
    lines.extend(f"  {ids[source]} --> {ids[target]}" for source, target in pairs)
    return {"graph.json": json.dumps(graph, indent=2, ensure_ascii=False) + "\n",
            "d1-imports.mmd": "\n".join(lines) + "\n"}


def impact(graph, target):
    if target not in {n["module"] for n in graph["nodes"]}:
        raise ValueError(f"Unknown module: {target}")
    seen, pending = {target}, deque([target])
    while pending:
        current = pending.popleft()
        for edge in graph["edges"]:
            if edge["target"] == current and edge["source"] not in seen:
                seen.add(edge["source"])
                pending.append(edge["source"])
    return sorted(seen - {target})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Default: ROOT/docs/code-graph")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Fail if saved graph differs; never write")
    mode.add_argument("--impact", metavar="MODULE", help="Print transitive importers; no writes")
    args = parser.parse_args()
    graph = build(args.root)
    if args.impact:
        print(json.dumps(impact(graph, args.impact), indent=2))
        return 0
    output = args.output or args.root / "docs/code-graph"
    artifacts = render(graph)
    if args.check:
        stale = [name for name, content in artifacts.items()
                 if not (output / name).is_file() or (output / name).read_text() != content]
        if stale:
            print("Stale graph: " + ", ".join(stale))
            return 1
    else:
        output.mkdir(parents=True, exist_ok=True)
        for name, content in artifacts.items():
            (output / name).write_text(content, encoding="utf-8")
    print(f"{len(graph['nodes'])} modules; {len(graph['edges'])} import edges; {graph['source_tree_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
