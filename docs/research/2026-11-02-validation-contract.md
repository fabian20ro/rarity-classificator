# Contract de validare versionat, audit-only — 2026-11-02

Implementat `rarity-validation-audit-v1`: prima schemă explicit versionată pentru
validarea surselor și raportarea separată. Nu înlocuiește gate-ul existent, nu
produce scoruri noi și nu poate autoriza uploadul. Funcție publică:
`audit_validation_contract(contract_path, output_dir)` în
`src/classificator/evaluation/validation_contract.py`.

## Contract și arhitectură

O singură limită publică: manifest JSON + CSV-uri originale → CSV-uri diagnostice,
raport JSON și manifest cu hashes. Refolosește citirea/normalizarea/metricile
existente; fără framework de politici, transport LLM sau integrare în Step4.
Se păstrează separarea dintre audit și efectele operaționale.

Schema cere exact câmpurile documentate; versiuni/moduri necunoscute sunt respinse.
Configurația reală este în [contract.json](2026-11-02-validation-contract/contract.json).

| Element | Câmpuri / semnificație |
|---|---|
| Rădăcină |`schema`, `mode="audit"`, `as_of`, `inventory`, `legacy_thresholds`, `references`, `candidates`|
| Inventar |`path`, `sha256`; CSV `word_id,word,type`, toate ID-urile unice|
| Orice sursă |`id`, `role`, `unit`, `path`, `sha256`, `universe_sha256`, `recorded_on`, `provenance`|
| Snapshot istoric |`historical_snapshot`, `inventory_id`, `level_column`; acoperire completă și POS verificat|
| Seed pozitiv |`positive_seed`, `exact_form`; text un cuvânt/linie, comentarii și duplicate ignorate|
| Etichete umane |`human_labels`, `exact_form`, `level_column`, `selection`: development/risk_selected/unspecified|
| Candidat |`candidate`, `exact_form`, `level_column`, `label_use` pentru fiecare sursă umană: fit/override/none/unknown|

`universe_sha256` fixează inventarul cu care sursa a fost aliniată; nu pretinde
că un seed sau un subset uman acoperă tot inventarul. `recorded_on=null` este permis
numai ca dată necunoscută explicită, cu diagnostic; nu inventăm data seed-ului.
Datele viitoare față de `as_of` sunt respinse. Proveniența și reutilizarea etichetelor
sunt declarații explicite ale manifestului; hashes verifică integritatea fișierelor,
nu pot demonstra singure cine a adnotat sau antrenat un model.

`legacy_thresholds` păstrează cele trei valori70%/80%/80%. Auditul diagnostichează
plafoanele imposibile pentru Jaccard/apartenența la seed și recall sub prag.
Nu rescrie pragurile uploaderului și nu transformă apartenența la seed în precizie
semantică. Nu aplică o limită arbitrară de vechime; orice snapshot istoric este
marcat ca atare, iar data sa este vizibilă în manifest.

Erorile de structură/integritate opresc publicarea: hash/univers/ID/grafie/POS
incompatibile, inventar sau candidat incomplet, scor în afara1–5, candidate cu
niveluri diferite între POS ale aceleiași forme, seed în afara inventarului,
etichete umane contradictorii. Nu se remapează ID-uri și nu se restaurează diacritice.
Referințe consistente pentru aceeași formă se numără o dată în cohorta respectivă.

Publicare atomică într-un director nou; refuz de suprascriere. Intrările și manifestul
sunt verificate din nou înaintea publicării; exportul păstrează hashes pentru
implementare și surse. Nicio referință umană nu este modificată.

## Metrici cu semnificație și numitori expliciți

- **Istoric:** Jaccard pe ID-uri, intersecție, cardinalități și plafon matematic;
  inconsistențele de scor între ID-urile aceleiași forme sunt raportate separat.
- **Seed pozitiv:** recall, acord±1 și abateri≥2 față de presupunerea seed L1.
  `membership_ratio` păstrează formula legacy pentru comparație;
  `semantic_precision=null`, fiindcă neapartenența la seed nu este etichetă negativă.
- **Evaluări umane:** o formă exactă peste toate POS-urile, erori≥2, cost suplimentar,
  MAE, matrice și rezultate pe fiecare clasă, inclusiv4/5; loturile150/50 separate.
  Precizie/recall L1 numai pe formele etichetate, numitorii și acoperirea lor explicite.
- **Reutilizare:** `fit` → training_fit_not_validation; `override` →
  integrity_only_not_accuracy; `none` → selected_cohort_not_population;
  `unknown` → unknown_reuse_not_validation. Un override încălcat produce diagnostic
  explicit; un override corect nu devine dovadă de acuratețe independentă.
- Numitor zero → `null`, nici0fals, nici1artificial. Raportul nu are `passed` global:
  mereu `status=audit_only`, `upload_authorized=false`, `population_accuracy=null`,
  inclusiv într-un test cu toate metricile observate perfecte.

## Rezultate pe datele existente

77.698ID-uri,75.147forme;200forme etichetate,74.947necunoscute.400comparații umane
(baseline+candidat) reconciliate cu CSV-urile originale.125/128ancore sunt la cel
mult un nivel distanță în ambele variante;3au abatere≥2. Recall exact71/128baseline,
72/128conservator. Jaccard și plafoanele reproduse identic cu auditul precedent.
17diagnostice explicite, inclusiv data seed necunoscută,1.783forme istorice cu
scoruri diferite, praguri imposibile și reutilizarea etichetelor.

| Scor / cohortă | Erori≥2 | Cost | Interpretare |
|---|---:|---:|---|
| Baseline fitted /150 |10|13|Calibrare pe aceleași etichete; nu OOF|
| Baseline /50 |13|14|Cohortă selectată după risc; nu estimare globală|
| Conservator /150 |0|0|Integritate prin override|
| Conservator /50 |0|0|Integritate prin override|

Pe4/5, baseline: pilot2/21 și3/22 severe; runda50:0/9 și1/6. Scorurile și rezultatele
anterioare nu s-au îmbunătățit prin introducerea raportului.

**Acoperirea L1 explică de ce nu putem certifica precizia globală:** pilotul are
45predicții baseline L1, dintre care38etichetate1:84,44%precizie pe acest subset,
recall38/51=74,51%. Dar subsetul acoperă numai45/870=5,17%din L1 și a fost folosit
la fitting. Runda50nu are nici predicții, nici etichete1; precizia/recall sunt `null`.
Conservatorul are51/51corecte prin override, dar numai51/876=5,82%L1etichetate.
**825forme L1 rămân fără referință umană în ambele variante.** Nu se deduce că sunt
incorecte; precizia populațională rămâne necunoscută.

## Blocarea uploadului verificată efectiv

Runner-ul a apelat `run_step4` cu candidatul real și gate-ul real, în modul implicit
partial. Singurele limite înlocuite sunt efectele externe: obiectele WordStore și
marker writer care eșuează dacă sunt accesate, plus interdicții proces/rețea/DB.
În ambele cazuri gate-ul ridică `Quality audit failed` înainte de accesarea lor:

| Candidat | Jaccard | Apartenență seed | Recall | Upload |
|---|---:|---:|---:|---|
| Baseline |3,180%|8,161%|55,469%|BLOCAT|
| Conservator |3,235%|8,219%|56,250%|BLOCAT|

Nici fișier de raport upload, nici marker, nici citire/scriere DB. Fișierele gate-ului,
ancorelor și scorurilor au aceleași hashes. Audit-only nu este o cale alternativă
pentru upload și nu este consumat de uploaderul existent.

## TDD și reproducere

Șapte teste noi pe limita CSV convenită; cicluri RED→GREEN observate pentru roluri,
metrici umane, preflight manifest, identitate/POS/referințe contradictorii, reutilizare,
L1gol și raportul CSV.18subcazuri negative. Testul cu metrici perfecte verifică
lipsa autorizării; replay și refuz de suprascriere păstrează intrările intacte.

Ruff + **947teste și381subteste PASS**. Revizie locală fără subagenți. Pe datele reale:
**4.718fișiere protejate intacte**,7artefacte identice byte cu byte la replay,
metrici comparate cu auditul independent anterior și400rânduri umane reconciliate;
zero apeluri LLM, acces DB sau descărcări.

Din checkoutul PR, folosind mediul Python al proiectului și un director nou:

```sh
PYTHONPATH=src python docs/research/2026-11-02-validation-contract/run.py --base /Users/fabian/git/word-rarity-classifier/build/d1 --output /Users/fabian/git/word-rarity-classifier/build/d1/validation-contract-replay
```

Pentru alte CSV-uri deja disponibile, interfața reutilizabilă primește un manifest
cu aceeași schemă; runner-ul de mai sus fixează sursele acestui experiment.
Artefactele locale: `audit/drift.csv`, `seed-comparison.csv`, `human-comparison.csv`,
`findings.csv`, `contract.json`, `report.json`, `manifest.json`, plus recipisa de
verificare. CSV-urile individuale rămân locale; în PR intră codul, testele,
contractul/proveniența și agregatele.

## Recomandare și ce rămâne

Păstrăm exportul conservator și contractul audit-only. Nu recalibrăm după raport și
nu mai cerem evaluări utilizatorului. Implementarea contractului este încheiată;
nu o confundăm cu adoptarea unei politici noi de upload.

**Următorul pas util: dry-run de migrare pe un snapshot proaspăt, obținut doar prin
citire**, cu proveniență și verificarea tuturor ID-urilor/grafiilor/POS; produce un
plan CSV al diferențelor și conflictelor, fără update, fără aplicarea automată a
vechii deplasări de ID și fără ocolirea gate-ului. Ar clarifica starea curentă și
amploarea schimbării propuse. Nu executăm acest acces în etapa de față.

Înaintea promovării rămâne necesară o politică explicită de acceptare compatibilă
cu obiectivul≥2 și rolurile surselor. Un snapshot nou nu este etalon uman. Precizia
globală L1, cele825L1neetichetate și discriminarea automată4/5 rămân nevalidate;
nu există justificare pentru ridicarea automată a blocării uploadului.

[Raport](2026-11-02-validation-contract/report.json) ·
[Verificare](2026-11-02-validation-contract/verification.json) ·
[Plan](../plans/2026-10-30-1000-form-risk-review.md).
