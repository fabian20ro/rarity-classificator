# Forma exactă: wordfreq și corpusul definițiilor rebus

2026-10-21. Analiză de dezvoltare; D1 neîncărcat, zero cereri către LM Studio.

## Rezultat

Contractul păstrează cele150 de forme din inventar, toate intrările LOC cu aceeași
grafie și218 contexte lexicale din auditurile existente. POS-ul inventarului rămâne
metadată istorică, fără a restricționa sensul evaluat. De exemplu, tău păstrează N52
și P92; masa include folosirea substantivală articulată, deși inventarul avea VT.
Cele7 forme cu mai multe coduri POS LOC păstrează toate intrările; contextele
curate completează LOC, care nu enumeră toate utilizările flexionare ale unei forme.
Acoperirea rămâne limitată la sursele consultate, nu declarată exhaustivă.

Ținta: **forma exactă prin cel mai familiar sens valid, indiferent de POS**.
NFC, cedilă→virgulă și casefold sunt convenții ortografice de potrivire; grafia
originală este păstrată. Fără substituții micșurat→micșorat, sezisa→sesiza,
ițar→ițari sau ata→ața. Cheia ASCII servește numai excluderii paginilor corpusului,
nu atribuirii frecvențelor sau etichetelor. Scorurile/estimările nu intră în
contractul lexical ori în starea modelului.

Metricile folosesc numai37 etichete cu țintă clarificată:12 minime contextuale și25
revizuiri explicite de formă.113 etichete inițiale opace sunt excluse. Aceleași
limitări rămân: un evaluator, selecție orientată spre neconcordanțe, unele răspunsuri
după expunerea la estimări, acoperire lexicală provizorie. Nu este set held-out.

## Comparație fără praguri calibrate

Spearman compară frecvența cu familiaritatea (-scor); mai aproape de1 înseamnă
ordine mai apropiată de evaluările umane. Nu este acuratețe de clasificare.

| Măsură | wordfreq3.1.1, ro/best | Definiții rebus |
|---|---:|---:|
| Forme observate din37 |29|29|
| Forme fără observații |8|8|
| Corelație pe propriile29 forme |0,565|0,647|
| Corelație pe aceleași26 forme |**0,451**|**0,536**|

Nu comparăm direct primele două corelații: acoperă mulțimi diferite. Diferența pe26
este descriptivă; lotul nu justifică o concluzie despre superioritate generală.

| Scor uman | Total | Observate wordfreq | Observate rebus |
|---|---:|---:|---:|
|1|17|17|17|
|2|6|6|6|
|3|6|3|4|
|4|4|1|2|
|5|4|2|0|

Împreună, sursele acoperă32/37. Doar rebus: țanc, antereu, izotop. Doar wordfreq:
carter, pinot, ata. Niciuna: micșurat, ițar, stenodactilograf, sezisa, bizam.
Absența rămâne lipsă de dovezi, niciodată scor5 implicit. Corelațiile condiționate
pe observații omit disproporționat formele rare; în special rebus nu observă
niciuna dintre cele4 forme cotate5.

## Diferențe utile

| Formă | Scor uman | Rang wordfreq* | Rang rebus* | Observație |
|---|---:|---:|---:|---|
|in|3|3|13,5|Frecvență wordfreq mare față de familiaritatea evaluată; posibilă ambiguitate/zgomot de corpus, neconfirmat aici.|
|ulterior|2|10,5|21|Corpusurile dau ordini diferite;12 ocurențe în definiții.|
|rasă|2|21|12|58 ocurențe în definiții; semnal lexicografic mai puternic.|
|nordic|2|26|29|Doar1 ocurență rebus, deși forma este evaluată comună.|
|masca|1|18|22|Doar7 ocurențe rebus; frecvența definițiilor nu înlocuiește familiaritatea.|
|carter|5|19|absent|Wordfreq observă grafia, fără a garanta sensul mecanic; numele proprii pot contribui, fără atribuire demonstrată aici.|

*Rang1 = frecvența maximă, în cele29 forme observate ale fiecărei surse; medie la
egalitate. Rangurile explică divergențele, nu clase prezise. Nu s-au ajustat praguri
și nu s-au inventat scoruri1..5 din frecvențe.

## Corpus și reproducibilitate

wordfreq: exportul înghețat3.1.1,101/150 forme observate. Refolosit cu hash-ul
original verificat, fără instalarea/descărcarea unui model.

Rebus:12.728 fișiere locale JSON procesate secvențial.60 pagini excluse deoarece
cheia lor ASCII coincide cu una dintre cele150 ținte;147 înregistrări non-ok.
Restul12.521 pagini contribuie114.689 corpuri de definiții unice și1.280.002 tokenuri;
59.809 corpuri duplicate eliminate. Se preferă tree-def, apoi def în defWrapper;
navigația/scripturile/stilurile sunt excluse. Deduplicare globală a textului
normalizat; formele cu cratimă/apostrof nu sunt desfăcute în potriviri sintetice.

Excluderea întregii pagini a țintei limitează contaminarea prin propria definiție.
Nu elimină toate trimiterile, omonimiile sau definițiile suprapuse din alte pagini.
Corpul lexicografic păstrează titlurile din interiorul definițiilor și abrevierile;
nu este un eșantion de conversație sau de proză generală. Sursele și extractorul
sunt fixate prin hash-uri; schimbarea limbii/politicii/hash-urilor este respinsă.

Artefacte locale finale:
`build/d1/exact-form-evaluation-2026-10-21-v2/`:
`contexts.csv`, `forms/forms.csv`, `rebus/frequencies.csv`, `rebus/source-files.csv`,
`comparison/comparison.csv`, `comparison/summary.json` și manifeste.

Implementare pe baza PR81, commitf990e6c, în checkout-ul separat
`build/d1/exact-form-code/`. Checkout-ul principal are modificări preexistente și
nu conținea modulele PR81; au fost recuperate din ramura GitHub, fără suprascriere.
Script reproductibil: `scripts/run_exact_form_pilot.py`; CLI public:
`evaluation-exact-forms`, `evaluation-rebus`, `evaluation-form-report`.
D1 acceptă `--form-contract-csv`; verificarea stării/transportului folosește numai
HTTP simulat în teste. Secvențialitatea existentă este păstrată.

## Recomandare și ce rămâne

1. **Păstrează cele două frecvențe ca dovezi separate**, cu abținere și proveniență.
   Rebus completează wordfreq, dar rezultatele nu justifică încă înlocuirea
   clasificatorului sau un hibrid antrenat.
2. Următoarea etapă: lot independent, cu forme și familii separate de pilot;
   evaluare oarbă și al doilea evaluator, aceeași regulă a formei exacte. Nu redeschide
   cele172 contexte și nu folosi aceste37 cazuri drept test independent.
3. Abia după fixarea seturilor dev/calibrare/test: compară praguri de frecvență și
   ablații wordfreq/rebus/ambele pe aceeași țintă, raportând acoperirea și erorile rare→comune.
4. D1 rămâne în așteptarea RAM-ului. Ulterior: cereri secvențiale, variante fără/cu
   dovezi lexicale; niciun prag ori verdict de înlocuire bazat numai pe acest pilot.
   Gating-ul Jaccard/ancore și upload-ul partial rămân obligatorii.


## Verificare

TDD la interfețele publice CSV→artefacte și BatchScorer: identități/POS, variante
ortografice distincte, respingerea etichetelor din intrarea lexicală, extracție HTML,
deduplicare/excludere, absențe/ranguri/egalități, surse incompatibile și CLI fără HTTP.
Ruff și suita completă:792 teste trecute,108 subteste. Cele34 verificări de hash
pentru artefacte/intrări/implementare și importul anterior au trecut; două extracții
integrale au produs frecvențe identice octet cu octet. Etichetele originale intacte.
