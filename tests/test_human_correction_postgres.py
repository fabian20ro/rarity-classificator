"""PostgreSQL adapter contract at the external psycopg boundary; no DB connection."""

import json
from contextlib import contextmanager
import unittest
from unittest.mock import patch


class Connection:
    def __init__(self):
        self.calls = []
        self.committed = False
        self.aborted = False
        self.result = []
        self.rowcount = 1
        self.empty_update = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @contextmanager
    def transaction(self):
        try:
            yield
        except BaseException:
            self.aborted = True
            raise
        self.committed = True

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if "pg_current_xact_id()" in sql:
            self.result = [("4294967317",)]
        elif "SELECT id::text" in sql:
            self.result = [("100", "a'ta", "N", "4", "10")]
        elif "SELECT receipt" in sql:
            self.result = []
        elif sql.startswith("UPDATE public.words"):
            self.result = [] if self.empty_update else [("100",)]
        else:
            self.result = []
        return self

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return self.result


class PostgresHumanStoreTests(unittest.TestCase):
    def test_full_lock_before_snapshot_parameterized_cas_and_receipt_share_one_transaction(self):
        from classificator.human_correction_postgres import PostgresHumanStore

        conn = Connection()
        with patch("psycopg.connect", return_value=conn) as connect:
            store = PostgresHumanStore("postgresql://explicit-test-target")
            self.assertEqual(connect.call_count, 0)
            with store.transaction() as tx:
                self.assertEqual(tx.txid, 4294967317)
                self.assertEqual(tx.snapshot()[0]["version"], "10")
                self.assertIsNone(tx.receipt("package"))
                ids = tx.update(
                    [
                        dict(
                            live_word_id="100",
                            word="a'ta",
                            type="N",
                            expected_level="4",
                            target_level="5",
                            expected_version="10",
                        )
                    ]
                )
                self.assertEqual(ids, ["100"])
                tx.save_receipt("package", dict(state="applied"))
                self.assertFalse(conn.committed)
            self.assertTrue(conn.committed)
            connect.assert_called_once_with("postgresql://explicit-test-target", autocommit=True)
        statements = [s for s, _ in conn.calls]
        lock = next(i for i, s in enumerate(statements) if s.startswith("LOCK TABLE"))
        snapshot = next(i for i, s in enumerate(statements) if s.startswith("SELECT id::text"))
        self.assertLess(lock, snapshot)
        self.assertIn("SHARE ROW EXCLUSIVE MODE", statements[lock])
        self.assertIn("classificator_private.human_correction_receipts", statements[lock])
        self.assertIn("SET LOCAL row_security = off", statements)
        self.assertIn("SET LOCAL synchronous_commit = on", statements)
        self.assertIn("SET TRANSACTION ISOLATION LEVEL READ COMMITTED", statements)
        self.assertIn("SET CONSTRAINTS ALL IMMEDIATE", statements)
        sql, params = next((s, p) for s, p in conn.calls if s.startswith("UPDATE public.words"))
        self.assertNotIn("a'ta", sql)
        self.assertIn("xmin::text = %s", sql)
        self.assertEqual(params, (5, 100, "a'ta", "N", 4, "10"))
        _, params = next((s, p) for s, p in conn.calls if s.startswith("INSERT INTO"))
        self.assertEqual(json.loads(params[1]), dict(state="applied"))

    def test_compare_and_set_count_mismatch_aborts_transaction(self):
        from classificator.human_correction_postgres import PostgresHumanStore

        conn = Connection()
        conn.empty_update = True
        with patch("psycopg.connect", return_value=conn):
            with self.assertRaises(ValueError):
                with PostgresHumanStore("test").transaction() as tx:
                    tx.update(
                        [
                            dict(
                                live_word_id="100",
                                word="ata",
                                type="N",
                                expected_level="4",
                                target_level="5",
                                expected_version="10",
                            )
                        ]
                    )
        self.assertTrue(conn.aborted)
        self.assertFalse(conn.committed)

    def test_failed_durable_receipt_write_aborts_instead_of_committing_unreceipted_changes(self):
        from classificator.human_correction_postgres import PostgresHumanStore

        for replace in (False, True):
            with self.subTest(replace=replace):
                conn = Connection()
                conn.rowcount = 0
                with patch("psycopg.connect", return_value=conn):
                    with self.assertRaises(ValueError):
                        with PostgresHumanStore("test").transaction() as tx:
                            tx.save_receipt("package", dict(state="applied"), replace=replace)
                self.assertTrue(conn.aborted)
                self.assertFalse(conn.committed)
