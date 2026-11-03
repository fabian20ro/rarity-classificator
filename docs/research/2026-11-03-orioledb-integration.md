# Revizii explicite și rollback pe OrioleDB — 2026-11-03

**Implementat cu TDD;28 teste OrioleDB1.8 trecute, inclusiv lotul165 pe77.698 de
rânduri.** Compatibilitatea este verificată într-un server izolat. DB-ul proiectului
nu a fost accesat; nicio instalare reală, modificare a evaluărilor sau apel LLM.

## Implementare

Interfețele rămân `run_human_corrections(...)` și `PostgresHumanStore.transaction()`.
Complexitatea SQL rămâne în adaptor; nicio modificare WordStore/Step4/Step5 sau
ocolire generică a gate-urilor. CSV-urile, politica și aprobarea fixată rămân valabile.

- Detectare access method. Heap păstrează xmin; OrioleDB cere contractul explicit
  instalat. Un motor necunoscut sau OrioleDB neconfigurat este refuzat înainte de
  snapshot/update. CLI-ul nu instalează nimic și rămâne dry-run implicit.
- Coloana `classificator_revision`, bigint pozitiv și unic, primește un token nou
  dintr-o secvență NO CYCLE/CACHE1 la **fiecare INSERT și UPDATE**, chiar dacă scorul
  nu se schimbă. Triggerul BEFORE ROW este ENABLE ALWAYS și suprascrie tokenurile
  furnizate de apelant. Ștergerea/reinserarea unui ID primește alt token.
- Funcție SECURITY DEFINER în schema privată, cu search_path fix și secvență
  calificată complet. Scriitorii obișnuiți nu primesc acces la secvență, funcție,
  contract sau DDL. Funcția și secvența trebuie să aparțină owner-ului words.
- Contractul are un UUID de instalare, păstrat într-o tabelă privată heap.
  Recipisa înregistrează `row_version_contract={kind: sequence-v1, epoch: ...}`.
  Retry/rollback refuză altă instalare sau interpretarea reviziilor ca xmin.
  Recipisele vechi fără acest câmp sunt acceptate numai în modul heap/xmin.
- Adaptorul verifică tipul/NOT NULL al coloanei, triggerul, corpul și owner-ul
  funcției, search_path și parametrii secvenței. Alte triggere BEFORE ROW pentru
  INSERT/UPDATE sunt refuzate: ar putea suprascrie tokenul. Contractul este
  reverificat la fiecare snapshot, inclusiv după scrierea recipisei.
- CAS și rollback folosesc tokenul salvat; păstrează toate233 de precondiții,
  apartenența/POS, lock-urile și verificarea completă după ultima scriere.
  Limita de vârstă a tranzacției rămâne pentru xmin; nu se aplică tokenului bigint
  care nu se reciclează. Epuizarea secvenței produce eroare, nu reutilizare.

## TDD și verificare

RED observat înaintea corecțiilor: motorul nesuportat ajungea la apelant; apply pe
OrioleDB era refuzat; schimbarea epoch-ului permitea rollback; triggerele dezactivate
sau concurente nu erau refuzate anticipat; triggerul ledger putea modifica epoch-ul
după verificarea inițială. Implementarea minimă a făcut aceste cazuri GREEN.

| Verificare | Rezultat |
|---|---:|
| PostgreSQL17.9 +OrioleDB1.8, inclusiv inventar complet |28/28 PASS|
| PostgreSQL17.9 heap, regresie completă |17 PASS;11 cazuri exclusiv OrioleDB skip|
| Suită offline +Ruff |980 teste +456 subteste PASS;28 integrări skip implicit|
| Corecții / rânduri cu scor păstrat |165 /77.533|
| Apply vs candidatul fixat / rollback vs snapshot |Identice|
| Retry și restart |Fără reaplicare|
| Fișiere originale protejate |6.151 intacte în fiecare rulare completă|

Teste reale: xmin indisponibil, rol fără privilegii, RLS, executor non-superuser cu
BYPASSRLS, scriitor extern fără acces la schema privată, token furnizat manual,
same-score/ABA/delete-reinsert, două apply concurente, blocarea scriitorilor,
triggere/deferred constraints, recipisă alterată, deconectare înainte de commit și
reluare după ACK pierdut. ACK-ul este simulat după un commit real; nu este un test
de întrerupere fizică a rețelei/discului. Modificarea epoch-ului prin triggerul ledger
anulează atomic și scorurile, și recipisa. Recipisele rezultate aparțin numai bazelor
de test, eliminate ulterior.

Harness: imagine Supabase17.9.0.029-orioledb, digest fixat, extensia1.8 verificată
în fiecare bază de test. Container propriu, volum nou, port numai127.0.0.1,512MiB RAM,
1CPU. Inițializare minimală fără date/credentiale ale aplicației. Locale C/UTF-8:
prima probă a arătat că locale-ul libc implicit nu este acceptat pentru tabelă.
Nu este o clonă a tuturor setărilor serviciului găzduit. Containerul și volumul sunt
șterse; imaginea rămâne cache. Manifestul ARM64 declară aproximativ350MiB de transfer.

[Raport OrioleDB](2026-11-03-orioledb-integration/orioledb-report.json) ·
[Regresie heap](2026-11-03-orioledb-integration/heap-report.json).
Jurnale, JUnit, CSV-uri, recipise și manifestele de hash: local în
`build/d1/human-oriole-integration-2026-11-03-verified/` și
`build/d1/human-heap-regression-2026-11-03-verified/`.

## Reproducere

```sh
docker pull supabase/postgres@sha256:62b4fa9f99afde62bb9fd49a218531b0f74cd639dc3b03749701005564b837ff
PYTHONPATH=src python scripts/check_postgres.py --engine orioledb --full-inventory --output <director-nou>
PYTHONPATH=src python scripts/check_postgres.py --engine heap --full-inventory --output <alt-director-nou>
python scripts/check.py
```

Fără `--full-inventory`, testele folosesc numai fixtures. Fără opt-in, nu pornesc
Docker și nu citesc un DSN. Harness-ul acceptă doar cele două imagini fixate și
baze create pe propriul server; nu primește DSN-ul proiectului.

## Instalare viitoare și limite

[SQL-ul reviziilor](../sql/2026-11-03-human-row-revisions.sql) este pregătit și a fost
executat **numai în containerele izolate**, după SQL-ul ledger-ului. Trebuie rulat
ca owner al words. Instalează coloană, secvență, contract și trigger; inițializează
reviziile tuturor celor77.698 de rânduri sub ACCESS EXCLUSIVE, fără schimbarea
scorurilor. **Aceasta este o migrare structurală separată de apply-ul165.**

Executorul primește numai USAGE pe scheme, SELECT/UPDATE pe words, SELECT pe
contract și SELECT/INSERT/UPDATE pe ledger, plus vizibilitate completă prin
BYPASSRLS. LOCK-ul contractului este ACCESS SHARE pentru a nu necesita drepturi
de UPDATE asupra lui. Instanța izolată validează aceste granturi; nu au fost create
roluri reale. RLS-ul words și granturile API existente nu sunt modificate de SQL.

Ownerii și administratorii de schemă/backup rămân de încredere: nu trebuie să
reseteze secvența, să dezactiveze temporar triggerul sau să restaureze tokenuri și
epoch-uri din istorii divergente. Nu pretindem detectarea falsificării de către
un administrator privilegiat. Restore/reinstalare cere reconciliere explicită;
nu se continuă automat cu recipise din altă istorie.

**Următorul pas:** pregătirea pachetului de instalare pentru mediul real (revizii,
ledger, rol/granturi, verificări înainte/după), cu verificarea compatibilității
scriitorilor existenți — inclusiv INSERT-uri fără listă de coloane. Fără instalare
implicită. După autorizarea separată a instalării: preflight cu DSN-ul efectiv;
apoi, numai la instrucțiune explicită, apply165 cu verificare live în tranzacție.
Nu sunt necesare alte evaluări sau reaprobarea politicii. Cele50.724 de modificări
baseline rămân excluse.
