# Dry-run de migrare pe snapshot proaspăt — 2026-11-02

**Mapare completă, fără upload.** Candidatul conservator păstrează toate scorurile
sale originale și cele200evaluări umane. Comparat cu snapshotul proaspăt, ar
schimba50.889rânduri;6.664diferă cu≥2niveluri. Datele DB nu au fost modificate.

## Captură verificabilă

Proiectul Supabase conectat: `propozitii-nostime`. Pluginul a fost folosit pentru
identificare și două interogări SELECT: o verificare preliminară de dimensiune/ID-uri,
apoi captura completă într-o singură instrucțiune, fără paginare:

```sql
SELECT statement_timestamp() AS captured_at,
       current_database() AS database_name,
       current_setting('server_version') AS server_version,
       count(*) AS row_count,
       json_agg(json_build_array(id,word,type,rarity_level) ORDER BY id) AS rows
FROM public.words
```

Timestamp server: **2026-11-02 20:32:03.276616 UTC**,22:32în București. Snapshot:
77.698rânduri,ID-uri233.095–310.792,PostgreSQL17.9. JSON-ul original are2.084.739octeți;
numărul primit coincide cu `count(*)`, ID-uri distincte, niveluri1–5 și patru coloane.
SQL, timestamp, hashes JSON/CSV și metoda de captură sunt păstrate local.

O singură instrucțiune SELECT asigură aceeași vedere pentru agregatele capturii;
vezi [semantica PostgreSQL](https://www.postgresql.org/docs/17/sql-set-transaction.html).
Nu declarăm că sesiunea pluginului avea `transaction_read_only=on`: am trimis numai
SELECT-uri, fără DML/DDL sau acces la fișiere pe server. Nicio cheie/parolă în artefacte.
Restul execuției/replay-ului este offline, cu rețea/procese/conexiuni DB interzise.
Captura reprezintă acel moment; nu promite că DB nu se va schimba ulterior.

## Maparea: forma exactă + POS, nu offset de ID

Interfață nouă, testată TDD: `plan_migration(candidate_csv, snapshot_csv, output_dir)`.
Normalizare NFC/șț/casefold, fără restaurarea diacriticelor sau transfer de lemă.
Nu folosește egalitatea de ID și nu aplică offseturi din istoricul restaurărilor.

| Tip | Grupuri | Rânduri live |
|---|---:|---:|
| Perechi formă/POS unice |73.308|73.308|
| Duplicate cu scor propus echivalent |2.165|4.390|
| Total |75.473|77.698|
| Lipsă, POS diferit sau cardinalitate incompatibilă |0|0|

La duplicate, planul păstrează toate ID-urile sursă și live din grup. Nu pretinde
identitate individuală: fiecare membru primește aceeași propunere deja fixată pentru
forma exactă. Cardinalitățile trebuie să coincidă, iar scorul/sursa candidatului
să fie consistente peste toate POS-urile. O diferență de cardinalitate sau o
formă/POS lipsă ar izola întreg grupul, fără mapare parțială sau fallback tacit.

Pe73.308perechi unice, diferența de ID observată este+155.396. Este numai diagnostic,
nu regulă de migrare; vechiul+77.698ar fi greșit. Testul folosește și un ID reutilizat
pentru alt cuvânt, ca să împiedice revenirea la un join pe ID.

## Impactul propus

| Rezultat | Rânduri |
|---|---:|
| Ar rămâne identice |26.809|
| Ar schimba nivelul |50.889|
| Diferență≥2 |6.664|
| Rânduri cu prioritate umană |233|
| Dintre acestea, schimbări față de DB |165|
| Dintre acestea, diferență≥2 |61|

Cele165schimbări umane acoperă144forme; cele61diferențe mari,54forme. Toate200
referințele originale rămân intacte.61din6.664diferențe mari sunt pe rânduri umane,
restul6.603pe rânduri provizorii baseline. O diferență față de DB nu dovedește
singură eroarea DB sau corectitudinea candidatului.

| Nivel | Snapshot live | Propunere conservatoare |
|---|---:|---:|
|1|1.233|978|
|2|6.608|6.291|
|3|12.522|4.389|
|4|24.496|66.009|
|5|32.839|31|

Tranziția dominantă: **30.540rânduri5→4**:30.524din baseline/fallback și16corecții
umane. Componenta fallback nu dovedește reevaluarea cu o sursă mai bună. Candidatul poate
fi complet și reproductibil, dar diferențierea automată4/5 rămâne nevalidată.

## Audit versionat și blocare operațională

Am proiectat candidatul și referințele existente în universul ID-urilor live,
în CSV-uri separate doar pentru audit. Originalele nu sunt rescrise. Pentru o
referință umană aflată într-un grup duplicat, ID-ul reprezentativ este cel mai mic
ID live din aceeași pereche formă/POS; provenance păstrează ID-ul original și toți
membrii live. Aceasta reprezintă o evaluare pe formă, nu o identitate de rând ghicită.

Contractul `rarity-validation-audit-v1` confirmă200override-uri,74.947forme fără
referință umană și lipsa autorizării uploadului. Snapshotul live are296forme cu
niveluri diferite între ID-uri/POS, față de1.783în snapshotul vechi.

| Gate existent | Snapshot vechi | Snapshot proaspăt | Prag |
|---|---:|---:|---:|
| Jaccard L1 |3,235%|14,678%|≥70%|
| Apartenență la seed |8,219%|8,219%|≥80%|
| Recall seed |56,250%|56,250%|≥80%|

Jaccard are acum plafon79,319% și este fezabil matematic; problema cardinalității
vechi a dispărut, dar suprapunerea efectivă rămâne mică:283ID-uri comune din978și1.233.
Problema seed-ului incomplet rămâne. Nu s-au schimbat pragurile sau ancorele.

Entry-point-ul real Step4, cu gate-ul real și limitele DB/markere interzise, a
ridicat `Quality audit failed` înainte de orice efect extern. Fără raport upload,
fără markere, fără citire/scriere DB în replay. `plan.csv` folosește
`live_word_id`/`proposed_level`, nu schema de input a uploaderului. Proiecția de
audit nu este un release aprobat; nu este generat niciun script UPDATE.

## Fișiere, teste și reproducere

Director local: `build/d1/migration-dry-run-2026-11-02/`.

- `snapshot.json`: captura originală a SELECT-ului; datele individuale rămân locale.
- `analysis/plan/plan.csv`: propuneri pentru fiecare ID live, delta, sursa umană/baseline,
  ID-urile sursă și tipul mapării.
- `analysis/plan/level-conflicts.csv`:6.664diferențe≥2; nu sunt automat erori confirmate.
- `analysis/plan/mapping.csv`:75.473grupuri; `identity-issues.csv` este gol, cu header.
- `analysis/validation/`: contractul audit-only, metricile și proveniența proiecțiilor.
- `analysis/report.json`, `manifest.json`, `snapshot-provenance.json`: rezultate și hashes.

Reproducere offline, pe aceeași captură și într-un director nou:

```sh
PYTHONPATH=src python docs/research/2026-11-02-migration-dry-run/run.py --base /Users/fabian/git/word-rarity-classifier/build/d1 --snapshot /Users/fabian/git/word-rarity-classifier/build/d1/migration-dry-run-2026-11-02/snapshot.json --output /Users/fabian/git/word-rarity-classifier/build/d1/migration-dry-run-2026-11-02/replay
```

Captura live a fost făcută prin plugin, nu de runner; regenerarea nu recitește DB.
Un snapshot ulterior este un nou input și necesită propriile timestamp/hashuri.

TDD4teste noi+5subcazuri: ID reutilizat/diacritice/POS, grupuri duplicate echivalente,
cardinalități și POS incompatibile, scoruri/surse contradictorii, nivel invalid,
plan fără schimbări, intrări nemodificate, replay și refuz de suprascriere.
Ruff + **951teste,386subteste PASS**. Reconciliere separată a fiecărui ID live și
scor propus;13artefacte identice la replay; **4.729fișiere protejate intacte**.
Niciun apel LLM/subagent, nicio schimbare DB; numai cele două SELECT-uri de captură.

## Recomandare

**Nu recomand migrarea integrală acum.** Majoritatea schimbărilor provin din
înlocuirea scorurilor istorice cu fallback, fără dovadă nouă de familiaritate.

Următorul pas mai bine justificat: pregătirea unui lot separat pentru cele
**165corecții umane**, cu precondiții asupra identității și scorului live, diff și
rollback CSV. Politica de acceptare a unui asemenea lot trebuie stabilită explicit;
nu poate fi ocolit gate-ul existent prin micșorarea artificială a numitorilor sau
prin folosirea candidatului ca referință. În acest pas nu am pregătit SQL executabil
și nu am aplicat corecțiile. Restul50.724schimbări propuse rămân provizorii.

Leftovers: politica de promovare, prospețimea la momentul unui viitor upload,
precizie globală L1necunoscută și4/5nevalidat. Nu cerem alte evaluări utilizatorului
și nu pornim alte experimente LLM. Scopul următor este limitarea unei schimbări
justificate de evaluări existente, nu promovarea implicită a întregului fallback.

[Raport agregat](2026-11-02-migration-dry-run/report.json) ·
[Plan](../plans/2026-10-30-1000-form-risk-review.md).
