# GPT through Codex: fixed150 comparison with Qwen and baseline

2026-10-31. Existing development150; exact Romanian Scrabble spelling, most familiar
valid sense across all valid POS. Primary error distance>=2; tolerated distance<=1.
No new human ratings, D1/Qwen inference, production scores or project database writes.

## Frozen design and access

Requested/configured model **gpt-6.1-sol**, reasoning **low**. No OpenAI API key was
configured in the process or project environment. The existing authenticated Codex
CLI0.166.0 provides the GPT transport, one new ephemeral session/form, sequential.
The task scripts did not inspect or extract credentials; Codex reused its own authentication. No credential enters campaign artifacts or publication.

The final corrected Qwen vocabulary, evidence CSV, visible Romanian rubric and JSON
schema are copied byte-for-byte:150 forms,131 with senses/19 without,49 missing
wordfreq,37 clarified references/113 initial opaque references. No frequency values,
human scores, baseline/Qwen predictions, distribution hints or few-shot examples
enter model input. No prompt selection or intermediate accuracy analysis.

[Official non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
describes saved authentication, JSONL events and output schemas. The
[model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
confirms low reasoning support. Actual API availability is not demonstrated by this
CLI run. Its requested model is pinned with binary/catalog/configuration hashes;
the native event stream does not attest a provider-served model ID.

## Isolation limits and verification

Codex adds generic managed tools, skills, permissions, global style instructions and
environment context. This is **GPT through Codex**, not a pure model-only comparison
with Qwen's Chat Completions system/user envelope. Temperature/token budgets also
remain provider-specific; low reasoning differs from Qwen's disabled reasoning.

Synthetic preflight revealed ignored settings and inherited runtime context. These
attempts are retained; no target words were classified during transport preparation.
Final environment inherits only standard OS variables, omitting parent session/tool
pipe variables; working directories are empty and outside the repository. User
configuration is skipped; project docs/memories/plugins are disabled where supported.
Nevertheless generic managed wrapper/tools persist. The assembled context was
inspected and contains no project conversation, pilot labels or other predictions.
The debug-context capture is a diagnostic, not a raw provider request dump.

A separate data-only developer instruction forbids tools, file/network access, other
agents and DB use. We do **not** claim tools are unavailable. Native events are audited:
any tool/unknown event, malformed event/item, runtime warning or nonempty stderr saves
a quarantine receipt and stops the campaign. Accepted runs require zero observed tool
use. The process runner persists raw receipts before validation; no application retry
or repair. Internal CLI transport retries are not independently measured.

The collector reuses campaign/Outcome and the existing offline CSV comparator.
Final answers require exact identity, integer1..5 and one short note; no invented
probabilities/confidence. Legacy run.csv remains empty. Native failures are explicit;
complete-score comparison uses the original frozen baseline as fallback. No live
model calls are made by offline analysis or replay.

## Analysis protocol

Frozen before completed collection: same all150, true4/5, missing49, with131/without19,
clarified37/opaque113 strata; exact/within1/severe, error2/3/4, excess loss, MAE and
full class confusion. Pairwise GPT-minus-baseline and GPT-minus-corrected-Qwen deltas,
rescued/introduced severe errors and grouped bootstrap5000; historical seed
`qwen-eval-bootstrap-v1`, sorted group keys, percentile indices124/4874.

Diagnostic ranking is unchanged and label-free: top8 globally primary (5.33%),
top5/fold25 secondary (16.7%). Error intersections describe overlap only, not an
achievable oracle ensemble or independence. No combined scorer is fitted here.
Existing numerical exploratory gates remain; no automatic production promotion.

The references are reused development labels, and curated lexical contexts have
historical label exposure. The new1000 include870 forms without usable context;
aggregate pilot gains cannot by themselves validate that distribution.

## Reproduction

Local campaign: `build/d1/gpt-judge-2026-10-31/`. Frozen protocol, copied inputs,
preflight/configuration, raw process/campaign receipts, executable runner, analysis,
replay and independent verifier remain explicit. Source snapshots preserve code.
Only aggregate results, verification receipts and scripts without lexical contents
are published; dictionary prose and raw judgments remain local.

See [runbook](../D1_EVALUATION.md#gpt-through-codex--2026-10-31) and
[current plan](../plans/2026-10-30-1000-form-risk-review.md).

## Results: all150, native coverage100%

| Method | Errors>=2 | Errors>=3 | Excess loss | Within±1 | Exact | MAE |
|---|---:|---:|---:|---:|---:|---:|
| Frozen OOF baseline |11|3|14|139/150|86|0.520|
| Corrected-evidence Qwen |5|4|9|145/150|80|0.527|
| GPT through Codex |**3**|**0**|**3**|**147/150**|77|0.507|

All150 GPT answers are natively valid; zero failures/fallbacks. The agreed severe-error
objective improves while exact agreement declines. All three GPT errors have distance2;
there are no distance3/4 errors. Numerical exploratory scorer/diagnostic gates pass.
This is not production authorization or an independently held-out evaluation.

| Subset | n | Baseline severe/excess | Qwen severe/excess | GPT severe/excess |
|---|---:|---:|---:|---:|
| True4/5 |43|5/8|2/3|2/2|
| Missing wordfreq |49|2/2|1/1|2/2|
| With senses |131|10/13|2/3|3/3|
| Without senses |19|1/1|3/6|0/0|
| Clarified references |37|4/5|1/1|1/1|
| Initial opaque references |113|7/9|4/8|2/2|

GPT repairs10 severe baseline errors and introduces2. Against Qwen, it repairs all5
severe errors and introduces3 different ones. Absolute errors improve/worsen/tie for
35/40/75 forms versus baseline and19/21/110 versus Qwen; most worsening is within the
accepted one-level tolerance. The severe-error sets of GPT and Qwen do not intersect
on this pilot. This does **not** mean we know which model to trust on an unseen
conflict, nor that averaging or voting creates an error-free classifier.

Paired group-bootstrap95% intervals for GPT-minus-baseline:
severe-rate delta[-0.1039,-0.0068], excess-mean delta[-0.1346,-0.0196]. Against Qwen:
[-0.0523,+0.0205] and[-0.1007,+0.0133], respectively. The Qwen comparison includes
zero; model superiority is not established by the two-error difference. All intervals
remain exploratory on repeatedly used development labels and model comparisons.

For true4(n21), GPT predictions1..5: `[0,1,13,7,0]`;20 within±1.
For true5(n22): `[0,0,1,17,4]`;21 within±1. The17 true5→4 predictions are acceptable
under the chosen tolerance. Missing49 merely ties baseline on severe/excess and is
worse than Qwen. Do not retune4vs5 or optimize exact agreement at the expense of the
agreed objective.

## Important differences

| Exact form | Human | Baseline | Qwen | GPT |
|---|---:|---:|---:|---:|
| carter |5|2|4|3|
| catalige |4|4|4|2|
| târfă |3|4|2|1|
| european |1|1|4|1|
| fulg |1|3|4|1|
| place |2|1|5|1|
| micșurat |5|4|3|4|
| tara |4|1|1|3|

The first three are the remaining GPT severe errors. Its notes recognize the relevant
meanings but assign greater familiarity than the references. That is a familiarity/
rubric discrepancy hypothesis, not proof that the human ratings are wrong.

The other five are Qwen's severe cases, now within tolerance for GPT. GPT recognizes
`place` as the Romanian verb form, retains the exact `tara` senses, and distinguishes
`micșurat` from the usual `micșorat`; the intentionally confirmed human5 stays intact.
`ata` remains5 and `ață`1. No spelling/label exception or prompt adjustment was added.

## Diagnostic usefulness and transfer limits

At the frozen **top8/150** budget, GPT-assisted ranking finds **6/11** severe baseline
errors: precision6/8, recall6/11, two false alarms. Corrected Qwen finds4/11 with four
false alarms; evidence-only finds1/11 with seven. Secondary top25 finds10/11 for GPT,
but25/150=16.7% cannot be presented as the50/1000 review budget.

The favorable0/19 result without senses is narrow: **16 references are level1, one
level2 and two level5; only2/19 lack wordfreq**. In the new sample, **764 of the870
forms without usable contexts lack wordfreq**. Consequently this pilot does not
validate the population that dominates the next batch. Zero shared GPT/Qwen severe
errors likewise does not establish independent errors, calibrated confidence or
population accuracy.

## Recommendation and next step

Use GPT as the **primary semantic judge candidate for the next research experiment**,
with Qwen as a second diagnostic on consequential disagreements. Keep the frozen
wordfreq+fallback4 operational scorer and all existing scores unchanged. Do not average
or promote scores automatically from this pilot.

Next: prepare the1000-form evidence CSV with explicit missingness and freeze the
routing/review rules, checking them offline against the already collected150 outputs.
Then run the authorized next experiment when requested: baseline for all, one sequential
GPT pass, and a bounded Qwen conflict route with source coverage kept explicit. Prefer
Qwen where usable lexical contexts exist; its unsupported-form regression remains.
The routing policy itself is still unimplemented/unvalidated, not an achieved result.

Report the600 general/400 stress slices and especially the764 unsupported/no-wordfreq
forms separately. Automate source-backed context improvement where available; do not
ask the user to fill870 gaps. Preserve unknown confidence; at most50 later review cards
in one round, only consequential unresolved cases. No new pilot ratings or broad
prompt sweeps are needed.

## Verification and operational result

Independent audit **PASS**:150 unique sessions,149 nonoverlap checks, identical lexical
input/rubric/schema, no observed tools/unknown events/stderr, all seven metric strata,
paired bootstrap and review ranks independently reconstructed. **2,092 protected files
unchanged**, including human evaluations and Qwen campaigns. Offline replay reproduces
requests/outcomes and comparison artifacts with subprocess/network/DB blocked.

TDD:6 new public-boundary tests/19 subtests, including fatal quarantine, malformed
messages, runtime warnings, identity/level validation and incompatible resume. Full
repository check: **915 tests +303 subtests and Ruff PASS**.

The150 sequential sessions took782.1seconds (~13minutes), median4.95seconds. Native
CLI usage:992416 input tokens (444928 cached),10004 output tokens,477 reasoning-output
tokens as reported. These are session usage counts, not an API billing receipt.
No local model was loaded or changed, and no project DB operation ran.

[Full metrics](2026-10-31-gpt-judge-pilot/report.json) ·
[paired comparison](2026-10-31-gpt-judge-pilot/paired-analysis.json) ·
[shared errors](2026-10-31-gpt-judge-pilot/shared-errors.json) ·
[independent verification](2026-10-31-gpt-judge-pilot/verification.json).
