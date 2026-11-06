# Instalare structurală automată reală — 2026-11-07

**Instalare comisă și verificată.** Confirmarea utilizatorului autorizează pasul
structural recomandat în etapa precedentă. Nu include activarea executorului sau
aplicarea scorurilor. Executorul nou rămâne **NOLOGIN**, ledgerul automat gol.

Executat exact pachetul repetat pe OrioleDB, fără modificarea SQL-ului:

- manifest SHA-256 `5c12270627b079aa7edfd8a392a315646401d4ec99287d54431b809d0dc8488b`;
- installer SHA-256 `bb6557c6d38132a429f080d66182c9d8507158552868dbd82721c7520f3d17cd`;
- commit implementare `c6a029b`, CI verde înaintea instalării.

Conexiunea Supabase verificată, proiect ACTIVE_HEALTHY. **28/28 precondiții PASS**
în tranzacție READ ONLY. Pachetul a fost executat o singură dată prin
`apply_migration`, cu numele `automatic_promotion_structural_installation_v1`;
intrarea în istoricul migrărilor confirmată. Tranzacția originală și limitele
lock5s/statement120s păstrate. Condițiile se repetă sub lock; nu s-au rulat separat
componentele SQL și nu s-a regenerat pachetul pentru a trece peste drift.

Recipisa înregistrează instalarea la **2026-11-07 01:12:21 Europe/Bucharest**
(2026-11-06T23:12:21Z). Postflight separat, după commit: **39/39 PASS**. O a treia
tranzacție READ ONLY confirmă recipisa, rolul și ledgerul la01:12:52 ora locală.

| Rezultat | Stare |
|---|---|
| Ledger automat și recipisă de instalare |Create, separate de fluxul uman|
| Executor |NOLOGIN,BYPASSRLS;fără SUPERUSER/INHERIT/CREATE/REPLICATION|
| Privilegii |Granturi explicite verificate;fără ledger uman/secvență/scriere contract|
| Inventar77.698rânduri |Identitate/POS/scor/revizie identice snapshotului aprobat|
| Toate coloanele words |Digest înainte=după,confirmat și după commit|
| Cele233rânduri evaluate |Păstrate integral|
| Recipise și granturi umane |Neschimbate|
| Revizii/epoch/secvență |Neschimbate|
| RLS/politici/hook-uri DDL |Neschimbate|
| Ledger automat |0recipise;niciun scor automat aplicat|
| Roluri API |Fără acces USAGE în schema privată|

[Verificările înainte/după](2026-11-07-automatic-production-installation/checks.json) ·
[Raport agregat](2026-11-07-automatic-production-installation/report.json).

Advisorul de securitate nu returnează constatări noi; aceleași5constatări existente
privind obiecte publice vizibile în GraphQL. Nu țin de noile tabele private și nu au
fost schimbate granturile aplicației. [Descrierea verificării Supabase](https://supabase.com/docs/guides/database/database-linter?lint=0026_pg_graphql_anon_table_exposed).
Rezultatul advisorului nu înlocuiește cele39verificări directe de catalog/date și
nu certifică întreaga configurație de expunere a API-ului găzduit.

## Evidență și recuperare

Capturi brute, răspunsul instalării, recipisa, SQL de verificare, istoric migrări,
advisor înainte/după și manifest local în
`build/d1/automatic-production-installation-2026-11-07/`.
`verify.py` reface analiza offline, fără conexiuni; raportul și verificările se
reproduc identic. Pachetul original și toate24artefactele sale rămân intacte.
În PR intră numai rezultate agregate; nu capturi operaționale sau date individuale.

**Nu reexecuta instalatorul:** obiectele există, iar recipisa și postcondițiile
confirmă commitul. Preflight-ul de instalare va refuza acum legitim condițiile
`*_absent`. Pentru inspecție înainte de activare se folosesc postflight-ul și
recipisa. Nu există dezinstalare automată; păstrează istoricul reviziilor/ledgerelor.

Nicio schimbare de runtime sau SQL în această etapă. Nu s-au repetat testele de
implementare fără motiv: rămân1.008teste+479subteste și20/20integrări din etapa
precedentă; aici validarea este pe mediul real. Fără cereri LLM, modele încărcate,
parole noi, evaluări sau aplicarea scorurilor.

**Pas următor:** activarea separat autorizată a executorului, credențiale dedicate
păstrate privat, conexiune verificată și dry-run offline. Abia apoi aplicarea separat
autorizată a celor50.724schimbări, cu verificare după commit și recipisă pentru rollback.
Politica acceptată și toate evaluările umane rămân neschimbate.
