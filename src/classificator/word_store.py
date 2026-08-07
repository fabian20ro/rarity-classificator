from __future__ import annotations

import os

from .models import BaseWordRow, WordLevel


class WordStore:
    def __init__(
        self,
        db_url: str | None = None,
        db_user: str | None = None,
        db_password: str | None = None,
    ) -> None:
        self.db_url = db_url or os.getenv("SUPABASE_DB_URL") or "postgresql://localhost:5432/postgres"
        self.db_user = db_user or os.getenv("SUPABASE_DB_USER") or "postgres"
        self.db_password = db_password if db_password is not None else os.getenv("SUPABASE_DB_PASSWORD", "")

    def _connect(self):
        try:
            import psycopg
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Missing dependency 'psycopg'. Install project dependencies with: pip install -e ."
            ) from exc
        return psycopg.connect(self.db_url, user=self.db_user, password=self.db_password, autocommit=False)

    def fetch_all_words(self) -> list[BaseWordRow]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, word, type FROM words ORDER BY id")
            rows = cur.fetchall()
        return [BaseWordRow(word_id=r[0], word=r[1], type=r[2]) for r in rows]

    def fetch_all_word_levels(self) -> list[WordLevel]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, rarity_level FROM words ORDER BY id")
            rows = cur.fetchall()
        return [WordLevel(word_id=r[0], rarity_level=r[1]) for r in rows]

    @staticmethod
    def _validate_update_payload(updates: dict[int, int]) -> None:
        for level in updates.values():
            if not isinstance(level, int):
                raise TypeError(
                    f"Level must be an integer, got {type(level).__name__}"
                )
            if not (1 <= level <= 5):
                raise ValueError(f"Level must be in range 1..5, got {level}")

    def update_rarity_levels(self, updates: dict[int, int]) -> None:
        self._validate_update_payload(updates)
        if not updates:
            return
        with self._connect() as conn, conn.cursor() as cur:
            payload = [(level, word_id) for word_id, level in updates.items()]
            cur.executemany("UPDATE words SET rarity_level = %s WHERE id = %s", payload)
            conn.commit()

    def update_rarity_levels_chunked(self, updates: dict[int, int], chunk_size: int = 5000) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self._validate_update_payload(updates)
        if not updates:
            return
        items = list(updates.items())
        with self._connect() as conn, conn.cursor() as cur:
            for i in range(0, len(items), chunk_size):
                chunk = items[i : i + chunk_size]
                payload = [(lvl, wid) for wid, lvl in chunk]
                cur.executemany("UPDATE words SET rarity_level = %s WHERE id = %s", payload)
            conn.commit()
