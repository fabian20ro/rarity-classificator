# Frequency robustness checks — 2026-10-24

Both requested checks completed with existing labels and100% operational coverage.
Wordfreq + fallback remains the simplest experimental baseline. Numerical wordfreq
adds useful information beyond presence alone on this pilot; family exclusion
provides limited additional evidence because only16 forms belong to paired groups.
No new human ratings, model-server requests, D1 loading or production changes.

## Frozen protocol

Reuse the same exact-form features, labels, threshold policy, fallback and Ridge
alpha1. Three views: original-round-final150, revised-working150, first-independent149.
The latest150 still mix37 clarified and113 original opaque form/POS ratings.
Run leave-one-form-out (LOO) and leave-one-group-out with identical methods.

Three new presence-only controls:

- `wordfreq_presence`: lower training median for the same wordfreq observed/missing flag.
- `rebus_presence`: analogous control for rebus.
- `presence_pattern`: lower training median for the exact pair of source flags;
  `(wordfreq present, rebus absent)` differs from the reverse.

An unseen flag/pattern uses the global training median. Neither numerical frequency
magnitudes nor held-out labels enter these controls. In grouped mode, every member
of the held-out group is excluded before thresholds, medians, imputation, scaling
and regression. Fixed historical predictions are comparison references, not refits.
All operational scores must be integers1–5 for every form. No hyperparameter tuning.

Group map fixed in `groups.csv` before this run, based on lexical evidence, without
using scores as grouping inputs. Previous results/labels were already known: this
is exploratory sensitivity, not a new independent test. The six original groups
are preserved: ata/ață, masa/masă, roman/român, sex/sexual, tanc/țanc, tara/țară.
Five are game-key collisions rather than necessarily morphological relatives.

Added acoperire/descoperi as a cover/discover root link, inferred from the local
acoperire definition and the [etymological dictionary](https://www.diacronia.ro/en/indexing/details/B132/pdf/04).
Added euro/european conservatively as Europe-related lexical material, using the
local euro definition and [european dictionary entry](https://dexonline.ro/definitie/european).
This does not claim direct Romanian derivation between euro and european.

No iț/ițar merge: the local exact iț entry concerns a child, while the loom ițar
entry derives from iță/ițe; shared spelling alone does not establish the link.
No numărat/numitor merge without verified derivation. This explicit map is a
limited family/collision stress test, not an exhaustive etymological partition.

Latest150:142 groups,8 pairs/16 forms and134 singletons. First-independent149:
142 groups,7 pairs/14 forms and135 singletons (`ata` has no first-independent label).
Grouped run:142 distinct training exclusions per view,426 total;449 individual
prediction records. LOO adds449 records, for898 checked predictions. Metrics are
per form, not averages giving each group equal weight.

## Latest150: every method scores150/150

MAE lower is better; severe means an error of at least2 levels.

| Method | LOO MAE | Grouped MAE | Grouped exact | Grouped severe |
|---|---:|---:|---:|---:|
| Wordfreq + fallback |0.520|0.520|86|11|
| Ridge |0.533|0.533|80|9|
| Joint presence pattern |0.587|0.587|84|19|
| Rebus + fallback |0.680|0.693|64|16|
| Wordfreq presence only |0.740|0.767|66|23|
| Rebus presence only |0.867|0.867|40|16|

Wordfreq numerical values reduce grouped total absolute error from115 to78 versus
its presence-only control:37 points, MAE gain0.247. Rebus numerical values reduce
130 to104:26 points, MAE gain0.173. Both contain information beyond binary coverage.
Using both source-presence flags is already strong:88 total error points, versus
wordfreq78 and Ridge80. Wordfreq's advantage over this joint control is10 error
points; Ridge's is8. Binary missingness accounts for a substantial predictive
signal in this selected pilot, though these are model comparisons, not a causal
variance decomposition.

The joint control learns latest-pilot medians: both observed→1 (90 forms),
wordfreq-only→3 (11), rebus-only→4 (20), neither→5 (29). These are learned patterns,
not dictionary facts or rules safe to apply to an arbitrary new corpus.

Among the43 latest human4/5 forms, severe underestimates: wordfreq5, Ridge4,
joint-pattern4, rebus6. All43 receive scores. The historical assistant and legacy
references remain unchanged: MAE0.473 and1.740 respectively.

## What family exclusion actually changes

Only16 latest forms have a different training set from LOO. Their grouped MAE:
wordfreq0.563, Ridge0.500, joint-pattern0.563, rebus0.750. On this slice rebus
LOO MAE was0.625; `euro` and `european` move3→4 against human1 when excluded together.
The wordfreq-presence control changes1→2 for euro/european and masa/masă.
Wordfreq-complete, Ridge and joint-pattern have unchanged latest integer predictions.

The134 singleton prediction rows are unchanged by construction. Therefore stable
aggregate MAE is not strong evidence of robustness across unseen lexical families.

## Sensitivity to label history and clarified forms

Every method covers each full denominator.

| View | Count | Grouped wordfreq | Grouped Ridge | Joint pattern | Grouped rebus |
|---|---:|---:|---:|---:|---:|
| Original round final |150|0.707|0.693|0.680|0.880|
| Latest working |150|0.520|0.533|0.587|0.693|
| First independent |149|0.624|0.664|0.664|0.805|

First-independent149: wordfreq74 exact/13 severe errors, Ridge62/8,
joint-pattern58/6. Better MAE still trades off against large mistakes.
The joint control ties Ridge's grouped MAE here and beats it on severe-error count;
Ridge complexity does not have a consistent advantage across label views.

Latest37 clarified slice: Ridge0.514, wordfreq0.568, joint-pattern0.622,
rebus0.622. This remains a slice of fitting on the full available reference, not
a separate37-label fit. Historical assistant alignment and original-round-final
scores may be affected by estimate exposure; immutable first labels are separate.

## Updated recommendation

Keep **wordfreq + fallback** as the simple complete offline baseline; keep Ridge
as a comparator for severe-error and clarified-form behavior. Do not add a more
complex hybrid or tune parameters against this pilot. Rebus alone remains weaker.

The next implementation step is to freeze a versioned wordfreq threshold/fallback
configuration fitted to the existing reference and expose deterministic offline
CSV scoring. Record for each form its frequency, direct/fallback route and model
version. Apply it to the full inventory as a shadow export, without updating the
production database. Verify coverage, reproducibility, corpus identity and fallback
rate across inventory strata. Unlabelled full-inventory output tests operability
and distribution shift, not accuracy; fitting all150 is deployment preparation,
not an additional validation score.

Remaining: that reusable scorer/configuration/export; operational validation on
full inventory; external generalization evidence; future sequential D1 comparison
only with explicit authorization and sufficient memory. No new human annotation
is required for the proposed implementation step. Production upload gates remain
mandatory for any separately authorized deployment.

## Artifacts and checks

`build/d1/robustness-baselines-2026-10-24/`: frozen `design.json`, `groups.csv`,
`run.py`, `verify.py`, source-validation and verification JSON. Each `loo/` and
`grouped/` directory contains three prediction CSVs, per-form fold JSON, protocol,
summary and pinned manifests. Existing prior outputs remain unchanged.

Public API: `evaluate_full_pilot(..., groups_csv=path)`; omit the keyword for LOO.
Groups schema: exactly `word_id,word,group`, matching the entire reference; nonempty
groups, at least two groups in every label view. Input violations fail before output.
New summary slices: `non_singleton`, `singleton`, `grouping`; operational ranking
continues in `views.<view>.operational`. Existing output directories are refused.

TDD: missing presence-control column failed, implemented to green; missing grouped
API failed, implemented to green. Regressions cover complete coverage, group-wide
label exclusion in all views, singleton equivalence, magnitude-invariant presence
controls, ordered source bits, unseen-pattern fallback and invalid group maps.
Ruff +804 tests/122 subtests pass. Independent script and planner review checked
all898 predictions, group/presence support, fallback medians, Ridge preprocessing,
complete-score metrics and hashes. Old LOO prediction columns remain unchanged.
D1/LLM calls:0.
