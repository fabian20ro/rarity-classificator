"""Real Requests responses at the public HTTP-to-CSV export boundary."""

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import requests

from classificator.evaluation.fineweb import export_fineweb_frequencies


class UnreadBody(io.BytesIO):
    def read(self, *args, **kwargs):
        raise AssertionError("unbounded response body must remain unread")


class FineWebTransportTests(unittest.TestCase):
    def test_real_requests_redirect_body_is_never_consumed(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            vocabulary = root / "vocabulary.csv"
            vocabulary.write_text("word_id,word,type\n1,casă,N\n")
            sink = pa.BufferOutputStream()
            pq.write_table(
                pa.Table.from_pylist(
                    [
                        dict(
                            text="Casă.",
                            url="https://news.ro/a",
                            date="2022-01-01T00:00:00Z",
                            language="ron",
                            language_score=0.99,
                        )
                    ]
                ),
                sink,
            )
            payload = sink.getvalue().to_pybytes()
            shards = root / "shards.json"
            shards.write_text(
                json.dumps(
                    [
                        dict(
                            path="data/ron_Latn/train/000_00000.parquet",
                            size=len(payload),
                        )
                    ]
                )
            )
            redirects = []

            def external_send(request, **kwargs):
                response = requests.Response()
                response.request, response.url = request, request.url
                if request.url.startswith("https://huggingface.co/"):
                    response.status_code = 302
                    response.headers.update(
                        {
                            "Location": "https://cdn.hf.co/data",
                            "Content-Length": str(1 << 20),
                        }
                    )
                    response.raw = UnreadBody(b"ignored")
                    redirects.append(response.raw)
                else:
                    start, end = map(int, request.headers["Range"][6:].split("-"))
                    response.status_code = 206
                    response.headers.update(
                        {
                            "Content-Range": f"bytes {start}-{end}/{len(payload)}",
                            "Content-Length": str(end - start + 1),
                        }
                    )
                    response.raw = io.BytesIO(payload[start : end + 1])
                return response

            with patch.object(
                requests.adapters.HTTPAdapter, "send", side_effect=external_send
            ):
                result = export_fineweb_frequencies(
                    vocabulary, shards, root / "out", initial_bytes=0, max_documents=1
                )
            self.assertEqual(result["counts"]["examined_documents"], 1)
            self.assertTrue(redirects)
            self.assertTrue(all(body.closed for body in redirects))
