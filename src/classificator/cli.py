from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_OUTLIER_THRESHOLD,
    DEFAULT_REBALANCE_BATCH_SIZE,
    DEFAULT_REBALANCE_LOWER_RATIO,
    DEFAULT_REBALANCE_TRANSITIONS,
    DEFAULT_TIMEOUT_SECONDS,
    ensure_output_dir,
)
from .lm.client import LmStudioClient
from .run_csv_repository import RunCsvRepository
from .step2_metrics import Step2Metrics
from .steps.step1_export import Step1Options, run_step1
from .steps.step2_score import Step2Options, run_step2
from .steps.step3_compare import Step3Options, run_step3
from .steps.step4_upload import Step4Options, run_step4
from .steps.step5_rebalance import Step5Options, run_step5
from .tools.build_retry_input import build_retry_input
from .tools.chain_rebalance_target_dist import ChainOptions, run_chain_rebalance
from .tools.quality_audit import run_quality_audit
from .tools.rarity_distribution import run_rarity_distribution
from .tools.review_low_confidence import parse_only_levels, run_l1_review_check, run_review_low_confidence
from .transitions import (
    LevelTransition,
    parse_transitions,
    require_valid_pair_transition,
    require_valid_transition,
    validate_transition_set,
)
from .upload_marker_writer import UploadMarkerWriter
from .word_store import WordStore
from .models import Step3MergeStrategy, UploadMode


def main(argv: list[str] | None = None) -> int:
    """Entry point for the classificator CLI. Handles subcommand routing and orchestration."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 2

    output_dir = ensure_output_dir(Path(args.output_dir))
    repo = RunCsvRepository()

    if args.command in {"step1-export", "step1"}:
        store = WordStore()
        run_step1(Step1Options(output_csv_path=Path(args.output_csv)), word_store=store, repo=repo)
        return 0

    if args.command in {"step2-score", "step2"}:
        metrics = Step2Metrics()
        lm_client = LmStudioClient(api_key=os.getenv("LMSTUDIO_API_KEY"), metrics=metrics)

        if args.dry_run:
            source_csv = Path(args.input) if args.input else Path(args.base_csv)
            pending_count = _count_pending(source_csv, Path(args.output_csv), args.force)
            print(f"Step 2 dry-run: would score {pending_count} words with model '{args.model}' from '{source_csv}' → '{Path(args.output_csv)}'")
            return 0

        run_step2(
            Step2Options(
                run_slug=args.run,
                model=args.model,
                base_csv_path=Path(args.base_csv),
                output_csv_path=Path(args.output_csv),
                input_csv_path=Path(args.input) if args.input else None,
                batch_size=args.batch_size,
                limit=args.limit,
                max_retries=args.max_retries,
                timeout_seconds=args.timeout_seconds,
                max_tokens=args.max_tokens,
                skip_preflight=args.skip_preflight,
                force=args.force,
                endpoint_option=args.endpoint,
                base_url_option=args.base_url,
                system_prompt=Path(args.system_prompt_file).read_text(encoding="utf-8").strip(),
                user_template=Path(args.user_template_file).read_text(encoding="utf-8").strip(),
            ),
            repo=repo,
            lm_client=lm_client,
            output_dir=output_dir,
        )
        return 0

    if args.command in {"step3-compare", "step3"}:
        run_step3(
            Step3Options(
                run_a_csv_path=Path(args.run_a_csv),
                run_b_csv_path=Path(args.run_b_csv),
                run_c_csv_path=Path(args.run_c_csv) if args.run_c_csv else None,
                output_csv_path=Path(args.output_csv),
                outliers_csv_path=Path(args.outliers_csv),
                base_csv_path=Path(args.base_csv),
                outlier_threshold=args.outlier_threshold,
                confidence_threshold=args.confidence_threshold,
                merge_strategy=Step3MergeStrategy.parse(args.merge_strategy),
                dry_run=args.dry_run,
            ),
            repo=repo,
        )
        return 0

    if args.command in {"step4-upload", "step4"}:
        store = WordStore()
        marker = UploadMarkerWriter(repo)
        run_step4(
            Step4Options(
                final_csv_path=Path(args.final_csv),
                mode=UploadMode.parse(args.mode),
                report_path=Path(args.report_csv),
                upload_batch_id=args.upload_batch_id,
                reference_csv=Path(args.reference_csv) if args.reference_csv else None,
                anchor_l1_file=Path(args.anchor_l1_file) if args.anchor_l1_file else None,
                min_l1_jaccard=args.min_l1_jaccard,
                min_anchor_l1_precision=args.min_anchor_l1_precision,
                min_anchor_l1_recall=args.min_anchor_l1_recall,
            ),
            word_store=store,
            repo=repo,
            marker_writer=marker,
        )
        return 0

    if args.command in {"step5-rebalance", "step5"}:
        metrics = Step2Metrics()
        lm_client = LmStudioClient(api_key=os.getenv("LMSTUDIO_API_KEY"), metrics=metrics)
        transitions = _resolve_step5_transitions(args)
        run_step5(
            Step5Options(
                run_slug=args.run,
                model=args.model,
                input_csv_path=Path(args.input_csv),
                output_csv_path=Path(args.output_csv),
                batch_size=args.batch_size,
                lower_ratio=args.lower_ratio,
                max_retries=args.max_retries,
                timeout_seconds=args.timeout_seconds,
                max_tokens=args.max_tokens,
                skip_preflight=args.skip_preflight,
                endpoint_option=args.endpoint,
                base_url_option=args.base_url,
                seed=args.seed,
                transitions=transitions,
                system_prompt=Path(args.system_prompt_file).read_text(encoding="utf-8").strip(),
                user_template=Path(args.user_template_file).read_text(encoding="utf-8").strip(),
                dry_run=args.dry_run,
            ),
            repo=repo,
            lm_client=lm_client,
            output_dir=output_dir,
        )
        return 0

    if args.command == "quality-audit":
        result = run_quality_audit(
            candidate_csv=Path(args.candidate_csv),
            reference_csv=Path(args.reference_csv) if args.reference_csv else None,
            anchor_l1_file=Path(args.anchor_l1_file) if args.anchor_l1_file else None,
            min_l1_jaccard=args.min_l1_jaccard,
            min_anchor_l1_precision=args.min_anchor_l1_precision,
            min_anchor_l1_recall=args.min_anchor_l1_recall,
            repo=repo,
        )
        return 0 if result.passed else 1

    if args.command in {"rarity-distribution", "dist"}:
        run_rarity_distribution(
            csv_path=Path(args.csv),
            level_column=args.level_column,
            repo=repo,
        )
        return 0

    if args.command in {"review-low-confidence", "review"}:
        run_review_low_confidence(
            csv_path=Path(args.csv),
            labels_csv=Path(args.labels_csv),
            repo=repo,
            level_column=args.level_column,
            confidence_column=args.confidence_column,
            only_levels=parse_only_levels(args.only_levels),
            max_items=args.max_items,
            include_undecided=args.include_undecided,
        )
        return 0

    if args.command == "l1-review-check":
        run_l1_review_check(
            labels_csv=Path(args.labels_csv),
            min_precision=args.min_precision,
            min_reviewed=args.min_reviewed,
        )
        return 0

    if args.command == "build-retry-input":
        rows = build_retry_input(
            failed_jsonl=Path(args.failed_jsonl),
            base_csv=Path(args.base_csv),
            output_csv=Path(args.output_csv),
            repo=repo,
        )
        print(f"Wrote retry input CSV: {args.output_csv} (rows={rows})")
        return 0

    if args.command == "chain-rebalance-target-dist":
        metrics = Step2Metrics()
        lm_client = LmStudioClient(api_key=os.getenv("LMSTUDIO_API_KEY"), metrics=metrics)
        run_chain_rebalance(
            options=ChainOptions(
                input_csv=Path(args.input_csv),
                model=args.model,
                run_base=args.run_base,
                runs_dir=Path(args.runs_dir),
                state_file=Path(args.state_file) if args.state_file else Path(args.runs_dir) / f"{args.run_base}.rebalance.state",
                resume=args.resume,
                final_output_csv=Path(args.final_output_csv) if args.final_output_csv else None,
                batch_size=args.batch_size,
                max_tokens=args.max_tokens,
                timeout_seconds=args.timeout_seconds,
                max_retries=args.max_retries,
                system_prompt_file=Path(args.system_prompt_file),
                user_template_file=Path(args.user_template_file),
                reference_csv=Path(args.reference_csv) if args.reference_csv else None,
                anchor_l1_file=Path(args.anchor_l1_file) if args.anchor_l1_file else None,
                min_l1_jaccard=args.min_l1_jaccard,
                min_anchor_l1_precision=args.min_anchor_l1_precision,
                min_anchor_l1_recall=args.min_anchor_l1_recall,
                endpoint_option=args.endpoint,
                base_url_option=args.base_url,
            ),
            repo=repo,
            lm_client=lm_client,
            output_dir=output_dir,
        )
        return 0

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    """Builds the argument parser with all subcommands and options."""
    parser = argparse.ArgumentParser(prog="classificator", description="Romanian rarity classificator pipeline")
    parser.add_argument("--output-dir", default="build/rarity", help="Output root dir (default: build/rarity)")

    sub = parser.add_subparsers(dest="command")

    p1 = sub.add_parser("step1-export", help="Export source words from DB to CSV")
    p1.add_argument("--output-csv", required=True)
    sub.add_parser("step1", help="Alias of step1-export").add_argument("--output-csv", required=True)

    p2 = sub.add_parser("step2-score", help="Score words with LM and write run CSV")
    _add_step2_args(p2)
    p2a = sub.add_parser("step2", help="Alias of step2-score")
    _add_step2_args(p2a)

    p3 = sub.add_parser(
        "step3-compare",
        help="Compare 2-3 run CSVs and produce final_level (use --dry-run to preview without writing)",
    )
    _add_step3_args(p3)
    p3a = sub.add_parser(
        "step3",
        help="Alias of step3-compare (use --dry-run to preview without writing)",
        description="Alias of step3-compare (use --dry-run to preview without writing)",
    )
    _add_step3_args(p3a)

    p4 = sub.add_parser(
        "step4-upload",
        help="Upload final levels to DB (default: partial; accepts full-fallback/full_fallback)",
    )
    _add_step4_args(p4)
    p4a = sub.add_parser(
        "step4",
        help="Alias of step4-upload (default: partial; accepts full-fallback/full_fallback)",
        description="Alias of step4-upload (default: partial; accepts full-fallback/full_fallback)",
    )
    _add_step4_args(p4a)

    p5 = sub.add_parser(
        "step5-rebalance",
        help="Rebalance levels with strict batch-local local_id selection (exact-count 1..N, unique, no 0, no word-id fallback)",
    )
    _add_step5_args(p5)
    p5a = sub.add_parser(
        "step5",
        help="Alias of step5-rebalance (strict batch-local local_id selection, exact-count 1..N, unique, no 0, no word-id fallback)",
    )
    _add_step5_args(p5a)

    qa = sub.add_parser("quality-audit", help="Compute distribution + L1 Jaccard + anchor precision/recall")
    qa.add_argument("--candidate-csv", required=True)
    qa.add_argument("--reference-csv")
    qa.add_argument("--anchor-l1-file")
    qa.add_argument("--min-l1-jaccard", type=float)
    qa.add_argument("--min-anchor-l1-precision", type=float)
    qa.add_argument("--min-anchor-l1-recall", type=float)

    rd = sub.add_parser("rarity-distribution", help="Print rarity level distribution for a CSV")
    rd.add_argument("--csv", required=True)
    rd.add_argument("--level-column", help="Optional explicit level column (e.g. rarity_level/final_level)")
    rda = sub.add_parser("dist", help="Alias of rarity-distribution")
    rda.add_argument("--csv", required=True)
    rda.add_argument("--level-column", help="Optional explicit level column (e.g. rarity_level/final_level)")

    rv = sub.add_parser(
        "review-low-confidence",
        help="Interactive review of lowest-confidence words (use --include-undecided to resurface undecided labels)",
        description="Interactive review of lowest-confidence words (use --include-undecided to resurface undecided labels)",
    )
    rv.add_argument("--csv", required=True)
    rv.add_argument("--labels-csv", default="build/rarity/review_labels.csv")
    rv.add_argument("--level-column")
    rv.add_argument("--confidence-column", default="confidence")
    rv.add_argument("--only-levels", help="Comma-separated levels to include (e.g. 1 or 1,2,3)")
    rv.add_argument("--max-items", type=int, default=200)
    rv.add_argument("--include-undecided", action=argparse.BooleanOptionalAction, default=False)
    rva = sub.add_parser(
        "review",
        help="Alias of review-low-confidence (use --include-undecided to resurface undecided labels)",
        description="Alias of review-low-confidence (use --include-undecided to resurface undecided labels)",
    )
    rva.add_argument("--csv", required=True)
    rva.add_argument("--labels-csv", default="build/rarity/review_labels.csv")
    rva.add_argument("--level-column")
    rva.add_argument("--confidence-column", default="confidence")
    rva.add_argument("--only-levels", help="Comma-separated levels to include (e.g. 1 or 1,2,3)")
    rva.add_argument("--max-items", type=int, default=200)
    rva.add_argument("--include-undecided", action=argparse.BooleanOptionalAction, default=False)

    l1c = sub.add_parser("l1-review-check", help="Gate L1 quality from human review labels")
    l1c.add_argument("--labels-csv", default="build/rarity/review_labels.csv")
    l1c.add_argument("--min-precision", type=float)
    l1c.add_argument("--min-reviewed", type=int)

    br = sub.add_parser("build-retry-input", help="Build retry input CSV from failed JSONL")
    br.add_argument("--failed-jsonl", required=True)
    br.add_argument("--base-csv", required=True)
    br.add_argument("--output-csv", required=True)

    ch = sub.add_parser("chain-rebalance-target-dist", help="Run fixed 8-step rebalance chain to target distribution")
    ch.add_argument("--input-csv", required=True)
    ch.add_argument("--model", default="openai/gpt-oss-20b")
    ch.add_argument("--run-base", default="rb_run")
    ch.add_argument("--runs-dir", default="build/rarity/runs")
    ch.add_argument("--state-file")
    ch.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    ch.add_argument("--final-output-csv")
    ch.add_argument("--batch-size", type=int, default=DEFAULT_REBALANCE_BATCH_SIZE)
    ch.add_argument("--max-tokens", type=int, default=1200)
    ch.add_argument("--timeout-seconds", type=int, default=120)
    ch.add_argument("--max-retries", type=int, default=2)
    ch.add_argument("--system-prompt-file", default="prompts/rebalance_system_prompt_ro.txt")
    ch.add_argument("--user-template-file", default="prompts/rebalance_user_prompt_template_ro.txt")
    ch.add_argument("--reference-csv")
    ch.add_argument("--anchor-l1-file")
    ch.add_argument("--min-l1-jaccard", type=float)
    ch.add_argument("--min-anchor-l1-precision", type=float)
    ch.add_argument("--min-anchor-l1-recall", type=float)
    ch.add_argument("--endpoint")
    ch.add_argument("--base-url")

    return parser


def _add_prompt_files_args(parser, system_prompt_default="prompts/system_prompt_ro.txt", user_template_default="prompts/user_prompt_template_ro.txt"):
    parser.add_argument("--system-prompt-file", default=system_prompt_default)
    parser.add_argument("--user-template-file", default=user_template_default)


def _add_step2_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--input")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--skip-preflight", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--force", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--endpoint")
    parser.add_argument("--base-url")
    _add_prompt_files_args(parser)
    parser.add_argument("--dry-run", action="store_true", help="Simulate the run without calling the LM or writing output CSVs")


def _add_step3_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-a-csv", required=True)
    parser.add_argument("--run-b-csv", required=True)
    parser.add_argument("--run-c-csv")
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--outliers-csv", default="build/rarity/step3_outliers.csv")
    parser.add_argument("--base-csv", default="build/rarity/step1_words.csv")
    parser.add_argument("--outlier-threshold", type=int, default=DEFAULT_OUTLIER_THRESHOLD)
    parser.add_argument("--confidence-threshold", type=float, default=DEFAULT_CONFIDENCE_THRESHOLD)
    parser.add_argument("--merge-strategy", default="median")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview without writing output CSVs or outliers file",
    )


def _add_step4_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--final-csv", required=True)
    parser.add_argument(
        "--mode",
        default="partial",
        help="Upload mode (default: partial; accepts full-fallback/full_fallback)",
    )
    parser.add_argument("--report-csv", default="build/rarity/step4_upload_report.csv")
    parser.add_argument("--upload-batch-id")
    parser.add_argument("--reference-csv")
    parser.add_argument("--anchor-l1-file")
    parser.add_argument("--min-l1-jaccard", type=float)
    parser.add_argument("--min-anchor-l1-precision", type=float)
    parser.add_argument("--min-anchor-l1-recall", type=float)


def _add_step5_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_REBALANCE_BATCH_SIZE)
    parser.add_argument("--lower-ratio", type=float, default=DEFAULT_REBALANCE_LOWER_RATIO)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--skip-preflight", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--endpoint")
    parser.add_argument("--base-url")
    parser.add_argument("--seed", type=int)

    parser.add_argument("--from-level", type=int, help="Start of the level range (required if --to-level is provided)")
    parser.add_argument("--from-level-high", type=int, help="Upper bound of the starting level range")
    parser.add_argument("--to-level", type=int, help="Target level (required if --from-level is provided)")
    parser.add_argument("--transitions", default=DEFAULT_REBALANCE_TRANSITIONS)

    _add_step5_prompt_files_args(parser)
    parser.add_argument("--dry-run", action="store_true", help="Simulate the run without writing the output CSV")


def _add_step5_prompt_files_args(parser, system_prompt_default="prompts/rebalance_system_prompt_ro.txt", user_template_default="prompts/rebalance_user_prompt_template_ro.txt"):
    parser.add_argument("--system-prompt-file", default=system_prompt_default)
    parser.add_argument("--user-template-file", default=user_template_default)


def _count_pending(source_csv: Path, output_csv: Path, force: bool = False) -> int:
    """Count words in source CSV not yet scored in the output CSV."""
    try:
        import csv as _csv

        with open(source_csv, newline="", encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            fieldnames = reader.fieldnames
            if fieldnames is not None and "word_id" not in fieldnames:
                raise ValueError(f"Source CSV '{source_csv}' is missing required column 'word_id'")
            word_ids_in_source = {row.get("word_id", "") for row in reader}
    except FileNotFoundError:
        return 0

    scored = set()
    try:
        with open(output_csv, newline="", encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            scored = {row.get("word_id", "") for row in reader}
    except FileNotFoundError:
        pass

    return sum(1 for wid in word_ids_in_source if force or wid not in scored)


def _resolve_step5_transitions(args) -> list[LevelTransition]:
    from_level = args.from_level
    from_level_high = args.from_level_high
    to_level = args.to_level

    if from_level is not None or to_level is not None or from_level_high is not None:
        missing = [name for name, val in [
            ("--from-level", from_level),
            ("--to-level", to_level),
            ("--from-level-high", from_level_high),
        ] if val is None]
        # When --from-level-high is given but neither from/to level is set → specific error.
        if from_level_high is not None and from_level is None:
            raise ValueError(
                "Step5 requires both --from-level and --to-level when using --from-level-high; "
                f"missing flags: {', '.join(missing)}"
            )
        # When only some of the base pair are given → specific error.
        if (from_level is not None) != (to_level is not None):
            raise ValueError(
                f"Step5 requires both --from-level and --to-level together; "
                f"missing flags: {', '.join(missing)}"
            )
        if from_level is None or to_level is None:
            raise ValueError("Step5 requires both --from-level and --to-level when one is provided")
        if from_level_high is not None:
            require_valid_pair_transition(from_level, from_level_high, to_level)
            transitions = [LevelTransition(from_level=from_level, from_level_upper=from_level_high, to_level=to_level)]
        else:
            require_valid_transition(from_level, to_level)
            transitions = [LevelTransition(from_level=from_level, to_level=to_level)]
    else:
        transitions = parse_transitions(args.transitions)

    validate_transition_set(transitions)
    return transitions


if __name__ == "__main__":
    import argparse as _argparse
    import unittest as _unittest

    class _Step5TransitionResolutionTest(_unittest.TestCase):
        """Contract tests for cli._resolve_step5_transitions.

        These cover the validation boundaries of step5's transition resolution:
        - missing flag pair → raises ValueError
        - partial flags (only one given) → raises ValueError with specific message
        - --from-level-high without --from-level → specific error
        - valid single transition from CLI args → correct LevelTransition list
        - valid pair transition with from_level_high → correct upper bound
        """

        def _make_args(self, **overrides):
            defaults = {
                "from_level": None,
                "from_level_high": None,
                "to_level": None,
                "transitions": None,
            }
            defaults.update(overrides)
            return _argparse.Namespace(**defaults)

        def test_missing_to_level_raises_requires_both(self):
            args = self._make_args(from_level=3)
            with self.assertRaises(ValueError) as ctx:
                _resolve_step5_transitions(args)
            self.assertIn("requires both --from-level and --to-level together", str(ctx.exception))

        def test_missing_from_level_raises_requires_both(self):
            args = self._make_args(to_level=2)
            with self.assertRaises(ValueError) as ctx:
                _resolve_step5_transitions(args)
            self.assertIn("requires both --from-level and --to-level together", str(ctx.exception))

        def test_from_level_high_without_from_level_raises_specific(self):
            args = self._make_args(from_level_high=3, to_level=2)
            with self.assertRaises(ValueError) as ctx:
                _resolve_step5_transitions(args)
            err = str(ctx.exception)
            self.assertIn("--from-level and --to-level", err)

        def test_valid_single_transition_returns_correct_list(self):
            args = self._make_args(from_level=3, to_level=2)
            transitions = _resolve_step5_transitions(args)
            self.assertEqual(len(transitions), 1)
            t = transitions[0]
            self.assertIsInstance(t, LevelTransition)
            self.assertEqual(t.from_level, 3)
            self.assertEqual(t.to_level, 2)
            self.assertIsNone(t.from_level_upper)

        def test_valid_pair_transition_with_from_level_high(self):
            args = self._make_args(from_level=3, from_level_high=4, to_level=2)
            transitions = _resolve_step5_transitions(args)
            self.assertEqual(len(transitions), 1)
            t = transitions[0]
            self.assertIsInstance(t, LevelTransition)
            self.assertEqual(t.from_level, 3)
            self.assertEqual(t.from_level_upper, 4)
            self.assertEqual(t.to_level, 2)

        def test_same_level_transition_allowed(self):
            args = self._make_args(from_level=4, to_level=4)
            transitions = _resolve_step5_transitions(args)
            self.assertEqual(len(transitions), 1)
            t = transitions[0]
            self.assertEqual(t.from_level, 4)
            self.assertEqual(t.to_level, 4)


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] in {"--cli", "--entry"}:
        sys.exit(main())
    else:
        import unittest as _unittest
        _unittest.main(argv=_sys.argv[:1], verbosity=2)
