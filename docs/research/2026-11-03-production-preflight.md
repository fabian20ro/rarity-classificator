# Preflight read-only al mediului real — 2026-11-03

**Lotul este valid; execuția este blocată de incompatibilitatea cu OrioleDB.**
Cele165 de corecții sunt încă necesare. Toate233 de precondiții corespund, inclusiv
cele68 de rânduri deja corecte. Nu s-a instalat sau aplicat nimic. Zero apeluri LLM.

Actualizare ulterioară: [revizii explicite implementate și testate pe OrioleDB izolat](2026-11-03-orioledb-integration.md).
Constatările de mai jos descriu preflight-ul anterior adaptării. Mediul real încă
necesită instalare separat autorizată; nu s-a aplicat lotul.

## Constatarea care schimbă următorul pas

Proiectul `propozitii-nostime` (`pdliedweugywbiczajxn`) este ACTIVE_HEALTHY,
engine `17-oriole`, canal `preview`. SQL raportează PostgreSQL17.9, extensie
OrioleDB1.8; atât `public.words`, cât și `default_table_access_method` folosesc
`orioledb`. Versiunea PostgreSQL identică cu serverul izolat nu implică același
comportament de stocare.

Citirea reală a `xmin` a eșuat cu `XX000: orioledb tuples does not have system
attribute: xmin`. Eșecul a venit din SELECT într-o tranzacție READ ONLY; nu dintr-o
încercare de update. Adaptorul actual citește `xmin` în snapshot și îl folosește în
compare-and-set și rollback. **Nu este compatibil cu tabela reală.** Eliminarea
versiunii sau substituirea cu scor/hash ar pierde detectarea A→B→A.

Cele17 teste anterioare rămân valide pentru PostgreSQL heap; nu certifică OrioleDB.
Nici ledger-ul instalat singur nu rezolvă incompatibilitatea. SQL-ul existent nu
fixează access method, deci aici ar crea implicit și ledger-ul pe OrioleDB.
[Documentația Supabase confirmă acest default](https://supabase.com/docs/guides/database/orioledb).

## Roluri, RLS, structură și triggere

| Observație din catalog | Consecință pentru flux |
|---|---|
| Owner `postgres`; LOGIN și BYPASSRLS, fără SUPERUSER | Conexiunea MCP vede inventarul complet; nu dovedește funcționarea unui DSN dedicat |
| RLS activ, FORCE RLS dezactivat; o politică SELECT `TO public USING (true)` | Politica permite citirea numai împreună cu grantul SQL; nu există politică UPDATE |
| `anon`: SELECT, fără UPDATE; `authenticated`: fără SELECT/UPDATE pe words | Nu sunt roluri de execuție pentru corecții |
| `service_role`: SELECT/UPDATE și BYPASSRLS, dar NOLOGIN | Rol API; cheia API nu este un DSN PostgreSQL |
| Numai `postgres` și `supabase_admin` dintre rolurile LOGIN au SELECT+UPDATE+BYPASSRLS | Niciun executor dedicat identificat; nu reutilizăm implicit un rol administrativ |
| `classificator_private` și tabela recipiselor lipsesc | Nicio recipisă de apply a acestui flux poate fi verificată aici |
| Zero triggere pe words, zero reguli de rescriere, fără moștenire/partiții | Nu s-au găsit efecte DML suplimentare în aceste mecanisme |
| PK(id), CHECK rarity_level între1 și5, validate; fără FK către/din words | Identitatea și domeniul scorurilor sunt compatibile; toate11 indexurile sunt valide/ready |

`row_security_active('public.words')=false` pentru sesiunea MCP `postgres`, deși
RLS este activ pe tabelă. Au fost inspectate atributele, apartenențele de rol și
privilegiile efective, inclusiv coloanele folosite. Nu s-au citit parole sau chei.
`HUMAN_CORRECTIONS_DSN` nu este prezent în mediul procesului; nu s-au inspectat
secrete din fișiere și nu s-a încercat autentificare directă.

Există9 event triggers pentru DDL, distincte de triggerele DML ale words:
`ensure_rls` operează numai în `public`; watcher-ele PostgREST notifică schimbări
de schemă, cele GraphQL avansează un contor; restul gestionează extensii.
Definițiile au fost citite, fără executarea funcțiilor. Nu există default ACL global
pentru tabelele create de `postgres`; granturile largi observate sunt pentru scheme
specifice, inclusiv `public`, nu pentru viitoarea schemă privată. `ensure_rls` nu va
activa automat RLS în acea schemă. ACL/RLS și expunerea API a ledger-ului trebuie
verificate după o instalare autorizată; catalogul actual nu certifică un obiect absent.

## Cele165 de corecții

Snapshot read-only: **2026-11-03 04:27:49 UTC / 06:27:49 Europe/Bucharest**.
Metadatele au fost citite separat între04:26:00 și04:27:52 UTC; nu reprezintă o
singură tranzacție care rezervă configurația până la execuție.

| Verificare | Rezultat |
|---|---:|
| Inventar complet |77.698 rânduri, ID233095..310792|
| Identitate/grafie/POS/scor față de snapshotul aprobat din2026-11-02 |Amprentă SHA-256 identică|
| Referințe umane / rânduri protejate |200 /233|
| Precondiții încălcate, inclusiv apartenența completă a formelor |0|
| Corecții încă necesare / rânduri protejate deja corecte |165 /68|
| Rânduri păstrate de proiecția lotului |77.533|
| Politica umană, reverificată offline din sursele originale |PASS|
| Jaccard proiectat, față de original și starea curentă egală |96,459% PASS|
| Seed: apartenență / recall |4,770% /42,969%, diagnostic pentru fluxul uman|

Amprenta compară ordonat numeric `id, word, type, rarity_level`, delimitate prin
TAB și LF, codare UTF-8; absența acelor delimitatori și a CR este verificată în
ambele surse. Hash:
`0d69e5c92a45c52e85afe6fd903388009d408ebda54bb97c1d9818c0672f6fc0`.
Au fost citite direct și cele233 de rânduri protejate, comparate individual.
Egalitatea întregii proiecții permite refolosirea snapshotului fixat în verificatorul
existent de apartenență/POS. Nu pretindem descărcarea unui nou CSV integral sau
egalitatea celorlalte coloane. Aceleași valori nu exclud editări A→B→A anterioare.

Auditul de proveniență și preview-ul au fost rerulate fără store/DSN. Scorurile
umane, pachetul și pragurile sunt neschimbate; gate-ul legacy continuă să fie FAIL
din cauza ancorelor și rămâne obligatoriu pentru Step4 automat.

## Dovezi și verificare

[Raport agregat](2026-11-03-production-preflight/report.json).
Capturile, SQL-urile exacte, eroarea xmin, comparația CSV, preview-ul și manifestul
sunt locale în `build/d1/human-production-preflight-2026-11-03/`. Niciun răspuns
individual nou publicat în PR. Analiza offline este păstrată în `analyze.py` din
acel director; pentru replay se copiază capturile și scriptul într-un director nou,
alături de worktree, fără directoarele de output `guards`/`offline-preview`.
Rulare din worktree: `PYTHONPATH=src <python-din-venv> <director-nou>/analyze.py`.

Cinci încercări SQL, exclusiv `BEGIN READ ONLY; SELECT ...; ROLLBACK;`: patru
reușite și una care a descoperit lipsa xmin. Nici DDL/DML, nici LOCK TABLE/funcții
de scriere, nici apelul executorului apply/rollback. Cele6.117 fișiere protejate
au hashurile intacte. Verificare focalizată: **26 teste +66 subteste PASS** pentru
pachet, acceptare, flux și adaptor. Nu s-a schimbat codul de producție; testele
OrioleDB lipsesc încă. Nu s-a instalat/descarcat alt server în această etapă.
Replay offline:7 rezultate identice byte cu byte;33 hashuri de artefacte verificate.
SQL-urile de catalog sunt păstrate și lângă raportul agregat pentru repetare.

## Recomandare

**Următorul pas: compatibilitate OrioleDB cu TDD, exclusiv offline/izolat.** Mai întâi
un test care reproduce eroarea și un control de capabilități care refuză devreme
un storage engine nesuportat. Apoi proiectarea și testarea unei versiuni explicite
a rândului, independentă de xmin, actualizată pentru toate căile de scriere.

Recomandare de investigat: token de revizie unic, emis de DB prin secvență și trigger
la fiecare INSERT/UPDATE; permisiuni care împiedică reutilizarea tokenului. Trebuie
verificate inclusiv A→B→A, ștergere/reinserare cu același ID, scriitori din afara
classifierului, concurență, receipte și rollback. Un contor care se resetează la
reinserare, un timestamp sau hashul scorului nu sunt suficiente. Alegerea finală
necesită probe pe versiunea reală OrioleDB, nu doar mockuri sau PostgreSQL heap.

Acest mecanism ar necesita o migrare viitoare; **nu este aprobată sau aplicată prin
preflight**. Până atunci: fără instalarea ledger-ului și fără apply. După validarea
soluției: pregătire executor/granturi și ledger privat, instalare explicit autorizată,
preflight cu DSN-ul efectiv și revalidare în tranzacție înaintea unei aplicări separat
instruite. Politica umană este deja aprobată; nu cere o nouă rundă de etichetare.
Cele50.724 de schimbări baseline rămân excluse.
