# Plan curent: 1.000 de forme noi, maximum 50 de revizuiri

Data: 2026-10-30. Stare: plan aprobat ca direcție; lot local pregătit; implementarea
cascadei, evaluarea judecătorilor noi și revizuirea celor maximum 50 sunt încă de făcut.
Acest document înlocuiește recomandările viitoare incompatibile din
[planul istoric](2026-10-15-d1-classifier-evaluation.md), inclusiv prioritatea unui
fallback dedicat numai diferenței 4–5. Istoricul experimentelor rămâne păstrat.

## Obiectiv și limite

Clasificăm 1.000 de forme Scrabble noi, cu dovezi verificabile și scoruri complete,
concentrând intervenția umană pe maximum 50 de forme cu risc de eroare importantă.
Ținta: **forma exactă, prin cel mai familiar sens valid, peste toate POS valide**.
Diacriticele nu se restaurează implicit; familiaritatea lemei nu se transferă automat.
Scara rămâne 1=comun, 5=obscur; o diferență de ±1 este acceptabilă.

- Primar: numărul/rata erorilor `abs(predicție − referință) >= 2`.
- Secundar: costul `max(abs(predicție − referință) − 1, 0)`; erorile 2/3/4 costă 1/2/3.
- Diagnostice obligatorii: erori separate 2/3/4, MAE, acord exact, distribuția
  predicțiilor, forme fără wordfreq, referințe 4/5 și proveniența etichetelor.
- Acoperire 100%: fiecare formă are scor 1–5, rută, dovezi și stare a încrederii.
  Eșecul tehnic folosește baseline-ul explicit; nu devine acord sau succes al modelului.
- Maximum 50 de forme cerute utilizatorului, într-o singură rundă. Nicio cotă ascunsă
  de audit aleator; nicio nouă evaluare a celor 150 deja notate.
- Fără modificări în DB, scorurile înghețate sau răspunsurile originale. Nicio promovare
  automată în producție. Step5, gating-ul Jaccard/ancore și upload partial rămân intacte.

## Ce știm deja

Baseline-ul wordfreq + fallback 4 rămâne recomandarea operațională. Experimentele D1
cu formulări, Choice/Score/Noul, definiții și few-shot nu au justificat înlocuirea lui.

| Metodă, pilot 150 | Erori ≥2 | Cost suplimentar total | MAE |
|---|---:|---:|---:|
| Baseline, evaluare OOF pe grupuri | 11 | 14 | 0,520 |
| D1 control Choice | 48 | 84 | 1,167 |
| D1 control Score | 43 | 45 | 1,120 |
| D1 few-shot Score | 35 | 52 | 1,147 |
| D1 relativ Score | 38 | 54 | 1,153 |

[Snapshotul metricilor](2026-10-30-1000-form-risk-review/severity.csv) include toate
cele nouă variante primare. Analiza secundară Choice cu mediană are minimum 29 erori
severe; nici aceasta nu depășește baseline-ul. Cele 150 sunt date de dezvoltare
refolosite, nu un test independent: 113 referințe inițiale opace și 37 clarificate.

Few-shot Score a redus numărul erorilor severe, dar a crescut costul lor: 124/150
predicții au devenit 2; toate cele 22 de referințe 5 au eroare ≥2. Separat, pe 23 de
forme fără definiții, erorile severe Choice au crescut 4→10 cu exemple. Toate ancorele
aveau definiții: nepotrivirea dovezilor este o ipoteză de investigat, nu o cauză dovedită.

**Decizie:** oprim căutarea largă de prompturi D1. Verificăm judecători diferiți și
calitatea dovezilor. D1 rămâne comparator diagnostic, fără vot suplimentar pentru
fiecare prompt sau mod Choice/Score/Noul.

## Lotul pregătit și proveniența

[Rezumatul înghețat](2026-10-30-1000-form-risk-review/sample-summary.json):
1.000 forme / 1.000 familii ortografice, reprezentând 1.146 rânduri de inventar/POS.
600 familii alese aleator cu seed fix, o grafie per familie; 400 cazuri de stres,
câte 100 pentru diacritice/grafii, POS multiple, lipsă wordfreq cu suport în corpusuri,
respectiv suport slab/absent. Cele cinci segmente sunt disjuncte.

Excluse 185 de familii din pilot și rezervările anterioare. 149 forme au wordfreq,
851 nu au; 97 au un martor lexical exact în cache. Martorul nu certifică toate
sensurile/POS. Această lipsă de suport este mult mai frecventă decât în pilot
(49/150 fără wordfreq); performanța pilotului nu se extrapolează automat.

Artefactele locale existente, relative la workspace-ul original:
`build/d1/independent-1000-2026-10-30/{forms.csv,vocabulary.csv,signals.csv,manifest.json,verification.json}`.
`forms.csv` păstrează toate ID-urile/POS/codurile LOC; `vocabulary.csv.type` este numai
metadată legacy. Selecția și îmbinările au fost reproduse independent. Nu există încă
judecăți multi-model sau etichete umane noi pentru aceste 1.000 de forme.

Sursele locale: inventarul Scrabble, exportul wordfreq înghețat, cache-ul lexical și
definițiile rebus, frecvențele/concordanțele FineWeb2 și CoRoLa deja colectate.
Nu sunt necesare descărcări noi pentru faza de semnale. Datele CoRoLa și CSV-ul derivat
`signals.csv` rămân locale, pentru cercetarea necomercială autorizată; nu intră în PR.
Manifestele trebuie să păstreze licența, versiunea, calea și hash-ul sursei.

## Implementare: etape și porți de decizie

Fiecare etapă produce CSV-uri explicite și manifest. Schimbarea rubricii, surselor,
promptului, modelului sau parserului cere o campanie nouă; reluarea incompatibilă e
respinsă. Implementare TDD pe interfețele publice, câte o felie verificabilă.

### 1. Fixarea contractelor și verificarea dovezilor

Depinde de: lotul înghețat. Reutilizăm extragerea lexicală existentă și identitatea
formei, fără un framework nou sau cuplare la upload.

- `forms.csv` → `contexts.csv`: grafie exactă, POS, sens, restricții, martor de variantă,
  identificator/sursă/hash; lipsa sau ambiguitatea rămân explicite.
- Surse locale → `signals.csv`: frecvențe/absențe distincte, proveniență, concordanțe
  când există; fără dublarea artificială a corpusurilor sau a paginilor copiate.
- Audităm legăturile lexicale explicite dintre familii; coliziunile ortografice nu
  sunt singura protecție împotriva contaminării. Nu schimbăm lotul după rezultate.
- Teste RED/GREEN: `ata`/`ață`, POS multiple, parent greșit, restricții de număr,
  lipsă definiție/frecvență, variante neconfirmate și zero ID-uri pierdute/dublate.

**Poartă:** 1.000 de forme și toate cele 1.146 rânduri mapate; fiecare context utilizat
are proveniență; nealinierea nu produce sensuri inventate. Lipsurile nu blochează
baseline-ul, dar blochează orice pretenție de încredere mare bazată pe sensuri complete.

### 2. Pilot independent al judecătorilor pe cele 150 existente

Depinde de: etapa 1 și intrările pilotului. Qwen Splash și GPT-6.1-sol, reasoning low,
sunt candidați; verificăm identitatea/configurația exactă înainte de rulare.

Aceleași dovezi validate, rubrică și format de răspuns; fără scorul uman al țintei,
fără predicțiile celuilalt. Prompt fixat înainte de rezultate. Dacă folosim ancore,
numai din grupurile de antrenare; comparațiile de variante se aleg în interiorul
antrenării. Opinia asistentului după inspectarea rezultatelor este diagnostic, nu vot
independent. Judecătorii diferiți pot totuși împărți greșeli.

- Local: un model încărcat odată; RAM verificat înainte de încărcare și între apeluri.
  Apeluri LLM secvențiale, inclusiv între furnizori. Qwen încărcat intenționat în faza
  proprie este păstrat; reapariția lui într-o fază D1 este tratată conform autorizării
  existente. Nu dezactivăm servicii externe care îl încarcă.
- CSV de predicții + schimburi brute + manifest: model/config, prompt/hash, timp,
  eroare tehnică/retry, score, surse. Nu solicităm raționament intern; doar referințe
  scurte la dovezi și flaguri verificabile.
- Teste: validare strictă 1–5/identitate, secvențialitate, checkpoint după întrerupere,
  lipsă gold în request, incompatibilitate manifest; apoi verificare pe răspunsuri reale.

**Poartă:** raport paired pe aceleași 150, cele 37 clarificate și missing49; distribuții,
erori 2/3/4, cost și suprapunerea greșelilor. Un candidat general poate continua ca
scorer propus numai dacă reduce erorile ≥2 sub 11 și nu crește costul peste 14,
nici erorile severe pe missing49 sau referințele 4/5 față de baseline. Acesta este
filtru exploratoriu, nu certificare. Un candidat care nu trece poate continua numai
ca detector de conflicte dacă îmbunătățește recuperarea erorilor severe baseline la
același buget față de trierea numai prin dovezi. Comparăm recall, precizia cozii și
alarmele false la top 5 din fiecare fold (aproximativ bugetul 50/1.000), fără alegerea
ordinii pe etichetele foldului testat. Raportăm numărătorii mici, fără garanții; dacă
nu există câștig, oprim evaluatorul diagnostic.

### 3. Înghețarea cascadei, a riscului și rularea celor 1.000

Depinde de: raportul etapei 2. Înghețăm protocolul înainte de rezultatele lotului nou.
Baseline + semnale pentru toate; dacă există un judecător util, o trecere semantică
pentru toate. Al doilea judecător numai pe ruta de conflict/lipsuri fixată pe pilot.
Dacă niciunul nu aduce valoare, păstrăm baseline-ul și trierea prin dovezi; fără o nouă
căutare nelimitată de prompturi.

Schema minimă `predictions.csv`: form_id, score, method, route, evidence_status,
technical_status, risk_band, reason_flags, manifest_id. O combinație numerică a
metodelor este permisă doar dacă regula sa a trecut aceeași evaluare fără leakage;
în lipsa ei, scorul final rămâne baseline și judecătorii furnizează semnale de audit.

**Regulă inițială pentru al doilea judecător:** conflict de minimum 2 niveluri cu
baseline-ul, identitate/POS/sens nerezolvat sau contradicție corpus–sens. Simpla lipsă
wordfreq nu declanșează încă un apel pentru toate cele 851 de forme; rămâne un flag.
Validăm acoperirea erorilor severe a acestei rute pe pilot și o fixăm înainte de rulare.
Orice schimbare înseamnă protocol nou, declarat ca exploratoriu.

Riscul vizează `P(eroare >= 2)`, nu probabilitatea clasei favorite. Implicit folosim
benzi ordinale și `unknown`. Fiecare bandă publică numitorul și erorile observate;
nicio probabilitate numerică de corectitudine fără calibrare verificată. Dacă învățăm
ponderi/praguri, totul se reface în foldurile de antrenare, inclusiv predicțiile folosite
ca features; nu antrenăm pe erori OOF globale apoi pretindem validare outer-heldout.

**Poartă:** exact 1.000 scoruri, niciun ID inventat, rute/fallback-uri vizibile; replay
fără rețea reproduce raportul. Separăm cele 600 generale de cele 400 de stres.
Raportăm și formele necunoscute; acordul mai multor metode nu devine etichetă gold.

### 4. Auditul cauzelor și maximum 50 de fișe

Depinde de: etapa 3. Întâi corectăm problemele mecanic verificabile ale dovezilor;
nu folosim predicțiile ca autoritate pentru schimbarea sensurilor. După orice corecție,
păstrăm campania inițială și rulăm din nou formele afectate cu manifest nou, înainte
de înghețarea cozii. Nu trimitem contradicții eliminate deja de corectarea surselor.

| Categorie de ipoteză | Verificare / intervenție generală |
|---|---|
| Grafie sau diacritice substituite | Identitate exactă, contrast antrenat fără expunerea țintei |
| Lemă/flexiune/variantă confundată | Martor explicit, restricții, fără transfer implicit |
| POS ori sens familiar omis | Completare din surse, toate POS valide |
| Definiție înțeleasă confundată cu familiaritate | Rubrică separând sensul de uzul formei |
| Nume proprii, citări, copii | Concordanțe și diversitatea surselor |
| Lipsa corpusului interpretată ca obscuritate | Missing explicit, fallback și risc separat |
| Nivel/rubrică interpretat diferit | Ancore numai din antrenare; controlul distribuției |
| Răspuns invalid/incomplet | Validare și fallback tehnic explicit |

Flagurile pot coexista. Raportăm rate și cost pe grupuri cu numitori; nu numim
explicațiile unui model „probabilități ale cauzelor”. Un scor uman confirmă eroarea, nu cauza ei. Cauza cere martor lexical verificabil
sau intervenție controlată; în lipsa acestora rămâne ipoteză.

`review-queue.csv` fixează cel mult 50 form_id înainte de afișarea răspunsurilor.
Prioritate: identitate/sens care poate schimba scorul cu ≥2, conflicte între surse
credibile și extreme incompatibile cu toleranța; apoi diversitate de cauze/familii.
Ordinea exactă și tie-break-ul determinist se îngheață pe pilot. Dezacordul 1 vs 3
poate avea adevărul 2; span ≥2 nu demonstrează singur eroare severă. 4 vs 5 singur
nu justifică fișă. Nu completăm artificial până la 50 și nu înlocuim ulterior fișele
răspunse cu alte întrebări care ar depăși bugetul total.

Interfață: o fișă/formă, grafie exactă, sensuri/POS relevante și surse, estimările
ascunse implicit; jurnal al expunerii lor. Răspunsurile deja date rămân intacte.

**Poartă:** buget total ≤50, persistare/reluare fără pierdere, fără estimări dezvăluite
accidental. Restul formelor incerte păstrează scor provizoriu și stare explicită.

### 5. Remedieri țintite și decizie finală

Depinde de: etapa 4. Analizăm cauzele confirmate și costul lor în eșantionul revizuit.
Alegem o remediere generală per cauză importantă, cu ablație și grupuri excluse fixate
înainte de rerulare. Fără excepții memorate pentru cuvinte; fără sweep-uri repetate.
Cele maximum 50 de cazuri selectate devin date de dezvoltare după utilizarea lor.

Livrabile: `comparison.csv`, `cause-audit.csv`, `review-responses.csv`,
`final-scores.csv`, manifest și raport cu ce păstrăm, ce respingem și ce rămâne incert.
Testele TDD și `python scripts/check.py` trebuie să treacă; verifier separat verifică
identități/hash-uri, replay și scorurile originale neatinse.

**Poartă finală:** păstrăm baseline-ul dacă nu există câștig susținut fără daune în
segmentele vulnerabile. Eventuala înlocuire în producție necesită o decizie separată;
acest plan livrează cercetare, CSV și recomandare, nu update de bază de date.

## Limitele concluziilor și rollback

Cele 50 de cazuri dificile nu estimează imparțial acuratețea celor 1.000; nu certifică
restul de 950. Pilotul refolosit și lotul cu multe lipsuri nu permit garanții de tip
„95% corecte”. Încrederea mare trebuie susținută de dovezi și evaluare adecvată;
în lipsa lor, rezultatul rămâne provizoriu. Nu cerem alte etichete pentru a ascunde
această limitare.

Schimbările rămân în modulele offline de evaluare, cu două limite publice:
surse → CSV cu dovezi; CSV + judecăți/referințe → predicții, audit și coadă de revizuire.
Separăm I/O și inferența de regulile pure de scor/risc; reutilizăm componentele existente,
fără orchestrator generic. Fiecare felie de implementare rămâne mică și testabilă.

Rollback: oprirea campaniei păstrează checkpoint-urile; retragerea unei metode schimbă
numai un export nou, niciodată scorurile originale. Nu există operații DB de inversat.

## Următoarea acțiune concretă

**Etapa 1**, apoi **pilotul Qwen/GPT pe cele 150**. Nu începem cu încă 1.000 de
apeluri D1 și nu trimitem utilizatorului fișe înainte de trierea dovezilor și a riscului.
Acest PR publică planul și două snapshoturi descriptive; campaniile locale complete,
implementarea experimentală necomisă și datele CoRoLa nu sunt incluse.
