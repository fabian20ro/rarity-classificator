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
