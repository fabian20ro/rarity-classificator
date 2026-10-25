# Local lexical evidence and fallback experiment — 2026-10-25

Implemented and evaluated one predeclared candidate. **Keep the frozen wordfreq +
fallback4 baseline.** The new candidate slightly improves latest mixed labels,
but increases severe errors, worsens clarified labels and fails first-independent
sensitivity. No production promotion, frozen model/export change, DB access or D1.

## Implemented boundaries

- `export_local_evidence`: inventory + original LOC + explicit hash-bound local
  source index + exact cross-entry mention counts → `senses.csv`, `evidence.csv`,
  `source-files.csv`, manifest. Strict identities/schema; atomic output; no overwrite.
- `evaluate_local_fallback`: those artifacts + frequencies, labels and frozen groups
  → per-view predictions, per-fold training IDs/tree support, summaries and manifest.
- CLI: `evaluation-local-evidence`, `evaluation-local-fallback`. Dispatch stays in
  offline evaluation before database configuration. No production Step2 changes.

The two CSV boundaries were explicitly confirmed by the user before tests.

## Extraction and scope

150 forms;168 hash-verified local source files covering134 forms. Structured DEX
headings bind literal spelling/explicit inflected alternatives to POS. Multiple
heading blocks preserve all stated POS. Meaning IDs, definitions, source paths/hashes,
parent meanings and scoped tags remain inspectable. Tags inherit down a meaning
branch; navigation, etymology, examples and unscoped raw-definition abbreviations
are excluded. No lemma transfer or diacritic folding. LOC F/M/MF map to noun family,
VT to verb; unknown codes remain unresolved rather than being guessed.

Aligned source-bounded evidence:123/150, including42/49 missing-wordfreq forms.
The remaining7 tail forms retain4: antereu, iț, micșurat, păpușire, preajm, sezisa,
văietare. For example, micșorat does not establish the meaning of exact micșurat.
All150 retain an evidence row and prediction. Known-POS coverage does not prove
that every valid sense or inflected use has been found; this remains a conservative
structured-source gate, not automatic linguistic verification.

Cross-entry counts reuse the audited frozen rebus corpus with its original target
page exclusions and outside-own-page correction. No source filenames, review-round
flags, snapshot counts, assistant contexts/estimates or inherited rarity scores
enter the feature vector. Selection of locally saved pages still limits external
validity; feature exclusion cannot make a selected pilot independent.

## Fixed protocol

Predeclared before this run: `build/d1/local-fallback-2026-10-25/protocol-proposed.json`.
One tree: `criterion=absolute_error`, depth2, minimum leaf5, seed0. Predictions use
the lower median of training labels in the selected leaf; fewer than10 eligible
training forms or unresolved target evidence →4. No parameter search or reranking
of alternative trees after results.

Three features: log1p(outside-page definition count), all aligned senses restricted
by obsolete/regional/rare tags, all aligned senses specialist-tagged. Any unmarked
aligned sense prevents the corresponding all-senses flag. These flags are candidate
signals, never direct instructions to assign5. The tree fits only eligible training
forms without wordfreq, allowing levels1–5 rather than forcing a binary4/5 decision.

All wordfreq thresholds are fitted inside each held-out group, identically for
baseline and candidate. The frozen all150-trained deployment configuration is
never used to evaluate its own training labels. Group map:142 groups for150 forms;
only16 forms belong to8 non-singleton groups. First-independent149 excludes the
unavailable first rating and refits every learned component.

## Results: complete coverage

MAE lower is better; severe means absolute error≥2. All methods cover100%.

| Label view / slice | n | Baseline MAE | Candidate MAE | Exact baseline→candidate | Severe baseline→candidate |
|---|---:|---:|---:|---:|---:|
| Latest mixed |150|0.520|0.500|86→90|11→12|
| Latest, no wordfreq |49|0.653|0.592|19→23|2→3|
| Latest, clarified |37|0.568|0.595|—|4→4|
| Latest, opaque original |113|0.504|0.469|—|7→8|
| Original round final |150|0.707|0.713|72→75|18→22|
| First independent |149|0.624|0.671|74→69|13→15|
| First independent, no wordfreq |49|0.653|0.796|19→14|1→3|

Original-round-final labels include revisions; they are not blind first responses.
The37/113 stratification refers to provenance of the latest reference; first-label
sensitivity has36/113 because one first rating is unavailable.

## Separate4 versus5 results

Latest labels, missing-wordfreq slice:19 human4,19 human5,11 human2/3.

| Human label | Candidate1–2 | Candidate3 | Candidate4 | Candidate5 |
|---|---:|---:|---:|---:|
|4 (19)|0|3|8|8|
|5 (19)|0|0|6|13|

Constant4 gets19/38 of those human4/5 cases exactly right; candidate21/38.
Across all49 tail forms, candidate assigns5 to24:13 correct,8 human4,3 human3.
**Precision5=54.2%; recall5 in the tail=68.4%.** False5 on human1–3:3
(clivaj, microunivers, târfă). Across all150, recall5=59.1% because3 human5
forms have wordfreq and remain on the common direct route. The full human4/5
subset has43 forms, including5 on the direct wordfreq route; complete5×5 confusion
and the separate2×5 human4/5 table are saved, so predictions1–3 are never dropped.

First-independent tail: candidate predicts no5. Of19 human4,14 receive4 and5
receive3; of17 human5,15 receive4 and2 receive3. Discrimination does not survive
rating-history sensitivity.

All84 non-leaf splits across latest eligible tail folds use the cross-entry count.
Neither tag feature is selected: only1 tail form has all-senses restriction and2
have all-senses specialist tags, below minimum leaf support. The modest latest
improvement therefore does **not** establish that semantic tags distinguish4/5;
the candidate mainly learns dictionary mention scarcity within aligned forms.

## Recommendation and leftovers

Keep extractor and diagnostic workflow; keep operational fallback4 unchanged.
Do not export or promote this candidate over the full inventory. The latest gain
is only3 absolute-error points overall, with an extra severe error and worse
clarified/first-independent results.

Next useful step: a source-coverage investigation for an independent Romanian
running-text frequency source, preferably an explicit versioned local/public corpus
with exact-form counts. Establish availability and provenance before implementing
another model. Expand grammatical alignment only where source structure supplies
an exact witness; never silently transfer a nearby lemma's tags. No new user
annotation is needed for source discovery, though the existing150 cannot establish
independent generalization. Further tree tuning on the same pilot is not warranted.

Remaining: better broad corpus coverage (the earlier inventory audit leaves47,319
fallback rows without positive local lexical/mention evidence), verified exact-sense
coverage, robust4/5 discrimination, independent generalization. D1 remains deferred.

## Reproduction

Install the existing `evaluation` extra. From the implementation checkout:

```sh
classificator evaluation-local-evidence \
  --vocabulary-csv ../local-fallback-2026-10-25/inputs/inventory.csv \
  --loc-file ../local-fallback-2026-10-25/inputs/loc.txt \
  --sources-csv ../local-fallback-2026-10-25/inputs/sources.csv \
  --mentions-csv ../local-fallback-2026-10-25/inputs/mentions.csv \
  --campaign-dir ../local-fallback-2026-10-25/evidence-replay
classificator evaluation-local-fallback \
  --reference-csv ../pilot-2026-10-17/data/evaluations/2026-10-21-fabian-short/working-reference-150.csv \
  --features-csv ../independent-2026-10-23/features.csv \
  --evidence-dir ../local-fallback-2026-10-25/evidence-replay \
  --first-independent-csv ../pilot-2026-10-17/data/evaluations/2026-10-19-fabian/labels-first-independent.csv \
  --groups-csv ../robustness-baselines-2026-10-24/groups.csv \
  --campaign-dir ../local-fallback-2026-10-25/comparison-replay
```

Local run artifacts under `build/d1/local-fallback-2026-10-25/`: input projection
and lineage, predeclared protocol, extraction, comparison, scripts and verification.
These are local artifacts; existing raw HTML/LOC snapshots are not bundled with
the source commit. Use fresh output paths; existing directories are refused.
