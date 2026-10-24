"""Offline preparation and evaluation commands, separate from production upload."""

import json
import hashlib
import os
from argparse import Namespace
from pathlib import Path

from .dataset import prepare_dataset
from .campaign import run_campaign
from ..run_csv_repository import RunCsvRepository
from ..csv_codec import CsvCodec
from ..scoring.d1 import D1Scorer, RUBRIC, INSTRUCTIONS


def add_commands(sub) -> None:
    forms = sub.add_parser(
        "evaluation-exact-forms", help="Freeze exact surfaces and all source-attested POS"
    )
    forms.add_argument("--vocabulary-csv", type=Path, required=True)
    forms.add_argument("--loc-file", type=Path, required=True)
    forms.add_argument("--contexts-csv", type=Path, required=True)
    forms.add_argument("--campaign-dir", type=Path, required=True)
    forms.set_defaults(evaluation_handler=_exact_forms)
    rebus = sub.add_parser(
        "evaluation-rebus", help="Count exact tokens in local rebus definitions; no network"
    )
    rebus.add_argument("--vocabulary-csv", type=Path, required=True)
    rebus.add_argument("--dex-cache", type=Path, required=True)
    rebus.add_argument("--campaign-dir", type=Path, required=True)
    rebus.set_defaults(evaluation_handler=_rebus)
    form_report = sub.add_parser(
        "evaluation-form-report", help="Development-only exact-form frequency rank comparison"
    )
    form_report.add_argument("--reference-csv", type=Path, required=True)
    form_report.add_argument("--form-contract-csv", type=Path, required=True)
    form_report.add_argument("--wordfreq-csv", type=Path, required=True)
    form_report.add_argument("--rebus-csv", type=Path, required=True)
    form_report.add_argument("--campaign-dir", type=Path, required=True)
    form_report.set_defaults(evaluation_handler=_form_report)
    prepare = sub.add_parser(
        "evaluation-prepare", help="Freeze Scrabble vocabulary and offline evidence"
    )
    prepare.add_argument("--vocabulary-csv", type=Path, required=True)
    prepare.add_argument("--campaign-dir", type=Path, required=True)
    prepare.add_argument("--source-version", required=True)
    prepare.add_argument("--seed", type=int, default=0)
    prepare.add_argument("--dex-cache", type=Path)
    prepare.add_argument("--frequencies-csv", type=Path)
    prepare.set_defaults(evaluation_handler=_prepare)
    run = sub.add_parser(
        "evaluation-run", help="Sequential D1 campaign; requires already loaded model"
    )
    run.add_argument("--vocabulary-csv", type=Path, required=True)
    run.add_argument("--campaign-dir", type=Path, required=True)
    run.add_argument("--evidence-csv", type=Path)
    run.add_argument(
        "--form-contract-csv",
        type=Path,
        help="Exact surface/all-POS contract, separate from labels",
    )
    run.add_argument("--model", required=True)
    run.add_argument("--run", help="Stable run identity; defaults to campaign directory name")
    run.add_argument("--model-file", type=Path, required=True)
    run.add_argument("--runtime-version", required=True)
    run.add_argument("--base-url", default="http://127.0.0.1:1234")
    run.add_argument("--min-probability", type=float, default=0.0)
    run.add_argument("--retry-failed", action="store_true")
    run.set_defaults(evaluation_handler=_run)
    report = sub.add_parser(
        "evaluation-report", help="Evaluate held-out labels including missing predictions"
    )
    report.add_argument("--labels-csv", type=Path, required=True)
    report.add_argument("--predictions-csv", type=Path, required=True)
    report.add_argument("--baseline-csv", type=Path)
    report.add_argument("--report", type=Path, required=True)
    report.add_argument("--split", choices=["dev", "calibration", "test"], default="test")
    report.add_argument("--bootstrap-samples", type=int, default=200)
    report.add_argument("--seed", type=int, default=0)
    report.set_defaults(evaluation_handler=_report)
    frequency = sub.add_parser("evaluation-frequency", help="Offline frequency threshold baseline")
    frequency.add_argument("--vocabulary-csv", type=Path, required=True)
    frequency.add_argument("--evidence-csv", type=Path, required=True)
    frequency.add_argument("--campaign-dir", type=Path, required=True)
    frequency.add_argument(
        "--thresholds",
        required=True,
        help="Four descending proportions, comma separated; fit on dev only",
    )
    frequency.set_defaults(evaluation_handler=_frequency)
    wordfreq = sub.add_parser(
        "evaluation-wordfreq", help="Export optional local Romanian wordfreq evidence"
    )
    wordfreq.add_argument("--vocabulary-csv", type=Path, required=True)
    wordfreq.add_argument("--output-csv", type=Path, required=True)
    wordfreq.set_defaults(evaluation_handler=_wordfreq)
    freeze = sub.add_parser("evaluation-freeze-wordfreq", help="Freeze complete offline wordfreq model from working labels")
    freeze.add_argument("--vocabulary-csv", type=Path, required=True)
    freeze.add_argument("--reference-csv", type=Path, required=True)
    freeze.add_argument("--wordfreq-csv", type=Path, required=True)
    freeze.add_argument("--campaign-dir", type=Path, required=True)
    freeze.set_defaults(evaluation_handler=_freeze_wordfreq)
    score = sub.add_parser("evaluation-score-wordfreq", help="Complete shadow CSV from frozen wordfreq model; no DB or LLM")
    score.add_argument("--vocabulary-csv", type=Path, required=True)
    score.add_argument("--wordfreq-csv", type=Path, required=True)
    score.add_argument("--model-json", type=Path, required=True)
    score.add_argument("--campaign-dir", type=Path, required=True)
    score.set_defaults(evaluation_handler=_score_wordfreq)



def _prepare(args) -> int:
    result = prepare_dataset(
        args.vocabulary_csv,
        args.campaign_dir,
        source_version=args.source_version,
        seed=args.seed,
        dex_cache=args.dex_cache,
        frequencies_csv=args.frequencies_csv,
    )
    print(json.dumps(result, default=str, ensure_ascii=False, indent=2))
    return 0


def _hash_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _run(args) -> int:
    items = RunCsvRepository().load_base_rows(args.vocabulary_csv)
    evidence = {}
    if args.evidence_csv:
        inventory_ids = {item.word_id for item in items}
        table = CsvCodec().read_table(args.evidence_csv)
        allowed_fields = {
            "word_id",
            "frequency",
            "frequency_present",
            "definition",
            "definition_status",
        }
        if not set(table.headers) <= allowed_fields:
            raise ValueError(
                "Unexpected evidence columns; gold labels must never enter model state"
            )
        if "word_id" not in table.headers or len(set(table.headers)) != len(table.headers):
            raise ValueError("Evidence requires unique headers and word_id")
        for record in table.records:
            row = dict(zip(table.headers, record.values))
            word_id = int(row.pop("word_id"))
            if word_id in evidence or word_id not in inventory_ids:
                raise ValueError("Duplicate or unknown evidence word_id")
            evidence[word_id] = row
    form_contract_path = getattr(args, "form_contract_csv", None)
    form_contract = None
    if form_contract_path:
        from .exact_form import load_form_contract

        form_contract = load_form_contract(
            form_contract_path, {item.word_id: item.word for item in items}
        )
    config = {
        "form_contract_sha256": _hash_file(form_contract_path) if form_contract_path else None,
        "target": "exact-form-most-familiar-valid-sense-v1",
        "run_slug": (getattr(args, "run", None) or args.campaign_dir.name),
        "model": args.model,
        "model_file_sha256": _hash_file(args.model_file),
        "runtime_version": args.runtime_version,
        "backend": "d1-systemone",
        "vocabulary_sha256": _hash_file(args.vocabulary_csv),
        "evidence_sha256": _hash_file(args.evidence_csv) if args.evidence_csv else None,
        "rubric": RUBRIC,
        "instructions": INSTRUCTIONS,
        "base_url": args.base_url,
        "min_probability": args.min_probability,
        "policy": "argmax-v1",
        "confidence_semantics": "maximum class probability; not calibrated correctness",
    }
    scorer = D1Scorer(
        model=args.model,
        base_url=args.base_url,
        evidence=evidence,
        form_contract=form_contract,
        min_probability=args.min_probability,
    )
    api_key = os.getenv("LMSTUDIO_API_KEY")
    if api_key:
        scorer.http.headers.update({"Authorization": "Bearer " + api_key})
    config["loaded_model"] = scorer.preflight()
    path = run_campaign(
        items, scorer, args.campaign_dir, config=config, retry_failed=args.retry_failed
    )
    print(path)
    summary = json.loads((args.campaign_dir / "summary.json").read_text())
    print(json.dumps(summary, indent=2))
    return 1 if summary["failed"] or summary["pending"] else 0


def run_step2_d1(args) -> int:
    if args.force or args.skip_preflight or args.endpoint or args.input or args.limit:
        raise ValueError(
            "D1 Step2 requires a frozen base CSV; force, skip-preflight, endpoint, input and limit are unsupported. Use a separate inventory/campaign and evaluation-run --retry-failed."
        )
    if args.dry_run:
        items = RunCsvRepository().load_base_rows(Path(args.base_csv))
        print(f"D1 dry-run: {len(items)} words; sequential requests; no model access")
        return 0
    if args.model_file is None or not args.runtime_version:
        raise ValueError("D1 requires --model-file and --runtime-version for reproducibility")
    output = Path(args.output_csv)
    campaign_dir = output.with_name(output.name + ".campaign")
    if output.exists() and not (campaign_dir / "manifest.json").exists():
        raise ValueError("Refusing to replace an existing output without a matching D1 campaign")
    run_args = Namespace(**vars(args))
    run_args.vocabulary_csv = Path(args.base_csv)
    run_args.campaign_dir = campaign_dir
    run_args.base_url = args.base_url or "http://127.0.0.1:1234"
    run_args.retry_failed = False
    code = _run(run_args)
    table = CsvCodec().read_table(campaign_dir / "run.csv")
    CsvCodec().write_table_atomic(output, table.headers, [row.values for row in table.records])
    print(output)
    return code


def _report(args) -> int:
    from .report import evaluate_predictions

    if args.report.exists():
        raise ValueError("Report already exists; choose a new path")
    result = evaluate_predictions(
        args.labels_csv,
        args.predictions_csv,
        split=args.split,
        baseline_csv=args.baseline_csv,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(args.report)
    return 0


def _frequency(args) -> int:
    from ..scoring.frequency import FrequencyScorer

    items = RunCsvRepository().load_base_rows(args.vocabulary_csv)
    table = CsvCodec().read_table(args.evidence_csv)
    if not {"word_id", "frequency", "frequency_present"} <= set(table.headers):
        raise ValueError("Evidence requires word_id, frequency and frequency_present")
    frequencies = {}
    allowed = {item.word_id for item in items}
    for record in table.records:
        row = dict(zip(table.headers, record.values))
        word_id = int(row["word_id"])
        if word_id in frequencies or word_id not in allowed:
            raise ValueError("Duplicate or unknown frequency word_id")
        presence = row["frequency_present"].lower()
        if presence not in {"true", "false", "1", "0"}:
            raise ValueError("frequency_present must be true or false")
        frequencies[word_id] = float(row["frequency"]) if presence in {"true", "1"} else None
    thresholds = tuple(float(value) for value in args.thresholds.split(","))
    scorer = FrequencyScorer(frequencies, thresholds=thresholds)
    config = {
        "model": "frequency-baseline",
        "thresholds": thresholds,
        "vocabulary_sha256": _hash_file(args.vocabulary_csv),
        "evidence_sha256": _hash_file(args.evidence_csv),
    }
    print(run_campaign(items, scorer, args.campaign_dir, config=config))
    return 0


def _wordfreq(args) -> int:
    from .wordfreq_source import export_wordfreq

    result = export_wordfreq(args.vocabulary_csv, args.output_csv)
    print(json.dumps(result, default=str, ensure_ascii=False, indent=2))
    return 0


def _exact_forms(args):
    from .exact_form import prepare_exact_forms

    result = prepare_exact_forms(
        args.vocabulary_csv, args.loc_file, args.contexts_csv, args.campaign_dir
    )
    print(json.dumps(result, default=str, indent=2))
    return 0


def _rebus(args):
    from .definition_frequency import export_rebus_frequencies

    result = export_rebus_frequencies(args.vocabulary_csv, args.dex_cache, args.campaign_dir)
    print(json.dumps(result, default=str, indent=2))
    return 0


def _form_report(args):
    from .form_frequency_report import compare_form_frequencies

    result = compare_form_frequencies(
        args.reference_csv,
        args.form_contract_csv,
        args.wordfreq_csv,
        args.rebus_csv,
        args.campaign_dir,
    )
    print(json.dumps(result, indent=2))
    return 0


def _freeze_wordfreq(args) -> int:
    from .wordfreq_baseline import freeze_wordfreq_model

    result = freeze_wordfreq_model(args.vocabulary_csv, args.reference_csv, args.wordfreq_csv, args.campaign_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _score_wordfreq(args) -> int:
    from .wordfreq_baseline import score_wordfreq_inventory

    result = score_wordfreq_inventory(args.vocabulary_csv, args.wordfreq_csv, args.model_json, args.campaign_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
