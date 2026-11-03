"""Dedicated PostgreSQL transaction boundary. Never used by the automatic uploader."""

from contextlib import contextmanager
import json

REVISION_BODY = """BEGIN
    NEW.classificator_revision := pg_catalog.nextval('classificator_private.words_revision_seq'::pg_catalog.regclass);
    RETURN NEW;
END;"""


def _revision_epoch(conn):
    valid = conn.execute(
        """SELECT a.attnotnull AND a.atttypid='bigint'::regtype
            AND t.tgenabled='A' AND t.tgtype=23 AND t.tgqual IS NULL
            AND t.tgattr=''::int2vector AND NOT t.tgisinternal
            AND p.prosecdef AND p.proconfig=ARRAY['search_path=pg_catalog']
            AND btrim(p.prosrc, E' \\n\\r\\t')=%s
            AND p.proowner=c.relowner AND p.proowner=s.relowner
            AND q.seqtypid='bigint'::regtype AND NOT q.seqcycle
            AND q.seqincrement=1 AND q.seqmin=1 AND q.seqcache=1
            AND NOT EXISTS (
                SELECT 1 FROM pg_trigger other WHERE other.tgrelid=c.oid
                AND other.oid<>t.oid AND (other.tgtype & 3)=3
                AND (other.tgtype & 20)<>0
            )
        FROM pg_attribute a
        JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_trigger t ON t.tgrelid=c.oid AND t.tgname='classificator_word_revision'
        JOIN pg_proc p ON p.oid=t.tgfoid
            AND p.oid=to_regprocedure('classificator_private.assign_word_revision()')
        JOIN pg_class s ON s.oid=to_regclass('classificator_private.words_revision_seq')
        JOIN pg_sequence q ON q.seqrelid=s.oid
        WHERE c.oid='public.words'::regclass AND a.attname='classificator_revision'
            AND NOT a.attisdropped""",
        (REVISION_BODY,),
    ).fetchone()
    if valid != (True,):
        raise ValueError(
            "Missing or incompatible revision contract: column/trigger/function/sequence"
        )
    rows = conn.execute(
        "SELECT epoch::text FROM classificator_private.words_revision_contract WHERE singleton"
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("Missing or ambiguous revision contract epoch")
    return rows[0][0]


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
                method = conn.execute(
                    "SELECT am.amname FROM pg_class c JOIN pg_am am ON am.oid=c.relam WHERE c.oid='public.words'::regclass"
                ).fetchone()
                if method not in {("heap",), ("orioledb",)}:
                    raise ValueError("Storage engine requires a verified revision contract")
                revision = method == ("orioledb",)
                if (
                    revision
                    and not conn.execute(
                        "SELECT to_regclass('classificator_private.words_revision_contract')"
                    ).fetchone()[0]
                ):
                    raise ValueError("Storage engine requires a verified revision contract")
                conn.execute(
                    "LOCK TABLE public.words, classificator_private.human_correction_receipts IN SHARE ROW EXCLUSIVE MODE"
                )
                epoch = None
                if revision:
                    conn.execute(
                        "LOCK TABLE classificator_private.words_revision_contract IN ACCESS SHARE MODE"
                    )
                    epoch = _revision_epoch(conn)
                txid = int(conn.execute("SELECT pg_current_xact_id()::text").fetchone()[0])
                yield _Transaction(conn, txid, epoch)


class _Transaction:
    def __init__(self, conn, txid, epoch=None):
        self.conn, self.txid = conn, txid
        self.version_column = "classificator_revision" if epoch else "xmin"
        self.version_contract = (
            {"kind": "sequence-v1", "epoch": epoch} if epoch else {"kind": "xmin-v1"}
        )

    def snapshot(self):
        if self.version_column == "classificator_revision":
            if _revision_epoch(self.conn) != self.version_contract["epoch"]:
                raise ValueError("The revision contract changed during execution")
        rows = self.conn.execute(
            f"SELECT id::text, word, type, rarity_level::text, {self.version_column}::text FROM public.words ORDER BY id"
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
                f"UPDATE public.words SET rarity_level = %s WHERE id = %s AND word = %s AND type = %s AND rarity_level = %s AND {self.version_column}::text = %s RETURNING id::text",
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
