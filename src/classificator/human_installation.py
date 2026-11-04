"""Prepare a reviewable installation bundle offline. Never connects or executes SQL."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .evaluation.dataset import _read_csv, _sha256
from .human_correction_flow import run_human_corrections
from .human_correction_postgres import REVISION_BODY

VERSION = "human-installation-bundle-v1"
ROLE = "classificator_human_executor"
SQL_ROOT = Path(__file__).resolve().parents[2] / "docs/sql"
PROJECTION = """(SELECT encode(sha256(convert_to(string_agg(id::text||chr(9)||word||chr(9)||type::text||chr(9)||rarity_level::text||chr(10),'' ORDER BY id),'UTF8')),'hex') FROM public.words)"""
FULL_DATA = """(SELECT encode(sha256(convert_to(string_agg((to_jsonb(w)-'classificator_revision')::text, E'\\n' ORDER BY id),'UTF8')),'hex') FROM public.words w)"""


def _literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _read_checks(checks):
    entries = ",\n".join(
        f"{_literal(name)}, COALESCE(({expr}),false)" for name, expr in checks.items()
    )
    return (
        "BEGIN READ ONLY;\nSET LOCAL standard_conforming_strings=on;\nSET LOCAL search_path=pg_catalog;\nSET LOCAL row_security=off;\nSELECT jsonb_build_object(\n"
        + entries
        + "\n) AS checks;\nROLLBACK;\n"
    )


def _assert_checks(checks):
    return "\n".join(
        f"IF NOT COALESCE(({expr}),false) THEN RAISE EXCEPTION 'Installation check failed: {name}'; END IF;"
        for name, expr in checks.items()
    )


def _body(path):
    lines = path.read_text().splitlines()
    if lines.count("BEGIN;") != 1 or lines.count("COMMIT;") != 1:
        raise ValueError("Installation source must have one explicit transaction")
    return "\n".join(line for line in lines if line not in {"BEGIN;", "COMMIT;"})


def prepare_human_installation(approval_path, policy_path, preflight_manifest, output_dir):
    """Approved CSVs + pinned preflight → atomic SQL/checks/manifest, with no execution."""
    approval_path, policy_path, preflight_manifest, output_dir = map(
        Path, (approval_path, policy_path, preflight_manifest, output_dir)
    )
    if output_dir.exists():
        raise FileExistsError(output_dir)
    capture = preflight_manifest.parent
    manifest = json.loads(preflight_manifest.read_text())
    names = ("project.json", "metadata.json", "storage.json", "snapshot.json", "supplement.json")
    data = {}
    inputs = {str(preflight_manifest.resolve()): _sha256(preflight_manifest)}
    for name in names:
        path = capture / name
        if manifest["artifacts"].get(name) != _sha256(path):
            raise ValueError("Preflight capture hash mismatch: " + name)
        data[name] = json.loads(path.read_text())
        inputs[str(path.resolve())] = _sha256(path)
    meta, storage, snap = (data[n] for n in ("metadata.json", "storage.json", "snapshot.json"))
    if any(data[n].get("read_only") != "on" for n in names if n != "project.json"):
        raise ValueError("Preflight must have been read-only")
    if (
        storage["access_method"] != "orioledb"
        or {"name": "orioledb", "version": "1.8"} not in storage["extensions"]
    ):
        raise ValueError("Unsupported captured engine/version")
    if meta["ledger_schema"] or meta["ledger_table"] or meta["triggers"] or meta["rules"]:
        raise ValueError("Existing schema/triggers/rules require a new deployment review")
    config = json.loads(policy_path.read_text())
    snapshot = (policy_path.parent / config["sources"]["snapshot"]["path"]).resolve()
    rows = _read_csv(snapshot, {"word_id", "word", "type", "rarity_level"})
    fields = ("word_id", "word", "type", "rarity_level")
    if any(any(c in r[k] for c in "\t\r\n") for r in rows for k in fields):
        raise ValueError("Ambiguous snapshot fingerprint")
    digest = hashlib.sha256(
        "".join(
            "\t".join(r[k] for k in fields) + "\n"
            for r in sorted(rows, key=lambda r: int(r["word_id"]))
        ).encode()
    ).hexdigest()
    if (
        snap["fingerprint_sha256"] != digest
        or snap["count"] != len(rows)
        or snap["unsafe_delimiters"] != 0
    ):
        raise ValueError("Preflight inventory differs from approved snapshot")
    owner = meta["table"]["owner"]
    if owner != "postgres":
        raise ValueError("Deployment must be reviewed for the actual words owner")
    package = (policy_path.parent / config["sources"]["package_manifest"]["path"]).resolve().parent
    source_paths = [
        SQL_ROOT / "2026-11-03-human-correction-receipts.sql",
        SQL_ROOT / "2026-11-03-human-row-revisions.sql",
    ]
    for path in source_paths:
        inputs[str(path.resolve())] = _sha256(path)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent) as tmp:
        staged = Path(tmp) / "bundle"
        staged.mkdir()
        preview = run_human_corrections(approval_path, policy_path, staged / "audit")
        assert preview["status"] == "dry_run"
        audit_inputs = json.loads((staged / "audit/manifest.json").read_text())["inputs"]
        inputs.update(audit_inputs)
        for name in ("preconditions.csv", "corrections.csv", "rollback.csv", "references.csv"):
            (staged / name).write_bytes((package / name).read_bytes())
        checks = {
            "owner_session": f"current_user={_literal(owner)}",
            "owner_unchanged": f"(SELECT pg_get_userbyid(relowner)={_literal(owner)} FROM pg_class WHERE oid='public.words'::regclass)",
            "engine": "(SELECT am.amname='orioledb' FROM pg_class c JOIN pg_am am ON am.oid=c.relam WHERE c.oid='public.words'::regclass)",
            "extension": "(SELECT extversion='1.8' FROM pg_extension WHERE extname='orioledb')",
            "inventory": f"{PROJECTION}={_literal(digest)} AND (SELECT count(*) FROM public.words)={len(rows)}",
            "unambiguous_fingerprint": "NOT EXISTS (SELECT 1 FROM public.words WHERE strpos(word,chr(9))>0 OR strpos(word,chr(10))>0 OR strpos(word,chr(13))>0 OR strpos(type::text,chr(9))>0 OR strpos(type::text,chr(10))>0 OR strpos(type::text,chr(13))>0)",
            "schema_absent": "to_regnamespace('classificator_private') IS NULL",
            "role_absent": f"NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname={_literal(ROLE)})",
            "no_word_triggers": "NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='public.words'::regclass)",
            "no_word_rules": "NOT EXISTS (SELECT 1 FROM pg_rewrite WHERE ev_class='public.words'::regclass)",
            "no_global_default_grants": "NOT EXISTS (SELECT 1 FROM pg_default_acl WHERE defaclrole=current_user::regrole AND defaclnamespace=0)",
        }
        policies = json.dumps(meta["policies"], ensure_ascii=False)
        acl = json.dumps(sorted(meta["table"].get("acl") or []))
        events = {
            e["name"]: {k: v for k, v in e.items() if k not in {"name", "function"}}
            for e in data["supplement.json"]["event_triggers"]
        }
        checks.update(
            {
                "creator_capability": "(SELECT (rolsuper OR rolcreaterole) AND (rolsuper OR rolbypassrls) FROM pg_roles WHERE rolname=current_user) AND has_database_privilege(current_user,current_database(),'CREATE')",
                "server_version": "current_setting('server_version')="
                + _literal(meta["server_version"]),
                "rls_unchanged": "(SELECT relrowsecurity="
                + str(meta["table"]["rls"]).lower()
                + " AND relforcerowsecurity="
                + str(meta["table"]["force_rls"]).lower()
                + " FROM pg_class WHERE oid='public.words'::regclass)",
                "policies_unchanged": "(SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY policyname),'[]'::jsonb) FROM pg_policies p WHERE schemaname='public' AND tablename='words')="
                + _literal(policies)
                + "::jsonb",
                "word_grants_preserved": "(SELECT coalesce(jsonb_agg(a::text ORDER BY a::text),'[]'::jsonb) FROM pg_class c CROSS JOIN LATERAL unnest(c.relacl) a WHERE c.oid='public.words'::regclass AND split_part(a::text,'=',1)<>"
                + _literal(ROLE)
                + ")="
                + _literal(acl)
                + "::jsonb",
                "ddl_hooks_unchanged": "(SELECT coalesce(jsonb_object_agg(t.evtname,jsonb_build_object('event',t.evtevent,'enabled',t.evtenabled,'tags',t.evttags,'owner',pg_get_userbyid(t.evtowner),'security_definer',p.prosecdef,'definition',pg_get_functiondef(p.oid))),'{}'::jsonb) FROM pg_event_trigger t JOIN pg_proc p ON p.oid=t.evtfoid)="
                + _literal(json.dumps(events, ensure_ascii=False))
                + "::jsonb",
            }
        )
        post = {
            "inventory": checks["inventory"],
            "ledger_empty": "(SELECT count(*)=0 FROM classificator_private.human_correction_receipts)",
            "revisions_complete_unique": "(SELECT count(*)=count(classificator_revision) AND count(*)=count(DISTINCT classificator_revision) AND min(classificator_revision)>0 FROM public.words)",
            "revision_trigger": "EXISTS (SELECT 1 FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid='public.words'::regclass AND t.tgname='classificator_word_revision' AND t.tgenabled='A' AND t.tgtype=23 AND p.prosecdef AND p.proconfig=ARRAY['search_path=pg_catalog'] AND btrim(p.prosrc,E' \\n\\r\\t')="
            + _literal(REVISION_BODY)
            + ")",
            "role_disabled_and_bounded": f"EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{ROLE}' AND NOT rolcanlogin AND rolbypassrls AND NOT rolsuper AND NOT rolinherit AND NOT rolcreaterole AND NOT rolcreatedb AND NOT rolreplication)",
            "role_no_untrusted_memberships": f"NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE (roleid='{ROLE}'::regrole OR member='{ROLE}'::regrole) AND NOT (roleid='{ROLE}'::regrole AND member='postgres'::regrole AND admin_option AND NOT inherit_option AND NOT set_option))",
            "executor_grants": f"has_schema_privilege('{ROLE}','classificator_private','USAGE') AND has_table_privilege('{ROLE}','public.words','SELECT') AND has_table_privilege('{ROLE}','public.words','UPDATE') AND NOT has_table_privilege('{ROLE}','public.words','INSERT') AND NOT has_table_privilege('{ROLE}','public.words','DELETE') AND has_table_privilege('{ROLE}','classificator_private.words_revision_contract','SELECT') AND NOT has_table_privilege('{ROLE}','classificator_private.words_revision_contract','UPDATE') AND NOT has_sequence_privilege('{ROLE}','classificator_private.words_revision_seq','USAGE') AND NOT has_sequence_privilege('{ROLE}','classificator_private.words_revision_seq','UPDATE')",
        }
        post["revision_sequence"] = (
            "EXISTS (SELECT 1 FROM pg_sequence WHERE seqrelid='classificator_private.words_revision_seq'::regclass AND seqtypid='bigint'::regtype AND seqincrement=1 AND seqmin=1 AND seqcache=1 AND NOT seqcycle)"
        )
        post.update(
            {
                k: checks[k]
                for k in (
                    "rls_unchanged",
                    "policies_unchanged",
                    "word_grants_preserved",
                    "ddl_hooks_unchanged",
                )
            }
        )
        post["ledger_grants"] = (
            f"has_table_privilege('{ROLE}','classificator_private.human_correction_receipts','SELECT') AND has_table_privilege('{ROLE}','classificator_private.human_correction_receipts','INSERT') AND has_table_privilege('{ROLE}','classificator_private.human_correction_receipts','UPDATE') AND NOT has_table_privilege('{ROLE}','classificator_private.human_correction_receipts','DELETE') AND NOT has_table_privilege('{ROLE}','classificator_private.human_correction_receipts','TRUNCATE')"
        )
        post["api_roles_denied"] = (
            "NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role','authenticator') AND has_schema_privilege(oid,'classificator_private','USAGE')) AND NOT EXISTS (SELECT 1 FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) a WHERE n.nspname='classificator_private' AND a.grantee=0)"
        )
        grants = f""" CREATE ROLE {ROLE} NOLOGIN BYPASSRLS NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT USAGE ON SCHEMA public, classificator_private TO {ROLE};
GRANT SELECT, UPDATE ON public.words TO {ROLE};
GRANT SELECT ON classificator_private.words_revision_contract TO {ROLE};
GRANT SELECT, INSERT, UPDATE ON classificator_private.human_correction_receipts TO {ROLE};"""
        sql = (
            """BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='120s';
SET LOCAL standard_conforming_strings=on;
SET LOCAL search_path=pg_catalog;
SET LOCAL row_security=off;
SET LOCAL default_table_access_method=orioledb;
SET LOCAL createrole_self_grant='';
LOCK TABLE public.words IN ACCESS EXCLUSIVE MODE;
DO $installation$
DECLARE before_data text; after_data text;
BEGIN
"""
            + _assert_checks(checks)
            + f"\nbefore_data := {FULL_DATA};\n"
            + "\n".join(_body(p) for p in source_paths)
            + "\n"
            + grants
            + "\n"
            + _assert_checks(post)
            + f"""
after_data := {FULL_DATA};
IF before_data IS DISTINCT FROM after_data THEN RAISE EXCEPTION 'Installation altered existing word data'; END IF;
CREATE TABLE classificator_private.installation_receipt (
    singleton boolean PRIMARY KEY CHECK(singleton), receipt jsonb NOT NULL
) USING heap;
REVOKE ALL ON TABLE classificator_private.installation_receipt FROM PUBLIC;
INSERT INTO classificator_private.installation_receipt VALUES (true,jsonb_build_object(
    'version','{VERSION}','package_id',{_literal(json.loads(approval_path.read_text())["package_id"])},
    'data_before',before_data,'data_after',after_data,'inventory_sha256',{_literal(digest)},
    'epoch',(SELECT epoch FROM classificator_private.words_revision_contract),
    'installed_at',clock_timestamp(),'executor_login',false,'corrections_applied',false));
END;
$installation$;
COMMIT;
"""
        )
        post["installation_receipt_bound"] = (
            f"EXISTS (SELECT 1 FROM classificator_private.installation_receipt i CROSS JOIN classificator_private.words_revision_contract c WHERE i.singleton AND c.singleton AND i.receipt->>'package_id'={_literal(json.loads(approval_path.read_text())['package_id'])} AND i.receipt->>'epoch'=c.epoch::text AND i.receipt->>'inventory_sha256'={_literal(digest)} AND i.receipt->>'corrections_applied'='false')"
        )
        post["existing_data_preserved"] = (
            f"EXISTS (SELECT 1 FROM classificator_private.installation_receipt WHERE receipt->>'version'='{VERSION}' AND receipt->>'data_before'=receipt->>'data_after' AND receipt->>'data_after'={FULL_DATA})"
        )
        prefix, suffix = sql.rsplit("\nEND;\n$installation$", 1)
        sql = prefix + "\n" + _assert_checks(post) + "\nEND;\n$installation$" + suffix
        tag = "$install_" + hashlib.sha256(sql.encode()).hexdigest()[:16] + "$"
        while tag in sql:
            tag = tag[:-1] + "x$"
        sql = sql.replace("DO $installation$", "DO " + tag, 1)
        sql = sql.removesuffix("$installation$;\nCOMMIT;\n") + tag + ";\nCOMMIT;\n"
        (staged / "01-preflight.sql").write_text(_read_checks(checks))
        (staged / "02-install.sql").write_text(sql)
        (staged / "03-postflight.sql").write_text(_read_checks(post))
        (staged / "README.md").write_text(
            """# Prepared installation bundle — NOT executed

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
"""
        )
        report = dict(
            version=VERSION,
            project=data["project.json"]["id"],
            preflight_captured_at=snap["captured_at"],
            scope=config["scope"],
            inventory_rows=len(rows),
            inventory_sha256=digest,
            executor=ROLE,
            preflight_checks=list(checks),
            postflight_checks=list(post),
            installation_authorized=False,
            execution_ready=False,
            sql_executed=False,
            db_calls=0,
            model_calls=0,
        )
        _json(staged / "report.json", report)
        for path, h in inputs.items():
            if _sha256(Path(path)) != h:
                raise ValueError("Installation input changed")
        _json(
            staged / "manifest.json",
            dict(
                version=VERSION,
                inputs=inputs,
                implementation={str(Path(__file__).resolve()): _sha256(Path(__file__))},
                artifacts={
                    str(p.relative_to(staged)): _sha256(p) for p in staged.rglob("*") if p.is_file()
                },
            ),
        )
        staged.rename(output_dir)
    return report


def verify_installation_bundle(output_dir):
    """Artifact integrity only; never grants installation/execution authority."""
    root = Path(output_dir)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest["version"] != VERSION:
        raise ValueError("Unknown installation bundle")
    actual = {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and p != root / "manifest.json"
    }
    if actual != set(manifest["artifacts"]) or any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("Installation artifact inventory differs from manifest")
    for name, digest in manifest["artifacts"].items():
        if _sha256(root / name) != digest:
            raise ValueError("Installation artifact changed: " + name)
    return dict(valid=True, installation_authorized=False, execution_ready=False)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--preflight-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            prepare_human_installation(
                args.approval, args.policy, args.preflight_manifest, args.output
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
