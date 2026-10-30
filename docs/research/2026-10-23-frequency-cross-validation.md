# Validare încrucișată a frecvențelor — 2026-10-23

**Concluzie:** pragurile de frecvență nu sunt suficiente pentru înlocuirea
clasificatorului. Pe aceleași26 de forme, rebus are MAE0,500 versus0,538 pentru
wordfreq, dar egalează reperul simplu calculat fără praguri. Acoperirea formelor
rare este slabă. Păstrăm ambele surse ca dovezi auxiliare; nicio încărcare D1,
nicio nouă evaluare cerută utilizatorului.

## Metodă și date

Toate150 de forme apar o singură dată în CSV, cu ultima evaluare existentă,
proveniența și metoda de comparație. Etichetele originale rămân nemodificate.

- **37 clarificate:** leave-one-form-out. Pentru fiecare formă, recalibrare pe
  celelalte36 de etichete clarificate; numai frecvențele observate intră în fit.
  Eticheta testată este eliminată efectiv din fișierul de referință al rundei.
- **113 inițiale:** control istoric separat. Aplicăm modelul calibrat pe toate37;
  niciuna dintre cele113 etichete nu influențează pragurile. **Acesta nu este CV**
  și păstrează ținta inițială ambiguă formă/POS. Nu calculăm o acuratețe globală
  care amestecă cele două reguli.
- Folosim algoritmul de praguri deja fixat: grilă logaritmică, minimizarea MAE,
  tie-break determinist, fără ajustări după rezultate. Rebus nu are nivel5 observat
  la antrenare: ultima limită rămâne convenție în toate37 de runde.
- Corpus neschimbat: wordfreq3.1.1 și corpusul rebus comun care exclude190 de
  forme/pagini colidente.100 pagini excluse,1.273.283 tokenuri.40 de forme noi
  neetichetate rămân în fișierul de features, dar nu intră în fit sau în metrici.
- Absența frecvenței înseamnă **abținere**, niciodată nivel5 implicit.
- Reper global: mediana celor36 de etichete, fără frecvențe. Reper comparabil
  per sursă: mediana etichetelor de antrenare cu frecvență observată în acea sursă;
  aceeași abținere ca sursa. Mediana inferioară la egalitate. Ambele exclud eticheta
  testată. Reperul per sursă a fost adăugat ca verificare a biasului de acoperire;
  predicțiile și pragurile frecvențelor au rămas identice între rulările v1/v2.

Aceasta este validare **internă** a unui pilot selectat, cu un singur evaluator,
uneori expus anterior estimărilor AI. Nu anulează selecția cazurilor ori alegerile
anterioare ale protocolului și nu demonstrează generalizare independentă.

## Comparația principală: aceleași26 de forme

MAE = distanța medie absolută pe scara1–5; mai mic este mai bine.

| Metodă | MAE | Exact | La cel mult1 nivel | Erori de cel puțin2 niveluri |
|---|---:|---:|---:|---:|
| wordfreq |0,538|15/26 (57,7%)|24/26 (92,3%)|2/26|
| Rebus |0,500|17/26 (65,4%)|22/26 (84,6%)|4/26|
| Mediana per sursă |0,500|17/26 (65,4%)|23/26 (88,5%)|3/26|
| Mediana globală |0,808|6/26 (23,1%)|25/26 (96,2%)|1/26|

Mediana per sursă rezultă1 în fiecare rundă pentru ambele surse. Nu este un
clasificator recomandat: servește doar drept control al utilității pragurilor.
Diferența wordfreq–rebus reprezintă **un singur punct de eroare totală** (14 vs13).
Rebus este mai aproape pe5 forme, wordfreq pe4, egalitate pe17. Rebus are mai multe
erori mari pe intersecție; nu există un câștigător clar pe toate criteriile.

Intersecția este dominată de forme comune:17 de nivel1,6 de nivel2,2 de nivel3,
una de nivel4 și **zero de nivel5**. Performanța de aici nu validează cuvintele rare.
Spearman între nivelurile prezise și umane: wordfreq0,189; rebus0,510, descriptiv.

## Toate37 clarificate: acoperire și subsetul propriu

| Sursă | Acoperire | MAE pe formele proprii | Exact | MAE reper per sursă |
|---|---:|---:|---:|---:|
| wordfreq |29/37|0,759|15/29|0,793|
| Rebus |29/37|0,517|18/29|0,690|

Subseturile diferă;0,759 și0,517 nu reprezintă comparația directă între surse.
Față de propria mediană, wordfreq reduce eroarea totală cu1 punct, rebus cu5.
Există un semnal util pentru rebus în cazurile acoperite doar de el, fără a rezolva
lipsa datelor. Împreună sursele acoperă32/37;5 rămân fără frecvență în ambele.

| Nivel uman | Forme | Wordfreq observate | Rebus observate |
|---|---:|---:|---:|
|1|17|17|17|
|2|6|6|6|
|3|6|3|4|
|4|4|1|2|
|5|4|2|0|

Dintre8 forme rare (4/5), wordfreq acoperă3 și le subestimează pe toate3 cu cel
puțin2 niveluri; rebus acoperă2, fără subestimare de cel puțin2 niveluri. Rebus
nu observă niciuna dintre cele4 forme de nivel5. Acest0/2 erori severe nu demonstrează
calitate bună pentru nivel5: acolo nu există predicții.

## Diferențe importante

„—” = frecvență absentă; nu reprezintă un scor.

| Formă | Evaluarea ta | Wordfreq CV | Rebus CV | Observație |
|---|---:|---:|---:|---|
|carter|5|1|—|Wordfreq subestimează cu4 niveluri; păstrăm sensul evaluat.|
|ata|5|3|—|Subestimare cu2 niveluri.|
|pag|4|1|3|Rebus mai aproape; wordfreq subestimează cu3.|
|izotop|4|—|3|Rebus furnizează un semnal unde wordfreq lipsește.|
|pinot|3|5|—|Wordfreq supraestimează raritatea cu2.|
|nordic|2|3|4|Rebus supraestimează raritatea cu2.|
|rahat|2|2|4|Wordfreq exact; rebus supraestimează cu2.|
|masca|1|2|3|Ambele supraestimează; rebus cu2.|
|in|3|1|1|Ambele subestimează cu2; frecvența nu rezolvă ținta semantică.|
|micșurat|5|—|—|Nota5 intenționată rămâne neschimbată; ambele surse se abțin.|

## Controlul istoric113 — separat, fără recalibrare

| Sursă | Acoperire | MAE pe subset propriu | Exact pe subset propriu |
|---|---:|---:|---:|
|wordfreq|72/113|0,750|42/72|
|Rebus|81/113|0,667|37/81|

Pe aceleași64 de forme: wordfreq MAE0,625/exact41/64; rebus MAE0,563/exact35/64;
reperul per sursă MAE0,625. Wordfreq este mai aproape pe19, rebus pe14,31 egalități;
rebus compensează prin reducerea unor erori mai mari. Aceste rezultate rămân un
control cu țintă istorică diferită, nu un al doilea scor CV.

Dintre35 de forme istorice de nivel4/5, wordfreq observă2 (ambele subestimate sever),
rebus13 (4 subestimate sever). Împreună acoperă89/113;24 lipsesc din ambele.
Exemple istorice: drac1→wordfreq5/rebus1; ață1→4/1; dorian5→2/3.
Nu modificăm evaluările pe baza acestor diferențe și nu le transformăm în etichete
de sens care nu au fost furnizate de evaluator.

## Recomandare actualizată

1. **Nu înlocuim clasificatorul cu praguri wordfreq sau rebus.** Avantajul pe
   intersecție este mic și dispare față de reperul per sursă; nivelurile rare
   sunt slab acoperite. Nicio modificare în clasificarea/uploadul de producție.
2. Păstrăm **ambele surse separat**, cu lipsa datelor explicită. Rebus oferă unele
   indicii complementare; absența din corpus nu devine automat „foarte obscur”.
   Niciun hibrid nou sau alte praguri alese pentru a îmbunătăți acest raport.
3. Următorul experiment util pentru obiectivul D1 este comparația **fără/cu dovezi
   de frecvență**, pe aceleași forme și etichete, cu aceleași separări37/113 și
   aceleași cazuri rare. Îl rulăm doar când utilizatorul autorizează încărcarea și
   există RAM; cereri strict secvențiale. Până atunci, păstrăm acest baseline.
4. **Nu mai cerem adnotări.** Cele150 și clarificările lor sunt reutilizate.
   Un evaluator independent rămâne opțional; lipsa lui este o limită raportată,
   nu un blocaj pentru progres.

Pragurile sunt instabile pe pilotul mic: limita1/2 wordfreq variază de10 ori între
runde (7,94e-6…7,94e-5). MAE de antrenare0,483/0,345 devine CV0,759/0,517 pe subseturile
proprii. Nu prezentăm scorurile de antrenare drept performanță de validare.

## Verificare și artefacte

TDD la interfața CSV: fixture cu rezultate calculate explicit; modificarea etichetei
testate nu schimbă modelul/predicția proprie sau reperele; modificarea etichetelor
istorice nu schimbă rezultatele CV. Absențele, separarea rubricilor și refuzul
suprascrierii sunt verificate. Ruff și796 teste +112 subteste trecute.

Audit pe datele reale:150 ID-uri unice,37 runde cu propriul ID exclus, hashurile
surselor și artefactelor verificate, metrici recalculate independent din CSV.
Nicio cerere D1 sau LM Studio; implementarea folosește exclusiv fișiere locale.

Director final: `build/d1/cross-validation-2026-10-23-v2/`.

- `comparison.csv`: toate150 de forme, note/proveniență, metodă, frecvențe,
  predicții, erori și repere.
- `summary.json`: metrici separate, intersecții, confuzii și acoperire per nivel.
- `folds.json`, `folds/<id>/`: fiecare set de antrenare, praguri și predicții.
- `full-fit/`: modelul celor37 pentru controlul istoric; nu folosit pentru CV37.
- `manifest.json`, `source-validation.json`, `run.py`, `run-manifest.json`:
  integritate, proveniență și reproducere; o nouă rulare cere alt director de ieșire.

API public în checkout-ul implementării:
`classificator.evaluation.frequency_cross_validation.cross_validate_frequencies`.
Inputuri: vocabular pilot150, working-reference150, features înghețate, output nou.
Manifestul final apare numai la încheierea reușită; ieșirile parțiale nu se suprascriu.
