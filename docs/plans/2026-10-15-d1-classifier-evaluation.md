# D1 adapter and Romanian Scrabble evaluation plan

Date: 2026-10-15. Updated: 2026-10-16. Status: offline implementation delivered; live validation and replacement decision pending. See implementation status below.

Recommendation: build an offline evaluation harness first, then a Step2 scoring adapter for D1 through LM Studio `/v1/systemone`. Evaluate D1 alone, with dictionary evidence, and alongside frequency features. Replace the existing scorer only if held-out Romanian results justify it. Expect a hybrid scorer to be a stronger candidate than D1 using word spelling alone; treat that as a hypothesis.

## What D1 and Jev provide

Jev is TypeSafe AI's System One model: state plus typed questions produces choices, scores, or yes/no probabilities. Type safety limits possible outputs; it does not establish that a Romanian lexical judgment is correct. D1 is Liquid AI's separate open-weight decision model, sharing the decision interface concept rather than Jev's weights or demonstrated performance. [TypeSafe introduction](https://typesafe.ai/blog/introducing-system-one-models-and-jev), [Liquid AI release](https://www.liquid.ai/blog/d1-open).

D1-3B returns typed judgments and probabilities in one forward pass rather than generated prose. Its advertised language metadata excludes Romanian; Romanian lexical rarity remains unvalidated. Evaluate the exact local Q8_0 artifact, not published full-precision benchmarks. [D1 model card](https://huggingface.co/LiquidAI/d1-3B).

Local inspection: LM Studio 0.4.26 build 4, llama.cpp runtime 2.58.0, server on port 1234. `d1-3b` Q8_0 GGUF is recognized as `decision`, `lfm2-d1`, unloaded. The FP16 MLX copy is listed as ordinary `llm`; do not assume it provides equivalent decision behavior. Supported HTTP shapes include `/v1/systemone` and `/v1/decisions`; start with the documented former. [LM Studio release](https://lmstudio.ai/changelog/lmstudio/lmstudio-v0.4.26), [System One contract](https://lmstudio.ai/docs/developer/jev-compat/systemone).

## Target and population

Provisional target: familiarity of each eligible word to an ordinary adult Romanian speaker, retaining the existing direction 1=common through 5=obscure. Corpus frequency is evidence for familiarity, not its definition. Confirm this target before annotation.

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
