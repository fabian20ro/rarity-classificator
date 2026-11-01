"""Frozen offline gate for large downward proposals; never changes operational scores."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ..models import BaseWordRow
from .chat_judge import _evidence as lexical_evidence, missing_definition_pos
from .corola_fallback import _evidence as corola_evidence
from .fineweb_fallback import _evidence as fineweb_evidence, SUPPORT
from .dataset import _lexeme, _sha256, _write_csv
from .judge_comparison import _indexed, _level

POLICY = dict(
    version="exact-form-reduction-gate-v1",
    reduction="baseline minus scored GPT >= 2; all other rows retain baseline",
    lexical="at least one usable sense and no known POS without a definition; source bounded, not exhaustive",
    corpus="FineWeb2 support OR CoRoLa count>=5; exact spelling, no lemma/accent folding",
    fineweb_support=SUPPORT,
    corola_count=5,
    scope="Offline noncommercial research. Attestation is not familiarity or a POS/sense-disambiguated count. No fitted thresholds, labels, models or DB.",
)


def export_reduction_gate(baseline_csv, evidence_csv, gpt_csv, fineweb_dir, corola_dir, output_dir):
    """Export all rows and ablations, failing closed on incomplete/corrupt inputs."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    base = _indexed(baseline_csv, {"word", "baseline_level"})
    gpt = _indexed(gpt_csv, {"word", "status", "rarity_level"})
    if set(base) != set(gpt) or len({r["word"] for r in base.values()}) != len(base):
        raise ValueError("Predictions require every unique exact form")
    for rows, fields in [
        (base, {"word_id", "word", "baseline_level"}),
        (gpt, {"word_id", "word", "status", "rarity_level"}),
    ]:
        if any(set(r) != fields for r in rows.values()):
            raise ValueError("Only label-free CSV columns allowed")
    lexical = lexical_evidence(
        evidence_csv, [BaseWordRow(int(wid), r["word"], "") for wid, r in base.items()]
    )
    fineweb, balanced = fineweb_evidence(fineweb_dir)
    corola = corola_evidence(corola_dir)
    rows = []
    for wid in sorted(base, key=int):
        original, proposal = base[wid], gpt[wid]
        word = original["word"]
        ident = int(wid)
        if ident not in fineweb or ident not in corola:
            raise ValueError("Missing corpus row is not an unobserved form")
        fw, co, lex = fineweb[ident], corola[ident], lexical[ident]
        if word != proposal["word"] or any(_lexeme(word) != _lexeme(r["word"]) for r in (fw, co)):
            raise ValueError("Exact spelling mismatch")
        b = _level(original["baseline_level"])
        if proposal["status"] == "scored":
            g = _level(proposal["rarity_level"])
        elif proposal["status"] == "failed" and proposal["rarity_level"] == "":
            g = None
        else:
            raise ValueError("Invalid native prediction status/level")
        reduction = g is not None and b - g >= 2
        lexical_ok = bool(lex["senses"]) and not missing_definition_pos(lex)
        fw_ok = (
            fw["count"] >= SUPPORT["count"]
            and fw["document_count"] >= SUPPORT["documents"]
            and fw["host_count"] >= SUPPORT["hosts"]
        )
        co_ok = co["count"] >= POLICY["corola_count"]
        corpus_ok = fw_ok or co_ok
        accepted = reduction and lexical_ok and corpus_ok
        reason = (
            "gpt_failed"
            if g is None
            else "not_large_reduction"
            if not reduction
            else "missing_lexical_and_corpus_support"
            if not lexical_ok and not corpus_ok
            else "missing_lexical_support"
            if not lexical_ok
            else "missing_corpus_support"
            if not corpus_ok
            else "accepted"
        )
        rows.append(
            dict(
                word_id=wid,
                word=word,
                baseline_level=b,
                gpt_level=g if g is not None else "",
                gpt_status=proposal["status"],
                gpt_full_level=g if g is not None else b,
                large_reduction=reduction,
                lexical_supported=lexical_ok,
                missing_definition_pos="|".join(missing_definition_pos(lex)),
                fineweb_supported=fw_ok,
                corola_supported=co_ok,
                corpus_supported=corpus_ok,
                fineweb_count=fw["count"],
                fineweb_documents=fw["document_count"],
                fineweb_hosts=fw["host_count"],
                corola_count=co["count"],
                ungated_reduction_level=g if reduction else b,
                lexical_only_level=g if reduction and lexical_ok else b,
                corpus_only_level=g if reduction and corpus_ok else b,
                candidate_level=g if accepted else b,
                reason=reason,
            )
        )
    summary = dict(
        forms=len(rows),
        large_reductions=sum(r["large_reduction"] for r in rows),
        accepted=sum(r["reason"] == "accepted" for r in rows),
        gpt_failed=sum(r["gpt_status"] == "failed" for r in rows),
        fineweb_balanced_sample=balanced,
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".reduction-gate-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        _write_csv(staged / "decisions.csv", list(rows[0]), rows)
        (staged / "policy.json").write_text(json.dumps(POLICY, indent=2) + "\n")
        (staged / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        inputs = [baseline_csv, evidence_csv, gpt_csv]
        for directory in (fineweb_dir, corola_dir):
            inputs += [
                directory / n for n in ("manifest.json", "vocabulary.csv", "frequencies.csv")
            ]
        manifest = dict(
            policy=POLICY["version"],
            inputs={str(p.resolve()): _sha256(p) for p in inputs},
            implementation={
                str(p.resolve()): _sha256(p)
                for p in (
                    Path(__file__),
                    Path(__file__).with_name("chat_judge.py"),
                    Path(__file__).with_name("fineweb_fallback.py"),
                    Path(__file__).with_name("corola_fallback.py"),
                )
            },
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return summary
