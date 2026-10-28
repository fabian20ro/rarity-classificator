# D1 Omni evaluation target and code map — 2026-10-29

Active evaluation examples now select `d1-omni-2b`, replacing the removed local
`d1-3b` artifact. The adapter already accepts an explicit model key; no model registry,
new default, request schema or scoring policy was needed. Offline wordfreq + fallback 4
remains the production recommendation. Historical results retain their model identity.

## Evidence and boundaries

Read-only `GET /api/v1/models` from the existing local LM Studio server returned:

```json
{
  "key": "d1-omni-2b",
  "type": "decision",
  "architecture": "lfm3",
  "decision_type": "lfm3-d1-omni",
  "quantization": {"name": "F16", "bits_per_weight": 16},
  "size_bytes": 4076585920,
  "max_context_length": 128000,
  "format": "gguf",
  "loaded_instances": []
}
```

Local artifact: `$HOME/.lmstudio/models/LiquidAI/d1-Omni-2B-GGUF/d1-Omni-2B-F16.gguf`.
The sibling `mmproj-...` file is not substituted for the model artifact. No load,
unload or inference request was sent. Recognition by the inventory does not establish
successful inference, runtime compatibility under load or Romanian classification quality.
Future runs still require an already loaded matching decision instance, actual runtime
version, artifact hash and a fresh campaign directory. Requests remain sequential.

The [official model card](https://huggingface.co/LiquidAI/d1-Omni-2B) lists typed
`choice` answers and probabilities, consistent with the adapter's decision contract.
Romanian is absent from its listed languages. The publisher recommends d1-2B for
text-only tasks; we retain the user's selected Omni target without claiming that it
improves this pilot. Quality and calibration must be measured before promotion.

## Graph before model change

Graphify plugin calls failed with `Unknown tool`, so no hosted graph was obtained.
A deterministic local Python AST map was generated and saved **before** model edits:
126 tracked modules / 381 import-site edges, with definitions, line numbers and source
hashes. [Graph instructions](../code-graph.md) explain regeneration, staleness checks,
impact queries and the distinction between import edges and runtime calls.

The D1 import neighborhood identifies the evaluation CLI, scorer, campaign and tests.
Direct source inspection confirmed that selection is already explicit and generic;
changing this target therefore needs invocation updates and compatibility tests, not
a special-case adapter. The post-change graph is regenerated separately; pre-change
JSON/Mermaid retained under `docs/code-graph/before-omni/`.

## Verification and remaining work

Offline compatibility tests cover the new model identity, resolved instance ID,
sequential preflight/request ordering and refusal to run an unloaded model. A campaign
regression proves that selecting Omni cannot resume an old d1-3b campaign or change
its existing files. These use mock HTTP and do not constitute an inference benchmark.
The graph CLI test covers relative imports, scope, definitions, deterministic outputs,
transitive importers and stale detection without overwriting artifacts.

1,150 protected score/evaluation/input files matched their previous hashes. No new
human evaluations, model execution, database changes or corpus download. The lexical
variant repair results remain 127/150 aligned forms, 45/49 in the missing-wordfreq
slice; no scores or reported classification metrics changed.

Remaining: restore Graphify service access and inspect index freshness; verify actual
Omni inference only in a separately authorized, adequately provisioned experiment;
robust Romanian 4/5 separation remains unproven. Do not spend more pilot iterations
searching thresholds merely because a newer model is installed.
