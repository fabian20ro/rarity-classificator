# Frozen offline wordfreq scorer and full inventory export — 2026-10-24

Implemented and exported77,698/77,698 inventory records, preserving75,147 exact
normalized forms and all POS rows. All scores are1–5. Two independent scoring runs
produce byte-identical CSVs. No database connection/write, HTTP request or D1 load.

**Operationally complete; unsuitable for production promotion on this evidence.**
85.06% of inventory rows use the same fallback4; no row receives5. The selected
pilot's32.67% fallback share substantially understates the inventory's missingness.
This export establishes coverage and reproducibility, not full-inventory accuracy.

## Frozen configuration

File: `configs/wordfreq-ro-pilot-2026-10-24.json`.
Model version: `8f3061e2332cf9d6844ff4ea9dabd4fd23111c04b713a8a0cde886a23c82e0cc`.
Fit on the latest150 working labels:37 clarified +113 original opaque form/POS
ratings. Exact form through its most familiar valid sense across all valid POS.
Fresh pilot frequencies match all150 values from the prior frozen experiment.

- Corpus: Romanian wordfreq3.1.1, best list; exact normalized dictionary lookup.
- Threshold fitting: unchanged ordinal-MAE monotone log-grid policy on101 observed
  training forms. Fit is deployment preparation, not a new validation score.
- Thresholds: `3.9810717055349695e-05`, `2.5118864315095823e-06`, `1e-06`,
  `7.943282347242822e-07`. Equality belongs to the more familiar class.
- Missing source: lower median of49 missing-frequency pilot labels =4.
- Global emergency median =2, used only when no trained missing group/model is
  available under the documented routes; not exercised in this inventory export.

The content-hashed config pins source language, package/version, lookup policy,
corpus digest, training input hashes/IDs, threshold support and fallback support.
It is copied unchanged into each export. Changing config content invalidates its
identity. Runtime requires neither original labels nor a fitted-model service.

## Full inventory result

Input: existing `build/rarity/step1_words.csv`, verified against the original pilot
source hash. This is the complete saved inventory snapshot, not a fresh DB query.
Inventory membership was previously checked against local LOC5.0; no newer-list
certification is claimed. Duplicate spelling/POS rows are retained.

| Route | Inventory rows | Share |
|---|---:|---:|
| Observed frequency thresholds |11,610|14.94%|
| Missing-frequency fallback4 |66,088|85.06%|
| Unclassified |0|0%|

By unique form:10,921 directly observed,64,226 fallback,75,147 total.
2,476 normalized forms occur in multiple inventory rows; every such form has an
identical frequency, route and score across its POS entries. Different literal
spellings such as `tara` and `țară` are never merged for scoring.

| Rarity level | Rows |
|---|---:|
|1|972|
|2|6,283|
|3|4,355|
|4|66,088|
|5|0|

Minimum positive inventory frequency is approximately1.023293e-6. It is above the
fitted L3/L4 and L4/L5 boundaries, so every directly observed form scores1–3.
All missing forms score4. This is the frozen model's result, not a post-hoc
histogram adjustment; no artificial5 assignments were added.

| Inventory POS | Total | Fallback |
|---|---:|---:|
|N|50,707|43,837|
|A|19,155|15,796|
|V|7,836|6,455|

| Form length | Total | Fallback |
|---|---:|---:|
|1–3|763|250|
|4–7|30,800|24,275|
|8+|46,135|41,563|

## Reusable interface and reproduction

Public CSV functions:
`freeze_wordfreq_model(pilot_csv, reference_csv, frequency_csv, output_dir)` and
`score_wordfreq_inventory(inventory_csv, frequency_csv, model_json, output_dir)`.
The second never trains. CLI commands expose these same boundaries.

Install `pip install -e '.[frequency]'` to generate fresh wordfreq evidence;
scoring pre-exported evidence needs only the normal project installation.
Existing output files/directories are refused. Use new paths for each run.

```sh
classificator evaluation-wordfreq \
  --vocabulary-csv /path/to/pilot.csv --output-csv /path/to/pilot-frequencies.csv
classificator evaluation-freeze-wordfreq \
  --vocabulary-csv /path/to/pilot.csv --reference-csv /path/to/working-reference.csv \
  --wordfreq-csv /path/to/pilot-frequencies.csv --campaign-dir /path/to/new-model
classificator evaluation-wordfreq \
  --vocabulary-csv /path/to/full-inventory.csv --output-csv /path/to/full-frequencies.csv
classificator evaluation-score-wordfreq \
  --vocabulary-csv /path/to/full-inventory.csv --wordfreq-csv /path/to/full-frequencies.csv \
  --model-json configs/wordfreq-ro-pilot-2026-10-24.json --campaign-dir /path/to/new-export
```

Outputs: `scores.csv`, copied `model.json`, `summary.json`, `manifest.json`.
CSV fields: `word_id,word,type,rarity_level,frequency,route,model_version`.
No invented confidence, probabilities, lemma expansion or missing classifications.

Frequency CSV metadata must bind the exact supplied vocabulary hash/count and the
export hash/count. Full normalized corpus digest, package version and lookup policy
must match the frozen model. Corruption, wrong language/version, incompatible
inventory, malformed values and modified config fail before publishing output;
they do not silently become fallback predictions.

## Verification

TDD red/green: missing corpus-policy provenance, missing freeze/score API, missing
CLI commands. Regression tests verify threshold equality, distinct diacritics,
repeated POS rows, observed/missing-only training edge cases, corrupted/mismatched
inputs, output refusal and byte-identical runtime replay without training files.
CLI tests block HTTP and DB connections; the actual77,698-row export and replay
also ran with those boundaries blocked. Runtime scorer uses no model transport.

Ruff +811 tests/137 subtests pass. Architect review: no actionable defects.
Independent script verified all77,698 identities/scores/routes, same-form
consistency, training support/medians, source/config/output hashes, summaries by
POS/length, and exact replay. No DB access or D1 requests.

Private artifacts: `build/d1/offline-wordfreq-2026-10-24/` contains fresh pilot/full
frequency snapshots and metadata, `frozen/`, `export/`, `replay/`, reproducible
`run.py`, independent `verify.py`, source-validation and verification JSON.
Primary deliverable: `export/scores.csv`.

## Updated recommendation and remaining work

Keep this frozen version as a reproducible **shadow baseline**. The previously
measured pilot CV MAE0.520 remains a pilot result; it must not be presented as
accuracy on the77,698 exported rows. Full-inventory missingness is much higher.

Do not promote this model into production: it collapses most forms to4 and cannot
separate rare4 from very obscure5 in this inventory. Do not manufacture a desired
histogram or tune thresholds on the same pilot to hide that limitation.

Next priority: audit additional lexical/frequency evidence for the fallback forms,
starting with existing local sources, then evaluate any candidate on the existing
human labels with the same complete-coverage protocol before exporting a new model.
The scorer/export implementation is complete; broader rare-form discrimination and
external generalization evidence remain. No new annotations or D1 load are required
for a read-only evidence audit. Production integration/upload remain outside this
iteration and retain all existing semantic gates if separately authorized later.
