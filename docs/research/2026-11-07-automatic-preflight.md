# Preflight automat real, read-only — 2026-11-07

**21/21 verificări PASS.** Inventarul și contractul de revizii sunt compatibile
cu pachetul acceptat. Putem pregăti instalarea minimă; fluxul automat **nu este
încă executabil** în producție: ledgerul și rolul dedicat lipsesc. Nicio instalare,
modificare DB, evaluare nouă sau cerere LLM în această etapă.

## Dovezi

Cinci tranzacții prin conexiunea Supabase MCP, fiecare explicit REPEATABLE READ,
READ ONLY, timeout statement30s/lock2s și ROLLBACK. Fiecare captură confirmă
read_only=on. Observații între 00:10:45 și 00:14:11 Europe/Bucharest,7noiembrie
(6noiembrie22:10:45–22:14:11UTC). SELECT-uri și SET LOCAL; fără nextval,
LOCK TABLE, DDL/DML sau executarea hook-urilor. Definițiile lor doar citite.

| Verificare | Rezultat |
|---|---|
| Inventar: ID, grafie exactă, POS, scor, revizie |77.698/77.698 identice snapshotului post-corecții|
| Evaluări protejate |233/233 rânduri identice,200forme|
| Recipisa corecțiilor umane |Identică integral;165corecții,stare applied|
| Contractul de revizii din adaptor |Valid;epoch neschimbat;secvență fără regres|
| RLS/politici words |RLS activ;politica neschimbată|
| Triggere/rules |Doar triggerul de revizie așteptat;fără rules/inheritance|
| Hook-uri DDL |9/9 definiții/owneri/taguri neschimbate|
| Indexuri |Toate valide și ready|
| Izolarea schemei private |Cele4roluri API verificate fără USAGE|
| Default grants globale/private pentru creator |Absente|
| Creator |Capabilități catalog necesare observate|
| Ledger/rol automat |Absente;instalarea rămâne de pregătit|

[Raport agregat cu21verificări](2026-11-07-automatic-preflight/report.json).
Acestea sunt verificări asupra capturilor, nu21teste noi de runtime.

Digestul folosește câmpuri UTF-8 precedate de lungimea în octeți și `:`, concatenate
în ordinea numerică a ID-ului. Python calculează din CSV, PostgreSQL independent
din inventarul live. Numărul rândurilor și absența NULL sunt verificate separat.
Aceeași metodă pe cele233ID-uri protejate. Validatorul contractului de revizii
folosește exact SELECT-ul și corpul funcției așteptate de adaptorul existent.
Comparația recipisei se face structural, inclusiv toate reviziile post-aplicare.

Capturile brute, SQL exact, așteptările și manifestul SHA-256 rămân local în
`build/d1/automatic-preflight-2026-11-07/`. `prepare.py` construiește SQL/așteptări
fără conexiune; `analyze.py` verifică răspunsurile salvate fără reinterogarea DB.
Replay din checkout: `../exact-form-code/.venv/bin/python
../automatic-preflight-2026-11-07/analyze.py`. Raportul reproducerii este identic.
Nu sunt publicate credențiale, răspunsuri individuale sau capturi de catalog.

## Recomandare și ce rămâne

1. Pachet de instalare versionat, cu precondiții repetate și verificări după:
   ledgerul automat separat USING heap, rol dedicat inițial NOLOGIN, granturi
   explicite și verificarea izolării. Refolosim schema și reviziile existente;
   nu reinstalăm fluxul uman. Pachetul trebuie repetat izolat înainte de utilizare.
2. Rolul automat are nevoie de USAGE privat, SELECT/UPDATE words la nivel de
   tabelă pentru lock, SELECT contract și SELECT/INSERT/UPDATE ledger automat.
   Adaptorul folosește row_security=off; acest SET nu acordă bypass. Rolul trebuie
   provisionat explicit cu BYPASSRLS, fără superuser/inherit/create/replication,
   cu ACL restrânse. Fără acces la ledgerul uman, secvență sau scrierea contractului.
3. Instalare separat autorizată; apoi conexiune dedicată verificată și dry-run.
4. Aplicare separat autorizată a celor50.724schimbări, cu verificare după commit,
   recipisă și rollback bazat pe reviziile efectiv scrise. Toate233rândurile umane
   rămân protejate. Acceptarea politicii există deja; nu cerem alte etichete.

Nicio incompatibilitate nouă observată. Nu schimbăm candidatul sau scorurile.
FAIL-urile Jaccard/ancore și precizia necunoscută a populației rămân vizibile,
conform politicii acceptate; preflight-ul operațional nu validează acuratețea.

## Limite

Capturi punctuale în tranzacții separate; nu rezervă starea sau o fereastră de
lock. Capabilități deduse din catalog, fără încercare DDL. Nu s-a verificat o
conexiune automată dedicată. Configurația schemelor expuse API nu este vizibilă în
setarea SQL; absența USAGE nu este un audit complet al serviciului găzduit.
Snapshotul arhivat fixează identitatea/POS/scorul/revizia, nu toate coloanele
auxiliare; acestea sunt protejate de fingerprint în tranzacția viitorului apply.

Nicio schimbare runtime/SQL în această etapă. Nu repetăm suita pentru documente:
1.003teste+479subteste și18/18integrări izolate rămân rezultatele commitului
7bd2b4a, documentate în [repetiție](2026-11-06-automatic-flow.md).
