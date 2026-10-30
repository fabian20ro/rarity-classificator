"""Project the published CoRoLa word list onto an inventory; research-only CSVs."""

from collections import Counter
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from .dataset import _lexeme, _sha256, _vocabulary, _write_csv


def export_corola_frequencies(
    vocabulary_csv: Path, source_tsv: Path, source_record_json: Path, output_dir: Path
):
    """Retain every ID/POS; sum normalized spelling aliases, never lemma variants."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    vocabulary = _vocabulary(vocabulary_csv)
    source = json.loads(source_record_json.read_text())
    expected = dict(
        record="7091535",
        member="corola_word_freq_all_lowercase.tsv",
        license="cc-by-nc-nd-4.0",
        archive_md5="0034d61d1825b38386dfa0bc2606a314",
    )
    if any(source.get(key) != value for key, value in expected.items()):
        raise ValueError("Wrong CoRoLa release/member/license")
    if (
        source.get("source_sha256") != _sha256(source_tsv)
        or source.get("source_bytes") != source_tsv.stat().st_size
    ):
        raise ValueError("CoRoLa source hash/size mismatch")
    counts = Counter()
    targets = {_lexeme(r["word"]) for r in vocabulary}
    total = 0
    entries = 0
    seen = set()
    with source_tsv.open(encoding="utf-8") as stream:
        for line in stream:
            entries += 1
            word, count = line.rstrip("\n").split("\t")
            if (
                not word
                or any(c.isspace() for c in word)
                or word in seen
                or not count.isascii()
                or not count.isdigit()
                or int(count) <= 0
            ):
                raise ValueError("Invalid or duplicate CoRoLa word/count row")
            seen.add(word)
            count = int(count)
            total += count
            normalized = _lexeme(word)
            if normalized in targets:
                counts[normalized] += count
    if source.get("entries") != entries or total <= 0:
        raise ValueError("CoRoLa entry count mismatch")
    rows = []
    for row in vocabulary:
        count = counts[_lexeme(row["word"])]
        rows.append(
            dict(
                row,
                count=count,
                token_total=total,
                frequency=count / total,
                status="observed" if count else "unobserved",
            )
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".corola-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        shutil.copyfile(vocabulary_csv, staged / "vocabulary.csv")
        _write_csv(
            staged / "frequencies.csv",
            ["word_id", "word", "type", "count", "token_total", "frequency", "status"],
            rows,
        )
        manifest = dict(
            schema=1,
            policy="corola-exact-forms-v1",
            source=source,
            normalization="NFC, cedilla-to-comma, casefold; no lemma or accent folding",
            denominator="sum of published filtered word-list counts",
            implementation_sha256=_sha256(Path(__file__)),
            source_record_sha256=_sha256(source_record_json),
            token_total=total,
            vocabulary_sha256=_sha256(vocabulary_csv),
            artifacts={
                name: _sha256(staged / name) for name in ("vocabulary.csv", "frequencies.csv")
            },
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return manifest
