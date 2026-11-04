# Preflight real actualizat — 2026-11-04

**PASS:17/17 precondiții ale pachetului original satisfăcute.** Niciun blocaj tehnic
observat pentru instalarea structurală pe conexiunea Supabase verificată. Pachetul
nu a fost instalat; nu s-au modificat schema, rolurile, datele sau scorurile.
Zero apeluri LLM. Instalarea și apply rămân acțiuni separat instruite.

## Conexiunea și momentul observației

Proiect `propozitii-nostime` / `pdliedweugywbiczajxn`, ACTIVE_HEALTHY.
Conexiune reală prin Supabase MCP `execute_sql`; current_user=session_user=`postgres`,
bază `postgres`. PostgreSQL17.9, OrioleDB1.8, default access method `orioledb`.

- Precondiții: **2026-11-04 00:49:33 Europe/Bucharest** /2026-11-03T22:49:33Z.
- Lot și detalii: **00:50:38 Europe/Bucharest** /2026-11-03T22:50:38Z.
- Două tranzacții `BEGIN READ ONLY ... ROLLBACK`; ambele raportează read_only=on.
  SELECT-uri/cataloage și SET LOCAL; fără DDL/DML, LOCK TABLE, nextval sau executarea
  funcțiilor hook. Timeout30s pentru statement,2s pentru lock implicit al citirii.

Au rulat expresiile originale din `01-preflight.sql`, adăugând numai timestamp,
identitatea sesiunii și limitele temporare. `02-install.sql` nu a fost trimis DB-ului.
SHA-256 instalator neschimbat:
`7d61f282b0fb5cfc6fa1ff747b554e6e6e5d040e87900172e714193c3d9ab7a7`.

## Rezultate

| Verificare | Rezultat |
|---|---|
| Owner, motor, versiune și capabilități de creare |PASS|
| Inventar77.698, ID/grafie/POS/scor |SHA-256 identic snapshotului aprobat|
| RLS, politici, granturi words |Neschimbate|
| Cele9 hook-uri DDL, definiții/owneri/taguri |Neschimbate|
| Schema privată și executor |Încă absente, cum cere instalatorul|
| Triggere/rules words și default grants globale |Absente, cum cere instalatorul|
| Rânduri protejate citite individual |233/233 identice|
| Corecții necesare / rânduri deja corecte |165 /68|
| Politică umană și proveniență reverificate offline |PASS|
| Alte lock-uri pe words vizibile în a doua captură |0; nu rezervă o fereastră viitoare|

`postgres` are CREATEROLE/BYPASSRLS și CREATE pe DB/public, fără SUPERUSER.
RLS activ pe tabelă, neaplicat sesiunii prin BYPASSRLS. Apartenențele și rolurile API
au fost recitite fără parole/chei. Configurația de scheme expuse PostgREST nu este
vizibilă prin setarea sesiunii; izolarea viitoarei scheme private se verifică după
instalare. Nu pretindem audit complet al tuturor setărilor serviciului găzduit.

[Rezultate17checks](2026-11-04-production-preflight/checks.json) ·
[Raport agregat](2026-11-04-production-preflight/report.json) ·
[Verificare/replay](2026-11-04-production-preflight/verification.json).

## Ce certifică și ce nu certifică

Conexiunea MCP reală a fost verificată. `HUMAN_CORRECTIONS_DSN` nu este configurat
în proces; nu s-a inspectat niciun fișier de secrete și nu s-a încercat un DSN direct.
Această lipsă nu invalidează preflight-ul MCP, dar **nu certifică o altă conexiune**
care ar putea fi folosită ulterior pentru instalare sau aplicare.

Observațiile sunt punctuale, în două tranzacții, fără rezervarea configurației.
Instalatorul repetă precondițiile sub lock exclusiv. Nu am încercat acel lock sau
un DDL doar pentru a proba permisiunile. Egalitatea inventarului se referă la cele4
coloane fixate; nu dovedește egalitatea tuturor coloanelor sau absența ABA anterior.
Hash-ul tuturor coloanelor existente va fi verificat în tranzacția de instalare.

## Verificare și artefacte

**35 teste focalizate +70 subteste PASS**, pe pachet/acceptare/flux/adaptor/instalare.
Nicio modificare de runtime/SQL. Analiza salvată refuză conexiunile psycopg; validarea
scorurilor și politicii se execută offline, cu originalele intacte. Șase artefacte
reproduse identic octet cu octet; manifestele verificate; **7.124fișiere protejate
neschimbate**, inclusiv pachetul și repetiția OrioleDB. Nu s-a reluat suita server:
rezultatele12/12 rămân cele ale [repetiției precedente](2026-11-04-installation-rehearsal.md).

Capturi brute, SQL exact, comparație233CSV, audit, script de replay și manifest:
`/Users/fabian/git/word-rarity-classifier/build/d1/human-production-preflight-2026-11-04-refresh`.
Replay separat: `human-production-preflight-2026-11-04-replay` în același părinte.
Răspunsurile individuale și capturile brute rămân locale; numai agregatele intră în PR.
Pentru replay se copiază capturile/scriptul într-un director nou, fără directoarele
`guards`/`offline-preview`, apoi se rulează `PYTHONPATH=src <python> <director>/analyze.py`
din checkout. Acesta nu repetă SELECT-uri reale.

**Recomandare:** pachetul poate trece la instalare structurală explicit autorizată,
cu aceeași identitate de owner, fereastră pentru lock, repetarea preflight-ului și
verificările17înainte/16după. Lasă executorul NOLOGIN, fără aplicarea celor165 de scoruri.
Activarea/credentialele și apply165 se verifică și autorizează separat. Nu mai este
nevoie de modificarea pachetului, repetarea politicii sau evaluări noi pe baza
acestor rezultate. Orice drift ulterior oprește instalarea; baseline50.724 exclus.
