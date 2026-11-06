# Separate, offline-prepared automatic installation

Scope: accepted automatic candidate, existing sequence-v1 revisions and completed
human corrections. Preparation/rehearsal do not authorize real installation or apply.

Public seams remain approved artifacts → SQL bundle and SQL bundle → database
pre/postchecks. `prepare_automatic_installation` never connects; the CLI has no DSN
or execute flag. Reuse the accepted flow's offline replay and existing small SQL
serialization helpers. Keep deployment observations/check expressions in a separate
module; reuse exactly the runtime revision-validator SQL, extracted as a constant
without changing its expression or human runtime behavior.

The bundle contains read-only preflight, one atomic installation, read-only postflight,
operator instructions, offline preview and complete artifact/input hashes. It pins
the observed environment, approved snapshot and human receipts. Installation locks
words, revision contract, human ledger and existing installation receipt. It creates
only a separate automatic ledger, installation receipt and NOLOGIN executor. No
revision bootstrap, score DML, login/password provisioning or human-grant changes.

The role uses BYPASSRLS with explicit SELECT/UPDATE words, SELECT contract and
SELECT/INSERT/UPDATE automatic ledger. Table-level UPDATE is needed by the existing
runtime lock. Check effective privileges and memberships; no sequence, human-ledger,
contract-write or installation-receipt access. The owner/DDL administrator remains
trusted; this is not protection against a malicious administrator or resealed files.

Before/after fingerprints cover all word columns; archived identities/scores/revisions
are also pinned. Postconditions run after the last installation receipt write. Pin
existing human receipts, grants, RLS, revision contract/epoch and reviewed DDL hooks.
Record/check sequence state independently: sequence changes are not transactional.
A failed DDL hook can leave a sequence advanced or reset despite transactional rollback.
Never reset a real sequence automatically to make a retry pass.

Lost acknowledgement: inspect the matching installation receipt and all postchecks.
Never infer rollback from a disconnected client or silently reinstall existing objects.
No automatic uninstall; activation/application and their rollback receipts are later
operations. Capture and checks are point-in-time; hosted external effects and private
schema API exposure still need operator review. Rehearse the exact immutable SQL on
an owned OrioleDB, including all archived rows and reviewed event-trigger definitions.
