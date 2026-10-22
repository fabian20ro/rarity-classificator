# Independent exact-form round — frozen 2026-10-23

> Superseded by user direction on2026-10-23: no additional annotation round.
> This pack remains unlabelled; reuse the existing150 evaluations with provenance.
> See the revised plan. The frozen protocol below records preparation, not an active user task.

40 new Scrabble inventory forms; one card and one form score each;70 relevant
lexical contexts. The label is familiarity of the **exact spelling through its
most familiar valid meaning**, across valid parts of speech. Definitions assist
identification, not a test of whether a supplied explanation is understandable.
No per-sense labels are inferred from the selected form score.

## Sampling and scope

10 forms each: Romanian wordfreq f≥1e-4,1e-5≤f<1e-4,0<f<1e-5,and unobserved.
Candidate pool restricted to exact-matching successful local dictionary-cache
records. Pool sizes132/713/1707/7015. Sort spelling, seeded shuffle20261023,
then take first10 surviving documented family exclusions. Pilot150 IDs and
ASCII collision groups excluded; conservative family exclusions: numit,mic,
muri,procesor,adăuga. Selected40 manually reviewed for known family overlap;
this is not exhaustive etymological proof. Order shuffled with seed20261023.

This is a cache-covered, frequency-stratified **diagnostic sample**, not an
unbiased estimate over the full Scrabble inventory. A new set of forms rated by
the same person: definition-assisted, estimate-blind, not second-rater validation.
No extra annotation round is planned to chase exhaustive dictionary coverage.
Missing familiar meaning can be supplied through “Alt sens”; ambiguity can remain
unscored. Do not replace held-out forms after seeing their ratings.

## Frozen calibration

Only37 clarified development labels qualify (12 context minima +25 form reviews).
113 opaque initial form/POS labels excluded. Each source has29 observed fit rows.
No held-out labels consumed. Zero/missing frequency means abstention, never level5.
Shared rebus corpus excludes the union of150 pilot and40 new target/collision
pages:100 pages excluded,114,114 unique definitions,1,273,283 tokens.
Wordfreq3.1.1 reproduces the original pilot export exactly where observed.

Four strictly descending boundaries; level=1+count(f<threshold). Fixed log grid
10**(k/10),k=-120..0; minimize unweighted ordinal MAE. Ties choose lexicographically
largest descending thresholds. No labels5 observed by rebus: its final threshold
is fixed at min(observed pilot frequency)/10, explicitly **not identified by data**.

| Source | L1/L2 | L2/L3 | L3/L4 | L4/L5 | Fit MAE |
|---|---:|---:|---:|---:|---:|
| wordfreq | 3.9810717055e-5 | 3.9810717055e-6 | 3.1622776602e-6 | 2.5118864315e-6 | 0.4828 |
| rebus | 1e-5 | 5.0118723363e-6 | 6.3095734448e-7 | 7.8537135892e-8 (convention) | 0.3448 |

These MAEs are training fit, not comparative held-out performance. Full precision,
class/boundary support and implementation/input hashes are in thresholds.json.
Predictions frozen for190 rows before user annotation. New40 coverage:30 wordfreq,
31 rebus. Assistant estimates frozen separately; no estimate/source prediction
or frequency/stratum enters the public lexical payload. No D1 requests/model load.

## Annotation and import

UI: http://127.0.0.1:8765/review-independent/

Select the most familiar valid sense and give one1–5 score per form. A singleton
sense is selected automatically; no score is prefilled. Changing the selected
sense invalidates the current score. “Alt sens” requires a note; “Nu pot decide”
remains unscored. First/final ratings, context choices, revisions and notes are
preserved in JSON. Export CSV and full JSON after completion.

New localStorage namespace `romanian-independent-forms-2026-10-23-v1`; old rounds
untouched. Pack hash binds answers to exact meanings/order. Invalid saved state
is preserved rather than reset; concurrent edits refuse overwrite. QA uses a
separate namespace and is not part of human data. Browser tests touched QA only.

On import: retain raw exports; verify version, pack hash, unique word IDs and
meaning identities; inspect notes/other/unsure without changing frozen predictions.
Use final form labels as primary, preserve first ratings for sensitivity analysis.
Never expand a form score into fabricated labels for its contexts.

## Locked comparison after annotation

1. Show coverage and abstentions over all40, plus unresolved human judgments.
2. Primary comparison: ordinal MAE on identical human-rated intersection for
   wordfreq versus rebus. Also report each source's own covered MAE with its n;
   do not rank sources from different subsets alone.
3. Report exact agreement, within-one accuracy, confusion counts, signed bias,
   and Spearman rarity ranking. Report numerators/denominators and per-form errors.
4. Rare-word check: human4/5, coverage, and severe underestimation
   (human score minus predicted score≥2). If no such cases, say “not estimable”.
5. Compare frozen assistant estimates separately, on matched forms. No hybrid,
   prompt tuning, new frequency thresholds or model selection on these labels.

Small strata and shared rater limit generalization. A baseline is only a candidate
if lower matched MAE is not purchased through worse rare-word underestimation or
lower coverage; report trade-offs rather than a universal winner. New tuning would
turn this batch into development data and require a fresh test batch.

Next: import this single round and run the locked comparison. Then decide whether
a separate frequency signal is useful. Second rater and D1 runtime/quality trials
remain outstanding. D1 only when explicitly authorized and RAM permits; sequential
requests. No replacement or upload decision from this preparation.

## Local artifacts and reproduction

Private experiment directory: `build/d1/independent-2026-10-23/` (outside web root).
`manifest.json` binds selection, evidence, labels, feature CSV and calibration;
`publication-manifest.json` seals actual public pack and frozen private files.
The earlier `prepublication-draft-models/` differs only by formatter/code hash;
final predictions were checked byte-identical before publication.

- `inventory.csv`, `selection.csv`, `candidate-pools.json`, `selected-draft.json`:
  identities, deterministic selection and source bands.
- `source-definitions.json`, `curated-forms.json`, `contexts.csv`, `forms/`:
  lexical evidence, source hashes, all matching LOC entries and curated contexts.
- `combined-inventory.csv`, `wordfreq.csv`, `rebus/`, `features.csv`: one shared
  extraction corpus and explicit input features.
- `frozen-models/thresholds.json`, `predictions.csv`: frozen calibration/output.
- `assistant-estimates-private.json`: estimates, not gold, outside web root.
- `prepare.py`, `curate.py`: local reproducible preparation, no network/model calls;
  output paths must be fresh. wordfreq3.1.1 is an optional exporter dependency.

Reusable APIs in the implementation checkout:
`freeze_frequency_thresholds(pilot_csv, reference_csv, features_csv, output_dir)`
and `build_blind_review(forms_json, output_dir, version=..., seed=...)`.
Both refuse existing output directories. Feature schema excludes labels; the
review publisher rejects estimates/frequencies/strata instead of hiding them in CSS.
To resume the same browser origin after server restart:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory build/d1/pilot-2026-10-17
```

Validation: Ruff;795 Python tests +112 subtests, including public calibration,
blind pack rejection and JS rating/reload/export regression (Node required for
that test; skipped when unavailable). Real-browser QA verified rating, sense
selection, notes and reload. No human answers created in the actual round.
