# Corecții regularizate pe clase: rezultat negativ

2026-11-08. **Implementare TDD și comparație offline150/50 finalizate; gate FAIL.**
Fără apeluri LLM, evaluări noi sau acces DB. Referințele umane păstrate integral.

## Protocol

[Plan fixat înainte de rulare](../plans/2026-11-08-d1-class-bias.md).
Distribuțiile control A d1-omni-2b din v3, aceleași200 forme,142 grupuri pe150.
q=softmax(log(max(p,1e-12))+b); bias centrat, patru grade de libertate.
Temperatura fix1; comparatorul temperaturii este experimentul anterior.

Fit: NLL medie + lambda/2 * suma bias². Grilă predeclarată0.01/0.1/1/10
plus identitate. Selecție după NLL inner-OOF agregată pe forme, nu media
neponderată a foldurilor; egalitate1e-10 → regularizare mai puternică.
Decoderul rămâne mediana inferioară. Nu am ajustat grila, obiectivul sau
regulile după rezultate.

150: cinci folduri istorice pe grupuri; fiecare outer-train își alege lambda
prin cele patru folduri rămase, apoi refit. Outer-heldout exclus din ambele
operații. 50: selecție în cinci folduri150, refit pe150, predicție pe50.
Nicio etichetă50 folosită pentru fit sau selecție. Lot50 explorat și selectat
pentru risc; fără nivel1, nu este test independent sau estimare populațională.

## Regularizarea aleasă

|Fit|Lambda|
|---|---:|
|Outer0|1|
|Outer1|Identitate|
|Outer2|Identitate|
|Outer3|10|
|Outer4|1|
|Full150 →50|10|

Bias full150 pentru clasele1..5:
`[0.0074264, 0.0001518, -0.0042424, -0.0004184, -0.0029174]`.
Corecție foarte mică. NLL în CV de selecție full150:identitate1.463751,
lambda10=1.463645; diferență≈0.000106. Nu o tratăm drept dovadă de câștig stabil.
Regularizarea mai slabă nu este susținută de CV internă. În două outer-folduri
este preferată explicit lipsa corecției.

## Erori și severitate

Exces=suma max(|predicție−referință|−1,0), conform toleranței de un nivel.

|Metodă|150 ≥2|150 exces|150 MAE|50 ≥2|50 exces|50 MAE|
|---|---:|---:|---:|---:|---:|---:|
|Baseline|11|14|0.513|13|14|1.080|
|D1 nativ|43|45|1.120|7|8|0.800|
|Afin v3|34|39|1.067|5|6|0.860|
|Temperatură|32|41|0.980|7|9|0.900|
|Bias regularizat|**41**|**43**|**1.120**|**7**|**8**|**0.800**|

Pe150 sunt39 erori de2 și2 de3. Pe50:6 erori de2 și1 de3.
Toate cele50 predicții sunt identice cu D1 nativ; pe150 se schimbă10 predicții.

|Metrică probabilistică|150 nativ|150 bias|50 nativ|50 bias|
|---|---:|---:|---:|---:|
|NLL, mai mic mai bine|1.463751|1.464868|1.608758|1.610910|
|Brier multiclasă|0.739677|0.739964|0.803685|0.804637|

NLL/Brier pe outer-heldout150 se înrăutățesc ușor. Faptul că lambda câștigă
în CV internă nu garantează îmbunătățirea pe outer-heldout; nested CV expune
această limită. Același sens al diferenței apare pe50.

## Separat nivelurile1/4/5

Celulele sunt erori≥2, cu suport explicit.

|Lot / nivel real|Suport|Baseline|D1 nativ|Afin v3|Temperatură|Bias|
|---|---:|---:|---:|---:|---:|---:|
|150 /1|51|3|22|16|8|**19**|
|150 /4|21|2|2|4|8|**3**|
|150 /5|22|3|18|12|13|**18**|
|50 /1|0|—|—|—|—|—|
|50 /4|9|0|0|0|0|**0**|
|50 /5|6|1|6|2|2|**6**|

- Nivel1: trei erori native evitate — `an`, `as`, `ou`:3→2, referință1.
  Rămân19/51, față de3/51 baseline.
- Nivel4: o eroare nouă — `caftan`:3→2, referință4. Nicio eroare nativă
  de nivel4 evitată. Regresie față de baseline și nativ, deși mai bine decât
  temperatura pe acest subset.
- Nivel5: niciun câștig. Pe150 rămân18/22 severe. `micșurat` rămâne referință5,
  predicție3. Pe50, `clefăit`, `descojit`, `ozene`, `pustnici`, `ștofă` rămân3;
  `otel` rămâne2. Toate șase sunt evaluate5 și rămân erori severe.

Biasul nu produce nicio predicție1 sau5 în cele două loturi. Precizia pentru
predicția5 este nedefinită, nu zero; recall exact5=0. Criteriul principal rămâne
însă eroarea≥2: predicția4 pentru o referință5 ar fi fost tolerată.

## Erori evitate versus introduse

|Control|150 evitate / introduse|50 evitate / introduse|
|---|---:|---:|
|D1 nativ|3 /1|0 /0|
|Afin v3|4 /11|2 /4|
|Temperatură|7 /16|4 /4|
|Baseline|6 /36|11 /5|

Față de baseline, aparentul câștig pe50 vine din11 forme evaluate2, pentru
care fallback4 era prea ridicat. În schimb se introduc cinci erori la nivel5.
Pe150 se introduc36 erori severe și se evită doar6. Acesta este motivul
practic pentru care nu promovăm pe baza rezultatului agregat50.

Fără wordfreq:150 bias18/49 vs baseline2/49;50 bias6/45 vs baseline12/45.
Datele nu susțin folosirea generală a D1 pentru formele fără frecvență.

## Verificare și reproducere

-10 teste noi la interfața CSV, inclusiv soluție analitică pentru lambda0.1,
  corectarea ordinii claselor, identitate, izolare outer/inner/50, minimum3folduri,
  probabilități zero, clase absente, intrări invalide și integritate artefacte.
- **1069passed,78skipped,479subtests; Ruff PASS.** Verificare offline;
  testele sărite nu validează integrările reale.
- SciPy independent:104 fituri regularizate verificate; diferență maximă între
  coeficienți2.71e−8; gradient maxim<1e−9. Toate candidatele și selecțiile
  lambda verificate, inclusiv ponderarea foldurilor inegale și identitatea.
- Probabilități, mediane, metrici, comparații pereche și gate recalculate independent.
  Șase verificări reale de izolare prin modificarea copiilor temporare ale
  etichetelor; niciun scor original modificat.
- Replay identic, comparatoare native/v3/temperatură identice,210 surse originale
  intacte. Review read-only: fără constatări acționabile.

[Predicții](2026-11-08-d1-class-bias/predictions.csv) ·
[Cazuri severe](2026-11-08-d1-class-bias/severe-cases.csv) ·
[Toate selecțiile și fiturile](2026-11-08-d1-class-bias/fits.json) ·
[Raport](2026-11-08-d1-class-bias/report.json) ·
[Protocol](2026-11-08-d1-class-bias/protocol.json) ·
[Audit independent](2026-11-08-d1-class-bias/audit.json).

Din rădăcina checkout-ului, cu Python-ul proiectului:

```sh
python scripts/run_d1_class_bias.py \
  docs/research/2026-11-08-d1-score-v3/inputs \
  docs/research/2026-11-08-d1-score-v3/inputs/references.csv \
  /tmp/d1-class-bias-replay
```

Output nou obligatoriu; rețea/subprocess/psycopg.connect blocate de CLI.
Nicio dependență nouă. Replay-ul folosește numai inputurile din repo.
Auditul `audit.py RUN REPO`, cu `PYTHONPATH=src` și guardul offline, necesită
numpy/scipy deja instalate și sursele locale originale pentru proveniența completă.

## Decizie și recomandare

**Păstrăm baseline și prioritatea scorurilor umane. Nu promovăm acest candidat.**
Nu extindem biasul pe1.000 sau inventarul complet. Rezultatul nu justifică
creșterea complexității calibrării globale pe aceleași etichete reutilizate.

Dacă mai testăm o opțiune offline, următoarea ipoteză simplă este un decoder
ordinal fix, care minimizează explicit costul așteptat
`max(|predicție−nivel|−1,0)`, cu regulă de egalitate predeclarată. Fără parametri
noi antrenați; comparator constant3 obligatoriu, pentru a detecta refugiul în
mijlocul scalei. Aceleași verificări1/4/5 și aceleași limite ale lotului50.
Neimplementat aici; beneficiul rămâne de demonstrat. D1 simplu rămâne amânat.
