"""Published word-list to exact-form CSV seam, using tiny synthetic source files."""

import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from classificator.evaluation.corola import export_corola_frequencies


def inputs(root, text="ȘARPE\t3\nşarpe\t2\nșarpe\t1\nsarpe\t7\nșerpi\t11\na\t100\n"):
    source = root / "words.tsv"
    source.write_text(text)
    record = root / "source.json"
    record.write_text(
        json.dumps(
            dict(
                record="7091535",
                member="corola_word_freq_all_lowercase.tsv",
                license="cc-by-nc-nd-4.0",
                archive_md5="0034d61d1825b38386dfa0bc2606a314",
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                source_bytes=source.stat().st_size,
                entries=len(text.splitlines()),
            )
        )
    )
    vocab = root / "vocabulary.csv"
    vocab.write_text("word_id,word,type\n1,șarpe,N\n2,șarpe,A\n3,șerpui,V\n4,sarpe,N\n")
    return vocab, source, record


def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def test_exact_forms_preserve_all_ids_and_use_complete_list_denominator():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        export_corola_frequencies(*inputs(root), root / "out")
        rows = read(root / "out/frequencies.csv")
        assert [r["word_id"] for r in rows] == ["1", "2", "3", "4"]
        assert [r["count"] for r in rows] == ["6", "6", "0", "7"]
        assert {r["token_total"] for r in rows} == {"124"}
        assert float(rows[0]["frequency"]) == 6 / 124
        assert rows[2]["status"] == "unobserved"
        manifest = json.loads((root / "out/manifest.json").read_text())
        assert manifest["source"]["record"] == "7091535"
        assert (
            manifest["vocabulary_sha256"]
            == hashlib.sha256((root / "vocabulary.csv").read_bytes()).hexdigest()
        )


def test_rejects_changed_source_or_wrong_release_before_publication():
    import pytest

    with TemporaryDirectory() as temp:
        root = Path(temp)
        paths = inputs(root)
        original = json.loads(paths[2].read_text())
        for key, value in [
            ("source_sha256", "0" * 64),
            ("source_bytes", 1),
            ("entries", 1),
            ("member", "corola_lemma_freq_all_lowercase.tsv"),
            ("record", "other"),
            ("license", "cc0"),
            ("archive_md5", "0" * 32),
        ]:
            paths[2].write_text(json.dumps(dict(original, **{key: value})))
            with pytest.raises(ValueError):
                export_corola_frequencies(*paths, root / "out")
            assert not (root / "out").exists()


def test_malformed_counts_and_duplicate_source_rows_do_not_publish():
    import pytest

    with TemporaryDirectory() as temp:
        root = Path(temp)
        for text in ["", "a\t0\n", "a\t-1\n", "a\t1.5\n", "a\t2\na\t3\n", "\t3\n", "a b\t2\n"]:
            with pytest.raises(ValueError):
                export_corola_frequencies(*inputs(root, text), root / "out")
            assert not (root / "out").exists()
