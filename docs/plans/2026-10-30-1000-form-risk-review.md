# Plan curent: 1.000 de forme noi, maximum 50 de revizuiri

Actualizat la 5 noiembrie 2026. Lotul uman a fost aplicat și verificat, iar
integrarea în main s-a încheiat prin PR87. Simularea pentru cele 50.724 de
schimbări automate recomandă păstrarea ambelor rute ca provizorii. Regula de
păstrare a scorului vechi la salturi de ≥2 a fost testată și respinsă.
[Rezultate pe rute și cohorte](../research/2026-11-05-automatic-promotion.md).

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
- Limita inițială a experimentelor: fără modificări în DB, scorurile înghețate sau
  răspunsurile originale. Etapele20–22 execută separat operațiile ulterior autorizate;
  răspunsurile originale rămân intacte. Nicio promovare automată în producție. Step5, gating-ul Jaccard/ancore și upload partial rămân intacte.

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

La închiderea etapei4 urmau auditul/remedierea grafie–POS–sens–restricții și un
experiment limitat cu regulă înghețată; realizate în etapa5 de mai jos. Nicio promovare pe baza unei reguli post-hoc. Rămân
950 forme fără referințe; planul nu le certifică și nu cere alte etichete umane.


## Rezultatul etapei5 — dovezi corectate, test pereche limitat, 2026-10-31

Implementare TDD la limitele CSV deja aprobate: intrări MDA exacte cu POS/restricții
și proveniență; relația grafiei cu intrarea-sursă păstrată în cerere; acoperire POS
cu distincția genurilor și recalculare după contextele curate. Fără restaurarea
diacriticelor sau sensuri inventate din numere de trimitere. Revizia a găsit două
defecte; regresii red→green înaintea colectării. Commit implementare:`a196520`.

Conținut lexical schimbat40/150 și4/50, fără modificarea scorurilor umane.
ceruit recuperează adjectivul; ozene recuperează neutru livresc; otel păstrează
explicit relația cu hotel. Pustnici rămâne fără sursă exactă; lista POS nu devine
interdicție pentru sensurile încă nedocumentate. Afixelor nu li se atribuie automat
sensuri ale unui cuvânt întreg.

30 forme înghețate:19pilot+11runda recentă; două brațe proaspete,60 apeluri GPT
secvențiale, prompt identic. Zece controale primesc intrări identice. Pilot:
0/19→0/19 erori≥2; runda recentă:4/11→3/11. **Îmbunătățirea este exclusiv în
controlul prășit**, cu aceeași cerere. În intervenția efectivă:0/14→0/14 și3/6→3/6;
nicio dovadă de reducere a erorilor mari prin corecțiile lexicale. iț se schimbă5→4,
față de referința5; abatere tolerată. 9/10 controale sunt identice, unul diferă cu1.

Pentru4/5: pilot0/6 și0/3 severe în ambele brațe; runda recentă2/2→1/2 numai prin
control, respectiv2/3→2/3. Neagravarea predeclarată trece; eficacitatea nu este
arătată. Nicio promovare sau extindere automată a campaniei.

Pe predicțiile istorice complete, poarta „GPT numai cu sensuri, altfel baseline”
produce4/150 severe/cost4 și9/50/cost11, față de baseline11/150/cost14 și13/50/cost14.
Este post-hoc și agravează referințele4 din runda recentă:0/9→2/9 severe. Nu o activăm.

Verificare: Ruff+932teste+344subteste;60sesiuni/59verificări de neconcurență;
4.468 fișiere protejate intacte; replay fără procese/rețea/DB cu138artefacte identice.
Aproximativ5,99minute. Încercarea inițială de pornire blocată de sandbox nu a ajuns
la model; păstrată separat. Nicio încărcare D1/Qwen, evaluare umană nouă sau scriere DB.
[Raport și reproducere](../research/2026-10-31-evidence-repair.md).

**Pas recomandat la închiderea etapei5, realizat în etapa6:** experiment offline cu predicțiile și atestările de
corpus existente: o poartă pentru reduceri≥2 care cere suport pentru forma exactă,
nu doar o definiție sau consens LLM. Regulă/praguri fixate înaintea comparației;
analiză pe familii, rezultate150/50 separate și fără agravare4/5. Fără apeluri LLM
suplimentare și fără etichete umane noi pentru această etapă.

Leftovers:19/150 și38/50 fără definiții; POS neacoperite27/150 și38/50; formate MDA
complexe/trimiteri interne excluse; eroarea comportamentală Qwen otel→oțel neretestată.
950 forme rămân fără referințe. Baseline operațional păstrat; nicio regenerare de
scoruri pe inventarul complet sau modificare DB autorizată aici.


## Rezultatul etapei6 — filtru lexical + corpus offline, 2026-11-01

Regulă înghețată înaintea comparației: acceptă numai reduceri GPT≥2 dacă există
sensuri pentru POS-urile cunoscute și suport FineWeb2(≥5apariții,≥3documente,
≥2gazde) SAU CoRoLa(≥5apariții). În toate celelalte cazuri păstrează baseline-ul.
Fără antrenare, modificarea pragurilor, apeluri LLM, downloaduri sau scrieri DB.
Toate150 și toate50 păstrate în evaluare; scorurile umane/originale intacte.

| Lot | Reduceri propuse / acceptate | Severe baseline → candidat | Cost |
|---|---:|---:|---:|
|150|9 /8|11 → 9|14 → 12|
|50 selectate după risc|49 /11|13 → 10|14 → 13|

**Criteriul predeclarat NU trece:** pe referințele4, erorile cresc2/21→3/21 și
0/9→2/9; pe referințele5 rămân3/22→3/22 în pilot, dar cresc1/6→2/6 în lotul recent.
Corpusul nu schimbă nicio decizie față de filtrul numai lexical. CoRoLa trece57/58
reduceri propuse; pragul de atestare nu este dovadă de familiaritate. Pilotul are
142grupuri, lotul recent50; un fold pilot se agravează2→4 severe. Fără validare
independentă sau pretenție de CV nouă.

Ruff936teste+354subteste PASS;4.662fișiere protejate intacte;8artefacte de replay
identice, verificare separată a etichetelor și aritmeticii. Runner-ul blochează
procese/rețea/DB. Revizie locală fără subagenți, respectând cererea fără LLM.
[Raport, ablații și reproducere](../research/2026-11-01-reduction-gate.md).

**Decizie:** baseline păstrat, filtru nepromovat. Încheiem ciclul de reglaj pe
aceste etichete; fallback-ul CoRoLa calibrat anterior nu trecuse nici el criteriul.

**Pas recomandat la închiderea etapei6, realizat în etapa7:** export CSV conservator pentru inventarul complet:
cele200 evaluări umane au prioritate pentru forma exactă, baseline pentru rest,
proveniență și statut verificat/provizoriu, conflictele GPT separat. Mapare exactă
la toate ID-urile/POS-urile, fără restaurarea diacriticelor. Acest export nu a fost
executat în etapa6; orice viitor upload cere verificările Jaccard și precizie/recall
pe ancore, fără activare implicită din rezultatul experimentului.

Leftovers:950forme din lotul nou fără referințe, acoperire lexicală incompletă,
numărători corpus fără sens/POS dezambiguizat și discriminare automată4/5
nevalidată. Nicio rundă nouă de adnotare propusă utilizatorului; nicio certificare
artificială a scorurilor automate prin acordul modelelor.


## Rezultatul etapei7 — export conservator complet, 2026-11-01

CSV separat,77.698ID-uri/75.147forme: cele200 evaluări umane au prioritate pe233
rânduri, inclusiv toate POS-urile aceleiași forme exacte. Cele77.465rânduri rămase
păstrează baseline-ul înghețat; nu refacem fitting-ul și nu folosim scorurile OOF
ca export operațional. Se schimbă numeric117rânduri/99forme. Statutul uman rămâne
explicit și când scorul coincide cu baseline-ul; restul sunt provizorii.

Proveniență CSV cu surse/hashuri, ID-uri/POS și chei de referințe.813conflicte
separate:99baseline–uman(23≥2),714observații model–candidat(160≥2), pe653forme.
1.331predicții istorice păstrate doar ca diagnostic; niciun vot sau override automat.
Formele fără diacritice rămân distincte. Referințele umane contradictorii opresc
exportul; sursele actuale sunt consistente. Scorurile originale rămân intacte.

**Verificările L1 nu trec**, nici pentru baseline-ul original: candidat Jaccard3,235%,
precizie ancore8,219%, recall56,250%, față de pragurile70%/80%/80%. Baseline:
3,180%/8,161%/55,469%. Snapshot local2.500ID-uri L1,128ancore seed neexhaustive;
nu este validare DB live sau acuratețe populațională. Prioritatea umană îmbunătățește
marginal indicatorii. Export valid structural; nepregătit pentru upload.

Ruff940teste+363subteste PASS; reconciliere independentă completă,10artefacte
identice la replay,4.688fișiere protejate intacte. Zero apeluri LLM/subagenți/DB.
[Raport, fișiere și reproducere](../research/2026-11-01-conservative-export.md).

**Pas recomandat la închiderea etapei7, realizat în etapa8:** audit offline al diferențelor L1 și al provenienței/acoperirii
ancorelor, folosind sursele existente. Explicăm divergența înaintea oricărei decizii
de upload; nu relaxăm pragurile, nu modificăm scorurile umane și nu ajustăm
histograma pentru a forța un PASS. Nu propunem încă o rundă de evaluare.

Leftovers:74.947forme din inventar fără referință umană, inclusiv950din lotul nou;
discriminare automată4/5 nevalidată, dovezi lexicale incomplete, corpus fără
sens/POS dezambiguizat. Compatibilitatea live și uploadul rămân etape separate,
neexecutate; gating-ul și modul implicit partial se păstrează.


## Rezultatul etapei8 — audit L1/ancore offline, 2026-11-02

**Cauze confirmate:** praguri imposibile la cardinalitățile actuale, seed pozitiv
tratabil doar ca listă incompletă, snapshot istoric slab aliniat evaluărilor umane,
plus limita reală a baseline-ului frecvență/fallback. Zero probleme de identitate
între77.698ID-uri locale; normalizarea nu schimbă mulțimile L1.

- Jaccard baseline maxim38,88% (972/2.500), sub prag70% chiar cu suprapunere
  perfectă. Efectiv3,180%; candidatul3,235%, maxim39,12%. Pe forme:3,283%/3,340%,
  deci agregarea POS nu rezolvă divergența. Snapshot:1.783forme cu niveluri diferite.
- Precizie seed baseline maxim14,713% (128/870), sub80%. Chiar400ancore ar permite
  cel mult45,98%. Cuvintele neincluse în seed nu sunt negative validate.
- Toate128ancore există în inventar; baseline71la1,54la2,1la3,2la4. Majoritatea
  ratărilor sunt abateri de1, tolerate de obiectiv. `stilou`3, `prună`/`ședea`4;
  ultimele două fără frecvență. Candidatul are72ancore L1 prin evaluarea umană `ou`.
- Snapshotul din15februarie precedă run-uri/uploaduri locale ulterioare. El însuși
  trece numai19/128ancore în L1 și produce76/150erori≥2, față de10/150baseline
  fitted; pe50:13vs13, cost18vs14. Nu confunda10fitted cu11OOF istoric.
- Restaurarea istorică a deplasat ID-urile cu+77.698; verificat pe toate rândurile.
  Nu aplicăm deplasarea și nu presupunem starea DB actuală fără snapshot nou.

Scoruri/export/ancore/praguri intacte. 4.707fișiere protejate;6artefacte replay
identice; gate-ul reprodus cu aritmetică independentă; Ruff940teste+363subteste.
Zero LLM/subagenți/DB. [Raport și reproducere](../research/2026-11-02-l1-audit.md).

**Pas recomandat la închiderea etapei8, realizat în etapa9:** TDD pentru manifestul și raportul de validare nou,
în mod audit separat: rol/data/universul fiecărei referințe, preflight pentru
cardinalități imposibile/identități incompatibile, Jaccard ca măsură a schimbării,
recall pentru seed pozitiv, erori≥2 și4/5 pe etichetele existente cu numitor și
acoperire explicite. Formele neetichetate rămân necunoscute; fără auto-ancorare,
fără scoruri noi sau altă rundă de evaluare. Gate-ul operațional rămâne nemodificat;
contractul trebuie stabilit înaintea oricărei integrări în upload.

Leftovers: referință live/ID-uri actuale neverificate, lipsă dovadă independentă de
precizie globală,74.947forme fără etichete umane, diferența4/5 automată nevalidată.
Un snapshot nou ar clarifica starea DB, nu ar valida semantic scorurile istorice.


## Rezultatul etapei9 — contract versionat audit-only, 2026-11-02

Prima schemă explicită `rarity-validation-audit-v1`. Manifest cu rol/unitate/datǎ/
proveniență/hash/univers; versiuni necunoscute și modul upload respinse. Surse
historical_snapshot/positive_seed/human_labels, candidat complet și utilizarea
etichetelor declarată. Erori structurale opresc exportul; publicare atomică,
fără suprascriere sau remapări implicite. Interfață reutilizabilă CSV→rapoarte.

Jaccard istoric, recall seed, erori umane separate150/50 și4/5. Numitori/acoperire
explicite; seed neexhaustiv nu produce precizie semantică. fit/override nu sunt
validare independentă; numitor zero→null. `upload_authorized=false` inclusiv cu
metrici perfecte; nicio integrare/înlocuire a gate-ului operațional.

Rezultate reproduse: baseline fitted10/150și13/50severe, override0prin construcție;
125/128ancore la±1,3abateri≥2. Precizia baseline pe L1etichetat38/45=84,44%, dar
acoperă numai45/870=5,17%L1și este fitting. Conservator51/51prin override, acoperire
51/876=5,82%. 825forme L1fără referință în ambele cazuri; lotul50nu are L1.

Verificare: TDD7teste noi+18subcazuri; total947teste+381subteste, Ruff PASS;
400comparații umane reconciliate,7artefacte replay identice,4.718fișiere intacte.
Apelat entrypoint-ul real Step4 cu efecte externe interzise: baseline și conservator
blocate de gate înainte de DB/markere. Scorurile/ancorele/pragurile originale intacte;
zero apeluri LLM/subagenți/DB. [Contract și raport](../research/2026-11-02-validation-contract.md).

**Pas recomandat la închiderea etapei9, realizat în etapa10:** dry-run de migrare pe snapshot actualizat doar prin
citire, cu proveniență, verificarea ID/grafie/POS și plan CSV de diferențe/conflicte.
Fără update, fără vechiul offset de ID aplicat automat, fără gate bypass. Nu este
executat în această etapă. Nu cerem alte evaluări și nu reglăm din nou pragurile.

Leftovers: politica explicită de acceptare înaintea oricărei integrări în upload;
precizie globală L1necunoscută(825L1neetichetate),74.947forme fără referință umană,
4/5nevalidat automat. Un snapshot nou rezolvă prospețimea/identitatea, nu adevărul
semantic. Gate-ul existent rămâne obligatoriu și FAIL; contractul nou este audit-only.


## Rezultatul etapei10 — dry-run pe snapshot proaspăt, 2026-11-02

Captură prin pluginul Supabase, două SELECT-uri (preflight+snapshot), zero scrieri:
2026-11-02T20:32:03.276616Z,77.698rânduri,ID233.095–310.792. Snapshot complet într-o
singură instrucțiune, fără paginare. Nu presupunem setarea read-only a sesiunii;
SQL-ul trimis este exclusiv SELECT. Restul runner-ului interzice rețea/procese/DB.

Mapare exactă formă/POS:73.308rânduri unice +4.390rânduri în2.165grupuri duplicate
cu scor propus echivalent. Toate75.473perechi regăsite, cardinalități egale; zero
identități lipsă. Nu se ghicește corespondența individuală în duplicate. Offsetul
observat+155.396este numai diagnostic; vechiul+77.698nu a fost aplicat.

Propunerea completă ar schimba50.889rânduri, păstrând26.809;6.664diferențe≥2.
30.540tranziții5→4provin în mare parte din fallback, nu din dovezi noi. Dintre233
rânduri umane,165ar necesita corecție(144forme),61diferă≥2(54forme).200evaluări și
exportul inițial intacte;6.603diferențe mari apar pe rânduri baseline provizorii.

Audit în universul live: Jaccard14,678%, acum fezabil teoretic(max79,319%), dar sub
70%; seed8,219%/recall56,250%, sub80%/80%. Entry-point-ul real Step4 rămâne blocat
înainte de DB/markere. Nu s-a generat SQL de modificare sau autorizare de upload.
TDD4teste+5subcazuri, total951teste+386subteste PASS;13artefacte replay identice,
4.729fișiere protejate intacte. [Raport și fișiere](../research/2026-11-02-migration-dry-run.md).

**Decizie:** nu promovăm migrarea integrală. **Pas recomandat la închiderea etapei10, realizat în etapa11:** pregătirea
unui lot separat pentru165corecții umane, cu precondiții ID/grafie/POS/scor live și
rollback CSV. Politica de acceptare pentru lot trebuie stabilită explicit, fără
ocolirea gate-ului, auto-referință sau reducerea artificială a numitorului. Fără
execuție DB în această etapă viitoare de pregătire; nu cerem alte evaluări umane.

Leftovers:50.724schimbări baseline provizorii, politica de promovare, verificarea
prospețimii înainte de orice upload, precizie globală L1necunoscută și4/5nevalidat.


## Rezultatul etapei11 —165corecții umane, precondiții și rollback, 2026-11-02

Pachet `human-corrections-package-v1`, exclusiv pregătire:165corecții/144forme,
165inverse de rollback;233rânduri protejate pentru200forme.68rânduri deja corecte
nu intră în update/rollback. Numai referințe umane originale, verificate față de
răspunsurile `working_level`; planul de migrare trebuie regenerat identic din
intrările fixate. Nu sunt suficiente flag-uri sau hashes recalculabile ale unui
CSV alterat. Niciun scor/ID nu este inventat sau selectat din baseline.

Precondiții before/after: ID/grafie/POS literal, scor și mulțimea completă de
ID-uri/POS pentru toate formele evaluate; detectează rânduri noi/dispărute și
schimbări ale celor68rânduri deja corecte. Metadatele rămân explicit fără dovadă
de prospețime/execuție și fără autorizare apply/rollback.

Simulare numai în CSV: exact165schimbări,77.533rânduri neatinse; inversa reconstruiește
snapshotul original byte cu byte. Rollback-ul viitor ar necesita recipisă confirmată
de apply, verificarea stării post și protecție față de schimbări concurente; un
scor care coincide nu demonstrează execuția și nu detectează singur A→B→A.

Gate pe întreg inventarul simulat: Jaccard96,459%PASS, apartenență seed4,770%FAIL,
recall42,969%FAIL.55/128ancore L1față de54inițial. Nicio modificare de prag/seed sau
numitor; uploaderul neinvocat. Snapshotul din20:32UTCeste reutilizat, nu recitit.
TDD5teste+10subcazuri, total956teste+396subteste PASS;16artefacte replay identice,
4.754fișiere protejate intacte. Zero DB/LLM. [Raport și fișiere](../research/2026-11-02-human-corrections.md).

**Pas recomandat la închiderea etapei 11, realizat în etapa 12:** politică explicită de acceptare pentru lotul uman,
cu exact setul aprobat, scoruri din referințe, rest neschimbat și precondiții complete.
Integrarea cu uploaderul/executorul este separată; fără relaxarea implicită a
gate-ului și fără altă rundă de evaluare. Nu aplicăm acum nici corecții, nici rollback.

Leftovers: prospețime live, tranzacție/concurență, recipisă de execuție și politica
de rollback după editări ulterioare, blocajul ancorelor legacy.50.724schimbări
baseline rămân provizorii, fără promovare sau experimente LLM noi.


## Rezultatul etapei 12 — politica de acceptare în audit, 2026-11-03

`human-corrections-acceptance-audit-v1`: toate cele șase criterii PASS pentru lotul
fixat. Pachetul este regenerat din plan și răspunsurile originale; 165 corecții,
233 precondiții, 200 referințe. Candidatul complet trebuie să fie exact snapshotul
plus lotul uman, fără alte modificări. Inversa restabilește fiecare rând al snapshotului.
Jaccard ≥0,70 rămâne obligatoriu; versiunile/modurile/pragurile suplimentare sunt
refuzate. Auditul fixează întregul pachet prin manifest, nu doar cardinalitatea lui.

Rezultat: `human_policy_satisfied=true`, dar `promotion_blocked=true` și nicio
autorizare upload/rollback. Gate-ul legacy rămâne FAIL: Jaccard 96,459% PASS,
apartenență seed 4,770%, recall 42,969%. Zero contradicții directe seed–uman;
seed-ul incomplet nu este reinterpretat ca adevăr negativ despre formele absente.
Nu schimbăm praguri, ancore, uploader sau scoruri. Snapshotul din 2026-11-02 este
reutilizat, fără dovadă de prospețime/execuție și fără acces DB/LLM.

TDD: 7 teste noi + 26 subcazuri; total **963 teste + 422 subteste PASS** și Ruff.
4.778 fișiere protejate intacte; 10 fișiere de audit identice la replay. Delta
reconciliată independent: 165 rânduri schimbate, 77.533 intacte. Cele 200 de evaluări
rămân originale. [Politică, rezultate și reproducere](../research/2026-11-03-human-acceptance.md).

**Pas recomandat la închiderea etapei12, aprobat și implementat în etapa13:** promovare operațională a politicii pentru
fluxul separat de corecții umane, inclusiv rolul ancorelor incomplete; apoi executor
tranzacțional cu verificare live, concurență, recipisă și rollback condiționat de
execuție confirmată. Politica de audit este gata; nu o redefinim și nu cerem evaluări
noi. Gate-ul operațional nu este înlocuit implicit prin acest audit.

Leftovers: acea integrare autorizată, prospețime și execuție atomică, blocajul legacy,
precizie globală L1 necunoscută, discriminare automată 4/5 nevalidată și 50.724 de
schimbări baseline provizorii nepromovate. Niciun upload sau SQL de modificare.


## Rezultatul etapei13 — flux uman aprobat, implementat fără DB, 2026-11-03

Utilizatorul a aprobat explicit politica: Jaccard obligatoriu, seed diagnostic pentru
corecții umane, fără schimbarea gate-ului automat. Flux separat CSV-first și adaptor
PostgreSQL; dry-run implicit, apply/rollback numai explicit cu package_id confirmat
și DSN dedicat. Auditul/proveniența originale sunt refolosite fără modificare.

Tranzacție: lock înainte de snapshot, toate233 precondițiile și apartenențele, candidat
integral cu165 corecții, Jaccard≥.7 față de referința fixată și starea curentă, update
condiționat de valori/versiuni, verificare post-state și recipisă în același commit.
Reluarea recuperează recipisa fără reaplicare. Rollback numai cu dovadă și versiuni
valide; detectează ABA, păstrează editările fără legătură și se poate recupera după
commit incert. Schema ledger-ului privat este pregătită, dar neexecutată.

Verificare:13 teste noi +27 subcazuri; **976 teste +449 subteste PASS**, Ruff PASS.
Lot real în preview și store simulat:165 schimbări exacte,77.533 rânduri neatinse,
233 guards,200 referințe păstrate; inversă corectă și retry fără reaplicare.
4.791 fișiere protejate intacte;14 fișiere preview identice la replay. Jaccard96,459%,
seed4,770%/recall42,969% raportate fără veto în fluxul uman. Zero DB/LLM/DDL.

**Limită:** transport substituit și store în memorie; nu s-au verificat pe server
blocările, rolurile, schema/triggerele, xmin sau commit-ul. Recipisele simulate nu
sunt recipise DB. [Implementare, rezultate și utilizare](../research/2026-11-03-human-flow.md).

**Pas recomandat la închiderea etapei13, realizat în etapa14:** integrare pe un PostgreSQL izolat, inclusiv concurență
și recuperare. După acea verificare, instalare ledger și aplicare reală numai cu
autorizare; politica nu mai necesită reaprobare. Snapshotul live va fi reverificat
în tranzacție. Nu promovăm50.724 schimbări baseline și nu solicităm evaluări noi.


## Rezultatul etapei14 — integrare PostgreSQL17.9 izolată, 2026-11-03

Aprobarea „ok. do it” a acoperit testele pe un server local separat. Harness Docker
cu imagine fixată prin digest, port numai127.0.0.1, volum nou și nume unic, maximum
512MiB RAM. Fără DSN arbitrar sau credentiale ale aplicației. Containerul și volumul
au fost eliminate; imaginea de aproximativ104MiB rămâne cache reutilizabil.

**17 teste reale PASS**, inclusiv concurență între conexiuni, aplicare simultană a
aceluiași pachet o singură dată, restart, RLS/roluri, triggere/deferred constraints,
deconectare înainte de commit, recuperare după commit confirmat dar ACK simulat
pierdut, rollback și ABA prin xmin. Lotul165 pe copia întregului inventar77.698:
candidat exact,77.533rânduri neatinse, retry fără reaplicare, rollback corect.

**Defect găsit și reparat cu TDD:** un trigger pe ledger putea modifica words sau
rescrie recipisa după verificarea inițială. Fluxul forțează acum constrângerile și
reverifică inventarul +recipisa după scrierea ledger-ului, înainte de commit; aplicare
și rollback protejate. Regresie în suita offline și pe server. Gate-ul automat intact.

Ruff PASS; suita normală **977 teste +452 subteste PASS**,17 integrări skip implicit,
rulate separat toate cu succes.4.885 fișiere originale protejate intacte; fără LLM.
Schema ledger instalată numai în container, niciun acces la DB-ul proiectului.
[Raport, reproducere și limite](../research/2026-11-03-postgres-integration.md).

**Pas recomandat la închiderea etapei14, realizat în etapa15:** preflight read-only al configurației reale (roluri/RLS/triggere,
identitatea și starea lotului), apoi instalarea ledger-ului și aplicarea lotului numai
la instrucțiune explicită. Nu mai este nevoie de reaprobarea politicii sau de o nouă
rundă de etichetare. Integrarea nu certifică mediul de producție și nu testează căderi
fizice de disc/mașină.50.724 modificări baseline rămân excluse.


## Rezultatul etapei15 — preflight real read-only, 2026-11-03

**Lot valid; mediu incompatibil cu executorul actual.** Proiectul folosește
PostgreSQL17.9 +OrioleDB1.8; words și access method implicit sunt `orioledb`.
SELECT-ul `xmin` eșuează cu XX000. Cele17 integrări anterioare au verificat heap,
nu acest motor. Nu eliminăm protecția la editări A→B→A pentru a permite execuția.

Inventarul77.698 are aceeași amprentă SHA-256 pe ID/grafie/POS/scor ca snapshotul
aprobat. Cele233 de precondiții trec:165 corecții încă necesare,68 deja corecte;
200 referințe originale păstrate. Preview/proveniență PASS, Jaccard96,459%; seed
diagnostic4,770%/42,969%. Restul77.533 de rânduri rămân neschimbate în proiecție.

RLS activ, o politică SELECT; sesiunea postgres are BYPASSRLS. Zero triggere/rules
pe words;9 event triggers DDL inspectate separat. Ledger-ul privat lipsește;
executor dedicat și DSN efectiv neverificate. Nu există autorizare de instalare
sau aplicare.5 încercări SQL read-only:4 reușite,1 eroare de capabilitate xmin.
Zero modificări DB/LLM;6.117 fișiere protejate intacte.26 teste +66 subteste PASS.
[Raport, roluri, artefacte și limite](../research/2026-11-03-production-preflight.md).

**Pas recomandat la închiderea etapei15, realizat în etapa16:** TDD pentru compatibilitate OrioleDB într-un mediu izolat:
reproducerea defectului, refuz timpuriu al capabilităților incompatibile, versiune
explicită a rândului și rollback care detectează ABA inclusiv delete/reinsert.
Recomandare de investigat: token unic emis de DB pentru fiecare INSERT/UPDATE,
prin secvență/trigger, acoperind toți scriitorii. Nu hash/scor/timestamp ca substitut.
Necesită proiectare și probe pe OrioleDB înainte de pregătirea unei migrări reale.

Leftovers: suportul motorului real; schema ledger/rol/granturi private; conexiune
directă verificată; instalare și apply numai la instrucțiune explicită, cu verificări
live în tranzacție. Politica umană deja aprobată. Blocajul legacy, precizia globală
L1 necunoscută și50.724 de schimbări baseline provizorii rămân în afara acestui lot.


## Rezultatul etapei16 — revizii OrioleDB cu TDD, 2026-11-03

Adaptorul păstrează xmin pentru heap și folosește revizii explicite pentru OrioleDB.
Motorul nesuportat/contractul absent este refuzat anticipat. Un trigger privat,
ENABLE ALWAYS, emite token bigint nou prin secvență la fiecare INSERT/UPDATE;
ignoră tokenurile furnizate de apelant. Recipisa fixează tipul și UUID-ul instalării.
Retry/rollback refuză alt contract; ABA și delete/reinsert nu reutilizează tokenuri.

Contractul coloanei/funcției/triggerului/secvenței este verificat înaintea execuției
și la snapshoturi, inclusiv după scrierea ledger-ului. Triggere BEFORE suplimentare
sunt refuzate; scriitorii obișnuiți nu pot reseta secvența sau dezactiva triggerul.
Interfețele CSV/tranzacționale, politica, scorurile și Step4/Step5 rămân neschimbate.

**28/28 teste OrioleDB1.8 PASS**, PostgreSQL17.9, imagine Supabase fixată prin digest.
Lot complet:165 scoruri schimbate,77.533 păstrate; candidat exact, retry fără
reaplicare, restart și rollback corecte. Regresie heap:17PASS,11cazuri numai OrioleDB
skip. Ruff și **980teste +456subteste PASS** offline.6.151fișiere protejate intacte;
container/volum eliminate. Zero acces la DB-ul real sau apeluri LLM.
[Implementare, reproducere și limite](../research/2026-11-03-orioledb-integration.md).

**Pas recomandat la închiderea etapei16, realizat în etapa17:** pregătirea pachetului de instalare pentru producție, separat de
apply165: ledger, revizii, executor/granturi, pre/postchecks și compatibilitatea
scriitorilor existenți. Inițializarea reviziilor atinge toate77.698 de rânduri fără
schimbarea scorurilor și cere o fereastră pentru lock exclusiv. Instalarea nu este
autorizată de testele izolate. După instrucțiunea explicită de instalare: preflight
cu DSN-ul efectiv, apoi apply numai la instrucțiune explicită și cu revalidare live.

Leftovers: schema/rolurile reale încă absente; administratori/restore de încredere,
fără resetarea istoricului de revizii; infrastructura găzduită nu este certificată
prin fixture. Fără evaluări noi; politica deja aprobată; baseline50.724 nepromovat.


## Rezultatul etapei17 — pachet de instalare offline, 2026-11-03

Interfață CSV/captură fixată → director nou cu SQL, audit, manifest și CSV-urile
originale.17 prechecks read-only; o tranzacție ledger/revizii/rol/granturi;
16 postchecks read-only. Inventarul și configurația reală capturate sunt precondiții,
reverificate sub lock exclusiv. Hash-ul tuturor coloanelor existente și recipisa
instalării verifică păstrarea datelor inclusiv după ultima scriere internă.

Executor NOLOGIN, fără credentiale; BYPASSRLS cu granturi limitate, fără secvență/DDL
sau scrierea contractului. Nicio instalare/aplicare implicită. Refolosește componentele
SQL existente; refuză schema/rolul deja prezente. Runbook pentru verificare, client
fail-fast și recuperarea unei confirmări pierdute; fără uninstall automat.

**6 teste noi PASS; Ruff +986teste +456subteste PASS**,28 integrări skip.9artefacte
principale reproduse identic;6.151fișiere originale intacte. Zero conexiuni DB,
instalări sau apeluri LLM. Wrapper-ul SQL complet **neexecutat**; probele server din
etapa16 nu certifică această nouă compoziție. [Raport și reproducere](../research/2026-11-03-installation-package.md).

Audit local: loader-ul dicționarului folosește coloane explicite, dar TRUNCATE/reload
poate schimba ID-urile și cere reconcilierea lotului. Nu reprezintă inventarul tuturor
scriitorilor deployați. Recitirea configurației reale și verificarea DSN-ului rămân
necesare înaintea oricărei instalări autorizate.

**Pas recomandat la închiderea etapei17, realizat în etapa18:** repetiție completă pe OrioleDB izolat: creator non-superuser,
rol/granturi, hook-uri DDL reprezentative, inventar complet, timeout/eșec/recuperare,
pre/postchecks. Ulterior: instalare explicit autorizată, activare controlată a
executorului, apoi apply165 separat autorizat și revalidat în tranzacție.
Politica deja aprobată; fără etichete noi;50.724schimbări baseline rămân excluse.


## Rezultatul etapei18 — repetiție integrală OrioleDB, 2026-11-04

**12/12 teste reale PASS**. Arhiva originală nemodificată executată ca proprietar
non-superuser, cu77.698rânduri și cele9hook-uri DDL capturate:17/17 prechecks,
16/16 postchecks; restart corect. Fixture separat pentru excepții DDL, modificări
ale coloanelor fără scor, backend terminat, drift, timeout la lock și ACK pierdut.
Eșecurile sunt atomice și permit retry; succesul incert se identifică prin recipisă,
nu prin reinstalare. Postflight detectează granturi/trigger/date alterate ulterior.

Granturile executorului generate sunt suficiente: apply165 +retry +rollback în
copia izolată;77.533rânduri cu scor păstrat, rollback identic proiecției inițiale.
Niciun defect de runtime găsit; pachetul/SQL-ul original păstrate. Corectat numai
setup-ul fixture-ului pentru ownerul event trigger-ului; instalarea fără SUPERUSER.
[Raport și reproducere](../research/2026-11-04-installation-rehearsal.md).

Ruff +986teste +456subteste PASS;40integrări skip implicit, cele12noi rulate separat.
6.175fișiere protejate intacte. Container/volum eliminate; imagine deja în cache,
fără download. Zero acces DB real și apeluri LLM. Fixture-ul nu clonează toate
coloanele/serviciile găzduite; ACK simulat după commit real, nu pană fizică.

**Pas recomandat la închiderea etapei18, preflight realizat în etapa19:** preflight read-only actualizat pe conexiunea efectivă; apoi,
numai explicit autorizată, instalarea structurală în fereastra de lock, cu checks
înainte/după. Executorul rămâne NOLOGIN. Activarea și apply165 separate, cu revalidare
live. Nu cere reaprobarea politicii sau etichete noi. Orice drift oprește execuția;
50.724schimbări baseline rămân excluse, gate-urile automate intacte.


## Rezultatul etapei19 — preflight real actualizat, 2026-11-04

**17/17 precondiții originale PASS** pe conexiunea Supabase MCP reală, ca postgres.
Proiect ACTIVE_HEALTHY; PostgreSQL17.9/OrioleDB1.8, RLS/granturi/hook-uri neschimbate.
Schema privată și rolul încă absente. Snapshot77.698 are aceeași amprentă pe
ID/grafie/POS/scor;233/233 rânduri protejate citite individual și comparate:
165corecții necesare,68deja corecte. Politica/proveniența reconfirmate offline.
[Raport și limite](../research/2026-11-04-production-preflight.md).

Două tranzacții READ ONLY,00:49:33 și00:50:38 Europe/Bucharest. Fără DDL/DML/lock
explicit/apeluri LLM. Zero alte lock-uri words la captura secundară; nicio rezervare
viitoare. Conexiunea MCP verificată; DSN dedicat neconfigurat și netestat. Setarea
schemelor API nu este vizibilă în sesiune; postflight-ul rămâne necesar.

35teste +70subteste PASS;6artefacte de replay identice;7.124fișiere protejate intacte.
Nicio schimbare runtime/SQL/pachet sau evaluare. Nu s-a reluat repetiția server12/12.

**Pas recomandat la închiderea etapei19, realizat în etapa20:** instalarea structurală numai la instrucțiune explicită, cu
preflight repetat și lock exclusiv, apoi verificările16după. Nu există blocaj tehnic
observat în precondițiile curente. Instalarea lasă executorul NOLOGIN; activarea,
conexiunea lui și apply165 sunt separate. Fără reaprobarea politicii/etichete noi;
50.724schimbări baseline rămân excluse. Orice drift real oprește execuția.


## Rezultatul etapei20 — instalare structurală reală, 2026-11-04

La instrucțiunea de continuare, pachetul original instalat o singură dată pe
pdliedweugywbiczajxn. Preflight17/17 repetat; verificări sub lock; postflight16/16
PASS din conexiune separată. Recipisă durabilă09:10:27 Europe/Bucharest, recitită
09:11:36. [Raport, hash-uri și limite](../research/2026-11-04-production-installation.md).

Ledger/revizii/rol/granturi create.77.698revizii unice; hash identic înainte/după
pentru TOATE coloanele existente, inclusiv scorurile. RLS/granturi existente și
hook-uri păstrate. Executor NOLOGIN, fără parolă provisionată; schema privată fără
USAGE pentru rolurile API. Ledger corecții gol;165scoruri încă neaplicate.

O tranzacție de instalare,3read-only pentru verificare. Zero apeluri LLM;
7.155fișiere originale intacte. Runtime/SQL neschimbate; fără repetarea testelor deja
trecute. Advisor:0findings private;5obiecte publice vizibile GraphQL pentru anon,
fără schimbări de acces suplimentare. Arhiva originală păstrată imutabilă.

**Pas recomandat la închiderea etapei20, realizat în etapa21:** configurarea/verificarea conexiunii dedicate și activarea
controlată a executorului, numai explicit instruite; inițial verificări read-only.
Apply165 rămâne separat, cu revalidare live și recipisă în aceeași tranzacție.
Nu reinstala schema și nu folosi rollback.csv pentru dezinstalare. Politica deja
aprobată; fără etichete noi;50.724schimbări baseline rămân excluse.


## Rezultatul etapei21 — conexiune dedicată verificată, 2026-11-04

Configurarea și activarea controlată încheiate, fără granturi noi. Autentificare
reală ca executor, TLS cu verificarea certificatului și hostname-ului; credentiale
numai local, protejate și excluse din Git. Configurația administrativă păstrată.
Session pooler folosit după ce endpointul direct nu s-a rezolvat local. CA oficial,
fără reducerea verificărilor TLS sau instalarea unor dependențe.

Validare explicit READ ONLY: contractul existent corespunde, inventarul complet
vizibil,233/233precondiții valide, ledger gol.165corecții încă necesare,68deja corecte;
zero scoruri aplicate sau apeluri LLM.7.172fișiere originale intacte. Runtime/SQL
neschimbate. [Rezultat și limite](../research/2026-11-04-executor-connection.md).

Opțiunile read-only de conectare nu au fost aplicate de pooler; verificarea folosește
BEGIN READ ONLY explicit și confirmă starea în tranzacție. Fișierul de conectare
nu este o barieră permanentă read-only. Check-ul de instalare NOLOGIN devine fals
intenționat după activare; celelalte15trec și atributele active sunt verificate separat.

**Pas recomandat la închiderea etapei21, realizat în etapa22:** apply165 numai la instrucțiune explicită, folosind conexiunea
pregătită și fluxul deja aprobat; revalidare live sub lock, CAS, verificare finală
și recipisă atomică. Fără alte evaluări sau configurări preventive. Orice drift
oprește aplicarea; baseline50.724 și gate-urile automate rămân excluse/intacte.


## Rezultatul etapei22 — corecții umane aplicate, 2026-11-04

La confirmarea continuării, fluxul aprobat a aplicat exact165corecții umane într-o
singură tranzacție, cu CAS secvențial și recipisă atomică. Preflight233/233 și auditul
sursei/politicii au trecut; condițiile au fost reverificate sub lock înainte de DML.
Jaccard96,459% față de ambele referințe. Gate-ul automat rămâne FAIL/nemodificat.

Citirea READ ONLY separată confirmă233/233postcondiții,165scoruri+revizii modificate,
77.533rânduri identice și toate celelalte coloane intacte. Recipisa DB coincide cu
cea locală.7.187fișiere originale intacte; zero apeluri LLM/DDL/granturi noi.
Runtime neschimbat; fără repetarea suitelor trecute. Arhivele și rollbackul păstrate.
[Rezultat, limite și recuperare](../research/2026-11-04-human-application.md).

**Următorul pas:** review/merge coordonat PR85/86. Lotul uman este închis;
nu mai necesită instalare, activare, aplicare ori evaluări noi. Nu relua verifierul
istoric cu ledger gol ca test al stării actuale; păstrează dovada post-apply.

**Leftovers:** cele50.724schimbări baseline rămân neaplicate. Promovarea automată
necesită în continuare o decizie distinctă despre contractul semantic L1/ancore și
validarea erorilor≥2 pe referințele existente; succesul lotului uman nu autorizează
acel upload. Nu transforma consensul modelelor sau potrivirea histogramei în gold.


## Review și integrare PR85/86 — 2026-11-04

Review offline pe puncte fixe: fără probleme blocante rămase; antetele documentelor
istorice clarificate. PR85:883teste+220subteste; PR86:986teste+456subteste,40teste DB
omise. Ruff și CI verde pe head-urile revizuite. Zero acces DB/apeluri LLM.
[Raport și limite](../research/2026-11-04-pr85-pr86-review.md).

Corecție față de recomandarea anterioară:85 era deja merged din30octombrie în
branch-ul lui82.86 trebuie integrat în acel părinte; simpla închidere a stivei85/86
nu înseamnă integrare în main. PR81/82 sunt încă deschise; extinderea review/merge-ului
la acestea este o etapă separată. Lotul uman și gate-urile automate nu se schimbă.


## Integrarea finală către main — 2026-11-04

81 a fost merged în main;82 a fost merged ulterior în branch-ul lui81, incluzând
85/86. Din acest motiv este necesar un PR final `codex/d1-evaluation-adapter` →
main. Autorizat explicit în această etapă, fără acces DB sau apeluri LLM.

Main combinat fără conflicte; actualizările dependențelor păstrate. Corectată
neconcordanța dintre extras pyproject și uv.lock; verificarea lock trece, toate
pin-urile existente păstrate. Ruff+986teste+456subteste PASS,40teste DB omise.
[Raport de integrare și limite](../research/2026-11-04-main-integration.md).

Merge numai după CI verde pe head-ul final, cu verificarea rezultatului în main.
Nu mai este necesară o altă operație DB pentru lotul uman; promovarea baseline-ului
rămâne separată. Consultă PR-ul final pentru statusul efectiv al integrării.

## Simularea politicii de promovare, 5 noiembrie

Politica exploratorie a fost fixată înainte de calculul pe rute. Pe pilotul de
150 de forme, wordfreq are 9/101 erori severe în validarea cu grup exclus,
fallback are 2/49. În lotul selectat după risc, rezultatele sunt 1/5 și 12/45.
Wordfreq pierde pe ambele forme de nivel 4 din pilot. Fallback atribuie 4 tuturor
celor 12 forme de nivel 2 ratate în lotul de risc. Verdictul pentru ambele rute
este păstrarea scorurilor existente. Cele 233 de rânduri evaluate sunt protejate.
[Politica, scenariile și motivele deciziei](../research/2026-11-05-automatic-promotion.md).

Experimentul propus pentru salturile de ≥2 este încheiat. Pe ruta fără
frecvență regula evită 0 erori și pierde 2 corecții utile în pilotul de 150,
câte una la nivel uman 4 și 5. În lotul de risc de 50 evită 3 erori și pierde 0,
cu zero intervenții la nivelurile umane 4/5. Pe fallback mai rămân 9/45 erori
severe în lotul de risc. **Decizie recomandată:** închidem această variantă.
Folosim diferența de ≥2 ca indicator de dezacord la audit. Scorul istoric singur
nu justifică alegerea între cele două estimări. Păstrăm ambele rute provizorii și
regulile operaționale de upload. [Comparația pereche](../research/2026-11-05-automatic-promotion.md#rezultatul-regulii-de-păstrare-la-salturi-de-2).
