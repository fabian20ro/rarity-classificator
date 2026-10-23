# Baseline-uri pe întregul pilot — 2026-10-23

**Toate cele 150 de evaluări au fost folosite.** Două experimente cu 150 de forme,
plus unul cu cele 149 de prime răspunsuri independente. 449 de runde leave-one-out.
Nicio încărcare D1, nicio cerere LLM, nicio evaluare nouă solicitată utilizatorului.

**Rezultat:** modelul local combinat este un baseline practic promițător: MAE 0,533
pe ultimele 150 de note și 0,671 pe primele 149 independente, față de 1,740 / 1,685
pentru snapshotul vechi. Estimările AI salvate rămân mai apropiate de primele note
independente (0,557), dar sunt un reper istoric, nu un clasificator local nou.

## Datele și cele trei perspective

1. `original_round_final`: toate 150 de note finale din prima rundă. Coloana
   `initial_level` coincide exact cu vechiul `labels-final.csv`; **nu** este primul
   răspuns independent. Unele note au urmat afișării estimării AI.
2. `revised_working`: toate 150 de ultime note disponibile, cu corecțiile ulterioare.
   37 de forme au clarificări explicite, 113 păstrează ținta inițială formă/POS.
   Este o evaluare operațională cu reguli mixte, nu un gold omogen nou.
3. `first_independent`: cele 149 de prime note marcate independente în importul
   original. `ata` lipsește din acest subset. 31 de note diferă de finalul primei
   runde. Independența este per item, nu dovada absenței oricărei influențe între itemi.

Legacy și AI sunt predicții fixe salvate înainte, cu identități și hashuri verificate.
Pentru toate metodele învățate am folosit aceleași folduri în fiecare perspectivă:
149 de etichete de antrenare pentru fiecare test din cele 150, respectiv 148 pentru
subsetul independent. Nici scorul, nici frecvența formei testate nu intră în fit-ul
pragurilor, imputării sau scalării. Feature-ul testat este folosit numai la predicție.

Datele și rezultatele vechi strict37 sunt păstrate. Detalierea37/113 din acest raport
folosește predicțiile antrenate în foldurile întregului lot, deci nu este același
experiment ca validarea exclusiv pe37.

## Rezultate pe toate 150

MAE: eroare absolută medie pe scara 1–5; mai mic este mai bine. Pentru sursele care
se abțin, MAE este condiționată de acoperire. Nu comparăm direct 101/110 cu 150.

| Metodă | Acoperire | MAE prima rundă finală | MAE ultimele note | Exact, ultimele note |
|---|---:|---:|---:|---:|
|Snapshot vechi DB|150/150|1,580|1,740|28/150|
|Estimări AI salvate|150/150|0,273|0,473|96/150|
|Mediană globală|150/150|1,767|1,227|31/150|
|Clasa majoritară|150/150|1,267|1,547|51/150|
|Praguri wordfreq|101/150|0,733|0,455|67/101|
|Praguri rebus|110/150|0,900|0,645|54/110|
|Mediană pe acoperirea wordfreq|101/150|0,812|0,782|51/101|
|Mediană pe acoperirea rebus|110/150|0,936|0,900|30/110|
|Ridge combinat|150/150|0,693|0,533|80/150|

Mediana primei runde are zero potriviri exacte din cauza distribuției: exact 75 de
note sunt ≤2 și 75 sunt ≥3. Omiterea unui item mută mediana de antrenare pe cealaltă
parte a acestei limite. Rezultatul este verificat, nu o eroare de implementare.

Pe ultimele note, Ridge și AI au fiecare 141/150 predicții la cel mult un nivel
față de scorul uman; Ridge are 80 scoruri exacte, AI 96. Snapshotul vechi are numai
74/150 la cel mult un nivel și bias +1,313: tinde să considere formele mai rare.

## Comparație pe aceleași 90 de forme acoperite de ambele frecvențe

Ultimele note, aceleași ID-uri pentru toate metodele:

| Metodă | MAE | Exact | Erori de cel puțin 2 niveluri |
|---|---:|---:|---:|
|Snapshot vechi DB|2,089|15/90|57/90|
|Estimări AI salvate|0,544|55/90|7/90|
|Mediană globală|0,722|28/90|2/90|
|Clasa majoritară|0,589|51/90|11/90|
|Praguri wordfreq|0,400|61/90|6/90|
|Praguri rebus|0,567|49/90|10/90|
|Ridge combinat|0,444|54/90|3/90|

Wordfreq este cel mai bun aici după MAE, cu 4 puncte de eroare totală mai puțin decât
Ridge (36 versus 40). Intersecția conține însă numai 2 forme rare (4/5). Nu rezolvă
cazurile rare și cele fără frecvență, iar avantajul nu se transferă automat pe tot lotul.

## Verificarea pe cele 149 de prime răspunsuri independente

Am recalibrat metodele învățate exclusiv pe primele răspunsuri ale celorlalte 148 de
forme, păstrând exact aceiași parametri. Astfel comparația cu AI nu folosește note
ulterioare expunerii drept antrenare. Cele două experimente150 au rămas identice.

| Metodă | Acoperire | MAE | Exact | La cel mult un nivel |
|---|---:|---:|---:|---:|
|Snapshot vechi DB|149/149|1,685|29/149|74/149|
|Estimări AI salvate|149/149|0,557|85/149|138/149|
|Mediană globală|149/149|1,188|34/149|107/149|
|Clasa majoritară|149/149|1,624|42/149|76/149|
|Praguri wordfreq|100/149|0,610|55/100|88/100|
|Praguri rebus|110/149|0,827|42/110|92/110|
|Ridge combinat|149/149|0,671|61/149|141/149|

Pe aceleași 90 de forme observate de ambele surse, MAE: AI 0,567, wordfreq 0,578,
Ridge 0,644, rebus 0,733. Datele nu susțin că Ridge ar depăși estimările AI.
Ridge are mai puține erori ≥2 pe întregul subset (8 vs 11 pentru AI), dar mai multe
erori de un nivel și mai multe subestimări severe ale formelor rare (7 vs 2).

Acordul AI cu finalul primei runde (MAE 0,273) este mult mai bun decât cu primele
răspunsuri independente (0,557). Nu atribuim cauzal această diferență, nu prezentăm
scorul 0,273 ca performanță independentă și nu schimbăm retrospectiv predicțiile AI.

## Detalierea 37/113, ultimele note

Ambele subseturi sunt extrase din aceleași folduri150; fiecare predicție a avut149
etichete de antrenare. Numărul de observații variază pentru sursele de frecvență.

| Subset | Metodă | Acoperire | MAE |
|---|---|---:|---:|
|37 clarificate|Snapshot vechi DB|37/37|2,081|
|37 clarificate|Estimări AI salvate|37/37|1,243|
|37 clarificate|Praguri wordfreq|29/37|0,552|
|37 clarificate|Praguri rebus|29/37|0,586|
|37 clarificate|Ridge combinat|37/37|0,514|
|113 inițiale|Snapshot vechi DB|113/113|1,628|
|113 inițiale|Estimări AI salvate|113/113|0,221|
|113 inițiale|Praguri wordfreq|72/113|0,417|
|113 inițiale|Praguri rebus|81/113|0,667|
|113 inițiale|Ridge combinat|113/113|0,540|

Estimările AI inițiale au fost făcute pentru forma/POS inițială; dezacordul pe37
clarificate include schimbarea țintei semantice. Nu este o măsură de degradare a
aceluiași model sub același protocol.

## Forme rare și lipsa dovezilor

43 de forme au ultima notă4/5. Frecvențele individuale se abțin când lipsesc datele;
Ridge produce estimări și acolo, pe baza tiparului de lipsă învățat din train.

| Metodă | Rare acoperite | Rare subestimate cu cel puțin 2 niveluri |
|---|---:|---:|
|Snapshot vechi DB|43/43|8/43|
|Estimări AI salvate|43/43|1/43|
|Praguri wordfreq|5/43|5/5|
|Praguri rebus|15/43|6/15|
|Ridge combinat|43/43|4/43|

Ultimele note, Ridge separat după dovezi:

| Frecvențe disponibile | Forme | MAE Ridge |
|---|---:|---:|
|Ambele|90|0,444|
|Una|31|0,516|
|Niciuna|29|0,828|

Dintre cele29 fără nicio frecvență,25 sunt rare în acest pilot. Modelul folosește
acest tipar: pe ultima referință prezice4 pentru25 și5 pentru4. Aceasta este
**inferență din lipsa dovezilor**, nu observație lexicală și nu justifică regula
„absent = nivel5”. Distribuția unui inventar mai mare poate fi diferită.

Exemple cu ultimele note (— = abținere):

| Formă | Tu | Vechi | AI salvat | Wordfreq | Rebus | Ridge |
|---|---:|---:|---:|---:|---:|---:|
|mai|1|5|4|1|1|1|
|la|1|4|5|1|1|1|
|nordic|2|5|3|2|4|2|
|rahat|2|5|2|2|3|2|
|carter|5|5|4|2|—|3|
|ata|5|3|5|3|—|3|
|pag|4|4|5|2|2|2|
|dorian|5|5|5|2|4|2|
|sezisa|3|4|4|—|—|5|
|micșurat|5|5|2|—|—|4|

## Implementare și verificare

- Praguri: algoritmul log-grid/MAE și tie-break anterioare, reutilizate. Acum sunt
  calibrate pe etichetele declarate ale întregului lot. Nicio falsificare a
  `reference_kind` pentru a trece prin filtrul vechi de37.
- Ridge: patru intrări — log10 wordfreq, log10 rebus, doi indicatori de lipsă.
  Imputare mediană a logurilor numai din train; scalare train cu ddof0; alpha1,
  solver SVD, intercept nepenalizat. Rotunjire floor(raw+0,5), limitare la1–5.
  Fără căutare de hiperparametri, fără confidence inventat, fără definiții noi.
- Același corpus frozen: wordfreq3.1.1, rebus cu100 pagini excluse și1.273.283
  tokenuri, excluzând țintele150+40. Cele40 neetichetate nu intră în niciun fit.
- Dependență opțională `evaluation`: scikit-learn; versiunile exacte sunt în
  protocol (scikit-learn1.9.1, numpy2.4.6, scipy1.17.1). CI instalează acest extra.
- TDD la interfața CSV: rezultate cunoscute pentru snapshoturi și metrici,
  excluderea etichetei testate în ambele perspective150, imputare/scalare numai
  pe train, subsetul149, lipsuri și refuzul suprascrierii.797 teste +112 subteste;
  Ruff trecut. Nicio cerere LLM sau LM Studio.
- Audit real:449 folduri, ID-ul testat exclus din fiecare; hashuri, identități,
  imputare/scalare recalculată independent și metrici recalculate din CSV.
- Prima rulare conținea numai cele două perspective150. V2 adaugă149 independente,
  fără schimbarea predicțiilor celor două perspective existente; egalitatea verificată.

Acestea sunt rezultate interne pe un pilot selectat, cu un singur evaluator.
Foldurile exclud forma exactă, nu toate rudele lexicale; nu este validare externă.

## Recomandare actualizată

**Baseline-ul local recomandat pentru continuarea experimentelor este Ridge combinat.**
Are acoperire integrală și rezultate mult mai bune decât snapshotul vechi și
reperele constante, atât pe ultimele150, cât și pe primele149 independente.
Păstrăm wordfreq separat: pe formele observate poate fi mai precis decât combinatul.
Păstrăm AI salvat drept reper puternic, distinct de un backend local reproductibil.

Nu promovăm modelul în producție pe baza acestui pilot. Cazurile fără frecvențe,
ținta mixtă, selecția lotului și erorile rare rămân limite materiale. Nu ajustăm
parametrii după acest raport pentru a-i cosmetiza rezultatul.

**Următorul pas util fără D1:** verificarea robusteții aceluiași candidat cu folduri
care țin rudele lexicale împreună și un control folosind numai indicatorii de lipsă.
Reutilizăm notele existente; nu cerem alte adnotări. Acest control ar arăta cât din
avantaj vine din frecvențe și cât din selecția cazurilor cu date lipsă. D1 rămâne
opțional pentru comparația ulterioară, cu RAM și autorizare explicită; numai secvențial.

## Artefacte și reproducere

Director final: `build/d1/full-pilot-baselines-2026-10-23-v2/`.

- `original_round_final/predictions.csv`: toate150, prima rundă finală.
- `revised_working/predictions.csv`: toate150, ultimele note.
- `first_independent/predictions.csv`:149, primele răspunsuri independente.
- Fiecare director include `folds/<word_id>.json`: train IDs, praguri, suport,
  mediane/majoritate, imputare, scalare, coeficienți și predicție Ridge continuă.
- `summary.json`: rezultate complete,37/113, intersecție90, acoperire pe nivel,
  confuzii, erori rare și grupuri de disponibilitate.
- `protocol.json`, `manifest.json`, `source-validation.json`, `verification.json`,
  `run.py`, `run-manifest.json`: politică, versiuni, integritate și reproducere.

API: `classificator.evaluation.full_pilot_baselines.evaluate_full_pilot`.
În checkout-ul implementării: `python -m pip install -e '.[dev,evaluation]'`.
Scriptul local `run.py` reproduce analiza după alegerea unui output nou. Orice
director existent este refuzat; `manifest.json` marchează încheierea completă.
Snapshoturile, notele umane, interfețele și scorurile de producție nu sunt modificate.
