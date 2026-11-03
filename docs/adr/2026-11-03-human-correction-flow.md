# Decision: separate approved human correction flow

Status: **accepted by the user, 2026-11-03**. Initial scope: implementation/offline tests;
subsequent approval covers disposable PostgreSQL integration. No production schema
deployment or application authorized or performed.

## Context

The frozen165 human corrections pass provenance, exact identity/POS, complete
233-row guards, inverse and L1 stability. The global incomplete positive seed
still fails its thresholds. User explicitly approved a separate human flow:
original human scores prevail; Jaccard stays mandatory; anchors are measured and
reported without vetoing this scoped flow. Automatic Step4 remains unchanged.

## Decision

- Separate `human_correction_flow` orchestration and `human_correction_postgres`
  transaction adapter; no changes to WordStore, Step4 or Step5. Default is offline
  `dry-run`, with no DSN lookup or store access. No general bypass flag.
- Approval record pins the existing audit-policy hash and exact package ID.
  An apply/rollback call additionally requires exact package confirmation and an
  explicit dedicated DSN. This is operational intent, not a cryptographic signature.
- Reuse the existing audit and source replay unchanged. Within a future execution
  transaction, capture the entire inventory and recheck every reviewed form/member,
  spelling/POS and score. Project only the approved IDs; preserve unrelated changes.
- Jaccard≥0.70 against **both** original pinned snapshot and locked current state.
  Measure legacy anchor precision/recall in both reports; failures remain visible
  but nonblocking here. No baseline changes can enter the package.
- Full-table `SHARE ROW EXCLUSIVE` locks on words and the receipt ledger precede
  the READ COMMITTED snapshot. PostgreSQL documents conflicts with ordinary writers;
  locks persist to transaction end. This avoids phantom POS/duplicate membership
  changes and serializes this small administrative batch. Normal reads continue.
  [PostgreSQL locking](https://www.postgresql.org/docs/17/explicit-locking.html).
- Compare-and-set each update using ID, literal spelling/POS, expected score and
  `xmin`. Enforce affected IDs/count, force deferred constraints before post-check,
  then compare the entire post-state, including untouched row versions. Recheck both
  inventory and stored receipt again after saving the ledger row; ledger triggers
  can introduce effects after the first check. Unexpected
  word-table trigger effects abort. Other tables/remote trigger effects are not
  covered by this inventory check and require deployment inspection.
- Write the durable receipt in a private schema in the **same transaction**;
  force synchronous commit. Psycopg transaction context commits only on normal exit,
  rolls back on exceptions. Local success receipt is written only after normal
  transaction exit. [Psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).
- A lost commit acknowledgement leaves an unconfirmed local attempt. Reissue the
  same action into a new output directory: query the ledger first, return the
  historical receipt, never reapply. `already_applied` does not claim that current
  rows are still identical. An already rolled-back package cannot be applied again.

## Rollback and row versions

Rollback requires the ledger receipt for the exact package/policy, exact changed
IDs and original values. Check all reviewed postconditions and membership; compare
changed-row `xmin` with the saved post-apply version. A same-score later write is a
conflict, so simple A→B→A edits do not pass. Preserve unrelated later edits.

`xmin` is a32-bit row version, not an eternal revision. Save the64-bit apply
transaction ID and fail closed if current transaction is earlier or ≥2^31
transactions later. No claim of portability across DB restore/replacement or
indefinite receipt validity. [PostgreSQL system columns](https://www.postgresql.org/docs/17/ddl-system-columns.html),
[transaction IDs](https://www.postgresql.org/docs/17/functions-info.html).

Rollback also requires both Jaccard checks; anchors remain diagnostic. Update only
receipt-confirmed IDs and mark that same ledger row rolled_back atomically. Lost
rollback acknowledgement is recovered identically, without repeated reversal.

## Consequences and limitations

Table locks briefly block writers:5s lock timeout,30s statement timeout. A dedicated
privileged backend role must see every word and own/access the private ledger;
`row_security=off` prevents silently accepting an RLS-filtered inventory. No schema
creation or role grants occur automatically. The SQL prerequisite is separate and
has been executed only on a disposable test server, **not in the project DB**. Existing schema conflicts deliberately fail.

CSV-first artifacts include preview, original approval/audit, locked before,
projected candidate, guard/quality reports, after-state and receipt. Inputs are
hash-checked before DML and before transaction exit. Local publication can fail after
commit; the DB ledger remains the recovery authority. Local CSVs/receipts cannot
prove a live transaction happened.

Initial tests used a memory transaction double and mocked psycopg boundary. The
subsequent approved integration ran17 tests on an owned Docker PostgreSQL17.9 server,
including real locks, concurrent writers, duplicate applies, role/RLS boundaries,
triggers, deferred failures, disconnect, restart and the full165-row package.
This exposed and fixed ledger-trigger effects after the first post-check. All tests
pass; container and volume are removed. Lost acknowledgement after a real commit
is injected at the transport boundary; this is not a physical power-loss test.
Production roles/triggers/schema were unverified at that stage.
[Integration report](../research/2026-11-03-postgres-integration.md).

## Production preflight follow-up (2026-11-03)

Read-only inspection found PostgreSQL17.9 with OrioleDB1.8 and words stored using
OrioleDB. Its xmin SELECT fails; the current adapter is **not deployable here**.
All233 data guards pass;165 changes remain pending. No production schema or score
changes. The accepted policy is unchanged; its xmin implementation needs an
engine-compatible revision mechanism, validated on isolated OrioleDB with ABA,
delete/reinsert, other writers and rollback. A future migration requires separate
authorization. [Preflight](../research/2026-11-03-production-preflight.md).
