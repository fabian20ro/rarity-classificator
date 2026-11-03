"""Opt-in real PostgreSQL tests; the harness creates its own disposable server."""

import json
import os
from pathlib import Path

import pytest

from classificator.human_correction_flow import run_human_corrections
from classificator.human_correction_postgres import PostgresHumanStore
from tests import test_human_correction_flow as fixtures

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_HUMAN_POSTGRES_INTEGRATION") != "1",
    reason="Opt in to a disposable Docker PostgreSQL with RUN_HUMAN_POSTGRES_INTEGRATION=1",
)


@pytest.fixture(scope="module")
def cluster():
    from tests.postgres_harness import isolated_postgres

    with isolated_postgres() as server:
        yield server


@pytest.fixture
def scenario(cluster, tmp_path):
    approval, policy, package, memory = fixtures.HumanFlowTests().inputs(tmp_path)
    dsn = cluster.database()
    cluster.seed(dsn, list(memory.rows.values()))
    return approval, policy, package, PostgresHumanStore(dsn), dsn


def run(scenario, out, action):
    approval, policy, package, store, _ = scenario
    return run_human_corrections(
        approval, policy, out, action=action, store=store, confirm_package=package
    )


def snapshot(store):
    with store.transaction() as tx:
        return {r["word_id"]: r for r in tx.snapshot()}


def test_real_schema_apply_retry_restart_and_rollback(cluster, scenario, tmp_path):
    store = scenario[3]
    before = snapshot(store)
    assert run(scenario, tmp_path / "apply", "apply")["status"] == "applied"
    after = snapshot(store)
    assert {i for i in before if before[i] != after[i]} == {"100"}
    assert after["100"]["rarity_level"] == "5"
    assert before["100"]["version"] != after["100"]["version"]
    with store.transaction() as tx:
        receipt = tx.receipt(scenario[2])
    assert receipt["changed_ids"] == ["100"]
    assert receipt["post_versions"]["100"] == after["100"]["version"]
    cluster.restart()
    assert run(scenario, tmp_path / "retry", "apply")["status"] == "already_applied"
    assert snapshot(store) == after
    assert run(scenario, tmp_path / "rollback", "rollback")["status"] == "rolled_back"
    restored = snapshot(store)
    assert {i: {k: v for k, v in row.items() if k != "version"} for i, row in restored.items()} == {
        i: {k: v for k, v in row.items() if k != "version"} for i, row in before.items()
    }
    assert run(scenario, tmp_path / "retry-rollback", "rollback")["status"] == "already_rolled_back"
    assert snapshot(store) == restored
    with store.transaction() as tx:
        assert tx.receipt(scenario[2])["state"] == "rolled_back"
    assert json.loads((tmp_path / "apply/receipt.json").read_text()) == receipt


@pytest.mark.parametrize(
    "fault",
    [
        "word_side_effect",
        "deferred_failure",
        "receipt_failure",
        "receipt_side_effect",
        "receipt_rewrite",
    ],
)
def test_real_trigger_failures_roll_back_words_and_receipt(scenario, tmp_path, fault):
    import psycopg

    store = scenario[3]
    before = snapshot(store)
    with psycopg.connect(scenario[4], autocommit=True) as conn:
        if fault == "receipt_rewrite":
            conn.execute("""CREATE FUNCTION rewrite_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN NEW.receipt = jsonb_set(NEW.receipt, '{state}', '"rolled_back"'); RETURN NEW; END $$""")
            conn.execute(
                "CREATE TRIGGER rewrite_receipt BEFORE INSERT ON classificator_private.human_correction_receipts FOR EACH ROW EXECUTE FUNCTION rewrite_receipt()"
            )
        elif fault in {"word_side_effect", "receipt_side_effect"}:
            conn.execute("""CREATE FUNCTION side_effect() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN UPDATE public.words SET rarity_level=2 WHERE id=104; RETURN NEW; END $$""")
            if fault == "word_side_effect":
                conn.execute(
                    "CREATE TRIGGER side_effect AFTER UPDATE ON public.words FOR EACH ROW WHEN (NEW.id=100) EXECUTE FUNCTION side_effect()"
                )
            else:
                conn.execute(
                    "CREATE TRIGGER side_effect AFTER INSERT ON classificator_private.human_correction_receipts FOR EACH ROW EXECUTE FUNCTION side_effect()"
                )
        else:
            conn.execute("""CREATE FUNCTION reject_test() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'injected integration failure'; END $$""")
            if fault == "deferred_failure":
                conn.execute(
                    "CREATE CONSTRAINT TRIGGER reject_test AFTER UPDATE ON public.words DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_test()"
                )
            else:
                conn.execute(
                    "CREATE TRIGGER reject_test BEFORE INSERT ON classificator_private.human_correction_receipts FOR EACH ROW EXECUTE FUNCTION reject_test()"
                )
    with pytest.raises((ValueError, psycopg.Error)):
        run(scenario, tmp_path / "failed", "apply")
    assert snapshot(store) == before
    with store.transaction() as tx:
        assert tx.receipt(scenario[2]) is None
    assert not (tmp_path / "failed/receipt.json").exists()


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO public.words VALUES (105,'ata','A',5)",
        "UPDATE public.words SET rarity_level=2 WHERE id=101",
    ],
)
def test_concurrent_writer_waits_and_later_drift_is_rejected(scenario, tmp_path, statement):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import time
    import psycopg

    ready = Event()
    worker_pid = []

    def writer():
        with psycopg.connect(scenario[4]) as conn:
            conn.execute("SET statement_timeout = '10s'")
            worker_pid.append(conn.info.backend_pid)
            ready.set()
            conn.execute(statement)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with scenario[3].transaction() as tx:
            original = tx.snapshot()
            future = pool.submit(writer)
            assert ready.wait(3)
            deadline = time.monotonic() + 3
            with psycopg.connect(scenario[4], autocommit=True) as observer:
                while not observer.execute(
                    "SELECT pg_blocking_pids(%s)", (worker_pid[0],)
                ).fetchone()[0]:
                    assert time.monotonic() < deadline, "Expected writer to block on table lock"
                    time.sleep(0.01)
            assert not future.done()
            assert tx.snapshot() == original
        future.result(timeout=5)
    current = snapshot(scenario[3])
    with pytest.raises(ValueError, match="preconditions"):
        run(scenario, tmp_path / "stale", "apply")
    assert snapshot(scenario[3]) == current
    with scenario[3].transaction() as tx:
        assert tx.receipt(scenario[2]) is None


def test_concurrent_same_package_applies_once(scenario, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(2)

    def apply(index):
        barrier.wait(timeout=5)
        return run(scenario, tmp_path / str(index), "apply")["status"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(apply, i) for i in range(2)]
        assert sorted(f.result(timeout=15) for f in futures) == ["already_applied", "applied"]
    with scenario[3].transaction() as tx:
        receipt = tx.receipt(scenario[2])
        rows = {r["word_id"]: r for r in tx.snapshot()}
        assert receipt["changed_ids"] == ["100"]
        assert receipt["post_versions"]["100"] == rows["100"]["version"]


def test_real_same_score_write_blocks_rollback_by_xmin(scenario, tmp_path):
    import psycopg

    run(scenario, tmp_path / "apply", "apply")
    with psycopg.connect(scenario[4]) as conn:
        conn.execute("UPDATE public.words SET rarity_level=4 WHERE id=100")
        conn.execute("UPDATE public.words SET rarity_level=5 WHERE id=100")
    before = snapshot(scenario[3])
    with pytest.raises(ValueError, match="Concurrent row change"):
        run(scenario, tmp_path / "aba", "rollback")
    assert snapshot(scenario[3]) == before
    with scenario[3].transaction() as tx:
        assert tx.receipt(scenario[2])["state"] == "applied"


def test_receipt_trigger_side_effect_on_rollback_is_atomic(scenario, tmp_path):
    import psycopg

    run(scenario, tmp_path / "apply", "apply")
    before = snapshot(scenario[3])
    with psycopg.connect(scenario[4]) as conn:
        conn.execute("""CREATE FUNCTION bad_rollback_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN UPDATE public.words SET rarity_level=2 WHERE id=104; RETURN NEW; END $$""")
        conn.execute(
            "CREATE TRIGGER bad_rollback_receipt AFTER UPDATE ON classificator_private.human_correction_receipts FOR EACH ROW EXECUTE FUNCTION bad_rollback_receipt()"
        )
    with pytest.raises(ValueError, match="Receipt write changed"):
        run(scenario, tmp_path / "failed-rollback", "rollback")
    assert snapshot(scenario[3]) == before
    with scenario[3].transaction() as tx:
        assert tx.receipt(scenario[2])["state"] == "applied"


@pytest.mark.parametrize("access", ["rls_filtered", "ledger_denied", "bypassrls_executor"])
def test_real_role_and_rls_boundaries(scenario, tmp_path, access):
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from uuid import uuid4

    role = "human_role_" + uuid4().hex[:10]
    before = snapshot(scenario[3])
    with psycopg.connect(scenario[4], autocommit=True) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD 'isolated_test_only'").format(
                sql.Identifier(role)
            )
        )
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        conn.execute(
            sql.SQL("GRANT SELECT, UPDATE ON public.words TO {}").format(sql.Identifier(role))
        )
        if access != "ledger_denied":
            conn.execute(
                sql.SQL("GRANT USAGE ON SCHEMA classificator_private TO {}").format(
                    sql.Identifier(role)
                )
            )
            conn.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE ON classificator_private.human_correction_receipts TO {}"
                ).format(sql.Identifier(role))
            )
        conn.execute("ALTER TABLE public.words ENABLE ROW LEVEL SECURITY")
        conn.execute("ALTER TABLE public.words FORCE ROW LEVEL SECURITY")
        conn.execute("CREATE POLICY partial_visibility ON public.words USING (id<>104)")
        if access == "bypassrls_executor":
            conn.execute(sql.SQL("ALTER ROLE {} BYPASSRLS").format(sql.Identifier(role)))
    dsn = make_conninfo(scenario[4], user=role, password="isolated_test_only")
    restricted = (*scenario[:3], PostgresHumanStore(dsn), dsn)
    if access == "bypassrls_executor":
        assert run(restricted, tmp_path / "role-apply", "apply")["status"] == "applied"
        assert snapshot(scenario[3])["104"] == before["104"]
    else:
        with pytest.raises(psycopg.errors.InsufficientPrivilege) as error:
            run(restricted, tmp_path / "denied", "apply")
        if access == "rls_filtered":
            assert "row-level security policy" in str(error.value)
        assert snapshot(scenario[3]) == before
        with scenario[3].transaction() as tx:
            assert tx.receipt(scenario[2]) is None


def test_backend_disconnect_before_commit_rolls_back_and_can_retry(scenario, tmp_path):
    import psycopg

    before = snapshot(scenario[3])
    with psycopg.connect(scenario[4]) as conn:
        conn.execute("""CREATE FUNCTION disconnect_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN PERFORM pg_terminate_backend(pg_backend_pid()); RETURN NEW; END $$""")
        conn.execute(
            "CREATE TRIGGER disconnect_receipt BEFORE INSERT ON classificator_private.human_correction_receipts FOR EACH ROW EXECUTE FUNCTION disconnect_receipt()"
        )
    with pytest.raises(psycopg.Error):
        run(scenario, tmp_path / "disconnected", "apply")
    assert snapshot(scenario[3]) == before
    with scenario[3].transaction() as tx:
        assert tx.receipt(scenario[2]) is None
    assert not (tmp_path / "disconnected/receipt.json").exists()
    with psycopg.connect(scenario[4]) as conn:
        conn.execute(
            "DROP TRIGGER disconnect_receipt ON classificator_private.human_correction_receipts"
        )
    assert run(scenario, tmp_path / "retry-disconnected", "apply")["status"] == "applied"


def test_lost_ack_after_real_commit_recovers_without_reapplying(scenario, tmp_path):
    from contextlib import contextmanager

    class LostAcknowledgement:
        @contextmanager
        def transaction(self):
            with scenario[3].transaction() as tx:
                yield tx
            # Real COMMIT has completed; inject only the missing acknowledgement at the boundary.
            raise ConnectionError("Injected lost commit acknowledgement")

    faulty = (*scenario[:3], LostAcknowledgement(), scenario[4])
    with pytest.raises(ConnectionError):
        run(faulty, tmp_path / "lost-ack", "apply")
    after = snapshot(scenario[3])
    assert after["100"]["rarity_level"] == "5"
    assert not (tmp_path / "lost-ack/receipt.json").exists()
    assert run(scenario, tmp_path / "recover", "apply")["status"] == "already_applied"
    assert snapshot(scenario[3]) == after


@pytest.mark.skipif(
    os.environ.get("RUN_HUMAN_POSTGRES_FULL_INVENTORY") != "1",
    reason="Full inventory needs existing local frozen artifacts",
)
def test_full_165_package_on_disposable_database(cluster, tmp_path):
    from tests.test_local_evidence import read
    from tests.postgres_harness import ROOT

    policy = ROOT / "docs/research/2026-11-03-human-acceptance/policy.json"
    approval = ROOT / "docs/research/2026-11-03-human-flow/approval.json"
    config = json.loads(policy.read_text())
    package = json.loads(approval.read_text())["package_id"]
    original = read(Path(config["sources"]["snapshot"]["path"]))
    candidate = {r["word_id"]: r for r in read(Path(config["sources"]["candidate"]["path"]))}
    dsn = cluster.database()
    cluster.seed(dsn, original)
    store = PostgresHumanStore(dsn)
    scenario = approval, policy, package, store, dsn
    before = snapshot(store)
    assert len(before) == 77698
    assert run(scenario, tmp_path / "apply165", "apply")["status"] == "applied"
    after = snapshot(store)
    assert {
        i: {k: v for k, v in row.items() if k != "version"} for i, row in after.items()
    } == candidate
    assert len({i for i in before if before[i] != after[i]}) == 165
    with store.transaction() as tx:
        receipt = tx.receipt(package)
        assert len(receipt["changed_ids"]) == 165
    assert run(scenario, tmp_path / "retry165", "apply")["status"] == "already_applied"
    assert snapshot(store) == after
    assert run(scenario, tmp_path / "rollback165", "rollback")["status"] == "rolled_back"
    restored = snapshot(store)
    assert {i: {k: v for k, v in row.items() if k != "version"} for i, row in restored.items()} == {
        r["word_id"]: r for r in original
    }
    assert {i for i in before if before[i] != restored[i]} == set(receipt["changed_ids"])
