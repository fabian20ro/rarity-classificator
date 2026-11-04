# Remediere lexicală și experiment pereche limitat — 2026-10-31

Scorurile umane rămân referințe imuabile. Exporturile lexicale și propunerile modelului
sunt artefacte separate; nicio evaluare umană nouă, nicio scriere în DB, niciun model
local încărcat. GPT este solicitat/configurat ca `gpt-6.1-sol`, efort `low`, prin
transportul Codex deja folosit. Identitatea servită nu este atestată de furnizor.

## Corecții generale, prin TDD

Interfețe deja aprobate: surse locale → CSV cu dovezi/proveniență; CSV + referințe
existente → predicții și raport. Extinderea nu introduce reguli de scor per cuvânt.

- Exportul recuperează intrări MDA cu **headword exact**, POS explicit și gramatică
  simplă verificabilă: definiții numerotate sau o definiție singulară. Ignoră
  indicii tipografici goi, păstrează restricțiile sensului și sursa exactă.
- Fără restaurarea diacriticelor, extinderea flexiunilor cu `~`, deducții din
  pronunție sau transfer automat de la sinonime. Formatele neînțelese nu furnizează
  aserțiuni noi; dovezile din arborii existenți rămân disponibile.
- Trimiterile numerice interne între paranteze sunt respinse conservator: în
  „urat”, numărul din `urări (2)` nu poate crea două fragmente declarate sensuri.
- Proiecția păstrează `form_relation`: forma exactă, headingul sursă, relația
  literală/flexionară/variantă explicită. Validarea respinge contradicții
  ortografice, identități modificate și câmpuri ascunse de scor.
- `missing_definition_pos` distinge și genurile substantivale. „Avem un sens
  substantival” nu mai maschează lipsa sensului neutru când există doar feminin.
  După reunirea contextelor curate, acoperirea este recalculată.
- Pilotul folosește acum aceeași proiecție verificată ca lotul nou; șapte forme
  pierd sensuri de prefix/sufix fără POS de cuvânt întreg. Contextele curate
  existente sunt păstrate cu aceeași proiecție lexicală, potențial expusă etichetelor.

Constatări documentare:

| Formă | Corecție / limită |
|---|---|
| ceruit | MDA oferă adjectivele „dat/uns cu ceară”, „lustruit”; exportul vechi avea doar substantivul. |
| ozene | MDA atestă substantiv neutru legat de obiecte zburătoare, marcat livresc; exista doar femininul medical în export. Explicația GPT nu dovedea o invenție lexicală. |
| otel | Relația explicită cu intrarea hotel ajunge acum în model. Nu este oțel; nu adăugăm diacritice. |
| tunet | Restricția rar era deja corect legată de un sens. Nu am generalizat-o la întreaga formă; se adaugă o definiție MDA neîngrădită. |
| pustnici | Nicio sursă exactă în cache-ul înghețat; rămâne lipsa definiției pentru verb. Nu inventăm sens și nu interzicem alte POS doar fiindcă lipsesc din surse. |

Export final: conținut lexical schimbat pentru **40/150** și **4/50**. Schimbările
includ definiții, POS și eliminarea sensurilor de afix; metadatele noi sunt mai largi.
Acoperirea rămâne limitată la sursele locale, niciodată exhaustivă.

## Protocol înghețat

30 forme: 5 diagnostice deja discutate, 15 modificări de conținut selectate prin
hash stabil, 10 controale cu intrări identice. Distribuție:19 din pilot,11 din
runda recentă. Controalele sunt5+5; restul14+6 primesc corecția.

Două sesiuni proaspete per formă, **60 apeluri secvențiale**, brațe în ordine
alternată. A=dovezi vechi; B=dovezi corectate, cu excepția controalelor identice.
Același prompt, model cerut, rubrică, schemă și configurare. Fără scoruri umane,
frecvențe, predicții anterioare sau exemple calibrate în cereri. Nicio ajustare
și nicio alegere a variantei după rezultate.

Criteriu principal: eroare absolută≥2. Cost suplimentar: `max(eroare−1, 0)`.
Raport separat pe pilot/runda50 și pe adevărat4/5. Condiția pentru un eventual
experiment pereche mai mare: fără creștere a erorilor severe/costului în niciun
lot sau clasă4/5. Nicio promovare operațională permisă de acest test mic.

Separat: sensibilitate retrospectivă pe toate150 și toate50, cu predicțiile vechi:
GPT dacă existau sensuri, altfel baseline. Regula este post-hoc; nu validare
independentă și nu estimare pentru cele950 fără etichete.

Prima pornire a clientului a fost blocată de sandbox înainte de crearea sesiunii.
Chitanța eșuată rămâne în v2; v3 folosește aceleași intrări/selecție și permisiunile
necesare pentru pornire. Zero rezultate lexicale din tentativa eșuată.

## Rezultate

**Niciun câștig demonstrat din corecția dovezilor asupra erorilor≥2.**

| Subset pereche | N | GPT vechi → corectat: severe | Cost suplimentar | MAE |
|---|---:|---:|---:|---:|
| Pilot, inclusiv controale |19|0 → 0|0 → 0|0,526 → 0,579|
| Runda recentă, inclusiv controale |11|4 → 3|5 → 4|1,455 → 1,364|
| Pilot, doar intervenție |14|0 → 0|0 → 0|0,571 → 0,643|
| Runda recentă, doar intervenție |6|3 → 3|4 → 4|1,667 → 1,667|

Reducerea aparentă din runda recentă provine **exclusiv din controlul prășit**:
aceeași cerere, scor GPT2→3, referință4. Celelalte9 controale sunt identice.
În intervenție, singura schimbare de scor este iț:5→4, referință5; abatere tolerată
≤1, fără reducerea erorilor mari. Nu atribuim variația unui control corecției.

| Referință | Pilot N | Severe vechi → corectat | Runda recentă N | Severe vechi → corectat |
|---|---:|---:|---:|---:|
|4|6|0 → 0|2|2 → 1, numai controlul|
|5|3|0 → 0|3|2 → 2|

ceruit rămâne2 față de referința4; ozene3 față de5; pustnici2 față de5.
otel rămâne4 față de5; tunet1 față de2. Corectitudinea unui sens nu măsoară
familiaritatea formei. Scorurile tale nu sunt rescrise pentru a potrivi modelul.
Nu am retestat Qwen; eroarea sa documentată otel→oțel nu este declarată rezolvată
la nivel de comportament al modelului.

Condiția predeclarată de **neagravare** trece, dar nu demonstrează eficacitate.
Nu justifică automat încă o campanie: beneficiul aparent se explică prin control.

Sensibilitate retrospectivă, toate referințele, predicții istorice nemodificate:

| Lot | Baseline severe / cost | GPT severe / cost | GPT cu sensuri, altfel baseline |
|---|---:|---:|---:|
|150|11 / 14|3 / 3|4 / 4|
|50 selectate după risc|13 / 14|19 / 25|9 / 11|

Poarta reduce totalul față de baseline, dar pe formele evaluate4 din runda recentă
crește erorile severe **0/9 → 2/9**; pe cele evaluate5 rămâne1/6. Nu o promovăm.
Nu agregăm loturile și nu extrapolăm la cele950 fără referințe.

## Recomandare și leftovers

Păstrăm remedierea lexicală și baseline-ul operațional. GPT rămâne propunere
separată. Fără prompt sweep sau încărcarea unui model local: testul nu susține că
mai multe definiții rezolvă eroarea de familiaritate.

Următorul experiment recomandat: **offline, fără apeluri LLM**, testarea unei porți
pentru reduceri de≥2 niveluri, folosind atât dovezi lexicale exacte, cât și atestările
de corpus deja existente. Praguri/regulă fixate înainte de comparație; analiză
pe familii și rezultate separate150/50, cu condiția să nu agraveze referințele4/5.
Nu folosim consensul modelelor drept adevăr și nu cerem etichete umane noi.

Rămân:19/150 și38/50 fără definiții; POS fără definiție la27/150 și38/50;
formate MDA complexe și trimiteri interne excluse conservator; validarea
comportamentului Qwen după metadatele noi. Nicio certificare a celor950 neadnotate,
nicio regenerare a scorurilor întregului inventar și nicio actualizare DB.

## Verificare și reproducere

TDD red→green: intrări MDA omise, respingerea trimiterilor numerice, relație
ortografică contradictorie. Regresii suplimentare: POS/gen, calificatori locali,
număr/POS conflictual, grafie exactă, markup neînțeles și actualizarea acoperirii
prin contextele curate. Revizia pe axe Standards/Spec a găsit două defecte
funcționale; ambele remediate înaintea experimentului.

**Ruff +932 teste +344 subteste PASS.** 60 sesiuni distincte,59 verificări de
neconcurență, aproximativ5,99minute. Toate4.468 fișierele protejate intacte.
Replay fără procese/rețea/DB:138 artefacte identice byte cu byte; metrici verificate
și prin aritmetică independentă. [Rezultate agregate](2026-10-31-evidence-repair/report.json)
și [verificare](2026-10-31-evidence-repair/verification.json).

Artefacte locale: `build/d1/evidence-repair-2026-10-31-v2/` pentru regenerare și
`build/d1/evidence-repair-2026-10-31-v3/` pentru campania validă. CSV-uri complete,
proveniență, protocol, intrări, chitanțe native și raport. Datele individuale,
conținutul dicționarelor și răspunsurile private nu sunt publicate în PR.

Scripturi: [prepare](2026-10-31-evidence-repair/prepare.py),
[freeze](2026-10-31-evidence-repair/freeze.py),
[run](2026-10-31-evidence-repair/run.py),
[analyze](2026-10-31-evidence-repair/analyze.py),
[verify](2026-10-31-evidence-repair/verify.py).

Din checkout-ul proiectului, cu mediul Python al proiectului și toate artefactele
locale păstrate; fiecare rulare cere un director nou:

```sh
PYTHONPATH=src python docs/research/2026-10-31-evidence-repair/prepare.py --base /cale/build/d1 --output /cale/build/d1/experiment-nou
PYTHONPATH=src python docs/research/2026-10-31-evidence-repair/freeze.py --base /cale/build/d1 --output /cale/build/d1/experiment-nou
PYTHONPATH=src python docs/research/2026-10-31-evidence-repair/run.py /cale/build/d1/experiment-nou
PYTHONPATH=src python docs/research/2026-10-31-evidence-repair/analyze.py --base /cale/build/d1 --output /cale/build/d1/experiment-nou
```

`prepare` este offline; `run` folosește autentificarea Codex existentă și poate
necesita execuție în afara sandbox-ului exterior pentru pornirea app-server-ului.
Fiecare sesiune de clasificare rămâne read-only, într-un director gol, cu
instrucțiuni de neutilizare a uneltelor. Evenimentele de unelte sau avertismentele
opresc campania; nu pretindem că facilitățile generice ale transportului lipsesc.
`analyze` și replay-ul unei campanii complete nu pornesc modele. Pentru verificarea
replay-ului, `verify.py` primește aceleași argumente ca `analyze.py`. Implementarea
măsurată este commitul `a196520`; protocolul fixează și hash-urile fiecărui fișier.
