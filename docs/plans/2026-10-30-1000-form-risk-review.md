# Plan curent: 1.000 de forme noi, maximum 50 de revizuiri

Actualizat: 2026-10-31. Stare: etapele1–4 încheiate;50/50 răspunsuri importate și comparate.
Rămâne o remediere generală a dovezilor și evaluarea ei limitată, fără alte etichete umane.
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
metadată legacy. Selecția și îmbinările au fost reproduse independent. Există acum
1.000 judecăți GPT și31 judecăți Qwen pe ruta fixată;50 referințe umane noi, selectate după risc.

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

### 2. Pilot al judecătorilor pe cele 150 existente

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
nici erorile severe pe missing49 sau referințele 4/5 față de baseline. Clarificarea
înghețată înainte de analiză cere și cost suplimentar fără regresie pe aceste două
segmente; raportăm separat poarta inițială și poarta completată. Acesta este
filtru exploratoriu, nu certificare. Un candidat care nu trece poate continua numai
ca detector de conflicte dacă îmbunătățește recuperarea erorilor severe baseline la
același buget față de trierea numai prin dovezi. Comparăm recall, precizia cozii și
alarmele false la **top8/150 global (5,33%)**, cu regulă fixată fără etichete.
Corecție înghețată înainte de inferență: top5 per fold înseamnă25/150=16,7%,
nu50/1000; rămâne doar diagnostic secundar. Nicio alegere a ordinii pe etichetele
formelor evaluate. Raportăm numărătorii mici, fără garanții; dacă
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

**Rutare înghețată, `exact-form-conflicts-v1`:** GPT pentru toate formele; Qwen
numai dacă GPT a răspuns valid, diferența GPT–baseline este ≥2 și există minimum
un context lexical utilizabil. Qwen primește aceeași dovadă lexicală, fără scorul GPT
sau baseline. Lipsa definițiilor/frecvenței nu declanșează singură inferență suplimentară.
Baseline-ul operațional se exportă separat; propunerea de cercetare este GPT valid,
altfel fallback baseline explicit. Qwen este diagnostic, fără medie/vot/suprascriere.

Coada eligibilă: eșec tehnic GPT sau diferență inițială GPT–baseline ≥2. Qwen nu are
drept de veto. Ordine lexicografică fixată înainte de cele1.000: eșec GPT; eșec Qwen;
dezacord Qwen–GPT ≥2; amplitudinea scorurilor descrescător; diferența inițială
descrescător; lipsă context; POS multiple; SHA256(`qwen-pilot-v1:` + ID). Maximum50,
fără completare artificială. Fișele se publică numai după încheierea rutei Qwen.
Contradicțiile lexicale cer verificare documentară separată; notele unui model nu
sunt dovezi suficiente pentru schimbarea sensurilor sau a cozii.

Verificare exploratorie pe150, fără căutare de praguri:12 apeluri Qwen eligibile,
13 forme eligibile pentru revizuire. Top8 găsește6/11 erori severe baseline și2/3 GPT;
toate8 au o eroare severă în cel puțin una dintre metode. Rămân nedetectate în coada
completă: baseline `carter`, `in`; GPT `carter`. Nicio excepție pentru aceste cuvinte.
Referințe de dezvoltare refolosite, fără pretenție de validare independentă.

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

**Audit și remediere a dovezilor locale**, cu grafie exactă, lecturi/POS și sensuri
susținute, restricții atașate sensului corect. Runda unică este completă și importată;
nu se mai cer evaluări sau exporturi utilizatorului.

[Comparația celor50 și auditul](../research/2026-10-31-review50.md): baseline13 erori≥2,
GPT19, cost14vs25. Pe cele12 cu Qwen disponibil: baseline7, GPT3, Qwen3; cost8/5/5.
Fără contexte (38): baseline6, GPT16. Pe referințe4/5 (15): baseline1, GPT14.
Păstrăm baseline-ul operațional; propunerile modelelor rămân separate. Nu promovăm
un hibrid ales după aceste rezultate. Următorul experiment trebuie predefinit după
remedierea dovezilor, cu evaluare exploratorie pe familii și150/50 raportate separat.

Cele50 nu estimează imparțial acuratețea celor1.000.950 sunt nerevizuite;121 conflicte
inițiale rămân peste buget. Acordul modelelor nu produce gold sau probabilități de
corectitudine. Nicio modificare DB, regenerare completă sau căutare largă de prompturi.

[Raportul celor1.000](../research/2026-10-31-1000-judges.md).


## Rezultatul etapei 1 — implementat și verificat

1.000/1.000 forme, 1.146/1.146 ID-uri păstrate. 130 forme cu contexte utilizabile:
121 acoperă POS din sursele disponibile, 9 parțial; 870 rămân fără context utilizabil.
62 cache-uri cu altă grafie excluse. Semnalele originale reverificate; scoruri intacte.
Ruff +893teste/241subteste pe branch-ul PR, replay identic și audit independent PASS.
Nicio inferență nouă, evaluare umană sau modificare DB.

[Rezultate, reproducere și limite](../research/2026-10-30-independent-evidence-audit.md).
Pilotul următor trebuie să măsoare explicit condiția fără definiții. Nu extrapolăm
calitatea pe cele150 asupra celor870 cu lipsuri și nu cerem utilizatorului să le
completeze manual. Relațiile lexicale fără martor rămân necunoscute.


## Rezultatul etapei 2 — Qwen, 2026-10-30

150/150 răspunsuri native valide în ambele campanii complete; secvențial, RAM verificat.
Scoruri și răspunsuri umane intacte. Modelul Qwen preexistent păstrat; fără D1/GPT/DB.

| Metodă | Erori≥2 | Cost suplimentar | În±1 | MAE |
|---|---:|---:|---:|---:|
| Baseline OOF |11|14|139/150|0,520|
| Qwen, dovezi inițiale |7|11|143/150|0,553|
| Qwen, toate contextele curate existente |5|9|145/150|0,527|

Corecție sistematică după primul rezultat:218 contexte existente/95forme omise de
proiecția veche. Proiecție lexicală explicită, cu cinci clauze adresate evaluatorului
eliminate;213 sensuri identice. Încercarea intermediară oprită la30 rezultate rămâne
separată, neanalizată. Campania finală rerulează toate150, prompt/opțiuni neschimbate.
Contexte curate anterior, potențial expuse etichetelor; nu validare independentă.

Pe43 referințe4/5: erori grave5→2. Missing-wordfreq49:2→1. Cu sensuri131:10→2;
**fără sensuri19:1→3**, cost1→6. Qwen corectează9 erori grave baseline, introduce3.
Top8 găsește4/11 erori baseline versus1/11 numai prin dovezi; patru alarme false.
Intervalele bootstrap includ zero. 12 scoruri diferă față de prima campanie, toate
în cele95 intrări completate;55 intrări neschimbate dau aceleași scoruri.

**Decizie:** porțile numerice exploratorii trecute; fără promovare generală.
870/1000 forme noi fără context blochează extrapolarea rezultatului agregat.
Păstrăm baseline, Qwen candidat diagnostic. GPT se compară pe aceleași dovezi;
abia apoi testăm o regulă combinată, înghețată explicit, și coada de maximum50.

Verificare:909teste+284subteste/Ruff, replay offline identic, audit independent;
1721fișiere protejate neschimbate. [Raport complet](../research/2026-10-30-qwen-judge-pilot.md).
Leftovers actualizate după pilotul GPT de mai jos: acoperirea lexicală a lotului nou,
politica cascadei și validarea riscului, inferența1000, auditul cauzelor, interfața≤50.
Nu există încă1000 etichete validate sau probabilități calibrate.


## Rezultatul etapei 2 — GPT prin Codex, 2026-10-31

150/150 răspunsuri native valide, sesiuni noi/secvențiale. Aceleași forme, dovezi finale
Qwen, rubrică și schemă; fără scoruri umane, frecvențe sau predicții în cereri.
GPT-6.1-sol/low configurat prin autentificarea Codex existentă; fără cheie API extrasă.
Înveliș generic Codex diferit de Qwen, instrumente disponibile dar zero utilizări
observate. Identitate configurată, nu ID servit atestat. Nu este comparație pură de
model sau test independent; contextele curate au expunere istorică la etichete.

| Metodă | Erori≥2 | Erori≥3 | Cost suplimentar | În±1 | MAE |
|---|---:|---:|---:|---:|---:|
| Baseline |11|3|14|139/150|0,520|
| Qwen corectat |5|4|9|145/150|0,527|
| GPT prin Codex |3|0|3|147/150|0,507|

GPT corectează10 erori grave baseline și introduce2; corectează toate5 Qwen și
introduce3 diferite: carter5→3, catalige4→2, târfă3→1. Zero intersecție a erorilor
grave GPT/Qwen observate; aceasta nu garantează că putem alege automat răspunsul
corect. Scorurile umane originale rămân intacte, inclusiv micșurat5 (GPT4, Qwen3).

Pe true4/5: baseline5, Qwen2, GPT2 erori grave. Missing-wordfreq49:2/1/2; GPT doar
îl egalează pe baseline. Cu sensuri131:10/2/3. Fără sensuri19:1/3/0, dar17/19 sunt
referințe1–2 și doar2/19 nu au wordfreq. Lotul nou are764/870 fără context și fără
wordfreq: performanța pe aceste forme rămâne necunoscută.

Top8 găsește6/11 erori baseline cu GPT (2alarme false),4/11 cu Qwen și1/11 numai prin
dovezi. Top25 GPT10/11 rămâne secundar, la16,7% revizuire. Bootstrap GPT-minus-baseline
favorabil exploratoriu; intervalele GPT-minus-Qwen includ zero. Acord exact GPT77
versus baseline86, dar criteriul acceptat este distanța≥2, nu potrivirea exactă.

**Decizie:** porțile exploratorii trecute; GPT candidat principal pentru experimentul
nou, Qwen diagnostic complementar, baseline operațional păstrat. Fără promovare DB,
încredere numerică sau ansamblu implicit. Nu mai căutăm prompturi pe aceleași150.

Verificare:915teste+303subteste/Ruff, replay fără procese/rețea/DB identic, audit
independent PASS,2092fișiere protejate intacte.150sesiuni distincte/149verificări de
neconcurență; aproximativ13minute. [Raport GPT](../research/2026-10-31-gpt-judge-pilot.md).

La închiderea pilotului rămâneau pregătirea/rutarea/campania1000 și interfața.
Acestea sunt încheiate în rezultatul etapei3 de mai jos; decizia despre scorurile finale
așteaptă runda de revizuire și analiza cauzelor confirmate.
Compatibilitatea API directă rămâne netestată; transportul Codex este cel măsurat.


## Rezultatul etapei3 și pregătirea rundei — 2026-10-31

1.000/1.000 GPT valide, apoi31/31 Qwen valide; zero fallback tehnic. Regula verificată
pe150 și înghețată înaintea lotului nou selectează171 conflicte GPT–baseline ≥2.
31 au contexte și au fost trimise la Qwen;11 dezacorduri Qwen–GPT ≥2. Fără combinare
numerică: baseline operațional păstrat, propuneri GPT în CSV separat.

| Segment | N | Dezacord GPT–baseline ≥2 | Apeluri Qwen | Fișe |
|---|---:|---:|---:|---:|
| General |600|88|18|20|
| Stres |400|83|13|30|
| Fără sensuri și fără wordfreq |764|130|0|34|

829/1.000 predicții GPT sunt la maximum1 de baseline; **nu înseamnă829 corecte**.
La închiderea etapei3 nu exista încă gold pe lotul nou. Coada are exact50 forme, inclusiv toate11 conflictele
mari GPT–Qwen;121 conflicte inițiale rămân în afara bugetului. Nicio cotă de completare,
înlocuire a fișelor sau probabilitate inventată.38 fișe nu au sensuri documentate;
această lipsă este afișată explicit. „Nu pot decide” rămâne fără scor.

Verificări:927teste+330subteste/Ruff; audit independent și replay fără procese/rețea/DB
PASS;1.000 sesiuni GPT distincte,999 verificări de neconcurență, Qwen ulterior;
4.456 fișiere protejate intacte. Aproximativ93,67minute GPT și2,51minute Qwen.
Baseline, răspunsurile vechi, modelele încărcate și DB nemodificate.

La închiderea etapei3 rămâneau răspunsurile rundei≤50, importul, auditul și o decizie
separată despre eventuale remedieri generale. Nu extrapolăm precizia celor50 asupra
celor950 nerevizuite; lipsa dovezilor pe764 rămâne limitarea majoră. Regenerarea întregului
inventar și orice actualizare DB rămân în afara acestui experiment.


## Rezultatul etapei4 — 50/50 importate, 2026-10-31

Exportul privat păstrează toate142 evenimentele, două observații și trei revizuiri
nete. Niciun ID/scor invalid; cele150 anterioare sunt distincte și intacte. Întreaga
coadă este evaluată; nicio rundă nouă. Comparația folosește numai predicții înghețate.

Baseline:13/50 severe, cost14. GPT:19/50, cost25; repară13 baseline și introduce19.
Cele12 comparabile cu Qwen:7/3/3 severe pentru baseline/GPT/Qwen, cost8/5/5; Qwen
include o eroare4 prin substituția explicită otel→oțel.32/50 au cel puțin o eroare
severă GPT/baseline; acesta este randamentul cozii, nu recall sau acuratețe globală.
Lipsa definițiilor și diferențele de rubrică rămân explicații de verificat; scorul
uman confirmă eroarea față de referință, nu mecanismul intern al modelului.

Verificare independentă și replay: PASS;4.456 fișiere protejate intacte;
Ruff+927teste+330subteste PASS. Importul, comparația și auditul au CSV-uri locale,
manifest și scripturi în PR. Datele individuale/CoRoLa rămân locale.

Leftovers: audit/remediere generală grafie–POS–sens–restricții; apoi un experiment
limitat cu regulă înghețată. Nicio promovare pe baza unei reguli post-hoc. Rămân
950 forme fără referințe; planul nu le certifică și nu cere alte etichete umane.
