# Simularea promovării scorurilor automate, 5 noiembrie 2026

**Recomandare: păstrăm ambele rute provizorii.** Wordfreq îmbunătățește rezultatul global pe formele cu frecvență, dar subestimează câteva forme rare. Fallback-ul 4 ratează mai ales cuvinte familiare. Decizia simulată păstrează scorurile din snapshotul verificat după aplicarea celor 165 de corecții umane. Impactul deciziei este zero modificări.

## Cum am comparat

Regula exploratorie a fost fixată în commitul `4dd8850`, înainte de calculul pe rute. Rezultatele agregate anterioare erau deja cunoscute. Pentru fiecare rută cerem, separat în fiecare lot, cel puțin 10 forme și cel mult 10% erori de două sau mai multe niveluri. Cerem și ca numărul de erori severe, costul lor total și numărul de erori severe pe fiecare dintre clasele umane 4 și 5 să nu crească față de comparator. Costul este suma nivelurilor de eroare peste toleranța de ±1. Pragurile 10 forme și 10% sunt alegeri pentru simulare și nu au fost aprobate ca politică de producție. Un lot mic oferă oricum puțină informație despre inventar.

Unitatea de evaluare este forma exactă. Comparatorul folosește scorurile dinaintea corecțiilor, luând minimul dintre POS-urile aceleiași forme conform regulii sensului celui mai familiar. Pe pilotul de dezvoltare, fiecare predicție provine dintr-o calibrare care a exclus întregul grup al formei. Pe cele 50 de forme selectate după risc folosim scorul automat înghețat înainte de override. Pentru impact folosim acest scorer înghețat și snapshotul local din 4 noiembrie, capturat după corecții. Cele 233 de rânduri evaluate uman sunt protejate în fiecare scenariu.

## Erori de ≥2 niveluri

| Lot | Rută | Forme | Scor anterior | Automat | Rată automată | Cost anterior → automat | Erori automate la nivel uman 4 | La nivel uman 5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Pilot 150, grup exclus | wordfreq | 101 | 28 | 9 | 8,9% | 47 → 12 | 2/2 | 3/3 |
| Pilot 150, grup exclus | fallback | 49 | 10 | 2 | 4,1% | 13 → 2 | 0/19 | 0/19 |
| Risc 50 | wordfreq | 5 | 4 | 1 | 20,0% | 6 → 2 | fără exemple | 1/1 |
| Risc 50 | fallback | 45 | 9 | 12 | 26,7% | 12 → 12 | 0/9 | 0/5 |

Wordfreq trece limita de eroare globală pe pilot. Însă pe cele două forme de nivel 4, comparatorul avea zero erori severe, iar wordfreq are două: `pag` primește 2 și `tara` primește 1. În lotul de risc, o eroare pe cinci forme depășește pragul propus, iar cinci forme sunt sub minimul de suport. Pe pilot, scorurile înghețate ajustate pe toate etichetele dau 8/101 erori pentru wordfreq și 2/49 pentru fallback. Validarea cu grup exclus dă 9/101 și 2/49. Raportul păstrează separat ambele măsurători.

Fallback-ul trece pe pilot și eșuează pe lotul de risc. Toate cele 12 erori severe din acel lot sunt forme de nivel uman 2 care primesc 4, inclusiv `tunet`, `ghemuit` și `împrejurare`. Costul total rămâne egal cu al comparatorului, deși mai multe forme depășesc toleranța. Toate cele 24 de forme de nivel 5 de pe ruta fallback primesc 4, în toleranța acceptată. Lotul de risc a fost selectat tocmai pentru dezacorduri. Ratele din tabel descriu aceste loturi, iar precizia pentru întreaga populație rămâne necunoscută.

## Impact pe cele 77.698 de rânduri

Frecvența este prezentă pe 11.610 rânduri, dintre care 11.492 eligibile pentru simulare după protejarea evaluărilor. Pentru fallback, numerele sunt 66.088 și 65.973. Fiecare scenariu produce un CSV complet. Cele trei coloane procentuale folosesc auditul existent, cu referința post-corecții și cu aceleași 128 de ancore.

| Scenariu | Rânduri schimbate | Forme schimbate | Schimbări ≥2 față de snapshot | Jaccard L1 | Apartenență la ancore | Recall ancore |
|---|---:|---:|---:|---:|---:|---:|
| Păstrăm scorurile existente | 0 | 0 | 0 | 100% | 4,77% | 42,97% |
| Numai wordfreq | 7.537 | 7.131 | 3.253 | 35,87% | 5,89% | 56,25% |
| Numai fallback | 43.187 | 41.878 | 3.350 | 70,89% | 6,82% | 42,97% |
| Ambele | 50.724 | 49.009 | 6.603 | 16,71% | 8,22% | 56,25% |

Schimbările de ≥2 față de snapshot măsoară amploarea intervenției. Erorile severe din primul tabel sunt măsurate față de evaluări umane. Scenariul fallback include 30.524 de treceri 5→4. Niciun scenariu nu trece toate pragurile operaționale 70%/80%/80%. Lista pozitivă de ancore are acoperire incompletă. Apartenența la listă nu estimează precizia semantică globală.

## Pasul recomandat

Prioritatea este protejarea formelor familiare trimise la 4. Pentru următorul experiment, testați o singură regulă de păstrare a scorului existent când lipsește frecvența și schimbarea propusă ar fi de ≥2 niveluri. Aplicați aceeași regulă întregului lot, inclusiv cazurilor unde scorul vechi greșește. Măsurați perechile „eroare introdusă / eroare eliminată” pe ambele cohorte și costul pe 4/5. Regula ar afecta 3.350 dintre schimbările fallback propuse. Acesta este un experiment de reducere a riscului pentru fallback, fără a soluționa suportul mic al rutei wordfreq în lotul de 50. Pentru wordfreq păstrăm verdictul provizoriu și cele cinci exemple drept limită explicită. Nu cerem alte evaluări. Orice promovare operațională necesită o decizie separată și verificările obligatorii.

## Reproducere

Din checkout-ul proiectului, cu datele istorice în directorul local `build/d1`, indicați un director nou pentru rezultate.

```sh
PYTHONPATH=src python docs/research/2026-11-05-automatic-promotion/run.py \
  --base /cale/catre/build/d1 --output /cale/noua/simulare
```

Hashurile celor șapte CSV-uri sunt fixate în politică și verificate înainte și după calcul. Cele două rulări au produs șase artefacte identice byte cu byte (patru scenarii, evaluări, raport). O reconciliere separată a verificat erorile din predicțiile sursă, ID-urile schimbate, disjuncția rutelor și protecția tuturor rândurilor umane. Rulările au folosit un guard local pentru conexiuni DB, rețea și procese de inferență. CSV-urile generate rămân locale. [Politică](2026-11-05-automatic-promotion/policy.json) · [Raport agregat](2026-11-05-automatic-promotion/report.json) · [Hashuri](2026-11-05-automatic-promotion/manifest.json).

## Rezultatul regulii de păstrare la salturi de ≥2

**Recomandăm respingerea regulii ca politică generală de promovare.** Pe lotul de risc protejează trei forme familiare. Pe pilot anulează două corecții utile pentru cuvinte rare. Loturile au selecții diferite și prea puține intervenții pentru o concluzie despre întregul inventar.

Pentru fiecare formă fără frecvență am păstrat scorul anterior când diferența absolută dintre propunere și scorul anterior a fost de cel puțin două niveluri. Am folosit aceleași predicții înainte de override și minimul istoric peste POS, din copia anterioară corecțiilor umane. Pe pilot am folosit predicțiile cu grup exclus, pe lotul de risc scorurile înghețate. Am folosit evaluarea umană doar pentru calculul erorii.

O eroare **evitată** trece de la ≥2 la ≤1 față de evaluarea umană. O corecție utilă **pierdută** trece de la ≤1 la ≥2. În aceste date, toate cazurile care se apropie sau se îndepărtează de evaluare trec și acest prag. Un caz păstrează aceeași distanță.

| Lot | Forme fără frecvență | Regula se activează | Evitate | Pierdute | Severe pe fallback, înainte → după | Severe pe tot lotul | Cost peste toleranță, tot lotul |
|---|---:|---:|---:|---:|---:|---:|---:|
| Pilot 150 | 49 | 2 | 0 | 2 | 2 → 4 | 11 → 13 | 14 → 18 |
| Risc 50 | 45 | 4 | 3 | 0 | 12 → 9 | 13 → 10 | 14 → 11 |

| Lot și nivel uman | Forme fără frecvență | Evitate | Pierdute | Severe pe fallback | Severe pe toate formele de acel nivel |
|---|---:|---:|---:|---:|---:|
| Pilot, 4 | 19 | 0 | 1 | 0 → 1 | 2 → 3 din 21 |
| Pilot, 5 | 19 | 0 | 1 | 0 → 1 | 3 → 4 din 22 |
| Risc, 4 | 9 | 0 | 0 | 0 → 0 | 0 → 0 din 9 |
| Risc, 5 | 5 | 0 | 0 | 0 → 0 | 1 → 1 din 6 |

Pilotul pierde la *caftan* (uman 4, fallback 4, anterior 1) și *micșurat* (uman 5, fallback 4, anterior 2). În lotul de risc, *urni* și *rănire* ajung la 2, iar *utilizabil* la 1. Toate trei au evaluare umană 2. Pentru *discreditat*, evaluat cu 3, atât fallback-ul 4 cât și scorul anterior 2 sunt la distanță de un nivel. Acestea sunt toate cele șase activări.

Pe lotul de risc rămân 9/45 erori severe la fallback (20%), peste limita exploratorie de 10% din simularea inițială. Recomandăm păstrarea saltului ca indicator de dezacord pentru audit și închiderea acestei variante. Ambele rute rămân provizorii.

**Reproducere.** După generarea fișierului local `evaluations.csv` prin comanda de mai sus, rulați din același checkout:

```sh
PYTHONPATH=src python docs/research/2026-11-05-automatic-promotion/bounded_fallback.py \
  --evaluations /cale/noua/simulare/evaluations.csv --output /cale/noua/regula
```

Runnerul verifică hashul evaluărilor pereche și exportă toate cele 200 de comparații în `paired.csv`, sumarul pe lot/rută/nivel și hashurile artefactelor. Verificarea separată a reconstruit decizia pentru fiecare formă din sursele originale și a reconciliat toate cele 18 rânduri agregate. [Rezultate agregate](2026-11-05-automatic-promotion/bounded-summary.csv) · [Hashuri](2026-11-05-automatic-promotion/bounded-manifest.json).
