# Export conservator al inventarului — 2026-11-01

Export complet, offline, separat de scorurile operaționale. Cele200 evaluări umane
au prioritate pentru forma exactă, peste toate ID-urile/POS-urile; baseline-ul
wordfreq + fallback înghețat se păstrează pentru rest. Modelele furnizează numai
conflicte diagnostice. Zero apeluri LLM, subagenți, încărcări modele sau operații DB.

## Rezultate

| Măsură | Rezultat |
|---|---:|
| ID-uri / forme distincte |77.698 /75.147|
| Forme evaluate uman / ID-uri acoperite |200 /233|
| Rânduri cu baseline păstrat |77.465|
| Forme / rânduri schimbate numeric |99 /117|
| Forme fără evaluare umană |74.947|
| Nivel1 /2 /3 /4 /5, pe ID-uri |978 /6.291 /4.389 /66.009 /31|

Toate scorurile sunt1–5, acoperire100%. Cele101 forme umane cu scor identic
baseline-ului păstrează statutul `human_reviewed`; egalitatea nu șterge proveniența.
Restul au `provisional_baseline`. Concordanța cu cele200 evaluări este prin
construcție, **nu** un nou rezultat de acuratețe sau validare populațională.

Baseline: exportul complet din2026-10-24, model
`8f3061e2332cf9d6844ff4ea9dabd4fd23111c04b713a8a0cde886a23c82e0cc`.
Fără recalibrare. Scorurile sale fitted nu se confundă cu predicțiile OOF folosite
în comparațiile istorice150/50. Surse umane: referința finală150 din2026-10-21
(identică prin SHA cu copia GPT) + cele50 răspunsuri importate din site.
Scorurile și observațiile originale rămân intacte.

## Proveniență și conflicte

Normalizare numai NFC, ș/ț cu virgulă și casefold. Fără eliminarea/restaurarea
diacriticelor, transfer de lemă sau flexiune: `ata` și `ață` rămân distincte.
Fiecare referință este verificată față de ID și grafie înaintea propagării pe POS.
Două referințe umane contradictorii pentru aceeași formă opresc exportul; nu se
calculează medii și nu se ghicește prioritatea. Nicio contradicție în sursele actuale.

| Conflict separat | Total | Diferență≥2 |
|---|---:|---:|
| Baseline față de evaluarea umană |99|23|
| Observație GPT/Qwen față de candidat |714|160|
| Total observații conflictuale |813|183|

653forme au cel puțin un conflict. Numărătorile nu sunt numere de forme independente:
aceeași formă poate avea mai multe observații. Cele1.331 predicții originale provin
din GPT150+1.000 și Qwen150+31; nu sunt selectate repetările ulterioare favorabile.
Niciun vot, consens sau scor de model nu modifică exportul. Dezacordul cu baseline-ul
provizoriu nu dovedește că modelul greșește. Diferența semnată este observat−candidat.

## Verificările L1: export valid structural, nepregătit pentru upload

Auditul existent folosește numai snapshotul CSV local și cele128 ancore seed.
Identitatea tuturor ID-urilor/grafiilor/POS din snapshot a fost verificată; starea
DB live nu a fost interogată. Pragurile existente rămân Jaccard≥0,7,
precizie ancore≥0,8 și recall≥0,8.

| Verificare | Baseline original | Candidat |
|---|---:|---:|
| Jaccard L1 pe ID-uri |3,180%|3,235%|
| Precizie față de ancore seed |8,161%|8,219%|
| Recall ancore seed |55,469%|56,250%|
| Toate pragurile trecute |NU|NU|

**Surpriză verificată:** baseline-ul original nu trecea nici el aceste praguri;
prioritatea umană le îmbunătățește marginal. Snapshotul are2.500 ID-uri L1,
candidatul978, intersecție109. Ancorele sunt un seed incomplet, nu lista exhaustivă
a cuvintelor comune: această precizie nu este acuratețe lexicală. Nici snapshotul,
nici ancorele nu certifică adevărul scorurilor. Totuși, gating-ul nu se ocolește.
Nu ajustăm histograma, ancorele sau scorurile umane pentru a forța trecerea.

**Recomandare:** păstrarea acestui candidat versionat; audit offline al divergenței
L1 și al acoperirii/provenienței ancorelor înaintea oricărei decizii de upload.
Separarea diferențelor de inventar, definiție a clasei și scor, pe dovezile deja
existente. Nu se cer alte evaluări utilizatorului și nu se declară că cele950 forme
noi fără referințe sau distincția automată4/5 au devenit validate.

## Fișiere și reproducere

Director local: `build/d1/conservative-export-2026-11-01/` din checkoutul principal.

- `export/candidate.csv`: toate ID-urile, scor final/baseline, sursă, statut, forma exactă.
- `export/provenance.csv`: câte o formă, toate ID-urile/POS, frecvența/ruta/modelul,
  cheile referințelor și observațiilor.
- `export/references.csv`, `observations.csv`, `sources.csv`: proiecții verificabile
  și fișiere originale cu SHA256; eșecurile model ar rămâne explicit fără scor.
- `export/conflicts.csv`: numai diferențe nenule, tip, sursă, amplitudine și prag≥2.
- `export/baseline-model.json`, `policy.json`, `summary.json`, `manifest.json`:
  configurație înghețată, politică și hashes.
- `protocol.json`, `quality.json`, `report.json`, `verification.json`: protocol,
  audit și reconciliere independentă. CSV-urile integrale rămân locale; PR-ul
  publică implementarea, testele și aceste agregate.

Din checkoutul PR, cu mediul Python al proiectului; `--output` trebuie să fie nou:

```sh
PYTHONPATH=src python docs/research/2026-11-01-conservative-export/run.py   --base /Users/fabian/git/word-rarity-classifier/build/d1   --output /Users/fabian/git/word-rarity-classifier/build/d1/conservative-export-replay
PYTHONPATH=src python docs/research/2026-11-01-conservative-export/verify.py   /Users/fabian/git/word-rarity-classifier/build/d1/conservative-export-replay
```

Interfața reutilizabilă `export_conservative_inventory` primește inventarul,
baseline-ul, două cataloage CSV de surse (`source_id,path,sha256`) și un director nou.
Export atomic, refuz de suprascriere; verifică sursele, integritatea baseline-ului,
acoperirea și consistența scorurilor între POS. Runner-ul cercetării fixează sursele
acestui experiment; nu este un upload sau un nou orchestrator de modele.

## Validare

TDD pe limita CSV deja aprobată: primul test RED (modul lipsă), apoi GREEN;
prioritate umană peste POS, diacritice distincte, model doar diagnostic, referințe
contradictorii, surse corupte, ID/grafie/nivel invalid, baseline incomplet/inconsistent,
eșec model fără scor, referință egală baseline-ului și replay fără mutații.

Ruff + **940teste,363subteste PASS**. Reconciliere independentă a fiecărui ID,
scor, proveniență, referință și observație; reconstrucție exactă a813conflicte și
aritmeticii auditului. Regenerare cu10artefacte identice byte cu byte;4.688fișiere
protejate nemodificate. Procesele/rețeaua/conexiunile DB blocate în runner și replay.
Verificatorul folosește citire CSV și aritmetică separate de implementarea deciziei.
Corectat înainte de publicare un contor de raportare care includea chei goale
introduse de `defaultdict`; fișierele exportului și scorurile nu au fost afectate.

[Raport JSON](2026-11-01-conservative-export/report.json) ·
[Verificare JSON](2026-11-01-conservative-export/verification.json) ·
[Plan](../plans/2026-10-30-1000-form-risk-review.md).
