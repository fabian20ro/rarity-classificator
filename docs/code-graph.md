# Local code graph

Deterministic static inventory of **tracked Python** under `src/`, `tests/` and
`scripts/`. Built with Python's standard-library AST parser; no imports of project
code, model requests, database access, network calls or additional dependencies.
This is the **local fallback**, not an output of the unavailable Graphify service.

## Regenerate and inspect

From the repository root, with Python 3.11 or newer:

```sh
python3 scripts/code_graph.py
python3 scripts/code_graph.py --check
python3 scripts/code_graph.py --impact classificator.scoring.d1
```

- [Complete graph](code-graph/graph.json): modules, file paths, SHA-256 hashes,
  qualified class/function definitions with line numbers, import statements and
  resolved internal module edges. `source_tree_sha256` binds the ordered source
  paths and content hashes. No timestamps or absolute workspace paths.
- [Focused D1 diagram](code-graph/d1-imports.mmd): Mermaid module-import view of
  the CLI, evaluation CLI, scorer, campaign, outcomes/models and CSV codec.
- `--check`: rebuild in memory; return nonzero for missing/stale artifacts; no writes.
- `--impact MODULE`: print transitive importers from current tracked sources;
  no writes. This can suggest inspection candidates, not prove affected behavior.
- `--output PATH`: write a separate snapshot before a change. Default output is
  `docs/code-graph/` under `--root` (default: this script's repository).

New source files must be `git add`ed before they enter the graph. Tracked working
contents, including edits not yet committed, are analyzed. A commit alone does not
make the graph stale; changed source content does. The generator and its CLI tests
are themselves in scope. Missing files, symlinks, conflicting module identities and
invalid Python fail visibly. Non-Python artifacts, corpus data, `build/`, `.venv/`,
`.env` and other configuration files are outside the scan.

## Efficient use

1. Regenerate after pulling/changing Python; use `--check` to detect staleness.
2. Start with a specific module and its `--impact` result. Follow only relevant
   edges in `graph.json`; load source definitions by recorded path and line.
3. Use the focused diagram to orient changes to the D1 path. Inspect source and
   tests before changing a contract; do not paste the whole JSON into every prompt.
4. Regenerate after the change and review the graph diff alongside code/tests.
   For a baseline comparison, keep a separate snapshot with `--output` first.

The initial graph was generated before the 2026-10-29 model-target update. It
contained 126 modules and 381 import-site edges. These are inventory counts, not
quality metrics. Repeated imports at different lines produce separate edges.

## Limits

Edges mean syntactically declared module imports, **not runtime calls**. Imports
inside functions, conditionals or `TYPE_CHECKING` blocks are included even if they
never execute. External/unresolved imports remain recorded as statements but have
no internal target edge. Dynamic imports, reflection, implicit package-initializer
execution and symbol alias/re-export resolution are not inferred. Definitions are
syntactic declarations, not evidence that a function is called.

Test modules appear as ordinary importers. An import edge or impact result does
not establish test coverage; inspect/run the tests. The D1 diagram intentionally
shows a small module subset; use the JSON for the complete inventory. Changes to
model configuration or documentation may have no Python-graph delta and still
require review. For semantic search or runtime architecture, use additional
validated evidence rather than promoting these structural edges to conclusions.

## Verification

`tests/test_code_graph.py` exercises the CLI on a temporary tracked repository:
relative imports, package imports, nested definitions, transitive impact,
untracked/out-of-scope exclusion, byte-identical regeneration and stale detection
without overwriting artifacts. Run:

```sh
python3 -m pytest tests/test_code_graph.py -q
python3 -m ruff check scripts/code_graph.py tests/test_code_graph.py
```

## Graphify plugin and reusable skill

[Repository skill](../skills/graphify/SKILL.md) describes bounded Graphify queries,
index freshness checks and this fallback. A copy was installed in
`~/.codex/skills/graphify/SKILL.md`; refresh that copy after changing the repository
skill. Invoke `$graphify`, or explicitly ask to read the repository skill.

On 2026-10-29, Graphify's tools were advertised but `list_repositories` and
`graph_stats` returned `Unknown tool`, including a retry after the user tagged the
plugin. No repository index or remote graph export was obtained. The plugin manifest
points to hosted `https://api.graphify.com/mcp`; a Homebrew package is not required
for that connector. Reconnection/service repair is separate from repository indexing.
The exposed tools query promoted snapshots; they do not expose a full index-build
or full-graph export operation. After connection works, check repository/index
readiness before treating a bounded subgraph as evidence of current code.

[Before-model snapshot](code-graph/before-omni/graph.json) preserves the graph made
before updating the active model examples/tests. Its Python source digest is
`cb1074dc544108ab222970065f72de962e6510724ae23f034056f64b8abe25a6`;
the initial graph generator/output is also preserved in commit `52745da`.
The local baseline was `b874395` plus the newly staged generator and graph test.
Only after saving this snapshot were the model examples/tests changed. The current
map was then regenerated; historical snapshots intentionally do not pass a check
against the newer working tree.
