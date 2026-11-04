# Bounded FineWeb2 experiment — 2026-10-27

## Decision

Keep the frozen **wordfreq + fallback 4** scorer. The source adds substantial exact-form
coverage, but this experiment does **not** establish an improved classifier or 4/5
separation. Only 8 of 49 missing-wordfreq pilot forms meet the frozen support rule;
none has latest human level 5. The declared minimum 10 eligible training rows is never
met. No FineWeb threshold model is fitted in any fold; candidate predictions equal
the baseline by the declared insufficient-evidence route. This is not an empirical
tie between two successfully trained classifiers.

No thresholds relaxed, additional labels requested, D 1 loaded, DB connection made,
production scorer changed or inventory scores overwritten. Latest 150, original-final 150
and first-independent 149 remain distinct internal validation views; none is a new
independent holdout.

## Resource limits and implementation

Public seams confirmed by user 2026-10-27; vertical TDD implementation. Source HTTP→CSV
separate from CSV→grouped comparison, with a small headers-first HTTP transport.
The [prior protocol](2026-10-25-romanian-running-text-corpora.md) and preparation on
2026-10-26 fixed 100,000 examined documents or 1 GiB transfer, support 5 occurrences/
3 documents/2 hosts, minimum 10 eligible training forms/two levels. Inputs and source
revision pinned before counts and calibration.

Actual run:

| Resource | Result |
|---|---:|
| Examined/reserved documents |100,000 /100,000|
| Selected groups / shards |100 /20|
| Documents per shard |5,000|
| HTTP response payload read |385,836,138 bytes (367.96 MiB)|
| Conservatively charged budget |436,626,538 bytes (416.40 MiB)|
| Cap / stop reason |1,073,741,824 bytes / document limit|
| HTTP requests / pending reservations |1,080 /0|
| Local experiment artifacts after comparison |about 180 MiB on disk|
| Peak process RSS |1,377,583,104 bytes (about 1.28 GiB)|

The budget includes 40 MiB reserved for the parser dependency and 8192 bytes per request
as an overhead allowance. It is a conservative application-payload budget, not an
exact TCP/TLS meter. No shard or raw corpus cache is stored. Small concordance windows,
CSV projections, source/input metadata and checkpoints remain for audit/resume.
Arrow chunks are bounded to 64 MiB compressed/request and 128 MiB selected uncompressed
group;5 GiB free-space floor checked before requests. Space started near 84 GiB free
and remained near84GiB. Installation used `uv --no-cache` (29.8MiB wheel reported).

Important regression: Requests Session can drain redirect bodies despite streaming
and disabled redirects. Direct HTTPAdapter.send avoids that hidden read. Reservations
persist before each request/document attempt; incomplete work remains charged.
Checkpoint schema/binding/hash/progress validated; low-space recovery invalidates
its provisional manifest before rebuilding CSVs. A completed real campaign replayed
with HTTP/DB forbidden and every source artifact byte-identical.

## Corpus and sample

Pinned [FineWeb2 Romanian train revision](https://huggingface.co/datasets/HuggingFaceFW/fineweb-2/tree/af9c13333eb981300149d5ca60a8e9d659b276b9/data/ron_Latn/train)
`af9c13333eb981300149d5ca60a8e9d659b276b9`; pyarrow21.0.0. Seed20261026 chooses rowgroups
across all 20 shards. Actual groups each contain 1,000 rows and are fully examined.
The general implementation allows a quota prefix for a partial final group. Counts
describe this selected sample; no uniform document probability or whole-corpus
frequency extrapolation is claimed. Numeric inclusion probabilities were not estimated;
this is an explicit limitation relative to the research note's probability-recording
suggestion. The selected group plan/row counts are saved.

- Primary crawl years 2020–2024: **70,255 documents,35,932,359 tokens**.
- Older 2013–2019 diagnostic: **29,715 documents,16,189,283 tokens**.
-30 documents excluded by the frozen dictionary-host list; no additional exclusions
  from language/duplicate rules occurred in this particular sample.
- All eligible text tokens contribute to the denominator, including noninventory
  tokens. NFC/cedilla-to-comma/casefold; no accent stripping or lemmatization.
- Exact text deduplication is within each temporal slice. All inventory IDs/POS
  retained; homographs, names and malformed uses are not disambiguated by counts.

Database licence: [ODC-By1.0](https://opendatacommons.org/licenses/by/1-0/) with
[Common Crawl terms](https://commoncrawl.org/terms-of-use); original content rights
remain distinct. Raw articles/concordance collections are not added to the repository.

## Exact-form coverage — primary slice

| Scope | Rows | At least 1 occurrence | Meets 5/3/2 support |
|---|---:|---:|---:|
|Full inventory|77,698|36,820|23,704|
|Missing wordfreq|66,088|25,211|12,110|
|Pilot|150|125|109|
|Pilot missing wordfreq|49|24|8|

For the missing-wordfreq inventory: **38.15% observed**, **18.32% supported**.
Distinct forms:24,319/64,226 observed;11,650 supported. Remaining 40,877 rows /
39,907 distinct forms unobserved. Source-frequency coverage is separate from operational
score coverage, which stays 100%. One directly observed-wordfreq inventory row is
unobserved in this sample; union coverage is 36,821/77,698 rows.

Missing-wordfreq row count bands:0=40,877;1=6,068;2–4=6,786;5–9=4,576;10+=7,781.
The host/document rule further reduces count-positive eligibility. Occurrence on
multiple hosts does not establish independent passages.

Pilot tail coverage by latest human level (labels joined only after extraction):

| Human level | Forms | Observed | Supported |
|---|---:|---:|---:|
|1|0|0|0|
|2|2|2|2|
|3|9|6|1|
|4|19|11|5|
|5|19|5|0|

The 8 supported forms: acrit,constricție,glandular,izotop,psihosocial,stolnic,târfă,zar.
Their latest labels are 2×level 2,1×level 3,5×level 4 and **zero level 5**. Larger raw
inventory coverage does not supply the missing rare-class calibration evidence.

## Label-blind source-quality audit

Auditor inspected 20 forms selected deterministically by SHA 256 from the 24,319 observed
missing-wordfreq forms, plus the 8 supported pilot forms, without human labels. At most
two 200-character source windows per form were retained. This bounded audit is not
an occurrence-level precision estimate or exhaustive sense validation.

Observed issues: copied passages across unrelated domains; keyword/SEO lists;
malformed translations; product/brand names; historical articles recrawled recently.
Examples: stolnic appears as a historical title and sausage brand; zar occurs in a
casino keyword list; constricție and târfă have incoherent keyword contexts. Two
retained contexts for glandular/psihosocial are coherent, but other occurrences may
still be noisy.2010/2019 publication URLs occur in the 2020–2024 crawl slice.

Consequences: exact whole-text deduplication does not remove copied passages; host
count is only a diversity proxy; crawl recency is not publication recency. No filter
was tuned after reading these examples. Raw corpus counts cannot certify the most
familiar valid sense/POS.

## Grouped comparison

All methods score every row. The wordfreq direct path is fitted once per held-out
group and shared; the new fallback can train only on supported missing-wordfreq
training forms. Since at most 8 are eligible before group exclusion, it remains 4.
Routes latest 150:101 wordfreq,41 unsupported→4,8 insufficient-training→4.

| Label view / scope | N | Baseline MAE | Candidate MAE | Exact (both) | Errors≥2 (both) |
|---|---:|---:|---:|---:|---:|
|Latest working|150|0.520|0.520|86|11|
|Latest missing wordfreq|49|0.653|0.653|19|2|
|Latest clarified|37|0.568|0.568|21|4|
|Latest opaque|113|0.504|0.504|65|7|
|Original round final|150|0.707|0.707|72|18|
|First-independent|149|0.624|0.624|74|13|

**4 vs 5, missing-wordfreq latest labels:**19 human 4 and 19 human 5; all 38 predicted 4.
19/38 exact; level 4 recall 100%, level 5 recall 0%; precision 5 undefined (no predictions 5).
Across all 150:22 human 5, none predicted 5;43 human 4/5,19 exact. False 5 on human 1–3=0,
which reflects no 5 predictions, not successful rare-class discrimination. First-independent
missing-wordfreq slice has 19 human 4/17 human 5, again all 4. No candidate changes in any
of the 449 held-out predictions across the three label views.

## Recommendation and remaining work

1. Retain frozen wordfreq+4; preserve this source exporter as an audited research tool.
   Do not lower the support/training floor or infer 5 from absence after seeing results.
2. Next small experiment: **the published CoRoLa exact-word frequency list**, if the
   intended noncommercial research use fits its BY-NC-ND terms. Match the same forms
   and measure coverage of the existing level 5 examples before any new calibration.
   Keep it a separate comparator; do not merge corpus denominators or ship restricted
   derived data automatically. This is a cheaper, more curated source check than a
   larger unfiltered web sample; no new annotation needed.
3. For further FineWeb work: predeclare passage deduplication, editorial/source-quality
   checks and treatment of names/lists before a new download. Broader sampling alone
   does not resolve the observed quality problem. A source with explicit publication
   dates would improve the recency claim. Recheck terms and version for any new source.
4. Remaining: enough clean, source-supported level 5 examples; defensible 4/5 separation;
   generalization beyond the reused pilot. A learned FineWeb fallback remains **untested
   on this run**, because the predeclared data gate prevented fitting. Model improvement
   must not be inferred from the new 25,211 count-positive inventory rows.

## Verification and artifacts

-860 tests +200 subtests and Ruff pass; vertical RED→GREEN regressions include exact
  Unicode counts, all-ID export, quotas, hard budgets, disk recovery, decompression
  limits, concurrency, real Requests redirect behavior, checkpoint corruption,
  publication interruption, source validation and held-out label mutation invariance.
- Independent audit:77,698 identities,64,226 tail forms,1,080 request reservations,
  checkpoints/projections, source hashes,449 folds and 36 metric slices pass. Baseline
  predictions exactly match the earlier local-fallback experiment.
- Real completed-source replay with HTTP/DB forbidden leaves every source artifact
  unchanged. Original inventory, frozen scores and pinned input hashes unchanged.

Workspace-local artifact directory: `build/d1/fineweb-2026-10-26/` (prepared26th,
executed27th). Key files: `protocol-confirmed.json`, `run.py`, `run.log`,
`source/manifest.json`, `source/budget.json`, `source/checkpoint.json`,
`source/sample-plan.json`, `source/sampling.csv`, `source/frequencies.csv`,
`source/older-frequencies.csv`, `source/concordances.csv`, `coverage.json`,
`tail-coverage-by-level.json`, `quality-audit.md/json`, `comparison/summary.json`,
three comparison prediction CSVs/fold directories, `verify.py`, `verification.json`,
`replay-verification.json`. No remote push or PR in this iteration.
