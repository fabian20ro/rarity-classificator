# Promovare automată acceptată — implementare și repetiție izolată

Politica `automatic-provisional-acceptance-v1` a fost aprobată prin confirmarea din
conversație, după prezentarea [pachetului de audit](2026-11-06-promotion-package.md).
Acceptarea numește candidatul înghețat și ambele rute. Fluxul separat este implementat
și verificat pe OrioleDB izolat. **Nicio instalare, citire sau aplicare în DB-ul real.**
Fără evaluări noi ori apeluri LLM. Nu mai este necesară reaprobarea aceleiași politici.

## Contractul implementat

- [Acceptarea](2026-11-06-automatic-flow/acceptance.json) fixează versiunea, data,
  hashul pachetului, hashul candidatului, wordfreq+fallback, prioritatea umană și
  acceptarea preciziei necunoscute în populație. Este evidență de intenție operațională,
  nu semnătură criptografică sau credential de conectare.
- Public `run_automatic_promotion(acceptance, package, output, ...)` și CLI separat.
  Modul implicit este `dry-run`, fără citirea DSN-ului sau accesarea store-ului.
  Pachetul se regenerează din CSV-urile originale și fiecare artefact este comparat.
  Manifestele incomplete sau resigilate contradictoriu sunt refuzate.
- Jaccard și precizia/recall seed rămân obligatorii, calculate cu pragurile originale
  0,70/0,80/0,80 atât față de snapshotul fixat, cât și față de starea blocată în
  tranzacție. Rezultatele FAIL rămân vizibile, cu rol diagnostic în acest domeniu
  acceptat. Step4, Step5 și gate-urile fluxului vechi nu sunt modificate.
- Execuția necesită acțiune explicită, confirmarea exactă a pachetului, DSN dedicat
  și epoch-ul așteptat al instalării reviziilor. Nu există flag generic `force`.
  Schema/rolurile nu sunt create automat de CLI.
- Un singur UPDATE condiționat pe ID/grafie/POS/scor/revizie aplică ambele loturi
  disjuncte în aceeași tranzacție. Parametri array, fără SQL construit din cuvinte,
  fără 50.724 de round-tripuri și fără apeluri paralele. Orice nepotrivire de ID/count
  anulează tranzacția, inclusiv rândurile deja potrivite.
- Lock-uri pe inventar și ledger înaintea snapshotului READ COMMITTED. Aplicarea
  refuză driftul identității, scorurilor și reviziilor întregului inventar arhivat.
  Verificarea stării complete include un SHA256 al celorlalte coloane, pentru a
  detecta și efectele secundare ale triggerelor asupra datelor fără scor.
- Ledger separat `automatic_promotion_receipts`. Scorurile și recipisa se confirmă
  atomic, cu post-verificare după ultima scriere în ledger. Fluxul și granturile
  corecțiilor umane rămân neschimbate; se reutilizează doar validatorul reviziilor.
- Retry citește recipisa durabilă și nu reaplică. `already_applied` confirmă un
  succes istoric, fără a pretinde că starea curentă coincide încă. Rollbackul folosește
  reviziile post-aplicare din recipisă, protejează formele umane și păstrează editările
  ulterioare pe rânduri neatinse. Un pachet anulat nu poate fi reaplicat.

Nu am rescris pachetul istoric audit/pending. [Preview-ul nou](2026-11-06-automatic-flow/preview.json)
este `policy_accepted=true`, `status=dry_run`, `applied=false`; rezultatele legacy
rămân FAIL. Acoperă exact 7.537 schimbări wordfreq și 43.187 fallback.

## Repetiția pe server real izolat

**18/18 probe PASS**, PostgreSQL17.9/OrioleDB1.8, imagine fixată prin același digest
folosit anterior. Cache-ul fusese eliminat; imaginea a fost descărcată din nou
(Docker raportează366.487.094bytes). Container/volum noi,512MiB/1CPU, port localhost,
fără DSN de aplicație sau credentiale reale. Containerul și volumul au fost eliminate;
imaginea cache rămâne disponibilă pentru repetare.

| Probă | Rezultat |
|---|---|
| Aplicare ambele rute, restart, retry, rollback/retry |PASS, fără rescrieri la retry|
| Efecte asupra scorurilor umane sau coloanelor fără scor |Rollback integral|
| Constrângere amânată, ledger indisponibil/rescris, epoch schimbat |Rollback integral|
| ACK pierdut după COMMIT, apply și rollback |Recuperare din ledger|
| Backend terminat înainte de COMMIT |Nicio schimbare parțială, retry reușit|
| Scriere externă cu același scor, înainte de apply/rollback |Conflict de revizie refuzat|
| Două cereri concurente pentru același pachet |O aplicare, o recipisă|
| Efect secundar al recipisei la rollback |Anulare atomică a inversării|
| Lock ocupat |Timeout5s, apoi retry reușit|
| UPDATE unic pentru ambele rute, potrivire CAS parțială |Buget respectat, nepotrivire atomică|
| Executor separat non-superuser, RLS activ |Apply/rollback reușite, acces human ledger refuzat|
| Inventar complet |50.724schimbate,233protejate,restaurare exactă|

Fixture-ul complet conține 77.698 de rânduri. Candidatul are același hash
`d7f52e307c523b74958bad4cf483706159cf843f4dbb593abea477c1611aa8ef`.
Reviziile și epoch-ul au fost generate pentru DB-ul de test, iar pachetul fixture
a fost legat explicit de acel snapshot. Acceptarea reală și sursele originale
nu au fost schimbate pentru a trece testele. Recipisele fixture nu pot autoriza
operații în producție.

Runda finală:31,17s total pentru toate18probe. Pe inventarul complet, apply6,75s,
rollback6,64s, incluzând replay/verificări/CSV. Aceste durate locale nu estimează
fereastra de lock din producție. Varianta inițială cu cereri individuale necesita
aproximativ20–22s local și risca latență mare pe o conexiune la distanță; înlocuită
cu un singur UPDATE și o regresie verificată întâi în eșec pe server.

## TDD și verificare offline

**1.003teste +479subteste PASS**,58integrări omise implicit, Ruff PASS. Dintre
integrările omise de suita offline, cele18noi au rulat separat pe serverul izolat.
Interfețe testate: pachet/acceptare→preview și apply/retry/rollback→store tranzacțional.
Nu s-au introdus dependențe Python noi.

Regresii red→green pentru interfața nouă, scope/manifest incomplet, citirea aprobării
modificate concurent, CLI fără DSN implicit și bugetul de UPDATE. Teste negative
pentru execuție fără confirmare/epoch, drift, eșec parțial/commit/ledger, ACK pierdut,
efecte post-recipisă și păstrarea editărilor neatinse la rollback.

Verificare finală a hashurilor implementării, a celor7surse protejate și a tuturor
celor1.135artefacte din repetiția finală. [Raport agregat](2026-11-06-automatic-flow/report.json)
și [proveniență](2026-11-06-automatic-flow/verification.json). Artefactele detaliate
rămân local în `build/d1/automatic-flow-2026-11-06/verified/`.

## Reproducere

Preview-ul original rămâne complet offline. Folosiți un director nou.

```sh
PYTHONPATH=src python -m classificator.automatic_promotion_flow \
  --acceptance docs/research/2026-11-06-automatic-flow/acceptance.json \
  --package ../automatic-promotion-audit-2026-11-06/final \
  --output ../automatic-flow-2026-11-06/new-preview
```

Repetiția nu acceptă DSN extern. Imaginea Docker fixată trebuie să existe local;
harness-ul folosește `--pull=never`. Scriptul elimină variabilele de aplicație din
mediul testelor. `--full-inventory` necesită sursele locale fixate, altfel rămân
probele fixture.

```sh
PYTHONPATH=src python scripts/check_automatic_promotion.py \
  --full-inventory --output ../automatic-flow-2026-11-06/new-rehearsal
python scripts/check.py
```

## Limite și pasul următor

Repetiția validează tranzacțiile pe motorul potrivit, cu proiecția completă și o
coloană suplimentară sintetică. Nu clonează toate coloanele, triggerele sau serviciile
reale. Detectează efectele în `words`/recipisă, nu toate efectele externe sau asupra
altor tabele. ACK-ul pierdut este injectat după COMMIT real; backend-ul și restartul
sunt reale. Administratorii DDL/backup rămân de încredere.

**Urmează preflight read-only în mediul real** pentru snapshot/revizii/epoch, roluri,
RLS, triggere și starea ledgerului automat. Schema și rolul dedicat automat nu au
fost instalate în mediul real în această etapă. Scriptul SQL pentru ledger este un
prerechizit separat, nu un instalator care poate fi rulat fără verificări.
După preflight se pregătesc instalarea/granturile minime pentru mediul verificat,
apoi instalarea și aplicarea se autorizează separat. Politica acceptată rămâne valabilă
pentru hashurile și rutele fixate; orice drift cere reconciliere, nu slăbirea CAS.
