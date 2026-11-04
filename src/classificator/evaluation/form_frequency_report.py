"""Development-only, threshold-free comparison on one explicit exact-form target."""

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _frequencies, _lexeme, _read_csv, _sha256, _write_csv
from .exact_form import load_form_contract, RUBRIC_ID
from .definition_frequency import POLICY

REFERENCE_KINDS = {"audited_context_minimum", "shortlist_form_review"}


def _ranks(values):
    positions = {}
    for index, value in enumerate(sorted(values), 1):
        positions.setdefault(value, []).append(index)
    means = {value: sum(indices) / len(indices) for value, indices in positions.items()}
    return [means[value] for value in values]


def _spearman(levels, frequencies):
    if len(levels) < 2:
        return None
    left, right = _ranks([-level for level in levels]), _ranks(frequencies)
    left_mean, right_mean = sum(left) / len(left), sum(right) / len(right)
    covariance = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((a - left_mean) ** 2 for a in left) * sum((b - right_mean) ** 2 for b in right)
    )
    return covariance / denominator if denominator else None


def _metrics(rows, source):
    present = [r for r in rows if r[source] is not None]
    by_level = {
        str(level): dict(
            total=sum(r["level"] == level for r in rows),
            covered=sum(r["level"] == level for r in present),
        )
        for level in range(1, 6)
    }
    concordant = discordant = tied = 0
    for i, a in enumerate(present):
        for b in present[i + 1 :]:
            if a["level"] == b["level"]:
                continue
            direction = (a["level"] - b["level"]) * (a[source] - b[source])
            concordant += direction < 0
            discordant += direction > 0
            tied += direction == 0
    return dict(
        covered=len(present),
        missing=len(rows) - len(present),
        coverage_by_level=by_level,
        spearman_familiarity=_spearman([r["level"] for r in present], [r[source] for r in present]),
        ordered_pairs=dict(concordant=concordant, discordant=discordant, tied_frequency=tied),
    )


def compare_form_frequencies(
    reference_csv: Path, forms_csv: Path, wordfreq_csv: Path, rebus_csv: Path, output_dir: Path
):
    """Compare ranks, not fitted levels. Validate identities and frozen corpus digests."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    reference = _read_csv(
        reference_csv,
        {"word_id", "word", "working_level", "reference_kind", "coverage_status", "witness"},
    )
    inventory = {int(r["word_id"]): r["word"] for r in reference}
    if not inventory or len(inventory) != len(reference) or min(inventory) <= 0:
        raise ValueError("Reference requires unique positive IDs")
    load_form_contract(forms_csv, inventory)
    for row in reference:
        if row["reference_kind"] not in REFERENCE_KINDS | {"initial_opaque_form_pos"}:
            raise ValueError("Unknown reference kind")
        if int(row["working_level"]) not in range(1, 6):
            raise ValueError("Reference level must be 1..5")
    metadata_path = wordfreq_csv.with_suffix(wordfreq_csv.suffix + ".metadata.json")
    metadata = json.loads(metadata_path.read_text())
    if any(
        metadata.get(k) != v
        for k, v in dict(
            schema_version=1, package="wordfreq", language="ro", wordlist="best"
        ).items()
    ) or not metadata.get("package_version"):
        raise ValueError("Expected versioned Romanian wordfreq best-list export")
    if metadata["frequencies_sha256"] != _sha256(wordfreq_csv):
        raise ValueError("wordfreq hash mismatch")
    rebus_manifest_path = rebus_csv.parent / "manifest.json"
    rebus_manifest = json.loads(rebus_manifest_path.read_text())
    if rebus_manifest.get("schema") != 1 or rebus_manifest.get("policy") != POLICY:
        raise ValueError("Incompatible rebus extraction policy")
    ledger_path = rebus_csv.parent / "source-files.csv"
    if rebus_manifest["artifacts"].get("source-files.csv") != _sha256(ledger_path):
        raise ValueError("Rebus source ledger hash mismatch")
    if rebus_manifest["artifacts"][rebus_csv.name] != _sha256(rebus_csv):
        raise ValueError("Rebus hash mismatch")
    wordfreq = _frequencies(wordfreq_csv)
    rebus = {}
    for row in _read_csv(
        rebus_csv,
        {"word_id", "word", "count", "document_count", "token_total", "frequency", "status"},
    ):
        word_id = int(row["word_id"])
        if word_id in rebus or inventory.get(word_id) != row["word"]:
            raise ValueError("Rebus identity mismatch")
        count, total, docs = int(row["count"]), int(row["token_total"]), int(row["document_count"])
        if total <= 0 or not 0 <= docs <= count <= total:
            raise ValueError("Invalid rebus counts")
        if row["status"] != ("observed" if count else "unobserved"):
            raise ValueError("Rebus status/count mismatch")
        value = float(row["frequency"]) if row["frequency"] else None
        if (count and (value is None or not math.isclose(value, count / total))) or (
            not count and value is not None
        ):
            raise ValueError("Rebus frequency/count mismatch")
        rebus[word_id] = dict(frequency=value, count=count, document_count=docs)
    if rebus.keys() != inventory.keys():
        raise ValueError("Rebus must cover reference inventory, including absences")
    rows = []
    for row in reference:
        if row["reference_kind"] not in REFERENCE_KINDS:
            continue
        word_id = int(row["word_id"])
        rows.append(
            dict(
                word_id=word_id,
                word=row["word"],
                level=int(row["working_level"]),
                reference_kind=row["reference_kind"],
                coverage_status=row["coverage_status"],
                witness=row["witness"],
                wordfreq=wordfreq.get(_lexeme(row["word"])) or None,
                rebus=rebus[word_id]["frequency"],
                rebus_count=rebus[word_id]["count"],
                rebus_document_count=rebus[word_id]["document_count"],
            )
        )
    if not rows:
        raise ValueError("No clarified-target reference labels")
    paired = [r for r in rows if r["wordfreq"] is not None and r["rebus"] is not None]
    result = dict(
        rubric=RUBRIC_ID,
        split="dev",
        reference_count=len(rows),
        excluded_opaque_count=len(reference) - len(rows),
        wordfreq=_metrics(rows, "wordfreq"),
        rebus=_metrics(rows, "rebus"),
        paired=dict(
            count=len(paired),
            wordfreq_spearman=_metrics(paired, "wordfreq")["spearman_familiarity"],
            rebus_spearman=_metrics(paired, "rebus")["spearman_familiarity"],
        ),
        limitations=[
            "Selected single-rater development labels, some after AI exposure.",
            "Coverage is source-bounded; only 1 reaches the absolute numerical floor.",
            "Missing frequency abstains; no level5 imputation, no thresholds fitted.",
            "Dictionary frequency is not general-language familiarity; correlations are descriptive.",
        ],
    )
    for source in ("wordfreq", "rebus"):
        present = [r for r in rows if r[source] is not None]
        for row, rank in zip(present, _ranks([-r[source] for r in present])):
            row[source + "_rank"] = rank
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".comparison-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        fields = list(rows[0])
        fields = list(dict.fromkeys(fields + ["wordfreq_rank", "rebus_rank"]))
        _write_csv(
            staged / "comparison.csv",
            fields,
            [{k: "" if v is None else v for k, v in r.items()} for r in rows],
        )
        (staged / "summary.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
        inputs = [
            ledger_path,
            reference_csv,
            forms_csv,
            wordfreq_csv,
            metadata_path,
            rebus_csv,
            rebus_manifest_path,
        ]
        manifest = dict(
            schema=1,
            inputs={str(p.resolve()): _sha256(p) for p in inputs},
            implementation={p.name: _sha256(p) for p in Path(__file__).parent.glob("*.py")},
            artifacts={name: _sha256(staged / name) for name in ("comparison.csv", "summary.json")},
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return result
