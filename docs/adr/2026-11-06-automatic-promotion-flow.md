# Approved provisional automatic promotion

User accepted `automatic-provisional-acceptance-v1` after reviewing the audit package.
Scope: frozen candidate `d7f52e307c523b74958bad4cf483706159cf843f4dbb593abea477c1611aa8ef`,
both wordfreq and fallback, human overrides protected. Acceptance is not a claim of
population accuracy and does not authorize live installation/application in this stage.

## Implementation plan and test seams

1. Pinned audit package + acceptance record → offline preview. Regenerate the package
   from original CSVs, compare all artifacts, require exact candidate and route scope.
2. Same public flow → apply/retry/rollback with injected transaction store. Default
   remains offline. Execution needs exact package confirmation and expected revision
   installation epoch. One transaction covers both disjoint routes, preserving the
   final candidate as a single accepted state. No histogram-only or generic bypass.
3. Separate PostgreSQL adapter and automatic receipt ledger. Reuse the existing
   revision-contract validator; leave human orchestration/adapter/grants untouched.
   Full inventory snapshot includes a fingerprint of other columns to catch trigger
   side effects. Compare identities/scores/revisions before updates; validate complete
   post-state and receipt after the final ledger write. One parameterized multi-row
   CAS statement for both routes avoids 50,724 network round trips. No parallel calls.
4. Owned OrioleDB rehearsal: both routes, failures, uncertain commit, retry, revision
   drift, rollback and full inventory. Pinned image, no production DSN accepted.

Implemented and verified:18real-server tests, including all77,698rows and50,724changes.
The missing image was downloaded again; owned server and volume removed afterward.
[Results and deployment leftovers](../research/2026-11-06-automatic-flow.md).

## Quality contract

All Jaccard and seed precision/recall metrics remain mandatory and recorded with
their unmodified 0.70/0.80/0.80 thresholds and actual FAIL results. In this separate,
hash-bound accepted scope they are diagnostics. No changes to Step4/Step5 or legacy
upload gates. A new candidate or changed source requires a new acceptance record.

## Transaction and recovery contract

Sequence-v1 revisions only, with explicitly expected installation epoch. Full-table
locks precede READ COMMITTED snapshots; source hashes checked before writes and
commit. Apply rejects any archived identity/score/revision drift. Rollback uses the
committed receipt's post-write revisions, protects all reviewed members and preserves
unrelated subsequent edits. Idempotent retry returns historical success, not a claim
that current scores still match. Rolled-back packages cannot be applied again.

The acceptance record records operational intent, not cryptographic authentication.
Dedicated DSN/DB grants remain the access boundary. Local files do not prove commit;
the private ledger is authoritative. Deployment inspection of triggers, other-table
effects, roles/RLS and current data remains necessary before any live action.
