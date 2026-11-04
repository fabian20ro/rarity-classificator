-- Production deployment prerequisite; CLI never installs it automatically.
-- Validated only in the disposable PostgreSQL integration server; not installed in the project DB.
-- Run only after explicit schema-deployment authorization, as the intended owner.
-- Use a dedicated privileged backend role. Never expose this schema via the web API.
BEGIN;
CREATE SCHEMA classificator_private;
REVOKE ALL ON SCHEMA classificator_private FROM PUBLIC;
CREATE TABLE classificator_private.human_correction_receipts (
    package_id text PRIMARY KEY CHECK (package_id ~ '^[a-f0-9]{64}$'),
    receipt jsonb NOT NULL CHECK (
        jsonb_typeof(receipt) = 'object'
        AND receipt ?& ARRAY['version', 'package_id', 'policy_sha256', 'state',
                            'apply_txid', 'changed_ids', 'changes', 'post_versions']
        AND receipt->>'version' = 'human-corrections-flow-v1'
        AND receipt->>'package_id' = package_id
        AND receipt->>'state' IN ('applied', 'rolled_back')
    )
);
REVOKE ALL ON TABLE classificator_private.human_correction_receipts FROM PUBLIC;
COMMIT;
-- Deliberately no IF NOT EXISTS: incompatible existing schema must fail, not be accepted.
-- No changes to public.words, RLS, automatic-upload policy or application-role grants.
