---
name: graphify
description: Inspect code dependencies and change impact with the Graphify plugin; verify snapshot freshness, export bounded subgraphs, or regenerate this repository's local static code map when Graphify is unavailable.
---

# Graphify

Use the active checkout's Git remote and commit, not its directory name, to identify
the repository. Start with `list_repositories` and `graph_stats`. Record indexed
commit, readiness and coverage when returned; unknown freshness stays unknown.
Compare with local HEAD and uncommitted files before relying on a graph result.

## Narrow the question

- Locate behavior: `graphify_rank_files` or `query_graph(skeleton=true, budget=1500)`.
- Read selected definitions: `graphify_node`; check `resolved` and actual file/symbol.
  A semantic match does not establish the requested symbol exists.
- Scope a change: `graphify_file_neighbors`, then `graphify_callers` / `graphify_callees`
  with `strict_calls=true`. Use `graphify_trace` for a specific directed path.
- Find candidate tests: `graphify_tests_for` or `impact_and_risk`. Static links are
  not runtime coverage; inspect and run the relevant tests.
- Draw a focused view: obtain returned node handles, then `graphify_render_subgraph`.
  Save the raw nodes/links response with the query, repository and snapshot identity.

Use bounded results (roughly 10–30 nodes initially). Read full bodies only for
selected symbols. Re-query changed areas when the index advances; do not dump the
whole graph into every task. Validate conclusions against the working tree.

## Missing or stale index

Do not invent an index/rebuild endpoint: the available Graphify tools query promoted
snapshots. If indexing controls are absent, report that limit and identify the needed
repository/branch in Graphify. `Unknown tool` means the service call failed, not an
empty repository. Do not silently relabel a local graph as a Graphify export.

For this repository, read `docs/code-graph.md` and run its documented
`scripts/code_graph.py` command from the active checkout. Save a separate pre-change
snapshot before modifying a model adapter. This fallback extracts Python syntax
only; imports and definitions do not prove runtime call paths or test coverage.
Exclude build artifacts, environments, secrets and model weights. Keep source hashes
and generator provenance with outputs. No model inference or database access needed.

After a change, regenerate the local map, verify freshness, and retain the pre-change
snapshot when the task requests before/after evidence. Use the graph to choose a
small code-reading/test scope, not to replace source review or execution checks.
