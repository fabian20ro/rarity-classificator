# Politică de acceptare a corecțiilor umane — audit, 2026-11-03

**Lotul satisface politica umană; promovarea rămâne blocată.** Politica versionată
`human-corrections-acceptance-audit-v1` verifică cele 165 de corecții pregătite,
fără să schimbe uploaderul, scorurile sau pragurile operaționale. Mod unic: `audit`.
Zero apeluri LLM, citiri/scrieri DB sau invocări ale uploaderului.

## Contract și criterii obligatorii

Interfață CSV: `audit_human_acceptance(policy_path, output_dir)`. Politica JSON fixează
prin cale și SHA-256 pachetul, planul, exportul cu referințe umane, snapshotul,
candidatul complet și ancorele. Manifestul pachetului fixează întregul set de ID-uri,
identități și valori, nu doar numărul 165. Înregistrarea din repo este politica
acestui lot; modificarea surselor/politicii creează alt audit, nu transferă acceptarea.

| Criteriu v1 | Verificare | Lotul pregătit |
|---|---|---|
| Proveniență și pachet original | Regenerare din plan și răspunsurile umane originale; manifest și artefacte identice, inclusiv rollback | PASS |
| Domeniu fixat | Exact 165 corecții, 233 rânduri protejate, 200 referințe | PASS |
| Toate precondițiile umane | ID, grafie, POS, scor inițial și apartenența completă la forme, inclusiv cele 68 de rânduri deja corecte | PASS |
| Candidat integral exact | Snapshot + exclusiv corecțiile din pachet; niciun alt ID, scor, cuvânt sau POS schimbat | PASS |
| Inversa | Rollback aplicat numai în memorie candidatului restabilește fiecare rând/scor al snapshotului | PASS |
| Stabilitate L1 | Jaccard pe întregul inventar ≥0,70, același prag existent | PASS: 0,964594807 |

Versiunile/modurile necunoscute, câmpurile sau pragurile suplimentare, lipsa hashurilor,
scorurile ambigue și manifestele nereproductibile sunt refuzate înainte de publicarea
raportului. Politica nu admite configurarea pragului pentru a obține PASS.
Snapshotul trebuie să fie exact referința planului fixat; candidatul nu poate deveni
propria referință. ID-uri canonice unice, niveluri 1–5, o singură coloană de scor.

Dacă datele sunt valide, dar domeniul, candidatul sau stabilitatea nu corespund,
auditul publică `human_policy_satisfied=false`, criteriile și diferențele pe rând.
Ieșire atomică într-un director nou, fără suprascriere. O referință/țintă/guardă/inversă
modificată și apoi rehashuită nu trece simplu drept pachet original: replay-ul verifică
sursele până la răspunsurile `working_level`. Hashurile sunt proveniență verificabilă,
nu semnătură sau dovadă independentă a identității evaluatorului.

## Rolul ancorelor și limitele deciziei

Scorurile umane originale au prioritate în această politică de audit. Ancorele
pozitive sunt dovezi separate: nu considerăm toate formele absente din seed greșite.
Eventualele contradicții directe seed–referință umană sunt enumerate în
`seed-conflicts.csv`, fără rescrierea scorurilor. Pe lotul existent: **zero contradicții**.
Aceasta nu demonstrează exhaustivitatea seed-ului sau precizia globală.

Gate-ul operațional este calculat separat, pe aceleași 77.698 de rânduri:

| Metrică legacy | Rezultat | Prag | Stare |
|---|---:|---:|---|
| Jaccard L1 | 96,459% | ≥70% | PASS |
| Apartenență L1 la seed | 4,770% | ≥80% | FAIL |
| Recall seed | 42,969% (55/128) | ≥80% | FAIL |

`human_policy_satisfied=true` înseamnă conformitate cu cele șase criterii de audit,
**nu acceptare operațională**. Raportul păstrează `legacy_gate.passed=false`,
`promotion_blocked=true`, `upload_authorized=false`, `rollback_authorized=false`.
Chiar și o combinație perfectă de metrici păstrează aceste blocări în mod audit.
Precizia semantică a seed-ului și acuratețea populației sunt `null`, nu 100%.
Acordul cu etichetele folosite la override este integritate, nu validare independentă.

Snapshot reutilizat: **2026-11-02T20:32:03.276616Z**. Nu a fost recitit DB.
`as_of=2026-11-03` datează auditul, nu dovedește prospețimea datelor.
`freshness_verified=false`, `apply_receipt_verified=false`. Nicio simulare nu
constituie recipisă de execuție sau permisiune pentru rollback.

## Verificare și reproducere

- TDD pe limita CSV deja agreată: **7 teste noi, 26 de subcazuri**. RED→GREEN pentru
  politica audit-only, pachet rehashuit, moduri/praguri/snapshot nepermise, coloane
  de scor ambigue, diagnostice pe candidat și verificarea inversei.
- Regresii: modificări în afara lotului, grafie cu diacritice, POS/ID lipsă sau nou,
  rând uman deja corect, scope greșit, Jaccard 0,5 respins, metrici perfecte fără
  autorizare, replay offline și refuz de suprascriere.
- `python scripts/check.py`: **Ruff + 963 teste și 422 subteste PASS**.
- **4.778 fișiere protejate intacte**, inclusiv vechiul pachet și toate referințele.
- **10 fișiere de audit identice byte cu byte la replay**; cele 165 de ID-uri și
  valori reconciliate independent cu diferența snapshot–candidat.
- 200 de referințe păstrate; 77.533 de rânduri neschimbate. Inversa restabilește
  toate valorile/identitățile; testul byte-identic al CSV-ului restaurat rămâne
  documentat în etapa precedentă.

Din checkoutul PR, cu mediul Python existent:

```sh
PYTHONPATH=src python docs/research/2026-11-03-human-acceptance/run.py --output /Users/fabian/git/word-rarity-classifier/build/d1/human-acceptance-replay
```

Runner-ul folosește implicit politica fixată alături de el, cere director nou și
blochează transportul de rețea, procesele și conexiunile DB. Sursele locale originale
sunt necesare; o copie izolată a raportului nu poate verifica proveniența completă.

Artefacte locale: `build/d1/human-acceptance-2026-11-03/`: criterii, probleme pe
candidat, corecțiile așteptate, contradicții seed–uman, verificarea precondițiilor,
politică, raport, manifest și verificarea independentă. Nu sunt o comandă de upload.
Publicăm numai codul/testele, politica și agregatele; datele individuale rămân locale.

## Următorul pas

Politica de audit este implementată și verificată; nu mai este necesară încă o
rundă de evaluare sau de calibrare. **Următoarea decizie este promovarea explicită
a acestei politici într-un flux operațional separat pentru corecții umane.** Aceasta
ar necesita o decizie arhitecturală despre rolul seed-ului incomplet față de etichetele
umane; prezentul PASS nu înlocuiește și nu dezactivează gate-ul obligatoriu existent.

După acea decizie: executor tranzacțional cu verificarea live a tuturor precondițiilor,
protecție la concurență, aplicare atomică și recipisă durabilă; rollback numai pentru
ID-urile confirmate în recipisă și fără conflicte ulterioare. Până atunci, nici lotul
uman și nici cele 50.724 de schimbări baseline provizorii nu sunt aplicate. Precizia
L1 globală și discriminarea automată 4/5 rămân nevalidate.

[Politica fixată](2026-11-03-human-acceptance/policy.json) ·
[Raport](2026-11-03-human-acceptance/report.json) ·
[Verificare](2026-11-03-human-acceptance/verification.json) ·
[Plan](../plans/2026-10-30-1000-form-risk-review.md).
