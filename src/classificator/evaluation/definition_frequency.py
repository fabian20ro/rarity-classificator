"""Local rebus definition corpus; exact tokens, no network or model access."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _DefinitionText, _game_key, _lexeme, _sha256, _vocabulary, _write_csv

POLICY = "rebus-definition-tokens-exclude-pilot-pages-v1"
# Keep hyphenated/apostrophe-bound forms intact; no synthetic component matches.
TOKEN = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", re.UNICODE)


def export_rebus_frequencies(vocabulary_csv: Path, cache: Path, output_dir: Path):
    """Stream cache files; deduplicate definition bodies, excluding all target game keys.

    Word frequencies pool uses across POS. Zero observations are missing evidence,
    not an inferred familiarity class. This is a dictionary corpus, not general usage.
    """
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    implementation = {
        p.name: _sha256(p) for p in (Path(__file__), Path(__file__).with_name("dataset.py"))
    }
    vocabulary = _vocabulary(vocabulary_csv)
    wanted = {_lexeme(row["word"]) for row in vocabulary}
    excluded = {_game_key(row["word"]) for row in vocabulary}
    paths = sorted(cache.glob("*.json"))
    if not paths:
        raise ValueError("Rebus cache must contain JSON records")
    counts, documents, stats = Counter(), Counter(), Counter()
    seen, sources = set(), []
    total = 0
    for path in paths:
        raw = path.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict) or any(
            not isinstance(payload.get(k), str) for k in ("word", "original", "status", "html")
        ):
            raise ValueError(f"Invalid cache record: {path}")
        if not payload["original"].strip() or not payload["status"].strip():
            raise ValueError(f"Empty cache identity/status: {path}")
        if _game_key(payload["word"]) != _game_key(payload["original"]):
            raise ValueError(f"Cache word/original mismatch: {path}")
        digest = hashlib.sha256(raw).hexdigest()
        status = "used"
        if _game_key(payload["original"]) in excluded:
            status = "excluded_target_pages"
        elif payload["status"] != "ok":
            status = "non_ok_pages"
        else:
            parser = _DefinitionText()
            parser.feed(payload["html"])
            parser.close()
            # Same definition-span selection policy as dataset preparation.
            parts = parser.tree or parser.raw
            bodies = [" ".join("".join(p).split()) for p in parts]
            if not bodies and not parser.full_page:
                bodies = [parser.text()]
            if not any(bodies):
                status = "empty_pages"
            page_words = set()
            for text in bodies:
                normalized = _lexeme(text)
                body_hash = hashlib.sha256(normalized.encode()).digest()
                if body_hash in seen:
                    stats["duplicate_definitions"] += 1
                    continue
                seen.add(body_hash)
                tokens = TOKEN.findall(normalized)
                total += len(tokens)
                stats["unique_definitions"] += 1
                relevant = [token for token in tokens if token in wanted]
                counts.update(relevant)
                page_words.update(relevant)
            documents.update(page_words)
        stats[status] += 1
        sources.append(dict(file=path.name, sha256=digest, disposition=status))
    if not total:
        raise ValueError("No usable definition tokens after target-page exclusion")
    rows = [
        dict(
            word_id=row["word_id"],
            word=row["word"],
            count=counts[_lexeme(row["word"])],
            document_count=documents[_lexeme(row["word"])],
            token_total=total,
            frequency=counts[_lexeme(row["word"])] / total if counts[_lexeme(row["word"])] else "",
            status="observed" if counts[_lexeme(row["word"])] else "unobserved",
        )
        for row in vocabulary
    ]
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".rebus-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        _write_csv(staged / "frequencies.csv", list(rows[0]), rows)
        _write_csv(staged / "source-files.csv", ["file", "sha256", "disposition"], sources)
        manifest = dict(
            schema=1,
            implementation=implementation,
            policy=POLICY,
            vocabulary_sha256=_sha256(vocabulary_csv),
            cache_path=str(cache.resolve()),
            counts=dict(stats, files=len(paths), tokens=total),
            normalization="NFC, cedilla-to-comma, casefold; no lemma/diacritic folding",
            tokenizer=TOKEN.pattern,
            deduplication="global normalized exact definition body",
            limitation="Lexicographic corpus; redirects and overlapping nonidentical definitions remain.",
            artifacts={
                name: _sha256(staged / name) for name in ("frequencies.csv", "source-files.csv")
            },
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return dict(frequencies=output_dir / "frequencies.csv", **manifest["counts"])
