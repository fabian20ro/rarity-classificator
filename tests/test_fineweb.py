import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

from classificator.evaluation.fineweb import export_fineweb_frequencies


class Response:
    def __init__(self, data, start, end):
        self.status_code = 206
        self.headers = {
            "Content-Range": f"bytes {start}-{end}/{len(data)}",
            "Content-Length": str(end - start + 1),
        }
        self.raw = io.BytesIO(data[start : end + 1])

    def close(self):
        pass


class HTTP:
    def __init__(self, data):
        self.data = data
        self.bytes_read = 0

    def get(self, url, **kwargs):
        start, end = map(int, kwargs["headers"]["Range"][6:].split("-"))
        self.bytes_read += end - start + 1
        return Response(self.data, start, end)


class FineWebTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vocab = self.root / "vocabulary.csv"
        self.vocab.write_text(
            "word_id,word,type\n1,casă,N\n2,casă,V\n3,țară,N\n4,cas,N\n5,necunoscut,N\n"
        )
        self.documents = [
            dict(
                text="Casă casă ţară Düsseldorf casa-mare.",
                url="https://news.ro/a",
                date="2022-01-01T00:00:00Z",
                language="ron",
                language_score=0.99,
            ),
            dict(
                text="Casă!",
                url="https://news2.ro/b",
                date="2023-01-01T00:00:00Z",
                language="ron",
                language_score=0.99,
            ),
        ]

    def source(self, documents=None):
        sink = pa.BufferOutputStream()
        pq.write_table(
            pa.Table.from_pylist(documents or self.documents), sink, row_group_size=1
        )
        raw = sink.getvalue().to_pybytes()
        path = self.root / "shards.json"
        path.write_text(
            json.dumps(
                [{"path": "data/ron_Latn/train/000_00000.parquet", "size": len(raw)}]
            )
        )
        return path, HTTP(raw)

    def run_export(self, documents=None, **kwargs):
        shards, http = self.source(documents)
        result = export_fineweb_frequencies(
            self.vocab,
            shards,
            self.root / "out",
            session=http,
            initial_bytes=0,
            **kwargs,
        )
        rows = {
            int(r["word_id"]): r
            for r in csv.DictReader((self.root / "out/frequencies.csv").open())
        }
        return result, rows, http

    def test_exact_surface_counts_preserve_every_inventory_identity(self):
        result, rows, http = self.run_export()
        self.assertEqual([int(rows[i]["count"]) for i in range(1, 6)], [3, 3, 1, 0, 0])
        self.assertEqual(rows[1]["document_count"], "2")
        self.assertEqual(rows[1]["host_count"], "2")
        self.assertEqual(rows[1]["token_total"], "6")
        self.assertEqual(rows[5]["status"], "unobserved")
        self.assertEqual(result["counts"]["examined_documents"], 2)
        self.assertLessEqual(result["budget"]["charged_bytes"], 1 << 30)

    def test_budget_exhaustion_keeps_all_rows_and_resume_cannot_reset_budget(self):
        shards, http = self.source()
        out = self.root / "out"
        result = export_fineweb_frequencies(
            self.vocab, shards, out, session=http, initial_bytes=0, max_bytes=1
        )
        self.assertEqual(result["counts"]["examined_documents"], 0)
        self.assertEqual(http.bytes_read, 0)
        self.assertEqual(result["stop_reason"], "transfer_budget")
        self.assertEqual(len(list(csv.DictReader((out / "frequencies.csv").open()))), 5)
        with self.assertRaisesRegex(ValueError, "changed"):
            export_fineweb_frequencies(
                self.vocab, shards, out, session=http, initial_bytes=0, max_bytes=100000
            )

    def test_filters_and_duplicates_count_toward_document_limit(self):
        docs = [
            self.documents[0],
            dict(self.documents[0], url="https://other.ro/duplicate"),
            dict(self.documents[1], date="2018-01-01"),
            dict(self.documents[1], url="https://dexonline.ro/definitie/casa"),
        ]
        result, rows, _ = self.run_export(docs, max_documents=4)
        self.assertEqual(result["counts"]["examined_documents"], 4)
        self.assertEqual(rows[1]["count"], "2")
        self.assertEqual(rows[1]["token_total"], "5")
        self.assertEqual(result["counts"]["duplicate"], 1)
        self.assertEqual(result["counts"]["excluded_dictionary"], 1)
        older = list(csv.DictReader((self.root / "out/older-frequencies.csv").open()))
        self.assertEqual(older[0]["count"], "1")

    def test_interrupted_run_resumes_without_double_counting_or_resetting_transfer(
        self,
    ):
        shards, http = self.source()
        original = http.get
        calls = 0

        def interrupted(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 7:
                raise ConnectionError("interrupted")
            return original(*args, **kwargs)

        http.get = interrupted
        with self.assertRaises(ConnectionError):
            export_fineweb_frequencies(
                self.vocab, shards, self.root / "out", session=http, initial_bytes=0
            )
        spent = json.loads((self.root / "out/budget.json").read_text())["charged_bytes"]
        http.get = original
        result = export_fineweb_frequencies(
            self.vocab, shards, self.root / "out", session=http, initial_bytes=0
        )
        self.assertEqual(result["counts"]["examined_documents"], 2)
        self.assertGreater(result["budget"]["charged_bytes"], spent)
        received = http.bytes_read
        replay = export_fineweb_frequencies(
            self.vocab, shards, self.root / "out", session=http, initial_bytes=0
        )
        self.assertEqual(replay, result)
        self.assertEqual(http.bytes_read, received)

    def test_document_budget_is_distributed_across_shards_before_filtering(self):
        shards, http = self.source()
        listing = json.loads(shards.read_text())
        listing.append(dict(listing[0], path="data/ron_Latn/train/000_00001.parquet"))
        shards.write_text(json.dumps(listing))
        result = export_fineweb_frequencies(
            self.vocab,
            shards,
            self.root / "out",
            session=http,
            initial_bytes=0,
            max_documents=2,
        )
        sample = list(csv.DictReader((self.root / "out/sampling.csv").open()))
        self.assertEqual({r["shard"] for r in sample}, {r["path"] for r in listing})
        self.assertEqual([int(r["examined"]) for r in sample], [1, 1])
        self.assertEqual(result["counts"]["examined_documents"], 2)

    def test_redirects_remain_bounded_and_full_file_responses_are_rejected(self):
        from unittest.mock import patch

        shards, http = self.source()
        original = http.get

        def redirected(url, **kwargs):
            if "huggingface.co" in url:
                response = Response(http.data, 0, 0)
                response.status_code = 302
                response.headers = {"Location": "https://cdn.hf.co/data"}
                return response
            return original(url, **kwargs)

        http.get = redirected
        result = export_fineweb_frequencies(
            self.vocab, shards, self.root / "out", session=http, initial_bytes=0
        )
        self.assertEqual(result["counts"]["examined_documents"], 2)
        bad = self.root / "bad"
        response = Response(http.data, 0, 0)
        response.status_code = 200
        with patch.object(
            response.raw, "read", side_effect=AssertionError("must not read full file")
        ):
            http.get = lambda *a, **k: response
            with self.assertRaisesRegex(ValueError, "range"):
                export_fineweb_frequencies(
                    self.vocab, shards, bad, session=http, initial_bytes=0
                )

    def test_low_disk_stops_before_http_and_keeps_explicit_zero_coverage(self):
        from unittest.mock import patch

        with patch("shutil.disk_usage", return_value=type("Disk", (), {"free": 1})()):
            result, rows, http = self.run_export()
        self.assertEqual(http.bytes_read, 0)
        self.assertEqual(result["stop_reason"], "disk_reserve")
        self.assertEqual(rows[1]["count"], "0")

    def test_invalid_or_duplicate_shard_identity_fails_before_transfer(self):
        shards, http = self.source()
        original = json.loads(shards.read_text())
        for listing in [
            original + original,
            [dict(original[0], path="../other.parquet")],
            [dict(original[0], size=-1)],
        ]:
            with self.subTest(listing=listing):
                shards.write_text(json.dumps(listing))
                with self.assertRaisesRegex(ValueError, "shard"):
                    export_fineweb_frequencies(
                        self.vocab,
                        shards,
                        self.root / str(len(str(listing))),
                        session=http,
                        initial_bytes=0,
                    )
        self.assertEqual(http.bytes_read, 0)

    def test_low_disk_pause_can_resume_after_space_recovers(self):
        from unittest.mock import patch

        shards, http = self.source()
        with patch("shutil.disk_usage", return_value=type("Disk", (), {"free": 1})()):
            export_fineweb_frequencies(
                self.vocab, shards, self.root / "out", session=http, initial_bytes=0
            )
        result = export_fineweb_frequencies(
            self.vocab, shards, self.root / "out", session=http, initial_bytes=0
        )
        self.assertEqual(result["counts"]["examined_documents"], 2)

    def test_compressed_group_cannot_exceed_decompression_limit(self):
        docs = [dict(self.documents[0], text="casă " * 2000)]
        result, rows, _ = self.run_export(docs, max_group_bytes=1024)
        self.assertEqual(result["stop_reason"], "row_group_memory_limit")
        self.assertEqual(result["counts"]["examined_documents"], 0)
        self.assertEqual(rows[1]["count"], "0")

    def test_interruption_does_not_refund_reserved_document_budget(self):
        shards, http = self.source()
        original = http.get
        calls = 0

        def interrupted(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 7:
                raise ConnectionError("interrupted")
            return original(*args, **kwargs)

        http.get = interrupted
        with self.assertRaises(ConnectionError):
            export_fineweb_frequencies(
                self.vocab,
                shards,
                self.root / "out",
                session=http,
                initial_bytes=0,
                max_documents=2,
            )
        http.get = original
        result = export_fineweb_frequencies(
            self.vocab,
            shards,
            self.root / "out",
            session=http,
            initial_bytes=0,
            max_documents=2,
        )
        self.assertEqual(result["budget"]["reserved_documents"], 2)
        self.assertEqual(result["counts"]["examined_documents"], 1)
        self.assertFalse(result["counts"]["balanced_sample"])

    def test_concurrent_export_cannot_share_or_reset_campaign_budget(self):
        shards, http = self.source()
        original = http.get
        attempted = False

        def nested(*args, **kwargs):
            nonlocal attempted
            if not attempted:
                attempted = True
                with self.assertRaises(BlockingIOError):
                    export_fineweb_frequencies(
                        self.vocab,
                        shards,
                        self.root / "out",
                        session=http,
                        initial_bytes=0,
                    )
            return original(*args, **kwargs)

        http.get = nested
        export_fineweb_frequencies(
            self.vocab, shards, self.root / "out", session=http, initial_bytes=0
        )
        self.assertTrue(attempted)

    def test_cli_uses_bounded_source_without_database_or_model(self):
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from classificator.cli import main

        shards, http = self.source()
        with (
            patch(
                "requests.adapters.HTTPAdapter.send",
                side_effect=lambda request, **kwargs: http.get(
                    request.url, headers=request.headers
                ),
            ),
            patch("psycopg.connect", side_effect=AssertionError("DB forbidden")),
            redirect_stdout(io.StringIO()),
        ):
            code = main(
                [
                    "--output-dir",
                    str(self.root / "logs"),
                    "evaluation-fineweb",
                    "--vocabulary-csv",
                    str(self.vocab),
                    "--shards-json",
                    str(shards),
                    "--campaign-dir",
                    str(self.root / "out"),
                    "--max-documents",
                    "2",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads((self.root / "out/manifest.json").read_text())["counts"][
                "examined_documents"
            ],
            2,
        )

    def test_bounded_concordances_retain_exact_match_and_source(self):
        self.run_export()
        rows = list(csv.DictReader((self.root / "out/concordances.csv").open()))
        country = next(r for r in rows if r["word"] == "țară")
        self.assertEqual(country["url"], "https://news.ro/a")
        self.assertIn("țară", country["context"])
        self.assertLessEqual(len(country["context"]), 200)
        self.assertEqual({r["word"] for r in rows}, {"casă", "țară"})

    def test_tampered_campaign_budget_cannot_be_reused(self):
        shards, http = self.source()
        export_fineweb_frequencies(
            self.vocab, shards, self.root / "out", session=http, initial_bytes=0
        )
        path = self.root / "out/budget.json"
        ledger = json.loads(path.read_text())
        ledger["charged_bytes"] = 0
        path.write_text(json.dumps(ledger))
        with self.assertRaisesRegex(ValueError, "budget"):
            export_fineweb_frequencies(
                self.vocab, shards, self.root / "out", session=http, initial_bytes=0
            )

    def test_corrupt_checkpoint_fails_closed_before_resuming(self):
        shards, http = self.source()
        original = http.get
        calls = 0

        def interrupted(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 7:
                raise ConnectionError("interrupted")
            return original(*args, **kwargs)

        http.get = interrupted
        with self.assertRaises(ConnectionError):
            export_fineweb_frequencies(
                self.vocab, shards, self.root / "out", session=http, initial_bytes=0
            )
        path = self.root / "out/checkpoint.json"
        data = json.loads(path.read_text())
        state = data.get("state", data)
        state["primary"]["counts"]["casă"] += 1
        path.write_text(json.dumps(data))
        http.get = original
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            export_fineweb_frequencies(
                self.vocab, shards, self.root / "out", session=http, initial_bytes=0
            )

    def test_interrupted_projection_after_disk_recovery_is_rebuildable(self):
        from unittest.mock import patch

        shards, http = self.source()
        calls = 0

        def disk(path):
            nonlocal calls
            calls += 1
            return type("Disk", (), {"free": (10 << 30) if calls <= 6 else 1})()

        with patch("shutil.disk_usage", side_effect=disk):
            stopped = export_fineweb_frequencies(
                self.vocab, shards, self.root / "out", session=http, initial_bytes=0
            )
        self.assertEqual(stopped["stop_reason"], "disk_reserve")
        original = Path.open

        def interrupted(path, *args, **kwargs):
            if path.name == "older-frequencies.csv" and args and args[0] == "w":
                raise OSError("publication interrupted")
            return original(path, *args, **kwargs)

        with patch.object(Path, "open", interrupted):
            with self.assertRaises(OSError):
                export_fineweb_frequencies(
                    self.vocab, shards, self.root / "out", session=http, initial_bytes=0
                )
        result = export_fineweb_frequencies(
            self.vocab, shards, self.root / "out", session=http, initial_bytes=0
        )
        self.assertEqual(result["counts"]["examined_documents"], 2)
        rows = list(csv.DictReader((self.root / "out/frequencies.csv").open()))
        self.assertEqual(rows[0]["count"], "3")
