# Evaluate D1 on Romanian Scrabble words

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
  --campaign-dir build/d1/word-only \
  --model d1-3b \
  --model-file /Users/fabian/.lmstudio/models/LiquidAI/d1-3B-GGUF/d1-3B-Q8_0.gguf \
  --runtime-version 'llama.cpp-2.58.0-lmstudio-0.4.26+4'
```

Use the actual installed runtime version and matching model file; values above describe the inspected setup. A second campaign with `--evidence-csv build/d1/dataset/evidence.csv` evaluates evidence assistance. For a definitions-only ablation, supply a derived CSV containing `word_id,definition,definition_status`; for frequency-assisted evaluation include `frequency,frequency_present`. Unknown evidence columns, including human labels, are rejected. Inputs and implementation changes require a new campaign directory.

Default English familiarity rubric is versioned in `scoring/d1.py`; no offensive-word rarity penalty. Comparing a Romanian rubric remains a development experiment. Full probabilities are saved; argmax selects the integer class, lower label wins an exact tie. `--min-probability` optionally abstains below a chosen maximum-class-probability threshold; default0 retains all valid predictions for unbiased initial evaluation. This threshold is not an estimated accuracy guarantee.

Artifacts: predictions.csv, run.csv, failures.csv, review.csv, summary.json, immutable manifest.json, records/ID.json. Records include raw request/response. Successful D1 predictions with confidence populate the compatible run.csv; unresolved/failed outcomes remain in diagnostic CSVs. Do not upload experimental scores without evaluating and satisfying existing semantic gates. `summary.json` includes coverage counts, cumulative latest-attempt scorer time and latency quantiles; it does not measure peak RAM or include discarded retry attempts.

Repeat the command to resume without repeating completed IDs. Add `--retry-failed` to explicitly retry failed IDs once each; it does not retry abstentions. HTTP errors are recorded without implicit retry loops. Failed/pending campaigns return exit code1. Separate campaign directories prevent mixing models/inputs; only one process may write a given campaign. Multiple independently launched processes are outside the single-run sequential guarantee.

The standard Step2 entrypoint also accepts D1:

```sh
python -m classificator step2-score --backend d1 --run d1-pilot \
  --base-csv build/d1/dataset/vocabulary.csv --output-csv build/d1/scored.csv \
  --model d1-3b --model-file /path/to/matching-model.gguf --runtime-version ACTUAL_VERSION
```

Sidecars live in `scored.csv.campaign/`. This path rejects force, skipped preflight, alternate endpoint, input overrides and limits: prepare the intended frozen inventory instead. For explicit failure retry, use `evaluation-run` against the same sidecar directory and matching `--run d1-pilot` identity, or a new campaign. No upload occurs. `--dry-run` never contacts the model. Production chat scoring remains the default.

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
  --predictions-csv build/d1/word-only/predictions.csv \
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
