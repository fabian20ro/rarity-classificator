"""Automatic flow on owned disposable OrioleDB only. No application DSN accepted."""

import json
import os
from pathlib import Path

import pytest

from classificator.automatic_promotion_flow import run_automatic_promotion
from classificator.automatic_promotion_postgres import PostgresAutomaticStore
from classificator.evaluation.promotion_audit import prepare_promotion_audit
from tests import test_promotion_audit as fixtures
from tests.test_exact_form import write_csv

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_AUTOMATIC_PROMOTION_INTEGRATION") != "1",
    reason="Explicit opt-in to owned OrioleDB required",
)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def cluster():
    from tests.postgres_harness import isolated_postgres

    assert os.environ.get("HUMAN_PG_ENGINE") == "orioledb"
    with isolated_postgres() as server:
        yield server


def prepare(cluster, root, full=False):
    import psycopg

    if full:
        original = ROOT / "docs/research/2026-11-06-promotion-package/contract.json"
        contract = json.loads(original.read_text())
        for item in contract["inputs"].values():
            item["path"] = str((original.parent / item["path"]).resolve())
        source = Path(contract["inputs"]["snapshot"]["path"])
    else:
        config = fixtures.PromotionAuditTests().fixture(root)
        contract = json.loads(config.read_text())
        for item in contract["inputs"].values():
            item["path"] = str((root / item["path"]).resolve())
        source = root / "snapshot.csv"
    dsn = cluster.database()
    cluster.seed(dsn, fixtures.rows(source))
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "ALTER TABLE public.words ADD COLUMN untouched text NOT NULL DEFAULT 'original'"
        )
        conn.execute(
            (ROOT / "docs/sql/2026-11-06-automatic-promotion-receipts.sql").read_text()
        )
        epoch = conn.execute(
            "SELECT epoch::text FROM classificator_private.words_revision_contract"
        ).fetchone()[0]
    store = PostgresAutomaticStore(dsn)
    with store.transaction() as tx:
        snapshot = [
            {k: v for k, v in r.items() if k != "other_columns_sha256"}
            for r in tx.snapshot()
        ]
    local_snapshot = root / "isolated-snapshot.csv"
    write_csv(local_snapshot, snapshot)
    contract["inputs"]["snapshot"] = dict(
        path=str(local_snapshot), sha256=fixtures.digest(local_snapshot)
    )
    config = root / "isolated-contract.json"
    config.write_text(json.dumps(contract))
    package = root / "isolated-package"
    prepare_promotion_audit(config, package)
    approval = root / "isolated-acceptance.json"
    approval.write_text(
        json.dumps(
            dict(
                version="automatic-provisional-acceptance-v1",
                approved_on="2026-11-06",
                package_id=fixtures.digest(package / "manifest.json"),
                candidate_sha256=fixtures.digest(package / "candidate.csv"),
                routes=["wordfreq", "fallback"],
                legacy_gate_role="diagnostic",
                population_accuracy="unknown",
                human_priority=True,
            )
        )
    )
    return approval, package, store, dsn, epoch


@pytest.fixture
def scenario(cluster, tmp_path):
    return prepare(cluster, tmp_path)


def run(scenario, out, action):
    approval, package, store, _, epoch = scenario
    return run_automatic_promotion(
        approval,
        package,
        out,
        action=action,
        store=store,
        confirm_package=fixtures.digest(package / "manifest.json"),
        expected_epoch=epoch,
    )


def snapshot(store):
    with store.transaction() as tx:
        return {r["word_id"]: r for r in tx.snapshot()}


def test_apply_restart_retry_and_rollback_keep_human_ledger_untouched(
    cluster, scenario, tmp_path
):
    import psycopg

    before = snapshot(scenario[2])
    assert run(scenario, tmp_path / "apply", "apply")["status"] == "applied"
    after = snapshot(scenario[2])
    assert {i for i in before if before[i] != after[i]} == {"103", "104"}
    assert after["103"]["rarity_level"] == "1" and after["104"]["rarity_level"] == "4"
    cluster.restart()
    assert run(scenario, tmp_path / "retry", "apply")["status"] == "already_applied"
    assert snapshot(scenario[2]) == after
    assert run(scenario, tmp_path / "rollback", "rollback")["status"] == "rolled_back"
    restored = snapshot(scenario[2])
    assert {
        i: {k: v for k, v in r.items() if k != "version"} for i, r in restored.items()
    } == {i: {k: v for k, v in r.items() if k != "version"} for i, r in before.items()}
    assert (
        run(scenario, tmp_path / "retry-rollback", "rollback")["status"]
        == "already_rolled_back"
    )
    with psycopg.connect(scenario[3]) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM classificator_private.human_correction_receipts"
            ).fetchone()[0]
            == 0
        )


@pytest.mark.parametrize(
    "fault",
    [
        "human_side_effect",
        "non_score",
        "deferred",
        "receipt_failure",
        "receipt_rewrite",
        "epoch",
    ],
)
def test_real_trigger_faults_abort_every_route_and_receipt(scenario, tmp_path, fault):
    import psycopg

    before = snapshot(scenario[2])
    with psycopg.connect(scenario[3], autocommit=True) as conn:
        body = {
            "human_side_effect": "UPDATE public.words SET rarity_level=1 WHERE id=101; RETURN NEW;",
            "non_score": "UPDATE public.words SET untouched='corrupt' WHERE id=103; RETURN NEW;",
            "deferred": "RAISE EXCEPTION 'injected deferred failure';",
            "receipt_failure": "RAISE EXCEPTION 'injected receipt failure';",
            "receipt_rewrite": "NEW.receipt=jsonb_set(NEW.receipt,'{state}','\"rolled_back\"'); RETURN NEW;",
            "epoch": "UPDATE classificator_private.words_revision_contract SET epoch=gen_random_uuid(); RETURN NEW;",
        }[fault]
        conn.execute(
            "CREATE FUNCTION injected_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            + body
            + " END $$"
        )
        if fault == "non_score":
            conn.execute(
                "CREATE TRIGGER injected_fault AFTER UPDATE ON words FOR EACH ROW WHEN (NEW.id=103 AND NEW.untouched='original') EXECUTE FUNCTION injected_fault()"
            )
        elif fault == "deferred":
            conn.execute(
                "CREATE CONSTRAINT TRIGGER injected_fault AFTER UPDATE ON words DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.id=104) EXECUTE FUNCTION injected_fault()"
            )
        else:
            timing = "BEFORE" if fault == "receipt_rewrite" else "AFTER"
            conn.execute(
                f"CREATE TRIGGER injected_fault {timing} INSERT ON classificator_private.automatic_promotion_receipts FOR EACH ROW EXECUTE FUNCTION injected_fault()"
            )
    with pytest.raises((ValueError, psycopg.Error)):
        run(scenario, tmp_path / "failed", "apply")
    assert snapshot(scenario[2]) == before
    with scenario[2].transaction() as tx:
        assert tx.receipt(fixtures.digest(scenario[1] / "manifest.json")) is None
    assert not (tmp_path / "failed/receipt.json").exists()


def test_commit_ack_loss_is_recovered_for_apply_and_rollback(scenario, tmp_path):
    from contextlib import contextmanager

    class LostAck:
        @contextmanager
        def transaction(self):
            with scenario[2].transaction() as tx:
                yield tx
            raise RuntimeError("Injected post-commit acknowledgement loss")

    uncertain = (scenario[0], scenario[1], LostAck(), scenario[3], scenario[4])
    for action, status in (
        ("apply", "already_applied"),
        ("rollback", "already_rolled_back"),
    ):
        with pytest.raises(RuntimeError, match="acknowledgement"):
            run(uncertain, tmp_path / f"lost-{action}", action)
        after = snapshot(scenario[2])
        assert not (tmp_path / f"lost-{action}" / "receipt.json").exists()
        assert run(scenario, tmp_path / f"retry-{action}", action)["status"] == status
        assert snapshot(scenario[2]) == after


def test_backend_termination_rolls_back_and_retry_recovers(scenario, tmp_path):
    import psycopg

    before = snapshot(scenario[2])
    with psycopg.connect(scenario[3], autocommit=True) as conn:
        conn.execute(
            "CREATE FUNCTION terminate_test() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_terminate_backend(pg_backend_pid()); RETURN NEW; END $$"
        )
        conn.execute(
            "CREATE TRIGGER terminate_test BEFORE INSERT ON classificator_private.automatic_promotion_receipts FOR EACH ROW EXECUTE FUNCTION terminate_test()"
        )
    with pytest.raises(psycopg.Error):
        run(scenario, tmp_path / "interrupted", "apply")
    assert snapshot(scenario[2]) == before
    assert not (tmp_path / "interrupted/receipt.json").exists()
    with psycopg.connect(scenario[3], autocommit=True) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM classificator_private.automatic_promotion_receipts"
            ).fetchone()[0]
            == 0
        )
        conn.execute(
            "DROP TRIGGER terminate_test ON classificator_private.automatic_promotion_receipts"
        )
    assert run(scenario, tmp_path / "retry", "apply")["status"] == "applied"


@pytest.mark.parametrize("phase", ["apply", "rollback"])
def test_same_score_external_write_rejects_stale_revision(scenario, tmp_path, phase):
    import psycopg

    if phase == "rollback":
        run(scenario, tmp_path / "apply", "apply")
    with psycopg.connect(scenario[3]) as conn:
        conn.execute("UPDATE public.words SET rarity_level=rarity_level WHERE id=103")
    before = snapshot(scenario[2])
    with pytest.raises(ValueError, match="revision"):
        run(scenario, tmp_path / "stale", phase)
    assert snapshot(scenario[2]) == before


def test_concurrent_requests_commit_one_receipt(scenario, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [
            pool.submit(run, scenario, tmp_path / f"concurrent-{i}", "apply")
            for i in range(2)
        ]
        assert sorted(p.result(timeout=20)["status"] for p in pending) == [
            "already_applied",
            "applied",
        ]


def test_both_routes_use_one_update_statement_under_network_budget(scenario, tmp_path):
    import psycopg

    with psycopg.connect(scenario[3], autocommit=True) as conn:
        conn.execute("CREATE TABLE update_budget (n integer NOT NULL)")
        conn.execute("INSERT INTO update_budget VALUES (0)")
        conn.execute(
            "CREATE FUNCTION check_update_budget() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE used integer; BEGIN UPDATE update_budget SET n=n+1 RETURNING n INTO used; IF used>1 THEN RAISE EXCEPTION 'too many update statements'; END IF; RETURN NULL; END $$"
        )
        conn.execute(
            "CREATE TRIGGER check_update_budget AFTER UPDATE ON words FOR EACH STATEMENT EXECUTE FUNCTION check_update_budget()"
        )
    assert run(scenario, tmp_path / "apply", "apply")["status"] == "applied"
    with psycopg.connect(scenario[3]) as conn:
        assert conn.execute("SELECT n FROM update_budget").fetchone() == (1,)


def test_adapter_partial_cas_match_rolls_back_matched_rows(scenario):
    before = snapshot(scenario[2])
    updates = [
        dict(
            live_word_id=wid,
            word=before[wid]["word"],
            type=before[wid]["type"],
            expected_level=before[wid]["rarity_level"],
            target_level="2",
            expected_version=before[wid]["version"] if wid == "103" else "999999",
        )
        for wid in ("103", "104")
    ]
    with pytest.raises(ValueError, match="affected-row"):
        with scenario[2].transaction() as tx:
            tx.update(updates)
    assert snapshot(scenario[2]) == before


def test_rollback_receipt_side_effect_aborts_reversal(scenario, tmp_path):
    import psycopg

    run(scenario, tmp_path / "apply", "apply")
    before = snapshot(scenario[2])
    with psycopg.connect(scenario[3], autocommit=True) as conn:
        conn.execute(
            "CREATE FUNCTION bad_inverse() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN UPDATE words SET untouched='corrupt' WHERE id=103; RETURN NEW; END $$"
        )
        conn.execute(
            "CREATE TRIGGER bad_inverse AFTER UPDATE ON classificator_private.automatic_promotion_receipts FOR EACH ROW EXECUTE FUNCTION bad_inverse()"
        )
    with pytest.raises(ValueError, match="Receipt write"):
        run(scenario, tmp_path / "failed-rollback", "rollback")
    assert snapshot(scenario[2]) == before
    with scenario[2].transaction() as tx:
        assert (
            tx.receipt(fixtures.digest(scenario[1] / "manifest.json"))["state"]
            == "applied"
        )


def test_lock_timeout_leaves_no_changes_and_retry_succeeds(scenario, tmp_path):
    import psycopg

    before = snapshot(scenario[2])
    with psycopg.connect(scenario[3]) as blocker:
        blocker.execute("LOCK TABLE words IN SHARE ROW EXCLUSIVE MODE")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            run(scenario, tmp_path / "timeout", "apply")
    assert snapshot(scenario[2]) == before
    assert not (tmp_path / "timeout/receipt.json").exists()
    assert run(scenario, tmp_path / "retry", "apply")["status"] == "applied"


def executor(dsn):
    """Create a dedicated fixture backend. Never grants access to the human ledger."""
    from uuid import uuid4
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    role, password = "automatic_test_" + uuid4().hex, uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS PASSWORD {}"
            ).format(sql.Identifier(role), sql.Literal(password))
        )
        for statement in (
            "GRANT USAGE ON SCHEMA public, classificator_private TO {}",
            "GRANT SELECT, UPDATE ON public.words TO {}",
            "GRANT SELECT ON classificator_private.words_revision_contract TO {}",
            "GRANT SELECT, INSERT, UPDATE ON classificator_private.automatic_promotion_receipts TO {}",
        ):
            conn.execute(sql.SQL(statement).format(sql.Identifier(role)))
        conn.execute("ALTER TABLE public.words ENABLE ROW LEVEL SECURITY")
    return PostgresAutomaticStore(make_conninfo(dsn, user=role, password=password))


def test_dedicated_executor_runs_with_rls_and_cannot_read_human_ledger(
    scenario, tmp_path
):
    import psycopg

    store = executor(scenario[3])
    scoped = (scenario[0], scenario[1], store, scenario[3], scenario[4])
    assert run(scoped, tmp_path / "apply", "apply")["status"] == "applied"
    with psycopg.connect(store.dsn) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "SELECT * FROM classificator_private.human_correction_receipts"
            )
    assert run(scoped, tmp_path / "rollback", "rollback")["status"] == "rolled_back"


@pytest.mark.skipif(
    os.environ.get("RUN_AUTOMATIC_FULL_INVENTORY") != "1",
    reason="Full inventory opt-in required",
)
def test_full_inventory_apply_retry_and_rollback(cluster, tmp_path):
    import time

    scenario = prepare(cluster, tmp_path, full=True)
    store = executor(scenario[3])
    scenario = (scenario[0], scenario[1], store, scenario[3], scenario[4])
    before = snapshot(store)
    assert len(before) == 77698
    started = time.monotonic()
    result = run(scenario, tmp_path / "apply", "apply")
    apply_seconds = time.monotonic() - started
    assert result["status"] == "applied"
    assert result["route_changes"] == {"wordfreq": 7537, "fallback": 43187}
    after = snapshot(store)
    changed = {i for i in before if before[i] != after[i]}
    assert len(changed) == 50724
    guards = {r["word_id"] for r in fixtures.rows(scenario[1] / "human-guards.csv")}
    assert len(guards) == 233 and not guards & changed
    assert (
        fixtures.digest(scenario[1] / "candidate.csv")
        == "d7f52e307c523b74958bad4cf483706159cf843f4dbb593abea477c1611aa8ef"
    )
    assert run(scenario, tmp_path / "retry", "apply")["status"] == "already_applied"
    assert snapshot(store) == after
    started = time.monotonic()
    assert run(scenario, tmp_path / "rollback", "rollback")["status"] == "rolled_back"
    rollback_seconds = time.monotonic() - started
    restored = snapshot(store)
    assert {
        i: {k: v for k, v in r.items() if k != "version"} for i, r in restored.items()
    } == {i: {k: v for k, v in r.items() if k != "version"} for i, r in before.items()}
    (tmp_path / "full-result.json").write_text(
        json.dumps(
            dict(
                inventory_rows=len(before),
                changed_rows=len(changed),
                protected_rows=len(guards),
                restored_scores_and_other_columns=True,
                apply_seconds=apply_seconds,
                rollback_seconds=rollback_seconds,
                candidate_sha256=fixtures.digest(scenario[1] / "candidate.csv"),
            ),
            indent=2,
        )
        + "\n"
    )
