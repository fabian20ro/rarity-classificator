# 001 — One complete project verification command

Date: 2026-09-29. Status: accepted.

## Context

CI and the Compound local gate used unittest discovery. Standalone pytest tests
were silently omitted, including six failing tests and a real fuzzy matching
inconsistency. A green command was not evidence of a complete collection.

## Decision

`python scripts/check.py` runs Ruff, then pytest using project-owned discovery
configuration. Both CI and the external Compound roster call this command.
Existing unittest tests stay unchanged; pytest collects both supported styles.
No framework, extra dependency, network service or second result store is added.
Collection remains inspectable with `python -m pytest --collect-only -q`.

Restore the original normalized Levenshtein threshold (`<= 2`, initial import
e4fe441), shared by both public matcher APIs. Prefix-only acceptance introduced
in 0b5f473 could assign scores to unrelated words; it was not a product contract.
Retain case/diacritic normalization and legitimate one/two-edit recovery.
Whitespace-only JSON assertions become value assertions, except deliberately
invalid JSON where token preservation is the actual requirement.

## Consequences

Missing dependencies, lint failure, empty collection and failing function-style
tests now fail the same entrypoint. Tests requiring stronger semantic evidence
remain a separate review concern: complete collection is not proof of product
acceptance. Keep the real-CSV eight-step Jaccard/anchor gate tests; remove the
redundant mocked gate test introduced in 8b536b1.
