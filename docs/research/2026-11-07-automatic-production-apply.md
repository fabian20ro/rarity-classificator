# Scoruri automate aplicate și verificate — 2026-11-07

**APPLIED_AND_VERIFIED.** Utilizatorul a autorizat aplicarea pachetului înghețat.
Cele **50.724schimbări** sunt comise în mediul real:7.537wordfreq și43.187fallback.
Inventarul complet de77.698rânduri coincide cu candidatul acceptat. Cele233rânduri
pentru200forme evaluate de utilizator sunt păstrate integral, inclusiv reviziile.
Nu s-au făcut apeluri LLM, evaluări noi sau schimbări ale politicii.

## Execuție și verificare

Codul de execuție coincide prin hash cu repetiția completă OrioleDB. Pachetul și
candidatul au fost verificate înaintea accesului de scriere:

- pachet `4bbc107268d845c954dbef8749a95704d5e6bcb25b6c20d49fa2f26f57abc090`;
- candidat `d7f52e307c523b74958bad4cf483706159cf843f4dbb593abea477c1611aa8ef`.

Preflight-ul a verificat din nou conexiunea dedicată TLS verify-full,READ ONLY explicit,
cele9condiții de privilegii,întregul snapshot și toate233protecțiile umane.38postchecks
administrative istorice treceau;NOLOGIN era deja intenționat fals după activare.

Aplicare o singură dată, prin fluxul existent și executorul dedicat, cu confirmare
exactă de pachet/epoch. O tranzacție pentru ambele rute,lock-uri,compare-and-set pe
ID/grafie/POS/scor/revizie,un UPDATE parametrizat pentru întregul lot. Număr/ID-uri
exacte,verificarea întregului rezultat și a coloanelor auxiliare,recipisă și verificare
finală după scrierea recipisei. Fără SQL manual de actualizare a scorurilor.

O conexiune separată, explicit READ ONLY, a recitit după commit inventarul și recipisa
la **2026-11-07 01:25:47 Europe/Bucharest** și a confirmat:

| Verificare după commit | Rezultat |
|---|---|
| Inventar complet vs.candidat |77.698/77.698rânduri identice|
| Scoruri schimbate |50.724,exact ID-urile aprobate|
| Rânduri neschimbate |26.974:26.741automate+233umane|
| Revizii pentru schimbări |50.724noi,identice recipisei comise|
| Rânduri umane |Scoruri/revizii intacte|
| Identitate/POS/alte coloane |Neschimbate integral|
| Ledger automat |O recipisă aplicată,identică celei locale|
| Recipise/granturi umane,RLS,epoch,hook-uri |Neschimbate,verificate administrativ|
| Surse/configurații protejate |32pini neschimbați|

35/39postchecks istorice ale instalării trec. Cele4excepții sunt intenționate:
`executor_disabled`,`automatic_ledger_empty`,`inventory`,`installation_receipt_bound`.
Ultimele două fixează snapshotul/digestul/reviziile de dinaintea aplicării;nu sunt
criterii pentru starea nouă. Postcheck-ul acestei operații verifică noul candidat și
recipisa comisă. Nu am modificat verificările vechi sau istoricul instalării.

[Raport agregat](2026-11-07-automatic-production-apply/report.json) ·
[Verificare administrativă](2026-11-07-automatic-production-apply/administrative-checks.json).

## Rezultat și limitele acceptate

| Nivel | Rânduri după aplicare |
|---|---:|
|1|978|
|2|6.291|
|3|4.389|
|4|66.009|
|5|31|

Distribuția este cea a candidatului înghețat,cu prioritate pentru evaluările umane.
Fallback-ul rămâne provizoriu:nu am rezolvat diferența4vs5 prin aplicare. Precizia
întregii populații rămâne necunoscută. Jaccard16,71%,anchor precision8,22%,recall56,25%
rămân FAIL la pragurile originale;au fost calculate față de snapshotul original și
cel curent sub lock,înregistrate ca diagnostice conform politicii explicit acceptate.
Step4/Step5 și fluxul uman nu au fost schimbate. Succesul operațional nu este o nouă
validare de acuratețe.

## Evidență și rollback

Artefacte locale în `build/d1/automatic-production-apply-2026-11-07/`:
`apply/` păstrează CSV-urile înainte/candidat/după/final,metricile și recipisa;
`after/` conține snapshotul recitit independent și recipisa comisă.
**rollback-preconditions.csv** are50.724rânduri cu scorul/revizia comise și scorul
de restaurat. Proiecția inversă verificată offline restaurează exact scorurile
dinainte;**rollbackul nu a fost executat**. Manifest SHA-256 pentru toate artefactele.
Răspunsurile individuale,credențialele și capturile operaționale rămân locale.

Dacă se cere rollback,folosește același flux cu `--action rollback`,pachet/epoch
fixate și un director nou de output. Recipisa din DB și reviziile post-aplicare sunt
precondiții;nu executa CSV-ul invers manual și nu ignora conflictele introduse de
scrieri ulterioare. Un retry apply confirmă istoricul commitului,nu starea curentă;
pentru audit folosește citiri separate.

Nu există schimbări de runtime în această etapă. Repetiția20/20 și suita1.008teste
+479subteste rămân dovezile implementării;validarea nouă este execuția reală și
postcheck-ul complet. Nicio reaplicare sau rollback pe DB real pentru a demonstra teste.

**Obiectiv încheiat:** candidatul automat acceptat este aplicat întregului inventar,
cu evaluările umane păstrate. Urmează review/merge PR89 și păstrarea artefactelor de
recuperare. Îmbunătățirea fallback-ului4vs5 rămâne lucru ulterior separat;nu blocaj
operațional și nu motiv pentru alte evaluări acum. Nu mai este necesară activare,
instalare sau o nouă rulare de clasificare pentru acest pachet.
