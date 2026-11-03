"""Dedicated PostgreSQL transaction boundary. Never used by the automatic uploader."""

from contextlib import contextmanager
import json


class PostgresHumanStore:
    """Explicit DSN only; creating this adapter does not open a connection."""

    def __init__(self, dsn: str):
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError("Explicit human-correction database DSN required")
        self.dsn = dsn

    @contextmanager
    def transaction(self):
        import psycopg

        with psycopg.connect(self.dsn, autocommit=True) as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                conn.execute("SET LOCAL lock_timeout = '5s'")
                conn.execute("SET LOCAL statement_timeout = '30s'")
                conn.execute("SET LOCAL synchronous_commit = on")
                conn.execute("SET LOCAL row_security = off")
                conn.execute(
                    "LOCK TABLE public.words, classificator_private.human_correction_receipts IN SHARE ROW EXCLUSIVE MODE"
                )
                txid = int(conn.execute("SELECT pg_current_xact_id()::text").fetchone()[0])
                yield _Transaction(conn, txid)


class _Transaction:
    def __init__(self, conn, txid):
        self.conn, self.txid = conn, txid

    def snapshot(self):
        rows = self.conn.execute(
            "SELECT id::text, word, type, rarity_level::text, xmin::text FROM public.words ORDER BY id"
        ).fetchall()
        return [
            dict(zip(("word_id", "word", "type", "rarity_level", "version"), row, strict=True))
            for row in rows
        ]

    def receipt(self, package_id):
        row = self.conn.execute(
            "SELECT receipt FROM classificator_private.human_correction_receipts WHERE package_id = %s",
            (package_id,),
        ).fetchone()
        return None if row is None else row[0]

    def update(self, changes):
        ids = []
        for change in changes:
            result = self.conn.execute(
                "UPDATE public.words SET rarity_level = %s WHERE id = %s AND word = %s AND type = %s AND rarity_level = %s AND xmin::text = %s RETURNING id::text",
                (
                    int(change["target_level"]),
                    int(change["live_word_id"]),
                    change["word"],
                    change["type"],
                    int(change["expected_level"]),
                    change["expected_version"],
                ),
            ).fetchall()
            if result != [(change["live_word_id"],)]:
                raise ValueError("Concurrent row change or affected-row mismatch")
            ids.append(change["live_word_id"])
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return ids

    def save_receipt(self, package_id, receipt, *, replace=False):
        if replace:
            cursor = self.conn.execute(
                "UPDATE classificator_private.human_correction_receipts SET receipt = %s::jsonb WHERE package_id = %s AND receipt->>'state' = 'applied'",
                (json.dumps(receipt), package_id),
            )
        else:
            cursor = self.conn.execute(
                "INSERT INTO classificator_private.human_correction_receipts (package_id, receipt) VALUES (%s, %s::jsonb)",
                (package_id, json.dumps(receipt)),
            )
        if cursor.rowcount != 1:
            raise ValueError("Durable receipt affected-row mismatch")
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
