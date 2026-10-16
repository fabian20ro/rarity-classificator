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
