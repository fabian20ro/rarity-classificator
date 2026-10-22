# Lessons Learned

> This file is maintained by AI agents working on this project.
> It captures validated, reusable insights discovered during development.
> **Read this file at the start of every task. Update it at the end of every iteration.**

## How to Use This File

### Reading (Start of Every Task)
Before starting any work, read this file to avoid repeating known mistakes
and to leverage proven approaches.

### Writing (End of Every Iteration)
After completing a task or iteration, evaluate whether any new insight was
gained that would be valuable for future sessions. If yes, add it to the
appropriate category below.

### Promotion from Iteration Log
Patterns that appear 2+ times in `ITERATION_LOG.md` should be promoted
here as a validated lesson.

### Pruning
If a lesson becomes obsolete (e.g., a dependency was removed, an API changed),
move it to the Archive section at the bottom with a date and reason.

---

## Architecture & Design Decisions

<!-- Insights about system design, patterns that work/don't work in this codebase -->
<!-- Format: **[YYYY-MM-DD]** Brief title — Explanation -->
**[2026-02-14]** Classifier/consumer boundary must stay explicit — `rarity-classificator` owns pipeline runtime and artifacts; downstream apps only consume `words.rarity_level`.
**[2026-02-14]** CSV-first orchestration is a reliability feature — reproducible step artifacts plus checkpoints are required for multi-hour recovery and auditability.

## Code Patterns & Pitfalls

**[2026-09-13]** Dry-run CSV previews need real CSV escaping too. Use `csv.writer`;
round-trip comma, quote and newline fields with `csv.reader`, while asserting no file writes.

<!-- Language/framework-specific gotchas discovered in this project -->
<!-- Format: **[YYYY-MM-DD]** Brief title — Explanation -->
**[2026-02-14]** Step5 id domain must remain batch-local — selection output must use only `local_id` in `1..N`; mixing in `word_id` or allowing `0` creates silent corruption risk.
**[2026-02-14]** Prompt/parser contract drift causes hard failures — exact-count semantics and id rules must match verbatim between prompt text and parser validation.
**[2026-02-14]** Prompt wording is a behavior contract — small phrasing edits can materially shift L1 composition; treat prompt files as versioned assets.
**[2026-02-14]** Strict parsing beats permissive autofill — long rebalance campaigns are safer when malformed LM selections fail fast instead of being auto-completed.
**[2026-05-10]** Selected-word-id mode must stay local-id only — accepting word text or 0-based positional fallbacks can silently corrupt batch-local selection contracts.
**[2026-05-11]** Duplicate selected local IDs must be rejected — deduping them can make an invalid LM response appear to satisfy exact-count checks while violating uniqueness.
**[2026-05-11]** Normalization boundaries need mixed-shape coverage — when a parser accepts ints, strings, and dicts for the same contract field, add tests that mix shapes so duplicate detection exercises the shared normalization path.
**[2026-05-11]** Numeric-string local_id aliases matter — selection parsers should treat "1" and 1 as the same local id when enforcing uniqueness.
**[2026-05-12]** Selected-word-id schema and parser must stay in lockstep — request-building should enforce the same exact-count local-id contract as the parser, so model-side JSON Schema cannot drift from runtime validation.
**[2026-05-12]** Selected-word-id schema should reject impossible counts — if the requested exact count exceeds the batch size, fail fast instead of emitting a schema the model cannot satisfy.
**[2026-05-14]** Selected-word-id request building must reject impossible exact counts before any response-format branching — the request builder should fail on `expected_items <= 0` and on counts larger than the batch, even when JSON schema is disabled, so prompt generation never advertises an impossible selection contract.
**[2026-05-14]** Selection repair prompts must restate the same strict batch-local contract — recovery wording should repeat exact-count `local_id` `1..N`, uniqueness, no `0`, and no `word_id` fallback so repair mode cannot drift from parser rules.
**[2026-02-14]** Deterministic decode profiles improve JSON stability — lower-variance decoding (for example `temperature=0`) reduces structured-output breakage.


## Testing & Quality

**[2026-10-15]** Exercise real producer/consumer boundaries — WordStore yields BaseWordRow, and Step3/Step5 preserve source level columns alongside final_level. Tuple-only mocks and isolated helpers hid broken exports, successful scoring calls and audited pipeline artifacts; smoke tests should use real internal collaborators and mock DB/LM I/O.
**[2026-10-15]** Duplicate test-class declarations silently remove coverage — an empty second TestStep4Upload replaced nine integration tests. Keep Ruff F811 enabled and verify collection of critical gate tests; a passing suite cannot detect tests it never discovers.
**[2026-10-15]** Forced rescoring needs atomic replacement per batch — appending an existing word ID poisons strict CSV loading before final merge. Persist complete replacement snapshots after each successful forced batch so interruptions retain unique readable rows, including failed/unprocessed/unrelated records.

**[2026-09-29]** Use `python scripts/check.py` for complete verification. The old
unittest-only command silently skipped function-style tests. CI and local gates
must call the project entrypoint, which runs Ruff then pytest (both test styles).

**[2026-09-29]** Fuzzy word identity requires full normalized edit distance.
Prefix-only acceptance introduced as "verification hygiene" matched unrelated
words and could assign one word's score to another pending row. Preserve the
original two-edit limit; test the parser consumer as well as matcher parity.
Do not encode a discovered inconsistency as a desired behavior assertion.

**[2026-09-25]** Quality-gate integration fixtures must satisfy earlier campaign
validation. Use isolated CSVs and the real repository/audit; stub the LM boundary,
not the gate. Check independent Jaccard and anchor failures, and prove the tests
reject a counterexample that ignores a failed audit.

<!-- What breaks, what's flaky, what testing strategies work here -->
<!-- Format: **[YYYY-MM-DD]** Brief title — Explanation -->
**[2026-02-14]** Histogram fit is insufficient as a release gate — upload candidates need semantic checks (L1 Jaccard plus anchor precision/recall), not just target distribution match.
**[2026-02-14]** Anchor coverage must grow over time — small anchor sets are only seed protection and should be curated/expanded to keep precision-recall gates meaningful.
**[2026-02-15]** Add a fast distribution check before deep audits — `classificator rarity-distribution` gives immediate sanity checks on level skew before running heavier quality gates.
**[2026-02-15]** L1 quality needs a human loop on weakest-confidence items — use `review-low-confidence --only-levels 1` plus `l1-review-check` thresholds as an ongoing gate.
**[2026-02-20]** Recovery uploads need goal-aligned reference gating — when DB is reset or intentionally diverged, strict Jaccard/anchor thresholds against stale reference snapshots can block valid restores; confirm/refresh reference policy before running mandatory gates.

## Performance & Infrastructure

**[2026-10-16]** DEX cache records can contain complete HTML pages — extract definition spans one file at a time; never retain the full cache or count navigation text as lexical evidence. Observed local rebus cache: roughly 1.3 GB across 12,728 records.
**[2026-10-16]** Retry projection cadence must count committed attempts — replacing existing IDs does not change record count. A modulo check on total record count can turn batched CSV projection into one full rewrite per retry.

<!-- Deployment quirks, scaling lessons, CI/CD gotchas -->
<!-- Format: **[YYYY-MM-DD]** Brief title — Explanation -->
**[2026-02-14]** Local model instability requires bounded recovery tactics — retries, partial salvage, and capped batch splitting are necessary for predictable throughput.
**[2026-02-14]** Pair-level rebalance works better with stratified source mixing — mixed batches from both source levels reduce unstable transitions.
**[2026-05-19]** PR branches need at least one workflow-backed check for compound gate — If a repo opens PRs but has no `.github/workflows` entry, GitHub returns an empty status rollup and compound gate reports checks as unknown.

## Dependencies & External Services

<!-- Version constraints, API quirks, integration lessons -->
<!-- Format: **[YYYY-MM-DD]** Brief title — Explanation -->
**[2026-02-14]** Upload default should stay partial — only rows present in candidate CSV should update by default; `full-fallback` is an explicit exception mode.

## Process & Workflow

**[2026-10-15]** Push new PR branches with explicit destinations — a source-only push followed the existing main upstream and updated main. Use `refs/heads/<branch>:refs/heads/<branch>`, set the matching upstream, and verify remote heads. If correcting an accidental update, preserve the commit first; respect protected-branch rules and use a normal revert when force rollback is prohibited.

<!-- What makes iterations smoother, communication patterns, PR conventions -->
<!-- Format: **[YYYY-MM-DD]** Brief title — Explanation -->
**[2026-02-15]** Keep one lessons source of truth — maintain lessons only in root `LESSONS_LEARNED.md` to prevent drift between duplicated files.
**[2026-02-15]** Prefer structured per-batch logs for long rebalances — progress JSONL with picked words and counters is easier to monitor and audit than stdout-only output.
**[2026-05-13]** Mirror strict Step5 rules in README quickstarts — The first runnable example should repeat the batch-local `local_id` contract (`1..N`, exact-count, unique, no `0`, no word-id fallback) so quickstart readers do not miss the parser boundary.
**[2026-05-14]** CLI help/docstring edits need import smoke checks — escaped quote corruption can break Python modules, so run a focused import or unit test after text-only source edits.
**[2026-05-15]** argparse help output wraps long descriptions — help assertions should use stable substrings, not one exact wrapped line.
**[2026-05-15]** Selected-word-id parsers must reject out-of-range ids — silently skipping extra local ids can let malformed LM output satisfy the exact-count check while still violating the batch-local contract.
**[2026-05-15]** Argparse subcommand aliases need description, not just help, for detailed alias output — `help=` shows in the parent command listing, while `description=` is what surfaces in the alias subcommand's own `format_help()` output.
**[2026-05-16]** Recovery affordances should live in parser descriptions, not only shell comments — if a subcommand exposes a recovery flag like `--include-undecided`, put the reminder in `description=` so the alias's own help surfaces it too.

**[2026-05-16]** Queue recovery affordances belong next to the command — Review flows are easier to rediscover when `--include-undecided` is shown beside the `review-low-confidence` example instead of only being described in the label legend.

---

## Archive

<!-- Lessons that are no longer applicable. Keep for historical context. -->
<!-- Format: **[YYYY-MM-DD] Archived [YYYY-MM-DD]** Title — Reason for archival -->

**[2026-10-21]** Corpus identity is part of evaluation validation — a matching CSV
hash alone does not establish Romanian wordfreq or the intended rebus corpus.
Validate language/package/versioned policy and source-ledger hashes; pin extractor
code. Exclude pilot/collision pages from dictionary token counts to reduce self-entry
contamination. Dictionary coverage is not familiarity: this pilot's rebus corpus
observed29/37 forms but none of the4 rated5; report paired coverage and missingness.

**[2026-10-23]** Blind review means removing predictions from the public payload —
CSS-hidden panels still expose estimates. Publish only lexical fields, use a new
pack-bound storage namespace, preserve old labels/events, and freeze predictions
outside the web root before annotation. Rebuild shared dictionary frequencies
excluding both development and held-out target pages before fitting thresholds.

**[2026-10-23]** Preparing an independent batch does not authorize more user
annotation workload — the user explicitly declined after150 pilot forms. Reuse
existing labels with rubric/provenance strata and internal validation; keep new
unlabelled forms optional. Never invent independent gold from assistant estimates.

**[2026-10-23]** Coverage-conditioned baselines matter — missing frequencies are
concentrated among rare forms. Compare each frequency method with a median fitted
on the same observed training labels, excluding the held-out label, alongside a
global median. Validated here: rebus matched26 CV MAE0.500 equals the source-matched
constant1 baseline, despite beating the global-median0.808. Always report per-level
coverage and rare-word abstentions; pooled MAE alone can hide this selection effect.
