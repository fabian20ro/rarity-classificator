import unittest
from unittest.mock import MagicMock

from classificator.word_store import WordStore


class _FakeCursor:
    def __init__(self):
        self.executemany_calls: list[tuple[str, list[tuple[int, int]]]] = []
        self._execute_sql: str | None = None
        self.fetchall_rows: list[list] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def executemany(self, sql: str, payload: list[tuple[int, int]]) -> None:
        self.executemany_calls.append((sql, payload))

    def execute(self, sql: str) -> None:
        self._execute_sql = sql

    def fetchall(self) -> list[list]:
        return self.fetchall_rows


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor
        self.commit_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor

    def commit(self) -> None:
        self.commit_calls += 1


class WordStoreTest(unittest.TestCase):
    def test_update_rarity_levels_chunked_updates_only_rarity_column(self):
        store = WordStore(db_url="postgresql://example.invalid/db", db_user="u", db_password="p")
        fake_cursor = _FakeCursor()
        fake_conn = _FakeConnection(fake_cursor)
        store._connect = MagicMock(return_value=fake_conn)

        updates = {
            101: 2,
            102: 5,
            103: 1,
        }
        store.update_rarity_levels_chunked(updates, chunk_size=2)

        self.assertEqual(fake_conn.commit_calls, 1)
        self.assertEqual(len(fake_cursor.executemany_calls), 2)
        self.assertEqual(
            fake_cursor.executemany_calls[0],
            (
                "UPDATE words SET rarity_level = %s WHERE id = %s",
                [(2, 101), (5, 102)],
            ),
        )
        self.assertEqual(
            fake_cursor.executemany_calls[1],
            (
                "UPDATE words SET rarity_level = %s WHERE id = %s",
                [(1, 103)],
            ),
        )
        for _, payload in fake_cursor.executemany_calls:
            for item in payload:
                self.assertEqual(len(item), 2)

    def test_update_rarity_levels_chunked_empty_updates_does_not_connect(self):
        store = WordStore(db_url="postgresql://example.invalid/db", db_user="u", db_password="p")
        store._connect = MagicMock()

        store.update_rarity_levels_chunked({}, chunk_size=2)

        store._connect.assert_not_called()

    def test_update_rarity_levels_non_chunked_sends_single_batch(self):
        store = WordStore(db_url="postgresql://example.invalid/db", db_user="u", db_password="p")
        fake_cursor = _FakeCursor()
        fake_conn = _FakeConnection(fake_cursor)
        store._connect = MagicMock(return_value=fake_conn)

        updates = {10: 3, 20: 1}
        store.update_rarity_levels(updates)

        self.assertEqual(len(fake_cursor.executemany_calls), 1)
        sql, payload = fake_cursor.executemany_calls[0]
        self.assertEqual(sql, "UPDATE words SET rarity_level = %s WHERE id = %s")
        # Items iteration order is insertion-ordered in modern CPython; accept any ordering.
        self.assertEqual(set(payload), {(3, 10), (1, 20)})
        self.assertEqual(fake_conn.commit_calls, 1)

    def test_update_rarity_levels_chunked_invalid_chunk_size_raises(self):
        store = WordStore(db_url="postgresql://example.invalid/db", db_user="u", db_password="p")

        with self.assertRaises(ValueError):
            store.update_rarity_levels_chunked({1: 2}, chunk_size=0)
        with self.assertRaises(ValueError):
            store.update_rarity_levels_chunked({1: 2}, chunk_size=-5)

    def test_update_rarity_levels_empty_updates_skips_connection(self):
        store = WordStore(db_url="postgresql://example.invalid/db", db_user="u", db_password="p")
        store._connect = MagicMock()

        store.update_rarity_levels({})

        store._connect.assert_not_called()

    def test_fetch_all_words_parses_rows_into_word_objects(self):
        store = WordStore(db_url="postgresql://example.invalid/db", db_user="u", db_password="p")
        fake_cursor = _FakeCursor()
        fake_conn = _FakeConnection(fake_cursor)
        store._connect = MagicMock(return_value=fake_conn)
        fake_cursor.fetchall_rows = [[1, "alpha", "noun"], [2, "beta", "verb"]]

        words = store.fetch_all_words()

        self.assertEqual(len(words), 2)
        self.assertEqual(words[0].word_id, 1)
        self.assertEqual(words[0].word, "alpha")
        self.assertEqual(words[0].type, "noun")
        self.assertEqual(words[1].word_id, 2)
        self.assertEqual(words[1].word, "beta")
        self.assertEqual(words[1].type, "verb")

    def test_fetch_all_word_levels_parses_rows_into_word_level_objects(self):
        store = WordStore(db_url="postgresql://example.invalid/db", db_user="u", db_password="p")
        fake_cursor = _FakeCursor()
        fake_conn = _FakeConnection(fake_cursor)
        store._connect = MagicMock(return_value=fake_conn)
        fake_cursor.fetchall_rows = [[10, 3], [20, 5]]

        levels = store.fetch_all_word_levels()

        self.assertEqual(len(levels), 2)
        self.assertEqual(levels[0].word_id, 10)
        self.assertEqual(levels[0].rarity_level, 3)
        self.assertEqual(levels[1].word_id, 20)
        self.assertEqual(levels[1].rarity_level, 5)

    def test_fetch_all_words_empty_table_returns_empty_list(self):
        store = WordStore(db_url="postgresql://example.invalid/db", db_user="u", db_password="p")
        fake_cursor = _FakeCursor()
        fake_conn = _FakeConnection(fake_cursor)
        store._connect = MagicMock(return_value=fake_conn)
        fake_cursor.fetchall_rows = []

        words = store.fetch_all_words()

        self.assertEqual(words, [])


if __name__ == "__main__":
    unittest.main()
