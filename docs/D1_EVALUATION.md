# Evaluate D1 on Romanian Scrabble words

Current evaluation target: **d1-omni-2b** (updated 2026-10-29). Model selection stays
explicit through `--model`; the production offline wordfreq configuration is unchanged.
LM Studio's read-only model inventory reports `type=decision`, `architecture=lfm3`,
`decision_type=lfm3-d1-omni`, F16, 4,076,585,920 bytes and no loaded instances.
This establishes recognition, not inference compatibility or measured Romanian quality.
The separate `mmproj-*.gguf` is not the `--model-file` argument for this text campaign.

Experimental, sequential path. No command loads a model. Preparation, frequency baseline and reporting work offline. Run inference only after a matching D1 GGUF has been manually loaded and sufficient RAM is available.

Start from an explicit Scrabble inventory CSV with `word_id,word,type`; optional `family` groups related spellings. Source version is required provenance supplied by the operator, not an eligibility certification. Preserve diacritics; do not expand inflections. Select a curated 150-word pilot inventory before preparing it; keep representative and rare-word challenge sampling records separately.

## Prepare evidence and blind labels

Optional dependency for local frequency export: `pip install wordfreq`. The exporter records the installed version and output digest. No downloads performed by these commands.

```sh
python -m classificator evaluation-wordfreq \
  --vocabulary-csv pilot.csv --output-csv build/d1/frequencies.csv

python -m classificator evaluation-prepare \
  --vocabulary-csv pilot.csv --source-version YOUR_SCRABBLE_SOURCE_VERSION \
  --frequencies-csv build/d1/frequencies.csv \
  --dex-cache /Users/fabian/git/generator-rebus/.cache/dex_definitions \
  --campaign-dir build/d1/dataset --seed 42
```

Omit either optional evidence flag when unavailable. Existing output directories are refused. Generated files: vocabulary.csv, evidence.csv, labels.csv, manifest.json. Splits approximate 25% development, 25% calibration, 50% test by deterministic group hashing; small pilots need manual inspection of split counts. Families and ASCII game-key collisions stay together.

`wordfreq` missingness is censored coverage, not proof of extreme rarity. DEX exact-original matches only; ambiguous/missing definitions remain marked. Full HTML pages contribute definition spans, not navigation text. Dictionary token-frequency estimation is available through `evaluation-rebus`; see the exact-form section below.

Have Romanian speakers label familiarity 1..5 without model predictions or definitions. Keep independent rater records; write adjudicated values into a COPY of labels.csv. Do not overwrite the frozen dataset or use test labels for tuning. All rows supplied to the report require valid labels; for a partially annotated inventory, supply matching curated label and prediction subsets. Initial tooling does not perform annotation adjudication or statistical sampling automatically.

## Run D1 when memory permits

```sh
python -m classificator evaluation-run \
  --vocabulary-csv build/d1/dataset/vocabulary.csv \
  --campaign-dir build/d1/omni-2b-word-only \
  --model d1-omni-2b \
  --model-file "$HOME/.lmstudio/models/LiquidAI/d1-Omni-2B-GGUF/d1-Omni-2B-F16.gguf" \
  --runtime-version ACTUAL_INSTALLED_RUNTIME_VERSION
```

Replace the runtime placeholder with the actual installed runtime version. The model key and F16 file above were verified locally on 2026-10-29; inference was not run. Never reuse a d1-3b campaign directory for this model. A second campaign with `--evidence-csv build/d1/dataset/evidence.csv` evaluates evidence assistance. For a definitions-only ablation, supply a derived CSV containing `word_id,definition,definition_status`; for frequency-assisted evaluation include `frequency,frequency_present`. Unknown evidence columns, including human labels, are rejected. Inputs and implementation changes require a new campaign directory.

Default English familiarity rubric is versioned in `scoring/d1.py`; no offensive-word rarity penalty. Comparing a Romanian rubric remains a development experiment. Full probabilities are saved; argmax selects the integer class, lower label wins an exact tie. `--min-probability` optionally abstains below a chosen maximum-class-probability threshold; default0 retains all valid predictions for unbiased initial evaluation. This threshold is not an estimated accuracy guarantee.

Artifacts: predictions.csv, run.csv, failures.csv, review.csv, summary.json, immutable manifest.json, records/ID.json. Records include raw request/response. Successful D1 predictions with confidence populate the compatible run.csv; unresolved/failed outcomes remain in diagnostic CSVs. Do not upload experimental scores without evaluating and satisfying existing semantic gates. `summary.json` includes coverage counts, cumulative latest-attempt scorer time and latency quantiles; it does not measure peak RAM or include discarded retry attempts.

Repeat the command to resume without repeating completed IDs. Add `--retry-failed` to explicitly retry failed IDs once each; it does not retry abstentions. HTTP errors are recorded without implicit retry loops. Failed/pending campaigns return exit code1. Separate campaign directories prevent mixing models/inputs; only one process may write a given campaign. Multiple independently launched processes are outside the single-run sequential guarantee.

The standard Step2 entrypoint also accepts D1:

```sh
python -m classificator step2-score --backend d1 --run d1-omni-2b-pilot \
  --base-csv build/d1/dataset/vocabulary.csv --output-csv build/d1/omni-2b-scored.csv \
  --model d1-omni-2b --model-file /path/to/matching-model.gguf --runtime-version ACTUAL_VERSION
```

Sidecars live beside the output, here `omni-2b-scored.csv.campaign/`. This path rejects force, skipped preflight, alternate endpoint, input overrides and limits: prepare the intended frozen inventory instead. For explicit failure retry, use `evaluation-run` against the same sidecar directory and matching `--run d1-omni-2b-pilot` identity, or a new campaign. No upload occurs. `--dry-run` never contacts the model. Production chat scoring remains the default.

## Baselines and held-out report

Use development labels to choose four descending frequency proportions for L1..L4 minima. Do not use the following illustrative thresholds as a calibrated production policy.

```sh
python -m classificator evaluation-frequency \
  --vocabulary-csv build/d1/dataset/vocabulary.csv \
  --evidence-csv build/d1/dataset/evidence.csv \
  --campaign-dir build/d1/frequency-baseline \
  --thresholds 0.001,0.0001,0.00001,0.000001

python -m classificator evaluation-report \
  --labels-csv build/d1/adjudicated-labels.csv \
  --predictions-csv build/d1/omni-2b-word-only/predictions.csv \
  --baseline-csv build/d1/frequency-baseline/predictions.csv \
  --split test --bootstrap-samples 1000 --seed 42 \
  --report build/d1/comparison.json
```

Missing/zero frequency abstains. Frequency predictions have no invented confidence or probability vector and are not exported as upload-ready run.csv rows. Existing chat run CSVs are accepted as baselines without a status column; they must describe the same gold-ID universe. Chat scores are operational predictions, not human truth. The ChatScorer adapter also supports programmatic sequential campaigns using the existing client/context and its established JSONL logs.

Reports include coverage/status counts, confusion with a missing column, ordinal MAE conditional on coverage, macro-F1 over gold-present classes, L1 precision/recall, rare recall, severe rare-to-common errors, Brier/log-loss/RPS with probability coverage, and paired grouped bootstrap intervals. MAE comparison uses only IDs scored by both systems, with paired coverage stated. Undefined metrics are null; fewer than two groups yields no bootstrap interval. Reports are unweighted gold-sample estimates, not population estimates. Weighted/sliced reports, calibration plots, automated promotion gates and fitted hybrid remain follow-up work.

## Verification and next experiment

`python scripts/check.py` runs Ruff and the complete offline suite. New tests use unittest interfaces, real temporary CSV/checkpoint files and simulated external HTTP/corpus data. No live D1 quality claim follows from those tests.

The pilot annotation phase is complete; no new user annotation is required. The
full150 baseline suite and independent-first-response149 sensitivity are available
in [the current results](research/2026-10-23-full-pilot-baselines.md). Keep the latest
plan as the current recommendation. D1 remains unloaded unless explicitly authorized
with sufficient RAM. Mandatory semantic upload gates and partial default remain.


## Exact-form/all-POS evaluation (2026-10-21)

The target is the exact Scrabble surface through its most familiar valid sense
across all valid parts of speech. Inventory `type` remains historical metadata,
not a restriction. `forms.csv` retains every exact LOC entry and explicitly
curated sense/POS evidence; coverage is source-bounded, not exhaustive. Human
scores and assistant estimates are rejected as lexical input columns.

```sh
python -m classificator evaluation-exact-forms \
  --vocabulary-csv pilot.csv --loc-file /path/to/LOC/words.txt \
  --contexts-csv curated-contexts.csv --campaign-dir build/d1/forms

python -m classificator evaluation-rebus \
  --vocabulary-csv pilot.csv --dex-cache /path/to/rebus/.cache/dex_definitions \
  --campaign-dir build/d1/rebus

python -m classificator evaluation-form-report \
  --reference-csv working-reference-150.csv \
  --form-contract-csv build/d1/forms/forms.csv \
  --wordfreq-csv frequencies.csv --rebus-csv build/d1/rebus/frequencies.csv \
  --campaign-dir build/d1/form-comparison
```

Contexts CSV schema: `word_id,word,context_id,pos,meaning,example,source`; all fields
required. Exact surface and ID must match the inventory. An empty context list is
allowed when only LOC evidence is available. This does not certify that all valid
uses have been enumerated. Frequency scoring pools exact-form uses across POS.

The comparison consumes versioned Romanian `wordfreq` export metadata and the
rebus export manifest/ledger. It selects only `audited_context_minimum` and
`shortlist_form_review` reference rows; `initial_opaque_form_pos` is excluded.
Reports are development-only Spearman/rank/coverage comparisons, without fitted
class thresholds. Missing values remain abstentions; undefined correlation is null.

Rebus extraction is local and sequential, excludes every target/collision page,
removes normalized exact duplicate definition bodies, and counts exact tokens
without lemma or diacritic substitution. The corpus includes lexicographic
conventions and is not a general-language familiarity sample. Source file hashes,
extractor hashes and policy are recorded. Existing outputs are refused.

For the future D1 campaign, add `--form-contract-csv build/d1/forms/forms.csv` to
`evaluation-run`. The contract is validated before HTTP and pinned in the campaign.
Without this optional evidence file, the rubric still covers all valid POS and
explicitly treats inventory type as nonrestricting. Existing campaign manifests
cannot resume under the changed instructions/implementation. Use a new campaign.
No live inference is part of preparation or comparison.

See [pilot results](research/2026-10-21-exact-form-frequency-results.md) and the
latest section of [the plan](plans/2026-10-15-d1-classifier-evaluation.md). The pilot
annotation phase is closed; the latest plan reuses existing150 labels and149
first-independent responses for explicitly internal validation. `scripts/run_exact_form_pilot.py` reproduces this local experiment:

```sh
python scripts/run_exact_form_pilot.py --pilot /path/to/pilot-2026-10-17 \
  --loc-file /path/to/LOC/words.txt --dex-cache /path/to/rebus/.cache/dex_definitions \
  --output /path/to/new-experiment-directory
```

## Full-pilot offline baselines (2026-10-23)

Install optional `evaluation` dependencies for Ridge: `pip install -e '.[evaluation]'`.
`evaluation.full_pilot_baselines.evaluate_full_pilot` compares saved legacy/AI,
constants, frequency thresholds and a fixed Ridge model using fold-only preprocessing.
Three distinct views: original-round-final150, revised-working150, independent-first149.
No model-server calls. [Results and reproduction](research/2026-10-23-full-pilot-baselines.md).


### Mandatory100% coverage (2026-10-24)

The full-pilot API now returns `views.<view>.operational` as the primary comparison.
`wordfreq_complete` and `rebus_complete` use unchanged observed-frequency thresholds
plus an explicit training-only missing-group median fallback (global training median
if necessary). Raw source-only columns remain diagnostics. Every operational method
must emit integer1–5 scores for the full view. Fold support, prediction route and route
metrics are saved. [Updated results and recommendation](research/2026-10-24-complete-coverage-baselines.md).

### Presence controls and grouped validation (2026-10-24)

`evaluate_full_pilot(..., groups_csv=path)` accepts an optional exact-reference CSV
with `word_id,word,group`. All group mates are excluded from training together;
omitting the argument preserves one-form-out validation. Presence-only baselines
use each source flag and the exact ordered pair of flags with fold-trained medians.
Reports include singleton/non-singleton slices to show how many forms actually
exercise group exclusion. [Robustness results and next implementation](research/2026-10-24-frequency-robustness.md).

### Frozen offline scorer and full shadow export (2026-10-24)

`evaluation-freeze-wordfreq` freezes the complete-source baseline from explicit
pilot vocabulary, latest working labels and a bound wordfreq export.
`evaluation-score-wordfreq` consumes that config and an exact-inventory frequency
snapshot; it never refits or connects to a database/model service. Both refuse
existing output directories. Install optional `.[frequency]` only to generate fresh
wordfreq exports; saved CSV scoring does not require wordfreq or sklearn.

Frozen configuration: `configs/wordfreq-ro-pilot-2026-10-24.json`.
[Commands, verification and full-inventory results](research/2026-10-24-offline-wordfreq-export.md).
All77,698 saved rows scored, but85.06% use fallback4 and none score5. Keep the model
as a shadow baseline; complete coverage is not evidence of full-inventory accuracy.

### Local evidence audit (2026-10-24)

[Local-source audit](research/2026-10-24-local-fallback-source-audit.md) inventories
LEX/DEX/rebus evidence for the66,088 fallback rows. Combined positive-source coverage
is18,769 rows; all49 pilot tail forms have raw local snapshots through prior reviews.
Sense-aware extraction and validation are the next step. Page tags, missing corpus
entries and inherited classifier scores are not reliable automatic level5 labels.

Local lexical fallback experiment (2026-10-25): `evaluation-local-evidence` and
`evaluation-local-fallback` provide reproducible offline extraction and grouped
validation. All150 scored; modest latest-label gain fails first-independent checks.
Keep frozen fallback4. [Results, limitations and commands](research/2026-10-25-local-lexical-fallback.md).


## Bounded FineWeb2 experiment (2026-10-27)

Install the evaluation extra (`pyarrow==21.0.0` included). Use a pinned HF train-file
listing for revision `af9c13333eb981300149d5ca60a8e9d659b276b9`, configuration
`ron_Latn`, with path/size entries. The existing experiment stores that verified
listing in `build/d1/fineweb-2026-10-26/inputs/shards.json`.

```sh
classificator evaluation-fineweb \
  --vocabulary-csv build/rarity/step1_words.csv \
  --shards-json build/d1/fineweb-2026-10-26/inputs/shards.json \
  --campaign-dir build/d1/fineweb-2026-10-26/source \
  --max-documents 100000 --max-transfer-bytes 1073741824
```

The same command resumes with the same inputs/code/limits. Never delete a budget
ledger to restart an interrupted run. Failed/uncertain transfer and document
reservations remain spent. Hard caps cannot be raised; the default1GiB budget
includes a conservative40MiB allowance for installing the optional parser.
5GiB free-disk floor pauses safely. Complete runs replay without network. Source
files are read via bounded HTTP ranges; no full shard or corpus cache is written.

Outputs: full inventory `frequencies.csv` (2020–2024 crawl dates), separate
`older-frequencies.csv`, sampled-group plan/ledger, bounded local concordances,
validated checkpoint and manifest. Missing counts stay explicit, never imply5.
Frequencies are descriptive of the selected sample; dates are crawl dates, not
publication dates. Multiple hosts can repeat a passage and are not independent
attestations. Check source quality before interpreting calibration.

```sh
classificator evaluation-fineweb-fallback \
  --reference-csv PATH_TO_WORKING_REFERENCE_150 \
  --features-csv PATH_TO_EXISTING_FREQUENCY_FEATURES \
  --evidence-dir build/d1/fineweb-2026-10-26/source \
  --first-independent-csv PATH_TO_FIRST_INDEPENDENT_149 \
  --groups-csv PATH_TO_FROZEN_GROUPS \
  --campaign-dir build/d1/fineweb-2026-10-26/comparison
```

Evaluation is CSV-only: complete predictions, shared fold-fitted wordfreq path,
source-supported fallback fitted outside each held-out group, unknown→4. No D1,
database access, production scorer changes or automatic upload. Dataset attribution
and original content rights remain applicable; concordance snippets stay local.

Completed run: [FineWeb2 bounded results](research/2026-10-27-fineweb-bounded-experiment.md).
Source coverage improved; the declared training gate did not pass. Frozen wordfreq+4 retained.


## CoRoLa noncommercial frequency diagnostic — 2026-10-28

Completed experiment and interpretation:
[CoRoLa report](research/2026-10-28-corola-experiment.md).
Public offline functions:
`evaluation.corola.export_corola_frequencies(vocabulary_csv, source_tsv, source_record_json, output_dir)`
and `evaluation.corola_fallback.evaluate_corola_fallback(reference_csv, frequency_features_csv, evidence_dir, first_independent_csv, groups_csv, output_dir)`.
Use `pathlib.Path` arguments. Outputs publish atomically and refuse existing targets.

Workspace-local `build/d1/corola-2026-10-28/` contains the frozen protocol, original
source, receipts, executable export/comparison scripts and independent verifier.
Do not rerun acquisition into existing files. Offline reproduction uses retained
source plus new output directories; no model/database setup is required. Source
and derived CSVs are not repository resources for commercial/distributed use.
Current recommendation remains frozen wordfreq+4; more coverage did not reduce
severe errors in this experiment.


## Local lexical variants — 2026-10-28

[Extraction report](research/2026-10-28-lexical-variant-extraction.md): existing
`export_local_evidence` now emits a source-scoped `variants.csv` ledger and additive
POS/restriction/provenance fields in `senses.csv`. `evidence.csv` stays compatible.
`explicit-variants-v1` is recorded in the manifest. Supported variant relations and
recovered exact senses are separate; unresolved records do not become aligned evidence.

Campaign: `build/d1/lexical-variants-2026-10-28/`. The 169-row source ledger includes
already-local atu.html explicitly bound to ata; this does not bypass witness checks.
Authoritative output: `evidence-reviewed/`; independent verification:
`verification-reviewed.json`. Earlier output directories are retained development
artifacts. Reproduce with the campaign's `run.py NEW_OUTPUT_NAME`, then
`compare_evidence.py NEW_OUTPUT_NAME` and `verify.py OUTPUT_PATH`, using the project
Python environment for export. Existing outputs are never overwritten. Scores and
ratings remain frozen; no model, database or network needed.

## Sequential chat judges (Qwen now; compatible GPT endpoint later)

Use `collect_chat_csv` for a fixed, blinded prompt over the existing evidence CSV;
use `compare_judge_csv` only after inference to join human references and baseline.
Both public boundaries are CSV-first, tested independently and provider-neutral.
The chat collector reuses campaign receipts/checkpoints; it does not manage local
model loading or databases. For the measured Qwen pilot, use the saved local runner
under `build/d1/qwen-judge-2026-10-30/run.py`: it checks RAM and exact live model
configuration before each sequential request. The generic CLI below delegates
transport only; local lifecycle/RAM checks remain the caller's responsibility.

```sh
PYTHONPATH=src python scripts/run_chat_judge.py \
  --vocabulary /path/to/vocabulary.csv \
  --evidence /path/to/evidence.csv \
  --output-dir /path/to/new-campaign \
  --model EXACT_SERVED_MODEL_ID \
  --endpoint http://127.0.0.1:1234/v1/chat/completions \
  --options-json /path/to/provider-options.json \
  --runtime-json /path/to/runtime-provenance.json

PYTHONPATH=src python scripts/compare_chat_judge.py \
  --predictions /path/to/new-campaign/predictions.csv \
  --reference /path/to/reference.csv \
  --baseline /path/to/baseline-oof.csv \
  --evidence /path/to/evidence.csv \
  --folds /path/to/folds.csv \
  --output-dir /path/to/new-comparison --review-budget 8
```

For a later compatible hosted model, keep the lexical CSV and rubric; change the
endpoint, pinned model ID and explicit provider options. `--api-key-env ENV_NAME`
reads credentials into the HTTP session only. The provider's concrete model/parameter
support must be probed separately; this is not a claim that GPT has been run or that
Chat Completions and Responses are interchangeable. Served model identity must match
the requested ID; alias behavior requires separate verification.

Labels, human estimates, baseline scores and other judges' predictions have no field
in the inference evidence schema. No examples or target labels enter the fixed prompt.
No regex repair or silent retries: invalid responses are persisted as native failures;
the offline comparison uses the frozen baseline as an explicit fallback. All input
IDs must still appear. Missing definitions are explicit, never an automatic level5.

Chat judgments have no invented probabilities or confidence. `predictions.csv` is
the research artifact; legacy `run.csv` intentionally has no scored rows because its
confidence requirement is unmet. Nothing is uploaded from this pilot.

Changed model/options/evidence/code reject resume. Use a fresh campaign; preserve
source snapshots and raw receipts for old runs. Complete existing records are reused
without another model call. Comparison reports >=2 errors, error2/3/4, excess loss,
4/5 confusion, evidence/reference strata and matched-budget diagnostic recall/precision.

To include all previously curated exact-form contexts in either provider's evidence:

```sh
PYTHONPATH=src python scripts/merge_judge_evidence.py \
  --evidence /path/to/evidence.csv \
  --form-contract-dir /path/to/verified-form-export \
  --projection /path/to/audited-projection.csv \
  --output-dir /path/to/new-merged-export
```

This preserves existing senses and adds every curated POS/meaning, retaining detailed
POS/restriction text. It verifies the source export hashes and complete identities.
Provenance is a separate CSV; illustrative examples are not corpus attestations and
are excluded from model state. Curated pilot contexts may be label-exposed: reuse
is transparent but does not establish independent validation. Existing outputs are
never overwritten. [Measured Qwen pilot](research/2026-10-30-qwen-judge-pilot.md).

When curated meaning fields contain reviewer prose, supply an explicit audited
projection. Columns: word_id,word,context_id,pos,original_meaning,definition. It must
cover every original context exactly once and preserve identity, POS and original
text. Only definition replaces model-bound prose; the original/projected pair stays
in provenance. There is no automatic blacklist or lexical rewriting. The argument
is optional for already lexical-only input, but **required to reproduce this pilot's
corrected arm**. Its218-row projection changes exactly five review clauses;213
meanings remain identical. The separate interrupted30-record arm is not a result.

## GPT through Codex — 2026-10-31

When only an existing Codex login is available, the public boundary
`evaluation.codex_judge.collect_codex_csv(vocabulary_csv, evidence_csv, output_dir,
executor=..., model=..., runtime=...)` consumes the same lexical CSV as the HTTP
collector. The executor receives a label-free request with the fixed rubric, JSON
schema, configured model/effort and one exact form. It returns the native process
receipt `{returncode, stdout, stderr}`. No simulated HTTP response or served-model
identity is added.

The measured local campaign is `build/d1/gpt-judge-2026-10-31/`. `prepare.py` freezes
inputs; `preflight/final_check.py` verifies a synthetic transport probe and captures
assembled context; `run.py` starts one fresh ephemeral Codex process per form with
minimal environment and a separate empty cwd. Its native process receipts precede
campaign parsing/checkpointing. Re-running the unchanged runner resumes persisted
records without asking the model again. A model/config/source change requires a new
campaign. Preserve raw files; do not edit manifests to force compatibility.

Run the saved runner using the project Python environment. Its `protocol.json` pins
the source checkout/binary/catalog paths; inspect these instead of assuming any clone
or newer installed CLI is equivalent. API credentials are not extracted or copied.
The runner requires the existing CLI authentication and permission to initialize its
local runtime; child model commands retain the declared read-only mode.

Codex has a generic managed instruction/tool wrapper, so this is not an identical
provider prompt to Qwen. Tools are not claimed unavailable: every accepted run must
have no observed tool events. Unknown/tool events, configuration warnings or stderr
save a quarantine receipt and stop collection; a quarantined directory cannot resume.
Review that failure and start a separately documented campaign if needed. Invalid
final JSON/levels/identities produce explicit native failures; the offline comparator
uses the original frozen baseline fallback, never a fabricated model score.

After all150 records: `evaluate.py`, `replay.py`, then the separate `audit.py`.
Comparison uses the existing `compare_judge_csv`; pairwise analysis additionally joins
corrected Qwen scores by exact ID/spelling and identical human reference. These files
are never supplied to the model. GPT configured identity and reasoning effort are
reported explicitly; a provider-served model ID is not exposed by this CLI's event
stream. [Pilot report](research/2026-10-31-gpt-judge-pilot.md).
