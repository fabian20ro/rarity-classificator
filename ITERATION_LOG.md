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
