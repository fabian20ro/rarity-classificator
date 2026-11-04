# Extragerea variantelor lexicale — 2026-10-28

Corecție exclusiv pentru dovezile lexicale locale. Interfața publică rămâne
`export_local_evidence`: inventar, LOC, registru de surse și mențiuni cu proveniență
→ CSV-uri verificabile. Niciun scor, prag, model, rating sau rezultat anterior nu
este recalculat. Fără D1, rețea, acces la baza de date ori evaluări suplimentare.

## Comportament

O variantă este acceptată numai cu declarație explicită în definiția-sursă.
Marcajul semantic al abrevierii trebuie să însemne „variantă”, nu „vezi”; forma
exactă și POS-ul variantei trebuie să fie identificabile. Se păstrează genul,
restricțiile și identificatorul definiției/dicționarului, plus fișierul și hashul.
Redirecturile, sinonimele, exemplele și asemănarea de grafie nu justifică transferul.

Legarea de sensuri structurate cere aceeași intrare de bază, POS compatibil și
același dicționar citat. Omonimele ambigue și restricțiile de număr insuficient
stabilite rămân nerezolvate. Restricțiile variantei se păstrează separat de cele ale
sensului. Forma exactă rămâne ținta; frecvențele altor forme nu sunt cumulate.

Pentru definițiile MDA2 în formatul restrâns cu antet între paranteze drepte și
sensuri numerotate consecutiv există o extragere directă, limitată la aceeași
înregistrare. Formatele mai complexe nu sunt ghicite. Aceasta permite recuperarea
sensurilor lui ata din MDA2 fără a le împrumuta din sinteza altor dicționare.

- **antereu:** substantiv neutru, prin declarațiile explicite sub anteriu. Sensurile
  de haină preoțească și haină istorică păstrează martorul din dicționarul potrivit.
- **sezisa:** verb, prin declarația DN sub sesiza; sunt păstrate sensurile structurate
  și restricțiile lor, inclusiv utilizarea reflexivă.
- **ata:** substantiv **feminin**, cu restricția MDA2 **învechit și rar**. Cinci sensuri
  numerotate despre carte/culoare de joc și avantaj, fiecare legat de aceeași sursă.
  Nu preia genul neutru al lui atu, definițiile ață sau omonimul monetar at.
- **văietare:** regula generală recuperează și varianta explicită a lui văitare.
  Nu există listă de excepții pentru cele trei cazuri care au declanșat corecția.

## Artefacte și compatibilitate

`evidence.csv` își păstrează schema și politica existentă. `senses.csv` primește
câmpuri suplimentare pentru POS detaliat, identitatea martorului/dicționarului,
restricția variantei și declarația brută. Noul `variants.csv` păstrează martorii și
starea lor explicită. Manifestul include revizia extractorului și hashurile.

Un martor valid de variantă nu înseamnă automat că toate sensurile lui sunt
recuperate. `source_bounded` înseamnă că părțile de vorbire cerute de inventarul LOC
au dovezi în sursele selectate; nu certifică exhaustivitatea semantică sau
familiaritatea. Martorii din fișiere/dicționare diferite sunt păstrați separat;
numărul de rânduri nu este număr de sensuri unice sau de atestări independente.

## Verificare locală

Rulare separată pe aceleași 150 de forme și aceleași mențiuni, cu 169 de înregistrări
în registrul surselor: cele 168 anterioare plus fișierul local atu.html, asociat
explicit țintei ata. Asocierea din registru nu ocolește validarea declarației.

Rezultate finale (`evidence-reviewed/`, revizia `explicit-variants-v1`):

| Măsură | Înainte | După |
|---|---:|---:|
| Forme cu dovezi aliniate la POS din inventar | 123/150 | 127/150 |
| Dintre cele fără frecvență wordfreq | 42/49 | 45/49 |
| Înregistrări de sens, inclusiv nerezolvate | 2.130 | 2.147 |

Toate cele **978 de înregistrări exacte existente** sunt păstrate. Sunt adăugate
**14 înregistrări exacte din surse, pentru 12 perechi formă–sens distincte**:
antereu 3/2, sezisa 4/4, ata 5/5, văietare 2/1 (înregistrări/sensuri).
Celelalte trei rânduri noi provin din sinteza atu/at și rămân nerezolvate.
Registrul variantelor conține 26 de martori: 22 cu relație susținută și 4 nerezolvați.
Schimbări de caracteristici agregate: numai aceste patru forme; ata păstrează
restricția „învechit și rar”. Nicio modificare de scor.

TDD la interfața publică CSV: declarații explicite, POS/gen, dicționar și omonime,
restricții de număr, proveniență; negative pentru trimiteri „vezi”, exemple,
etimologie, POS absent/incompatibil și transfer între surse. Rularea reală a prins
un nod HTML `] – Din` care combina delimitatorul și etimologia: test RED, corecție,
GREEN. Review-ul a prins un POS propriu contradictoriu într-un sens MDA brut:
regresie RED/GREEN, sens păstrat nerezolvat cu motiv `conflicting_meaning_pos`.

Validare finală: **880 de teste + 220 de subteste**, Ruff și `git diff --check` trecute.
Review pe specificație și standarde încheiat; observația POS remediată și reverificată.
Verificator independent, fără importuri din implementare: **PASS** pentru surse,
martori, POS, restricții, retenția sensurilor și hashurile a **1.150 de fișiere
protejate**, inclusiv scoruri, evaluări și configurații. Exportul real a blocat
explicit HTTP, conexiunile de rețea și conexiunea PostgreSQL.

Artefacte autoritative: `evidence-reviewed/{evidence,senses,variants}.csv`,
`evidence-reviewed/manifest.json`, `evidence-reviewed-comparison.json` și
`verification-reviewed.json`. Directoarele `evidence-probe`, `evidence` și
`evidence-final` sunt încercări istorice păstrate pentru trasabilitate; nu reprezintă
exportul final al codului revizuit. Reproducere locală: `run.py NUME_NOU`,
`compare_evidence.py NUME_NOU`, apoi `verify.py CALE_EXPORT`; scripturile sunt în
folderul campaniei. Niciun export existent nu se suprascrie.

## Recomandare și limite rămase

Păstrăm scorerul înghețat **wordfreq + fallback 4**. Dovezile mai complete repară o
lipsă de extracție; nu demonstrează o îmbunătățire a clasificării. Nu folosim
„învechit/rar” ca regulă automată pentru scorul 5 și nu transferăm familiaritatea
între forme.

Sensul argotic „bani” pentru ata nu este recuperat prin declarația MDA2: el aparține
altei surse. Declarațiile fără POS suficient, trimiterile incomplete și formatele
brute neacceptate rămân limitări explicite, fără a schimba etichetele umane existente.
Nu cerem o altă rundă de evaluări.

Următorul pas recomandat este folosirea acestor artefacte ca strat de explicații și
proveniență lângă scorurile deja înghețate, cu stări distincte pentru dovadă prezentă,
relație fără sens recuperat și dovadă nerezolvată. O nouă regulă de scor ar necesita
o ipoteză generală stabilită înainte și verificare separată; această corecție nu
justifică încă o căutare de praguri pe pilotul reutilizat.

Artefacte locale: `build/d1/lexical-variants-2026-10-28/`. Sursele, scorurile și
ratingurile istorice rămân nemodificate; exporturile noi sunt separate și nu se
suprascriu.
