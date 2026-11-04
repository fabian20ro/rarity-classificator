# Lot separat:165corecții umane și rollback — 2026-11-02

**Pachet pregătit, neaplicat.**165corecții pe144forme,165rânduri inverse de rollback,
233precondiții pentru toate200formele evaluate. Cele68rânduri umane deja corecte
rămân protejate, dar nu intră în corecții sau rollback. Nicio schimbare baseline
provizorie nu este inclusă.61corecții au amplitudine≥2niveluri.

Folosește exclusiv snapshotul deja salvat la2026-11-02T20:32:03.276616Z. Nu am
recitit DB, invocat uploaderul, modificat scoruri originale sau apelat LLM/subagenți.

## Interfețe și validarea provenienței

Două limite CSV în `src/classificator/evaluation/human_corrections.py`:

- `prepare_human_corrections(plan_dir, human_export_dir, output_dir)` produce
  lotul, rollback-ul, precondițiile, referințele originale și manifestul cu hashes.
- `verify_correction_snapshot(package_dir, snapshot_csv, output_dir, phase=...)`
  verifică offline starea `before` sau `after`. Nu execută operații și nu verifică
  prospețimea live. `rollback` nu este o fază autorizabilă prin acest checker.

Pregătirea verifică manifestele existente, regenerează planul de migrare din
intrările fixate și compară hashes ale tuturor artefactelor. Reconciliază fiecare
referință cu răspunsul original `working_level`, nu se bazează numai pe flag-ul
`decision_source=human`. Nu acceptă rânduri omise, referințe inventate sau un plan
alterat căruia i-a fost recalculat numai hash-ul. Scorurile țintă trebuie să fie
exact cele umane, iar fiecare formă evaluată trebuie să fie reprezentată complet.

Ieșire atomică într-un director nou; fără suprascriere. `package_id` derivă din
versiunea politicii și manifestele intrărilor. Hashurile fixează datele folosite;
nu constituie semnătură/autorizare de execuție. Sursele originale rămân necesare
pentru verificarea completă a provenienței.

## Fișiere și precondiții

| Fișier | Conținut |
|---|---|
|`corrections.csv`|165ID-uri live, grafie/POS exacte, `expected_level`, `target_level`, chei de referințe și ID-uri originale|
|`rollback.csv`|Aceleași165ID-uri, `expected_level=target_level`, `restore_level=scorul anterior`|
|`preconditions.csv`|233ID-uri: identitate literală, forma normalizată, before/after, `will_change`, proveniență|
|`references.csv`|Cele200referințe originale, copiate identic|
|`policy.json`|`human-corrections-package-v1`, mod prepared_only, nicio autorizare apply/rollback|
|`summary.json`, `manifest.json`|Numărători, tranziții, hashes și implementare|

Precondițiile acoperă **toate rândurile tuturor celor200forme evaluate**, nu numai
cele144forme cu modificări. Checker-ul detectează rând dispărut, ID reutilizat,
grafie/POS schimbate, scor schimbat și ID/POS nou în aceeași formă, inclusiv duplicate
noi. Un rând uman deja corect care se schimbă între timp produce conflict. Formele
neevaluate sunt în afara acestor precondiții; o schimbare exclusiv la ele nu este
interpretată ca eșec al lotului uman. Gate-ul global rămâne separat și obligatoriu.

Înaintea unei eventuale execuții, identitățile, toate233scorurile și apartenența
la forme trebuie recitite/verificate tranzacțional, inclusiv protecție față de
schimbări concurente de apartenență. Aplicare atomică a tuturor corecțiilor sau
niciuneia; număr exact de rânduri afectate și recipisă de execuție confirmată.
Acestea sunt cerințe pentru un executor viitor, **nu capabilități implementate aici**.

**Rollback-ul nu se rulează doar pentru că există CSV-ul.** Este necesară dovada
că acest pachet a schimbat acele ID-uri, apoi verificarea identității și a stării
post-aplicare. Nu se restaurează automat rânduri cu conflicte sau rânduri care nu
apar în recipisa de execuție. Compararea nivelului curent nu detectează singură un
ciclu A→B→A și nu dovedește cine a scris valoarea. Nu există recipisă de apply în
această etapă; nici verificarea simulării `after` nu este o asemenea recipisă.

## Rezultate verificate offline

| Verificare | Rezultat |
|---|---:|
| Corecții / rollback |165 /165|
| Forme schimbate |144|
| Rânduri umane protejate |233|
| Rânduri umane deja corecte, neatinse |68|
| Referințe umane păstrate |200|
| Rânduri din inventar neatinse de simulare |77.533|
| Diferențe≥2 în lot |61|

Selecția celor165ID-uri a fost reconciliată independent cu planul complet și cu
referințele originale. Simularea scrie numai CSV-uri separate: aplică exact165valori
pe o copie, verifică toate233postcondițiile, apoi aplică inversa pe copie.
**CSV-ul restaurat este identic byte cu byte cu snapshotul original.** Aceasta
probează inversabilitatea datelor pregătite, nu execuția sau concurența în DB.

## Gate-ul nu este ocolit

Am evaluat gate-ul existent pe **întregul inventar simulat de77.698rânduri**,
cu165corecții și toate celelalte scoruri păstrate. Fără numitori restrânși artificial,
fără referință egală cu propunerea, fără schimbarea pragurilor sau ancorelor:

| Metrică după simulare | Rezultat | Prag | Stare |
|---|---:|---:|---|
| Jaccard L1 |96,459%|≥70%|PASS|
| Apartenență la seed |4,770%|≥80%|FAIL|
| Recall seed |42,969%|≥80%|FAIL|

L1ar avea1.264ID-uri,1.226în comun cu1.233din snapshot. Seed-ul ar avea55/128
ancore L1, față de54/128în snapshot. Raportul de apartenență scade ușor din cauza
numitorului mai mare; nu demonstrează că o corecție umană este greșită. Lista de
ancore rămâne pozitivă și incompletă. Blocarea legacy rămâne activă; **uploaderul
nu a fost invocat** în acest experiment.

Nu am folosit contractul complet de candidat pentru a forța uniformizarea POS la
formele neevaluate: lotul parțial lasă scorurile lor istorice intacte. Verificarea
celor200forme evaluate și gate-ul pe inventarul întreg au roluri separate.

## TDD, reproducere și limite

Cicluri RED→GREEN pe interfața CSV: extragere/rollback, plan/referințe alterate,
precondiții de stare. Regresii pentru aplicare/inversă pe copii, lipsa autorizării,
lot gol când toate scorurile umane sunt deja corecte, replay și refuz de suprascriere.
5teste noi+10subcazuri; **Ruff956teste+396subteste PASS**.

4.754fișiere protejate intacte;16artefacte de pachet/verificare identice la replay.
165ID-uri reconciliate independent,200referințe originale intacte. Procesele,
rețeaua și conexiunile DB sunt interzise în runner. Zero citiri/scrieri DB și LLM.

Reproducere în checkoutul PR, cu mediul Python existent și un director nou:

```sh
PYTHONPATH=src python docs/research/2026-11-02-human-corrections/run.py --base /Users/fabian/git/word-rarity-classifier/build/d1 --output /Users/fabian/git/word-rarity-classifier/build/d1/human-corrections-replay
```

Artefacte locale: `build/d1/human-corrections-2026-11-02/package/`, verificări
`check-before/`, `check-after/`, `check-restored/`, două CSV-uri explicit numite
`simulation-*`, raport și manifest. Ele nu sunt fișiere de upload. Publicăm în PR
codul, testele, politica și agregatele; evaluările individuale rămân locale.

## Următorul pas și leftovers

Lotul și rollback-ul sunt pregătite. **Următorul pas recomandat: stabilirea explicită
a politicii de acceptare pentru corecții umane**, cu criterii verificabile: exact
setul de ID-uri aprobat, scoruri exclusiv din referințe, nicio altă schimbare,
precondiții complete și dovezi separate de stabilitate/seed. Nu eliminăm și nu
relaxăm implicit gate-ul existent. Un executor sau o nouă politică de promovare
ar fi o etapă separată, cu teste și autorizare înainte de DB.

Rămân: verificarea live înainte de orice aplicare, concurența/tranzacția și recipisa
de execuție, politica de rollback după modificări ulterioare și blocajul legacy pe
ancore. Scorurile baseline provizorii și întregul lot de migrare nu sunt promovate.
Nu cerem alte evaluări și nu pornim experimente LLM.

[Raport](2026-11-02-human-corrections/report.json) ·
[Politică pregătire](2026-11-02-human-corrections/policy.json) ·
[Plan](../plans/2026-10-30-1000-form-risk-review.md).
