# Temperatura relativă D1: câștig local, fără promovare

2026-11-08. **Implementat cu TDD; experiment offline complet150/50; gate FAIL.**
Fără LLM, evaluări noi sau acces DB. Scorurile umane rămân identice.

## Protocol și proveniență

[Plan predeclarat](../plans/2026-11-08-d1-temperature.md).
Aceleași200 distribuții salvate, control A/d1-omni-2b, aceleași142 grupuri
și cinci folduri pe150. Parametrul relativ T minimizează NLL pe outer-train;
fit pe150 pentru50. Nu este temperatura de sampling și nu schimbă runtime-ul.

q = softmax(log(max(p,1e-12))/T), T în[0.05,20]; mediană inferioară.
Zero valori sub floor în datele reale. NLL/Brier native folosesc normalizarea
cu același floor; predicția nativă rămâne cea istorică. Niciun parametru
nu a fost ales după rezultatele50 sau după numărul de erori severe.

T pe folduri:0.445037,0.429238,0.375794,0.376969,0.364626;
T full150: **0.396120**. Toate soluțiile interioare; limitele nu au constrâns fitul.
T<1 concentrează probabilitățile spre clasele deja favorizate. Ordinea claselor
nu se schimbă; o clasă favorizată greșit poate deveni o eroare mai gravă.

Comparatoarele sunt regenerate prin interfața publică v3; predicțiile,
coeficienții și raportul v3 sunt identice byte-cu-byte cu rezultatele publicate.
Pragurile baseline sunt refăcute în outer-train, fără covariate OOF cu scurgeri.

## Rezultate principale

„Exces” = suma max(|predicție−referință|−1,0). Diferența de un nivel este tolerată.

|Metodă|150: ≥2|150: exces|150: MAE|50: ≥2|50: exces|50: MAE|
|---|---:|---:|---:|---:|---:|---:|
|Baseline|11|14|0.513|13|14|1.080|
|D1 nativ|43|45|1.120|7|8|0.800|
|D1 afin v3|34|39|1.067|5|6|0.860|
|D1 temperatură|**32**|**41**|**0.980**|**7**|**9**|**0.900**|

Temperatura reduce numărul de erori față de v3 pe150, dar crește severitatea
lor cumulată:41 vs39. Pe150:23 erori de2 și9 de3; pe50:6 de2 și1 de4.
Pe50, câștigul față de baseline nu justifică regresia pe150.

|Metrică probabilistică|150 nativ|150 temperatură|50 nativ|50 temperatură|
|---|---:|---:|---:|---:|
|NLL, mai mic mai bine|1.46375|1.40175|1.60876|1.70280|
|Brier multiclasă, sumă pe clase|0.73968|0.71102|0.80369|0.86063|

NLL se îmbunătățește out-of-fold pe150, dar se înrăutățește pe50. Calibrarea
probabilităților pe pilot nu se transferă automat la lotul selectat pentru risc.

## Separat nivelurile1/4/5

Celulele sunt număr de erori≥2; suportul este în coloana a doua.

|Lot / nivel real|Suport|Baseline|D1 nativ|V3 afin|Temperatură|
|---|---:|---:|---:|---:|---:|
|150 /1|51|3|22|16|**8**|
|150 /4|21|2|2|4|**8**|
|150 /5|22|3|18|12|**13**|
|50 /1|0|—|—|—|—|
|50 /4|9|0|0|0|**0**|
|50 /5|6|1|6|2|**2**|

- Nivel1: cel mai clar câștig D1;14 erori native evitate, zero introduse.
  Exemple: `ai`, `an`, `os`, `ou`, `român`, `stat`:3→2, referință1.
  Rămâne mult sub baseline:8 erori față de3.
- Nivel4: regresie importantă;6 erori noi față de D1 nativ, niciuna evitată.
  `entropie`, `glandular`, `instrumentație`, `pag`, `văietare`:3→2;
  `caftan`:3→1, referință4. Temperatura accentuează semnalul greșit existent.
- Nivel5 pe150:5 erori native evitate (`abietacee`, `diorit`, `hipochinezie`,
  `preajm`, `xilem`:3→4), dar13/22 rămân severe. `micșurat` rămâne
  referință5, predicție3; evaluarea intenționată este păstrată.
- Nivel5 pe50: `clefăit`, `ozene`, `pustnici`, `ștofă`:3→4, erori tolerate.
  `descojit`:3 rămâne3, referință5. `otel`:2→1, referință5, eroare de4.
  Ambele au clasa1 cea mai probabilă în distribuția inițială; temperatura
  pozitivă nu poate inversa această ordine.

Predicțiile exacte5 nu sunt fiabile între loturi:3/3 corecte pe150
(`bromocet`, `eolit`, `sferoidizare`),0/3 pe50 (`aurolac`=4,
`descâlcit`=3, `mormăit`=3). Numere prea mici pentru concluzii populaționale.

## Erori evitate și introduse

|Control|150 evitate / noi|50 evitate / noi|
|---|---:|---:|
|D1 nativ|19 /8|4 /4|
|V3 afin|9 /7|0 /2|
|Baseline|5 /26|9 /3|

Pe50, cele patru îmbunătățiri la nivel5 sunt anulate numeric de patru erori noi:
`descâlcit`3:4→5, `mormăit`3:4→5, `industrializa`2:3→4, `napolitană`2:3→4.

Fără wordfreq: pe150 temperatura17/49 severe vs baseline2/49;
pe50,6/45 vs12/45. Nu justifică o regulă generală „D1 când lipsește frecvența”.

## Verificare

-12 teste noi la interfața CSV; soluție analitică, fold/50 invariance, uniforme,
  zero probabilități, capete, input invalid, hash-uri, refuz suprascriere.
- Suita offline: **1059passed,78skipped,479subtests**, Ruff PASS. Testele
  sărite nu reprezintă validare a integrărilor reale; nu s-a accesat DB/rețeaua.
- Solver independent SciPy:6 fituri, diferență maximă beta<8.2e−8.
- Audit independent: probabilități/mediane/metrici/erori pereche,200 identități
  și referințe păstrate,6 mutații temporare de etichete pentru verificarea izolării,
  replay identic,210 surse originale cu hash neschimbat.
- Review read-only conform planului: fără constatări de corectitudine.

[Predicții complete](2026-11-08-d1-temperature/predictions.csv) ·
[Cazuri severe](2026-11-08-d1-temperature/severe-cases.csv) ·
[Fituri](2026-11-08-d1-temperature/fits.json) ·
[Raport](2026-11-08-d1-temperature/report.json) ·
[Protocol](2026-11-08-d1-temperature/protocol.json) ·
[Audit](2026-11-08-d1-temperature/audit.json).

## Reproducere

Din rădăcina checkout-ului, cu Python-ul proiectului (fără instalări):

```sh
python scripts/run_d1_temperature.py \
  docs/research/2026-11-08-d1-score-v3/inputs \
  docs/research/2026-11-08-d1-score-v3/inputs/references.csv \
  /tmp/d1-temperature-replay
```

Output nou obligatoriu; scriptul blochează rețea, subprocess și psycopg.connect.
Manifestul include hash-uri pentru intrări, implementare și artefacte; nu suprascrie
rezultatele anterioare. Auditul independent este inclus ca `audit.py`; necesită
numpy/scipy deja instalate și cele210 surse locale originale pentru verificarea
întregii proveniențe. Replay-ul comparației necesită numai inputurile CSV din repo.

## Decizie și pas următor

**Nu promovăm temperatura; păstrăm baseline și prioritatea evaluărilor umane.**
Nu extindem această calibrare la1.000 sau inventarul complet. Nu ajustăm acum
T după erorile50, nu schimbăm decoderul sau obiectivul pentru a trece acest lot.

Dacă continuăm experimentele cu Omni, următoarea ipoteză separată: corecție
regularizată a biasului pe clase, care poate schimba ordinea claselor, spre
 deosebire de temperatură. Protocol fixat înainte, regularizare aleasă numai
în CV internă pe150, comparație cu baseline și temperatura, apoi50 descriptiv.
Este o opțiune de testat, nu o îmbunătățire demonstrată;150 etichete limitează
complexitatea. Trecerea la d1 simplu rămâne amânată, conform solicitării.
