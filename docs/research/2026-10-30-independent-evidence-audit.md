# Auditul dovezilor pentru 1.000 de forme — 2026-10-30

Etapa 1 implementată și rulată offline. Forma exactă, toate POS valide, sensuri și
restricții cu proveniență; fără scoruri noi, inferență, evaluări umane sau modificări DB.

## Rezultate

| Verificare | Rezultat |
|---|---:|
| Forme păstrate | 1.000/1.000 |
| ID-uri originale reprezentate | 1.146/1.146 |
| Surse cache cu identitate exactă, status ok | 137 |
| Cache absent | 801 |
| Cache găsit pentru altă grafie, exclus | 62 |
| Forme cu cel puțin un context utilizabil | 130 |
| Acoperirea POS cerute de LOC, în sursele disponibile | 121 |
| Acoperire POS parțială | 9 |
| Sursă exactă, fără context utilizabil | 7 |
| Contexte utilizabile | 515 |
| Contexte nealiniate, păstrate pentru audit | 418 |
| Context cu POS nerecunoscut | 1 |

Cele 863 fără sursă admisă includ 801 absente și 62 cu altă grafie. Împreună cu cele
7 fără context utilizabil, **870/1.000 nu au context lexical utilizabil**. Absența nu
este o etichetă de raritate. Nici cele 121 cu POS acoperite nu au sensuri demonstrate
exhaustive; starea rămâne `source_bounded_not_exhaustive`.

Cele 9 cazuri cu POS incomplet: cirenaic, urat, ceruit, parcurs, cotărit, adaos, talian,
stupit, uric. Sursa furnizează sensuri nominale, dar lipsește contextul adjectival cerut
de LOC. Nu am transferat automat sensuri de la verb sau de la altă flexiune.

| Segment | Fără sursă admisă | Fără context utilizabil, cu sursă | POS parțial | POS acoperit |
|---|---:|---:|---:|---:|
| General 600 | 520 | 7 | 1 | 72 |
| Grafii/diacritice 100 | 89 | 0 | 1 | 10 |
| POS multiple 100 | 70 | 0 | 7 | 23 |
| Suport corpus 100 | 89 | 0 | 0 | 11 |
| Suport slab 100 | 95 | 0 | 0 | 5 |

Semnalele wordfreq/FineWeb2/CoRoLa/rebus au fost verificate independent prin îmbinare
cu sursele originale. Scorurile baseline și semnalele înghețate sunt neschimbate:
149 forme cu wordfreq, 851 fără. Dintre cele 851, 87 au context lexical utilizabil.
Nu este o comparație de acuratețe: lotul nou nu are etichete umane sau predicții LLM.

## Implementare și TDD

`audit_form_evidence` este o limită publică CSV: lotul înghețat + inventarul complet +
exporturile lexicale și de formă existente → audit, mapare ID-uri, contexte și manifest.
Nu introduce parser lexical, scorer, orchestrator generic sau dependență către DB.

- Reutilizează `export_local_evidence` pe 1.146 ID-uri și `prepare_exact_forms` pe
  1.000 de grafii. Contractul formei păstrează toate intrările LOC; contextele cu
  exemple obligatorii rămân goale, în loc de exemple inventate. Sensurile sunt în
  exportul lexical și `contexts.csv`.
- Respinge ID-uri pierdute/dublate, grafii/POS nepotrivite, JSON invalid, hash-uri
  schimbate, manifeste fără proveniență și revizii de extracție incompatibile.
- Părinții unui sens sunt legați prin formă, sursă/hash, heading, POS/detail,
  intrare, dicționar și variantă. Părintele lipsă/ambiguu/ciclic rămâne nerezolvat.
- Contextele nealiniate nu intră în dovezile utilizabile; toate rămân inspectabile.
- Export atomic într-un director nou; refuză suprascrierea. CLI subțire în
  `scripts/audit_form_evidence.py`.

10 teste noi, 21 subteste la interfața publică. Bucle RED/GREEN înregistrate în sesiune:
mapare completă, lipsă de sursă, identitate/POS, proveniență, parent scoping și contexte
incomplete. Cazul de review „manifest fără inputs/implementation” a fost reprodus,
acoperit prin regresie și corectat înaintea exportului final.

**Verificare pe branch-ul PR, fără modificările experimentale locale nepublicate:**
`python scripts/check.py` — Ruff PASS, **893 teste + 241 subteste PASS**.
Verificare Ruff separată pentru noul CLI: PASS. Replay cu HTTP/rețea/DB blocate:
toate cele 5 artefacte de audit, inclusiv manifestul, identice byte cu byte.
Audit independent: toate sursele existente verificate (199, inclusiv cele excluse),
8 CSV-uri finale identice cu rularea verificată, identități/LOC/semnale și 1.363 de
fișiere protejate neschimbate. Inspecție directă a surselor pentru sensuri normale,
parent–copil, leme/genuri respinse și varianta arhaică neutră `clas`.

## Artefacte și reproducere

Publicate aici doar [auditul de acoperire](2026-10-30-independent-evidence-audit/form-evidence-audit.csv),
[maparea ID-urilor](2026-10-30-independent-evidence-audit/membership.csv),
[rezumatul](2026-10-30-independent-evidence-audit/summary.json),
[auditul independent](2026-10-30-independent-evidence-audit/verification-final.json) și
[verificarea replay](2026-10-30-independent-evidence-audit/replay-verification.json).
Copiile CSV publicate folosesc LF; receipt-urile păstrează hash-urile artefactelor
originale CRLF. Valorile CSV sunt identice. Textele dicționarului, sursele brute și
semnalele CoRoLa derivate rămân locale.

În workspace-ul original:
`build/d1/independent-evidence-2026-10-30/` păstrează `prepare.py`, `run.py`, `replay.py`,
`inputs/`, `run-final/{lexical,form-contract,audit}/`, protocolul și hash-urile protejate.
Scripturile de pregătire refuză suprascrierea; exportul final păstrează sursele înghețate.
Pentru o nouă rulare completă cu aceleași intrări pregătite, din checkout-ul de cod:

```sh
.venv/bin/python ../independent-evidence-2026-10-30/run.py run-nou
```

Pentru refacerea numai a auditului, folosind noul CLI și exporturile existente:

```sh
PYTHONPATH=src python scripts/audit_form_evidence.py \
  --forms /Users/fabian/git/word-rarity-classifier/build/d1/independent-evidence-2026-10-30/inputs/forms.csv \
  --inventory /Users/fabian/git/word-rarity-classifier/build/rarity/step1_words.csv \
  --lexical-dir /Users/fabian/git/word-rarity-classifier/build/d1/independent-evidence-2026-10-30/run-final/lexical \
  --form-contract-dir /Users/fabian/git/word-rarity-classifier/build/d1/independent-evidence-2026-10-30/run-final/form-contract \
  --output-dir /Users/fabian/git/word-rarity-classifier/build/d1/independent-evidence-2026-10-30/audit-nou
```

Hash-urile surselor și ale extractorului trebuie să coincidă. Dacă implementarea sau
sursele se schimbă, refacem exporturile într-o campanie nouă; nu edităm manifestele
vechi pentru a forța reluarea.

## Recomandare și leftovers

Următorul pas: pilot Qwen/GPT independent pe cele 150 existente, înaintea inferenței
pe 1.000. Evaluarea trebuie să separe explicit condițiile cu/fără definiții. Pilotul
are mult mai puține lipsuri decât lotul nou; nu extrapolăm calitatea asupra celor
870 fără context. Un judecător poate rămâne numai detector de conflicte, după poarta
preciziei/recuperării la buget fix; nu devine scorer prin vot majoritar.

Rămân: pilotul judecătorilor, înghețarea cascadei/riscului, rularea celor 1.000,
verificarea relațiilor lexicale între familii când există martori, trierea cauzelor și
maximum 50 de fișe. Nicio fișă nouă nu este necesară utilizatorului în această etapă.
Nu am recuperat toate sensurile lipsă și nu am validat scorurile celor 1.000.
