"""Dedicated automatic ledger and sequence revisions; no implicit schema installation."""

from contextlib import contextmanager
import json

from .human_correction_postgres import _revision_epoch


class PostgresAutomaticStore:
    def __init__(self, dsn: str):
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError("Explicit automatic-promotion DSN required")
        self.dsn = dsn

    @contextmanager
    def transaction(self):
        import psycopg

        with psycopg.connect(self.dsn, autocommit=True, connect_timeout=10) as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                conn.execute("SET LOCAL lock_timeout = '5s'")
                conn.execute("SET LOCAL statement_timeout = '30s'")
                conn.execute("SET LOCAL synchronous_commit = on")
                conn.execute("SET LOCAL row_security = off")
                conn.execute(
                    "LOCK TABLE public.words, classificator_private.automatic_promotion_receipts IN SHARE ROW EXCLUSIVE MODE"
                )
                conn.execute(
                    "LOCK TABLE classificator_private.words_revision_contract IN ACCESS SHARE MODE"
                )
                epoch = _revision_epoch(conn)
                txid = int(
                    conn.execute("SELECT pg_current_xact_id()::text").fetchone()[0]
                )
                yield _Transaction(conn, txid, epoch)


class _Transaction:
    def __init__(self, conn, txid, epoch):
        self.conn, self.txid = conn, txid
        self.version_contract = dict(kind="sequence-v1", epoch=epoch)

    def snapshot(self):
        if _revision_epoch(self.conn) != self.version_contract["epoch"]:
            raise ValueError("Revision installation changed during execution")
        rows = self.conn.execute("""SELECT id::text, word, type, rarity_level::text,
            classificator_revision::text,
            encode(sha256(convert_to((to_jsonb(w) - ARRAY['rarity_level', 'classificator_revision'])::text, 'UTF8')), 'hex')
            FROM public.words w ORDER BY id""").fetchall()
        return [
            dict(
                zip(
                    (
                        "word_id",
                        "word",
                        "type",
                        "rarity_level",
                        "version",
                        "other_columns_sha256",
                    ),
                    r,
                    strict=True,
                )
            )
            for r in rows
        ]

    def receipt(self, package_id):
        row = self.conn.execute(
            "SELECT receipt FROM classificator_private.automatic_promotion_receipts WHERE package_id=%s",
            (package_id,),
        ).fetchone()
        return None if row is None else row[0]

    def update(self, changes):
        result = self.conn.execute(
            """UPDATE public.words AS w SET rarity_level=c.target_level
            FROM unnest(%s::bigint[], %s::text[], %s::text[], %s::integer[],
                        %s::bigint[], %s::integer[])
                AS c(id, word, type, expected_level, expected_version, target_level)
            WHERE w.id=c.id AND w.word=c.word AND w.type=c.type
              AND w.rarity_level=c.expected_level
              AND w.classificator_revision=c.expected_version
            RETURNING w.id::text""",
            (
                [int(r["live_word_id"]) for r in changes],
                [r["word"] for r in changes],
                [r["type"] for r in changes],
                [int(r["expected_level"]) for r in changes],
                [int(r["expected_version"]) for r in changes],
                [int(r["target_level"]) for r in changes],
            ),
        ).fetchall()
        ids = [r[0] for r in result]
        if sorted(ids) != sorted(r["live_word_id"] for r in changes):
            raise ValueError("Concurrent row change or affected-row mismatch")
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return ids

    def save_receipt(self, package_id, receipt, *, replace=False):
        if replace:
            cursor = self.conn.execute(
                """UPDATE classificator_private.automatic_promotion_receipts
                SET receipt=%s::jsonb WHERE package_id=%s AND receipt->>'state'='applied'""",
                (json.dumps(receipt), package_id),
            )
        else:
            cursor = self.conn.execute(
                "INSERT INTO classificator_private.automatic_promotion_receipts (package_id,receipt) VALUES (%s,%s::jsonb)",
                (package_id, json.dumps(receipt)),
            )
        if cursor.rowcount != 1:
            raise ValueError("Durable receipt affected-row mismatch")
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
