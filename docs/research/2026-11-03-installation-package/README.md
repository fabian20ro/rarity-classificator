# Prepared installation bundle — NOT executed

This bundle does not authorize installation, login activation or correction apply.
Verify manifest integrity with `verify_installation_bundle(path)` before review/use.
Use the source worktree/version recorded by manifest.json; inputs and SQL are pinned.

Order after explicit installation authorization:
1. Confirm the target project from report.json and the connection endpoint. An
   identical cloned inventory is not proof of project identity. Use the words owner.
2. Run 01-preflight.sql READ ONLY. Every check must be true. Save the JSON result
   outside this immutable bundle. Confirm external writers/API schema exposure;
   schedule a maintenance window for an ACCESS EXCLUSIVE lock on all words.
3. Execute 02-install.sql once, using a client that stops on the first error
   (psql: -X --set=ON_ERROR_STOP=1 --file=02-install.sql). It repeats preconditions
   under the lock, installs ledger/revisions/role and checks data before COMMIT.
   Do not execute the historical component SQL files separately or in addition.
4. Run 03-postflight.sql READ ONLY; save all checks and the private installation
   receipt. All existing word columns/scores must match the pre-install digest.
   No correction receipt should exist. These checks describe the installation
   state before any future corrections; they are not a general post-apply audit.
5. Executor remains NOLOGIN, with no password in this bundle. Credential creation,
   login activation, real-DSN checks and apply165 require separate instructions.
   No role memberships for API roles. Never expose the private schema via Data API.

Recovery: any failed check aborts the single schema/role/data transaction. Close
or explicitly roll back the failed connection. Inspect actual state read-only
before retrying; an acknowledgement failure does not prove rollback. A matching
installation receipt plus passing postchecks is required to recognize success.
Existing installation/role/schema makes this installer fail; no silent resume or
automatic DROP/uninstall. SQL rollback.csv concerns later score corrections only.
DDL hooks may advance external bookkeeping counters even when installation aborts.

Token bootstrap updates every row's new revision, preserving every existing column.
Never reset the sequence or disable its trigger. Dictionary truncate/reload and
backup restore require package/receipt reconciliation. Schema owners remain trusted.
This assembled SQL was prepared and checked offline; it has NOT been executed.
Rehearse the complete package on an isolated target before production installation.
