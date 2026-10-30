# Sequential scoring and offline evaluation

Date: 2026-10-16. Status: implemented experimental path.

The current classifier combines chat generation, repair, CSV orchestration and selection. D1 returns typed distributions; reusing chat repair would create misleading abstractions. Evaluation also needs failures and abstentions that the existing production CSV cannot represent.

Decision: one small `BatchScorer.score_batch(items)` Interface returning an explicit `Outcome` per ID. D1, existing chat, and frequency thresholds are Adapters. The campaign module owns checkpointing, CSV projections and manifests. Dataset preparation and statistical reports are pure offline workflows. D1 is opt-in through `evaluation-run` or `step2-score --backend d1`; the existing chat Step2 remains the default and retains its established orchestration. `ChatScorer` allows programmatic experiments through the new Interface without changing legacy repair behavior.

One word per D1 request, one blocking request at a time. No worker pool, async scheduler, model loader, downloader or automatic fallback. Read-only preflight requires one already-loaded decision instance, uses that instance ID for inference and rejects identity/configuration changes. The caller must keep the server's model configuration stable during a campaign; the adapter cannot atomically lock LM Studio's UI against external changes.

Durable per-ID JSON contains raw requests/responses and outcomes. CSV projections refresh every 100 committed records and on clean completion/interruption; restart rebuilds them from validated records. No response payload accumulation in RAM, no full CSV rewrite per word. Manifest pins vocabulary, evidence, rubric, thresholds, implementation digest, user-declared runtime version and supplied model-file digest. The supplied model file is hashed, but the server does not prove that its loaded weights match that local file; operators must select the matching artifact. Raw class probabilities are not calibrated correctness estimates.

Architecture principles applied:

- KISS: synchronous requests, plain functions, one dataclass and Protocol; no framework.
- YAGNI: no fine-tuning, trainable hybrid or calibration infrastructure before gold labels justify them.
- DRY and Rule of Three: reuse existing CSV codec, repository and locking; abstract shared scoring only where actual adapters vary. Small source-specific parsing remains local.
- SoC: transport, lexical evidence, persistence and metrics evolve independently.
- POLA: chat stays default; no implicit model loading; unsupported D1 Step2 flags fail visibly.
- Fail Fast: invalid identities, probability vectors, source schemas and changed manifests stop unsafe resumption. Item-level HTTP failures remain visible outcomes.
- Gall's Law: offline, testable vertical slices precede live pilot and replacement.
- High cohesion / low coupling: each module owns one behavior; campaign knows no HTTP details.
- Explicit dependencies and composition: injected scorers/HTTP session; no inheritance hierarchy or service locator.
- Reproducibility: immutable inputs, versioned policy, retained probabilities and explicit missingness.

Step5's exact-count local-ID selection and Step4's semantic gates remain separate. D1 scores do not automatically implement exact-K selection. No upload or production default change in this feature.


## 2026-10-21: exact surface across valid POS

Keep the existing BatchScorer and CSV boundaries. Add a separate versioned
`forms.csv` lexical contract rather than extending production BaseWordRow or
reinterpreting its `type` column. The request exposes `inventory_type` as historical
metadata plus optional all-POS evidence. The rubric uses the most familiar valid
sense of the literal surface; normalization never lemmatizes or strips diacritics.

Source-bounded LOC/curated evidence is separate from human labels and assistant
estimates. Exact-form reference kinds gate metrics, preventing the113 opaque
initial pilot labels from entering the clarified-target comparison. Raw frequency
and ranking comparisons precede any threshold fitting. Rebus uses sequential local
cache extraction with target-page exclusion and exact-definition deduplication.
No new scoring framework, parallel inference, automatic model load or upload path.

## 2026-10-24: frozen complete wordfreq scorer

Use two plain CSV functions in `evaluation.wordfreq_baseline`: freeze a model from
an explicit pilot/reference/frequency snapshot, then score an explicit inventory
from that model and compatible exported frequencies. Calibration imports the fitter
lazily; scoring never refits or imports wordfreq, sklearn, DB clients or model
transport. CLI handlers dispatch before database configuration. Keep the existing
abstaining FrequencyScorer unchanged; the offline workflow applies an explicit
recorded fallback to its unresolved outcomes. No integration with production Step2.

Frequency exports now pin exact lookup policy and normalized full-corpus digest,
in addition to package/version/language and inventory/export hashes. Each scoring
input must be an export for that exact inventory; a subset cannot masquerade as
missing evidence. Configuration identity is a canonical-content SHA256. Every CSV
row carries the model identity, frequency and direct/fallback route. Preserve all
inventory IDs/POS, including repeated forms; no lemmatization or diacritic stripping.
Publish staged output directories atomically and refuse existing output paths.
A shadow export is an operational artifact, not authorization to upload or evidence
of accuracy on unlabelled inventory. Step5 and upload gates remain independent.

## 2026-10-25: local lexical evidence and fallback experiment

Two plain offline CSV functions: local_evidence exports source-bound senses and
features; local_fallback validates artifacts and runs grouped comparisons. Reuse
exact normalization, threshold fitter and metrics. Keep extraction label-free and
retain unresolved identities/POS instead of transferring lemma evidence. A small
fixed tree is evaluation-only; shared direct thresholds fit inside training folds.
No production scorer integration or alteration of the frozen wordfreq configuration.
Local sources stream sequentially by file; outputs publish atomically with hashes.

Mention counts carry a mandatory sidecar tying the exact inventory to a versioned
corpus, source ledger, extractor and checked derivation; hashing a bare counts CSV
is insufficient provenance. Explicit singular/plural restrictions participate in
sense alignment. A child's explicit number scope overrides its parent's; usage
preferences such as “mai ales la plural” are not exclusive restrictions.


## 2026-10-27: bounded FineWeb2 evidence and comparison

Keep source extraction and fold-local evaluation as independent CSV functions.
FineWeb2 is optional offline research, never a production scorer/DB integration.
PyArrow21 reads only required column chunks through an explicit seek/read adapter;
pre_buffer=False/use_threads=False. HTTPAdapter.send returns headers without the
Requests Session redirect-body drain; all body reads and redirects are controlled.

One locked campaign binds inventory, pinned shard metadata, policy and implementation
hashes. Reserve payload+8192bytes/request before transport, and document attempts
before decoding; uncertain reservations survive interruption. Default transfer cap
1GiB includes40MiB dependency allowance. No corpus cache or full shard file; range
cap64MiB, selected-group uncompressed cap128MiB, free-disk floor5GiB. HTTP accounting
is conservative application payload/reservations, not a TCP/TLS wire-byte meter.

Checkpoint schema, campaign binding, state digest and progress validated on resume.
CSV generation becomes readable only when its manifest is published; a low-space
provisional manifest is invalidated before rebuilding resumed projections. Complete
runs replay locally without network; exhausted hard budgets cannot be reset in place.

Freeze seeded rowgroup order across all shards and per-shard document quotas before
labels. Partial groups use leading rows; frequencies describe this bounded sample,
not a uniform document sample or unbiased whole-corpus estimate. Count attempted
documents before filtering. Exact Unicode token policy retained; temporal-slice-local
text deduplication, explicit source/language exclusions and bounded concordances.
Primary2020–2024 and older2013–2019 counts remain separate.

Evaluator validates complete-inventory source CSV/hash binding and keeps the shared
wordfreq path fold-local. Only balanced sample plus5tokens/3docs/2hosts can enter
the fallback; minimum10 eligible training forms/two levels. Unsupported inputs
remain4. Three existing label views/4vs5 diagnostics, no new annotation or tuning.


## 2026-10-28: CoRoLa research evidence and shared grouped comparison

Keep public CSV seams: `export_corola_frequencies` consumes a local published TSV,
release receipt and full inventory; `evaluate_corola_fallback` consumes validated
CSV artifacts plus existing labels/groups. No new production scorer or DB/LM path.
CoRoLa source identity, complete counts/denominator and exact-form consistency are
validated independently; no invented document/host fields. Published source and
modified lookup artifacts stay local to the authorized noncommercial experiment.

FineWeb and CoRoLa now use one private grouped-frequency engine with a small
validated evidence record. Source validators and support rules remain in adapters.
This consolidates repeated grouped orchestration while preserving FineWeb's public
CSV/result behavior and source-specific policy. Local lexical-tree evaluation keeps
its distinct model. Test public CSV functions, not helper internals.

CoRoLa denominator is the complete published filtered word list, not a guessed full
corpus token count. Normalize only NFC/cedilla/casefold, preserve all IDs/POS, sum
source spelling aliases. Missing source counts remain4. The source improves coverage
but fails the severe-error gate; neither frozen scorer configuration nor upload
workflow changes.


## 2026-10-28: Source-scoped lexical variant witnesses

Keep `export_local_evidence` as the public CSV seam and `evidence.csv` compatible.
Add `variants.csv` plus additive sense fields for target POS detail, source entry,
dictionary, declaration and variant number restriction. Manifest extraction revision
`explicit-variants-v1` distinguishes the repaired algorithm; all outputs remain hashed.

A relation needs an explicit semantic variant declaration and identifiable target POS.
Bind structured meanings to the same dictionary/headword/POS; reject ambiguous
homographs. Raw MDA2 extraction supports only bracket headers and consecutive numbered
meanings. Preserve variant gender/usage and meaning restrictions; contradictory own
POS or number scope remains unresolved with a reason. Relation support does not imply
all meanings recovered. No inference from redirects, spelling similarity or examples.

Keep format-specific parsing local; no new framework, scorer coupling, frequency
transfer or database/model path. Coverage is source-bounded, never a completeness or
familiarity claim. Test CSV behavior, negative cases and provenance through the public
function. Frozen scoring configuration and human labels remain outside this repair.


## 2026-10-30: exact-form evidence audit before independent judges

Keep the approved sources-to-CSV boundary. `audit_form_evidence` consumes the frozen
form sample, full inventory, and existing lexical/exact-form exports; outputs one
coverage row per form, all original memberships and source-scoped contexts. Reuse
existing parsers; do not add scoring, model or DB dependencies. A thin CLI delegates
to the same public function.

Validate complete membership/POS and mandatory hashed provenance/revision before
export. Parent joins include source, heading, POS detail, dictionary/entry/variant;
unresolved parents never become usable context. Missing evidence stays explicit.
LOC POS coverage is source bounded, never exhaustive semantic completeness or score
confidence. Empty example-based form contexts are valid: do not fabricate examples
just to adapt lexical definitions into that older schema. Atomic new directories,
no overwrites; tests at the CSV seam. Native scores and labels remain separate.

## 2026-10-30: provider-neutral sequential chat judges

Reuse `run_campaign` and `Outcome` for durable per-form receipts and predictions.csv.
The new CSV collector validates complete exact-form lexical evidence before HTTP;
its small Chat Completions adapter returns a strict integer judgment or explicit
failed outcome. Model loading, RAM/live-instance checks and credentials stay outside
in the runner/session. No Step2 default or upload integration.

No fabricated probabilities or confidence: use `probabilities=()`, `confidence=None`.
The legacy run.csv projection therefore stays empty; evaluate predictions.csv. This
prevents research-only judgments from masquerading as upload-ready scored runs.

Pin endpoint, requested model, provider options, lexical/prompt implementation
hashes and runtime metadata in the existing campaign manifest. Options are copied
before the manifest and scorer are created. Raw failed HTTP/JSON results are retained;
no repair, retry or implicit alternate-model route. One final assistant response,
matching identity, stop finish reason, exact schema, no duplicate keys/refusal/tools.

The same fixed evidence CSV and prompt can be reused with another compatible
Chat Completions endpoint. Provider-specific reasoning/token options remain explicit;
GPT availability, alias resolution and concrete parameter support require a later
separate probe/campaign. No GPT inference is implied by this interface reuse.

A separate offline CSV comparison joins human references only after inference.
It requires full identity coverage, reports native failures separately, uses the
frozen baseline explicitly for complete coverage, and reports severe>=2/excess loss,
4/5 diagnostics and deterministic review queues. Ranking has no human-label input;
selected cases are assessed afterward. No calibrated confidence or automatic promotion.

Curated contract contexts are a separate evidence source and must not disappear
when projecting parsed dictionary senses. Merge all contexts, preserving every POS
and existing restriction. Keep source metadata and illustrative examples out of
model state. If meaning prose contains reviewer instructions, use an explicitly
audited complete projection CSV; validate original identity/POS/meaning, hash it,
and retain original/projected text in provenance. No word-specific scoring rules or
automatic lexical blacklist. Curated, label-exposed evidence remains exploratory;
source fidelity is not the same as independence or exhaustive semantic coverage.
