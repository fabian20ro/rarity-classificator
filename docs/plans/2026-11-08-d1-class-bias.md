# Corecții regularizate pe clase — protocol offline

2026-11-08. Protocol fixat înaintea calculului pe datele reale.

## Model și validare

Aceleași distribuții control A, forme și referințe din v3. Interfața CSV deja
convenită: inputuri înghețate → predicții, probabilități, ledger complet, raport.
Fără LLM, evaluări noi sau DB. Baseline și scorurile umane rămân neschimbate.

q = softmax(log(max(p,1e-12)) + b). Cinci biasuri, sumă zero (patru grade de
libertate). Temperatura fixă1; temperatura anterioară rămâne comparator separat.
Nu adăugăm simultan un parametru de scală. Decoder: aceeași mediană inferioară.

Fit: mean NLL + lambda/2 * sum(b²). Grilă fixă lambda=[0.01,0.1,1,10] plus
identitate b=0. Alegere după NLL agregată pe toate rândurile inner-heldout;
egalitate în1e-10 → regularizare mai puternică, identitate prima.
Gradient descent determinist, pas1/(0.5+lambda), gradient maxim≤1e-9,
maximum10.000 iterații; neconvergență → eșec, fără rezultate parțiale.

150: cele cinci folduri istorice pe grupuri. Fiecare outer-train păstrează
patru folduri pentru CV internă; outer-heldout exclus din fit ȘI din alegerea
lambda. Minimum trei folduri la interfața reutilizabilă. Pentru50, alegem lambda
prin CV pe toate cele cinci folduri150, apoi refit pe150. Niciun reglaj pe50.
În ledger: fiecare candidat/fold intern, train/validation IDs, coeficienți,
NLL nepenalizată de validare, parametru ales și refit final.

## Comparație și criterii

Baseline, D1 nativ, afin v3, temperatură, bias regularizat. Erori≥2, exces
sum(max(|eroare|-1,0)), MAE, clasele reale1/4/5, lipsa frecvenței, NLL/Brier,
confuzie și erori evitate/introduse. Toate formele incluse.

Gate neschimbat: fără regresie severe/exces față de baseline în fiecare lot,
global și true1/4/5, câștig strict global în cel puțin un lot. Subset gol →
necunoscut; fără promovare automată. Lot50 explorat și selectat pentru risc,
fără true1: verificare descriptivă, nu estimare pentru inventarul complet.

## Pași

1. TDD la limita CSV: corectarea biasului cunoscut, identitate, regularizare,
   izolare nested-CV/50, date invalide, probabilități zero și surse intacte.
2. CLI offline; export complet al selecției și comparațiilor, hash-uri.
3. Rulare150/50; solver independent, replay, mutații temporare pentru auditul
   izolării, suite offline. Analiză și recomandare fără reglaje post-hoc.

## Executat și verificat

- [x]10 teste noi; soluție analitică pentru bias, identitate, nested leakage,
  clase absente/zero probabilități, minimum3folduri, integritate și output atomic.
- [x] CLI reutilizabil offline; toate candidatele/fiturile/IDs/NLL în ledger.
- [x] Comparație completă150/50;1069passed,78skipped,479subtests; Ruff PASS.
- [x] Audit independent104 fituri SciPy,6 verificări reale de izolare,
  selecție pooled și gate verificate; replay identic,210 surse originale intacte.
- [x] [Analiză și artefacte](../research/2026-11-08-d1-class-bias.md).

Lambda outer:1,identitate,identitate,10,1; full150→50:10. Corecțiile sunt mici.
Erori≥2:41/150 și7/50; baseline11/150 și13/50; temperatură32/150 și7/50.
True1 pe150:19/51; true4:3/21; true5:18/22. True5 pe50:6/6.
Față de D1 nativ se evită3 și se introduce1 eroare pe150; pe50 predicțiile sunt
identice. NLL se înrăutățește ușor pe ambele loturi. **Gate FAIL.**

## Rămâne / următorul pas

1. Review/publicare a acestei iterații; fără push în această execuție.
2. Păstrăm baseline și scorurile umane; nu extindem candidatul la inventar.
3. Nu prioritizăm un calibrator global mai complex pe aceleași etichete.
   Opțiune separată, dacă continuăm offline: decoder ordinal fix pentru costul
   tolerat±1, fără parametri noi, cu constant3 drept control și gate1/4/5.
   Protocolul și tie-break-ul trebuie fixate înainte; neimplementat aici.
4. D1 simplu amânat; nicio evaluare nouă, apel LLM sau operație DB necesară aici.

## Continuare: decoderul ordinal

2026-11-08: [decoderul ordinal fix](2026-11-08-d1-ordinal.md) implementat și
verificat offline.46/150 și6/50 erori severe; constant3 73/150 și6/50.
Gate baseline și constant3 FAIL. Opțiunea de experiment propusă mai sus este
executată; păstrăm baseline-ul și recomandăm consolidarea rezultatelor.
