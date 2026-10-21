# Iteration Log

> Append-only journal of AI agent work sessions on this project.
> **Add an entry at the end of every iteration.**
> When patterns emerge (same issue 2+ times), promote to `LESSONS_LEARNED.md`.

## Format

Each entry should follow this structure:

---

### [YYYY-MM-DD] Brief Description of Work Done

**Context:** What was the goal / what triggered this work
**What happened:** Key actions taken, decisions made
**Outcome:** Result — success, partial, or failure
**Insight:** (optional) What would you tell the next agent about this?
**Promoted to Lessons Learned:** Yes/No

### [2026-05-13] Synced README quickstart with Step5 local-id contract

**Context:** The README quickstart showed the Step5 rebalance command but did not restate the strict batch-local `local_id` contract beside the runnable example.
**What happened:** Added a short Step5 reminder under the README quickstart so the example now says selections are exact-count, unique `local_id` values in `1..N`, with no `0` and no word-id fallback. Also recorded the same doc-surface lesson in `LESSONS_LEARNED.md` and appended this iteration note.
**Outcome:** Success. The quickstart now matches the parser/request contract more closely, and the repo-local learning log was updated as required.
**Insight:** Command snippets that drive a strict parser should restate the boundary right where the user copies them.
**Promoted to Lessons Learned:** Yes

---

### [2026-02-20] Restored rarity after reset by remapping shifted word IDs

**Context:** Requested immediate upload of the latest computed rarity file after DB rarity was reset to level 4 for all rows.
**What happened:** Ran `step4-upload` on the latest CSV and got `updated=0` with all rows `missing_db_word`; verified DB `words.id` range shifted (`155397..233094`) versus candidate IDs (`77699..155396`); validated deterministic remap `new_id = old_id + 77698` against DB samples; generated remapped CSV `rb_l4split25k_20260215_134927.idshift77698.csv`; reran `step4-upload --mode partial` successfully.
**Outcome:** Success. Upload updated `77,698` rows and DB rarity distribution is now `1:1234, 2:6610, 3:12517, 4:25000, 5:32337` (not all 4 anymore).
**Insight:** After table recreation/reset, ID domains may shift even when `(word,type)` content is unchanged; step4 partial uploads can silently become no-op with `missing_db_word` unless IDs are remapped.
**Promoted to Lessons Learned:** Yes

---

### [2026-02-20] Added rarity-only upload regression test and blocked restore upload on gate failure

**Context:** Requested restoration of `words.rarity_level` after DB was reset to 4 for all rows, using the latest computed CSV while ensuring schema additions are not overwritten.
**What happened:** Added `tests/test_word_store.py` to assert `update_rarity_levels_chunked` executes only `UPDATE words SET rarity_level = %s WHERE id = %s` with `(level, word_id)` payloads and no-op behavior for empty updates; ran full unit suite; validated candidate CSV integrity/distribution; ran mandatory `quality-audit` against `build/rarity/reference/current_db_levels.csv`.
**Outcome:** Partial success. Code safety test and unit suite passed, but quality gate failed (`l1_jaccard=0.0267`, `anchor_l1_precision=0.0479`, `anchor_l1_recall=0.4219`), so upload was not executed per policy.
**Insight:** Recovery uploads can be intentionally blocked by strict reference-based gates when candidate and reference represent different states; gate policy/reference selection must match the restore objective.
**Promoted to Lessons Learned:** Yes

---

### [2026-02-15] Uploaded final rebalance output to Supabase

**Context:** Rebalance run finished with target distribution (`L4=25k`, rest of previous L4 moved to L5).
**What happened:** Ran `step4-upload` in partial mode for `rb_l4split25k_20260215_134927.csv` and validated DB distribution with direct SQL counts.
**Outcome:** Success. DB now reflects `1:1234, 2:6610, 3:12517, 4:25000, 5:32337`.
**Insight:** N/A
**Promoted to Lessons Learned:** No

---

### [2026-02-15] Mirrored Step5 batch progress into main run log

**Context:** Requested batch progress visibility in the main log stream used for tailing.
**What happened:** Updated Step5 to append each batch progress payload to both `rebalance/progress/<run>.progress.jsonl` and `rebalance/runs/<run>.jsonl` (`event=batch_progress`), added tests, and ran full unit suite.
**Outcome:** Success. New/resumed Step5 processes now expose per-batch progress directly in the primary run log.
**Insight:** Logging progress in the same stream operators already tail reduces observability friction during long retries.
**Promoted to Lessons Learned:** No

---

### [2026-02-15] Added Step5 structured progress logs with picked words

**Context:** Needed Step5 logs to show explicit progress and exactly which words were picked per batch.
**What happened:** Added `rebalance/progress/<run>.progress.jsonl` output with per-batch counters and picked word ids/words, kept checkpoint compatibility for resume, added tests, and updated runbook docs.
**Outcome:** Success. New Step5 runs (or resumed runs after restart) produce progress logs suitable for live tailing and audit.
**Insight:** Checkpoint-compatible logging allows richer observability without sacrificing resumability.
**Promoted to Lessons Learned:** Yes

---

### [2026-02-15] Started level-4 to level-5 rebalance run in tmux

**Context:** Requested rebalance to keep about 25k words on level 4 and move the remainder of current level-4 words to level 5.
**What happened:** Started Step5 run `rb_l4split25k_20260215_134927` in detached tmux with transition `4:4` and `--lower-ratio 0.45589657` from input `initial_20260215_034523.csv`.
**Outcome:** In progress. Process is running in tmux and writing Step5 run logs under `build/rarity/rebalance/runs/`.
**Insight:** For this objective, transition `4:4` is the correct split mode; it controls the kept count in level 4 while moving the rest to level 5.
**Promoted to Lessons Learned:** No

---

### [2026-02-15] Uploaded new run and added low-confidence review app with L1 gate

**Context:** Requested production upload of the latest run and a way to continuously validate Level 1 quality with human review.
**What happened:** Uploaded `build/rarity/runs/initial_20260215_034523.csv` via `step4-upload` (partial), implemented `review-low-confidence`/`review` interactive labeling app, implemented `l1-review-check` threshold gate, and integrated docs/tests.
**Outcome:** Success. New rarity levels are uploaded, and an operator workflow now exists to review lowest-confidence words and enforce L1 precision thresholds.
**Insight:** Combining anchor checks with recurring low-confidence human review gives stronger L1 protection than either alone.
**Promoted to Lessons Learned:** Yes

---

### [2026-02-15] Compared latest Step2 run with current DB rarity levels

**Context:** Needed Jaccard and distribution comparison between latest generated run and currently stored DB levels.
**What happened:** Exported current DB levels to `build/rarity/reference/current_db_levels.csv`, ran `rarity-distribution` on candidate/reference, then ran `quality-audit` with `--reference-csv`.
**Outcome:** Success. Produced L1 Jaccard and side-by-side distribution snapshots for direct comparison.
**Insight:** N/A
**Promoted to Lessons Learned:** No

---

### [2026-02-15] Added rarity-distribution CLI utility and docs integration

**Context:** Needed a quick way to inspect rarity level distribution directly from generated CSV outputs.
**What happened:** Implemented `classificator rarity-distribution` (alias `dist`), added parser/tests, updated README/RUNBOOK/AGENTS docs, and executed it on the latest Step2 output.
**Outcome:** Success. Distribution can now be checked with a single command and is integrated into operational docs.
**Insight:** Fast distribution visibility helps catch obvious skew earlier in the pipeline.
**Promoted to Lessons Learned:** Yes

---

### [2026-02-15] Consolidated lessons into single root file

**Context:** Requested to merge duplicate lessons files into the root project lessons file.
**What happened:** Merged remaining unique wording from `docs/LESSONS_LEARNED.md` into root `LESSONS_LEARNED.md`, updated README reference, removed the duplicate docs file, and ran unit tests plus a `quality-audit` smoke command.
**Outcome:** Success. Lessons are now maintained in one authoritative location at project root, and verification commands passed.
**Insight:** Keeping a single lessons source prevents divergence in future agent sessions.
**Promoted to Lessons Learned:** Yes

---

### [2026-02-14] Synced docs and memory with external system contract

**Context:** Imported the updated external classifier description from the `propozitii-nostime` reference document.
**What happened:** Updated boundary/contract docs (`README`, onboarding, handover, pipeline design), recorded validated operational lessons in both lessons files, ran unit tests, and executed a `quality-audit` smoke command.
**Outcome:** Success. Repository docs now reflect current ownership boundary, strict Step5 rules, mandatory semantic quality gates, and partial-upload default; verification commands passed.
**Insight:** Cross-repo boundary wording should be kept explicit to prevent runtime/code ownership confusion.
**Promoted to Lessons Learned:** Yes

---

### [2026-05-10] Hardened selected-word-id parsing to reject non-local fallbacks

**Context:** `selected-word-id` mode is supposed to obey the strict batch-local id contract (`1..N`, no zero, no word-id fallback).
**What happened:** Removed the word/positional fallback path from `LmStudioResponseParser._coerce_selections_to_word_ids`, added a regression test that `[0]` is rejected, and verified the full unit suite with `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'`.
**Outcome:** Success. The parser now fails fast when the model returns non-local ids instead of silently reinterpreting them.
**Insight:** For batch-local selection flows, permissive recovery creates contract drift; it is better to reject bad ids than guess.
**Promoted to Lessons Learned:** Yes

---

### [2026-05-11] Rejected duplicate local IDs in selected-word-id parsing

**Context:** Strict Step5 selection contracts require exact-count local ids with no duplicates, but the parser only deduped repeated ids and could still accept `[1, 1]` when one id was expected.
**What happened:** Updated `LmStudioResponseParser._coerce_selections_to_word_ids` to track seen local ids and raise on duplicates, added a regression test, and reran the full unit suite.
**Outcome:** Success. Duplicate local ids now fail fast instead of slipping through exact-count validation.
**Insight:** Unique-count checks are not enough for batch-local selection contracts; duplicate detection must be explicit.
**Promoted to Lessons Learned:** Yes

---

### [2026-05-11] Added mixed-shape duplicate-id coverage for selected-word-id parsing

**Context:** The parser normalizes selected ids from ints, strings, and dicts, so duplicate detection should be exercised across shape boundaries instead of only with repeated scalar ids.
**What happened:** Added a regression test that mixes an int local id and a dict local id with the same value, then reran the focused `tests.test_response_parser` suite.
**Outcome:** Success. The new test passed, and the strict duplicate-id contract is now covered across heterogeneous LM response shapes.
**Insight:** Normalization boundaries are where duplicate bugs hide; mixed-shape fixtures are worth adding whenever a contract accepts more than one input form.
**Promoted to Lessons Learned:** Yes

---

### [2026-05-12] Hardened selected-word-id request schema

**Context:** Step5 selected-word-id mode already had strict parser validation, but the request builder still allowed implicit expected-count fallback when generating JSON Schema.
**What happened:** Added a request-builder guard that requires `expected_items` in selected-word-id schema mode, and added focused tests covering the exact-count/uniqueItems schema plus the missing-count failure path. Ran the request-builder and response-parser tests, then the full unit suite.
**Outcome:** Success. Schema generation now matches the parser's exact-count contract and the full test suite passed.
**Insight:** The request schema is part of the same contract as the parser; if they diverge, the model can be prompted into a shape the runtime will reject.
**Promoted to Lessons Learned:** Yes

### [2026-05-12] Rejected impossible expected count in selected-word-id request schema

**Context:** Selected-word-id request generation already required exact-count JSON Schema, but it still allowed `expected_items` values larger than the batch size.
**What happened:** Added a guard in `LmStudioRequestBuilder.build_request` to fail fast when `expected_items > len(batch)`, added a focused regression test in `tests/test_request_builder.py`, updated `LESSONS_LEARNED.md`, and reran the request-builder, response-parser, step5 progress, and full unit suites with `PYTHONPATH=src`.
**Outcome:** Success. The request builder now refuses impossible exact-count schemas instead of generating prompts the model cannot satisfy.
**Insight:** Exact-count contracts need both shape validation and feasibility validation; a schema can still be invalid for the current batch even when it is structurally correct.
**Promoted to Lessons Learned:** Yes

### [2026-05-12] Synced README quality gate with mandatory anchor recall

**Context:** The README quality gate example still showed only Jaccard and anchor precision, while the CLI and runbook already require anchor recall too.
**What happened:** Updated the README quality gate example to include `--min-anchor-l1-recall 0.70`, so the quickstart matches the actual `quality-audit` contract.
**Outcome:** Success. Documentation now reflects the full gate threshold set used by the tool.
**Insight:** Quality-gate examples need to stay in lockstep with the CLI flag set, or the quickest path becomes the wrong path.
**Promoted to Lessons Learned:** No

### [2026-05-13] Clarified Step5 contract in runbook

**Context:** The operator runbook showed the Step5 command, but the exact-count local-id contract was only stated in higher-level docs.
**What happened:** Added a short Step5 contract reminder to `docs/RUNBOOK.md` so the rebalance section now explicitly says selections must be exact-count `local_id` values in `1..N`, with no duplicates, no `0`, and no word-id fallback.
**Outcome:** Success. Operator-facing docs now restate the strict batch-local contract where the command is shown.
**Insight:** Small contract reminders belong next to the operational command, not only in overview docs.
**Promoted to Lessons Learned:** No

### [2026-05-13] Clarified Step5 contract in onboarding

**Context:** The onboarding checklist still sent readers through the validation flow without restating the strict batch-local Step5 selection contract.
**What happened:** Added a short reminder to `docs/ONBOARDING.md` so the first-safe-validation flow now says Step5 selections must be exact-count `local_id` values in `1..N`, with no duplicates, no `0`, and no word-id fallback.
**Outcome:** Success. The onboarding path now mirrors the same strict Step5 contract already shown in the README and runbook.
**Insight:** First-run checklists should restate the strictest selection contract where new contributors are most likely to see it.
**Promoted to Lessons Learned:** No

---

### [2026-05-14] Hardened selected-word-id request building against impossible counts

**Context:** The Step5 selected-word-id contract already had parser/schema guards, but the request builder still coerced `expected_items=0` to `1` in non-schema mode.
**What happened:** Updated `LmStudioRequestBuilder.build_request` so selected-word-id mode now rejects `expected_items <= 0` and counts larger than the batch before any response-format branching; added focused request-builder tests for the non-schema zero-count and overflow cases.
**Outcome:** Success. The request builder now fails fast on impossible exact-count selection requests in every response-format mode, and the full unit suite passed.
**Insight:** Contract validation belongs at the request boundary, not only in the schema branch.
**Promoted to Lessons Learned:** Yes

---

### [2026-05-14] Synced Step5 contract wording across handover and design docs

**Context:** The strict Step5 local-id contract was already enforced in code and covered in README/runbook/onboarding, but the handover and pipeline design docs still used shorter wording.
**What happened:** Expanded the Step5 wording in `docs/HANDOVER.md` and `docs/PIPELINE_DESIGN.md` to restate the exact batch-local contract: exact-count `local_id` values in `1..N`, unique, no `0`, no word-id fallback.
**Outcome:** Success. The operator-facing design docs now mirror the same contract language as the executable request/parser boundary.
**Insight:** Small contract reminders belong in every operator-facing surface, not just the main quickstart.
**Promoted to Lessons Learned:** No

---

### [2026-05-14] Restated Step5 contract in selection-repair prompt

**Context:** The Step5 recovery prompt still said "select the most common entries" without explicitly repeating the batch-local exact-count contract that the parser and request builder already enforce.
**What happened:** Tightened `SELECTION_REPAIR_SYSTEM_PROMPT` and `SELECTION_REPAIR_USER_TEMPLATE` in `src/classificator/lm/client.py` so repair mode now restates exact-count `local_id` `1..N`, uniqueness, no `0`, and no `word_id` fallback; added a focused unit test for the prompt strings.
**Outcome:** Success. The recovery prompt now mirrors the strict Step5 contract instead of leaving it implicit, and the focused unittest passed.
**Insight:** Repair prompts are part of the same contract surface as the main request builder; if they stay vague, they can reintroduce drift during fallback paths.
**Promoted to Lessons Learned:** Yes

---

### [2026-05-14] Pinned upload-mode parser defaults and aliases

**Context:** The upload-mode and merge-strategy parsers are part of the CLI contract, but they had no direct unit coverage for default handling or accepted aliases.
**What happened:** Added `tests/test_models.py` to pin `UploadMode.parse` defaulting to `partial`, accepting `full-fallback` and `full_fallback`, rejecting unknown values, and to cover the `Step3MergeStrategy.parse` aliases and rejection path. Verified the new test file with `PYTHONPATH=src python3 -m unittest tests.test_models` after discovering `python` is not installed in this environment.
**Outcome:** Success. The parser contract now has direct regression coverage for its documented defaults and aliases.
**Insight:** Small enum parsers are easy to drift; pinning their defaults and accepted spellings keeps CLI behavior stable.
**Promoted to Lessons Learned:** No

---

### [2026-05-14] Clarified Step5 CLI help and fixed broken docstring syntax

**Context:** The Step5 CLI entrypoint help was vague, and importing `classificator.cli` exposed literal escaped docstring quotes that broke Python syntax.
**What happened:** Repaired the escaped docstrings in `src/classificator/cli.py`, expanded the `step5`/`step5-rebalance` help text to restate the batch-local exact-count `local_id` contract, and added a focused CLI-help test.
**Outcome:** Success. The CLI module imports cleanly again, and the help text now points operators at the strict Step5 selection contract.
**Insight:** Syntax verification can catch mechanical text corruption before it turns into a runtime blocker.
**Promoted to Lessons Learned:** Yes

---

### [2026-05-15] Mirrored Step5 help contract into docs and tests

**Context:** The Step5 CLI help and README quickstart already named the strict batch-local selection contract, but the wording could better mirror the parser/request boundary and the help test needed to survive argparse wrapping.
**What happened:** Expanded `src/classificator/cli.py` help text for `step5` and `step5-rebalance` to include `unique`, `no 0`, and `no word-id fallback`; added the same reminder to the README quickstart; strengthened `tests/test_cli_help.py` with stable substrings instead of one wrapped line; recorded the wrapping caveat in `LESSONS_LEARNED.md`.
**Outcome:** Success. Focused CLI-help verification passed with `PYTHONPATH=src python3 -m unittest tests.test_cli_help`.
**Insight:** Generated help text can wrap, so assertions should target durable substrings rather than one exact line.
**Promoted to Lessons Learned:** Yes

---

### [2026-05-15] Tightened selected-word-id parsing for out-of-range ids

**Context:** The selected-word-id parser already enforced exact-count and duplicate checks, but malformed responses could still include extra out-of-range local ids that were silently ignored if enough valid ids remained.
**What happened:** Hardened `src/classificator/lm/response_parser.py` so selected-word-id mode now requires integer `local_id` values on every result item and rejects any `local_id` outside the current batch range. Added a regression test in `tests/test_response_parser.py` for out-of-range ids.
**Outcome:** Success. Focused response-parser tests passed with `PYTHONPATH=src python3 -m unittest tests.test_response_parser -v`.
**Insight:** Exact-count selection contracts need to reject extra malformed ids, not just count the valid ones, or invalid model output can slip through with a superficially correct total.
**Promoted to Lessons Learned:** Yes

---

### [2026-05-15] Clarified handover upload wording

**Context:** The handover doc still said `full-fallback` uploads during experiments unless explicitly intended, which read awkwardly next to the project-wide partial-default contract.
**What happened:** Reworded the `docs/HANDOVER.md` do/don't line to say `Avoid full-fallback uploads unless explicitly intended.` so it matches the rest of the upload-mode guidance more directly.
**Outcome:** Success. Documentation now states the same upload-mode intent more plainly.
**Insight:** Small contract wording fixes are easiest to trust when the negative case is phrased directly.
**Promoted to Lessons Learned:** No

---

### [2026-05-15] Made step4 alias help discoverable in argparse output

**Context:** The `step4` alias was present, but its detailed upload-mode guidance only showed up in the top-level parser help. The alias subcommand's own `format_help()` output stayed generic because `help=` alone does not surface there.
**What happened:** Expanded `src/classificator/cli.py` so `step4` now carries the same partial-default / `full-fallback` wording in both `help=` and `description=`, added a focused CLI-help regression for the alias output, and recorded the argparse behavior in `LESSONS_LEARNED.md`.
**Outcome:** Success. Focused CLI-help verification passed with `PYTHONPATH=src python3 -m unittest tests.test_cli_help`.
**Insight:** For subcommand aliases, put operator-facing wording in `description=` if you want it visible in the alias's own help output.
**Promoted to Lessons Learned:** Yes

---

### [2026-05-16] Added README tip for undecided review labels

**Context:** The README human-review example showed `review-low-confidence`, but the `--include-undecided` queue option was only called out in the runbook.
**What happened:** Added a short shell-comment tip beside the README `review-low-confidence` example so operators can rediscover `--include-undecided` from the top-level quickstart.
**Outcome:** Success. The README now points at the existing undecided-label queue path without changing behavior.
**Insight:** Small queue-affordance notes are most useful when they sit next to the copy/paste command.
**Promoted to Lessons Learned:** No

---

### [2026-05-16] Surfaced undecided-review recovery tip in the runbook

**Context:** The README already showed `--include-undecided` beside the human-review example, but the operator runbook still only mentioned it in the label legend.
**What happened:** Added the same `--include-undecided` tip as a shell comment beside the `review-low-confidence` example in `docs/RUNBOOK.md` so the recovery affordance is visible where operators launch the queue.
**Outcome:** Success. The runbook now mirrors the review-queue recovery path at the point of use.
**Insight:** Queue recovery switches are easier to rediscover when they sit next to the copy/paste command.
**Promoted to Lessons Learned:** Yes

---

### [2026-05-16] Surfaced review recovery flag in CLI help

**Context:** The `review-low-confidence` command already supported `--include-undecided`, but that recovery affordance was only visible in the shell comment tip and not in the subcommand's own help description.
**What happened:** Updated `src/classificator/cli.py` so both `review-low-confidence` and its `review` alias mention `--include-undecided` in `description=` as well as `help=`; added focused CLI-help coverage in `tests/test_cli_help.py`; verified the touched surface with `PYTHONPATH=src python3 -m unittest tests.test_cli_help tests.test_review_low_confidence`.
**Outcome:** Success. The recovery flag now surfaces in both the primary command help and the alias help, and the focused tests passed.
**Insight:** If a recovery flag matters during operator use, expose it in the subcommand description so `format_help()` shows it on every entry point.
**Promoted to Lessons Learned:** Yes

---

### [2026-05-17] Tightened Step5 selected-id contract test

**Context:** Compound Autopilot picked the existing Step5 contract plan, which called for verifying the rebalance path does not drift toward 0-based local-id handling.
**What happened:** Reworked `tests/test_step5_contract.py` from a passive output word-id check into a mocked Step5 run that forces LM selection, asserts `ScoringOutputMode.SELECTED_WORD_IDS`, asserts exact expected item count, verifies progress has one selected id and no `0`, and checks the output level update matches the selected word.
**Outcome:** Success. Focused Step5 contract test and full unit discovery both pass.
**Insight:** No new reusable lesson; this reinforced existing Step5 local-id contract guidance.
**Promoted to Lessons Learned:** No

---

### [2026-05-19] Added PR CI for compound gate

**Context:** `make gate` blocked on this repo because GitHub reported no PR checks for the branch.
**What happened:** Added `.github/workflows/ci.yml` with a pull-request test job that runs the documented unittest command, then verified locally with `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'`.
**Outcome:** Success. Local tests pass; the branch now has a workflow for GitHub to report in the PR status rollup.
**Insight:** Compound gate cannot turn green for a repo with an open PR and no GitHub Actions workflow because the PR status rollup stays empty.
**Promoted to Lessons Learned:** Yes

---

### [2026-07-13] Reduced Compound unittest progress noise

**Context:** Compound local-green used unittest verbose mode for the full suite, producing hundreds of per-test lines even when successful.
**What happened:** Changed the central roster command and preferred-check hint from `-v` to `-q`. Project CI remains unchanged and failures still retain unittest tracebacks and summaries.
**Outcome:** Focused runtime-config and quiet/full-suite verification passed.
**Insight:** Runner verbosity belongs in central orchestration when project CI already uses a concise command.
**Promoted to Lessons Learned:** No

---

### [2026-08-04] Migrate repository to Rarity Classificator

**Context:** Git transport for `word-rarity-classifier` was disabled, so the repository was recovered into `rarity-classificator` from a verified full-ref bundle.
**What happened:** Updated the product title, current repository ownership references, and downstream links to the already-migrated `propozitii-absurde` identity. Preserved the Python package and CLI name `classificator` as the stable executable contract.
**Outcome:** Success. Ruff and all 372 unit tests pass from the replacement repository.
**Insight:** A repository rename should update current integration-boundary documentation while preserving stable CLI/package identifiers and historical iteration records.
**Promoted to Lessons Learned:** No

### [2026-09-07] Complete JSON distribution acceptance

**What happened:** Added executable known/empty distribution and CLI JSON acceptance tests, alias coverage, and an exact legacy text-output assertion. Reused the existing distribution accumulator during CSV traversal instead of expanding counts into a second list of individual levels.
**Verification:** New no-re-expansion regression failed before the fix; all 35 focused tests passed after. Container-isolated local-green passed Ruff and all 437 unit tests.
**Insight:** A changed test file is not proof of added coverage; assertions must exercise the promised behavior. JSON serialization needs only five aggregated counts, not another per-row allocation.
**Promoted to Lessons Learned:** No

### [2026-09-13] CSV-safe dry-run preview

**What happened:** Replaced comma joining with standard CSV serialization for the
three-row dry-run preview. No output files written; normal export unchanged.
**Verification:** Regression tests failed for comma/newline fields before the fix;
13 step1 tests pass after. Actual container local-green: Ruff and444 tests PASS.
**Insight:** Preview correctness needs escaping coverage even when happy-path output passes.
**Promoted to Lessons Learned:** Yes

### [2026-09-25] Recover chained quality-audit coverage with valid fixtures

**What happened:** Reproduced the recovered test failure: a generic mocked CSV
repository had no level headers, so the passing case failed before the audit.
Replaced that uncommitted recovery design with isolated temporary CSVs, the real
repository and quality audit. Only the network-backed rebalance step is replaced.
Covered passing output, independent Jaccard rejection and anchor rejection, plus
the final candidate path and threshold forwarding. Production checks unchanged.
**Verification:** Recovered fixture failed as expected. Three replacement tests
pass; an in-memory counterexample that ignores failed audits causes both negative
tests to fail. Container local-green: Ruff and all 451 tests PASS.
Expanded verification with pytest found six pre-existing failures among 499
tests (493 passed): three fuzzy-matcher expectations contradict current behavior,
three JSON-repair tests constrain incidental whitespace. These function-style
tests are not collected by the current unittest-only roster and CI commands.
Runner migration needs a separate requirement/test audit; no unrelated semantics
changed here. This is a verification gap, not a fully green complete test suite.
**Insight:** Gate tests need fixtures satisfying earlier validations; replacing
the gate itself with a canned result cannot prove its threshold behavior.
**Promoted to Lessons Learned:** Yes

## 2026-09-29 — Complete verification and fuzzy identity contract

Maintenance-reserved Word; no concurrent cron edit. Baseline full pytest:
494 passed / 6 failed / 23 subtests. Three matcher assertions used incorrect edit
distances; three JSON repair assertions constrained incidental whitespace.

TDD: new matcher/parser regressions initially 3 failed / 4 passed. Proven defect:
the prefix shortcut accepted distance-four `abcdef`/`abxyzw`, assigning an
unrelated response score to the pending word. Initial import e4fe441 establishes
the original normalized distance <=2 contract; restore it through the existing
distance helper, preserving legitimate typo recovery and strict Step5 unchanged.
Correct mathematical expectations; use parsed JSON values where valid. Replace
repeated shortcut-specific tests with explicit distance cases and parity checks.

One project-owned `python scripts/check.py` now runs Ruff and full pytest, used
by CI and requested for Compound local-green. Project pytest configuration
discovers both unittest classes and function tests; updated stale planner advice.
Removed redundant 8b536b1 mocked audit test: existing real-CSV tests already prove
all eight steps, final candidate path, forwarded thresholds, independent Jaccard
and anchor rejection, and passing output. No production gate weakened.

Verification: Ruff PASS; 536 pytest tests +23 subtests PASS. AST-to-pytest
collection audit: all 27 standalone test definitions included (parametrization
expands these), 536 total items. In-memory audit-bypass mutant killed by both
negative real-CSV tests (2 failed / 1 passed). Check-command tests prove lint
fail-fast and propagation of pytest exit5/no collection. No live DB/model calls.
Host legacy .venv Python points into unavailable Xcode runtime; tests used an
isolated container /tmp venv with already-declared dev dependencies instead.
Architecture decision: docs/adr/001-complete-project-verification.md.


## 2026-10-15 — Repair eight whole-codebase review findings

User requested all eight fixes, regressions, push and PR, conditional on GitHub activity.
Verified repository unarchived; PR #79 merged 2026-10-14 22:12 UTC (2026-10-15
01:12 Europe/Bucharest), with daily merged PRs during the preceding week. Started
from latest origin/main dc98588 on codex/fix-review-regressions; original dirty
checkout preserved.

Red-to-green fixes at existing public boundaries:
- Step1 consumes actual BaseWordRow attributes, including sort/null/dry-run paths;
  real WordStore with only DB connection mocked round-trips escaped CSV data.
- Successful flock no longer raises; contention handled through BlockingIOError;
  real lock tests cover normal release, exceptions, interruption and rejected handles.
- Nontrivial Step5 batches no longer pass unsupported rng to selection helper.
- Selector rejects malformed counts, duplicate/foreign/nonpositive IDs and wrong
  levels before assignments/checkpoints. Removed random auto-fill/truncation.
- Both upload modes require reference/anchors and finite 0..1 thresholds, rerun
  all three semantic gates, and block before DB access on invalid configuration
  or independent Jaccard/precision/recall failure. CLI defaults now match API.
- Audit follows final_level > rarity_level > median_level, allowing actual Step3
  and Step5 output while retaining source-level provenance.
- Forced scoring atomically persists complete replacement snapshots per batch;
  strict duplicate loading retained, unprocessed/failed/unrelated rows preserved.
  Interruption and atomic-replace failure tests prove readable partial progress.
- Removed duplicate empty TestStep4Upload; restored nine integration tests. Added
  collection regression and Ruff F811 to prevent silently shadowed definitions.

Surprises flagged to user: previous suite passed despite fatal orchestration bugs;
old Step5 test explicitly demanded truncation contrary to AGENTS. Corrected those
expectations rather than preserving the broken behavior. Original repros already
proved causes, so exploratory hypothesis/instrumentation phases were unnecessary.

Verification: each regression observed failing before its corresponding fix.
python scripts/check.py on Python 3.11.16: Ruff PASS, 691 tests +34 subtests PASS.
No live database/model calls. README/Runbook show mandatory upload audit inputs.
Force mode intentionally trades per-batch full-CSV rewrites for crash-safe recovery;
ordinary scoring retains append persistence.

Publication correction: a source-only push inherited the upstream main destination
and advanced main to 01d5752. Preserved that commit on the intended PR branch.
GitHub rejected a lease-protected force rollback; restored the original source
tree with normal revert 287d3a7 (tree verified identical to dc98588), then reapplied
the fixes on the PR branch. No repository rules changed. Subsequent pushes use
explicit full source:destination refspecs and matching branch upstreams.

## 2026-10-16 — Sequential D1 adapter and offline Romanian evaluation

Implemented accepted plan using Matt Pocock TDD, implement, codebase-design and
code-review workflows. Base: origin/main 7ccddb9 after merged PR80. Work isolated
in /tmp/word-rarity-fixes on codex/d1-evaluation-adapter; original dirty checkout
preserved. No model loading/inference, database access or upload.

Delivered explicit inventory/evidence preparation, Unicode/family collision
splits, blind labels, optional local wordfreq export, strict System One scorer,
chat/frequency adapters, durable per-ID campaign records and CSV projections,
resume fingerprints, experimental Step2 opt-in, and offline paired gold reports.
D1 HTTP requests blocking/sequential; preflight requires already-loaded decision
instance, aborts on metadata changes; malformed distributions fail explicitly.
Human labels barred from evidence columns. Missing frequency remains censored
coverage, never automatically L5. Confidence means max class probability, not
calibrated accuracy. Existing chat default, Step5 and upload gates preserved.

TDD: observed red/green for adapter distributions/loading constraints, artifact
resume/incompatibility, dataset joins/collisions, evaluation metrics and CLI
integration. External HTTP and optional corpus mocked; real temporary files.
Architecture review found retry write amplification and quadratic ID validation;
regression reproduced 101 predictions.csv writes for 100 retries, fixed to <=2.
Evidence IDs now materialized once. Raw response payloads remain on disk rather
than accumulating in the campaign working set. DEX full-page cache size (~1.3GB)
was a surprise flagged to user and shaped streaming extraction.

Validation: Python 3.11.16, python scripts/check.py: Ruff PASS; 785 tests and
98 subtests PASS. Implementation/ADR/runbook/plan record known limitations:
authoritative inventory and human gold still needed; no live protocol/accuracy
claim; no fitted hybrid, calibration, weighted/subgroup reporting, or automatic
promotion. Next: freeze 150-word pilot/rubric, blind labels, then explicit live
smoke/ablations when RAM permits. Additional principles recommended: high
cohesion/low coupling, explicit dependencies, composition and reproducibility.


## 2026-10-21 — Exact-form/all-POS contract and offline frequency comparison

- Recovered PR81 f990e6c sources into isolated `build/d1/exact-form-code`; primary
  checkout main lacked experimental modules and contained unrelated dirty files.
- Read Matt Pocock TDD and project lessons; planner supplied read-only seam/source
  review. Red/green slices: CSV exact-form contract, nested label/identity rejection,
  scorer request target, rebus extraction, paired development report, offline CLI,
  source policy/hash checks and extractor provenance. Existing BatchScorer retained.
- Frozen150 exact targets /218 lexical contexts. All LOC entries and curated POS
  retained; inventory POS nonrestricting. No fabricated sense labels or added targets.
- Reused frozen wordfreq3.1.1; streamed12,728 rebus cache records, excluding60 target
  pages and147 non-ok records;114,689 unique definitions /1,280,002 tokens. Repeated
  full extraction yielded identical frequency CSV bytes.
- Compared37 clarified development labels, excluding113 opaque labels:29 observed
  each,26 paired,32 union; paired Spearman0.451(wordfreq)/0.536(rebus). No threshold
  fit or independent accuracy claim; rebus missing all4 L5 forms is material.
- Review found source-identity validation and extractor fingerprint gaps; regression
  tests demonstrated failures before fixes. Final Ruff +792 tests /108 subtests pass.
  Verified34 current/previous artifact, input and implementation hashes; original
  latest annotation import unchanged. D1 never loaded/contacted; tests simulate HTTP.
- Plan/results/docs updated: retain separate frequency signals, next independent
  held-out labels before thresholds/hybrid; no renewed172-context request. D1 later,
  sequentially, conditional on RAM. Implementation retained as a separate Git branch;
  primary checkout code left intact. No remote push or production upload.
