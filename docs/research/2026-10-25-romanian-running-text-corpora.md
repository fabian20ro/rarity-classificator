# Romanian running-text sources for the missing-frequency inventory — 2026-10-25

Scope: 66,088 missing-wordfreq inventory rows / 64,226 exact forms. Read-only
investigation of primary sources and bounded public endpoints; no D1, database,
provider messaging, credentials or full corpus downloads. Access tests below were
performed on 2026-10-25. Availability, advertised licence and usable frequency
coverage are separate questions; no new coverage percentage is claimed here.

## Decision

**Next: a bounded FineWeb2 Romanian coverage experiment**, then at most one simple
fallback comparison. Keep frozen wordfreq→4 until evidence improves both error
severity and label-provenance strata. CoRoLa is the cheapest supplementary lookup
if its noncommercial terms fit the intended use. No additional human labels needed.
“Contemporary” does not mean live 2026 text: the preferred web snapshot ends in 2024.
Actual coverage of the 66,088 rows remains unmeasured in every newly investigated source.

## FineWeb2: first operational candidate

The official card describes cleaned, deduplicated Common Crawl text from summer
2013 through April 2024. Romanian configuration `ron_Latn` advertises about 35.0B
words / 58.3M documents. The train files expose text, source URL, crawl date and
language metadata. These enable source/date diagnostics; crawl dates do not establish
when articles were written. [Official dataset](https://huggingface.co/datasets/HuggingFaceFW/fineweb-2),
[publisher code](https://github.com/huggingface/fineweb-2).

Anonymous access **actually verified**: repository metadata 200 (`gated=false`),
Romanian file listing 200, first Parquet range 206 (4,096 bytes), one-row viewer 200.
Pinned revision `af9c13333eb981300149d5ca60a8e9d659b276b9`; 20 train shards total
91,670,592,103 bytes ≈85.37 GiB. First shard alone is 4.85 GB, so a small document
limit must not silently download it whole. The viewer's first Romanian row has a
2013 date: the recency of a first-prefix streaming sample cannot be assumed.
[Versioned file list](https://huggingface.co/datasets/HuggingFaceFW/fineweb-2/tree/af9c13333eb981300149d5ca60a8e9d659b276b9/data/ron_Latn/train).

Declared database licence: **ODC-By 1.0**, with Common Crawl terms also applying.
ODC attribution obligations and original content rights are separate; the database
licence does not grant blanket rights to republish every crawled article. Retain
attribution/notices and provenance; this proposal exports aggregate counts rather
than a new raw-text collection. [ODC-By terms](https://opendatacommons.org/licenses/by/1-0/),
[Common Crawl terms](https://commoncrawl.org/terms-of-use).

Inference: strongest accessible scale/metadata combination, but web boilerplate,
foreign-language contamination, dictionaries and domain concentration can inflate
counts. Deduplication also means counts measure this processed corpus, not unfiltered
web prevalence. Do not upweight documents by `minhash_cluster_size`.

## CoRoLa: strongest low-cost frequency candidate, restricted reuse

The official contemporary-Romanian reference corpus spans multiple genres and
provides a published frequency-list link. Its text spans 1989 onward and contains
both older and newer orthographic conventions; retain literal spelling under our
rubric rather than silently combining î/â variants. The search interface explicitly
prohibits downloading the corpus itself, partly or wholly. Query access is not bulk
redistribution permission. [CoRoLa](https://corola.racai.ro/),
[KorAP terms displayed at entry](https://korap.racai.ro/).

The separately released **CoRoLa Frequency Lists v1**, 2022-09-19, is downloadable.
The all-lowercase **word** list has 1,813,746 entries; choose it over lemma, ASCII-folded
or minimum 5/10-occurrence versions. The dataset excludes tokens containing digits
or special symbols; this creates a known token-policy boundary, not rarity evidence.
[Publisher's dataset record](https://zenodo.org/records/7091535).

Actual metadata API 200: licence `cc-by-nc-nd-4.0`; ZIP 114,091,202 bytes,
MD5 `0034d61d1825b38386dfa0bc2606a314`. Two bounded 206 range requests inspected the ZIP
central directory and first compressed block (81,920 bytes total). Member
`corola_word_freq_all_lowercase.tsv`: 10,128,887 compressed bytes / 23,732,979
uncompressed; plain token-TAB-count rows confirmed, with no lemma field.
[Metadata API](https://zenodo.org/api/records/7091535),
[published archive](https://zenodo.org/api/records/7091535/files/corola_frequencies.zip/content).

The declared licence requires attribution, limits use to noncommercial purposes,
and prohibits distributing adapted material. Do not assume that an app-facing
derived CSV or commercial integration is cleared merely because the aggregate
list is openly downloadable. Eligibility of the intended reuse needs clarification;
this investigation does not infer that all statistical outputs necessarily count
as adaptations. A separate appropriately scoped permission could resolve this.
No permission request was sent. [Official CC BY-NC-ND 4.0 terms](https://creativecommons.org/licenses/by-nc-nd/4.0/).

Inference: technically the cheapest direct test of the long tail, with much lower
RAM/storage requirements than web-corpus processing. It does not supply document
frequency, dated subcorpora or sense/POS-specific familiarity. Use only within the
applicable research-use terms; not an unrestricted replacement data dependency.

## Leipzig news: working frequency API; limited scale and unresolved archive terms

Official public API metadata returned 200. It lists one Romanian corpus,
`ron_news_2011_300K`: 300,000 sentences, 5,316,634 tokens, 240,135 types. One exact-word
probe returned 200 for `izotop`, frequency 1. This verifies access and a usable
count field, not inventory coverage. No 66k-query campaign was run.
[Official corpus list](https://api.wortschatz-leipzig.de/ws/corpora),
[word endpoint example](https://api.wortschatz-leipzig.de/ws/words/ron_news_2011_300K/word/izotop).

OpenAPI declares **CC BY 4.0** and links the terms-of-service page. However, official
usage/download pages currently returned an Anubis challenge in this environment;
the archive-specific current licence and bulk-download route were not verified.
Do not silently equate the API licence declaration with every historical corpus
archive's terms. No challenge bypass attempted.
[OpenAPI schema](https://api.wortschatz-leipzig.de/ws/v3/api-docs),
[official usage](https://wortschatz-leipzig.de/en/usage),
[downloads](https://wortschatz.uni-leipzig.de/en/download).

Inference: useful small news-domain comparator, not first choice for filling 64k
rare forms. 2011 is modern running text but not recent 2020s language. Prefer a
verified downloadable snapshot to tens of thousands of live queries, if its terms
and exact source can be confirmed.

## SETIMES v2: accessible Romanian news, narrower and duplication-sensitive

The OPUS publisher identifies SETIMES as Balkan news parallel text and advertises
**CC-BY-SA**. Romanian is included; the displayed en–ro alignment has about 213k
sentence pairs. The page does not identify a CC version in the inspected licence
label, so do not invent one. The original compiler URL was not successfully fetched.
[Official OPUS dataset](https://opus.nlpl.eu/datasets/SETIMES).

The official API returned the Romanian monolingual download, listing 1,812,594
sentence fragments, 46,753,269 tokens and 9 documents. Bounded 1 KiB download returned
206 with gzip magic; the archive is 97,888,697 bytes. These aggregate figures do not
establish unique Romanian text volume; parallel-pair exports can repeat the same
side. Inspect source-document structure and deduplicate before frequency estimation.
[Official query](https://opus.nlpl.eu/opusapi/?corpus=SETIMES&source=ro&preprocessing=mono&version=v2),
[Romanian archive](https://object.pouta.csc.fi/OPUS-SETIMES/v2/mono/ro.txt.gz),
[API documentation](https://opus.nlpl.eu/opusapi).

Inference: reasonable news-domain diagnostic, not a standalone general familiarity
reference. Translation and geopolitical-news selection bias matter. Preserve
attribution/share-alike obligations when redistributing applicable adaptations;
verify the exact licence before shipping derived resources.

## ParlaMint-RO: do not confuse project existence with a current full release

The Romanian project's official page remains marked work in progress and gives
session statistics, with source-code links. The corpus-builder is MIT-licensed
**code**; that is not evidence of a licence for the full underlying transcripts.
[Romanian project](https://romanian-parlamint.github.io/),
[corpus builder](https://github.com/romanian-parlamint/corpus-builder).

The current ParlaMint.ana 5.0 repository record (2025-07-08) is publicly downloadable
under CC BY 4.0, but its enumerated languages and full corpus archives do **not**
include Romanian. 4.1 similarly lacks Romanian. Older release sample archives contain
RO examples; they do not establish a complete Romanian downloadable corpus. Do not
recommend the 29-country 1.2B-word collection as if that size applied to Romanian.
[ParlaMint 5.0](https://www.clarin.si/repository/xmlui/handle/11356/2005),
[ParlaMint 4.1](https://www.clarin.si/repository/xmlui/handle/11356/1911),
[older sample listing](https://www.clarin.si/repository/xmlui/handle/11356/1405?show=full).

Inference: defer until a specific full RO release and transcript licence are located.
Even then, parliamentary language should be an auxiliary domain check, not sole
basis for everyday-word familiarity or 4/5 separation.

## Other candidates and access blockers

| Source | Access / terms verified | Decision |
|---|---|---|
| [CulturaX](https://huggingface.co/datasets/uonlp/CulturaX) | Login and acceptance/share-user-information gate; no acceptance made. Card inherits mC4/OSCAR terms, not a new uniform content licence. Romanian ≈40.3M documents. | Secondary option; not an immediate anonymous experiment. |
| [OSCAR-2301](https://huggingface.co/datasets/oscar-corpus/OSCAR-2301) | Official notice explicitly suspends access; manual gate will not grant access pending clarification. CC0 covers metadata/annotations only, not crawled text. | Unavailable now; no mirror workaround. |
| [CC-News](https://huggingface.co/datasets/stanford-oval/ccnews) | Public card documents multilingual yearly shards, 2016–June 2024, language filtering and Common Crawl terms. No Romanian-only dump or actual file transfer verified here. | News-domain follow-up; extraction cost and rights need a specific snapshot check. |
| [roTenTen21](https://www.sketchengine.eu/rotenten-romanian-corpus/) | Official description: ≈2.76B words, chiefly March 2021 crawl. Account/trial corpus tools; no public bulk licence/export rights verified. | Useful only if suitable access/export agreement already exists. |

The existing [wordfreq source table](https://github.com/rspeer/wordfreq/blob/master/README.md)
assigns Romanian Wikipedia, subtitles and OSCAR web data, but not its news source.
A different Common Crawl derivative is therefore **not automatically independent**
of wordfreq. News adds a domain, while a lower-cutoff web count can add rare-form
coverage. Neither creates independent gold labels or guarantees 4/5 separation.

### wROdfreq: relevant engineering, not a verified drop-in dataset

The project's own October 2026 documentation describes six domains, exact surface
counts, lemma aggregation and source-agreement measures. Its source table explicitly
leaves some redistribution terms unresolved. These are publisher claims, not an
accuracy validation. [Repository](https://github.com/gov2-ro/wrodfreq),
[source ledger](https://github.com/gov2-ro/wrodfreq/blob/main/docs/sources.md),
[method](https://github.com/gov2-ro/wrodfreq/blob/main/docs/method.md).

Actual GitHub API inspection: revision `ee8fe0a621cb6b0c338ef7115517514fd6ae349a`,
repository licence field null; no LICENSE file in returned tree. Packaged frequency
binaries are absent from that tree and configured as locally built/ignored assets.
No downloadable table was verified, and nothing was installed. Licence/data access
must be established before integration; use only exact-form mode if revisited.
The described tokenizer can split foreign accented words into fragments, which
conflicts with our exact-token policy. [Packaging configuration](https://github.com/gov2-ro/wrodfreq/blob/main/pyproject.toml).

Excluded false lead: [FineFreq](https://huggingface.co/datasets/lgi2p/finefreq)
counts **characters**, not words; unsuitable for this inventory.

## Experiment constraints carried forward

Start with a **coverage audit**, not another flexible classifier. Freeze source
version, licence record, hashes and token policy. Match the existing inventory with
NFC + cedilla-to-comma + casefold only; no lemmatization, accent folding or variant
substitution. Preserve every ID/POS row and report both 66,088-row and 64,226-form
coverage, including counts 1, 2–4, 5–9, 10+ and missing. Absence remains missing evidence.

Only after checking added coverage and source quality, compare one predeclared
wordfreq→new-source→4 fallback against frozen baseline behavior through existing
group-held-out evaluation. Refit any new thresholds inside each fold; report all 150,
missing 49, clarified 37 / opaque 113, first-independent 149 and full 4/5 confusion plus
false 5 on human 1–3. Do not tune multiple variants on the same held-out predictions.
A broader source can improve frequency coverage without improving familiarity.

## Proposed next experiment — not executed

1. **Freeze input and sampling policy before counts.** Pin FineWeb2 revision above,
   existing inventory/export hashes, tokenizer and exclusion list. Sequential range
   reads; maximum 100,000 examined documents or 1 GiB total transferred bytes,
   whichever comes first. Include metadata/failed reads in the byte budget. Sample
   row groups across all 20 shards with a fixed seed and saved selection manifest;
   record row-group sizes and selection probabilities. Counts describe the selected
   sample only; do not extrapolate whole-corpus frequencies without a justified
   probability design. Verify range/row-group feasibility before processing. Stop explicitly if the cap
   prevents balanced sampling, rather than silently substituting the first shard.
2. **Measure current-text support.** Report crawl-year strata; use 2020–2024 as the
   primary contemporary slice, older text as a separate diagnostic. Apply the budget
   before filtering, so retained sample size may be smaller. Remove duplicate text,
   declared dictionary/word-list sources and low-quality language records using
   frozen rules. Log exclusions. Do not select documents by human rarity labels.
3. **CSV-first evidence, complete target ledger.** Export every missing inventory
   row (66,088; 64,226 normalized forms), including zeros, plus all 150 pilot targets
   for calibration/controls. Fields: ID/form/POS, exact token count, document count,
   distinct host count, corpus token denominator, source/time slice, support status.
   Count all eligible text tokens in the denominator, not just Scrabble targets.
   Corpus counts pool observed surface uses, potentially including names, homographs
   and noise; they cannot alone prove which sense/POS
   is familiar. Keep that limitation explicit, without inventing POS disambiguation.
4. **Coverage gate before scoring.** Show new support by count bands and pilot
   level; inspect a bounded, label-blind concordance sample for false matches and
   dictionary contamination. Proposed support floor: ≥5 occurrences in ≥3 documents
   and ≥2 hosts, fixed before scoring. Document host count is only a coarse diversity
   proxy. If supported tail labels cannot fit useful thresholds within training
   folds, report insufficient evidence; do not relax the floor after seeing scores.
5. **One candidate, same folds.** Shared fold-fitted direct wordfreq path; supported
   missing forms use monotone thresholds on log normalized corpus frequency,
   learned within training groups only; unsupported/unseen forms remain 4. Compare
   with wordfreq→4 on all 150 and the strata above. Report 4/5 precision, recall,
   confusion and severe errors; first-independent labels are a sensitivity check,
   not a fresh untouched test set. No extra feature/tree search or invented labels.
6. **Decision.** No production promotion if first-independent performance or severe
   errors worsen. Improvement must not rely only on the latest mixed labels or
   tiny covered subset. If coverage is too sparse, decide whether a larger bounded
   sample is warranted from coverage curves, not by tuning to held-out labels.
   Unseen in any finite sample stays “unobserved”, never automatic 5.

Optional separate diagnostic: published CoRoLa complete word-form TSV, only if the
intended noncommercial analysis/use fits its terms. Preserve source identity and
report separately; do not merge counts with FineWeb2 under one denominator.

## Evidence and remaining work

Public endpoint receipts and bounded probe script:
`build/d1/romanian-corpora-research-2026-10-25/access-checks.json` and `probe.py`
(workspace-local artifacts, outside the implementation clone). Receipt SHA-256s
bind metadata, file lists, 4 KiB Parquet response and single-row preview. No full
corpus acquired. CoRoLa/Leipzig/SETIMES response observations are recorded above.

Remaining: implement/test bounded extractor, quantify actual exact-form coverage,
verify sample cleanliness/recency, run the predeclared comparison, and decide whether
any new evidence distinguishes 4 from 5. Source discovery alone resolves none of
those quality questions. Frozen scorer/config/export unchanged; no D1 or DB access.
