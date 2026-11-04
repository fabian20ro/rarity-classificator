# Complete-coverage pilot baselines — 2026-10-24

> Follow-up completed: [presence controls and grouped validation](2026-10-24-frequency-robustness.md). Original results below preserved.

Operational requirement: a score for every form. Incomplete methods cannot enter
the main comparison; conditional MAE on observed words is diagnostic only.
All150 latest working labels retained; no new annotation, model inference or D1 load.

## Protocol fixed before this run

Same frozen exact-form features and labels as the previous full-pilot experiment.
Leave one form out; fit on149 other labels. Separate original-round-final150,
revised-working150 and first-independent149 views;449 sequential folds total.
Latest labels still mix37 clarified forms and113 initial opaque form/POS ratings.
The first-independent subset lacks `ata`; no synthetic150th label added there.

For each source independently:

1. Observed frequency with a fitted model: unchanged monotone MAE thresholds.
2. Missing frequency: lower median of training labels whose frequency is missing
   from that same source. If that subgroup is empty, use the global training median.
3. Observed frequency but no observed training data/model: global training median.

Zero and empty frequency mean missing. The evaluated form's label is excluded from
thresholds, fallback groups and global medians. No assumption that missing means5.
Save fallback support IDs, score and selected route in each fold/CSV. Require integer
scores1–5 for every operational method before producing a successful report.
The prior abstaining outputs remain unchanged as explicit diagnostics.

This fallback was chosen after inspecting the pilot, then fixed before this run.
Results are exploratory internal validation, not independent generalization evidence.
Ridge alpha1, training-only imputation/scaling and historical predictions unchanged.

## Main comparison: latest working labels, all150

MAE = average absolute difference from human score, lower is better.
Severe error = difference of at least2 levels. Every method below covers150/150.

| Method | MAE | Exact | Within1 | Severe errors | Rare severe underestimates /43 |
|---|---:|---:|---:|---:|---:|
| Historical assistant |0.473|96|141|9|1|
| Wordfreq + fallback |0.520|86|139|11|5|
| Ridge (both sources + missingness) |0.533|80|141|9|4|
| Rebus + fallback |0.680|64|134|16|6|
| Training median |1.227|31|107|43|43|
| Training majority |1.547|51|82|68|43|
| Legacy snapshot |1.740|28|74|76|8|

Wordfreq's former0.455 on101 is not its full-system MAE: with all49 missing forms
included, MAE is0.520. It has78 absolute-error points versus Ridge80: a small
2-point advantage, with2 more severe errors. No strong winner established.
Historical assistant estimates are saved predictions, not a newly executed model;
some later human labels followed estimate exposure. No claim that any baseline
outperforms that reference.

## Fallback contribution

| Source | Frequency route | Fallback route | Fallback MAE | Fallback exact |
|---|---:|---:|---:|---:|
| Wordfreq |101|49|0.653|19/49|
| Rebus |110|40|0.775|10/40|

Every missing-group fallback happens to predict4 in the latest150 folds;4 is learned,
not hard-coded. Neither source needs the global emergency fallback on this pilot.
Both edge cases requiring that route are covered by regression tests.

Wordfreq: observed errors46 + fallback errors32 =78;78/150 =0.520.
Rebus: observed errors71 + fallback errors31 =102;102/150 =0.680.
38/49 wordfreq-missing forms and28/40 rebus-missing forms have human4/5. That selected
pilot distribution helps the fallback; absence from a source does not prove rarity.

Wordfreq's fallback severe errors: `acrit` human2→4 and `zar` human2→4.
Its5 severe rare underestimates all come from observed frequencies, not fallback:
`ata`5→3, `carter`5→2, `dorian`5→2, `pag`4→2, `tara`4→1.
Coverage is fixed; ambiguous/familiarity-misaligned frequency evidence remains.

## Sensitivity and rubric strata

All methods cover the full denominator of each view.

| Label view | Count | Assistant MAE | Wordfreq + fallback | Ridge | Rebus + fallback |
|---|---:|---:|---:|---:|---:|
| Original round final |150|0.273|0.707|0.693|0.867|
| Latest working |150|0.473|0.520|0.533|0.680|
| First independent |149|0.557|0.624|0.671|0.805|

First-independent149: wordfreq74 exact,13 severe errors; Ridge61 exact,8 severe
errors. Better average error does not imply fewer large mistakes.
Within the latest37 clarified forms, Ridge MAE0.514 versus wordfreq0.568 and
rebus0.622. Within113 opaque forms, wordfreq0.504 versus Ridge0.540 and rebus0.699.
These are slices of the150-fit LOO experiment, not the earlier37-only CV fits.

## Recommendation and remaining work

Use **wordfreq + explicit fallback as the simple complete offline baseline**;
retain Ridge as a challenger because it makes fewer severe errors and performs
better on the37 clarified forms. Rebus alone, even completed, is weaker here.
Do not promote a new production default based on a2-point aggregate advantage.
The old own-coverage ranking is superseded by this complete comparison.

Next: missingness-only control and family-grouped validation using existing labels.
These test whether gains survive beyond the selected pilot's rarity/missingness
pattern and closely related forms. Preserve latest37/113 provenance strata and
first-independent149 sensitivity. No new annotation required, no parameter search
against these reported held-out predictions, no D1 load.

Remaining: those robustness checks; external generalization evidence; any future
D1 run only under separate authorization and sufficient memory. This change affects
offline evaluation only; production scoring and upload gates remain unchanged.

## Reproduction and verification

Implementation: `evaluation.full_pilot_baselines.evaluate_full_pilot`.
Primary JSON section: `views.<view>.operational`; source-only diagnostics remain in
`all`, `on_source_coverage` and `common_frequency_coverage`. Route metrics are in
`completion_routes`. CSV columns `wordfreq_complete_level` / `rebus_complete_level`
and corresponding `_basis` contain operational source predictions.

Private artifacts: `build/d1/complete-coverage-baselines-2026-10-24/`:
`run.py`, `verify.py`, three predictions CSVs,449 fold files, `protocol.json`,
`summary.json`, `manifest.json`, `source-validation.json`, `verification.json`.
To rerun, use the evaluation extra and change the output path in a copy of `run.py`
to a new directory. Existing outputs are refused. Frozen inputs and earlier results
are preserved. Primary source hashes and original human/prediction provenance checked.

TDD: missing completion columns failed first; then missing route metrics failed;
both passed after implementation. Regression coverage includes all-missing data,
zero/blank equivalence, empty missing subgroup, unavailable threshold model,
held-out-label independence in all3 views, direct prediction preservation and
full-denominator arithmetic. Ruff +800 tests/115 subtests pass.
Independent artifact audit checked449 train exclusions/fallback supports/medians,
all operational scores and MAE, input/output/code hashes, and unchanged prior
prediction columns. D1/LM requests:0.
