# Local evidence audit for the wordfreq fallback — 2026-10-24

Scope: the frozen export's66,088 fallback inventory rows, representing64,226
normalized exact forms. Read-only inspection of local files/source in the classifier,
generator-rebus and propozitii-nostime workspaces. No DB/API access, model loading or
changes to the frozen scores. This is an evidence audit, not a new trained classifier.

## Quantitative source coverage

Audited all12,728 cached DEX files by streaming raw JSON/HTML. Verified every file
hash against the prior corpus ledger. Reproduced1,273,283 tokens,114,114 deduplicated
spans (one empty structural span), and all190 previously frozen frequency counts.
No source scores, corpus exclusions or production files were changed.

| Evidence in generator cache / frozen definition corpus | Fallback rows /66,088 | Distinct forms /64,226 |
|---|---:|---:|
| LOC validity/POS match |66,088|64,226|
| Any game-key cache file, including mismatches/status failures |10,415|9,937|
| Exact query spelling + ok + nonempty definition material |7,334|7,025|
| Above, with an exact lexeme-name witness in the HTML |6,256|6,165|
| Token mention in frozen definition corpus |15,526|14,715|
| Token mention outside own game-key page |13,991|13,278|
| At least2 distinct outside-page definition bodies |7,178|6,749|
| At least5 such bodies |2,289|2,129|
| Union: exact-query page or outside-page mention |18,744|17,874|

That union is28.36% of fallback rows.47,344 rows/46,352 forms have neither signal
in this broad cache/corpus. An exact query or lexeme witness is still not exhaustive
sense/POS validation. Other-page mentions may be quotations, references or copied
definitions; they are not independent natural-language documents.

Removing own-page-only appearances reduces observed coverage by1,535 rows/1,437
forms. At full-inventory scope,12,565 of12,728 cache page keys belong to inventory;
passing all target words to the previous corpus exporter would exclude almost the
entire cache. This audit preserves the existing100-page exclusion policy and adds
separate outside-own-page counts; it does not silently redefine the corpus.

For exact-query pages, scoped candidate hints occur on2,963 fallback rows for
obsolete/archaic usage,2,629 regional,1,312 rare,2,115 specialist and2,478 register
(popular/familiar/slang/etc.). Categories overlap. These are **page-level candidates**,
not verified labels on all senses: raw definitions may tag a synonym or variant,
and a page may include both familiar and obscure meanings. In the pilot, both
human2 forms `acrit` and `zar` have obsolete/regional page hints—an immediate
counterexample to mapping such a page flag directly to5.

The installed wordfreq package has a Romanian small list and no Romanian large
list (`available_languages("large")` has no `ro`). Merely changing the wordlist
option cannot recover these missing forms from this installation. See the
[pinned local source diagnostic](</Users/fabian/git/word-rarity-classifier/build/d1/local-source-audit-2026-10-24/other-sources.json>).

### Supplement: existing lexical-review archives

The prior review archives contain117 hash-valid, nonempty exact-query HTML
snapshots. They cover48/49 pilot tail forms; the broad generator cache supplies the
remaining one. Thus **all49 wordfreq-missing pilot forms have a local raw lexical
snapshot** available for a uniform parser, without new human annotation or fetches.
An exact-query snapshot still does not certify the correct sense or all valid POS.

These snapshots add40 distinct fallback forms/41 rows beyond the generator cache.
Combined raw-page coverage is7,065 forms/7,375 rows. Combined pages OR outside-page
mentions cover **17,898 forms/18,769 rows (28.40%)**; **46,328 forms/47,319 rows**
remain without either positive signal. Archived sources improve pilot extraction,
not broad population coverage.

The consolidated lexical CSV has218 contexts for95 forms, including36/49 tail
forms. Its150-row form contract includes55 empty context lists. Context prose was
assistant-authored and selected after previous ratings: do not use annotations,
estimates, justifications or “was reviewed” as model features. Parse the original
source HTML with the same policy for every word. The unused40-word round copies
existing generator-cache material and adds no independent raw-source coverage.

A provenance anomaly: `CASA.json` is the only status-ok cache record under4KB and
contains only41 HTML characters, “O locuință.”. Its origin is unverified. Preserve
old frozen counts for comparability, but quarantine/verify such minimal pages before
building a new trusted corpus; status-ok and a matching checksum establish file
identity, not publisher authenticity. Do not silently change the frozen corpus.

Supplement details and input hashes:
[supplemental audit](</Users/fabian/git/word-rarity-classifier/build/d1/local-source-audit-2026-10-24/supplemental-coverage.json>).

## What the available sources actually represent

### Raw DEX cache: best local source for lexical evidence, not ground truth

The cache stores `word`, `original`, `status`, raw `html` and `fetched_at`. Files are
keyed by an ASCII-uppercase game form. `original` therefore matters: the same key
can conflate diacritics and distinct forms. `status=ok` or a matching filename does
not certify that every returned definition describes the requested exact surface.
The provider also follows redirects and can combine definition material.
[Cache schema and loading](</Users/fabian/git/generator-rebus/packages/rebus-generator/src/rebus_generator/platform/io/dex_cache.py:429>),
[game normalization](</Users/fabian/git/generator-rebus/packages/rebus-generator/src/rebus_generator/domain/diacritics.py:3>).

The source code recognizes archaic, regional, jargon, slang, technical, popular,
familiar, literary and obsolete usage categories. These could help distinguish
specialized rarity from extreme obscurity, but their contribution is a hypothesis
to test, not a deterministic mapping to level5.
[Usage categories and extraction](</Users/fabian/git/generator-rebus/packages/rebus-generator/src/rebus_generator/platform/io/dex_cache.py:87>).

A whole-HTML regex for “regional/archaic/obsolete” is invalid: dictionary-selector
navigation itself contains names such as the dictionary of archaic/regional words.
This was observed in local `ITAR.json`. Even inside content, tags must be associated
with the correct sense and exact form. Examples, etymologies, cross-references and
other returned headwords cannot donate an unqualified usage label to the target.
[Observed local page](</Users/fabian/git/generator-rebus/.cache/dex_definitions/ITAR.json>),
[current classifier's definition-span parser](</Users/fabian/git/word-rarity-classifier/build/d1/exact-form-code/src/classificator/evaluation/dataset.py:109>).

Current text extraction primarily captures definition-span text and may omit sibling
sense tags. A new audit should retain sense-local metadata from the raw HTML, with
source/sense provenance and ambiguity flags. A page-level candidate flag is not
proof that all valid senses of an exact form are restricted. Under the accepted
most-familiar-valid-sense rule, one familiar valid meaning can override an obscure
one; “at least one archaic sense” must never automatically produce5.
[Exact-form contract](</Users/fabian/git/word-rarity-classifier/build/d1/exact-form-code/src/classificator/evaluation/exact_form.py>),
[domain decision](</Users/fabian/git/word-rarity-classifier/build/d1/exact-form-code/docs/adr/2026-10-16-d1-evaluation-seam.md>).

Do not call `DexProvider.get`, `prefetch` or `lookup` for an offline-only audit.
`get`/prefetch may fetch and store; even `lookup` can query Supabase when a client
is attached and then write the disk cache. Parsing existing JSON directly provides
a narrower read-only boundary.
[Provider lookup implementation](</Users/fabian/git/generator-rebus/packages/rebus-generator/src/rebus_generator/platform/io/dex_cache.py:532>).

### Definition text as a corpus: positive evidence, with self-entry controls

The existing rebus-frequency extractor counts exact tokens from definition bodies,
globally deduplicates identical bodies and excludes target/collision pages. This
provides lexical mention evidence, not normal-language frequency. Dictionary style,
etymologies, abbreviations, historical citations and inflected examples differ
from the intended familiarity target.
[Existing corpus policy](</Users/fabian/git/word-rarity-classifier/build/d1/exact-form-code/src/classificator/evaluation/definition_frequency.py:15>).

For this audit, extend the existing frozen corpus's query vocabulary while keeping
its original exclusions fixed; verify the old150 counts remain unchanged. Also
report occurrences outside each target's own game-key page. Counting the word's
own dictionary headword as independent familiarity evidence inflates coverage.
Conversely, passing the entire inventory to the old exclusion interface would
remove many dictionary pages and create a different corpus rather than merely
extending the query set. Changes in corpus definition require a new explicit
version and validation, not silent reuse of old thresholds.
[Prior corpus manifest](</Users/fabian/git/word-rarity-classifier/build/d1/independent-2026-10-23/rebus/manifest.json>).

Positive occurrences across multiple distinct entries are plausible evidence
against extreme obscurity. Zero occurrences are censored coverage: they cannot
justify5 alone. A reference-only mention, spelling variant or ASCII collision must
remain distinct from an occurrence of the requested literal surface.

### LOC: validity and grammatical structure, not frequency

The local `words.txt` originates from LOC5.0; the Gradle download task identifies
that source explicitly. Rows contain spelling/stress plus grammatical/paradigm
codes. These identify valid forms/POS and help reject accidental headword or
inflection transfers. The database importer supports a restricted subset of POS;
therefore the original LOC file is needed for an all-valid-POS audit.
[Local LOC file](</Users/fabian/git/propozitii-nostime/src/main/resources/words.txt>),
[LOC download configuration](</Users/fabian/git/propozitii-nostime/build.gradle:115>),
[importer POS mapping](</Users/fabian/git/propozitii-nostime/src/main/kotlin/scrabble/phrases/tools/LoadDictionary.kt:86>).

The numeric paradigm code must not be interpreted as a token count, rarity score or
frequency rank. Presence in LOC proves neither commonness nor obscurity. Length,
POS and morphology may be useful control features; they should not directly assign5.
The importer is executable DB-mutating code and was read only, never run.

### Rebus vocabulary snapshot: broad overlap, inherited scores and collisions

`generator-rebus/build/words.json` contains73,676 records with normalized/original
spelling, length and an inherited `rarity_level`. Its producer reads the database's
word/rarity/type rows, folds diacritics and keeps the first row for each game key.
It does not count natural-language usage. Current producer code also carries POS,
but this saved snapshot does not; treat its actual schema as authoritative.
[Snapshot](</Users/fabian/git/generator-rebus/build/words.json>),
[producer](</Users/fabian/git/generator-rebus/packages/rebus-generator/src/rebus_generator/workflows/generate/download.py:13>).

Overlap with the frozen fallback export, using NFC/cedilla/case normalization only:

| Match | Inventory rows | Unique forms |
|---|---:|---:|
| Exact original spelling |64,910|63,104|
| Only folded game-key match |1,178|1,122|
| Total fallback universe |66,088|64,226|

Exact-match inherited-level histogram:1=362,2=2,946,3=9,212,4=22,398,5=29,992.
These are snapshot scores, not new labels. Among those64,910 rows,21,020 agree with
the classifier's saved `current_db_levels.csv`;43,890 disagree. Snapshot drift and
lossy normalization make automatic score borrowing particularly unsuitable.
[Classifier legacy snapshot](</Users/fabian/git/word-rarity-classifier/build/rarity/reference/current_db_levels.csv>).

The classifier legacy snapshot covers all66,088 fallback rows, with levels
1=1,772,2=5,982,3=12,644,4=19,600,5=26,090. It is useful as an explicitly historical
comparator or disagreement prioritizer. It cannot serve as independent training
truth for a replacement intended to correct the old classifier.

### Curated clues and generated text: task-specific material, not usage corpus

`build/words.answer_supply.json` contains260 plate-code/TLD-oriented answer rows.
It overlaps zero fallback forms by exact spelling and one by game key only. Its
`clue_support_score` and derived rarity are assigned by source category; the
implementation assigns curated entries a fixed rarity2. These clues must not turn
an arbitrary matching ASCII sequence into a familiar Scrabble sense.
[Answer-supply snapshot](</Users/fabian/git/generator-rebus/build/words.answer_supply.json>),
[source-category defaults](</Users/fabian/git/generator-rebus/packages/rebus-generator/src/rebus_generator/domain/answer_supply.py:30>).

The70-row curated rebus assessment set uses low/medium/high *clue-quality* tiers.
Its default `avg_rebus_score` values4.0/6.8/9.2 are configured values, not human
rarity ratings. Other prompt-evaluation datasets aggregate model/pipeline success
rates and rebus scores. Counting repeated generated clues or benchmark appearances
would measure selection/generation policy rather than spontaneous usage.
[Curated builder](</Users/fabian/git/generator-rebus/packages/rebus-generator/src/rebus_generator/evaluation/datasets/build_curated.py:32>),
[prompt-evaluation builder](</Users/fabian/git/generator-rebus/packages/rebus-generator/src/rebus_generator/evaluation/prompt_eval.py:98>).

`propozitii-nostime`'s “DefinitionProvider” generates humorous templates by randomly
sampling words already filtered by database rarity. Its output is circular as
rarity evidence; it is not a dictionary-definition source or independent corpus.
[DefinitionProvider](</Users/fabian/git/propozitii-nostime/src/main/kotlin/scrabble/phrases/providers/DefinitionProvider.kt:13>).

No separate broad natural-language Romanian frequency corpus was identified in the
scoped local data inventory. This is a statement about the inspected workspaces,
not proof that no suitable file exists anywhere on the machine. Repeated exports,
compiled copies and cached benchmark runs are not independent corpora.


## What existing labels say about4 versus5

There are49 pilot forms without wordfreq:19 human4,19 human5,9 human3 and2 human2.
Only8 of those49 have clarified latest labels; the rest retain the original rubric.
Among the20 with rebus mentions,3 are human5; among29 without mentions,16 are5.
Absence is informative on this selected sample, but not decisive.

Reusing the already-frozen **group-held-out** predictions, with no new fit or tuning:

| Method, restricted to49 wordfreq-missing forms | MAE | Exact | Errors≥2 | Correct5 / predicted5 |
|---|---:|---:|---:|---:|
| Constant4 fallback |0.653|19|2|0/0|
| Median learned from the two presence bits |0.592|26|6|16/29|
| Ridge with numerical frequencies/missingness |0.694|19|4|0/4|
| Legacy snapshot |1.204|10|14|8/29|

The presence control finds16/19 human5 (84.2% recall), but only16/29 predictions5
are correct (55.2% precision). Its13 false5 comprise9 human4 and4 human3. It saves
only3 total absolute-error points while adding4 severe errors. On immutable first
responses, its median becomes4 for every missing form, giving exactly the same
0.653 MAE as constant4 and zero5 predictions. The latest-label improvement is not
stable across the preserved rating history.

Therefore neither absence-only rules nor the existing Ridge justify replacing the
fallback for rare-word discrimination. Page hints and richer lexical evidence need
a separate test; they have not been validated as predictors by this audit.

## Recommended improvement protocol

1. Preserve fallback4 as the operational default until an evaluated replacement
   improves it; keep complete coverage and the frozen baseline unchanged.
2. The first coverage table is now available. Next, build a uniform exact-sense extractor over the49 existing raw pilot snapshots and covered inventory pages: cross-entry definition
   mentions/document counts; exact-original cache coverage; sense-local usage tags;
   unresolved collision/redirect flags; LOC POS/paradigm evidence. No new LLM calls.
   Start with a small interpretable candidate (for example, a predeclared shallow
   median-leaf tree) rather than many ad-hoc thresholds. This is a candidate to
   evaluate, not an already-supported improvement. Preserve4 when evidence is
   absent/unresolved; missingness alone cannot justify promotion to5.
3. Separate positive lexical evidence from missing coverage. A page absent from a
   selected rebus cache is not evidence of5. A tagged obscure sense does not overrule
   another familiar valid sense. Technical, slang or regional usage is not inherently5.
4. Test a small fallback candidate against constant4 using the existing pilot,
   keeping feature extraction label-free and fitting/calibrating inside held-out
   folds. Keep all150 results and the49 wordfreq-missing slice; also report actual
   human4/5 confusion, level5 precision/recall and severe false5 assignments to1–3.
   Do not constrain all wordfreq-missing forms to4/5: some existing human ratings are
   lower, so a binary rule would introduce avoidable errors.
5. Preserve latest37/113 provenance strata and first-independent149 sensitivity.
   Use group-held-out validation as already established. Any feature/hyperparameter
   selection requires inner-fold fitting or an explicitly exploratory label; avoid
   selecting the best rule on the same held-out predictions and calling it validated.
6. Promote only if improvement survives those checks, coverage remains100%, and
   per-word reasons are inspectable. An unevaluated “tag→5” or “no mention→5” rule
   merely manufactures the missing class and is not an accuracy improvement.

This is a recommendation to extract/validate evidence, not evidence that any one
feature already solves4 versus5. The small existing labelled tail limits strong
claims. Full-inventory source coverage alone cannot establish predictive accuracy.


## Deliverables and verification

Audit artifacts: `build/d1/local-source-audit-2026-10-24/`.
`fallback-local-evidence.csv` is the combined deliverable, adding review-snapshot
paths and combined local-coverage flags. `fallback-evidence.csv` preserves the
underlying generator-cache audit for all66,088 IDs/POS with LOC, exact-query/lexeme
flags, ambiguity, mention counts and candidate usage hints; `inventory-evidence.csv`
contains all77,698 rows. `cache-metadata.json` retains lexical marker candidates;
`cache-ledger.csv` pins every source file. `pilot-fallback-evidence.csv` and
`pilot-fallback-diagnostic.json` separate existing labels from label-free extraction.
Scripts `audit.py`, `diagnostics.py` and `verify.py` reproduce the measurements.

Verified all77,698 identities and source flags,66088-row fallback membership,
64,226 unique fallback forms, summary arithmetic, corpus/input/artifact hashes,
all190 prior counts and original score immutability. Parser fixtures reject
navigation labels and etymology-only tags. Initial audit detected a one-span
count mismatch caused by dropping the corpus's empty structural span; preserving
it restored exact compatibility without changing any token frequencies.
Supplement input hashes, merged7375-page/18769-union row counts and all49 pilot
raw snapshots also verified. No classifier code/config or frozen scores changed;
no DB or D1 access.
