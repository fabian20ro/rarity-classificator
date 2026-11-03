# Handover

## What This Project Replaces

This Python project replaces only the rarity/classification tooling. Backend API/runtime apps remain unchanged.

`fabian20ro/propozitii-absurde` is a consumer of DB rarity output only (`words.rarity_level` via `minRarity`/`rarity` filters). Classifier orchestration, prompts, and audits live in this repository.

## Non-Negotiable Contracts

- Output rarity levels stay in `1..5` with lower level = more common word.
- Step5 rebalance selections use only batch-local ids (`1..N`), no duplicates, no `0`, exact count.
- Automatic Step4 upload must stay gated by both:
  - L1 set stability (Jaccard vs reference),
  - L1 anchor precision/recall.
- Upload mode default is `partial`; `full-fallback` is explicit exception mode.

## What Worked

- Strict Step5 `local_id` contract: exact-count `1..N`, unique, no `0`, no word-id fallback.
- Batch split retries with preserved expected selection counts.
- Gated upload policy based on semantic quality metrics (not histogram only).
- CSV-first workflow with resumable JSONL logs and explicit checkpoints.
- Deterministic decoding profiles (`temperature=0`) for stable structured output.
- Stratified source mixing improves pair-level rebalance stability.

## What Did Not Work (and is avoided here)

- Accepting mixed id semantics (`word_id`/`local_id`) in rebalance output.
- Silent parser auto-fill of missing selections.
- Uploading solely because counts matched target distribution.
- Treating small anchor lists as sufficient long-term quality protection.

## Do / Don’t

Do:

- Keep rebalance prompts strict and schema-driven.
- Gate every upload with Jaccard + anchor metrics.
- Run low-confidence L1 human review regularly (`review-low-confidence` + `l1-review-check`).
- Expand anchor list over time (target >= 400 curated L1 words).
- Preserve partial upload default during iteration.

Don’t:

- Relax Step5 selection count checks.
- Re-enable permissive fallback that invents/auto-fills ids.
- Avoid `full-fallback` uploads unless explicitly intended.

## Suggested Baseline Run Flow

1. `step1-export`
2. one or more `step2-score` runs
3. optional `step3-compare`
4. optional `step5-rebalance`
5. `quality-audit` (must pass)
6. `step4-upload`

## Troubleshooting

- Frequent malformed LM output:
  - reduce `--batch-size`,
  - keep `temperature=0` model profiles,
  - use retry input builder for unresolved words.

- Rebalance count mismatch errors:
  - verify prompt files unchanged,
  - ensure model supports strict JSON output,
  - avoid manually editing rebalance local-id input shape.

- Low anchor precision:
  - check candidate L1 words manually,
  - tighten prompt instructions,
  - rerun targeted rebalance on levels `1+2 -> 1`.

## Handoff Checklist for Next Operator

- Confirm DB credentials and LM endpoint reachability.
- Confirm prompt files used in command are the intended ones.
- Confirm quality thresholds used for this campaign.
- Confirm upload mode is `partial` unless approved otherwise.
- Archive run command lines and generated artifacts paths.


## Approved human-only exception (2026-11-03)

User-approved separate flow: original human labels, exact pinned package, complete
live guards, Jaccard mandatory, anchors measured without veto. Default dry-run;
no change to Step4 behavior. Transactional receipt/recovery and guarded rollback
implemented and verified on disposable PostgreSQL17.9. Project DB schema deployment
and application remain unperformed. [Integration results](research/2026-11-03-postgres-integration.md).
**Production preflight found OrioleDB1.8 without xmin.** Explicit revision support
is now implemented and verified with28 tests on isolated OrioleDB; heap regression17
tests also pass. All233 guards matched,165 corrections pending. Production still
lacks revision/ledger/role deployment. Next: prepare that installation separately
from apply, including external-writer compatibility and all-row token bootstrap.
[Preflight evidence](research/2026-11-03-production-preflight.md).
[OrioleDB implementation/results](research/2026-11-03-orioledb-integration.md).
[Decision](adr/2026-11-03-human-correction-flow.md) ·
[Runbook/results](research/2026-11-03-human-flow.md).


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
