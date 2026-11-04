# Qwen pilot: reusable sequential chat judge

2026-10-30. Existing development150; exact Romanian form, most familiar valid sense
across all valid POS. Primary error: distance >=2; secondary loss: excess over1.
No new human reviews, D1/GPT inference, database access or production score changes.

## Protocol and implementation

Qwen `qwen3.8-27b-splash` (IncoAI Qwen3.8-27B-Splash,4bit) was already loaded.
Preserved its instance: context61696, parallel1. The runner checks exact live identity,
>=2GiB available-memory proxy and >=10% OS free percentage before every request.
One blocking request/form, no retries or repairs. Native failures are recorded;
only the offline comparison can explicitly substitute the frozen baseline.

Fixed Romanian zero-shot rubric, exact identity and strict JSON schema. Options:
`temperature=0,max_tokens=256,reasoning_effort=none`. The backend advertised off/on
but rejected `off` at the Chat Completions boundary; a synthetic preflight established
`none` before any lexical inference. Failed preflight and original protocol retained.
No labels, frequencies, other judges' predictions or few-shot examples enter requests.
Model notes are short hypotheses about usage, never verified causal explanations.

The collector and comparison are provider-neutral CSV interfaces. Existing
`run_campaign` persists checkpoints/raw exchanges; no new orchestration framework.
Evidence schema excludes scores/estimates; responses require exact ID/spelling,
integer1..5, one complete assistant message and the pinned model ID. Duplicate JSON
keys, truncation, refusals, tool calls and invalid content fail explicitly.
No probabilities or confidence are invented. Use predictions.csv; legacy run.csv
is intentionally empty because the upload-oriented confidence requirement is unmet.

[LM Studio's structured-output documentation](https://lmstudio.ai/docs/developer/openai-compat/structured-output)
describes this transport. Concrete GPT model/parameter compatibility remains untested:
reuse the frozen evidence/prompt, pin a served model ID and validate its transport in
a separate campaign. Credentials stay in session headers, never campaign manifests.

## Initial arm and systematic correction

Initial lexical input:126 forms with senses,24 without; two incomplete parent
contexts excluded. This differs from earlier D1 evidence127/23, so it is not a pure
model-only comparison. All150 Qwen responses were valid; no baseline fallback.

After examining errors, we found the older evidence formatter omitted the existing
`contexts` from the exact-form contract. The correction adds **all218 contexts across
95forms**, not just contexts for mistakes. Existing source-derived senses remain.
New coverage:131 with senses,19 without. Prompt, options, labels and IDs unchanged;
a new campaign reruns all150. The initial campaign remains immutable.

These are previously curated, potentially label-exposed contexts, not all human
reviewed or dictionary-verbatim text. Every POS/meaning/example matched at least one
frozen source pack;93 referenced JSON snapshots were checked/reproduced offline.
18 pack references lack an explicit snapshot and retain pack provenance. A code
review found five evaluator-directed clauses inside meaning prose. The first
corrective attempt was stopped after30 completed records, without quality analysis;
it remains under `qwen-judge-complete-evidence-2026-10-30/`, excluded from results.
An explicit reviewed218-row projection removes those five clauses, preserving the
other213 meanings and all POS/restrictions; original/projected text stays in a
hash-pinned provenance ledger. No generic word or rarity blacklist. Only POS
and meaning enter model input; illustrative examples, pack notes, labels, estimates
and source metadata stay outside it. Therefore this arm measures a systematic
pre-existing evidence correction on reused data, not independent confirmation.

## Initial results

| Subset | n | Baseline severe | Qwen severe | Baseline excess | Qwen excess |
|---|---:|---:|---:|---:|---:|
| All |150|11|7|14|11|
| References4/5 |43|5|2|8|3|
| No wordfreq |49|2|1|2|1|
| With senses |126|9|2|11|2|
| Without senses |24|2|5|3|9|
| Clarified references |37|4|3|5|3|
| Initial opaque references |113|7|4|9|8|

Within±1:139→143/150; exact86→78; MAE0.520→0.553. Qwen rescued9 baseline severe
errors but introduced5. All numerical scorer gates passed, but the condition without
senses deteriorated. That matters because870/1000 new forms lack usable contexts.

Primary matched review budget is **top8/150 (5.33%)**: evidence-only recovers1/11
baseline severe errors; Qwen-assisted3/11, with5 false alarms. Top5 per fold means
25/150=16.7%, not50/1000; it is retained only as a secondary diagnostic (2→8/11).
This budget correction was frozen before lexical collection. Detailed POS labels
are counted as distinct labels, not necessarily distinct coarse POS categories.

Paired group bootstrap,5000 resamples: severe-rate delta95% interval
[-0.0795,+0.0258]; excess-mean delta[-0.0878,+0.0523]. Both cross zero. These are
exploratory intervals on reused development labels, not population guarantees.

True5(n22): Qwen predicts3/18/1 at levels5/4/3; the18 predictions4 are acceptable
under±1. True4(n21):9 exact,9 level3,2 level5,1 level1. No specialized4/5 fitting.

## Reproduction and verification

Local immutable campaigns, relative to the original workspace:

- `build/d1/qwen-judge-2026-10-30/`: initial protocol,inputs,runtime,raw records,
  comparison, paired analysis, source snapshots and independent verification.
- `build/d1/qwen-judge-curated-2026-10-30/`: corrective merge manifest,
  source provenance and a separate full campaign using the same prompt/options.

Each campaign's `run.py` enforces RAM/model checks and sequential calls; `evaluate.py`
performs offline comparison and paired analysis. `replay.py` reuses saved HTTP
responses with network/DB blocked and verifies identical request payloads, outcomes
and comparison artifacts. Source artifacts/dictionary texts stay local; only aggregate
reports and hashed receipts belong in this PR. See [runbook](../D1_EVALUATION.md#sequential-chat-judges-qwen-now-compatible-gpt-endpoint-later).

Initial audit:150 nonoverlapping requests,125978 prompt tokens,14823 completion,
zero reasoning tokens;904.7seconds wall time. Minimum memory proxy2.89GiB; minimum
OS free15%. All1368 protected original files unchanged. Independent raw-record
verification and offline replay passed. Qwen's preexisting instance was preserved.

## Corrected evidence arm: final results

**150/150 native valid predictions**, zero failures/fallbacks. Fixed model/prompt,
with all pre-existing curated contexts projected as described above.

| Subset | n | Baseline severe | Qwen severe | Baseline excess | Qwen excess |
|---|---:|---:|---:|---:|---:|
| All |150|11|5|14|9|
| References4/5 |43|5|2|8|3|
| No wordfreq |49|2|1|2|1|
| With senses |131|10|2|13|3|
| Without senses |19|1|3|1|6|
| Clarified references |37|4|1|5|1|
| Initial opaque references |113|7|4|9|8|

**Within±1:139→145/150 (92.7%→96.7%)**. Exact agreement86→80, MAE0.520→0.527.
Severe-error histogram: Qwen one distance2 and four distance3 errors, none distance4;
baseline eight distance2 and three distance3. Qwen rescues9 severe baseline errors
and introduces3 new ones;29 absolute errors improve,33 worsen,88 tie. Numerical
scorer gates pass; this is not automatic promotion or independent validation.

For true4(n21), predictions at levels1..5 are `[1,0,9,11,0]`:20 within±1.
For true5(n22), `[0,0,1,17,4]`:21 within±1. The17 level4 predictions for true5 are
acceptable under the agreed tolerance. Exact4/5 discrimination remains weak and is
not a reason to request new human review by itself.

Matched top8 triage: evidence-only finds1/11 baseline severe errors; Qwen-assisted
**4/11**, precision4/8, four false alarms. Secondary top25 finds1→7/11, but its16.7%
review fraction does not represent the allowed5% budget. Remaining unselected cases
are not certified correct. Label counts in this heuristic are detailed POS labels,
not a normalized coarse grammatical taxonomy.

Paired group-bootstrap95% intervals still include zero: severe-rate delta
[-0.0890,+0.0067], excess-mean delta[-0.1007,+0.0338]. Small reused development150;
no calibrated correctness probabilities, population guarantee or selected-error
sampling estimate for the new1000.

Compared with the initial Qwen arm,12 scores change, all within the95 forms receiving
curated contexts:7 errors improve,5 worsen; severe7→5, excess11→9. All55 unchanged
inputs produce identical scores in these two runs. The correction fixes severe errors
for `literare` and `masca`; it is an evidence intervention, not a prompt sweep.

Five severe cases remain:

| Form | Human | Baseline | Qwen | Evidence condition / audit observation |
|---|---:|---:|---:|---|
| european |1|1|4|No senses; model note incorrectly invokes an anglicism/spelling issue.|
| fulg |1|3|4|No senses; note substitutes an archaic/flash-related interpretation.|
| place |2|1|5|No senses despite verb POS; note treats it as an English word.|
| micșurat |5|4|3|Curated adjective senses present; human5 intentionally confirmed and unchanged.|
| tara |4|1|1|Curated exact senses present; note recognizes tară yet asserts everyday familiarity.|

Notes suggest identity/meaning and familiarity-transfer failure modes; they are not
verified probabilities of causes. Defining a word does not guarantee correct
familiarity judgment. In particular, `tara` shows that more evidence alone is insufficient.

Corrected arm took871.5seconds (~14.5minutes),141994 input/14794 output tokens,
zero reasoning tokens. Minimum RAM proxy2.94GiB, OS free16%. Requests sequential;
preexisting Qwen preserved. All1721 protected files unchanged, including initial
campaign artifacts. Offline replay reproduces requests/outcomes and comparison
artifacts exactly with network/DB blocked. Full repository check: **909 tests +284
subtests and Ruff PASS**; the three new CLIs also pass Ruff. TDD covers collection,
strict failures/resume, comparison and provenance-pinned lexical projection.

## Recommendation and remaining work

Keep **wordfreq+fallback4 as the operational scorer**. Qwen is promising as a
research judge and disagreement detector, especially with usable lexical evidence.
Do not replace all1000 scores:870 new forms lack usable contexts, while Qwen regresses
on the19 unsupported pilot forms. The favorable overall result does not cover that
shift. No numerical confidence band or automatic production promotion is justified.

Next controlled step: a separately pinned GPT pilot on **the same final evidence CSV,
reference and fixed rubric**, reporting the19 missing-context forms explicitly. The
transport/parser/comparison already support this reuse; actual provider compatibility
and model availability still need verification. No GPT classification has run here.
Compare error overlap and matched-budget triage before defining any combined scorer.

In parallel planning for the1000, prioritize automatic source-backed context coverage;
do not ask the user to fill870 gaps. A later rule using Qwen only where evidence is
usable and baseline elsewhere must be frozen and evaluated explicitly; it is not an
already validated production policy. No more broad D1/prompt sweeps or human ratings
are needed for this pilot. Maximum50 reviews remains a later, single-round cap.

Published aggregates and receipts: [initial report](2026-10-30-qwen-judge-pilot/initial-report.json),
[corrected report](2026-10-30-qwen-judge-pilot/corrected-report.json),
[paired arm comparison](2026-10-30-qwen-judge-pilot/arm-comparison.json),
[corrected audit](2026-10-30-qwen-judge-pilot/corrected-verification.json).
