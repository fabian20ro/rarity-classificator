# D1 adapter and Romanian Scrabble evaluation plan

Date: 2026-10-15. Updated: 2026-10-20. Status: offline implementation delivered; consolidated audit imported (46 contexts, 12 exact forms). Independent evaluation, live validation and replacement decision pending. Latest status and leftovers at the end.

Recommendation: build an offline evaluation harness first, then a Step2 scoring adapter for D1 through LM Studio `/v1/systemone`. Evaluate D1 alone, with dictionary evidence, and alongside frequency features. Replace the existing scorer only if held-out Romanian results justify it. Expect a hybrid scorer to be a stronger candidate than D1 using word spelling alone; treat that as a hypothesis.

## What D1 and Jev provide

Jev is TypeSafe AI's System One model: state plus typed questions produces choices, scores, or yes/no probabilities. Type safety limits possible outputs; it does not establish that a Romanian lexical judgment is correct. D1 is Liquid AI's separate open-weight decision model, sharing the decision interface concept rather than Jev's weights or demonstrated performance. [TypeSafe introduction](https://typesafe.ai/blog/introducing-system-one-models-and-jev), [Liquid AI release](https://www.liquid.ai/blog/d1-open).

D1-3B returns typed judgments and probabilities in one forward pass rather than generated prose. Its advertised language metadata excludes Romanian; Romanian lexical rarity remains unvalidated. Evaluate the exact local Q8_0 artifact, not published full-precision benchmarks. [D1 model card](https://huggingface.co/LiquidAI/d1-3B).

Local inspection: LM Studio 0.4.26 build 4, llama.cpp runtime 2.58.0, server on port 1234. `d1-3b` Q8_0 GGUF is recognized as `decision`, `lfm2-d1`, unloaded. The FP16 MLX copy is listed as ordinary `llm`; do not assume it provides equivalent decision behavior. Supported HTTP shapes include `/v1/systemone` and `/v1/decisions`; start with the documented former. [LM Studio release](https://lmstudio.ai/changelog/lmstudio/lmstudio-v0.4.26), [System One contract](https://lmstudio.ai/docs/developer/jev-compat/systemone).

## Target and population

Accepted target (2026-10-19): familiarity of the exact eligible spelling through its most familiar valid sense, across valid parts of speech. Retain the direction 1=common through 5=obscure; project contextual scores by minimum and preserve all winning contexts. Do not transfer familiarity from another spelling or inflection. Corpus frequency is evidence for familiarity, not its definition.

Freeze an authoritative Scrabble inventory as `vocabulary.csv`: `word_id`, original spelling, part of speech, source/version, and game-normalized key. Existing `words` exports are candidates; verify importer provenance and eligibility before calling them authoritative. Include only inventory rows in final output. Do not expand into all Romanian inflections, and do not reduce eligible forms to lemmas. If an inflected form is explicitly in the inventory, preserve it as its own target.

Preserve Romanian diacritics for frequency lookup and model input. Normalize Unicode and cedilla/comma variants explicitly; keep ASCII game keys separately. A shared ASCII key can collapse distinct diacritic spellings or senses. Report collisions and unresolved joins; never silently copy evidence between them. Explicit lemma/family relations may supply additional evidence, never replace the exact-form measurement or add new output words.

Current prompt policy penalizes vulgar/obscene/insulting/sexual words with rarity>=4. Separate lexical familiarity from suitability tags during evaluation. Preserve the frozen existing classifier as an as-is baseline; report raw lexical and policy-adjusted results separately. Any production change to that policy needs an explicit decision, not an incidental consequence of switching models.

## Evidence sources

| Source | Role | Limitation and treatment |
|---|---|---|
| Frozen Scrabble inventory | Defines population and stable IDs | Eligibility/provenance audit first; model cannot decide membership |
| `wordfreq` Romanian | Exact-form written-frequency feature and standalone baseline | Romanian has only the small list; absent entries are censored/missing, not zero real use or automatic level 5 |
| DEX definitions and usage labels | Meaning, archaic/regional/technical labels, variant relations | Meaning supplied in a definition can make an unfamiliar word look easy; test this effect |
| Token counts across DEX definition bodies | Experimental frequency feature | Dictionary prose is a biased corpus; deduplicate entries, exclude headings/examples of the entry itself and repeated boilerplate; retain as a separate source |
| Existing classifier outputs | Operational baseline and disagreement sampling | Predictions are not gold labels |
| Native-speaker labels | Primary evaluation reference | Familiarity varies; preserve rater disagreement and adjudicate rubric disputes |

`wordfreq` lists Romanian coverage from Wikipedia, subtitles, and web text, with no large list. Small lists cut off at Zipf 3; zero is the default return for an absent item. Store membership/coverage explicitly alongside frequency. Do not infer tail ordering from a pile of zero values. Pin package/data version. [wordfreq documentation](https://github.com/rspeer/wordfreq).

Available locally: `/Users/fabian/git/generator-rebus/.cache/dex_definitions`, 12,728 JSON files, 12,580 `ok` and 148 `not_found` at inspection. Fields: `word`, `original`, `status`, `html`, `fetched_at`. Cache success is not proof of a correct sense match or usable parsed definition. Export cached source HTML to stable text/evidence CSV; do not invoke a provider that fetches missing entries or writes caches during evaluation. Keep original DEX text separate from model-generated rebus clues and quality labels. Existing parser: `packages/rebus-generator/src/rebus_generator/platform/io/dex_cache.py`.

Start with dictionary definitions as evidence. Evaluate definition-corpus frequencies only as an ablation. If tail coverage remains poor, inventory the user's other frequency projects before selecting another corpus. Whole-dictionary crawling and model fine-tuning are outside the first implementation.

## Benchmark and experiment design

1. Pilot: 150 inventory entries covering common words, rare/regional/archaic/technical words, missing-frequency words, short ambiguous forms, diacritic collisions, and policy-sensitive words. Two Romanian raters independently score familiarity before seeing definitions, model predictions, or frequencies. Then show definitions for a separate meaning/sense check; do not overwrite the first response. Refine the rubric on this development set.
2. Main benchmark: target 1,200 entries, including the pilot in development: 300 development, 300 calibration, 600 locked test. Split before prompt/threshold tuning, grouped by spelling variants and known lexical families. Group unresolved ASCII collisions conservatively. Keep prompt exemplars and anchors out of the test groups.
3. Within the locked test, retain a representative probability sample (suggested 400) and a rare-word challenge sample (200). Track sampling probabilities; publish population-weighted results separately from challenge results. Stratify using source evidence and legacy labels, while ensuring neither defines gold truth. Expand sample sizes if key confidence intervals remain too wide.
4. Record per-rater level, recognition, sense check, uncertainty, and adjudicated reference. Measure ordinal agreement; ambiguous gold labels remain visible. A single expert can start the pilot, but expert vocabulary alone is a weak proxy for ordinary-speaker familiarity.

| Experiment | Inputs | Question answered |
|---|---|---|
| Legacy baseline | Frozen current scorer and settings | What quality and cost are being replaced? |
| Frequency baseline | Exact-form frequency, missingness | Can a simple calibrated frequency-to-level mapping suffice? |
| Evidence baseline | Frequency plus dictionary features, no D1 | Does D1 add value beyond available data? |
| D1 word only | Original word and POS | What does the model know about Romanian unaided? |
| D1 with definitions | Word, POS, matched definitions/usage labels | Does lexical evidence repair rare-word errors? |
| D1 with all evidence | Above plus frequency and missingness | Does supplying frequencies improve decisions or merely anchor them? |
| Hybrid | D1 probability vector plus evidence features | Does a small fitted classifier improve reliability? |

Use development data to compare Romanian versus English instructions while retaining Romanian words and definitions. Select one prompt/input recipe before calibration and final test. Initial hybrid: regularized ordinal or multinomial logistic model; avoid unnecessary complex training. Fit on development data with grouped cross-validation; reserve calibration for confidence/abstention thresholds. Lock one candidate before opening the test set.

Report every requested ID, including abstentions and failed predictions; never silently drop failures from denominators. Report unconditional performance/coverage and accepted-only performance separately. Report macro-F1, ordinal MAE, confusion matrix, recall for gold levels 4/5, and severe errors where gold 4/5 becomes predicted 1/2. Report L1 precision/recall separately. For probability-producing candidates, report Brier score, log loss, calibration curves, and error versus accepted coverage. Legacy self-reported confidence is a separate score, not a substitute for a full class distribution. Break results down by frequency presence, definition presence, usage labels, form ambiguity, and word length. Use paired bootstrap intervals by lexical group; do not treat correlated variants as independent samples.

Runtime metrics: wall time/word, throughput, p50/p95 latency, failures/retries, memory, and review/fallback share. Compare sequentially on the same machine; no simultaneous large-model loading. Reuse a frozen compatible baseline snapshot where possible, otherwise schedule its run separately. No load, unload, or inference as part of this planning task.

## Adapter recommendation

Create a small scoring Interface at the Step2 seam: `score_batch(items) -> outcomes`, with one explicit outcome per requested ID: scored, unresolved, or failed. Inject a configured scorer. Chat and D1 are two Adapters behind the same Interface; Step2 retains locks, CSV persistence, resumption, and orchestration. Avoid extending the chat JSON-repair pipeline to handle decision responses.

Start D1 with one word per HTTP request and concurrency 1. State contains original spelling, POS, and versioned optional evidence. Ask one `choice` question with explicit keys `L1` through `L5` and full rubric descriptions. Preserve the returned probability vector. Compute expected level `sum(level * probability)` for analysis; convert to an integer through a documented policy selected on development data. Start with argmax; compare ordinal-loss mapping later. A `score` primitive is optional later, once its indexing and scale are contract-tested; never assume it already uses 1..5.

Validate exact answer/question keys, allowed class keys, finite probabilities within [0,1], sum within a documented tolerance, and completeness. Reject missing/unknown/duplicate answers; parse duplicate JSON object keys explicitly if strictness requires it. Keep unsupported confidence fields as raw diagnostics. Primary confidence is a named class probability, calibrated on Romanian labels before it controls acceptance. Transport failures must remain failures, not low-confidence predictions or rare labels.

Preflight uses read-only model metadata and requires an already loaded decision model with the expected ID. No JIT loading, download, unload, or model switching. Bound retries to transient HTTP errors; persist failure IDs. Abort on model identity/configuration changes. Verify response behavior with recorded fixtures and a later explicit live smoke run; documentation alone does not establish throughput or calibration.

Artifacts: `vocabulary.csv`, `evidence.csv`, `labels.csv`, `split.csv`, `predictions.csv`, `failures.csv`, raw request/response JSONL, `manifest.json`, and metrics/report files. Predictions include p_L1..p_L5, expected level, selected level, acceptance status, and source/model/rubric versions. Manifest pins vocabulary/evidence hashes, model artifact hash/quantization, runtime, prompt, policy, seed, and split. Keep prompts/raw responses auditable; resume by ID plus complete configuration fingerprint. Refuse incompatible mixed runs. Commit results atomically and never silently substitute legacy scores into a D1 run.

Do not infer lexical tags such as archaic or regional from the rarity level. Populate tags only from separately validated evidence or a documented compatibility value. Write accepted results into the existing RunCsvRow format for downstream compatibility; keep full evidence/probabilities in sidecars. Preserve unresolved rows in a review queue. A separate explicit fallback run may fill them with existing human/legacy labels and recorded provenance. Do not reinterpret current CSV confidence without versioning its semantics.

Step5 selection is a separate task. Independent D1 scores do not enforce exact-K selection. Initial D1 evaluation bypasses histogram rebalancing; assess lexical quality first. Keep existing Step5 intact and optional. A later deterministic ranking/top-K design would be an explicit algorithm change with complete-score requirements, stable tie-breaking, local IDs 1..N, exact count, and no autofill. Do not claim Step5 migrated merely because Step2 supports D1.

## Implementation sequence

Each phase should be independently reviewable, with a narrow change set and unittest coverage through the public Interface.

| Phase | Proposed files and work | Completion check |
|---|---|---|
| 1 Population and evidence | `evaluation/dataset.py`, `evaluation/evidence.py`, associated tests | Exact inventory ID preservation; diacritic/collision reports; source coverage; no external writes |
| 2 Gold labels and baseline | `evaluation/benchmark.py`, benchmark manifest/rubric, tests | Reproducible group splits, blind annotation export, leakage checks, frozen baseline |
| 3 Offline D1 Adapter | `scoring/base.py`, `scoring/d1.py`, tests | Fixture-based request mapping, strict distributions, failures, no auto-load paths |
| 4 Shared Step2 seam | `scoring/chat.py`, `steps/step2_score.py`, orchestration tests | Existing chat outputs/recovery preserved; both adapters produce explicit per-ID outcomes |
| 5 CLI and provenance | `cli.py`, `evaluation/artifacts.py`, tests | Explicit provider selection; checkpoint fingerprint rejection; interruption/atomic resume |
| 6 Live pilot when RAM permits | Versioned experiment configs and recorded responses | Already-loaded-only smoke; all pilot IDs accounted for; language/input ablations |
| 7 Locked evaluation | `evaluation/metrics.py`, report generator, tests | Gold/test separation, hand-checked metric examples, group intervals, evidence-only/hybrid comparisons |
| 8 Candidate release | Existing Step3/audit/Step4 integration, runbook | Full tests; semantic gates; partial candidate upload only after acceptance; rollback snapshot |

Implementation baseline: latest reviewed fixes in PR80 or their merged successor; original local main is stale and contains unrelated work. Check merge status before coding. The existing untracked continuous-scoring files are not an approved production Interface; preserve them and inspect before any overlapping change.

Minimum regression cases: exact inventory filtering; Unicode/ASCII collisions; missing wordfreq membership; DEX redirect ambiguity; malformed probabilities; missing/extra question IDs; timeouts/partial failure; model not loaded; prompt/model hash mismatch on resume; crash between evidence/results writes; class-level off-by-one; Step5 strict contract and mandatory upload gates unchanged.

## Replacement decision and rollback

Proposed gates, to freeze before final testing: candidate macro-F1 within 0.02 of legacy, ordinal MAE within 0.05, and rare-level recall within 0.03, using paired confidence intervals rather than point estimates alone. Require no increase in severe rare-to-common errors. For automatically accepted L1, target a 95% confidence lower bound on precision of at least 0.90; expand the sample if too few predicted L1 examples support that estimate. Compare L1 recall and coverage too, so abstaining on everything cannot pass. Proposed accepted coverage target: at least 80%; calibrate thresholds without test labels.

A hybrid release must also improve meaningfully on the evidence-only baseline to justify D1's cost. Report achieved speed/memory rather than adopting vendor latency claims. If D1 fails, retain frequency/dictionary tooling and use D1 only on demonstrated-safe slices, or retain the existing scorer. Fine-tuning comes later, only after sufficient independent labels and evidence of a correctable error pattern.

Before any eventual upload, retain mandatory Jaccard plus anchor precision/recall gates and default partial mode. Reference agreement is a drift check, not ground-truth accuracy: adjudicate justified deviations and version a new reference explicitly rather than weakening gates. Keep the previous accepted CSV and prior database levels for rollback. Produce a reviewable candidate CSV before publishing.

## Decisions to resolve before execution

- Authoritative Scrabble inventory/version and precise handling of eligible inflected entries.
- Familiarity versus written-frequency target; provisional choice above is familiarity.
- Any additional frequency projects and their available artifacts.
- Native-speaker raters and annotation budget; 150-word pilot first.
- Treatment of current suitability policy in the eventual production field.

Research detail: [D1 and Jev source notes](../research/2026-10-15-d1-jev.md).


## Implementation status on 2026-10-16

| Planned area | Delivered | Remaining |
|---|---|---|
| Population/evidence | Explicit inventory, source hashes, Unicode handling, transitive family/collision grouping, local DEX extraction, optional wordfreq export | Confirm actual Scrabble source; representative/challenge sampling; human audit of sense matches |
| Benchmark | Blind label template and deterministic grouped dev/calibration/test splits | Two-rater collection/adjudication; exact sample quotas; immutable approved gold release |
| D1 adapter | Blocking sequential System One requests, loaded-instance preflight, strict full distributions, explicit errors/abstentions, retained raw exchange | Live response verification for installed runtime; RO/EN prompt ablation; measured peak RAM |
| Step2 integration | Explicit `--backend d1`, compatible scored CSV plus campaign sidecars; shared BatchScorer Interface for D1/chat/frequency experiments | Production default switch only after quality acceptance; original chat orchestration deliberately retained |
| Provenance/resume | Per-ID atomic records, CSV projections, config/input/model-file/implementation fingerprints, explicit failure retries | Server cannot attest that supplied local model file matches loaded weights; operator verifies matching artifact |
| Evaluation | Frequency threshold baseline, legacy run import, missing-aware ordinal/class metrics, proper scores, paired grouped bootstrap | Fitted evidence-only/hybrid, calibrated thresholds/probabilities, subgroup/weighted metrics, reliability diagrams, automated acceptance gates |
| Release | Runbook and offline integration tests; no upload/default change | Live pilot, gold benchmark, candidate review, existing semantic upload gates |

No LLM execution, model loading, database writes or measured Romanian accuracy in this iteration. Runtime calls are sequential within each campaign; no thread/async pool. Existing model state is not managed by the application. The plan's statistical margins remain proposed, not validated acceptance criteria.

Architectural choices: KISS, YAGNI, DRY, Rule of Three, SoC, POLA, Fail Fast and Gall's Law; add high cohesion/low coupling, explicit dependencies, composition and reproducibility. See [decision record](../adr/2026-10-16-d1-evaluation-seam.md). No generic provider framework or trained hybrid before labels establish the need.

Offline verification: Python 3.11.16, `python scripts/check.py`: Ruff passed; 785 tests and 98 subtests passed. Independent architecture review identified and resolved retry projection write amplification and quadratic evidence-ID validation. Live compatibility and Romanian quality remain unverified.

Next recommended action: freeze a confirmed 150-entry pilot inventory and familiarity rubric, collect blind labels, then manually load the matching D1 GGUF when RAM permits. Compare word-only, definitions-only, full-evidence, frequency and frozen current-classifier predictions. Inspect rare-to-common errors first. Use those results to decide whether a fitted hybrid deserves implementation, then expand the gold benchmark. Continue via [evaluation runbook](../D1_EVALUATION.md).

## Pilot prepared on 2026-10-17

Local package: `build/d1/pilot-2026-10-17/`; UI: `index.html` (currently served at
http://127.0.0.1:8765). All 150 exact forms checked against local LOC 5.0 and
selected from existing stable IDs. Seed 20261017; 100 frequency-stratified random
forms plus 50 targeted challenge forms. Wordfreq3.1.1 coverage101/150; exact DEX
text53/150, missing85, ambiguous12. These are coverage counts, not model results.
All pilot rows explicitly assigned to development; collision IDs reserved for
future benchmark expansion. Full inventory/model-family audit still required
before selecting a held-out benchmark.

User requested an easy annotation interface plus assistant estimates. Delivered
150 explicit assistant estimates with short rationales, stored separately from
blank human labels. UI shows estimates after first human rating by default;
optional early reveal is audited, as is definition exposure. CSV preserves first
and final ratings, independent/assisted status and source; JSON preserves action
history and supports import. Autosave remains local. Test responses use a separate
QA storage namespace; user session starts0/150. Two independent CSV rater sheets
also available. Estimates are neither D1 outputs nor human gold.

Next: collect the user's first-pass ratings through the UI, adjudicate unclear
POS/senses, optionally obtain a second independent rater. Then run D1 only when
memory permits and compare independent versus assisted labels separately.
No model loaded, no inference or DB writes. Calibration, hybrid fitting and
live accuracy remain pending. Pilot files are local artifacts; PR81 unchanged.

## Human pilot imported on 2026-10-19

Imported Fabian's150/150 completed scores and199 audit events (196 rating events)
from browser CSV/JSON exports. Preserved originals and hashed assistant estimates;
validated all IDs, POS, splits, first/final scores and exposure against the log.
Results: final agreement112/150 (74.7%), MAE0.273; first-independent agreement
85/149 (57.0%), MAE0.557.31 revisions all moved closer to assistant estimates;
this is observational, not proof of causal anchoring. Final ratings are a separate
assisted reference, not an independent validation set. Single-rater developmental
reference, no population accuracy or D1 performance claims.

Two final gaps≥2: micșurat user5/assistant2 (user explicitly confirmed5), nordic
user1/assistant3. Twelve-item optional sense/rubric queue prepared. Main next
recommendation: reconcile ambiguous form+POS versus any-sense word familiarity,
freeze rubric, obtain a second blind review/new batch before calibration. Future
independent UI rounds should defer AI reveal until the whole batch is completed.
D1 word-only/evidence runs remain pending sufficient memory, sequential only.

Local [comparison report](../../build/d1/pilot-2026-10-17/data/evaluations/2026-10-19-fabian/comparison-report.md)
and [all differences](../../build/d1/pilot-2026-10-17/data/evaluations/2026-10-19-fabian/differences.csv).
Human pilot annotation is now done; adjudication, independent second-rater evidence,
live D1 verification, calibration and hybrid decisions remain open.

## Sense review UI delivered on 2026-10-19

Twelve cases ready at http://127.0.0.1:8765/review-12/ with POS, sourced meanings,
illustrative examples and original scores; multiple contexts explicitly selectable
for mai, ata, carter and sezisa. State and exports isolated from the original150.
Original LOC gender narrows ițar to a loom component; initial AI explanation had
assumed the trousers sense. micșurat needs exact-variant familiarity, not implicit
normalization to micșorat. Frozen assistant predictions remain unchanged.

Leftovers: user's12-case review; import contextual revisions as a separate assisted
layer; decide how multiple senses map to a single word/POS rarity label. Preserve
source gender and curate POS-compatible definitions before evaluating evidence-fed
D1. Next recommendation: finish this sense/rubric decision before collecting a
second blind batch or fitting calibration. D1 still awaits available memory;
requests remain sequential.

## Sense review imported on 2026-10-19 — current next step

**Done:** user's12/12 contextual labels imported and validated against both exports,
case pack and final event. Four changes from the first round's final scores:
nordic1→2, mai (mallet)5→4, pag4→5, ițar (loom component)4→5. Eight retained;
micșurat5 reconfirmed. Original150 labels and frozen AI estimates unchanged.
No AI reveal in this round, but it remains assisted by definitions, prior scores
and previous exposure. Descriptive numeric agreement4/12→7/12 cannot establish
model improvement: ițar/carter rationale scopes differ, ata's initial AI sense was
unspecified, and micșurat's exact variant was not distinguished by its rationale.
No new150-item aggregate computed from mixed contextual/word-level targets.

**Rubric accepted by user on 2026-10-19:** familiarity of the exact accepted form through its most familiar valid
sense. Keep POS/gender/sense as explicit evidence. The game target is the exact form
across its valid senses, including valid POS uses; contextual labels remain
separate. Do not silently normalize spelling variants. This is an accepted
product rule; projection implementation remains a follow-up.

**Immediate small follow-up:** rate carter as a mechanical housing and ata as a
trump card. User selected carter=volume5 and ata=money5; neither resolves the
potentially more familiar alternative. The12-case review itself is complete;
these are additional contexts, not missing answers. Four unchosen contexts remain
recorded without labels (also mai=liver and sezisa=notify).

**Implementation recommendation:** preserve contextual labels keyed by word_id +
sense_id and LOC gender; curate definitions to match POS and exact form; make any
projection to a game score explicit and reject unresolved priority senses. No
hybrid fitting or threshold changes from these12 selected cases. After rubric
freeze, obtain a second blind rater/new batch; then run D1 sequentially when RAM
permits, comparing word-only, curated-evidence, frequency and current classifier
against the same target. Live compatibility and Romanian D1 quality still untested.

[Imported contextual review and full comparison](../../build/d1/pilot-2026-10-17/data/evaluations/2026-10-19-fabian-sense-review/comparison-report.md).


## Two additional contexts delivered on 2026-10-19

UI: http://127.0.0.1:8765/review-2/ — carter/housing and ata/trump, each with
fixed sense, POS, definition, example and sources from the frozen lexical pack.
Fresh scores required; no carry-over of5 from volume/money. Separate storage
version `additional-contexts-2026-10-19-v1` and CSV/JSON export names.

Accepted rule: **exact form through its most familiar valid sense**. On the
current1(common)–5(obscure) scale, a form-level projection takes the minimum
of its valid sense scores; it must retain the contributing context/provenance
and flag unresolved priority senses. Include valid senses across POS; keep
contextual POS labels available for diagnosis. Do not equate a known normalized
variant with familiarity of the exact spelling. A minimum over only the reviewed
contexts is provisional when relevant alternatives remain unresolved.

Next: import the two responses; combine them with the frozen volume/money labels
under the accepted rule, preserving raw contextual ratings. Then audit remaining
priority sense coverage before producing an explicit form-level benchmark. Blind
second-rater/new-batch evaluation and sequential D1 verification remain pending.

## Additional contexts imported and form projection computed — 2026-10-19

**Done:** carter/housing=5 and ata/trump=5 imported from the live UI exports,
validated against JSON/CSV, case pack and final event. Combined14 contextual
ratings across12 exact forms. Accepted minimum rule yields carter=min(5,5)=5,
ata=min(5,5)=5. No numeric changes from the12-case review; four differences from
the initial final ratings remain. Numeric agreement with frozen AI remains7/12,
MAE0.583, descriptive only. carter's mechanics comparison is now sense-matched:
human5 versus AI4. Raw150 and previous12 imports unchanged.

**New coverage finding:** original LOC includes tău N52 and tău P92, while the
pilot retains only the noun. The rating5 for lake cannot certify exact-form
familiarity across valid senses/POS. Also unreviewed in the existing case pack:
mai/liver and sezisa/notify. Other forms have not had exhaustive coverage audit.
All12 computed minima therefore carry provisional observed-sense status, with
separate coverage flags and winning context IDs; no automatic overwrite of gold.

**Current recommendation:** the two requested contexts are complete. Next, audit
valid exact-form homographs/POS and priority meanings once, then produce one
consolidated missing-context list. Preserve all valid LOC entries instead of
choosing a single row; start with confirmed tău/pronoun omission and verify
la/mai/literare context coverage before finalizing the benchmark. Ask the user
only for genuinely missing ratings that could affect the minimum. Keep raw
context labels and form projection separate. The calculation is implemented as
a small analysis function, tested for cross-POS minimum, exact-variant isolation,
invalid ratings and duplicate contexts. Calibration/model changes remain deferred
until coverage and an independent second-rater/new-batch check are complete.
D1 stays unloaded; future inference sequential and conditional on available RAM.

[Updated comparison and recommendation](../../build/d1/pilot-2026-10-17/data/evaluations/2026-10-19-fabian-form-projection/comparison-report.md)
· [Explicit form projection](../../build/d1/pilot-2026-10-17/data/evaluations/2026-10-19-fabian-form-projection/form-projection.csv).

## Consolidated sense/POS audit delivered — 2026-10-19

Audited the12 adjudicated exact forms against saved DEX/MDA2/DOOM evidence and
local LOC.32 missing semantic-family contexts across10 forms in one UI:
http://127.0.0.1:8765/review-consolidated/. Existing14 contextual labels retained.
Carter and stenodactilograf need no additional distinct contexts in reviewed
sources. Common omissions include la/preposition+music, mai/adverb+month,
tău/possessive and literare/adjectival exact-form uses. Regional/archaic meanings
also queued; assistant rarity guesses never exclude a candidate.

Scope is the12-form queue, not the other138 pilot forms. No claim of absolute
lexicographic exhaustiveness or newer Scrabble-edition certification. Exclusions
include other spellings, proper nouns, symbols, unattached suffixes, and senses
explicitly limited to other forms (notably ițari clothing versus exact ițar).
Related senses grouped with instruction to score their most familiar listed use.

UI now keys answers by word_id:sense_id, preserving multiple answers per form.
Tests cover independent scores, reload/export,32 unique contexts, uncertainty and
old-state isolation. JSON retains full source pack, history and prior labels;
CSV preserves context identity and original inventory POS separately. Single
new namespace; old datasets/imports unchanged. No model or DB calls.

Next: complete this one round, import using composite-key validation, merge with
prior14 contextual labels, inspect unresolved responses/notes and project exact
forms via minimum. Only then freeze audited coverage for independent evaluation.
[Consolidated audit](../../build/d1/pilot-2026-10-17/review-consolidated/audit-report.md).

## Consolidated audit imported — 2026-10-20 (current recommendation)

**Done:**32/32 new ratings, no unresolved answers/notes; combined with14 preserved
contextual labels. All46 audited families now rated across12 exact forms. Frozen
CSV/JSON, case pack, events, dictionary hashes and prior-import hashes verified.
Coverage is complete within the audited sources/families, not a claim of absolute
lexicographic exhaustiveness. Original150 labels unchanged.

Exact-form minima: micșurat5, nordic2, mai1, la1, tău1, literare2, ata5,
carter5, pag4, ițar4, stenodactilograf4, sezisa3. Six changes from the previous
projection; five from the initial final ratings. Common cross-POS senses resolve
la/mai/tău/literare; regional pag/page and ițar/cloth reduce their minima to4.
Sezisa remains3 from notice despite three new context ratings5.

New contextual estimates: final26/32 exact (81.25%), MAE0.1875; first choices
21/32 (65.625%), MAE0.34375. All first choices preceded their own estimate;
four later revisions followed reveal and moved toward it. Definition assistance
and earlier exposure remain; this is development data, not independent evidence
of model performance. Original frozen estimates agree numerically with1/12
projected forms (previously7/12); their target was inconsistent with the newly
accepted rule. Do not interpret that drop as model degradation or mix rubric
versions into a revised150-item accuracy.

**Next:** freeze this12-form reference as semantic regression/development data;
align the model/evidence contract to exact form across all valid POS; then obtain
independent labels under the frozen rubric. No further annotation round for
these12 is recommended absent new lexical evidence.

**Leftovers, in order:**
1. Preserve all LOC POS entries per exact form in the evaluation input. Keep
   contextual labels, form projection and game-normalized keys separate.
2. Audit the other138 pilot forms before reusing their labels under this rubric;
   request only ratings needed to close real coverage gaps.
3. Prepare a fresh held-out batch and independent second rater, hiding AI and
   prior scores; freeze split and criteria before model/threshold tuning.
4. When RAM permits, run D1 sequentially on the same target as frequency and the
   current classifier. Compare word-only versus curated lexical evidence. Decide
   replacement/hybrid/calibration from held-out results. No model loaded today.

[Full updated comparison](../../build/d1/pilot-2026-10-17/data/evaluations/2026-10-20-fabian-consolidated/comparison-report.md)
· [12 exact-form scores](../../build/d1/pilot-2026-10-17/data/evaluations/2026-10-20-fabian-consolidated/form-projection.csv).

## Remaining138 exact-form audit delivered — 2026-10-20 (current recommendation)

Audited the other138 forms:34 already at1,21 with no distinct missing family
identified,83 with172 additional candidate contexts. All104 forms above1 have
saved dictionary evidence; all138 retain exact LOC matches and initial metadata.
Initial labels remain opaque form/POS ratings, never retroactively assigned to
specific senses. This closes the source-review task within consulted families,
not absolute lexicographic coverage or contextual labeling of the entire pilot.

One round: http://127.0.0.1:8765/review-remaining/. Cards show exact sense/POS,
example, source and optional assistant estimate. No estimate-based exclusions.
A human1 makes other unrated contexts for the exact same form optional, without
inventing ratings; revising the final1 reopens them. Existing answers preserved.
Exports retain all172 contexts, actual decisions, events, eligibility and witness
IDs. TDD and browser checks cover this behavior plus persistence/state isolation.

**Next:** complete this round; import CSV/JSON with the new optional-context
semantics. Recompute eligibility from human answers rather than trusting exported
flags. Validate composite IDs and score-time AI exposure; inspect unresolved
answers/notes. Keep original opaque ratings separately from contextual minima and
winning-context provenance. Then update the150-form comparison under explicitly
stated coverage/rubric limits. No new model-performance accuracy from mixed targets.

**Leftovers:** independent second-rater/new held-out batch; exact-form/all-POS
input contract; frequency/context baselines; RAM-permitted sequential D1 trial.
No additional annotation round recommended now; use the notes field for omissions.

[Audit report](../../build/d1/pilot-2026-10-17/review-remaining/audit-report.md)
· [138-form ledger](../../build/d1/pilot-2026-10-17/review-remaining/audit.csv).

## Annotation burden reduced — 2026-10-21 (supersedes172-round requirement)

User rejected the need to rate172 contexts and authorized one card per form,
probable-impact cases only. Delivered review-short:25 forms/32 relevant contexts,
selected when assistant context estimate is below original human form rating.
This is triage, not exhaustive coverage. One selected familiar sense plus one
explicit form score; estimates optional. Full audit remains reference material.

Old context answers/events/notes remain untouched; new form decisions use a
separate schema/version. Old raw snapshots retained and reread on reload/export.
Context1 closes a form even if that context is excluded from the shortlist;
no synthetic ratings. Existing complete shortlisted contexts also resolve a card.
A new score above an old context score flags a conflict and stays uncompleted.

**Next:** finish only the short round; import form decisions separately from
context labels, recompute derived statuses, inspect conflicts/notes, update the
comparison with provisional coverage. Do not require172 ratings. Earlier
independent-label/held-out and sequential-D1/RAM constraints remain.

[Short round](../../build/d1/pilot-2026-10-17/review-short/README.md)
· http://127.0.0.1:8765/review-short/.

## Short25 review imported — 2026-10-21 (current recommendation)

25 explicit form ratings imported;0 unresolved.19 decrease from the initial
ratings,6 unchanged.14 forms now at1 (numeric minimum closed);11 remain provisional
against unreviewed senses. The ai/other note explicitly describes second-person
a avea: retained raw, analytically mapped to79068:have; no user clarification
needed and no new per-sense labels manufactured.

New assistant estimates:16/25 exact (64%), MAE0.36; all differences one level.
First choices15/25 (60%), MAE0.40.22 first ratings preceded their own AI panel;
21 final ratings preceded it.19 panels opened,3 revisions: circulat1→2 before
reveal; in2→3 after reveal (away from estimate); înșelat2→1 after (toward estimate).
This remains selected, definition-assisted single-rater development data; not D1
performance or independent validation. Original AI numeric agreement7/25 has a
different semantic target and must not be used to claim model degradation.

**Annotation phase closed for this pilot.** Do not request the remaining172
contexts. Preserve25 form labels separately from46 prior context labels/12 minima.
Working-reference150 has37 entries under the clarified target and113 original
opaque form/POS labels, with per-row provenance/coverage;24 numeric changes versus
the initial150. No mixed-rubric global accuracy.

**Recommended next implementation:** freeze the reference and align model/evidence
input to exact Scrabble surface across valid POS; verify that contract offline on
the37 development cases. Then compute comparable exact-form frequency baselines
(wordfreq and rebus definitions), preserving missingness and avoiding lemma or
diacritic substitution. Prepare a separate held-out batch and independent labels
before calibration. D1 trials remain sequential and conditional on RAM; no model
was loaded in this iteration. Replacement decision still awaits empirical results.

[Imported comparison](../../build/d1/pilot-2026-10-17/data/evaluations/2026-10-21-fabian-short/comparison-report.md)
· [25 form labels](../../build/d1/pilot-2026-10-17/data/evaluations/2026-10-21-fabian-short/form-labels.csv)
· [Working reference150](../../build/d1/pilot-2026-10-17/data/evaluations/2026-10-21-fabian-short/working-reference-150.csv).

## Exact-form contract and frequency comparison — 2026-10-21 (current recommendation)

Implemented with TDD on PR81 sources: exact surface + every matching LOC entry +
curated all-POS contexts; inventory POS is historical, nonrestricting metadata.
Frozen150 forms /218 lexical contexts, with no human/AI scores in model inputs.
D1 request contract updated and verified with simulated HTTP only; no model loaded.
Offline CSV commands and manifests preserve source/implementation hashes, missingness
and source-bounded coverage. No lemma/inflection/diacritic substitution.

Compared the37 clarified development labels; excluded113 opaque initial labels.
Both wordfreq3.1.1 and rebus cover29/37; union32, intersection26. On the same26,
Spearman with familiarity is0.451 for wordfreq and0.536 for rebus. No fitted
thresholds or classification-accuracy claim. Rebus contributes țanc/antereu/izotop;
wordfreq contributes carter/pinot/ata. Five forms remain unobserved in both.
Rebus has zero observations among the4 forms rated5; coverage-conditioned metrics
must not be interpreted as evidence of rare-word classification quality.

Rebus extraction:12,728 local cache files;60 target/collision pages excluded,
147 non-ok;114,689 unique definition bodies /1,280,002 tokens,59,809 duplicate bodies
removed. Wordfreq export reused with its original digest. Initial/form/context labels
remain unchanged. Results: [frequency comparison](../research/2026-10-21-exact-form-frequency-results.md).

**Next:** preserve both sources as separate signals; prepare independent, family-separated
held-out labels before fitting thresholds/hybrids. Keep this pilot development-only;
no further172-context round. Then evaluate same-target frequency ablations and,
when RAM permits, sequential D1 without/with evidence. No replacement/upload decision yet.

**Leftovers:** independent second-rater agreement; locked calibration/test split;
held-out threshold and rare-error comparison; D1 runtime/quality trial; source-bounded
lexical coverage remains a stated limitation, not another mandatory annotation round.
Implementation checkout: `build/d1/exact-form-code/`, based on open PR81 f990e6c;
main checkout left intact because it lacks PR81 and contains unrelated local changes.
Final experiment artifacts: `build/d1/exact-form-evaluation-2026-10-21-v2/`.

## Independent40 prepared — 2026-10-23 (superseded below)

40 unseen inventory forms,10 per wordfreq band;70 lexical contexts on40 cards.
Pilot150/collision IDs excluded; conservative family review recorded. Cache-covered
diagnostic sample, same rater, definition-assisted and estimate-blind. New namespace
preserves earlier answers; no predictions/frequencies/strata sent to the UI.

User-authorized calibration now fixed on37 clarified pilot labels only, before
new labels. Shared rebus corpus excludes190 targets;100 pages removed.29 observed
fit cases per source. Training MAE wordfreq0.4828/rebus0.3448 is **not** validation.
Rebus L4/L5 boundary remains an explicitly unvalidated convention (no observed
pilot5). Predictions and assistant estimates sealed outside the web root.

**Next:** finish this single40-card round, export/import JSON+CSV, compare matched
MAE, coverage, agreement and severe rare-word errors under frozen thresholds.
No tuning on the new labels; no mandatory further sense-audit round.
**Leftovers:** actual held-out comparison; second-rater agreement; D1 feasibility
and sequential quality trials when RAM permits; source-bounded lexical coverage.
No D1 loaded, no production classifier/upload changes.

[Protocol, thresholds and artifacts](../research/2026-10-23-independent-form-round.md).
UI: http://127.0.0.1:8765/review-independent/.
Implementation branch: `codex/independent-form-benchmark`, based on PR82.

## 2026-10-23 — Revised scope: reuse existing annotations, no new user round

User declined any additional annotation:150 forms already evaluated, with later
clarifications preserved. The40-card round is withdrawn from the required workflow;
its artifacts remain unused/unlabelled, not a benchmark with human ground truth.
Do not ask the user to complete it or replace human labels with assistant estimates.

Next comparison uses existing answers only. Keep a150-row view with the latest
available human score and explicit provenance. Primary exact-form metrics use37
clarified forms; report the113 initial opaque form/POS labels separately as a
historical diagnostic, without claiming a single homogeneous150-form benchmark.
No annotations discarded or silently reinterpreted as sense labels.

For a less optimistic internal estimate on37, use leave-one-out calibration:
fit thresholds on the other36 clarified forms, predict the omitted form, and
compare sources on the same covered cases. Keep missingness/rare-error counts
explicit. This is internal cross-validation of selected development data, not
independent validation. Existing all37 fitted thresholds remain a reproducible
training-fit artifact, not a test result. Do not tune against the omitted label.

No additional user annotation is a prerequisite. New human ground truth and
second-rater agreement are deferred, optional future work. D1 remains unloaded;
any future inference must be sequential and separately authorized.

## Cross-validation completed — 2026-10-23 (current recommendation)

37 clarified leave-one-form-out folds; each held-out label removed before fitting.
All150 retained in CSV;113 opaque initial labels evaluated only as a separate
historical diagnostic with the full37 model, never included in calibration.
Frozen features/corpus and threshold policy unchanged. No D1/LM calls.

Matched26: MAE wordfreq0.538, rebus0.500; source-matched training-median baseline
0.500. Only1 total absolute-error point separates sources; severe errors2 vs4.
Own coverage29/37 each; own MAE0.759 vs0.517 (different subsets). Rare4/5 coverage
3/8 vs2/8; all3 observed wordfreq rare forms severely underestimated. Rebus observes
none of4 human5 forms, so its L5 convention remains unsupported. No replacement
decision justified. Historical matched64: MAE0.625 vs0.563, not a CV score.

**Next:** keep both frequency sources as separate optional evidence with explicit
abstention. Preserve this baseline; no new threshold/hybrid tuning to improve it.
When RAM and explicit loading authorization permit, compare sequential D1 without
and with evidence on the same existing labels, separating37/113. No new human
annotation required. **Leftovers:** D1 runtime and quality comparison; rare-word
coverage; optional independent-rater/generalization evidence. Production unchanged.

[Results, errors and limitations](../research/2026-10-23-frequency-cross-validation.md).
Artifacts: `build/d1/cross-validation-2026-10-23-v2/`.
Verified796 tests +112 subtests, input/output hashes and all37 exclusion folds.

## Full150 baseline suite completed — 2026-10-23 (current recommendation)

All150 evaluated in two separate label views: original-round-final and latest
working labels; latest is explicitly mixed37 clarified/113 original. Added149
immutable first-independent labels as a third learned-model validation, not just
saved-AI scoring.449 LOO folds;149/148 train labels; fold-only imputation/scaling.
Fixed historical legacy/AI, median/majority, individual frequency thresholds,
source-matched medians, and fixed-alpha1 Ridge with logs+missing flags. No D1.

Latest150 full-coverage MAE: legacy1.740, AI0.473, Ridge0.533, median1.227.
First-independent149: legacy1.685, AI0.557, Ridge0.671, median1.188.
Latest matched90: wordfreq0.400, Ridge0.444, AI0.544, rebus0.567. Individual
frequency coverage101/150 and110/150; never rank their own-subset MAE against
full150 without matching IDs. Latest rare43: Ridge4 severe underestimates,
wordfreq5/5 observed rare, rebus6/15 observed rare. Missingness is learned,
not proof of rarity:25/29 fully missing forms are rare in this selected pilot.

**Next:** retain Ridge as the local experimental baseline, AI as a historical
reference, wordfreq as a separate source. Before any production decision, check
family-group robustness and a missingness-only control on existing labels.
No parameter search to improve this report; no new human annotation required.
**Leftovers:** those robustness checks, generalization beyond this selected pilot,
optional future sequential D1 when explicitly authorized and RAM permits.

[Full results and provenance](../research/2026-10-23-full-pilot-baselines.md).
Artifacts: `build/d1/full-pilot-baselines-2026-10-23-v2/`.
Ruff +797 tests/112 subtests pass; all449 fold exclusions/scalers audited.


## Mandatory complete coverage — 2026-10-24 (current recommendation)

Supersedes source-only rankings and abstention as an operational option. A method
must score every form; own-coverage MAE remains diagnostic. Implemented fold-local
missing-source median fallback, with global training median for empty support or
unavailable threshold model. All primary methods now cover150/150.

Latest150: wordfreq+fallback MAE0.520 (86 exact,11 severe), Ridge0.533 (80 exact,
9 severe), rebus+fallback0.680 (64 exact,16 severe), historical AI0.473, legacy1.740.
Wordfreq49/rebus40 fallback predictions all learn4; no hard-coded rarity assumption.
First-independent149: wordfreq0.624, Ridge0.671, rebus0.805. Latest clarified37:
Ridge0.514 beats wordfreq0.568. Keep all views and provenance strata separate.

**Recommendation:** wordfreq+fallback as the simple complete offline baseline;
Ridge as challenger for severe-error and clarified-form performance. Wordfreq's
latest MAE advantage is only2 total absolute-error points; no production promotion.
**Next:** missingness-only control and family-grouped validation on existing labels.
**Leftovers:** those robustness checks and generalization evidence; future sequential
D1 only with explicit authorization and sufficient RAM. No new user ratings needed.

[Complete comparison](../research/2026-10-24-complete-coverage-baselines.md).
Artifacts: `build/d1/complete-coverage-baselines-2026-10-24/`.
TDD + Ruff;800 tests/115 subtests pass.449 folds audited; previous predictions
unchanged, complete scores and fallback support verified. No D1/LM requests.

## Robustness checks completed — 2026-10-24 (current recommendation)

Implemented three fold-trained presence controls and optional group-held-out
validation at the existing CSV seam. All methods retain100% coverage. Reused all
three reference views;898 per-form predictions checked across LOO/grouped runs.
Frozen groups preserve6 original family/collision pairs and add2 conservative
lexical links:142 groups,16 paired forms in latest150. Shared prefixes alone
rejected (iț/ițar and numărat/numitor not merged). Group map has explicit limits.

Latest grouped MAE: wordfreq+fallback0.520, Ridge0.533, joint-presence0.587,
rebus+fallback0.693; source-only presence controls0.767 and0.867. Numeric frequencies
add information beyond presence. Wordfreq latest predictions unchanged from LOO;
only16 forms have changed training sets, so aggregate stability is weak evidence
for broad generalization. First-independent149: wordfreq0.624, Ridge/joint-pattern
both0.664, rebus0.805. Ridge still better on latest clarified37 and large mistakes.

**Recommendation:** retain simple complete wordfreq baseline, Ridge comparator;
no additional pilot-driven hybrid tuning. **Next implementation:** freeze fitted
wordfreq threshold/fallback config, deterministic offline scorer with route/version
provenance, then shadow CSV export over the full inventory. Validate coverage,
reproducibility and fallback rates; unlabelled export does not measure accuracy.
No production upload or new user annotation in that next step.
**Leftovers:** scorer/config/export, inventory operational checks, generalization
evidence, future sequential D1 only if explicitly authorized and RAM permits.

[Results and grouping limitations](../research/2026-10-24-frequency-robustness.md).
Artifacts: `build/d1/robustness-baselines-2026-10-24/`.
TDD + Ruff;804 tests/122 subtests pass. Independent artifact and planner audits
confirm group exclusions, presence supports, full coverage and metrics. No D1 calls.

## Frozen offline scorer and full export completed — 2026-10-24 (current recommendation)

Implemented CSV freeze/score functions and CLI commands using TDD. Exact-form
wordfreq export now pins corpus digest and lookup policy; scoring validates exact
inventory/source/config identity, preserves every ID/POS and records frequency,
route and model version. Runtime never refits. Existing abstaining scorer unchanged.
Committed configuration: `configs/wordfreq-ro-pilot-2026-10-24.json`, model version
`8f3061e2332cf9d6844ff4ea9dabd4fd23111c04b713a8a0cde886a23c82e0cc`.
Fit on latest150,101 observed/49 missing, fallback4; global emergency median2.

Complete saved inventory exported:77,698 records/75,147 forms;11,610 direct and
66,088 fallback (85.06%, versus32.67% in selected pilot). Histogram1..5:
972 /6,283 /4,355 /66,088 /0. Positive frequency floor exceeds both rare-class
boundaries; direct scores1–3, missing forms4. No fabricated5 or histogram repair.
The saved inventory hash matches the pilot source; no database query/write.

**Recommendation updated:** implementation complete, keep frozen shadow baseline;
do not promote to production. Full-inventory missingness exposes poor rare-form
discrimination despite complete coverage. **Next:** read-only coverage audit of
additional local lexical/frequency evidence for fallback forms; evaluate any future
candidate against existing labels before a new export. No extra annotation required.
**Leftovers:** better4/5 discrimination and generalization evidence; production
integration/upload only if later authorized and semantic gates pass; D1 remains
unloaded, any future model run requires explicit authorization and sufficient RAM.

[Export results and reproduction](../research/2026-10-24-offline-wordfreq-export.md).
Artifacts: `build/d1/offline-wordfreq-2026-10-24/export/scores.csv` plus frozen config,
source snapshots, manifests and replay. Ruff +811 tests/137 subtests pass; complete
independent numeric/identity audit and byte-identical77,698-row replay. Actual CLI
runs blocked HTTP and DB connection boundaries. Architect review passed.

## Local fallback-source audit completed — 2026-10-24 (current recommendation)

Audited66,088 fallback rows/64,226 distinct forms, without changing scores/config.
Streamed12,728 local DEX cache pages; hashes and old190 frequency counts reproduced.
LOC matches every form but provides validity/POS, not familiarity. Query-exact
nonempty cache pages cover7,334 rows; prior review snapshots extend that to7,375.
Outside-own-page definition mentions cover13,991 rows. Union across local raw
snapshots/mentions:18,769 rows/17,898 forms;47,319 rows still lack either signal.
Page/query match is candidate evidence, not verified meaning/all-POS coverage.

Supplemental review archives restore raw lexical source coverage for all49 pilot
forms without wordfreq. Existing218 authored contexts cover only36 of those49;
use uniform parsing of raw sources, never label-exposed estimates/rationales or
review-selection flags. Regional/archaic HTML menu text is not a usage marker.
Legacy generator scores are inherited and disagree with classifier snapshot on
43,890 exact-match rows; do not borrow as independent gold. No separate broad
natural-language corpus found in scoped local workspaces; installed ro wordfreq
has no large list. One minimal status-ok CASA cache payload needs provenance check.

On existing group-held-out tail predictions, presence-pattern MAE0.592 beats
constant4 at0.653 by only3 aggregate error points, but severe errors rise2→6.
Only16/29 predictions5 are correct (13 false5); the gain disappears on immutable
first-response labels. No validated replacement for4/5 separation yet.

**Next:** implement a uniform source/sense/POS-aware lexical evidence extractor,
starting with the49 local pilot snapshots; retain usage scope and ambiguity.
Test one small predeclared interpretable fallback candidate on existing grouped
folds, reporting all150, tail49,4/5 precision/recall and false5 on human1–3.
Allow lower scores when supported:11/49 latest tail labels are2/3. Keep4 where
coverage/sense alignment is unresolved; do not turn absence into5 or tune to a
histogram. No new human annotation required. **Leftovers:** validate lexical
features, improve broad-source coverage and generalization; no production promotion,
DB write or D1 loading authorized by this audit.

[Source audit and recommendation](../research/2026-10-24-local-fallback-source-audit.md).
Combined evidence: `build/d1/local-source-audit-2026-10-24/fallback-local-evidence.csv`.
Audit/diagnostic/supplement scripts and hashes saved;77,698 identities and merged
coverage checked. Classifier implementation, frozen model and output CSV unchanged.


## Local lexical fallback implementation prepared — 2026-10-25

User authorized TDD implementation of local evidence extraction and one simple
fallback comparison on all150 ratings, with separate4/5 results. Proposed public
boundaries: raw-source/LOC/mentions CSV inputs → senses/evidence/source-ledger CSVs;
validated evidence + labels/frequencies/groups → grouped predictions/metrics.
TDD skill requires explicit seam confirmation; question pending before tests/code.

Predeclared protocol saved at `build/d1/local-fallback-2026-10-25/protocol-proposed.json`.
Candidate: depth2 absolute-error tree, min leaf5, seed0, lower-median leaves;
features cross-entry definition counts, all-senses restriction and specialist tags.
Unknown exact-form/POS alignment→4. Fit direct wordfreq thresholds and fallback
only on training groups, never reuse frozen all150 thresholds for held-out metrics.
Preserve latest150, original-final150, first-independent149 and37/113 strata.
No results yet; existing frozen scorer/config/export remain unchanged.

Parser review confirms structured headings, explicit inflections, multiple POS
heading blocks and inherited parent-sense tags. Redirects such as micșurat→micșorat
must remain unresolved. No database or D1 access. Next: confirm CSV seams, then
vertical red/green slices, grouped comparison, independent review and results.

## Local evidence + fallback experiment completed — 2026-10-25 (current recommendation)

CSV interfaces confirmed; implemented with vertical TDD. Exact structured headings,
explicit inflections, all known LOC POS, inherited sense tags and source hashes
exported independently of labels. Two offline CLI commands; no production changes.
150 evidence rows;168 sources/134 forms,123 source-bounded aligned, including42/49
tail forms. Seven tail forms unresolved→4; raw query match alone is insufficient.

One predeclared depth2/minleaf5 median-leaf tree, three lexical/count features,
no search. Shared direct wordfreq thresholds refit within frozen group folds;
latest150/original150/first-independent149 all100% covered,37/113 strata retained.
Latest MAE0.520→0.500, severe11→12; tail0.653→0.592. Clarified37 worsens0.568→0.595.
First-independent149 worsens0.624→0.671; tail0.653→0.796. Latest predicted5=24,
correct13 (54.2% precision);8 human4 and3 human3 become5. Tail human4/5 exact19→21/38.
Only cross-entry count is selected in tree splits; tag evidence too sparse to split.

**Recommendation:** retain frozen wordfreq+fallback4. Preserve the extractor and
comparison tools; do not promote this candidate or rescore the full inventory.
**Next:** investigate a versioned independent Romanian running-text corpus/source
and its exact-form coverage/provenance before another model. No new annotation
required for discovery; no repeated tree tuning on the same150. **Leftovers:**
broad coverage, exact-sense alignment, robust4/5 separation and external validation.
DB and frozen scorer/config/export unchanged; no D1 or model server calls.

[Implementation, results and reproduction](../research/2026-10-25-local-lexical-fallback.md).

Final checks:832 tests/173 subtests +Ruff pass. Mandatory mention sidecar binds
corpus policy/ledger/extractor/derivation and projected counts; plural-only meanings
cannot leak into singular targets. Review corrected19 sense rows, unchanged scores.
Independent449-fold audit and457-artifact CLI replay pass; no open review findings.
Final local artifacts: `build/d1/local-fallback-2026-10-25/evidence-final/` and
`comparison-final/`; frozen scorer/config/full inventory export verified unchanged.


## Romanian running-text corpus research — 2026-10-25 (current recommendation)

Investigated public access and advertised terms; no new corpus coverage measured.
FineWeb2 Romanian train is anonymously readable (actual HTTP206/200 probes), pinned
revision af9c13333eb981300149d5ca60a8e9d659b276b9;20 shards≈85.37GiB. Database ODC-By1.0
plus Common Crawl/content rights. Crawl dates2013–April2024, not live2026 text.
CoRoLa publishes a complete lowercase word-form list (1.81M entries), but BY-NC-ND
limits reuse: optional eligible noncommercial diagnostic, not automatic app dependency.
Leipzig news2011 API works but bulk licence unresolved; SETIMES archive reachable,
CC-BY-SA version/unique text volume need checking. OSCAR access explicitly suspended;
CulturaX gated. Full current ParlaMint release omits RO. wROdfreq relevant but no
frequency binary or repository licence verified; not an immediate drop-in.

**Next experiment:** coverage-first FineWeb2 sample, sequential bounded range reads,
≤100k examined documents /≤1GiB transferred including metadata, whichever first;
fixed seed/manifest spread across20shards, verify balanced sampling feasibility.
Report2020–2024 primary slice and older separately; freeze exact tokenizer, exclusions,
source/input hashes. Export every66,088 missing row/64,226form and pilot targets,
with token/document/host counts and denominator; keep zero as unobserved.

Only after coverage/quality gate: one predeclared wordfreq→supported corpus frequency
→4 candidate; thresholds fit inside existing group folds. Proposed support floor
5occurrences/3docs/2hosts, fixed before labels; insufficient training support stops
calibration. Full150,missing49,37/113,first-independent149,4/5confusion/false5/severe
errors reported. No promotion if first-response performance or severe errors worsen.
Common Crawl ancestry may overlap wordfreq; new source is not independent gold.
No new user annotation. Retain frozen wordfreq+4 pending validated improvement.

**Leftovers:** extractor/TDD, real coverage, sample quality/recency, comparison and
robust4/5 discrimination; larger sample only if coverage justifies cost. No D1,
database access, raw-text corpus redistribution or frozen config/export changes.
[Source/access/licence audit and experiment protocol](../research/2026-10-25-romanian-running-text-corpora.md).


## FineWeb2 bounded experiment completed — 2026-10-27 (historical recommendation)

Both public CSV seams confirmed; vertical TDD implemented source exporter, bounded
HTTP transport and grouped evaluator. 860 tests / 200 subtests + Ruff pass. Review
fixed hidden Requests redirect-body reads, checkpoint integrity and interrupted
publication after disk recovery. No remaining blocking findings.

Real sequential run: 100,000 examined documents; 100 row groups across 20 shards,
5,000 documents per shard. Payload 385,836,138 bytes; charged 436,626,538 bytes
(~416 MiB), including 40 MiB parser allowance and request overhead; below 1 GiB.
No full shard cache; local artifacts ~180 MiB. Primary 2020–2024: 70,255 documents /
35,932,359 tokens; older 29,715 documents separate; 30 dictionary pages excluded.
Crawl date does not prove publication recency.

Missing wordfreq: 25,211/66,088 rows observed (38.15%); 12,110 meet the fixed
5 occurrences / 3 documents / 2 hosts rule (18.32%). Distinct forms: 24,319/64,226
observed; 11,650 supported. Operational scoring coverage remains 100%.
Pilot: 125/150 observed, 109 supported. Missing 49: 24 observed, only 8 supported.
Those 8 have latest labels 2×level2, 1×level3, 5×level4, none level5. Among the 19
level5 tail forms, 5 are observed and none supported. No training fold reaches 10.

Comparison completed on all three existing label views. No FineWeb model fitted;
all candidate predictions equal baseline. Latest 150: MAE 0.520, 86 exact, 11 severe
errors; missing 49: MAE 0.653, 19 exact, 2 severe. First-independent 149: MAE 0.624,
13 severe. Tail 4 vs 5: 19 human4 + 19 human5 all predicted4; 19/38 correct and
zero level5 recall. This is insufficient calibration data, not a tie between two
successfully trained classifiers. Floors unchanged.

Label-blind audit: 20 deterministic forms + all 8 supported pilot forms. Found
copied passages across unrelated hosts, SEO lists, malformed translations and
names/brands. Small snippets cannot estimate corpus precision. Whole-body dedup
and host count do not establish independent valid uses. No posthoc filter tuning
or additional annotation.

**Recommendation:** keep frozen wordfreq + fallback4. **Next:** eligible noncommercial
CoRoLa complete exact-word frequency-list diagnostic; first measure support for
existing level5 examples under its BY-NC-ND terms. Keep corpus denominators separate;
no automatic redistribution of restricted derived data. Further FineWeb work needs
predeclared passage/source-quality handling before another download.

**Leftovers:** clean rare-class evidence, 4/5 discrimination and generalization.
A learned FineWeb fallback remains untested because its data gate did not pass.
Independent source/budget/checkpoint/identity audit passes; 449 folds / 36 metric
sections independently recomputed; baseline matches the earlier experiment.
Completed-source replay with HTTP/DB forbidden is byte-identical. Frozen inputs
and scores unchanged. No D1, DB connection, production promotion, push or new PR.

[Full results and reproduction](../research/2026-10-27-fineweb-bounded-experiment.md).
Artifacts: `build/d1/fineweb-2026-10-26/` (prepared 26th, run 27th).


## CoRoLa noncommercial experiment completed — 2026-10-28 (experiment decision)

User authorized noncommercial research. Published CoRoLa v1 complete lowercase
word-form list acquired and verified: 114 MB ZIP; one 23.7 MB TSV; retained campaign
about 141 MiB. CC BY-NC-ND 4.0 source/derived CSVs remain local. No D1, database,
production-score change, new annotations or remote publication.

Completed with TDD at existing CSV seams. Full inventory projection retains all
77,698 IDs/POS, exact normalized spellings and source/hash provenance. Shared grouped
comparison engine preserves FineWeb behavior; CoRoLa adds no fabricated document/
host support. Fixed before counts: count≥5, minimum10 eligible training forms/two
levels, monotone thresholds fitted outside each held-out group; otherwise4.

**Coverage:** 144/150 pilot forms observed,136 with count≥5. Missing-wordfreq pilot:
43/49 observed,35 supported, including7 latest-human5 forms. All22 latest-human5:
16 observed,10 supported. Full missing inventory:49,464/66,088 rows observed
(74.85%);37,614 supported. Every method still returns150/150 scores.

**Results:** latest MAE0.520→0.533, severe errors11→13; tail49 MAE0.653→0.694;
clarified37 MAE0.568→0.649. First-independent149 MAE0.624→0.617 but severe13→15;
original-final150 MAE0.707→0.700 but severe18→19. Unlike FineWeb, all35 supported
tail forms actually use fitted CoRoLa fallback models. Latest6 changes all4→5:
bromocet/hipochinezie corrected; clevetitor/ițar become wrong; antereu/sezisa gain
errors of two levels. Latest precision5=2/6, recall5=2/22; tail4/5 exact stays19/38.

**Decision:** keep frozen wordfreq+4; do not promote CoRoLa fallback. Coverage improves,
but severe errors worsen in every label view. Do not tune support/cutoffs on these
results or infer5 from absence. Preserve intentional human labels, including micșurat5.

**Next:** small diagnostic audit using existing local source records for the nine
changed forms across views plus ata/carter/dorian on the direct path. Separate
sense/form ambiguity, historical label changes and overlap between frequency and
familiarity. No new user evaluation required. Explanations based on these known
labels are not independent training features. If no general defensible rule emerges,
stop tuning this pilot and retain the baseline pending independent evidence.

**Leftovers:** robust4/5 separation; absent/weak evidence; valid-sense/POS corpus
attribution; external generalization; permission before future commercial/distributed
CoRoLa-derived resources. No larger web download or additional threshold search
recommended from this result alone.

Verification:871tests+211subtests and Ruff pass; two-axis code review clear.
Independent raw-source/count/hash audit,449 folds,554 independently reoptimized
models and36 metric sections pass; all449 baseline predictions match prior run;
frozen scorer/input hashes unchanged. [Full report](../research/2026-10-28-corola-experiment.md).
Local artifacts: `build/d1/corola-2026-10-28/`; implementation in
`build/d1/exact-form-code` on current branch. No push/PR this iteration.


## Local divergence audit completed — 2026-10-28 (decision before extraction repair)

Audited the nine forms changed in at least one CoRoLa label view plus ata/carter/
dorian on the direct wordfreq path. Existing local dictionary records, human
annotations,35foldrecords, saved FineWeb contexts and the case-preserving member of
the already-downloaded ZIP only. No new labels, fitting, download, D1 or DB access.

**Findings:**
- Exact frequency collisions: antereu/diorit both20 occurrences but latest labels3/5;
  clevetitor/xilem both18 but labels4/5. A single frequency-only mapping cannot
  distinguish each pair. Different out-of-fold predictions reflect different
  training folds; latest audited4/5 cutoffs correspond to16.02 or25.39 occurrences.
- Human decisions already settle the familiar valid sense: antereu3 after explicit
  form review; sezisa3=min(3,5,5,5); ițar4=min(cloth4,loom5), excluding plural-only
  trousers. Ata and both carter meanings remain5. No relabeling needed or done.
- Case-preserving CoRoLa: carter1427/1532 anddorian844/853 occurrences have uppercase;
  saved FineWeb snippets are person names. This is an ambiguity risk, not a measured
  proper-name fraction in CoRoLa/wordfreq. Ata snippets reflect unaccented ață.
  Blanket uppercase exclusion would leave hipochinezie2/12, removing its support.
- Lexical extractor gap: antereu/sezisa marked unresolved despite explicit variant/
  exact historical-entry witnesses; ata's selected source resolves to ață, while
  local ata/atu records contain the needed explicit relation and femininePOS.
  This is evidence coverage, not a CoRoLa counting/scoring bug.
- Secondary case-preserving list denominator differs by2725tokens from primary
  lowercase list; cause unresolved. All12target counts reconcile. Primary counts,
  denominator, predictions and frozen scorer remain unchanged.

**Decision:** retain frozen wordfreq+4; no candidate promotion, per-word exceptions,
uppercase filtering or new threshold search. Existing CoRoLa results still apply.

**Next engineering step:** repair the general local lexical-evidence path with
explicit variant/entry witnesses, target-specific POS/number scope and raw-source
provenance; include already-saved linked sources such as atu when justified for
ata. Keep casing/diacritic ambiguity as separate diagnostic metadata. Do not merge
variant frequencies, substitute lemma familiarity, or change production scores.
Public CSV regression cases: positive antereu/sezisa/ata witnesses; negatives for
ata←ață, ițar←plural-only ițari, and unverified spelling similarity. No additional
user evaluation or corpus acquisition needed for this work. Any later scorer trial
needs a predeclared general hypothesis; evidence repair alone does not prove gain.

**Leftovers:** validated4/5 discrimination, context-aware sense/POS evidence and
external generalization; existing opaque form/POS labels retain their provenance.
Audit closed—no UI review queue. Source/derived CoRoLa data stay local noncommercial.

Independent audit passed:492input hashes,12cases,35foldrecords,16rawlexical witnesses,
case-count reconciliation and existinghuman minima. No production code changes;
no repeat scorer test run required. [Audit report](../research/2026-10-28-corola-divergence-audit.md).
Artifacts: `build/d1/corola-divergence-audit-2026-10-28/` including CSV ledger,
source/context receipts, audit script and independent `verification.json`.


## Lexical variant extraction repaired — 2026-10-28 (current recommendation)

Completed with TDD through the existing `export_local_evidence` CSV boundary.
Explicit variant declarations retain target POS/gender, usage/number restrictions,
dictionary/entry identity and source path/hash. Structured sense transfer requires
matching source, headword and POS; raw parsing accepts only the bounded MDA2 format.
Contradictory meaning POS, ambiguous homographs and insufficient restrictions remain
unresolved. New `variants.csv` ledger; additive sense provenance fields; unchanged
`evidence.csv` schema and scorer seam. No frequency or familiarity transfer.

Local replay: all 150 forms, 169 source records; 14 added exact source-backed sense
records (12 distinct form–sense identities), covering antereu, sezisa, ata and
văietare. Aligned forms **123→127/150**, missing-wordfreq slice **42→45/49**.
All 978 prior exact records retained; 26 variant witnesses (22 supported relations,
4 unresolved). Supported relation is not exhaustive sense recovery. Ata remains
feminine and “învechit și rar”; no money sense imported from another dictionary.

**Decision:** retain frozen wordfreq + fallback 4. Existing scores, human ratings,
thresholds and evaluations unchanged; no new labels, D1, DB access or downloads.
This repairs evidence extraction, not demonstrated scoring quality. No new accuracy
claim or threshold search on the reused pilot.

**Next recommendation:** use the versioned evidence as explanations alongside frozen
scores, distinguishing supported relation, recovered sense and unresolved evidence.
Any later scorer experiment requires a predeclared general hypothesis and separate
validation; no additional human evaluation round requested.

**Leftovers:** unsupported raw dictionary formats (including ata's separate money
sense), incomplete source/POS coverage, contextual ambiguity, reliable 4/5 separation
and external generalization. These remain explicit limits, not guessed senses or
per-word scoring exceptions.

Verification: **880 tests + 220 subtests**, Ruff and two-axis review passed after
fixing a raw-meaning POS conflict. Independent source/hash verifier PASS; all 1,150
protected inputs unchanged. [Report](../research/2026-10-28-lexical-variant-extraction.md).
Authoritative local artifacts: `build/d1/lexical-variants-2026-10-28/evidence-reviewed/`,
`evidence-reviewed-comparison.json`, `verification-reviewed.json`.
Implementation in `build/d1/exact-form-code`; committed locally, no push this iteration.
