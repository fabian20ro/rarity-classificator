"""Frozen complete wordfreq baseline: explicit offline CSV fit and scoring stages."""

from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import median_low
from tempfile import TemporaryDirectory

from .dataset import _frequencies, _lexeme, _read_csv, _sha256, _vocabulary, _write_csv
from .form_frequency_report import REFERENCE_KINDS
from ..models import BaseWordRow
from ..scoring.frequency import FrequencyScorer

POLICY = "wordfreq-exact-form-complete-v1"
LOOKUP = "exact-nfc-cedilla-casefold-v1"
SOURCE_FIELDS = (
    "package",
    "package_version",
    "language",
    "wordlist",
    "lookup_policy",
    "corpus_sha256",
)


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def _absent(path):
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)


def _source(vocabulary_csv, frequency_csv, rows):
    metadata_path = frequency_csv.with_suffix(frequency_csv.suffix + ".metadata.json")
    metadata = json.loads(metadata_path.read_text())
    expected = dict(
        schema_version=1, package="wordfreq", language="ro", wordlist="best", lookup_policy=LOOKUP
    )
    corpus = metadata.get("corpus_sha256", "")
    if any(metadata.get(k) != v for k, v in expected.items()) or not metadata.get(
        "package_version"
    ):
        raise ValueError("Expected versioned exact Romanian wordfreq export")
    if (
        not isinstance(corpus, str)
        or len(corpus) != 64
        or any(c not in "0123456789abcdef" for c in corpus)
    ):
        raise ValueError("Missing corpus identity")
    if metadata.get("vocabulary_sha256") != _sha256(vocabulary_csv) or metadata.get(
        "inventory_count"
    ) != len(rows):
        raise ValueError("Frequency export must cover this exact inventory, not a subset")
    if metadata.get("frequencies_sha256") != _sha256(frequency_csv):
        raise ValueError("Frequency export hash mismatch")
    frequencies = _frequencies(frequency_csv)
    inventory_forms = {_lexeme(r["word"]) for r in rows}
    if (
        metadata.get("exported_count") != len(frequencies)
        or not frequencies.keys() <= inventory_forms
    ):
        raise ValueError("Frequency rows/count do not match inventory export")
    if any(v <= 0 for v in frequencies.values()):
        raise ValueError("Observed export frequencies must be positive")
    return frequencies, {k: metadata[k] for k in SOURCE_FIELDS}, metadata_path


def _publish(output_dir, files, inputs, fitting=False):
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".wordfreq-baseline-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        for name, content in files.items():
            if name.endswith(".csv"):
                _write_csv(staged / name, list(content[0]), content)
            else:
                (staged / name).write_text(
                    json.dumps(content, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
        code = [
            Path(__file__),
            Path(__file__).with_name("dataset.py"),
            Path(__file__).parents[1] / "scoring/frequency.py",
        ]
        if fitting:
            code.append(Path(__file__).with_name("frequency_calibration.py"))
        manifest = dict(
            inputs={str(p.resolve()): _sha256(p) for p in inputs},
            implementation={str(p.resolve()): _sha256(p) for p in code},
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
            database_writes=0,
            model_requests=0,
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        _absent(output_dir)
        staged.rename(output_dir)


def freeze_wordfreq_model(
    pilot_csv: Path, reference_csv: Path, frequency_csv: Path, output_dir: Path
):
    """Fit latest working labels, pin source/config; training fit is not validation."""
    from .frequency_calibration import _fit

    _absent(output_dir)
    pilot = _vocabulary(pilot_csv)
    vocabulary = {int(r["word_id"]): r["word"] for r in pilot}
    references = _read_csv(reference_csv, {"word_id", "word", "working_level", "reference_kind"})
    labels, kinds = {}, Counter()
    for r in references:
        i, level = int(r["word_id"]), int(r["working_level"])
        if i in labels or vocabulary.get(i) != r["word"] or level not in range(1, 6):
            raise ValueError("Reference must uniquely match pilot identities and levels1..5")
        if r["reference_kind"] not in REFERENCE_KINDS | {"initial_opaque_form_pos"}:
            raise ValueError("Unknown label provenance")
        labels[i] = level
        kinds[r["reference_kind"]] += 1
    if labels.keys() != vocabulary.keys() or len(labels) < 3:
        raise ValueError("Reference must cover the entire pilot, at least three forms")
    frequencies, source, metadata_path = _source(pilot_csv, frequency_csv, pilot)
    observed = [
        (frequencies[_lexeme(word)], labels[i])
        for i, word in vocabulary.items()
        if _lexeme(word) in frequencies
    ]
    missing = [i for i, word in vocabulary.items() if _lexeme(word) not in frequencies]
    fit = _fit(observed) if observed else None
    if fit:
        fit["objective"] = (
            "minimum ordinal MAE on observed latest working labels; training fit only"
        )
    global_level = int(median_low(labels.values()))
    inputs = [pilot_csv, reference_csv, frequency_csv, metadata_path]
    model = dict(
        schema=1,
        policy=POLICY,
        source=source,
        target="exact form through most familiar valid sense across all valid POS",
        label_view="revised_working",
        reference_kind_counts=dict(kinds),
        training_ids=sorted(labels),
        threshold_fit=fit,
        fallback=dict(
            missing_level=int(median_low(labels[i] for i in missing)) if missing else global_level,
            missing_basis="missing_group_median" if missing else "global_median",
            missing_train_ids=missing,
            global_level=global_level,
        ),
        training_inputs={str(p.resolve()): _sha256(p) for p in inputs},
        limitations=[
            "Selected single-rater development pilot, mixed label provenance.",
            "Missingness is censored corpus evidence, not proof of rarity.",
            "All-pilot fit is deployment preparation, not a validation result.",
        ],
    )
    model["model_version"] = _digest(model)
    _publish(output_dir, {"model.json": model}, inputs, fitting=True)
    return model


def _model(path):
    model = json.loads(path.read_text())
    content = {k: v for k, v in model.items() if k != "model_version"}
    if (
        model.get("schema") != 1
        or model.get("policy") != POLICY
        or model.get("model_version") != _digest(content)
    ):
        raise ValueError("Unsupported or modified frozen model")
    fallback = model["fallback"]
    for field in ("missing_level", "global_level"):
        if type(fallback[field]) is not int or fallback[field] not in range(1, 6):
            raise ValueError("Fallback levels must be integers1..5")
    if fallback["missing_basis"] not in {"missing_group_median", "global_median"}:
        raise ValueError("Unknown fallback route")
    if model["threshold_fit"] is not None:
        FrequencyScorer({}, thresholds=tuple(model["threshold_fit"]["thresholds"]))
    return model


def score_wordfreq_inventory(
    inventory_csv: Path, frequency_csv: Path, model_json: Path, output_dir: Path
):
    """Score every inventory ID from a frozen config and evidence; never refit or connect."""
    _absent(output_dir)
    model = _model(model_json)
    inventory = _vocabulary(inventory_csv)
    frequencies, source, metadata_path = _source(inventory_csv, frequency_csv, inventory)
    if source != model["source"]:
        raise ValueError("Source corpus/version/policy differs from frozen model")
    values = {int(r["word_id"]): frequencies.get(_lexeme(r["word"])) for r in inventory}
    fit, fallback = model["threshold_fit"], model["fallback"]
    levels = {}
    if fit is not None:
        scorer = FrequencyScorer(values, thresholds=tuple(fit["thresholds"]))
        items = [BaseWordRow(int(r["word_id"]), r["word"], r["type"]) for r in inventory]
        levels = {o.word_id: o.rarity_level for o in scorer.score_batch(items)}
    rows = []
    for r in inventory:
        i = int(r["word_id"])
        direct = levels.get(i)
        if direct is not None:
            level, route = direct, "frequency_thresholds"
        elif values[i] is not None:
            level, route = fallback["global_level"], "global_median_no_thresholds"
        else:
            level, route = fallback["missing_level"], fallback["missing_basis"]
        rows.append(
            dict(
                word_id=i,
                word=r["word"],
                type=r["type"],
                rarity_level=level,
                frequency=values[i],
                route=route,
                model_version=model["model_version"],
            )
        )

    def summarize(selected):
        return dict(
            total=len(selected),
            routes=dict(Counter(r["route"] for r in selected)),
            levels=dict(sorted(Counter(str(r["rarity_level"]) for r in selected).items())),
        )

    summary = dict(
        **summarize(rows),
        unique_forms=len({_lexeme(r["word"]) for r in rows}),
        model_version=model["model_version"],
        mode="offline_shadow_no_upload",
        by_pos={
            pos: summarize([r for r in rows if r["type"] == pos])
            for pos in sorted({r["type"] for r in rows})
        },
        by_length={
            name: summarize([r for r in rows if lo <= len(_lexeme(r["word"])) <= hi])
            for name, lo, hi in [("1-3", 1, 3), ("4-7", 4, 7), ("8+", 8, float("inf"))]
        },
        calibration_note="Full-inventory distribution is not accuracy validation.",
    )
    _publish(
        output_dir,
        {"scores.csv": rows, "summary.json": summary, "model.json": model},
        [inventory_csv, frequency_csv, metadata_path, model_json],
    )
    return summary
