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


## 2026-10-21 — Publish exact-form frequency evaluation

- User requested push and PR for `codex/exact-form-frequency-evaluation`.
- Confirmed clean implementation checkout at085e71d and open PR81 headf990e6c.
- PR base: `codex/d1-evaluation-adapter`; dependency explicit, avoiding duplicate
  adapter changes in the review. Includes implementation, comparison results and
  updated plan. Prior validation:792 tests /108 subtests and Ruff passed; no code
  changed since validation. D1 remains unloaded.

## 2026-10-23 — Independent40 blind round and frozen calibration

Prepared40 unseen forms/70 contexts, deterministic frequency strata, collision and
conservative family exclusions. Rebuilt rebus corpus excluding union190, fit only
37 clarified pilot labels; froze190 predictions before annotation. Rebus has no
observed pilot5: final boundary explicitly conventional. True blind public payload
and separate storage namespace; old answers intact. TDD public APIs/UI, then
format/review; note-clearing regression first failed and then passed. Ruff and795
tests/112 subtests passed; browser QA rating/context/notes survive reload. D1 not
loaded/contacted. Updated protocol/plan; held-out comparison awaits user's round.

## 2026-10-23 — Withdraw additional annotation workload

User clarified they will not evaluate another batch after the150-word pilot.
Withdrawn40-card round from required work; retained all artifacts/answers unchanged.
Plan now reuses150 existing latest labels, separates37 clarified from113 opaque
initial targets, and recommends fold-local calibration for internal comparison.
No new annotations requested, no AI estimates promoted to gold, no D1 load.
Documentation-only correction; no code/tests changed.

## 2026-10-23 — Frequency cross-validation on existing annotations

Implemented public CSV orchestration with existing frozen calibrator:37 LOO folds,
113 separate historical diagnostics, no mixed-rubric total accuracy. TDD red missing
module→green; added source-conditioned median red→green. Mutating held-out truth
does not alter its own prediction/baselines; opaque truth changes cannot affect CV.
Verified150 identities,37 train-ID exclusions, all hashes and metric arithmetic.
Matched26 MAE0.538/0.500; surprise: source-conditioned constant1 baseline also0.500.
Own source coverage29/37; rare coverage3/8 vs2/8. Explicitly report this selection
limitation; no frequency-only replacement. Added baseline diagnostic after initial
run without changing frequency predictions; retainedv1, finalv2. Updated report/plan.
Ruff +796 tests/112 subtests pass. No model calls/loading, no new annotation asked.

## 2026-10-23 — Baseline inventory and full150 scope clarification

Confirmed150 latest human scores,150 frozen legacy DB scores,150 original assistant
estimates and149 first-independent initial ratings.37 is the explicitly clarified
subset, not the number of available evaluations. Proposed operational comparison
on all150 with original/latest-label views and37/113 breakdown, explicitly retaining
mixed-target limitation. Prioritize frozen legacy/assistant comparisons, then
constant/frequency baselines and a small regularized combined-feature model using
fold-local preprocessing/fitting. No new benchmark or model executed in this Q&A;
no D1 loaded and no additional annotation required.

## 2026-10-23 — Full150 historical and learned baseline suite

User authorized all proposed baselines. Reused150 labels in two separate views;
added149 first-independent learned CV because original initial_level is exposed
round-final, not first response.449 folds, shared frozen source evidence; no D1.
TDD CSV seam: initial red→green; independent-view red→green; holdout label mutation
leaves its model unchanged. Optional sklearn extra and CI installation added.
Latest150 Ridge MAE0.533 vs legacy1.740; independent149 Ridge0.671 vs AI0.557 and
legacy1.685. Recommend Ridge experimental baseline, not production replacement.
Missingness selection remains material (25/29 fully missing forms rare).
Surprise verified: original-final median LOO has0 exact due75/75 boundary split.
Preserved initial two views byte-identical when adding independent149; finalv2.
Audit449 train exclusions, imputation/scaling, hashes, CSV arithmetic;797 tests
+112 subtests/Ruff pass. Reports, plan and stale annotation guidance updated.


## 2026-10-24 — Mandatory100% coverage baseline comparison

User correction: no unclassified forms in operational comparison. Extended the
existing CSV evaluation seam with source-specific missing-training-group lower
median fallback; empty subgroup or unavailable threshold model uses global training
median. All calibration excludes held-out labels. Primary operational summary
requires complete integer1–5 predictions; raw abstentions retained diagnostically.

TDD red: missing completion columns; green. Next red: missing route summaries;
green. Regressions cover missing-group vs global fallback, missing model, zero/blank,
all-missing data, no held-out-label leakage in3 views, full-denominator MAE and
preservation of source predictions. Ruff +800 tests/115 subtests pass.
449 folds run offline. Independent script and planner audit verify support, medians,
completeness, arithmetic, hashes and unchanged old prediction columns.

Latest150 MAE: wordfreq+fallback0.520, Ridge0.533, rebus+fallback0.680; all150 scored.
Fallback counts49/40, all learned4. First-independent149:0.624/0.671/0.805.
Surprise flagged to user: wordfreq wins MAE by only2 aggregate error points while
Ridge has fewer large errors and wins the clarified37 slice; no broad winner claim.
Recommendation: simple complete wordfreq baseline, Ridge challenger; next robustness
checks on missingness alone and lexical families using existing labels. No new user
annotation, D1 loading/inference, production change, upload or push.
Artifacts: build/d1/complete-coverage-baselines-2026-10-24/. Report and plan updated;
prior output directories preserved. Changes maintained in exact-form-code clone;
root's unrelated dirty work preserved.


## 2026-10-24 — Presence-only and grouped robustness checks

Implemented at existing full-pilot CSV seam: source-specific presence medians,
ordered two-bit presence-pattern median, global train median for unseen patterns;
optional exact-reference groups CSV with complete group exclusion before all fits.
Fail-fast group validation includes each label view. Per-form artifacts retain
held-out group/members, training support and complete integer scores.

TDD red/green for missing presence columns, then grouped API. Regression checks:
family-wide label changes cannot alter that family's fits; singleton equivalence;
source-bit identity, numeric-magnitude invariance, unseen patterns, invalid maps.
Ruff +804 tests/122 subtests pass.898 prediction records independently audited,
including group support, medians, Ridge train preprocessing, metrics and hashes.
Planner review found no actionable defect.

Frozen8 pair groups: original6 preserved, cover/discover and Europe-related links
added using dictionary evidence. Candidate iț/ițar link not established by exact
cached meanings; excluded rather than merging by prefix. Latest142 groups,16
paired forms; first-independent142 groups,14 paired forms. Grouped426 unique
training exclusions across3 views,449 per-form records; LOO449 more.

Latest grouped MAE: wf+fallback0.520, Ridge0.533, joint-presence0.587, rebus0.693;
source-presence0.767/0.867. Numeric values help; only16 forms exercise different
training sets. Surprise flagged: joint-presence matches Ridge0.664 on first149;
more complexity not consistently useful. No production-quality claim.

Report/plan updated: retain complete wordfreq baseline, Ridge comparator; next
freeze offline scorer/config and shadow-export full inventory with provenance.
No parameter search, extra human annotations, D1/model calls, production upload,
remote push. Artifacts build/d1/robustness-baselines-2026-10-24/; previous results
preserved. Root unrelated changes untouched; docs/logs mirrored from code clone.


## 2026-10-24 — Frozen offline wordfreq scorer and full inventory CSV

Implemented plain CSV freeze/score APIs, two lazy CLI handlers and optional pinned
wordfreq extra. Kept FrequencyScorer's old abstaining behavior. New workflow binds
source to exact inventory and corpus, freezes config digest/support/thresholds,
records every score's frequency/route/version, preserves all IDs/POS and publishes
atomic staged outputs without overwriting. Runtime does not refit.

TDD red/green: source-policy/corpus provenance, freeze/replay API, CLI command.
Negative and edge tests: corrupted metadata/config, wrong inventory/version,
malformed frequency never becoming fallback, duplicate/invalid labels/IDs,
no missing/no observed training examples, threshold equality, diacritics and
repeated POS. Ruff +811 tests/137 subtests pass; architect found no actionable flaw.

Frozen on latest150:101 observed/49 missing, fallback4/global median2. Source
values equal previous experiment for all150. Config version8f3061e2332cf9d6844ff4ea9dabd4fd23111c04b713a8a0cde886a23c82e0cc.
Full saved inventory77,698 rows/75,147 forms:11,610 direct,66,088 fallback85.06%.
Histogram1..5=972/6283/4355/66088/0. Surprise flagged: fallback dominates compared
with pilot32.67%; positive frequency floor exceeds rare thresholds, so no5.
Do not promote or manufacture a histogram; keep shadow baseline, prioritize
additional evidence for missing/rare forms. Plan and ADR updated accordingly.

Actual CLI run and byte-identical replay blocked requests.Session.request and
psycopg.connect. Independent audit checked all scores/identities/routes/support,
same-form POS consistency, hashes and summary arithmetic. No DB access/write,
D1 loading/inference, production upload or remote push. Artifact directory:
build/d1/offline-wordfreq-2026-10-24/; tracked config in configs/. Root's unrelated
changes preserved; docs/logs/config mirrored from implementation clone.


## 2026-10-24 — Local source audit for fallback4/5

Read-only audit of classifier/generator-rebus/propozitii-nostime local artifacts,
using Matt Pocock research skill/background source researcher. No product code,
config, frozen scores, DB/API or model loading changes.66,088 fallback rows =64,226
forms. LOC covers all.12,728 DEX payloads streamed/hash-checked; frozen1,273,283
corpus tokens and190 prior counts reproduced. Initial span-count check found one
empty structural span; retained for exact compatibility, zero token effect.

Broad-cache exact-query pages7,334 rows, outside-own-page mentions13,991. Added117
prior-review snapshots: combined pages7,375 rows, union positive evidence18,769
rows/17,898 forms;47,319 rows lack both. Supplemental snapshots give all49 pilot
missing-wordfreq forms raw lexical material. Query match is not sense validation.

Validated traps: menu labels trigger regional/archaic HTML regexes; lexical page
hints can describe another meaning/reference. Generator rarity is inherited and
43,890 exact-match rows disagree with classifier legacy snapshot. Installed ro
wordfreq has no large list; curated/generated clues are not independent use counts.
Minimal CASA status-ok HTML41chars has unverified provenance; not silently removed
from the frozen corpus. Source researcher/count scripts independently cross-checked.

Tail49 latest existing grouped predictions: constant4 MAE.653,severe2; presence
pattern.592,severe6, only16 correct of29 predictions5. Gain vanishes on first
responses. Reported to user; no absence→5 rule justified. Recommended uniform
sense/POS-aware raw-source extraction, then one small interpretable fallback test
on existing labels, preserving100% coverage and unknown→4. Eleven tail labels are
2/3, so do not force a binary4/5 target. No extra annotation needed for this step.

Saved full/combined evidence CSVs, source ledger, scopes, diagnostics, verification
and reproducible scripts under build/d1/local-source-audit-2026-10-24. Verified
77,698 identities, hashes, summaries, all49 raw snapshots and merged coverage.
Updated research note, plan and evaluation guide; root docs/logs mirrored. No
production tests rerun because classifier code/config unchanged. No remote push.


## 2026-10-25 — Local evidence implementation preparation

Read lessons and Matt implement/TDD/code-review instructions; planner/architect
subagent inspected local HTML and evaluation seams. Proposed two public CSV
boundaries; explicit confirmation requested per TDD skill, pending. No tests or
production implementation started before confirmation. Predeclared one depth2
median-leaf fallback and leakage controls in local-fallback-2026-10-25 protocol.
Structured headings support exact forms/explicit inflections/all POS; redirects
stay unresolved, parent tags inherited. Fold-fitted wordfreq required to avoid
using all150-trained frozen configuration in held-out metrics. Plan updated with
pending implementation, not claimed results. No D1, DB, frozen artifact changes.

## 2026-10-25 — Local lexical evidence implementation and experiment

User confirmed both CSV test seams. Vertical TDD: exact/all-POS source export;
scoped/inherited tags and exclusion guards; inflections/multiple headings/redirects;
input hashes/schema/identity and atomic output; LOC gender/transitive codes;
CLI offline integration. Evaluator agent used TDD for fold-local thresholds/tree,
unknown→4, complete coverage, group-label mutation invariance,4/5 metrics and strict
artifact contracts. Two modules and offline commands; frozen scorer untouched.

168 sources/134 pilot forms;150 evidence rows,123 aligned (42/49 tail),7 tail unknown.
Predeclared depth2/minleaf5 tree evaluated on latest150, original150 and first149.
Latest MAE.520→.500 but severe11→12 and clarified37.568→.595; first149.624→.671.
Tail predicted5 precision13/24=.542, false5=8human4+3human3; only mention-count
feature selected. Recommendation: keep frozen4; investigate independent running-text
corpus coverage/provenance, no extra annotation or pilot tree search. Report/plan/ADR
updated. Full826 tests/157 subtests +Ruff pass; HTTP/DB blocked in integration/run.
Independent code review and final artifact verification next. No D1, DB or push.

### 2026-10-25 — Review fixes and final verification

Spec review passed. Standards review found bare mention CSV lacked corpus contract;
added mandatory schema/policy sidecar, input/ref hashes, corpus→ledger binding and
per-row agreement with audited derivation. New public-export TDD regression slices.
Independent artifact reviewer found plural-only ițar/zar sense alignment defect;
added explicit number gate, literal plural/invariant witnesses, child singular
scope override and nonexclusive preference handling. RED→GREEN regression;19
sense rows corrected (16 distinct pairs), no change to the three prediction CSVs.

Final832 tests/173 subtests and Ruff pass. Independent audit449 folds/126 trees/
36 metric slices/168 source hashes passes. Guarded real CLI replay457 data artifacts
byte-identical. Frozen model/input/export hashes unchanged. Final artifacts in
local-fallback-2026-10-25/evidence-final andcomparison-final; manifests, projection,
protocol, verifier and replay scripts retained. Plan/report/ADR updated. No open
review findings. No D1, database access, production promotion or remote push.


## 2026-10-25 — Romanian running-text corpus access and licence investigation

Used Matt research skill plus background primary-source researcher. Inspected
CoRoLa, Leipzig, SETIMES, ParlaMint, FineWeb2, CulturaX, OSCAR, CC-News, roTenTen and
wROdfreq. Bounded anonymous probes verify FineWeb2 metadata/files/range/viewer,
CoRoLa frequency ZIP segments, Leipzig exact-word API and SETIMES archive range.
No full corpus download, gated-term acceptance, provider contact, D1 or DB access.

Recommendation: bounded cross-shard FineWeb2 coverage experiment, recent crawl
slice separately; ODC-By+Common Crawl rights recorded. CoRoLa optional eligible
NC diagnostic. Surprises: OSCAR explicitly suspended, current full ParlaMint lacks
RO despite project existence; FineFreq counts characters, not words. wROdfreq data
binaries/licence not verified. New Common Crawl data is not automatically independent
of wordfreq. No measured new inventory coverage or 4/5 improvement claimed.

Research note and plan updated; protocol keeps all66,088 rows/64,226 forms, existing
150-label strata, fold-local calibration and unknown→4. Frozen scorer/config/export
unchanged. Documentation-only checks; production tests not rerun. Probe receipts in
build/d1/romanian-corpora-research-2026-10-25. Root mirrors receive only new sections,
preserving divergent historical logs. No remote push.

Independent research review: no blocking source/licence findings. Clarified observed
vs valid uses, unverified prefix recency and sample-only inference; require row-group
sizes/selection probabilities before extrapolation. Markdown diff checks pass.


## 2026-10-26 — FineWeb2 implementation preparation

User authorized bounded TDD experiment,100k examined docs or1GiB transfer, lowdisk,
150-label comparison; no D1/DB. Read lessons, implement/TDD skill and planner/architect
instructions; background planner reviewed architecture. New HTTP→CSV seam confirmation
pending; existing CSV evaluation seam retained. No tests or production code written.

Disk57GiB free at start. Installed pyarrow21.0.0 into existing active-clone venv via
uv --no-cache (29.8MiB reported); conservatively reserve40MiB inside total1GiB. Prepared
input inventory/shard snapshot and protocol under build/d1/fineweb-2026-10-26. Planned
durable pre-request reservation, strict206 range checks, sequential sampling across
20shards,5GiB free-space floor, sample-only frequency claims and fold-local comparison.
No corpus downloaded, model loaded or database accessed. Await seam confirmation
before RED→GREEN implementation, per explicit TDD skill requirement.


## 2026-10-27 — FineWeb2 bounded implementation and experiment completed

User confirmed HTTP→CSV andCSV→comparison seams. VerticalTDD; source/sequential
transport/evaluator andtwoCLIcommands. Optionalpyarrow21.0.0 pinned. Stricttransfer/
docattemptreservations,resumeidentity,5GiBdiskfloor,64MiBrange/128MiBdecompression
limits, exacttokens/dedup/sourcefilters,completeinventoryCSV andtemporalstrata.

Review found realRequests Session redirectdrain despiteallow_redirects=False;
headers-firstHTTPAdapter transport plusrealResponseregression. Checkpointintegrity
anddisk-recoverypublication regressionsfixed.860tests/200subtests+Ruff pass; no
remainingblockingstandards/specfindings. Samplingdescriptiveonly; no numeric
wholecorpusinclusionprobability claim.

Run100,000docs/20shards:385,836,138bytespayload,436,626,538charged incl40MiBdependency
reserve;1080requests/0pending.70,255primarydocs/35,932,359tokens,olderseparate.
No fullcorpuscache; experimentartifacts~180MiB. Full77,698rows exported. Missing
66,088rows:25,211observed,12,110supported. Pilotmissing49:24observed,8supported,
noneof8human5. Thusminimum10trainingrows nevermet; all449candidatepredictions
identicalbaseline. Latest150MAE.520/11severe; tail49.653/2severe; first149.624/13.
Tail4vs5all4,19/38correct; no validatedimprovement. No posthocfloorrelaxation.

Label-blind20form+8pilotconcordanceaudit confirmedwebnoise/copiedpassages/brands
andoldpublicationrecentcrawl. Recommendkeepfrozen4; CoRoLaeligibleNCfrequency
lookupnext, morecleanrareclasssupport beforecalibration; qualityhandlingbefore
largerwebsamples. No newuserannotation,D1orDBaccess.

Independent sourceartifactaudit and449fold/36metricrecomputationpass; baseline
paritywithpreviousrun. Realcompletedsource replay underHTTP/DBblocks byteidentical.
Frozeninventory/input/scoreshashes unchanged. Researchreport,plan,guide,ADR updated;
rootmirrorsappendonly. Localcommits; no remotes modified.


## 2026-10-28 — CoRoLa noncommercial exact-form experiment

- User authorized noncommercial research; reused approved CSV seams and Matt TDD/
  implement/review workflow. Task-start baseline a02963f; code commit abd5554.
- Pinned protocol before counts: count≥5, minimum10trainingforms/twolevels,
  grouped monotone fallback for wordfreq-missing forms; otherwise4. No tuning.
- Downloaded114,091,202-byte ZIP, verified publishedMD5; extracted only23,732,979-byte
  lowercase word-form TSV, verifiedCRC/SHA. Local campaign~141MiB, free~88GiB.
- Parsed1,813,746entries, denominator637,764,339. Surprising distinction: published
  filtered-list token total is smaller than headline corpus size; use exact listsum.
- Exported77,698IDs. CoRoLa coverage144/150; latesthuman5=16/22observed,10supported.
  Missing-wordfreq49:43observed,35supported including7human5. Inventorytail66,088:
 49,464observed,37,614supported. Preserved allPOS and original labels.
- New source/evaluation CSV adapters; private grouped engine shared withFineWeb.
  No production scorer integration. RED/GREEN for source integrity/counts/normalization
  and public evaluation support/group-label invariance. Full871tests+211subtests,
  Ruff and two-axis code review pass.
- All3labelviews compared at100%scorecoverage. LatestMAE.520→.533,severe11→13;
  first-independentMAE.624→.617,severe13→15; originalfinalMAE.707→.700,severe18→19.
  Latest6changes4→5:2corrections,2newone-levelerrors,2newtwo-levelerrors.
- Independent stdlib verifier recomputed rawsource/projections/coverage,449folds,
  554fittedmodels with independentDP,36metricslices. All449baselinepredictions
  matchpriorFineWeb; frozenconfig/scores/inputs unchanged. HTTP/DB blocked offline.
- Recommendation: keepwordfreq+4; next local diagnostic audit9changedforms plus
  ata/carter/dorian; no newannotation or thresholdsearch. RestrictsourceandderivedCSV
  tolocalresearch. Updated report/plan/ADR/runbook; mirrored docs to rootworkspace.
- No D1 loaded, DB access/writes, remote push or PR. Artifacts:build/d1/corola-2026-10-28/.


## 2026-10-28 — Local CoRoLa divergence audit

- Audited9cross-view divergences plusata/carter/dorian using saved evidence only.
  Produced12-case CSV ledger,35fold diagnostics, raw lexical witnesses, human-history
  linkage, saved-context extracts, case-frequency diagnostic and492input hashes.
- Read case-preserving member inside existing ZIP locally, no newdownload; all12
  target sums match primarylowercase counts. Surprising member-total difference2725
  confirmed independently; primarydenominator/scoring unaffected, cause unknown.
- Found exactcount collisions20antereu/diorit withlabels3/5 and18clevetitor/xilem
  withlabels4/5; fold cutoff instability is not evidence of heldout-label leakage.
- Existingratings resolveantereu3,sezisa3,ițar4,ata5,carter5. Preserve opaque
  labels/provenance; no synthetic per-sense labels or requests for further review.
- Raw sources explicitly attestantereu/sezisa/ata while prior lexical extractor
  leaves themunresolved. Ata requires target femininePOS/atu-source relation,
  never ață accentfolding. Evidence extraction improvement is separate from scoring.
- CoRoLa carter93.1%/dorian98.9%uppercase; savedFineWeb shows names. No corpuswide
  namefraction inferred. Hipochinezie10/12uppercase refutes blanket casing exclusion.
- Independent auditPASS:492hashes,12cases,35folds,16witnesses,bothZIPmembertotals,
  labelminima/countreconciliation. No productioncode changed; fullsuite not rerun.
- Updated report and plan; next general lexical evidence repair + provenance and
  separate ambiguity metadata. Keep frozenwordfreq+4; no threshold tuning or
  per-wordexceptions. NoD1, DBaccess, newannotations, remote push or PR.
- Artifacts:build/d1/corola-divergence-audit-2026-10-28/. Rootdocs mirrored; logs
  append-only and existingsource/score/input hashes verified unchanged.


## 2026-10-28 — Source-scoped lexical variants, evidence-only TDD repair

Implemented in build/d1/exact-form-code on codex/independent-form-benchmark.
Public CSV TDD: explicit declarations, target POS/gender, usage/number scope,
dictionary/entry witnesses, negative ambiguity cases; new variants ledger and
additive sense provenance. Real-source replay exposed closing delimiter + etymology
in one HTML node; RED/GREEN fix. Spec review exposed conflicting raw-meaning POS;
RED/GREEN fix, review closed. Standards review had no actionable findings.
Final checks: 880 tests + 220 subtests, Ruff, independent source/hash verifier PASS.
150 forms / 169 source records; 14 new exact records / 12 distinct form–sense pairs;
123→127 aligned forms, tail 42→45/49. All 978 old exact senses retained.
Four changed evidence forms: antereu, sezisa, ata, văietare. 1,150 protected input
hashes unchanged. No new evaluations, scoring, network, D1 or DB access.
Final campaign output: build/d1/lexical-variants-2026-10-28/evidence-reviewed/;
verification-reviewed.json. Earlier output candidates retained, not authoritative.
Plan/report/ADR/runbook updated. Retain frozen wordfreq+4; use evidence for
explanations; unsupported formats and robust 4/5 separation remain. No push/PR.

## 2026-10-29 — Publish accumulated offline work; map code before Omni target update

User requested push/PR of local commits plus reproducible Graphify map, then switch
active evaluation target to installed d1-omni-2b. Active implementation checkout:
build/d1/exact-form-code, codex/independent-form-benchmark; PR stacked on existing
codex/exact-form-frequency-evaluation (#82) because offline experiment dependencies
were still local. Historical scores/results retained.
Graphify tools advertised but list_repositories/graph_stats returned Unknown tool,
including retry after user plugin mention. Hosted connector needs no Homebrew;
service/index readiness unresolved. Created/validated repository Graphify skill,
installed copy at ~/.codex/skills/graphify. Clearly labeled local AST fallback:
126 tracked Python modules / 381 import-site edges; complete JSON, focused Mermaid,
source hashes, regeneration/staleness/impact commands. Pre-model snapshot saved
before invocation/test edits; post-change graph regenerated. No runtime call claims.
Read-only LM Studio inventory confirmed Omni decision/lfm3/F16, no loaded instances.
Updated active model examples/fresh campaign names; generic adapter unchanged.
Offline tests verify Omni identity, no POST while unloaded, sequential requests,
and rejection of old-model campaign reuse without file changes. No inference/load,
DB operations, score updates or new annotations. 883 tests + 220 subtests, Ruff,
graph freshness, skill validation PASS; all 1,150 protected file hashes unchanged.

Published PR #85: https://github.com/fabian20ro/rarity-classificator/pull/85,
base codex/exact-form-frequency-evaluation (#82). Two-axis current-delta review
passed with no findings; historical lexical correction already reviewed.
Generated JSON graphs marked generated for readable PR review.


## 2026-10-29 — Generate actual Graphify graph from user checkout

Used ~/git/graphify at 0a8cd4e1 (0.9.97); uv frozen runtime-only dependencies in
isolated build environment. Source checkout unchanged. Code-only extraction,
GRAPHIFY_BACKEND=none, no-label clustering; no semantic LLM pass or model calls.
Saved build/d1/graphify-2026-10-29/graphify-out: JSON, interactive HTML, report,
manifest and local-run provenance. Final 2,119 nodes / 6,057 edges / 87 communities.
131 code files scanned; pyproject.toml and thin __main__.py yielded no symbols.
Verified unique IDs, edge endpoints, D1Scorer query and incremental 130-unchanged /
1-added-file extraction. Added reproducible scripts/graphify_local.sh, updated skill
and docs. No D1 load, DB access, score/evaluation changes. Local CLI works despite
hosted plugin Unknown tool; retain distinction and extractor coverage caveats.


## 2026-10-30 — Consolidated 1,000-form / 50-review plan

Published a focused successor plan: exact-form/all-POS evidence, sequential Qwen/GPT
pilot on existing150, frozen cascade with100% score coverage, severe-error/excess-loss
gates, causal audit and at most50 user review cards. Separated prepared candidates
from new model/human validation; retained baseline and explicit unknown confidence.
Added aggregate severity/sample snapshots; kept CoRoLa-derived counts local.
Documentation-only branch stacked on#85; unrelated local code/artifacts preserved.
Verification: cross-checked snapshots, plan links, scope and whitespace; no new model
inference or DB writes. Implementation/testing of proposed stages remains pending.


## 2026-10-30 — TDD exact-form evidence audit on independent 1,000

Implemented public CSV audit + thin CLI, reusing lexical/form exporters. RED/GREEN
covered full identity/POS membership, missing sources, source-scoped parent chains,
hashes and manifest provenance/revisions. Review found empty provenance could bypass
checks; regression added and fixed. 10 new tests/21 subtests. PR-isolated full check:
893 tests/241 subtests + Ruff PASS; byte-identical offline replay PASS.

Local run:1000forms/1146IDs;137exact-querysources,801absent,62wrongspellingexcluded.
130forms with usable contexts (121allLOC-POS sourcebounded,9partial),7source-backed
withoutusablecontext;515usable/418unaligned/1unknownPOS contexts. All1363protected
files unchanged. Independent audit rejoined original frequency sources; scores intact.
Surprise: source availability is much narrower than total frequency-signal coverage;
870forms still lack usable lexical contexts. Next: independent150judgepilot with
explicit missing-evidence strata; no new human review, models or DB writes this stage.


## 2026-10-30 — Reusable sequential Qwen judge pilot (GPT deferred)

Implemented CSV collection/comparison over existing campaign/Outcome seam; strict
JSON/identity/model validation, durable native failures, explicit baseline fallback,
no fabricated confidence. Thin CLIs, fixed provider options/runtime hashes, no DB
integration. TDD public seams:16new tests/43subtests; full909tests/284subtests and
Ruff PASS. Architect caught malformed-message/options mutation issues before inference.

Initial Qwen150:150native,7severe/excess11 versus baseline11/14; withoutsense24 worsened
2→5severe. Discovered older formatter omitted218existing curated contexts/95forms.
Systematic merge, allPOS/restrictions/source provenance. Further review found five
reviewer clauses inside meaning prose; stopped first correction at30completed records,
retained it without quality analysis. Explicit complete218row projection removesonly
those clauses,213meanings unchanged, source/identity/POS checked; originals preserved.

Final corrective150:150native,5severe/excess9,145within±1; exact80,MAE.527. Initial7/11
retained;12scorechangesallamong95changedinputs,55unchangedidentical. True4/5 severe5→2;
missingwordfreq2→1. No-context19 regresses1→3severe/excess1→6. Top8 recovers4/11baseline
severe versus1evidence-only,4falsealarms. Bothpairedbootstrapintervalsincludezero.
Correction is label-exposed development evidence, not independent validation.

Sequential Qwen-only, RAM guard beforeeachcall, preexisting instance preserved.
Finalminmemoryproxy2.94GiB/OSfree16%,~14.5minutes;0reasoningtokens. Independent audit
and offline replay PASS;1721protectedfiles unchanged. Rawtext/records stay local,
aggregate reports/receipts published. No newratings,D1/GPTclassification,DBwrites.
Plan: retain operationalwordfreq+4; Qwen diagnosticcandidate. NextcomparableGPTpilot
uses same finalCSV/prompt; concreteprovidercompatibilityuntested. Address870/1000
missingcontexts before blanketrollout; nocertifiedconfidence or automaticpromotion.
