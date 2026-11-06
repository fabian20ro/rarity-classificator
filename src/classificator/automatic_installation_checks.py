"""SQL observations shared by capture and installation checks. No connection code."""

from .human_correction_postgres import REVISION_BODY, REVISION_VALID_SQL
from .human_installation import _literal

ROLE = "classificator_automatic_executor"
# Existing ACLs are compared excluding only the new role's entry. Its exact grants
# are checked separately after installation, so the human/API grants cannot expand.
STATE = {
    "server_version": "to_jsonb(current_setting('server_version'))",
    "engine_version": "(SELECT to_jsonb(extversion) FROM pg_extension WHERE extname='orioledb')",
    "words_owner": "(SELECT to_jsonb(pg_get_userbyid(relowner)) FROM pg_class WHERE oid='public.words'::regclass)",
    "schema_owner": "(SELECT to_jsonb(pg_get_userbyid(nspowner)) FROM pg_namespace WHERE nspname='classificator_private')",
    "inventory": """(SELECT jsonb_build_object('rows',count(*),'digest',encode(sha256(convert_to(string_agg(
        octet_length(id::text)::text||':'||id::text||
        octet_length(word)::text||':'||word||
        octet_length(type::text)::text||':'||type::text||
        octet_length(rarity_level::text)::text||':'||rarity_level::text||
        octet_length(classificator_revision::text)::text||':'||classificator_revision::text,
        '' ORDER BY id),'UTF8')),'hex')) FROM public.words)""",
    "epoch": "(SELECT jsonb_agg(epoch::text ORDER BY epoch) FROM classificator_private.words_revision_contract WHERE singleton)",
    "revision_valid": "(" + REVISION_VALID_SQL.replace("%s", _literal(REVISION_BODY)) + ")",
    "human_installation_receipt": "(SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY singleton),'[]'::jsonb) FROM classificator_private.installation_receipt r)",
    "human_receipts": "(SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY package_id),'[]'::jsonb) FROM classificator_private.human_correction_receipts r)",
    "words_security": f"""(SELECT jsonb_build_object('rls',relrowsecurity,'force_rls',relforcerowsecurity,
        'acl',(SELECT coalesce(jsonb_agg(a::text ORDER BY a::text),'[]'::jsonb) FROM unnest(relacl) a WHERE split_part(a::text,'=',1)<>'{ROLE}')) FROM pg_class WHERE oid='public.words'::regclass)""",
    "policies": "(SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY policyname),'[]'::jsonb) FROM pg_policies p WHERE schemaname='public' AND tablename='words')",
    "triggers": """(SELECT coalesce(jsonb_agg(jsonb_build_object('name',t.tgname,'enabled',t.tgenabled,'definition',pg_get_triggerdef(t.oid),'owner',pg_get_userbyid(p.proowner),'function_definition',pg_get_functiondef(p.oid)) ORDER BY t.tgname),'[]'::jsonb) FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid='public.words'::regclass AND NOT t.tgisinternal)""",
    "events": """(SELECT coalesce(jsonb_agg(jsonb_build_object('name',t.evtname,'event',t.evtevent,'enabled',t.evtenabled,'tags',t.evttags,'owner',pg_get_userbyid(t.evtowner),'security_definer',p.prosecdef,'definition',pg_get_functiondef(p.oid)) ORDER BY t.evtname),'[]'::jsonb) FROM pg_event_trigger t JOIN pg_proc p ON p.oid=t.evtfoid)""",
    "schema_acl": f"(SELECT coalesce(jsonb_agg(a::text ORDER BY a::text),'[]'::jsonb) FROM pg_namespace n CROSS JOIN LATERAL unnest(n.nspacl) a WHERE n.nspname='classificator_private' AND split_part(a::text,'=',1)<>'{ROLE}')",
    "private_objects": """(SELECT coalesce(jsonb_agg(jsonb_build_object('name',c.relname,'owner',pg_get_userbyid(c.relowner),'acl',(SELECT coalesce(jsonb_agg(x::text ORDER BY x::text),'[]'::jsonb) FROM unnest(c.relacl) x WHERE split_part(x::text,'=',1)<>'classificator_automatic_executor'),'rls',c.relrowsecurity,'engine',a.amname) ORDER BY c.relname),'[]'::jsonb) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_am a ON a.oid=c.relam WHERE n.nspname='classificator_private' AND c.relkind IN ('r','S') AND c.relname NOT IN ('automatic_promotion_receipts','automatic_installation_receipt'))""",
    "human_role": "(SELECT coalesce(jsonb_agg(jsonb_build_object('login',rolcanlogin,'inherit',rolinherit,'superuser',rolsuper,'bypassrls',rolbypassrls,'createrole',rolcreaterole,'createdb',rolcreatedb,'replication',rolreplication)),'[]'::jsonb) FROM pg_roles WHERE rolname='classificator_human_executor')",
    "human_memberships": """(SELECT coalesce(jsonb_agg(jsonb_build_object('role',r.rolname,'member',m.rolname,'admin',a.admin_option,'inherit',a.inherit_option,'set',a.set_option) ORDER BY r.rolname,m.rolname),'[]'::jsonb) FROM pg_auth_members a JOIN pg_roles r ON r.oid=a.roleid JOIN pg_roles m ON m.oid=a.member WHERE r.rolname='classificator_human_executor' OR m.rolname='classificator_human_executor')""",
}
FULL_DATA = "(SELECT encode(sha256(convert_to(string_agg(to_jsonb(w)::text,E'\\n' ORDER BY id),'UTF8')),'hex') FROM public.words w)"


def automatic_installation_capture_sql():
    """Return a read-only capture query for manual execution on the intended target."""
    pairs = ",".join(_literal(k) + "," + v for k, v in STATE.items())
    return (
        "BEGIN READ ONLY;\nSET LOCAL statement_timeout='30s';\nSET LOCAL lock_timeout='2s';\nSET LOCAL search_path=pg_catalog;\nSET LOCAL row_security=off;\nSELECT jsonb_build_object('version','automatic-installation-capture-v1','read_only',current_setting('transaction_read_only'),'captured_at',clock_timestamp(),'state',jsonb_build_object("
        + pairs
        + ")) AS capture;\nROLLBACK;\n"
    )


def deployment_checks(state):
    import json

    checks = {
        name: f"to_jsonb({expr})={_literal(json.dumps(state[name]))}::jsonb"
        for name, expr in STATE.items()
    }
    checks.update(
        {
            "owner_session": "current_user='postgres' AND has_schema_privilege(current_user,'classificator_private','CREATE')",
            "creator_capability": "(SELECT rolcreaterole AND rolbypassrls FROM pg_roles WHERE rolname=current_user)",
            "engine": "(SELECT am.amname='orioledb' FROM pg_class c JOIN pg_am am ON am.oid=c.relam WHERE c.oid='public.words'::regclass)",
            "no_null_identity": "NOT EXISTS (SELECT 1 FROM public.words WHERE id IS NULL OR word IS NULL OR type IS NULL OR rarity_level IS NULL OR classificator_revision IS NULL)",
            "sequence_ahead": "(SELECT is_called AND last_value >= (SELECT max(classificator_revision) FROM public.words) FROM classificator_private.words_revision_seq)",
            "no_rules": "NOT EXISTS (SELECT 1 FROM pg_rewrite WHERE ev_class='public.words'::regclass)",
            "no_defaults": "NOT EXISTS (SELECT 1 FROM pg_default_acl WHERE defaclrole=current_user::regrole AND (defaclnamespace=0 OR defaclnamespace='classificator_private'::regnamespace))",
            "api_roles_denied": "NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role','authenticator') AND has_schema_privilege(oid,'classificator_private','USAGE')) AND NOT EXISTS (SELECT 1 FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) a WHERE n.nspname='classificator_private' AND a.grantee=0)",
        }
    )
    pre = dict(
        checks,
        automatic_ledger_absent="to_regclass('classificator_private.automatic_promotion_receipts') IS NULL",
        installation_receipt_absent="to_regclass('classificator_private.automatic_installation_receipt') IS NULL",
        automatic_role_absent=f"NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{ROLE}')",
    )
    post = dict(
        checks,
        automatic_ledger_empty="(SELECT count(*)=0 FROM classificator_private.automatic_promotion_receipts)",
        executor_disabled=f"EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{ROLE}' AND NOT rolcanlogin AND rolbypassrls AND NOT rolsuper AND NOT rolinherit AND NOT rolcreaterole AND NOT rolcreatedb AND NOT rolreplication)",
        executor_memberships=f"NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE (roleid='{ROLE}'::regrole OR member='{ROLE}'::regrole) AND NOT (roleid='{ROLE}'::regrole AND member='postgres'::regrole AND admin_option AND NOT inherit_option AND NOT set_option))",
        executor_schema=f"has_schema_privilege('{ROLE}','public','USAGE') AND has_schema_privilege('{ROLE}','classificator_private','USAGE') AND NOT has_schema_privilege('{ROLE}','public','CREATE') AND NOT has_schema_privilege('{ROLE}','classificator_private','CREATE')",
        executor_no_sequence=f"NOT has_sequence_privilege('{ROLE}','classificator_private.words_revision_seq','USAGE') AND NOT has_sequence_privilege('{ROLE}','classificator_private.words_revision_seq','SELECT') AND NOT has_sequence_privilege('{ROLE}','classificator_private.words_revision_seq','UPDATE')",
        new_tables_private="""(SELECT count(*)=2 AND bool_and(am.amname='heap' AND pg_get_userbyid(c.relowner)='postgres') FROM pg_class c JOIN pg_am am ON am.oid=c.relam WHERE c.oid IN ('classificator_private.automatic_promotion_receipts'::regclass,'classificator_private.automatic_installation_receipt'::regclass)) AND NOT EXISTS (SELECT 1 FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a WHERE c.oid IN ('classificator_private.automatic_promotion_receipts'::regclass,'classificator_private.automatic_installation_receipt'::regclass) AND a.grantee NOT IN ('postgres'::regrole,'classificator_automatic_executor'::regrole))""",
        new_tables_no_hooks="""NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid IN ('classificator_private.automatic_promotion_receipts'::regclass,'classificator_private.automatic_installation_receipt'::regclass)) AND NOT EXISTS (SELECT 1 FROM pg_rewrite WHERE ev_class IN ('classificator_private.automatic_promotion_receipts'::regclass,'classificator_private.automatic_installation_receipt'::regclass))""",
    )
    # Check effective privileges, including inherited/PUBLIC grants, not just ACL text.
    for name, table, allowed in [
        ("words", "public.words", {"SELECT", "UPDATE"}),
        ("contract", "classificator_private.words_revision_contract", {"SELECT"}),
        (
            "ledger",
            "classificator_private.automatic_promotion_receipts",
            {"SELECT", "INSERT", "UPDATE"},
        ),
        ("human_ledger", "classificator_private.human_correction_receipts", set()),
        ("human_installation", "classificator_private.installation_receipt", set()),
        (
            "installation_receipt",
            "classificator_private.automatic_installation_receipt",
            set(),
        ),
    ]:
        post["executor_" + name] = " AND ".join(
            ("" if p in allowed else "NOT ") + f"has_table_privilege('{ROLE}','{table}','{p}')"
            for p in (
                "SELECT",
                "INSERT",
                "UPDATE",
                "DELETE",
                "TRUNCATE",
                "REFERENCES",
                "TRIGGER",
                "MAINTAIN",
            )
        )
    return pre, post


SEQUENCE_STATE = "(SELECT jsonb_build_object('last_value',last_value,'is_called',is_called) FROM classificator_private.words_revision_seq)"
