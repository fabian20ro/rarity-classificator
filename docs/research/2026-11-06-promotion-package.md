# Pachet de promovare automată — audit, 6 noiembrie 2026

**Status la generarea pachetului: pregătit și verificat, aplicare blocată, politică neaprobată.**
Acesta este statusul la generarea pachetului. Ulterior, utilizatorul a acceptat
politica; [fluxul separat și repetiția izolată sunt încheiate](2026-11-06-automatic-flow.md).
Artefactele audit inițiale rămân imutabile. Aplicarea reală nu a fost autorizată/executată.
Reutilizează exact exportul conservator existent, cu evaluările umane prioritare,
wordfreq pentru frecvențe prezente și fallback 4 pentru rest. Nu modifică scoruri,
praguri, contractul operațional, executorul uman sau baza de date. Nicio evaluare
nouă, cerere LLM ori conexiune DB. Această etapă nu este un nou experiment statistic.

## Decizia propusă, concretă

Versiune propusă `automatic-provisional-acceptance-v1`, statut `pending`.
Schema generatorului `automatic-promotion-audit-v1` descrie numai pachetul de audit.

Recomandarea pentru obiectivul „acoperire integrală fără alte evaluări umane” este
acceptarea **provizorie și reversibilă** a candidatului înghețat, cu următorul domeniu.

1. Cele 200 de forme evaluate, corespunzătoare celor 233 de rânduri/POS, rămân
   protejate. Automatizarea nu poate suprascrie scorurile lor.
2. Celelalte 77.465 de rânduri primesc baseline-ul existent. Dintre ele, 50.724
   necesită schimbarea scorului și 26.741 sunt deja egale cu propunerea.
   Proveniența automată și statutul provizoriu trebuie păstrate în artefacte/recipise.
3. Acceptarea ar include riscul cunoscut de erori ≥2 și **precizia necunoscută în
   populație**. Nu ar declara trecute criteriile statistice eșuate și nu ar atribui
   procente de încredere individuale. Diferența 4–5 rămâne în toleranța ±1.
4. Propunerea pentru un contract operațional ulterior este să distingă explicit
   protecțiile obligatorii ale datelor de acceptarea riscului semantic. Jaccard și
   apartenența/recall pe ancore rămân calculate și raportate obligatoriu. Pentru
   acest candidat, valorile FAIL ar fi asumate explicit în decizie, cu lista pozitivă
   incompletă tratată drept diagnostic, fără a pretinde precizie semantică globală.
   **Această schimbare de rol a gate-urilor este doar propusă. Nu este implementată.**
5. O eventuală aprobare trebuie să numească versiunea politicii, hashul candidatului
   și ambele rute. Cererea actuală de pregătire a pachetului nu constituie acea
   aprobare și nu autorizează uploadul. Nici aprobarea riscului singură nu execută DB.

Nu se propune coborârea pragurilor numerice până când acest candidat trece.
Contractul actual continuă să blocheze aplicarea. Dacă acceptarea riscului de mai sus
nu este potrivită, alternativa cu dovezile actuale este păstrarea scorurilor automate
existente. Nu există o garanție de corectitudine integrală derivabilă din aceste date.

## Impactul exact

Inventar complet, 77.698 de rânduri și 75.147 de forme normalizate. Snapshotul este
copia locală post-corecții din 4 noiembrie, nu o citire actualizată a mediului real.

| Rută | Rânduri automate | Schimbări | Forme schimbate | Salturi ≥2 față de snapshot |
|---|---:|---:|---:|---:|
| wordfreq | 11.492 | 7.537 | 7.131 | 3.253 |
| fallback 4 | 65.973 | 43.187 | 41.878 | 3.350 |
| Total | 77.465 | 50.724 | 49.009 | 6.603 |

Cele 233 de rânduri protejate sunt excluse din ambele loturi. Loturile sunt disjuncte.
Fallback include 30.524 de treceri 5→4. Acestea nu sunt automat erori în toleranța
acceptată. Saltul față de snapshot nu reprezintă eroarea față de o evaluare umană.

Candidatul final este identic byte cu byte cu `both.csv` din simularea anterioară,
SHA256 `d7f52e307c523b74958bad4cf483706159cf843f4dbb593abea477c1611aa8ef`.
Regula respinsă de păstrare a scorului vechi la salturi mari nu este inclusă.

## Dovezile de calitate păstrate

Rezultatele de mai jos provin din [simularea fixată anterior](2026-11-05-automatic-promotion.md),
înainte de suprascrierile umane. Pilotul folosește predicțiile cu grup exclus.
Lotul de risc folosește scorurile înghețate. Cele 50 nu sunt un eșantion aleator.

| Rută | Severe, pilot | Severe, risc | Pilot, uman 4 | Pilot, uman 5 | Risc, uman 4 | Risc, uman 5 |
|---|---:|---:|---:|---:|---:|---:|
| wordfreq | 9/101 | 1/5 | 2/2 | 3/3 | fără suport | 1/1 |
| fallback | 2/49 | 12/45 | 0/19 | 0/19 | 0/9 | 0/5 |
| Total | 11/150 | 13/50 | 2/21 | 3/22 | 0/9 | 1/6 |

Cele 12 erori severe fallback din lotul de risc sunt forme umane 2 estimate la 4.
Frecvența absentă nu dovedește obscuritatea. Suportul wordfreq din lotul de risc
este prea mic pentru certificarea rutei. Pilotul a fost folosit în dezvoltare,
iar evaluările repetate pe aceleași forme nu produc o validare independentă nouă.
Potrivirea candidatului final cu cele 200 de etichete este prin construcție.

Gate-ul existent, recalculat pe candidatul complet, rămâne **FAIL**.

| Diagnostic | Valoare | Prag existent |
|---|---:|---:|
| Jaccard L1 față de snapshot | 16,71% | 70% |
| Apartenență L1 la seed, câmp istoric `anchor_precision` | 8,22% | 80% |
| Recall seed | 56,25% | 80% |

Acoperirea incompletă a listei pozitive împiedică interpretarea lui
`anchor_precision` drept precizie semantică globală. Această limită nu transformă
FAIL în PASS. Contractul versionat de audit existent rămâne neschimbat.

## Conținut și precondiții

Director local `build/d1/automatic-promotion-audit-2026-11-06/final/`.

- `candidate.csv` — proiecția completă pe ID-urile din snapshot.
- `wordfreq-changes.csv`, `fallback-changes.csv` — numai schimbările, cu grafie,
  POS, scor așteptat, scor propus, revizia din snapshot și proveniența sursei.
- `wordfreq-rollback.csv`, `fallback-rollback.csv` — inversarea scorurilor propuse.
  `version_source=committed_apply_receipt_required` exprimă precondiția încă absentă.
  Aceste CSV-uri nu sunt comenzi de rollback executabile și nu inventează revizii viitoare.
- `human-guards.csv` — toate cele 233 de postcondiții umane protejate.
- `mapping/` — maparea completă formă exactă/POS, conflictele ≥2 și auditul identității.
- `contract.json`, `report.json`, `manifest.json` — surse fixate prin hash,
  rezultate și blocajele explicite. Manifestul acoperă toate artefactele pachetului.

Se reutilizează maparea existentă pentru grupurile de duplicate echivalente.
Generatorul verifică identitatea sursă/candidat, toate POS-urile, prioritatea
etichetei umane și egalitatea scorurilor automate cu baseline-ul. Refuză driftul,
maparea incompletă, sursele contradictorii, reviziile invalide, directoarele deja
existente și orice mod/aprobare diferit de `audit`/`pending`. Publicarea locală
este atomică după verificarea hashurilor înainte și după generare.

Aplicarea viitoare necesită recitirea stării reale și a contractului de revizii,
identitate/scor/revizie verificate în tranzacție, protejarea celor 233 de rânduri,
recipisă și postcondiții atomice. Un reload al dicționarului sau orice drift cere
reconciliere și un pachet nou, nu modificarea silențioasă a precondițiilor.
Rollbackul trebuie legat de recipisă, instalare și reviziile **post-aplicare**.
Executorul dedicat corecțiilor umane nu este extins de această schimbare.

## Verificare și reproducere

Interfața CSV → pachet audit a fost testată în cicluri red→green. Cazurile includ
protecția tuturor POS-urilor unei forme umane, separarea rutelor și inversarea
loturilor, surse modificate sau resigilate contradictoriu, tentative de activare,
mapare incompletă, replay și refuzul suprascrierii unui rezultat existent.

**992 teste și 468 subteste PASS**, 40 integrări DB omise. Ruff PASS. Două rulări
complete produc 15 artefacte identice byte cu byte. Verificatorul separat, stdlib,
reconstruiește scorurile din baseline și etichete, verifică toate cele 77.698 de
rânduri și simulează în memorie aplicarea/inversarea celor 50.724 de schimbări.
Rezultatul aplicării coincide cu candidatul, inversarea restabilește toate scorurile
snapshotului. Aceasta nu este o repetiție a tranzacțiilor pe un server DB.

Rulările și suita au folosit guardul offline existent pentru rețea/DB/procese LLM.
Cele șase surse rămân nemodificate. Copiile agregate, fără rânduri DB, sunt în Git.

Din checkout-ul din `build/d1`, cu sursele istorice alături, folosiți directoare noi.
În altă locație, ajustați numai căile dintr-o copie a contractului, păstrând hashurile.

```sh
PYTHONPATH=src python -m classificator.evaluation.promotion_audit \
  --contract docs/research/2026-11-06-promotion-package/contract.json \
  --output ../automatic-promotion-audit-2026-11-06/new-run
PYTHONPATH=src python docs/research/2026-11-06-promotion-package/verify.py \
  --package ../automatic-promotion-audit-2026-11-06/new-run
```

[Contract](2026-11-06-promotion-package/contract.json) ·
[Raport](2026-11-06-promotion-package/report.json) ·
[Manifest](2026-11-06-promotion-package/manifest.json) ·
[Reconciliere](2026-11-06-promotion-package/verification.json).

## Ce mai rămânea la închiderea auditului

Decizia de acceptare a politicii provizorii de mai sus. Dacă este aprobată, următoarea
implementare este contractul operațional explicit și fluxul automat separat,
cu TDD și repetiție izolată pentru ambele rute, eșec, retry și rollback. Apoi
preflight real și aplicare autorizată separat. Nicio nouă rundă de evaluări umane
și nicio nouă inferență nu sunt necesare pentru acești pași tehnici. Fără acceptarea
riscului, aplicarea integrală rămâne blocată de dovezile de calitate existente.
