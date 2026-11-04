"""Owned Docker server only: no arbitrary/environment DSN or application credentials."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import socket
import time
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

IMAGE = "postgres@sha256:c7526c0f6c3f30260a563d7bcf8ad778effac59a44f8ffa86678c35418338609"
ORIOLE_IMAGE = (
    "supabase/postgres@sha256:62b4fa9f99afde62bb9fd49a218531b0f74cd639dc3b03749701005564b837ff"
)
ROOT = Path(__file__).resolve().parents[1]


def docker(*args, check=True, env=None):
    return subprocess.run(
        ["docker", *args], check=check, env=env, text=True, capture_output=True, timeout=60
    ).stdout.strip()


class IsolatedPostgres:
    def __init__(self, name, port, password, engine="heap"):
        self.engine = engine
        self.name = name
        self.options = dict(
            host="127.0.0.1",
            port=port,
            user="codex_human_test",
            password=password,
            dbname="postgres",
            connect_timeout=3,
        )
        self.wait_ready()
        with psycopg.connect(self.dsn) as conn:
            self.version = conn.execute("SHOW server_version").fetchone()[0]
            assert self.version.startswith("17.9"), self.version

    @property
    def dsn(self):
        return make_conninfo(**self.options)

    def wait_ready(self):
        deadline = time.monotonic() + 30
        while True:
            try:
                with psycopg.connect(self.dsn):
                    return
            except psycopg.OperationalError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)

    def database(self):
        name = "human_test_" + uuid4().hex
        with psycopg.connect(self.dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        return make_conninfo(**dict(self.options, dbname=name))

    def seed(self, dsn, rows, *, revisions=True):
        # Only databases minted by this owned server; callers cannot redirect the fixture.
        from psycopg.conninfo import conninfo_to_dict

        config = conninfo_to_dict(dsn)
        assert all(
            config.get(k) == str(self.options[k]) for k in ("host", "port", "user", "password")
        )
        assert config["dbname"].startswith("human_test_")
        with psycopg.connect(dsn, autocommit=True) as conn:
            if self.engine == "orioledb":
                conn.execute("CREATE EXTENSION orioledb")
                assert conn.execute(
                    "SELECT extversion FROM pg_extension WHERE extname='orioledb'"
                ).fetchone() == ("1.8",)
                conn.execute("SET default_table_access_method = orioledb")
            conn.execute(
                "CREATE TABLE public.words (id bigint PRIMARY KEY, word text NOT NULL, type text NOT NULL, rarity_level integer NOT NULL CHECK (rarity_level BETWEEN 1 AND 5))"
            )
            with conn.cursor().copy(
                "COPY public.words (id, word, type, rarity_level) FROM STDIN"
            ) as copy:
                for row in rows:
                    copy.write_row(
                        (int(row["word_id"]), row["word"], row["type"], int(row["rarity_level"]))
                    )
            conn.execute((ROOT / "docs/sql/2026-11-03-human-correction-receipts.sql").read_text())
            if self.engine == "orioledb" and revisions:
                conn.execute((ROOT / "docs/sql/2026-11-03-human-row-revisions.sql").read_text())

    def restart(self):
        docker("restart", "--time", "5", self.name)
        self.wait_ready()


@contextmanager
def isolated_postgres():
    engine = os.environ.get("HUMAN_PG_ENGINE", "heap")
    if engine not in {"heap", "orioledb"}:
        raise ValueError("Only owned heap/orioledb fixtures supported")
    image = ORIOLE_IMAGE if engine == "orioledb" else IMAGE
    command = [image, "-c", "max_wal_size=128MB", "-c", "shared_buffers=32MB"]
    if engine == "orioledb":
        command = ["--entrypoint", "sh", image, "-c", ORIOLE_BOOTSTRAP]
    name = "codex-human-pg-" + uuid4().hex[:12]
    volume = name + "-data"
    password = uuid4().hex
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    docker("volume", "create", "--label", "codex.task=human-correction-integration", volume)
    try:
        docker(
            "run",
            "--detach",
            "--pull=never",
            "--name",
            name,
            "--label",
            "codex.task=human-correction-integration",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--publish",
            f"127.0.0.1:{port}:5432",
            "--mount",
            f"type=volume,source={volume},target=/var/lib/postgresql/data",
            "--env",
            "POSTGRES_PASSWORD",
            "--env",
            "POSTGRES_USER=codex_human_test",
            "--env",
            "POSTGRES_DB=postgres",
            *command,
            env=dict(os.environ, POSTGRES_PASSWORD=password),
        )
        binding = json.loads(
            docker("inspect", "--format", "{{json .NetworkSettings.Ports}}", name)
        )["5432/tcp"]
        assert len(binding) == 1 and binding[0]["HostIp"] == "127.0.0.1"
        server = IsolatedPostgres(name, binding[0]["HostPort"], password, engine)
        report_path = os.environ.get("HUMAN_PG_REPORT_PATH")
        report = dict(
            image=image,
            engine=engine,
            extension_version="1.8" if engine == "orioledb" else None,
            server_version=server.version,
            container=name,
            volume=volume,
            host="127.0.0.1",
            host_port=int(binding[0]["HostPort"]),
            memory_limit_mib=512,
            container_removed=False,
            volume_removed=False,
        )
        if report_path:
            Path(report_path).write_text(json.dumps(report, indent=2) + "\n")
        yield server
    finally:
        docker("rm", "--force", name, check=False)
        docker("volume", "rm", volume)
        if "report" in locals() and report_path:
            report.update(container_removed=True, volume_removed=True)
            Path(report_path).write_text(json.dumps(report, indent=2) + "\n")


# Only a fresh owned volume. Avoid Supabase application initialization/credentials.
ORIOLE_BOOTSTRAP = r"""
export PGDATA=/var/lib/postgresql/data
mkdir -p "$PGDATA"
chown postgres:postgres "$PGDATA"
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    printf '%s\n' "$POSTGRES_PASSWORD" > /tmp/test-pw
    chown postgres /tmp/test-pw
    gosu postgres initdb --locale=C --encoding=UTF8 -D "$PGDATA" -U codex_human_test --auth-host=scram-sha-256 --auth-local=trust --pwfile=/tmp/test-pw >/dev/null || exit 1
    rm /tmp/test-pw
    printf 'host all all 0.0.0.0/0 scram-sha-256\n' >> "$PGDATA/pg_hba.conf"
fi
exec gosu postgres postgres -D "$PGDATA" -c listen_addresses='*' -c shared_preload_libraries=orioledb -c orioledb.main_buffers=32MB -c shared_buffers=32MB -c max_wal_size=128MB
"""
