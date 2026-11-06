"""Generated deployment SQL on an owned server, never an application DSN."""

import json
import os
from contextlib import contextmanager

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo, conninfo_to_dict
import pytest

from tests.postgres_harness import isolated_postgres
from tests.integration.test_automatic_promotion_postgres import prepare
from tests.integration.test_human_installation_postgres import checks, install

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_AUTOMATIC_INSTALLATION_INTEGRATION") != "1",
    reason="Owned OrioleDB opt-in only",
)


@pytest.fixture(scope="module")
def cluster():
    assert os.environ.get("HUMAN_PG_ENGINE") == "orioledb"
    with isolated_postgres() as server:
        with psycopg.connect(server.dsn, autocommit=True) as conn:
            conn.execute("CREATE ROLE postgres LOGIN CREATEROLE BYPASSRLS PASSWORD 'isolated_only'")
            for name in ("anon", "authenticated", "service_role", "authenticator"):
                conn.execute(sql.SQL("CREATE ROLE {}").format(sql.Identifier(name)))
        yield server


@contextmanager
def scenario(cluster, root, full=False):
    from classificator.automatic_installation import (
        prepare_automatic_installation,
        automatic_installation_capture_sql,
    )

    approval, package, store, admin, epoch = prepare(cluster, root, full=full)
    owner = make_conninfo(admin, user="postgres", password="isolated_only")
    try:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute("DROP TABLE classificator_private.automatic_promotion_receipts")
            conn.execute("ALTER SCHEMA classificator_private OWNER TO postgres")
            for table in (
                "public.words",
                "classificator_private.human_correction_receipts",
                "classificator_private.words_revision_contract",
            ):
                conn.execute(
                    sql.SQL("ALTER TABLE {} OWNER TO postgres").format(
                        sql.Identifier(*table.split("."))
                    )
                )
            conn.execute(
                "ALTER SEQUENCE classificator_private.words_revision_seq OWNER TO postgres"
            )
            conn.execute(
                "ALTER FUNCTION classificator_private.assign_word_revision() OWNER TO postgres"
            )
            conn.execute("ALTER TABLE public.words ENABLE ROW LEVEL SECURITY")
            conn.execute("CREATE POLICY public_read ON public.words FOR SELECT USING(true)")
            conn.execute("SET ROLE postgres")
            conn.execute("CREATE ROLE classificator_human_executor NOLOGIN BYPASSRLS NOINHERIT")
            conn.execute(
                "GRANT USAGE ON SCHEMA classificator_private TO classificator_human_executor"
            )
            conn.execute("GRANT SELECT,UPDATE ON public.words TO classificator_human_executor")
            conn.execute(
                "GRANT SELECT,INSERT,UPDATE ON classificator_private.human_correction_receipts TO classificator_human_executor"
            )
            conn.execute(
                "GRANT SELECT ON classificator_private.words_revision_contract TO classificator_human_executor"
            )
            conn.execute("RESET ROLE")
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute("""CREATE FUNCTION public.installation_fault() RETURNS event_trigger
                LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
                DECLARE cmd record;
                BEGIN
                  FOR cmd IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
                    IF cmd.command_tag='CREATE TABLE' AND cmd.object_identity='classificator_private.automatic_installation_receipt' THEN
                      CASE current_setting('rehearsal.fault',true)
                        WHEN 'reject' THEN RAISE EXCEPTION 'injected DDL failure';
                        WHEN 'mutate' THEN UPDATE public.words SET untouched='unexpected';
                        WHEN 'grant' THEN GRANT INSERT ON public.words TO PUBLIC;
                        WHEN 'disconnect' THEN PERFORM pg_terminate_backend(pg_backend_pid());
                        WHEN 'human_receipt' THEN UPDATE classificator_private.installation_receipt SET receipt='{"damaged":true}';
                        WHEN 'sequence' THEN PERFORM setval('classificator_private.words_revision_seq',1,false);
                        ELSE NULL;
                      END CASE;
                    END IF;
                  END LOOP;
                END $$""")
            conn.execute(
                "CREATE EVENT TRIGGER installation_fault ON ddl_command_end EXECUTE FUNCTION public.installation_fault()"
            )
        with psycopg.connect(owner, autocommit=True) as conn:
            conn.execute(
                "CREATE TABLE classificator_private.installation_receipt (singleton boolean PRIMARY KEY CHECK(singleton), receipt jsonb NOT NULL) USING heap"
            )
            conn.execute("REVOKE ALL ON classificator_private.installation_receipt FROM PUBLIC")
            conn.execute(
                "INSERT INTO classificator_private.installation_receipt VALUES(true,'{\"preserve\":true}')"
            )
        capture = root / "capture.json"
        with psycopg.connect(owner, autocommit=True) as conn:
            cur = conn.execute(automatic_installation_capture_sql())
            while cur.description is None:
                assert cur.nextset()
            capture.write_text(json.dumps(cur.fetchone()[0]))
        bundle = root / "installation"
        prepare_automatic_installation(approval, package, capture, bundle)
        yield owner, admin, bundle, approval, package, epoch
    finally:
        with psycopg.connect(cluster.dsn, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(conninfo_to_dict(admin)["dbname"])
                )
            )
            conn.execute("DROP ROLE IF EXISTS classificator_automatic_executor")
            conn.execute("DROP ROLE IF EXISTS classificator_human_executor")


def test_installs_disabled_executor_preserving_existing_data_and_human_flow(cluster, tmp_path):
    with scenario(cluster, tmp_path) as (owner, admin, bundle, *_):
        assert all(checks(owner, bundle / "01-preflight.sql").values())
        install(owner, bundle)
        after = checks(owner, bundle / "03-postflight.sql")
        assert all(after.values()), after
        with psycopg.connect(admin) as conn:
            assert conn.execute(
                "SELECT rolcanlogin FROM pg_roles WHERE rolname='classificator_automatic_executor'"
            ).fetchone() == (False,)
            assert conn.execute(
                "SELECT has_table_privilege('classificator_automatic_executor','classificator_private.human_correction_receipts','UPDATE')"
            ).fetchone() == (False,)
        cluster.restart()
        assert checks(owner, bundle / "03-postflight.sql") == after
        with pytest.raises(psycopg.Error):
            install(owner, bundle)
        assert checks(owner, bundle / "03-postflight.sql") == after


@pytest.mark.parametrize(
    "fault", ["reject", "mutate", "grant", "disconnect", "sequence", "human_receipt"]
)
def test_install_failure_is_detected_and_recovery_preserves_human_state(cluster, tmp_path, fault):
    with scenario(cluster, tmp_path) as (owner, admin, bundle, *_):
        with pytest.raises(psycopg.Error):
            install(owner, bundle, fault)
        if fault == "sequence":
            # nextval/setval are not transactional. Recovery is explicit, fixture-only.
            with psycopg.connect(admin, autocommit=True) as conn:
                conn.execute(
                    "SELECT setval('classificator_private.words_revision_seq',(SELECT max(classificator_revision) FROM public.words))"
                )
        before = checks(owner, bundle / "01-preflight.sql")
        assert all(before.values()), before
        install(owner, bundle)
        assert all(checks(owner, bundle / "03-postflight.sql").values())


def test_existing_installation_receipt_drift_blocks_deployment(cluster, tmp_path):
    with scenario(cluster, tmp_path) as (owner, admin, bundle, *_):
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(
                "UPDATE classificator_private.installation_receipt SET receipt='{\"changed\":true}'"
            )
        before = checks(owner, bundle / "01-preflight.sql")
        assert before["human_installation_receipt"] is False
        with pytest.raises(psycopg.Error, match="human_installation_receipt"):
            install(owner, bundle)


@pytest.mark.parametrize(
    "locked_table", ["public.words", "classificator_private.installation_receipt"]
)
def test_lock_timeout_leaves_package_retryable(cluster, tmp_path, locked_table):
    with scenario(cluster, tmp_path) as (owner, admin, bundle, *_):
        with psycopg.connect(admin) as blocker:
            blocker.execute(
                sql.SQL("LOCK TABLE {} IN ROW EXCLUSIVE MODE").format(
                    sql.Identifier(*locked_table.split("."))
                )
            )
            with pytest.raises(psycopg.errors.LockNotAvailable):
                install(owner, bundle)
        assert all(checks(owner, bundle / "01-preflight.sql").values())
        install(owner, bundle)
        assert all(checks(owner, bundle / "03-postflight.sql").values())


def test_uncertain_commit_recovers_by_receipt_without_reinstall(cluster, tmp_path):
    with scenario(cluster, tmp_path) as (owner, admin, bundle, *_):

        def lost_ack():
            install(owner, bundle)
            raise ConnectionError("injected acknowledgement loss after actual commit")

        with pytest.raises(ConnectionError):
            lost_ack()
        after = checks(owner, bundle / "03-postflight.sql")
        assert all(after.values())
        with pytest.raises(psycopg.Error, match="automatic_ledger_absent"):
            install(owner, bundle)
        assert checks(owner, bundle / "03-postflight.sql") == after


@pytest.mark.parametrize(
    ("damage", "check_name"),
    [
        (
            "GRANT DELETE ON public.words TO classificator_automatic_executor",
            "executor_words",
        ),
        ("ALTER ROLE classificator_automatic_executor LOGIN", "executor_disabled"),
        ("GRANT USAGE ON SCHEMA classificator_private TO anon", "api_roles_denied"),
        (
            "UPDATE public.words SET untouched='external change'",
            "installation_receipt_bound",
        ),
        (
            "GRANT classificator_human_executor TO classificator_automatic_executor",
            "executor_memberships",
        ),
    ],
)
def test_postflight_rejects_privilege_activation_and_data_drift(
    cluster, tmp_path, damage, check_name
):
    with scenario(cluster, tmp_path) as (owner, admin, bundle, *_):
        install(owner, bundle)
        with psycopg.connect(admin) as conn:
            conn.execute(damage)
        assert checks(owner, bundle / "03-postflight.sql")[check_name] is False


@pytest.mark.parametrize(
    "damage",
    [
        "UPDATE public.words SET rarity_level=rarity_level WHERE id=103",
        "ALTER TABLE public.words DISABLE TRIGGER classificator_word_revision",
        "GRANT USAGE ON SCHEMA classificator_private TO anon",
    ],
)
def test_preinstall_drift_refused_before_new_objects(cluster, tmp_path, damage):
    with scenario(cluster, tmp_path) as (owner, admin, bundle, *_):
        with psycopg.connect(admin) as conn:
            conn.execute(damage)
        assert not all(checks(owner, bundle / "01-preflight.sql").values())
        with pytest.raises(psycopg.Error):
            install(owner, bundle)
        before = checks(owner, bundle / "01-preflight.sql")
        assert before["automatic_ledger_absent"] and before["automatic_role_absent"]


@pytest.mark.skipif(
    os.environ.get("RUN_AUTOMATIC_INSTALLATION_FULL") != "1",
    reason="Pinned local production package required",
)
def test_exact_bundle_with_nine_hooks_full_inventory_and_executor_roundtrip(cluster, tmp_path):
    from pathlib import Path
    from classificator.automatic_installation import verify_automatic_installation
    from classificator.automatic_promotion_flow import run_automatic_promotion
    from classificator.automatic_promotion_postgres import PostgresAutomaticStore
    from tests.integration.test_human_installation_postgres import prepared
    from tests.postgres_harness import ROOT
    from tests.test_promotion_audit import rows, digest

    base = ROOT.parent / "automatic-installation-2026-11-07"
    bundle = base / "verified"
    assert verify_automatic_installation(bundle)["valid"]
    captured = json.loads((base / "capture.json").read_text())["state"]
    source = ROOT.parent / "human-production-apply-2026-11-04/after/snapshot.csv"
    expected = rows(source)
    epoch = captured["epoch"][0]
    try:
        with prepared(cluster, tmp_path, full=True, captured_hooks=True) as (
            owner,
            admin,
            human_bundle,
            *_,
        ):
            install(owner, human_bundle)
            # Reconstruct the archived post-human state in this owned fixture only.
            with psycopg.connect(admin, autocommit=True) as conn:
                conn.execute("ALTER ROLE classificator_human_executor LOGIN")
                conn.execute("ALTER TABLE public.words DISABLE TRIGGER classificator_word_revision")
                conn.execute(
                    "CREATE TEMP TABLE restore_rows (id bigint,level integer,revision bigint) USING heap"
                )
                with conn.cursor().copy("COPY restore_rows FROM STDIN") as cp:
                    for r in expected:
                        cp.write_row((r["word_id"], r["rarity_level"], r["version"]))
                conn.execute(
                    "UPDATE public.words w SET rarity_level=r.level,classificator_revision=r.revision FROM restore_rows r WHERE w.id=r.id"
                )
                conn.execute(
                    "ALTER TABLE public.words ENABLE ALWAYS TRIGGER classificator_word_revision"
                )
                conn.execute(
                    "SELECT setval('classificator_private.words_revision_seq',(SELECT max(classificator_revision) FROM public.words))"
                )
                conn.execute(
                    "UPDATE classificator_private.words_revision_contract SET epoch=%s",
                    (epoch,),
                )
                conn.execute(
                    "UPDATE classificator_private.installation_receipt SET receipt=%s::jsonb",
                    (json.dumps(captured["human_installation_receipt"][0]["receipt"]),),
                )
                for r in captured["human_receipts"]:
                    conn.execute(
                        "INSERT INTO classificator_private.human_correction_receipts VALUES(%s,%s::jsonb)",
                        (r["package_id"], json.dumps(r["receipt"])),
                    )
            before = checks(owner, bundle / "01-preflight.sql")
            assert all(before.values()), before
            install(owner, bundle)
            after = checks(owner, bundle / "03-postflight.sql")
            assert all(after.values()), after
            (tmp_path / "exact-prechecks.json").write_text(json.dumps(before, indent=2))
            (tmp_path / "exact-postchecks.json").write_text(json.dumps(after, indent=2))
            cluster.restart()
            assert checks(owner, bundle / "03-postflight.sql") == after
            with psycopg.connect(admin, autocommit=True) as conn:
                conn.execute(
                    "ALTER ROLE classificator_automatic_executor LOGIN PASSWORD 'isolated_only'"
                )
            executor = make_conninfo(
                admin, user="classificator_automatic_executor", password="isolated_only"
            )
            store = PostgresAutomaticStore(executor)
            acceptance = ROOT / "docs/research/2026-11-06-automatic-flow/acceptance.json"
            package = ROOT.parent / "automatic-promotion-audit-2026-11-06/final"
            with store.transaction() as tx:
                initial = tx.snapshot()
            results = {}
            for action, name in [
                ("apply", "apply"),
                ("apply", "retry"),
                ("rollback", "rollback"),
            ]:
                results[name] = run_automatic_promotion(
                    acceptance,
                    package,
                    tmp_path / name,
                    action=action,
                    store=store,
                    confirm_package=digest(package / "manifest.json"),
                    expected_epoch=epoch,
                )
            assert results["apply"]["status"] == "applied"
            assert results["retry"]["status"] == "already_applied"
            assert results["rollback"]["status"] == "rolled_back"
            assert sum(results["apply"]["route_changes"].values()) == 50724
            with store.transaction() as tx:
                final = tx.snapshot()
            assert [{k: v for k, v in r.items() if k != "version"} for r in final] == [
                {k: v for k, v in r.items() if k != "version"} for r in initial
            ]
            with psycopg.connect(owner) as conn:
                receipts = conn.execute(
                    "SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY package_id),'[]'::jsonb) FROM classificator_private.human_correction_receipts r"
                ).fetchone()[0]
            assert receipts == captured["human_receipts"]
            (tmp_path / "full-result.json").write_text(
                json.dumps(
                    dict(
                        rows=len(initial),
                        changed=50724,
                        human_rows=233,
                        rollback_restored=True,
                        human_receipt_preserved=True,
                    ),
                    indent=2,
                )
            )
    finally:
        with psycopg.connect(cluster.dsn, autocommit=True) as conn:
            conn.execute("DROP ROLE IF EXISTS classificator_automatic_executor")
