# D1 Score v2: candidat și următoarea implementare

Stare: **implementat, testat, executat și respins pe criteriile predeclarate**.
800/800 apeluri Score secvențiale; scoruri umane și DB nemodificate.
[Rezultate complete](../research/2026-11-07-d1-score-v2.md).

## Rezultatul iterației

- [x] Validator lexical comun; Score explicit, Choice implicit neschimbat.
- [x] Mediana istorică; replay1.000/1.000; schema dovezilor corectate1.150/1.150.
- [x] CSV reluabil, receipts native, arhivarea eșecurilor, oprire la eșec;
  după execuție, test și refuz al reluării implicite peste un eșec salvat.
- [x] Patru brațe pe150/50,800 apeluri; RAM verificat; D1 descărcat la final.
- [x] Audit integral: cereri, matrice experimentală, identități, buget,
  secvențialitate și integritatea surselor. Comparația respinge loturi trunchiate.
- [x] Analiză separată4/5, cost peste±1, distribuții și constant3.

Erori≥2 pe150/50: baseline11/13; A43/7; B59/6; C64/6; D72/6.
Niciun candidat trece. D:147/150 scoruri3; erori la referințele5:21/22 și5/6.
Îmbunătățirea mică pe50 nu compensează regresia pe150; fără promovare.

### Ce rămâne și pasul următor

1. Review/PR pentru infrastructură, teste, protocol și rezultatul negativ;
   nu activarea promptului v2 în producție.
2. Păstrăm baseline + prioritatea evaluărilor umane; închidem această ramură de
   prompturi. Nu extindem D1 v2 pe1.000 și nu schimbăm decodorul post-hoc.
3. Pentru îmbunătățirea inventarului: prioritate dovezilor de frecvență/fallback.
   D1 rămâne diagnostic de dezacord. Altă familie de decizii ar necesita un
   protocol nou, nu ajustări până trec aceste aceleași etichete.
4. Nicio evaluare nouă cerută utilizatorului; nicio operație DB în acest pas.

Secțiunile următoare păstrează designul predeclarat și justificarea implementării.

## Candidatul

- `prompts/d1-score-exact-form-v2.candidate.json`: întrebare nativă Score,
  cu `type`, `instructions`, cinci `criteria` în ordinea rarității1–5.
- `prompts/d1-score-exact-form-v2-instructions-only.candidate.json`: aceleași
  instrucțiuni noi, exact criteriile vechi; izolează modificarea scării.
- Controlul rămâne banca înghețată a campaniei1.000. Drafturile anterioare nu
  sunt înlocuite; v2 le sintetizează și elimină regulile few-shot neutilizate.

Instrucțiuni:190cuvinte, față de217 în control. Criteriile sunt mai explicite;
nu susținem că întregul mesaj este mai scurt sau că formularea nouă este mai bună
înaintea unui experiment. Fără exemple de cuvinte, etichete sau predicții externe.

Reguli centrale: forma exactă și diacriticele, toate POS admise, relația explicită
cu intrarea-sursă, restricții atașate sensului potrivit, sensul valid cel mai
familiar. Înțelegerea definiției sau deducerea morfologică nu demonstrează
familiaritate. Nivel3 nu este categoria „nu știu”; nivel5 nu presupune obligatoriu
arhaism. Lipsa documentării nu impune3 sau5 și nu anulează un POS valid.

Aceste instrucțiuni sunt ipoteze de remediere. Nu rezolvă prin ele însele
distribuțiile native prea răspândite sau eșecurile medianei la referințele5.

## Prima felie de implementare: un singur caz CSV cap-coadă

**Dovezi corectate → cerere D1 Score → răspuns nativ păstrat → CSV reluabil.**
Mai întâi TDD offline, cu transport fals la limita HTTP; nu încă un lot de inferență.
Interfețele CSV de dovezi și evaluare au fost deja convenite în această sesiune.

Arhitectură verificată în checkout-ul integrat:

1. **Validare lexicală comună.** Validatorul existent din `chat_judge.py`
   acceptă deja `form_relation` și `missing_definition_pos`; este folosit de
   exportul dovezilor, corectarea lor și filtrul offline. Extragem această logică
   într-un modul lexical comun și actualizăm importurile fără schimbare semantică.
   Evităm un al doilea validator D1 care ar respinge sau elimina aceste câmpuri.
2. **Extindere mică a `D1Scorer`.** Mod explicit `score`, cu `choice` păstrat
   implicit. Configurația întrebării este validată și înghețată. Păstrăm
   `BatchScorer`/`Outcome`, transportul, preflight-ul și validarea distribuției.
   Score verifică și legenda nativă0..4, apoi folosește aceeași mediană inferioară
   ca experimentul istoric; nu citește câmpul nativ scalar drept scor1..5.
3. **Reutilizarea `run_campaign`.** Rulează deja câte un element, păstrează
   răspunsurile native și refuză reluarea cu configurație diferită. În manifest:
   hash-urile întrebării/dovezilor, schema lexicală, versiunea decodorului,
   identitatea/configurația modelului. Nu introducem un nou orchestrator.

Collectorul experimental Choice/Score/Noul din `build/d1/exact-form-code` nu
există ca modul în checkout-ul integrat inspectat. Nu îl copiem integral doar
pentru acest pas: noua nevoie este Score în infrastructura existentă, fără
introducerea implicită a încă cinci apeluri per formă.

Teste RED→GREEN, câte un comportament la interfețele publice:

- Cererea păstrează forma, toate POS, relația variantei, restricțiile și lipsurile
  declarate; nu introduce coloane de etichetă/scor/propunere externă.
- Variante cu grafie-sursă diferită sunt acceptate numai cu relație explicită
  validă; nepotrivirile de ID/grafie și POS coverage inconsistent sunt respinse.
- Score are exact cinci probabilități finite și normalizate, legendă identică;
  mediana0..4→1..5 și egalitatea la0,5 reproduc contractul existent.
- O secvență de două forme face cererile în ordine; eșecul rămâne în receipt,
  iar reluarea nu repetă rezultatele valide. Schimbarea promptului/dovezilor
  refuză campania veche. Datele istorice nu se rescriu.
- Comportamentul Choice și campaniile existente rămân compatibile.

Apoi verificăm offline schema tuturor1.000 de forme și replay-ul răspunsurilor
Score existente. O reimplementare a decodorului trebuie să reproducă toate
scorurile salvate înaintea oricărei comparații de prompt.

## Experimentul predeclarat, executat după autorizarea inferenței

Patru brațe, aceeași configurație și mediană fixă:

| Braț | Dovezi | Instrucțiuni | Criterii |
|---|---|---|---|
|A|istorice|istorice|istorice|
|B|corectate existente|istorice|istorice|
|C|corectate existente|v2|istorice|
|D|corectate existente|v2|v2|

B−A izolează dovezile; C−B schimbarea instrucțiunilor; D−C schimbarea scării.
V2 include mai multe clarificări în instrucțiuni: C−B măsoară efectul lor comun,
nu demonstrează separat fiecare mecanism. Acest design concretizează și înlocuiește
matricea preliminară cu drafturi adăugate peste control; acelea rămân artefacte istorice.

Mai întâi150 și50 separat: maximum800apeluri Score secvențiale într-o campanie
proaspătă cu control comun. Fără selecție după cele42 de dezacorduri, fără cereri
noi utilizatorului. Toate sunt referințe de dezvoltare reutilizate, nu test independent.
Fără scoruri umane/baseline/GPT în cereri; contextele curățate cu intervenție umană
își păstrează proveniența și limita de independență. Nu reglăm praguri sau few-shot.

Precondiții de execuție: joburile concurente idle, RAM verificat, un singur model
și apel activ; stop cu checkpoint la evicție sau lipsă de RAM. Managementul
resurselor rămâne în runner, nu în scorer; nu oprim procese străine fără acord.

Raport: erori2/3/4, cost peste±1, MAE, toate referințele4/5, distribuția scorurilor,
concentrarea la3, diagnosticul constant3. Decizie predeclarată:

- față de controlulA, fără agravarea erorilor≥2 sau costului în niciun lot;
- îmbunătățire strictă în cel puțin un lot și fără regresie separată la4 sau5;
- performanța față de baseline rămâne vizibilă: câștigul față de D1 vechi nu
  este suficient pentru înlocuirea baseline-ului;
- lipsa unui câștig înseamnă oprirea acestei ramuri, nu reglaj până trece.

Chiar dacă trece, nu aplicăm scoruri automat. Extinderea candidatului pe1.000
este un pas separat, pentru acord și audit; cele950 fără etichete nu oferă
acuratețe măsurată. Promovarea în producție rămâne în afara experimentului.
