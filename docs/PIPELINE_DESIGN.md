# Pipeline Design

## Goal

Classify Romanian lexical rarity (`1..5`) with robust offline orchestration:

- deterministic intermediate files,
- resumable LM batch processing,
- strict rebalance contracts,
- gated uploads (Jaccard + anchor precision/recall).

## Repository Boundary

This repository is the source of truth for offline rarity classification.
`fabian20ro/propozitii-absurde` consumes `words.rarity_level` at runtime, but does not host classifier runtime code, prompts, or orchestration.

## Why Python

- Better data tooling for batch CSV analysis and audits.
- Faster iteration on parser/repair heuristics and experiment scripts.
- Easier standalone extraction as a dedicated classification repo.

## Implementation Shape

- Python CLI + modular pipeline steps.
- CSV-first and resumable execution.
- Strict parser/schema enforcement around LM JSON.
- Rebalance transitions with checkpoints and recoverable state.
- Prompt assets + quality-audit tooling + optional chained rebalance helper.

## Step Model

- `step1-export`: DB -> `step1_words.csv` (`word_id,word,type`).
- `step2-score`: LM scores full list into run CSV (`rarity_level`, `tag`, `confidence`) with:
  - append-resume behavior,
  - lock file (`.lock`),
  - guarded final rewrite,
  - adaptive batch size,
  - run/failure JSONL logs.
- `step3-compare`: merges 2/3 runs into `final_level` and outliers.
- `step4-upload`: writes `final_level`/`rarity_level` to DB (default partial mode) and writes upload markers.
- `step5-rebalance`: strict two-bucket split from source levels to target level using exact-count batch-local `local_id` selections only (`1..N`, unique, no `0`, no word-id fallback).

## Rebalance Contract (Critical)

- LM must return exactly `N` selected ids per batch.
- Id domain is strictly local batch ids (`1..batch_size`), unique, exact count, no `0`, no word-id fallback.
- Parser fails fast when count mismatches (no silent auto-fill).
- Recursive split retries preserve expected selection counts proportionally.

## Quality Gate Contract

Before automatic Step4 upload, candidate CSV must pass:

- L1 Jaccard against trusted reference run (`word_id` set overlap stability),
- L1 anchor precision/recall from curated Romanian base vocabulary anchors.

This protects against superficially correct histograms with semantically poor L1 content.

## Data Contracts

- Level semantics: lower number means more common word.
- Output values are constrained to `1..5`.
- Step5 selection mode uses local batch ids only (`1..N`, unique, exact count, no `0`, no word-id fallback).
- Step4 upload default mode is `partial`.

## Artifact Layout

- `build/rarity/runs/*.csv` step2/step5 outputs
- `build/rarity/runs/*.jsonl` step2 raw LM logs
- `build/rarity/failed_batches/*.failed.jsonl` step2 unresolved failures
- `build/rarity/rebalance/**` step5 runs/failures/checkpoints/switched words
- `build/rarity/step4_upload_report.csv`

## Known Tradeoffs

- Step2 and Step5 are single-process orchestrations (not distributed workers).
- Quality anchors start as seed set; precision improves with larger curated anchors.
- Local LM behavior varies by model; strict parser/schema catches drift but may increase retries.


## Approved human correction flow (2026-11-03)

A separate CSV-first flow accepts only an explicitly approved, source-verified human
package. Jaccard remains mandatory; anchor metrics remain visible but do not veto
this flow. Default offline preview; transactional execution, durable receipt and
version-guarded rollback are separate from Step4. No general gate-bypass option.
See [accepted decision](adr/2026-11-03-human-correction-flow.md) and
[runbook](research/2026-11-03-human-flow.md). Implementation verified offline and on disposable PostgreSQL17.9;
no schema deployment or application in the project database.
[Integration evidence](research/2026-11-03-postgres-integration.md).

**Production preflight found OrioleDB1.8 without xmin.** The adapter now uses explicit
DB-issued revisions on OrioleDB and binds receipts to an installation UUID; heap
retains xmin. Same-score writes and delete/reinsert invalidate rollback, including
ordinary external writers.28 OrioleDB tests and17 heap regressions pass. The165 lot
and233 guards remain valid; production still needs separately authorized revision,
ledger and role installation. [Preflight](research/2026-11-03-production-preflight.md) ·
[Implementation/results](research/2026-11-03-orioledb-integration.md).


## Offline installation bundle (2026-11-03)

`classificator.human_installation` prepares pinned CSVs/captures → SQL/checks/manifest;
no DB connection or execution. One atomic ledger/revision/NOLOGIN executor proposal,
17 prechecks and16 postchecks, full existing-column digest and installation receipt.
Runtime never auto-installs. Source/label files preserved; automatic gates unchanged.
The assembled SQL has not run on a server; previous integration tests cover its
components only. Next: complete-package rehearsal on isolated OrioleDB, before any
separately authorized production installation/activation/apply. Local dictionary
TRUNCATE/reload requires package/receipt reconciliation.
[Bundle, writer audit and reproduction](research/2026-11-03-installation-package.md).


## Complete installation rehearsal (2026-11-04)

12/12 owned-OrioleDB tests pass, including the unchanged original bundle, captured
nine DDL hooks, full inventory, non-superuser installer, faults/recovery, and an
executor apply/retry/rollback. No installer correction needed. Production untouched.
The fixture's event-trigger ownership setup needed temporary superuser privileges;
removed before installer execution. Local data/SQL remain unchanged. Next: fresh
read-only real preflight, then separately authorized structural installation and
activation/apply. [Results and limitations](research/2026-11-04-installation-rehearsal.md).


## Refreshed real preflight (2026-11-04)

17/17 original installer checks PASS on the real Supabase MCP connection;233/233
human guards match,165pending. Inventory/configuration unchanged, schema/role absent.
Two READ ONLY transactions; no installation or LLM calls. Dedicated DSN not configured
or tested. Next: separately instructed structural installation, then postchecks;
executor stays NOLOGIN and score application is separate. Recheck under the install
lock; this observation reserves nothing. [Current result](research/2026-11-04-production-preflight.md).


## Production structural installation (2026-11-04)

Original bundle installed once on pdliedweugywbiczajxn following user instruction.
17/17 repeated prechecks and16/16 postchecks PASS; durable receipt read separately.
77,698 unique revisions; all existing columns/scores preserved by full-row hash.
Executor remains NOLOGIN; no credentials/activation/apply165. Private API-role USAGE
false; correction ledger empty. Next: separately instructed dedicated connection
setup/activation, initially read-only checks; apply remains separate. Do not rerun
installer or use score rollback.csv as uninstall. [Current state](research/2026-11-04-production-installation.md).


## Dedicated connection verified (2026-11-04)

Connection setup/controlled activation complete; no new grants or score changes.
Certificate/hostname-verified TLS, dedicated identity and explicit READ ONLY checks
pass for the existing revision contract and all human guards. Credentials/config
remain local and untracked. Startup read-only options were not applied by the pooler;
verification explicitly begins and checks READ ONLY. The installer NOLOGIN check
is intentionally obsolete after activation; do not weaken the immutable installer.
Next: separately instructed apply through the approved transactional flow.
[Current result](research/2026-11-04-executor-connection.md).


## Human corrections applied and independently verified (2026-11-04)

The approved human package is now applied:165 score/revision changes,77,533 rows
unchanged;233 human postconditions pass. A separate read-only connection confirmed
the durable receipt and full post-state, including unchanged remaining columns.
No runtime/grant/schema changes or LLM calls. Automatic upload gates still fail;
baseline-only changes remain unapplied. Keep original artifacts and guarded rollback.
Next: coordinated review/merge of stacked PR85/86; no further DB work for this lot.
[Current result](research/2026-11-04-human-application.md).
