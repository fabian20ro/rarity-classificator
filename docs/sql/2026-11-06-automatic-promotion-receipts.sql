-- Separate deployment prerequisite. Never executed by the automatic runtime.
-- This stage installs it only on an owned disposable test server.
-- Existing private schema and sequence revision contract are required.
-- No role, human-ledger, words, RLS or application-grant changes here.
BEGIN;
CREATE TABLE classificator_private.automatic_promotion_receipts (
    package_id text PRIMARY KEY CHECK (package_id ~ '^[a-f0-9]{64}$'),
    receipt jsonb NOT NULL CHECK (
        jsonb_typeof(receipt) = 'object'
        AND receipt ?& ARRAY['version', 'package_id', 'approval_sha256', 'state',
                            'apply_txid', 'changes', 'post_versions', 'row_version_contract', 'quality']
        AND receipt->>'version' = 'automatic-promotion-flow-v1'
        AND receipt->>'package_id' = package_id
        AND receipt->>'state' IN ('applied', 'rolled_back')
    )
) USING heap;
REVOKE ALL ON TABLE classificator_private.automatic_promotion_receipts FROM PUBLIC;
COMMIT;
-- Deliberately fail if the table already exists. No automatic repair or broad bypass.
-- Deployment must provision a separate backend role with schema USAGE, full-inventory
-- SELECT/UPDATE words (table-level privilege for the lock), SELECT revision contract,
-- and SELECT/INSERT/UPDATE automatic receipts. No sequence/contract/DDL grants.
-- Human executor grants and human receipts remain unchanged.
