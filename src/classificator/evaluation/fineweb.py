"""Bounded, sequential FineWeb2 surface-frequency experiment; no model or DB access."""

from collections import Counter, defaultdict
import io
import hashlib
import fcntl
import math
import random
import re
import json
import os
from pathlib import Path
import shutil
from urllib.parse import urlparse, urljoin

from .dataset import _lexeme, _sha256, _vocabulary, _write_csv
from .definition_frequency import TOKEN

REVISION = "af9c13333eb981300149d5ca60a8e9d659b276b9"
BASE = f"https://huggingface.co/datasets/HuggingFaceFW/fineweb-2/resolve/{REVISION}/"
POLICY = "fineweb-exact-forms-v1"
COLUMNS = ["text", "url", "date", "language", "language_score"]


class _Stop(Exception):
    pass


def _save(path, data):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as handle:
        json.dump(
            data,
            handle,
            ensure_ascii=False,
            allow_nan=False,
            default=lambda value: sorted(value) if isinstance(value, set) else None,
        )
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _digest(data):
    return hashlib.sha256(
        json.dumps(
            data, sort_keys=True, allow_nan=False, default=lambda v: sorted(v)
        ).encode()
    ).hexdigest()


def _checkpoint(path, state, binding):
    _save(path, dict(schema=1, binding=binding, state=state, sha256=_digest(state)))


class _Budget:
    def __init__(self, path, binding, maximum, initial):
        self.path, self.maximum = path, maximum
        if path.exists():
            self.state = json.loads(path.read_text())
            expected = initial + sum(
                r["reserved"] if r["status"] == "pending" else r["received"] + 8192
                for r in self.state["requests"]
            )
            if expected != self.state["charged_bytes"] or not 0 <= expected <= maximum:
                raise ValueError("Invalid campaign budget ledger")
            if self.state["binding"] != binding:
                raise ValueError("Run inputs/configuration changed")
        else:
            self.state = dict(
                binding=binding,
                charged_bytes=initial,
                received_bytes=0,
                reserved_documents=0,
                requests=[],
            )
            _save(path, self.state)

    def reserve_documents(self, count):
        if (
            self.state["reserved_documents"] + count
            > self.state["binding"]["max_documents"]
        ):
            raise _Stop("document_budget")
        self.state["reserved_documents"] += count
        _save(self.path, self.state)

    def reserve(self, url, start, end):
        if shutil.disk_usage(self.path.parent).free < 5 << 30:
            raise _Stop("disk_reserve")
        if end - start + 1 > 64 << 20:
            raise _Stop("range_size_limit")
        charge = end - start + 1 + 8192
        if self.state["charged_bytes"] + charge > self.maximum:
            raise _Stop("transfer_budget")
        record = dict(
            url=url.split("?")[0],
            start=start,
            end=end,
            reserved=charge,
            status="pending",
        )
        self.state["requests"].append(record)
        self.state["charged_bytes"] += charge
        _save(self.path, self.state)
        return record

    def finish(self, record, received, status):
        record.update(status=status, received=received)
        # Completed responses refund only known unread payload; pending calls stay charged.
        self.state["charged_bytes"] -= record["reserved"] - (received + 8192)
        self.state["received_bytes"] += received
        _save(self.path, self.state)


class _RemoteFile(io.RawIOBase):
    def __init__(self, session, shard, budget):
        self.budget = budget
        self.session, self.shard, self.position = session, shard, 0
        self.received = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (
            self.position if whence == 1 else self.shard["size"] if whence == 2 else 0
        )
        return self.position

    def read(self, size=-1):
        size = min(
            size if size >= 0 else self.shard["size"],
            self.shard["size"] - self.position,
        )
        if size <= 0:
            return b""
        start, end = self.position, self.position + size - 1
        url = BASE + self.shard["path"] + f"?download=true&range={start}-{end}"
        for redirect in range(5):
            parsed = urlparse(url)
            if parsed.scheme != "https" or not any(
                parsed.hostname == h or (parsed.hostname or "").endswith("." + h)
                for h in ("huggingface.co", "hf.co")
            ):
                raise ValueError("Untrusted range redirect")
            record = self.budget.reserve(url, start, end)
            response = self.session.get(
                url,
                headers={
                    "Range": f"bytes={start}-{end}",
                    "Accept-Encoding": "identity",
                },
                stream=True,
                allow_redirects=False,
                timeout=30,
            )
            try:
                if response.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, response.headers["Location"])
                    self.budget.finish(record, 0, response.status_code)
                    continue
                if (
                    response.status_code != 206
                    or response.headers.get("Content-Range")
                    != f'bytes {start}-{end}/{self.shard["size"]}'
                ):
                    raise ValueError("Server must honor exact byte range")
                if (
                    response.headers.get("Content-Encoding", "identity") != "identity"
                    or int(response.headers.get("Content-Length", size)) != size
                ):
                    raise ValueError("Invalid range encoding/length")
                data = response.raw.read(size)
                if len(data) != size:
                    raise ValueError("Truncated range")
                self.budget.finish(record, len(data), 206)
                break
            finally:
                response.close()
        else:
            raise ValueError("Too many range redirects")
        self.position += size
        self.received += size
        return data


EXCLUDED_HOSTS = (
    "dexonline.ro",
    "dex.ro",
    "dex.md",
    "dexx.ro",
    "wiktionary.org",
    "scrabble.ro",
)


def _empty_counts():
    return dict(tokens=0, counts={}, documents={}, hosts={}, seen=[])


def _observe(row, wanted, state):
    stats = state["stats"]
    stats["examined_documents"] += 1
    if not all(
        isinstance(row.get(k), str) for k in ["text", "url", "date", "language"]
    ):
        stats["invalid_metadata"] += 1
        return
    host = urlparse(row["url"]).hostname
    if not host or urlparse(row["url"]).scheme not in ("http", "https"):
        stats["invalid_metadata"] += 1
        return
    if any(host == h or host.endswith("." + h) for h in EXCLUDED_HOSTS):
        stats["excluded_dictionary"] += 1
        return
    score = row["language_score"]
    if (
        row["language"] != "ron"
        or not isinstance(score, (int, float))
        or not math.isfinite(score)
        or score < 0.8
    ):
        stats["excluded_language"] += 1
        return
    try:
        year = int(row["date"][:4])
    except ValueError:
        stats["invalid_metadata"] += 1
        return
    if not 2013 <= year <= 2024:
        stats["excluded_date"] += 1
        return
    stats["year_" + str(year)] += 1
    slice_name = "primary" if year >= 2020 else "older"
    corpus = state[slice_name]
    normalized = _lexeme(row["text"])
    digest = hashlib.sha256(" ".join(normalized.split()).encode()).hexdigest()
    if digest in corpus["seen"]:
        stats["duplicate"] += 1
        return
    corpus["seen"].add(digest)
    tokens = TOKEN.findall(normalized)
    corpus["tokens"] += len(tokens)
    stats[slice_name + "_documents"] += 1
    hits = Counter(t for t in tokens if t in wanted)
    if slice_name == "primary":
        pending = {
            token for token in hits if len(state["witnesses"].get(token, [])) < 2
        }
        for match in TOKEN.finditer(normalized):
            token = match.group()
            if token in pending:
                state["witnesses"].setdefault(token, []).append(
                    dict(
                        word=token,
                        url=row["url"][:2048],
                        year=year,
                        sha256=digest,
                        context=normalized[
                            max(0, match.start() - 80) : match.start() + 120
                        ],
                    )
                )
                pending.remove(token)
    for token, count in hits.items():
        corpus["counts"][token] += count
        corpus["documents"][token] += 1
        corpus["hosts"][token].add(host)


def _runtime_state():
    return dict(
        stats=Counter(),
        witnesses={},
        primary=dict(
            tokens=0,
            counts=Counter(),
            documents=Counter(),
            hosts=defaultdict(set),
            seen=set(),
        ),
        older=dict(
            tokens=0,
            counts=Counter(),
            documents=Counter(),
            hosts=defaultdict(set),
            seen=set(),
        ),
    )


def _project(vocabulary, corpus, path):
    rows = []
    for item in vocabulary:
        form = _lexeme(item["word"])
        count = corpus["counts"][form]
        rows.append(
            dict(
                word_id=item["word_id"],
                word=item["word"],
                type=item["type"],
                count=count,
                document_count=corpus["documents"][form],
                host_count=len(corpus["hosts"][form]),
                token_total=corpus["tokens"],
                frequency=count / corpus["tokens"] if count else "",
                status="observed" if count else "unobserved",
            )
        )
    _write_csv(path, list(rows[0]), rows)


def _export(
    vocabulary_csv: Path,
    shards_json: Path,
    output_dir: Path,
    *,
    session=None,
    initial_bytes=40 << 20,
    max_bytes=1 << 30,
    max_documents=100000,
    max_group_bytes=128 << 20,
):
    import pyarrow.parquet as pq

    if (
        not 0 <= initial_bytes <= max_bytes <= 1 << 30
        or not 1 <= max_documents <= 100000
    ):
        raise ValueError("Invalid experiment limits")
    shards = json.loads(shards_json.read_text())
    if (
        not isinstance(shards, list)
        or not shards
        or any(
            not isinstance(s, dict)
            or not isinstance(s.get("path"), str)
            or not re.fullmatch(r"data/ron_Latn/train/[0-9_]+\.parquet", s["path"])
            or type(s.get("size")) is not int
            or s["size"] < 8
            for s in shards
        )
        or len({s["path"] for s in shards}) != len(shards)
    ):
        raise ValueError("Invalid or duplicate shard identity")
    if not 1 <= max_group_bytes <= 128 << 20:
        raise ValueError("Invalid decompression limit")
    output_dir.mkdir(exist_ok=True)
    binding = dict(
        vocabulary=_sha256(vocabulary_csv),
        shards=_sha256(shards_json),
        max_bytes=max_bytes,
        initial_bytes=initial_bytes,
        max_documents=max_documents,
        max_group_bytes=max_group_bytes,
        implementation={
            p.name: _sha256(p)
            for p in (
                Path(__file__),
                Path(__file__).with_name("dataset.py"),
                Path(__file__).with_name("definition_frequency.py"),
                Path(__file__).with_name("fineweb_transport.py"),
            )
        },
    )
    budget = _Budget(output_dir / "budget.json", binding, max_bytes, initial_bytes)
    vocabulary = _vocabulary(vocabulary_csv)
    wanted = {_lexeme(r["word"]) for r in vocabulary}
    final = output_dir / "manifest.json"
    if final.exists():
        result = json.loads(final.read_text())
        for name, digest in result["artifacts"].items():
            if Path(name).name != name or _sha256(output_dir / name) != digest:
                raise ValueError("Completed artifact changed")
        if result["stop_reason"] != "disk_reserve":
            return result
        # Invalidate the provisional generation before replacing any projection.
        final.unlink()
    checkpoint = output_dir / "checkpoint.json"
    state = _runtime_state()
    state["next_group"] = 0
    state["sampling"] = []
    if checkpoint.exists():
        saved = json.loads(checkpoint.read_text())
        if (
            saved.get("schema") != 1
            or saved.get("binding") != binding
            or _digest(saved.get("state")) != saved.get("sha256")
        ):
            raise ValueError("Invalid or changed checkpoint")
        state = saved["state"]
        if (
            state["next_group"] != len(state["sampling"])
            or sum(r["examined"] for r in state["sampling"])
            != state["stats"]["examined_documents"]
            or state["stats"]["examined_documents"] > budget.state["reserved_documents"]
        ):
            raise ValueError("Invalid checkpoint progress")
        state["stats"] = Counter(state["stats"])
        for name in ("primary", "older"):
            corpus = state[name]
            corpus["counts"] = Counter(corpus["counts"])
            corpus["documents"] = Counter(corpus["documents"])
            corpus["hosts"] = defaultdict(
                set, {k: set(v) for k, v in corpus["hosts"].items()}
            )
            corpus["seen"] = set(corpus["seen"])
    stop_reason = "source_exhausted"
    try:
        readers = []
        for shard in shards:
            source = _RemoteFile(session, shard, budget)
            readers.append(pq.ParquetFile(source, pre_buffer=False))
        plans = []
        randomizer = random.Random(20261026)
        for index, (shard, parquet) in enumerate(zip(shards, readers)):
            order = list(range(parquet.num_row_groups))
            randomizer.shuffle(order)
            remaining = max_documents // len(shards) + (
                index < max_documents % len(shards)
            )
            local = []
            for group in order:
                if not remaining:
                    break
                row_count = parquet.metadata.row_group(group).num_rows
                take = min(row_count, remaining)
                local.append(
                    dict(
                        shard=shard["path"],
                        shard_index=index,
                        row_group=group,
                        row_group_rows=row_count,
                        selected_rows=take,
                        row_group_selection="seeded permutation; quota prefix",
                        row_selection="leading rows in selected group; sample-only inference",
                    )
                )
                remaining -= take
            plans.append(local)
        plan = []
        for round_index in range(max(map(len, plans), default=0)):
            plan.extend(
                local[round_index] for local in plans if round_index < len(local)
            )
        _save(output_dir / "sample-plan.json", dict(seed=20261026, groups=plan))
        for index, item in enumerate(plan):
            if index < state["next_group"]:
                continue
            parquet = readers[item["shard_index"]]
            metadata = parquet.metadata.row_group(item["row_group"])
            uncompressed = sum(
                metadata.column(c).total_uncompressed_size
                for c in range(metadata.num_columns)
                if metadata.column(c).path_in_schema in COLUMNS
            )
            if uncompressed > max_group_bytes:
                raise _Stop("row_group_memory_limit")
            # A partial group consumes transfer but exposes at most the assigned document quota.
            budget.reserve_documents(item["selected_rows"])
            batches = parquet.iter_batches(
                batch_size=item["selected_rows"],
                row_groups=[item["row_group"]],
                columns=COLUMNS,
                use_threads=False,
            )
            rows = next(batches).to_pylist()
            for row in rows:
                _observe(row, wanted, state)
            state["sampling"].append(dict(item, examined=len(rows)))
            state["next_group"] = index + 1
            _checkpoint(checkpoint, state, binding)
        if state["stats"]["examined_documents"] >= max_documents:
            stop_reason = "document_limit"
    except _Stop as exc:
        stop_reason = str(exc)
    state["stats"]["examined_documents"] += 0
    state["stats"]["balanced_sample"] = state["stats"][
        "examined_documents"
    ] == max_documents and len({r["shard"] for r in state["sampling"]}) == len(shards)
    _write_csv(
        output_dir / "sampling.csv",
        [
            "shard",
            "shard_index",
            "row_group",
            "row_group_rows",
            "selected_rows",
            "row_group_selection",
            "row_selection",
            "examined",
        ],
        state["sampling"],
    )
    _write_csv(
        output_dir / "concordances.csv",
        ["word", "url", "year", "sha256", "context"],
        [
            row
            for token in sorted(state["witnesses"])
            for row in state["witnesses"][token]
        ],
    )
    _project(vocabulary, state["primary"], output_dir / "frequencies.csv")
    _project(vocabulary, state["older"], output_dir / "older-frequencies.csv")
    shutil.copyfile(vocabulary_csv, output_dir / "vocabulary.csv")
    manifest = dict(
        schema=1,
        policy=POLICY,
        vocabulary_sha256=_sha256(vocabulary_csv),
        protocol=dict(
            revision=REVISION,
            primary_years=list(range(2020, 2025)),
            support=dict(count=5, documents=3, hosts=2),
            max_documents=max_documents,
            max_transfer_bytes=max_bytes,
            max_group_uncompressed_bytes=max_group_bytes,
            min_free_disk_bytes=5 << 30,
            seed=20261026,
            language_min_score=0.8,
            excluded_hosts=list(EXCLUDED_HOSTS),
            deduplication="normalized exact text within each temporal slice",
            tokenizer=TOKEN.pattern,
            normalization="NFC; cedilla-to-comma; casefold; exact forms",
            inference="selected sample only; randomized rowgroups with quota prefixes",
            transfer_accounting="HTTP response payload plus8192-byte conservative allowance perrequest; pending reservations never refunded; dependency reserve included; not a TCP/TLS wire meter",
        ),
        counts=dict(
            state["stats"],
            tokens=state["primary"]["tokens"],
            older_tokens=state["older"]["tokens"],
        ),
        budget={k: v for k, v in budget.state.items() if k != "requests"},
        stop_reason=stop_reason,
        artifacts={
            n: _sha256(output_dir / n)
            for n in [
                "vocabulary.csv",
                "frequencies.csv",
                "older-frequencies.csv",
                "sampling.csv",
                "concordances.csv",
            ]
        },
    )
    _save(output_dir / "manifest.json", manifest)
    return manifest


def export_fineweb_frequencies(vocabulary_csv, shards_json, output_dir, **options):
    """Resume one bounded HTTP→CSV campaign; source and limits cannot change."""
    if output_dir.is_symlink():
        raise ValueError("Campaign cannot be a symlink")
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if any(p.is_symlink() for p in output_dir.iterdir()):
            raise ValueError("Campaign artifacts cannot be symlinks")
        if not (output_dir / "budget.json").exists() and any(
            p.name != ".lock" for p in output_dir.iterdir()
        ):
            raise ValueError("Campaign budget missing; refusing reset")
        from .fineweb_transport import HTTP

        owned_transport = options.get("session") is None
        if owned_transport:
            options["session"] = HTTP()
        try:
            return _export(vocabulary_csv, shards_json, output_dir, **options)
        finally:
            if owned_transport:
                options["session"].close()
