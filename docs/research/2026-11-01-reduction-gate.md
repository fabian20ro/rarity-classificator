# Reduceri ≥2: filtru lexical + corpus, offline — 2026-11-01

**Candidatul nu trece criteriul de acceptare.** Totalul erorilor mari scade, dar
referințele4/5 se agravează. Baseline-ul operațional și scorurile umane rămân
intacte. Zero apeluri LLM, modele încărcate, descărcări sau scrieri în DB.

## Regula fixată înainte de comparație

Acceptăm propunerea GPT numai când toate condițiile sunt îndeplinite:

1. `baseline − GPT ≥ 2`, cu răspuns GPT existent și valid.
2. Cel puțin un sens utilizabil și nicio parte de vorbire cunoscută fără definiție.
   Acoperirea include genurile substantivale, dar rămâne limitată la surse.
3. Suport pentru forma exactă: FineWeb2≥5 apariții,≥3documente,≥2gazde **sau**
   CoRoLa≥5apariții. Praguri preluate din experimentele anterioare, fără ajustare.

În toate celelalte cazuri, candidatul păstrează baseline-ul. Nu aplică măriri sau
schimbări de un nivel. Toate150 și toate50 au scor candidat explicit, inclusiv
formele fără dovezi; refuzul unei reduceri nu devine rând omis.

Au fost fixate și comparațiile: baseline, GPT integral istoric, reduceri fără
filtre, numai lexical, numai corpus, lexical+corpus. Nu sunt șase reglaje de
praguri. Deciziile CSV sunt produse înainte de citirea etichetelor umane.

Criteriu: mai puține erori≥2 și cost suplimentar `max(eroare−1,0)` neagravat în
**ambele** loturi; fără agravarea numărului/costului erorilor în referințele4 sau5.
Nicio autorizare de promovare în producție, nici dacă acest criteriu ar fi trecut.

## Comparație completă, loturi separate

| Metodă | Severe /150 | Cost /150 | Severe /50 | Cost /50 |
|---|---:|---:|---:|---:|
| Baseline înghețat |11|14|13|14|
| GPT integral istoric |3|3|19|25|
| Numai reduceri≥2, fără filtre |8|11|20|27|
| Filtru lexical |9|12|10|13|
| Filtru corpus |8|11|20|27|
| **Lexical + corpus** |**9**|**12**|**10**|**13**|

GPT integral poate include și măriri utile; experimentul curent izolează reducerile.
De aceea coloana „numai reduceri” nu este identică cu GPT integral.

Candidatul acceptă8/9 reduceri propuse în pilot și11/49 în runda recentă. Pe150,
repară4 erori mari ale baseline-ului și introduce2; pe50 repară6 și introduce3.
MAE:0,520→0,493 pe150;1,080→1,060 pe50. Câștigul total nu compensează eșecul
criteriului predeclarat pentru clasele rare.

## Referințe4 și5

Diferența4↔5 este tolerată de criteriul utilizatorului. Aici urmărim în special
cazurile rare împinse cu minimum două niveluri spre comun.

| Lot / scor uman | N | Severe baseline → candidat | Cost baseline → candidat |
|---|---:|---:|---:|
|150 /4|21|2 → 3|3 → 4|
|150 /5|22|3 → 3|5 → 5|
|50 /4|9|0 → 2|0 → 3|
|50 /5|6|1 → 2|2 → 4|

Exemple de reduceri greșite acceptate: catalige în pilot; căldicel, ceruit și ozene
în runda recentă. Un sens valid și câteva atestări nu justifică automat un nivel
comun. Corpusurile numără grafia, nu sensul/POS-ul care a generat fiecare apariție.

Filtrul refuză și reduceri utile: fulg în pilot; șase forme în runda recentă.
Lipsa unei definiții/POS nu dovedește că forma este rară. Acesta este costul
conservator al condiției lexicale, nu motiv de rescriere a evaluărilor umane.

## Ce adaugă corpusurile

**Nicio decizie diferită față de filtrul numai lexical, pe cele200 de forme.**
CoRoLa trece57/58 reduceri propuse; FineWeb2 trece37/58. Cazul fără suport corpus
nu avea nici suport lexical. Prin regula OR, pragul CoRoLa de atestare este prea
permisiv pentru a bloca aceste reduceri nejustificate.

Rezultatul este despre regula aceasta și loturile acestea. Nu dovedește că
frecvența normalizată, distribuția pe documente sau corpusurile sunt inutile.
Frecvența și familiaritatea nu sunt echivalente; count≥5 era prag de atestare,
nu calibrare a unui scor2. Regula și pragurile înghețate au rămas neschimbate.

## Grupuri și limite

Pilot:142grupuri, maximum2forme/grup; runda recentă:50grupuri. Nicio formă exactă
sau cheie de grup comună între loturi. Gruparea existentă nu este o dovadă de
independență lingvistică exhaustivă.

Rata severă cu pondere egală per grup:6,69%→5,63% pe pilot și26%→20% pe runda
recentă. Diagnosticul pe cele cinci folduri existente:1→1,4→2,2→4,2→1,2→1 severe.
Foldul2 se agravează chiar dacă totalul se îmbunătățește. Nu s-a antrenat nimic:
acestea sunt diagnostice pe grupuri/folduri existente, **nu o nouă validare încrucișată**.

150 sunt referințe reutilizate;50 sunt selectate după risc și au fost deja analizate.
Ambele sunt acum date de dezvoltare. Contextele curate ale pilotului pot fi expuse
istoricului etichetelor. Rezultatele nu estimează precizia celor950 nerevizuite sau
a întregului inventar. Scorurile GPT sunt cele istorice complete, nu alese din
experimentul pereche ulterior pentru a favoriza candidatul.

## Recomandare și următorul pas

1. Păstrăm baseline-ul operațional și remedierea dovezilor. Filtrul nou rămâne
   experiment reproductibil, fără activare implicită.
2. Încheiem acest ciclu de reglaj pe etichetele reutilizate. Nici acest prag de
   atestare, nici [fallback-ul CoRoLa calibrat anterior](2026-10-28-corola-experiment.md)
   nu au trecut criteriul de eroare. Nu există justificare pentru o nouă căutare de
   praguri pe aceleași rezultate.
3. Următorul pas de inginerie recomandat: **CSV candidat conservator pentru inventar**,
   cu cele200 de evaluări umane explicite prioritare pentru formele exacte și
   baseline pentru rest; proveniență, statut verificat/provizoriu și conflicte
   păstrate separat. Aplicarea pe toate ID-urile/POS-urile aceleiași forme cere
   mapare exactă, fără restaurarea diacriticelor. Exportul nu este executat în
   această etapă și nu autorizează upload în DB.

Leftovers: acoperire lexicală incompletă, corpusuri fără dezambiguizare sens/POS,
separarea automată fiabilă4/5 și950forme fără referințe. Orice viitoare îmbunătățire
automată cere o ipoteză nouă susținută de dovezi independente; nu cerem alte
adnotări utilizatorului aici. Verificările Jaccard și precizie/recall pe ancore
rămân obligatorii înaintea oricărei viitoare operații de upload.

## Verificare și reproducere

- TDD la interfața CSV deja aprobată: praguri, identitate exactă, lipsă versus zero
  corpus, lipsă POS, eșec GPT, respingere etichete și date/proveniență corupte.
- Ruff + **936teste și354subteste PASS**. Revizie locală, fără subagenți sau apeluri LLM.
- **4.662fișiere protejate intacte**; referințe/scoruri originale nemodificate.
- Replay offline:8artefacte identice byte cu byte; aritmetică și referințe verificate
  separat. Procesele, rețeaua și DB sunt blocate în runner/verificator.
- Corpusuri locale existente: FineWeb2, subsetul curent2020–2024; CoRoLa Frequency
  Lists v1, Vasile Păiș2022, DOI10.5281/zenodo.7091535, cercetare necomercială conform
  permisiunii deja stabilite. Niciun download nou. CSV-urile cu date individuale și
  frecvențe CoRoLa rămân locale; PR-ul conține numai agregate și cod.

Artefacte locale: `build/d1/reduction-gate-2026-11-01/`, cu protocol și hashuri înainte
de comparație, intrări, două exporturi de decizii, comparații, raport și verificare.
[Raport agregat](2026-11-01-reduction-gate/report.json),
[verificare](2026-11-01-reduction-gate/verification.json).

Din checkout, cu mediul Python și sursele locale păstrate, într-un director nou:

```sh
PYTHONPATH=src python docs/research/2026-11-01-reduction-gate/freeze.py --base /cale/build/d1 --output /cale/build/d1/test-nou
PYTHONPATH=src python docs/research/2026-11-01-reduction-gate/run.py --base /cale/build/d1 --output /cale/build/d1/test-nou
PYTHONPATH=src python docs/research/2026-11-01-reduction-gate/verify.py --base /cale/build/d1 --output /cale/build/d1/test-nou
```

Toți pașii sunt offline. Directorul nou previne suprascrierea rezultatelor; verificatorul
reproduce exporturile în directoare temporare și compară octeții fără a relansa modele.
