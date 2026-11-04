# Integrarea fluxului uman pe PostgreSQL izolat — 2026-11-03

**17 teste de integrare trecute pe PostgreSQL17.9.** Inclusiv aplicarea celor165 de
corecții și rollback-ul lor pe copia completă a inventarului. **DB-ul proiectului
nu a fost accesat.** Nicio evaluare originală modificată și niciun apel LLM.

**Constatare ulterioară:** [preflight-ul real read-only](2026-11-03-production-preflight.md)
a identificat OrioleDB1.8, fără xmin pe words. Aceste teste validează PostgreSQL
heap, nu motorul real; instalarea/aplicarea rămân blocate până la adaptare.

## Mediu controlat și reproducere

Harness-ul pornește singur un server Docker nou, cu volum nou, identități aleatoare,
port publicat exclusiv pe127.0.0.1 și limită512MiB RAM. Nu acceptă un DSN extern și
nu citește credentialele aplicației. Imagine oficială PostgreSQL17.9 Alpine,
fixată prin digest:

```
postgres@sha256:c7526c0f6c3f30260a563d7bcf8ad778effac59a44f8ffa86678c35418338609
```

Imagine descărcată:109.303.511bytes (~104MiB). Rămâne cache reutilizabil. Containerul
și volumul fiecărei rulări sunt eliminate prin cleanup; verificat și prin inventarul
Docker după teste. Portul este explicit pentru durata containerului, inclusiv restart.
Datele inițiale sunt CSV-uri locale și fixtures; schema words minimă reproduce
ID/grafie/POS/scor, nu toate particularitățile DB-ului aplicației.

Pregătire o singură dată, dacă imaginea nu este în cache:

```sh
docker pull postgres@sha256:c7526c0f6c3f30260a563d7bcf8ad778effac59a44f8ffa86678c35418338609
```

Suită izolată, fără dependență de inventarul local complet:

```sh
python scripts/check_postgres.py --output /private/tmp/human-pg-integration-new
```

Cu cele165 corecții și sursele locale existente:

```sh
python scripts/check_postgres.py --full-inventory --output /Users/fabian/git/word-rarity-classifier/build/d1/human-pg-replay-new
```

Director nou obligatoriu. Scriptul nu schimbă niciun DSN de producție și nu aplică
schema în afara containerului său. Testele Docker sunt opt-in; verificarea obișnuită
`python scripts/check.py` rămâne offline. Configurația imaginii urmează
[documentația oficială](https://hub.docker.com/_/postgres).

## Ce am verificat pe server real

| Scenariu | Rezultat |
|---|---|
| Schema ledger, apply, retry, restart, rollback, retry rollback |PASS|
| Trigger words cu efect secundar |întreaga tranzacție anulată|
| Constraint trigger deferred cu eroare |întreaga tranzacție anulată|
| Eroare la salvarea recipisei |niciun scor sau ledger parțial|
| Trigger ledger care modifică words sau rescrie recipisa |detectat înainte de commit, rollback|
| Efect secundar ledger în timpul rollback-ului |anulat; recipisa rămâne applied|
| Writer concurent: POS nou sau modificare rând protejat |blocare observată prin pg_blocking_pids; drift ulterior respins|
| Două apply simultane pe același pachet |unul applied, unul already_applied|
| Editare A→B→A după apply |rollback respins prin xmin real|
| Rol cu RLS filtrant / acces insuficient la ledger |fail closed, fără modificări|
| Executor non-superuser cu BYPASSRLS și granturi explicite |apply trece, rândurile neatinse păstrate|
| Terminarea backend-ului înainte de commit |anulare reală și retry valid|
| ACK pierdut după commit real |recuperare din ledger, fără reaplicare|
| Pachet165 pe toate77.698rândurile |candidat exact, retry și inversă corecte|

ACK-ul post-commit este injectat ca excepție la limita transportului **după un commit
real**; nu este un experiment de pierdere fizică de pachete. Restart-ul este restart
Docker controlat; terminarea backend-ului înainte de commit este reală. Nu am testat
pană de curent, disc pierdut sau configurația de replicare/durabilitate a producției.

## Defect real găsit și corectat cu TDD

Verificarea post-state se făcea înainte de scrierea ledger-ului. Un trigger pe
ledger putea modifica inventarul sau recipisa ulterior, iar operația se confirma.
Am observat două teste RED pe server: `receipt_side_effect` și `receipt_rewrite`.

Corecție minimă: după salvarea recipisei, forțăm constrângerile restante, recitim
inventarul și recipisa și comparăm cu starea exactă verificată. Orice diferență
aruncă eroare în tranzacție. Aceeași protecție există pentru apply și rollback.
Adăugată regresie offline cu3 subcazuri; testele reale acoperă și rollback-ul.
**Nu am relaxat Jaccard, politica ancorelor sau gate-ul automat.**

## Lotul complet și verificarea finală

- PostgreSQL17.9 real: **17 teste PASS**, zero skip în rularea completă.
- Suita obișnuită: **977 teste +452 subteste PASS**,17 integrări skip implicit.
- Ruff PASS pentru cod, teste și runner.
- Inventar77.698rânduri: exact165modificări,77.533rânduri neatinse inclusiv versiuni;
  candidatul coincide cu exportul fixat.233precondiții și200referințe originale.
- Retry fără reaplicare; rollback reface toate valorile originale. Versiunile celor
  165rânduri se schimbă legitim în DB-ul temporar; identitatea/scorurile sunt restaurate.
- **4.885fișiere originale protejate intacte.** Schema ledger instalată numai în
  bazele temporare; containerul și volumul eliminate.

Rulare finală: `build/d1/human-postgres-integration-2026-11-03-verified/`, cu JUnit,
metadata server, raport, manifest și artefactele CSV. Recipisele de acolo aparțin
**bazelor temporare deja șterse**, nu proiectului; nu pot autoriza rollback în producție.
Publicăm în PR doar teste, cod, rezultate agregate și instrucțiuni, nu inventarul.

## Următorul pas

Integrarea izolată este încheiată. Recomandarea următoare: preflight read-only al
mediului real — roluri, RLS, triggere, disponibilitatea ledger-ului și concordanța
lotului. Schema reală poate avea comportamente inexistente în fixture.

Instalarea ledger-ului și aplicarea celor165 în DB-ul proiectului rămân acțiuni
separate, la instrucțiune explicită. Politica umană este deja aprobată; nu mai cerem
aceeași aprobare și nu solicităm noi evaluări. Cele50.724 modificări baseline
provizorii rămân excluse.

[Raport agregat](2026-11-03-postgres-integration/report.json) ·
[Decizie arhitecturală](../adr/2026-11-03-human-correction-flow.md) ·
[Plan actualizat](../plans/2026-10-30-1000-form-risk-review.md).
