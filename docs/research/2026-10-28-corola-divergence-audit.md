# Audit local al divergențelor CoRoLa — 2026-10-28

**Decizie: păstrăm wordfreq + fallback 4.** Auditul explică limite concrete ale
frecvenței și identifică o îmbunătățire justificată a extragerii dovezilor lexicale.
Nu identifică o regulă de scor validată care să înlocuiască baseline-ul.

Au fost auditate cele nouă forme cu predicții CoRoLa diferite de baseline în cel
puțin una dintre cele trei evaluări, plus ata, carter și dorian din ruta wordfreq.
Doar fișiere existente: dicționare salvate, evaluări importate, frecvențe, modele de
fold și contextele FineWeb deja păstrate. Fără reetichetare, recalibrare, descărcări,
D1, bază de date sau sarcini noi pentru utilizator. Rezultatele experimentului
anterior rămân neschimbate: MAE actuală 0,520→0,533; erori ≥2 niveluri 11→13.

## Registrul celor 12 cazuri

H = evaluarea umană actualizată; B = baseline; C = candidatul CoRoLa. Frecvențele
sunt apariții ale formei, cumulate după normalizarea deja fixată. Descrierile de
sens provin din dicționarele locale; numai etichetele umane existente stabilesc H.

| Formă | Sens/POS susținut local | H | B→C actual | CoRoLa | Concluzie |
|---|---|---:|---:|---:|---|
|anhidrit|Substantiv neutru: sulfat natural de calciu, mineral.|4|4→4|26|Doar evaluările istorice produc 5. Eticheta proprie rămâne 4; se schimbă pragul învățat din celelalte etichete.|
|antereu|Substantiv neutru, variantă explicită a lui anteriu; utilizatorul a ales sensul de sutană.|3|4→5|20|Revizuire umană explicită 5→3. Extractorul lexical marchează încă nerezolvată legătura cu anteriu, deși sursa o atestă.|
|bromocet|Substantiv neutru: dezinfectant; o intrare salvată îl marchează farmaceutic.|5|4→5|15|Corecție față de eticheta existentă; sens susținut. Nu dovedește că toate cuvintele farmaceutice sau rare merită 5.|
|clevetitor|Substantiv masculin / adjectiv: persoană care bârfește, vorbește de rău.|4|4→5|18|Eroare nouă. Sens/POS atestate; context FineWeb compatibil. Aceeași frecvență ca xilem, etichetat 5.|
|diorit|Substantiv neutru: rocă eruptivă folosită la construcții/ornament.|5|4→4|20|Contextele FineWeb păstrate sunt compatibile cu roca. Frecvență identică lui antereu; 5 apare doar în evaluările istorice.|
|hipochinezie|Substantiv feminin, medicină: scăderea capacității de mișcare.|5|4→5|12|Corecție față de eticheta existentă. Excluderea automată a majusculelor ar lăsa doar 2 apariții, sub pragul de suport.|
|ițar|Substantiv: pânză groasă, sens masculin singular învechit/regional; separat, piesă de țesut, neutru.|4|4→5|9|Pânza a primit 4, mecanismul 5; minimul rămâne 4. Pantalonii ițari sunt exclusiv plural și nu justifică forma singulară.|
|sezisa|Verb, variantă explicită a lui sesiza; există și intrare istorică SEZISA.|3|4→5|19|„A observa/înțelege” are 3; celelalte sensuri revizuite au 5. Minimul valid este deja stabilit, nu lipsește o evaluare.|
|xilem|Substantiv neutru, botanică: țesut lemnos conducător.|5|4→4|18|Contextul FineWeb păstrat este compatibil cu sensul botanic. Aceeași frecvență ca clevetitor; doar evaluările istorice produc 5.|
|ata|Substantiv feminin: variantă atestată a lui atu, cu sensuri de joc/avantaj și bani în argou.|5|3→3|645|Toate cele trei contexte evaluate au 5. Ata nu este ață. Datele de corpus pot amesteca grafii fără diacritice și alte utilizări.|
|carter|Substantiv neutru: carcasă mecanică; separat, unitate de volum.|5|2→2|1.532|Ambele contexte au fost evaluate cu 5. Numele propriu Carter este un risc documentat în contextele păstrate.|
|dorian|Substantiv masculin/adjectiv: persoană din populația doriană / referitor la dorieni; și dialect, substantiv neutru.|5|2→2|853|Există sensuri lexicale valide; contextele FineWeb păstrate sunt nume de persoane. Eticheta rămâne cea originală de formă/POS, fără inventarea unor scoruri per sens.|

Șapte dintre cele 12 etichete rămân din categoria originală opacă formă/POS; patru
au minimul contextelor auditate, iar antereu are alegere explicită de sens pe fișa
formei. Auditul dicționarelor nu transformă cele șapte etichete opace în etichete
noi de sens și nu deschide o nouă rundă de evaluare.

## 1. Frecvența singură nu identifică familiaritatea

Două coliziuni exacte în CoRoLa:

- **antereu și diorit:** 20 de apariții, etichete actuale **3 și 5**;
- **clevetitor și xilem:** 18 apariții, etichete actuale **4 și 5**.

Orice funcție deterministă care folosește numai această frecvență trebuie să dea
același scor membrilor unei perechi. Prin urmare, nu poate reproduce ambele etichete:
eroarea absolută totală minimă pe pereche este cel puțin 2, respectiv 1. Aceasta
este o limită descriptivă pe cele două perechi, nu o estimare a erorii întregului
inventar și nici un argument pentru schimbarea etichetelor.

Predicțiile out-of-fold pot totuși diferi între membrii perechii, fiindcă provin
din modele diferite. În cele nouă cazuri auditate, pragul actual 4/5 corespunde
aproximativ la **16,02 sau 25,39 apariții**, în funcție de grupul exclus. De exemplu,
înlăturarea lui antereu din antrenare produce un prag 25,39 și predicția 5;
înlăturarea lui diorit produce un prag 16,02 și predicția 4. Niciuna nu folosește
propria etichetă ținută în afara antrenării. Diferența arată instabilitatea pragului
pe puține exemple și clase suprapuse, nu o eroare de implementare sau o regulă
semantică învățată. Nu am ajustat pragul după observarea acestor cazuri.

Istoricul etichetelor explică și diferențele între rapoarte: antereu este 5 la prima
rundă și 3 după alegerea sensului; ițar este 3 la prima evaluare independentă,
4 la finalul acelei runde și 4 după contexte; dorian este inițial independent 4,
apoi 5. Ata nu are răspuns independent anterior expunerii în setul de 149; câmpul
rămâne absent. Anhidrit, diorit și xilem nu și-au schimbat etichetele, dar își schimbă
predicțiile când modelul este antrenat cu celelalte etichete istorice.

## 2. Majuscule și grafii ambigue: diagnostic, nu filtru automat

ZIP-ul CoRoLa deja descărcat conține `corola_word_freq_all.tsv`, cu capitalizarea
păstrată. L-am citit local, fără extragerea unui fișier nou pe disc. Pentru toate
cele 12 forme, suma variantelor de capitalizare reproduce exact frecvența din
experiment. Nu am folosit acest membru pentru antrenare sau schimbarea scorurilor.

| Formă | Total | Numai minuscule | Cu cel puțin o majusculă | Proporție cu majuscule |
|---|---:|---:|---:|---:|
|carter|1.532|105|1.427|93,1%|
|dorian|853|9|844|98,9%|
|ata|645|155|490|76,0%|
|hipochinezie|12|2|10|83,3%|

Contextele FineWeb existente pentru carter menționează Viviane Carter și Jimmy
Carter; cele pentru dorian menționează Dorian Furtună și Dorian Micu. Ele dovedesc
utilizări ca nume în acele fragmente. Combinate cu distribuția CoRoLa, susțin
riscul de amestec lexical/nume; **nu măsoară procentul de nume în CoRoLa sau în
wordfreq**. Majuscula poate marca și început de propoziție, titlu sau acronim.
Nu eliminăm automat majusculele: chiar hipochinezie, o corecție reușită în experiment,
ar pierde suportul minim dacă am păstra numai cele două apariții cu minuscule.

Pentru ata, contextele FineWeb păstrate folosesc ata în expresii despre cusut și
„fir de ata”, compatibile cu ață scris fără diacritice, nu cu sensurile lexicale
ata evaluate de utilizator. CoRoLa are și 373 apariții ATA; lista agregată nu permite
stabilirea sensului lor. Nu transferăm frecvențele de la ață, atu sau forme înrudite.
Numărarea exactă a textului nu poate reconstitui diacriticele pierdute în textul-sursă.

Surpriză verificată: membrul cu capitalizare însumează **637.767.064** tokeni, iar
lista lowercase folosită inițial **637.764.339**, diferență de **2.725**. Cauza nu este
stabilită de fișierele inspectate. Toate cele 12 ținte se reconciliază exact;
păstrez separat totalurile și nu schimb normalizarea experimentului anterior.
Metadatele/hashurile fiecărui membru sunt în `case-source.json`.

## 3. Lipsuri concrete ale dovezilor lexicale extrase

Există o regulă generală justificată pentru o îmbunătățire a **extragerii dovezilor**:
recunoașterea relațiilor de variantă explicit atestate, cu sursă și domeniu gramatical.

- **antereu:** `senses.csv` îl marchează nerezolvat fiindcă titlul principal este
  anteriu. Snapshotul JSON conține explicit „Var.: antereu s. n.”, precum și o
  trimitere de la ANTEREU la anteriu. Sensul de sutană nu a fost inventat de fișa UI.
- **sezisa:** titlul principal sesiza împiedică alinierea extractorului. Snapshotul
  conține atât declarația de variantă, cât și definiții cu titlul SEZISA. Sensul
  deja evaluat cu 3 are suport lexical; lipsa alinierei automate nu înseamnă lipsa
  unui sens valid.
- **ata:** sursa selectată de extractor ajunge la familia ață și rămâne nerezolvată.
  Alte înregistrări deja salvate atestă ata ca feminin cu plural atale și relația
  cu atu; snapshotul atu conține explicit varianta, sensurile de joc/avantaj și
  înregistrarea argotică pentru bani. Fișierul atu nu apare în ledgerul de surse
  atribuite lui ata în experimentul lexical anterior. Este o lipsă de selecție și
  de relație între surse, nu permisiunea de a elimina diacritice din potrivire.

Aceste lipsuri apar în extractorul lexical anterior, **nu în numărarea CoRoLa**.
Corectarea lor poate face dovezile mai complete și verificabile; nu demonstrează
că MAE va scădea. Etichetele și scorurile experimentelor finalizate rămân intacte.

## Recomandare actualizată

1. **Păstrează scorerul înghețat wordfreq + fallback 4.** Nu promova fallback-ul
   CoRoLa și nu introduce excepții de scor pentru cele 12 cuvinte.
2. **Următorul pas util: corectarea dovezilor lexicale, prin regulă generală.**
   Folosește sursele locale existente pentru martori expliciți de variantă/trimiteri
   între intrări; înregistrează forma exactă, POS al variantei, sensul și restricțiile
   de număr, plus fișier/hash/intrare. Transferul lexical trebuie susținut explicit;
   asemănarea de grafie, redirectul singur și pagina ață nu sunt suficiente pentru ata.
   Nu cumula frecvențele variantelor și nu deduce familiaritatea din sinonim.
3. **Păstrează separat indicatorii de calitate ai frecvenței.** Capitalizarea,
   posibila lipsă a diacriticelor și lipsa contextului sunt metadate de diagnostic,
   nu reguli de scădere/creștere a scorului. Includerea lor nu necesită D1 sau alte
   etichete umane. Datele CoRoLa derivate rămân locale, pentru cercetare necomercială.
4. Verifică eventuala corecție a extractorului la interfața CSV, cu cazuri pozitive
   de variantă explicită și negative pentru ață/ata, transfer de plural ițari/ițar
   și presupuse rude bazate doar pe grafie. **Nu porni încă o căutare de praguri**
   pe aceleași 150 de etichete. O nouă comparație de scoruri ar necesita o ipoteză
   generală declarată înainte, după corectarea dovezilor; nu este autorizare de
   promovare și nu produce validare externă.

Auditul solicitat este încheiat. Nu există o rundă nouă de evaluări pentru utilizator.
Rămân limitele de generalizare, sens/POS în corpus și discriminarea fiabilă 4/5.
Nu este necesară încă o descărcare pentru următorul pas de inginerie recomandat.

## Artefacte și verificare

`build/d1/corola-divergence-audit-2026-10-28/`:
`audit.py`, `cases.csv` (12 forme), `fold-diagnostics.csv` (35 înregistrări din cele
3 vederi), `case-counts.csv`, `case-source.json`, `frequency-ties.json`,
`dictionary-witnesses.json`, `evidence.json`, `manifest.json`.

Manifestul leagă 492 fișiere de intrare prin SHA-256, inclusiv etichetele, sursele,
rezultatele CoRoLa și scorerul înghețat. Verificate hashurile artefactelor existente,
checksumul ZIP, CRC/hashul membrului citit, reconcilierea tuturor celor 12 forme,
excluderea grupului din antrenare și neschimbarea intrărilor. Nu a fost modificat
codul de producție; nu a fost necesară repetarea suitei de teste a scorerului.


Verificarea independentă a trecut: 492 hashuri de intrare, 12 cazuri, 35 folduri,
16 martori lexicali bruți, ambele liste din ZIP, minimele umane și coliziunile de
frecvență. Rezultatul și limitele interpretării: `verification.json`.
