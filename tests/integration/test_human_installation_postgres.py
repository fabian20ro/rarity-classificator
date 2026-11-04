"""Execute generated installation SQL only on an owned disposable OrioleDB."""

import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from classificator.human_installation import prepare_human_installation, verify_installation_bundle
from tests import test_human_installation as fixtures
from tests.postgres_harness import ROOT, isolated_postgres
from tests.test_local_evidence import read

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_HUMAN_INSTALLATION_INTEGRATION") != "1",
    reason="Opt in to owned OrioleDB installation rehearsal",
)


@pytest.fixture(scope="module")
def cluster():
    assert os.environ.get("HUMAN_PG_ENGINE") == "orioledb"
    with isolated_postgres() as server:
        with psycopg.connect(server.dsn, autocommit=True) as conn:
            conn.execute("CREATE ROLE postgres LOGIN CREATEROLE BYPASSRLS PASSWORD 'isolated_only'")
            for role in ("anon", "authenticated", "service_role", "authenticator"):
                conn.execute(sql.SQL("CREATE ROLE {}").format(sql.Identifier(role)))
        yield server


def checks(dsn, path):
    with psycopg.connect(dsn, autocommit=True) as conn:
        cur = conn.execute(path.read_text())
        while cur.description is None:
            assert cur.nextset()
        return cur.fetchone()[0]


def install(dsn, bundle, mode=None):
    with psycopg.connect(dsn, autocommit=True) as conn:
        if mode:
            conn.execute("SELECT set_config('rehearsal.fault',%s,false)", (mode,))
        conn.execute((bundle / "02-install.sql").read_text())


@contextmanager
def prepared(cluster, tmp_path, full=False, captured_hooks=False):
    approval, policy, capture_manifest = fixtures.inputs(tmp_path)
    if full:
        approval = ROOT / "docs/research/2026-11-03-human-flow/approval.json"
        policy = ROOT / "docs/research/2026-11-03-human-acceptance/policy.json"
    config = json.loads(policy.read_text())
    rows = read(Path(config["sources"]["snapshot"]["path"]))
    admin = cluster.database()
    dbname = conninfo_to_dict(admin)["dbname"]
    owner = make_conninfo(admin, user="postgres", password="isolated_only")
    capture = capture_manifest.parent
    try:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(
                sql.SQL("ALTER DATABASE {} OWNER TO postgres").format(sql.Identifier(dbname))
            )
            conn.execute("CREATE EXTENSION orioledb")
            conn.execute("SET default_table_access_method=orioledb")
            conn.execute(
                "CREATE TABLE public.words (id bigint PRIMARY KEY, word text NOT NULL, type text NOT NULL, rarity_level integer NOT NULL, extra text DEFAULT 'preserve me')"
            )
            with conn.cursor().copy(
                "COPY public.words (id,word,type,rarity_level) FROM STDIN"
            ) as copy:
                for r in rows:
                    copy.write_row((r["word_id"], r["word"], r["type"], r["rarity_level"]))
            conn.execute("ALTER TABLE public.words OWNER TO postgres")
            conn.execute("ALTER TABLE public.words ENABLE ROW LEVEL SECURITY")
            conn.execute(
                'CREATE POLICY "Enable read access for all users" ON public.words FOR SELECT USING(true)'
            )
            conn.execute("SET ROLE postgres")
            conn.execute("GRANT SELECT ON public.words TO anon")
            conn.execute("GRANT ALL ON public.words TO service_role")
            conn.execute("RESET ROLE")
            conn.execute("CREATE SEQUENCE public.ddl_counter")
            conn.execute("GRANT USAGE ON SEQUENCE public.ddl_counter TO postgres")
            conn.execute("""CREATE FUNCTION public.rehearsal_hook() RETURNS event_trigger
                LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
                DECLARE cmd record;
                BEGIN
                  PERFORM nextval('public.ddl_counter');
                  FOR cmd IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
                    IF cmd.object_identity='classificator_private.installation_receipt' THEN
                      IF current_setting('rehearsal.fault',true)='reject' THEN
                        RAISE EXCEPTION 'injected DDL failure';
                      ELSIF current_setting('rehearsal.fault',true)='mutate' THEN
                        UPDATE public.words SET extra='unexpected';
                      ELSIF current_setting('rehearsal.fault',true)='disconnect' THEN
                        PERFORM pg_terminate_backend(pg_backend_pid());
                      END IF;
                    END IF;
                    IF cmd.schema_name='public' AND cmd.object_type='table' AND cmd.command_tag='CREATE TABLE' THEN
                      EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY',cmd.object_identity);
                    END IF;
                  END LOOP;
                END $$""")
            conn.execute(
                "CREATE EVENT TRIGGER rehearsal_hook ON ddl_command_end EXECUTE FUNCTION public.rehearsal_hook()"
            )
            if captured_hooks:
                conn.execute("DROP EVENT TRIGGER rehearsal_hook")
                # Bootstrap historical event ownership, then remove SUPERUSER before installation.
                conn.execute("ALTER ROLE postgres SUPERUSER")
                conn.execute("CREATE ROLE supabase_admin SUPERUSER NOLOGIN")
                for schema in ("extensions", "graphql", "graphql_public"):
                    conn.execute(
                        sql.SQL("CREATE SCHEMA {} AUTHORIZATION supabase_admin").format(
                            sql.Identifier(schema)
                        )
                    )
                conn.execute("CREATE SEQUENCE graphql.seq_schema_version")
                conn.execute("ALTER SEQUENCE graphql.seq_schema_version OWNER TO supabase_admin")
                events = json.loads(
                    (
                        ROOT.parent / "human-production-preflight-2026-11-03/supplement.json"
                    ).read_text()
                )["event_triggers"]
                # Captured function bodies are reviewed local fixtures; no hosted service/extension call.
                for e in events:
                    conn.execute(e["definition"])
                    function = re.search(r"FUNCTION ([a-z_]+)\.([a-z_]+)\(", e["definition"])
                    ident = sql.Identifier(function[1], function[2])
                    conn.execute(
                        sql.SQL("ALTER FUNCTION {}() OWNER TO {}").format(
                            ident, sql.Identifier(e["owner"])
                        )
                    )
                for e in events:
                    function = re.search(r"FUNCTION ([a-z_]+)\.([a-z_]+)\(", e["definition"])
                    tags = (
                        sql.SQL("")
                        if e["tags"] is None
                        else sql.SQL(" WHEN TAG IN ({})").format(
                            sql.SQL(",").join(sql.Literal(t) for t in e["tags"])
                        )
                    )
                    conn.execute(
                        sql.SQL("CREATE EVENT TRIGGER {} ON {}{} EXECUTE FUNCTION {}()").format(
                            sql.Identifier(e["name"]),
                            sql.SQL(e["event"]),
                            tags,
                            sql.Identifier(function[1], function[2]),
                        )
                    )
                    conn.execute(
                        sql.SQL("ALTER EVENT TRIGGER {} OWNER TO {}").format(
                            sql.Identifier(e["name"]), sql.Identifier(e["owner"])
                        )
                    )
            if captured_hooks:
                conn.execute("ALTER ROLE postgres NOSUPERUSER")
            meta = json.loads((capture / "metadata.json").read_text())
            meta["server_version"] = conn.execute("SHOW server_version").fetchone()[0]
            meta["table"]["acl"] = conn.execute(
                "SELECT relacl::text[] FROM pg_class WHERE oid='public.words'::regclass"
            ).fetchone()[0]
            meta["policies"] = conn.execute(
                "SELECT jsonb_agg(to_jsonb(p) ORDER BY policyname) FROM pg_policies p WHERE schemaname='public' AND tablename='words'"
            ).fetchone()[0]
            events = conn.execute(
                "SELECT jsonb_agg(jsonb_build_object('name',t.evtname,'event',t.evtevent,'enabled',t.evtenabled,'tags',t.evttags,'owner',pg_get_userbyid(t.evtowner),'security_definer',p.prosecdef,'definition',pg_get_functiondef(p.oid))) FROM pg_event_trigger t JOIN pg_proc p ON p.oid=t.evtfoid"
            ).fetchone()[0]
        (capture / "metadata.json").write_text(json.dumps(meta))
        (capture / "supplement.json").write_text(
            json.dumps(dict(read_only="on", event_triggers=events))
        )
        canonical = "".join(
            "\t".join(r[k] for k in ("word_id", "word", "type", "rarity_level")) + "\n"
            for r in sorted(rows, key=lambda r: int(r["word_id"]))
        )
        snap = json.loads((capture / "snapshot.json").read_text())
        snap.update(
            count=len(rows), fingerprint_sha256=hashlib.sha256(canonical.encode()).hexdigest()
        )
        (capture / "snapshot.json").write_text(json.dumps(snap))
        manifest = json.loads(capture_manifest.read_text())
        manifest["artifacts"] = {
            name: hashlib.sha256((capture / name).read_bytes()).hexdigest()
            for name in manifest["artifacts"]
        }
        capture_manifest.write_text(json.dumps(manifest))
        bundle = tmp_path / "bundle"
        prepare_human_installation(approval, policy, capture_manifest, bundle)
        if captured_hooks:
            bundle = ROOT.parent / "human-installation-2026-11-03/verified"
        assert verify_installation_bundle(bundle)["valid"]
        yield owner, admin, bundle, approval, policy
    finally:
        with psycopg.connect(cluster.dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(dbname)))
            conn.execute("DROP ROLE IF EXISTS classificator_human_executor")
            conn.execute("DROP ROLE IF EXISTS supabase_admin")


def test_complete_bundle_installs_as_non_superuser_and_survives_restart(cluster, tmp_path):
    with prepared(cluster, tmp_path) as (owner, admin, bundle, _, _):
        before = checks(owner, bundle / "01-preflight.sql")
        assert all(before.values()), before
        install(owner, bundle)
        after = checks(owner, bundle / "03-postflight.sql")
        assert all(after.values()), after
        cluster.restart()
        assert checks(owner, bundle / "03-postflight.sql") == after
        with pytest.raises(psycopg.Error, match="schema_absent"):
            install(owner, bundle)
        assert checks(owner, bundle / "03-postflight.sql") == after


@pytest.mark.parametrize("fault", ["reject", "mutate", "disconnect"])
def test_failed_installation_leaves_no_partial_objects_and_retry_succeeds(cluster, tmp_path, fault):
    with prepared(cluster, tmp_path) as (owner, admin, bundle, _, _):
        with pytest.raises(psycopg.Error):
            install(owner, bundle, fault)
        # Same public preflight proves schema/role absent and inventory unchanged.
        before = checks(owner, bundle / "01-preflight.sql")
        assert all(before.values()), before
        with psycopg.connect(admin) as conn:
            assert conn.execute(
                "SELECT bool_and(extra='preserve me') FROM public.words"
            ).fetchone() == (True,)
        install(owner, bundle)
        assert all(checks(owner, bundle / "03-postflight.sql").values())


def test_inventory_drift_refuses_installation_before_any_schema_change(cluster, tmp_path):
    with prepared(cluster, tmp_path) as (owner, admin, bundle, _, _):
        with psycopg.connect(admin) as conn:
            conn.execute("UPDATE public.words SET word=word||'changed' WHERE id=100")
        before = checks(owner, bundle / "01-preflight.sql")
        assert not before["inventory"]
        with pytest.raises(psycopg.Error, match="inventory"):
            install(owner, bundle)
        after = checks(owner, bundle / "01-preflight.sql")
        assert after == before and after["schema_absent"] and after["role_absent"]


def test_exclusive_lock_timeout_is_atomic_and_retryable(cluster, tmp_path):
    with prepared(cluster, tmp_path) as (owner, admin, bundle, _, _):
        with psycopg.connect(admin) as blocker:
            blocker.execute("LOCK TABLE public.words IN ACCESS SHARE MODE")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                install(owner, bundle)
        assert all(checks(owner, bundle / "01-preflight.sql").values())
        install(owner, bundle)
        assert all(checks(owner, bundle / "03-postflight.sql").values())


def test_lost_commit_ack_is_recovered_by_receipt_without_reinstallation(cluster, tmp_path):
    with prepared(cluster, tmp_path) as (owner, admin, bundle, _, _):

        def lose_ack():
            install(owner, bundle)
            raise ConnectionError("simulated ACK loss after real commit")

        with pytest.raises(ConnectionError):
            lose_ack()
        assert all(checks(owner, bundle / "03-postflight.sql").values())
        with psycopg.connect(admin) as conn:
            before = conn.execute(
                "SELECT receipt FROM classificator_private.installation_receipt"
            ).fetchone()[0]
        with pytest.raises(psycopg.Error, match="schema_absent"):
            install(owner, bundle)
        with psycopg.connect(admin) as conn:
            assert (
                conn.execute(
                    "SELECT receipt FROM classificator_private.installation_receipt"
                ).fetchone()[0]
                == before
            )
        assert all(checks(owner, bundle / "03-postflight.sql").values())


@pytest.mark.skipif(
    os.environ.get("RUN_HUMAN_POSTGRES_FULL_INVENTORY") != "1",
    reason="Needs pinned local evaluation artifacts",
)
def test_full_inventory_install_then_executor_apply_and_rollback(cluster, tmp_path):
    from classificator.human_correction_flow import run_human_corrections
    from classificator.human_correction_postgres import PostgresHumanStore

    with prepared(cluster, tmp_path, full=True) as (owner, admin, bundle, approval, policy):
        assert all(checks(owner, bundle / "01-preflight.sql").values())
        install(owner, bundle)
        after = checks(owner, bundle / "03-postflight.sql")
        assert all(after.values()), after
        # Test-only activation on owned server, never part of installation SQL.
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute("ALTER ROLE classificator_human_executor LOGIN PASSWORD 'isolated_only'")
        executor = make_conninfo(
            admin, user="classificator_human_executor", password="isolated_only"
        )
        store = PostgresHumanStore(executor)
        package = json.loads(approval.read_text())["package_id"]

        def run(action, directory):
            return run_human_corrections(
                approval,
                policy,
                tmp_path / directory,
                action=action,
                store=store,
                confirm_package=package,
            )

        assert run("apply", "apply")["status"] == "applied"
        assert run("apply", "retry")["status"] == "already_applied"
        assert run("rollback", "rollback")["status"] == "rolled_back"
        with psycopg.connect(admin) as conn:
            assert conn.execute(
                "SELECT count(*),bool_and(extra='preserve me') FROM public.words"
            ).fetchone() == (77698, True)
        # Receipt and tokens legitimately changed; score projection still matches.
        assert checks(owner, bundle / "03-postflight.sql")["inventory"]


@pytest.mark.skipif(
    os.environ.get("RUN_HUMAN_POSTGRES_FULL_INVENTORY") != "1",
    reason="Needs original bundle and captured hooks",
)
def test_original_immutable_bundle_with_captured_nine_hooks(cluster, tmp_path):
    with prepared(cluster, tmp_path, full=True, captured_hooks=True) as (
        owner,
        admin,
        bundle,
        _,
        _,
    ):
        before = checks(owner, bundle / "01-preflight.sql")
        assert all(before.values()), before
        install(owner, bundle)
        after = checks(owner, bundle / "03-postflight.sql")
        assert all(after.values()), after
        (tmp_path / "original-bundle-prechecks.json").write_text(json.dumps(before, indent=2))
        (tmp_path / "original-bundle-postchecks.json").write_text(json.dumps(after, indent=2))
        with psycopg.connect(admin) as conn:
            receipt = conn.execute(
                "SELECT receipt FROM classificator_private.installation_receipt"
            ).fetchone()[0]
            assert conn.execute("SELECT count(*) FROM public.words").fetchone() == (77698,)
        (tmp_path / "installation-receipt.json").write_text(json.dumps(receipt, indent=2))
        cluster.restart()
        assert all(checks(owner, bundle / "03-postflight.sql").values())


@pytest.mark.parametrize(
    ("damage", "failed_check"),
    [
        ("GRANT USAGE ON SCHEMA classificator_private TO anon", "api_roles_denied"),
        (
            "ALTER TABLE public.words DISABLE TRIGGER classificator_word_revision",
            "revision_trigger",
        ),
        (
            "UPDATE public.words SET extra='changed outside installer' WHERE id=100",
            "existing_data_preserved",
        ),
    ],
)
def test_postflight_rejects_permission_trigger_and_non_score_data_drift(
    cluster, tmp_path, damage, failed_check
):
    with prepared(cluster, tmp_path) as (owner, admin, bundle, _, _):
        install(owner, bundle)
        assert all(checks(owner, bundle / "03-postflight.sql").values())
        with psycopg.connect(admin) as conn:
            conn.execute(damage)
        result = checks(owner, bundle / "03-postflight.sql")
        assert not result[failed_check]
        assert result["inventory"]  # Unchanged scores alone cannot certify installation.
