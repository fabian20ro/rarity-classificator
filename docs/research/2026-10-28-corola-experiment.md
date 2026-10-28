# CoRoLa exact-form research experiment — 2026-10-28

## Decision

**Keep frozen wordfreq + fallback 4.** CoRoLa substantially improves raw coverage,
but the predeclared learned fallback increases severe errors in every label view.
On the latest 150 labels, MAE worsens from 0.520 to 0.533 and errors of at least two
levels increase from 11 to 13. No production promotion or threshold retuning.

This is a completed noncommercial, offline research experiment. No D1 loaded, model
request, database access or upload. Every method returns a score for every labelled
form; raw frequency coverage is a separate diagnostic.

## Source, access and resource use

Vasile Păiș (2022), [CoRoLa Frequency Lists v1](https://zenodo.org/records/7091535),
DOI 10.5281/zenodo.7091535. Licence verified in the record metadata:
[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/).
User authorized noncommercial research. Source and derived lookup/prediction CSVs
remain workspace-local; this experiment does not authorize commercial integration
or redistribution of modified source data.

Published ZIP downloaded once: **114,091,202 bytes**; MD5
`0034d61d1825b38386dfa0bc2606a314`. Extracted only
`corola_word_freq_all_lowercase.tsv`: **23,732,979 bytes**, SHA-256
`ce262fea71d16e3b0d024527054c9ddf321fa59690e492abb8e9056517aa6859`.
Archive MD5, member CRC/size, metadata identity and TSV hash verified. Direct HTTP
requests use bounded reads, no retries/redirect-following; the 120 MiB payload cap
covers archive plus at most 1 MiB metadata. A 5 GiB free-disk floor checked before
acquisition; about 88 GiB free. Total retained artifacts about **141 MiB**, including
the original ZIP, single TSV, CSVs, comparison and independent verification.

Use the complete lowercase **word-form** list, not lemma, ASCII-folded or truncated
count lists. The publisher excludes tokens containing numbers/special symbols.
Parsed **1,813,746 entries**; count denominator **637,764,339** is the sum of this
published filtered list, not a claim about every token in the entire CoRoLa corpus.

Normalization: NFC, cedilla-to-comma, casefold. Sum source spelling aliases under
that normalization. Preserve accents, literal inflections, î/â distinctions and all
inventory IDs/POS rows. No lemmatization or inferred sense labels. Counts pool names,
homographs and all surface uses; the list has no document/host/time/context fields.

## Frozen protocol

Saved `protocol.json` before downloading/count lookup. Existing CSV boundaries:
source TSV + provenance + inventory → complete frequency CSV; frequency evidence +
existing labels → grouped predictions and metrics. Source-specific validation stays
separate; FineWeb and CoRoLa now share the fold orchestration.

One candidate only: share the fold-fitted wordfreq direct path with the baseline.
For missing-wordfreq forms with **CoRoLa count ≥5**, fit the existing monotone
frequency thresholds using eligible missing-wordfreq training forms. Require at
least **10 training forms and two distinct levels**. Otherwise return 4. Never
interpret absence as 5. No invented document-diversity support, no search over
alternative floors/models, no merged corpus denominators.

Existing leave-one-group-out exclusions retained; fit separately for latest working
150, original-round-final 150 and first-independent 149. Every held-out group is
excluded from both fits. Labels have been used in prior experiments: these are
internal sensitivity checks, not independent generalization estimates. The frozen
production configuration remains unchanged; baseline thresholds here are refitted
inside folds for a fair out-of-fold comparison.

## Coverage

| Scope | Total | Count >0 | Count ≥5 |
|---|---:|---:|---:|
| Full inventory rows |77,698|61,073|49,223|
| Missing-wordfreq rows |66,088|49,464|37,614|
| Pilot forms |150|144|136|
| Missing-wordfreq pilot forms |49|43|35|
| Latest human 5, all pilot |22|16|10|
| Latest human 5, missing wordfreq |19|13|7|

Wordfreq raw pilot coverage remains 101/150; CoRoLa observes 144/150. Both complete
scoring paths cover **150/150**. Among 66,088 missing inventory rows, CoRoLa observes
74.85%, versus 38.15% in the bounded FineWeb sample. These are differently sized
sources; this is coverage on the same targets, not a controlled corpus-quality claim.

Distinct missing-wordfreq forms: 47,874/64,226 observed, 36,325 supported; 16,352
unobserved. Full inventory: 58,794/75,147 distinct forms observed, 47,245 supported.
Missing-row count bands: 0=16,624; 1=5,039; 2–4=6,811; 5–9=5,330; 10+=32,284.

Latest pilot labels:

| Human level | Forms | Observed | Supported |
|---|---:|---:|---:|
|1|51|51|51|
|2|31|31|31|
|3|25|25|25|
|4|21|21|19|
|5|22|16|10|

Of the missing-wordfreq human-5 examples, seven pass support: bromocet, iț, bizam,
cioareci, diorit, hipochinezie, xilem. Six are present below support: micșurat,
sericină, abietacee, boraci, cașerare, preajm. Six are absent: aalenian, păpușire,
briofită, eolit, sferoidizare, ștrecui. Detailed counts for all 22 are in the local
`human5-coverage.csv`. The other three human-5 forms—carter, dorian, ata—already have
wordfreq values and therefore retain the direct path. Surface counts do not resolve
their exact-sense ambiguity. The intentional rating 5 for micșurat is preserved.

## Grouped comparison

All 35 supported missing-wordfreq pilot forms use a fitted CoRoLa model in each
view; no training gate blocks them. Latest routes: 101 wordfreq, 35 CoRoLa, 14
unsupported→4. First-independent has 100 direct-wordfreq rows; the other routes
are unchanged. All 449 baseline predictions match the previous FineWeb experiment.

| View / scope | N | Baseline MAE | Candidate MAE | Exact baseline→candidate | Errors ≥2 baseline→candidate |
|---|---:|---:|---:|---:|---:|
|Latest working|150|0.520|0.533|86→86|11→13|
|Latest missing wordfreq|49|0.653|0.694|19→19|2→4|
|Latest clarified|37|0.568|0.649|21→20|4→6|
|Latest opaque|113|0.504|0.496|65→66|7→7|
|Original round final|150|0.707|0.700|72→74|18→19|
|First-independent|149|0.624|0.617|74→77|13→15|
|First-independent missing wordfreq|49|0.653|0.633|19→22|1→3|

The historical views gain only one point of total absolute error each. Both
increase severe errors; latest clarified labels worsen. Non-singleton subsets
remain unchanged (16 latest/original rows; 14 first-independent). The aggregate
historical gain is insufficient for promotion.

Exactly six latest-label predictions change, all from baseline 4 to candidate 5:

| Form | Human | Baseline | Candidate | Effect |
|---|---:|---:|---:|---|
|bromocet|5|4|5|corrected|
|hipochinezie|5|4|5|corrected|
|clevetitor|4|4|5|new error|
|ițar|4|4|5|new error|
|antereu|3|4|5|error grows to two levels|
|sezisa|3|4|5|error grows to two levels|

Nine unique forms change across the three views: those six plus anhidrit, diorit
and xilem in historical views. Do not infer one fixed cutoff from this list: each
prediction uses a different held-out training fold.

### 4 versus 5

Latest missing-wordfreq slice: 19 human-4 and 19 human-5 forms.

| Human | Baseline predicts 4 /5 | Candidate predicts 4 /5 |
|---|---:|---:|
|4|19 /0|17 /2|
|5|19 /0|17 /2|

4/5 exact accuracy stays **19/38**. Human-5 recall in this slice rises from 0 to
2/19 (10.5%), while human-4 recall falls from 100% to 17/19 (89.5%). Across all 150,
human-5 recall is **2/22 (9.1%)**, precision **2/6 (33.3%)**; two predicted 5s belong
to human 3 and two to human 4. Baseline precision 5 is undefined because it predicts
no 5, not evidence of a better rare-class recognizer.

First-independent: 5 correct 5s out of 9 predictions; precision 55.6%, recall 5/20
(25%). Two false 5s on human 1–3. Original-final: precision 5/9, recall 5/29, one
false 5 on human 1–3. Full 5×5 matrices, precision/recall 4 and 5, every prediction,
strata and fold models remain in the comparison artifacts.

## Recommendation and leftovers

Follow-up completed: [local divergence audit](2026-10-28-corola-divergence-audit.md).
The baseline decision remains; next engineering work is evidence extraction and
provenance, with no new annotation or scoring change. The list below records the
recommendation immediately after this experiment.

1. **Retain frozen wordfreq+4.** CoRoLa adds useful frequency evidence, but this
   predeclared frequency-only fallback fails the severe-error gate in every view.
   Do not lower support, relabel examples, infer 5 from absence, or search for a
   favourable cutoff on these same predictions.
2. **Next: a bounded diagnostic audit using already available local evidence.**
   Inspect the nine changed forms across views plus ata/carter/dorian from the
   direct path. Separate exact-form/sense ambiguity, historical label changes and
   genuinely overlapping familiarity/frequency. No new user annotation, model
   loading or download required. Existing human labels remain fixed; assistant
   interpretations of these cases are explanations, not independent training data.
3. If that audit exposes a general source-quality or sense rule supported by local
   source records, specify it before another experiment. Otherwise stop tuning the
   150-word pilot and retain the conservative baseline until independent evidence
   becomes available. Repeated cross-validation on reused labels cannot establish
   external generalization.
4. Still unresolved: reliable 4/5 separation, absent/weakly supported rare forms,
   POS/sense-disambiguated corpus use, external validation, and reuse permissions
   for any future distributed/commercial CoRoLa dependency. Counts alone cannot
   settle personal familiarity of the most familiar valid exact-form sense.

## Verification and reproduction

**871 tests +211 subtests, Ruff pass.** TDD through the previously approved CSV
boundaries: exact normalization and complete denominators, malformed/duplicate TSV
records, source integrity, count support, minimum training, held-out own/group-label
mutation, unchanged wordfreq path, complete outputs and deterministic replay.
Independent standards review and spec review: zero actionable code findings.

Independent stdlib verifier (no production imports): source checksums, all 77,698
IDs/75,147 forms, every coverage section, 449 group folds, 554 fitted models
reoptimized with a separate prefix-DP solver, and 36 metric sections including
4/5 and severe errors. All baseline predictions identical to previous experiment;
frozen scorer/input hashes unchanged. Offline extraction/evaluation explicitly
block HTTP and DB connections. No D1 or database activity.

Workspace-local campaign: `build/d1/corola-2026-10-28/`. Acquisition and reproduction
scripts `acquire.py`, `export.py`, `coverage.py`, `compare.py`, `verify.py`; pinned
`protocol.json`, `metadata.json`, `source-record.json`, `access-receipts.json`,
`input-hashes.json`, source CSV/manifest, `coverage.json`, `human5-coverage.csv`,
comparison summary/predictions/folds/manifests, `verification.json`. Source and
comparison exports deliberately refuse existing output directories; reproduce into
new directories rather than overwriting results. No remote push/PR this iteration.
