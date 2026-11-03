# Pachet de instalare pregătit offline — 2026-11-03

Actualizare2026-11-04: pachetul original a trecut repetiția izolată; [12 teste și limite](2026-11-04-installation-rehearsal.md). Textul de mai jos păstrează starea istorică a pregătirii offline.

**Pregătit; neinstalat.** Generatorul fixează reviziile, ledger-ul, executorul și
verificările într-un singur pachet. Niciun apel DB/LLM, nicio instalare sau modificare
scoruri în această etapă. Politica umană aprobată rămâne intactă; pregătirea nu
activează executarea celor165 de corecții.

## Conținut și limite

- [Preflight](2026-11-03-installation-package/01-preflight.sql):17 verificări read-only.
- [Instalare](2026-11-03-installation-package/02-install.sql): o tranzacție, lock exclusiv,
  repetarea precondițiilor sub lock, ledger +revizii +rol/granturi, recipisă privată.
- [Postflight](2026-11-03-installation-package/03-postflight.sql):16 verificări read-only.
- [Runbook](2026-11-03-installation-package/README.md),
  [raport](2026-11-03-installation-package/report.json),
  [verificare/hash-uri](2026-11-03-installation-package/verification.json).
- Local: copiile CSV originale preconditions/corrections/rollback/references, auditul
  politicii și manifestul SHA-256 al intrărilor, implementării și fiecărui artefact.
  Datele individuale nu sunt publicate în PR.

Țintă: `pdliedweugywbiczajxn`, PostgreSQL17.9/OrioleDB1.8,77.698rânduri.
Captura reală folosită:2026-11-03T04:27:49Z; nu a fost recitită DB acum.
Proiecția ID/grafie/POS/scor este legată de snapshotul aprobat prin SHA-256
`0d69e5c92a45c52e85afe6fd903388009d408ebda54bb97c1d9818c0672f6fc0`.
O captură alterată sau incompatibilă este refuzată înaintea generării.
Identitatea proiectului/conexiunii trebuie verificată separat: o clonă poate avea
aceeași amprentă. La execuția viitoare, orice drift verificat blochează instalarea.

Preflight-ul verifică proprietarul/capabilitățile, motorul/versiunea, inventarul,
absența schemei/rolului/triggerelor, RLS/politicile, ACL-urile și cele9 hook-uri DDL.
Respinge granturi implicite globale ale instalatorului. Postflight-ul verifică și
reviziile unice, triggerul ALWAYS, secvența, ledger-ul gol, rolul/granturile,
izolarea față de rolurile API și recipisa legată de pachet/UUID-ul instalării.

Bootstrap-ul atribuie tokenuri tuturor rândurilor; nu aplică scorurile umane.
În aceeași tranzacție se compară hash-ul **tuturor coloanelor existente**, excluzând
numai noua revizie. Verificările finale se repetă după ultima scriere în recipisa de
instalare. Lock timeout5s, statement timeout120s: limite conservatoare, încă
nemăsurate pentru wrapper-ul complet. Instalarea poate eșua sigur prin timeout.

## Executor și recuperare

`classificator_human_executor`: NOLOGIN, fără parolă, BYPASSRLS, NOINHERIT,
fără SUPERUSER/CREATEDB/CREATEROLE/REPLICATION. USAGE pe scheme; SELECT/UPDATE words;
SELECT contract; SELECT/INSERT/UPDATE ledger. Fără granturi pe secvență, DDL sau
scrierea contractului. UPDATE words este necesar și pentru operațiile de blocare
ale executorului; rolul rămâne un backend privilegiat, nu un rol API.

Nicio apartenență la roluri API. PostgreSQL17 poate acorda automat creatorului
non-superuser apartenență ADMIN la rolul creat; verificarea permite numai această
apartenență pentru postgres, fără INHERIT/SET. `createrole_self_grant=''` previne
activarea suplimentară a acestor drepturi.
[CREATE ROLE](https://www.postgresql.org/docs/17/sql-createrole.html) și
[configurația clientului](https://www.postgresql.org/docs/17/runtime-config-client.html)
fundamentează acest tratament; comportamentul wrapper-ului rămâne de probat izolat.

Prima eroare anulează tranzacția; clientul trebuie să oprească execuția
(`psql -X --set=ON_ERROR_STOP=1`). Lipsa confirmării COMMIT nu dovedește rollback:
se inspectează read-only recipisa +postcheck-urile. Nu există DROP/uninstall automat,
reparare sau reluare peste o schemă existentă. `rollback.csv` inversează numai
corecțiile viitoare, nu instalarea structurală. Hook-urile DDL pot avansa contoare
auxiliare chiar dacă tranzacția eșuează. Administratorii/restore rămân de încredere.
Activarea loginului, credentialele, DSN-ul și aplicarea sunt etape separate.

## Scriitori existenți: audit local

Scanate surse kt/sql/py/ts/js/java din classifier, propozitii-nostime,
generator-rebus și shared-api-host. Nu s-a găsit `INSERT INTO words VALUES` pozițional.
[Proveniență](2026-11-03-installation-package/writer-audit.json).

`propozitii-nostime/src/main/kotlin/scrabble/phrases/tools/LoadDictionary.kt:68`
folosește lista explicită de coloane: noua coloană nu deplasează valorile INSERT.
Loader-ul face însă **TRUNCATE +reîncărcare**, apoi restaurează scoruri prin
word/type/gender. Poate schimba ID-urile și apartenența lotului: impune reconcilierea
pachetului/recipiselor înaintea unei aplicări sau anulări ulterioare. Secvența nouă
nu este OWNED BY words și nu trebuie resetată. Compatibilitatea INSERT și păstrarea
istoricului sunt concluzii din surse, nu un test executat al loader-ului.
Sursele locale nu certifică toate joburile externe sau versiunile deployate.

## TDD și verificare

**6 teste noi PASS** la interfața pachetului. RED→GREEN observat pentru modulul
absent, artefact suplimentar neînregistrat, contractul verificărilor incomplet și
lipsa reverificării după ultima scriere. Teste suplimentare: captură alterată,
inventar incompatibil chiar după refacerea hash-ului, SQL modificat, output existent,
replay determinist. Generarea este exercitată cu conexiunea psycopg interzisă.

Ruff și suita offline: **986 teste +456 subteste PASS**,28 integrări skip implicit.
Două generări reale:9 artefacte principale identice octet cu octet; manifestele
verificate;6.151fișiere originale protejate intacte. Manifestul detectează modificări,
nu reprezintă semnătură criptografică sau autorizare.

**SQL-ul asamblat nu a fost executat ori validat de parserul PostgreSQL în această
etapă.** Cele28 teste OrioleDB și17 heap din etapa anterioară validează componentele
și fluxul, nu noua tranzacție completă cu rol/granturi și hook-uri găzduite.

## Reproducere și artefact local

Din checkout-ul sursă, cu mediul Python existent și intrările locale fixate:

```sh
PYTHONPATH=src python -m classificator.human_installation \
  --approval docs/research/2026-11-03-human-flow/approval.json \
  --policy docs/research/2026-11-03-human-acceptance/policy.json \
  --preflight-manifest ../human-production-preflight-2026-11-03/manifest.json \
  --output <director-nou>
```

Verificare offline: `classificator.human_installation.verify_installation_bundle(path)`.
Pachet verificat:
`/Users/fabian/git/word-rarity-classifier/build/d1/human-installation-2026-11-03/verified`.
Arhivă: același părinte, `human-installation-review.zip`.
SHA-256 ZIP: `380d14666afcac4fdb7985a983438174741ac40675eb16c8e003b9cb195474b0`.
Fișierele SQL publicate sunt copii de review; pachetul complet verificabil rămâne local.

**Următorul pas:** repetiție a întregului pachet într-un OrioleDB izolat, cu creator
non-superuser, roluri/granturi, DDL hooks reprezentative, inventarul complet, eșecuri
și verificări înainte/după. Abia apoi instalare reală la instrucțiune explicită,
preflight cu DSN-ul efectiv și aplicare165 autorizată separat. Fără evaluări noi;
50.724schimbări baseline rămân excluse; gate-urile automate intacte.
