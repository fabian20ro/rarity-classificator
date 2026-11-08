# Temperatura relativă a distribuțiilor D1 — experiment offline

2026-11-08. Protocol fixat înaintea rulării pe referințele reale.

## Contract

Interfața CSV deja convenită: aceleași features/references înghețate din v3 →
predicții complete, distribuții transformate, fit ledger, raport și manifest.
Control A, d1-omni-2b existent; fără LLM, etichete noi sau DB.

- q = softmax(beta * log(max(p, 1e-12))); beta = 1/T.
- Un singur parametru; beta ∈ [0.05,20], deci T ∈ [0.05,20]. Limite numerice
  fixe, nu hiperparametri aleși după rezultate. Flat objective → beta=1.
- Minimizare NLL medie prin derivata monotonă, 80 pași de bisecție sau capăt.
  Fără ponderare de clase, optimizare ordinală sau praguri ajustate ulterior.
- Decoder lower median, identic v3. Flooring poate crea egalități sub epsilon;
  raportăm numărul de valori afectate și NLL nativ cu același floor.
- 150: aceleași cinci folduri pe grupuri; fit doar outer-train. 50: fit pe150,
  fără etichetele50. Raport50 descriptiv: lot deja explorat, selectat pentru risc,
  fără nivel1; nu estimăm performanța întregului inventar din el.
- Recalculăm comparatorii prin interfața publică v3; baseline își reface pragurile
  în outer-train. Temperatura nu primește predicțiile sau etichetele holdout.
- Comparații: baseline, D1 nativ, v3 afin, temperatură. NLL/Brier pe holdout;
  erori ≥2, exces peste toleranța1, MAE, true1/4/5, lipsa frecvenței,
  erori evitate/introduse și lista cazurilor severe.
- Gate: fără regresie severe/exces în ambele loturi, global și true1/4/5,
  plus câștig strict global într-un lot față de baseline. Subset gol → necunoscut.
  Nicio promovare automată chiar dacă trece.

## Pași

1. TDD la interfața CSV: temperatură cu soluție analitică; izolare fold/50;
   uniforme/zero/extreme; integritate/refuz input invalid și suprascriere.
2. CLI offline reutilizabil, protocol și hash-uri input/source în artefacte.
3. Rulare200 forme; verificare solver independent și replay, surse intacte.
4. Analiză separată150/50 și1/4/5; actualizare rezultate/recomandare.

Protocolul de mai sus a fost fixat înaintea rulării. Rezultatele de mai jos au fost adăugate ulterior.

## Execuție și rezultate

- [x]12 teste CSV, inclusiv soluție analitică, izolarea fold/50, cazuri numerice,
  integritate și output atomic. CLI offline reutilizabil.
- [x] Rulare200 forme;1059passed,78skipped,479subtests; Ruff PASS.
- [x]6 fituri confirmate SciPy,6 verificări reale de izolare a etichetelor,
  replay identic, comparatoare v3 identice,210 surse originale intacte.
- [x] [Analiză și artefacte](../research/2026-11-08-d1-temperature.md).

T full150=0.396120; OOF150 T=0.365..0.445. Toate optimele interioare.
Erori≥2:baseline11/13, D1 nativ43/7, v3 afin34/5, temperatură32/7 (150/50).
Exces temperatură41/9 vs v3 afin39/6. NLL150 scade1.464→1.402,
NLL50 crește1.609→1.703. Pe150 true1:22→8 severe, true4:2→8, true5:18→13
față de D1 nativ. Pe50 true5:6→2, dar `otel` devine eroare de4.
Față de baseline, temperatura evită5/9 și introduce26/3 erori severe.
**Gate FAIL; fără promovare.**

## Rămâne / recomandare

1. Păstrăm baseline și scorurile umane; nicio extindere pe1.000/inventar/DB.
2. Publicat în [PR #91](https://github.com/fabian20ro/rarity-classificator/pull/91),
   continuarea PR90 deja merged. Review și merge pentru infrastructură/rezultate;
   fără promovarea scorurilor.
3. Dacă vrem următorul experiment Omni: bias pe clase, puternic regularizat,
   selecție exclusiv în CV internă pe150;50 rămâne challenge descriptiv.
   Scop: verificăm dacă ordinea claselor poate fi corectată, nu mai reglăm
   scalarul T pe lotul50. Necesită protocol separat; neimplementat aici.
4. D1 simplu amânat. Nicio evaluare nouă cerută; fără LLM sau DB.

## Continuare: corecțiile pe clase

2026-11-08: [experimentul regularizat pe clase](2026-11-08-d1-class-bias.md)
implementat cu nested CV150. Rezultat41/150 și7/50 erori severe, gate FAIL;
regularizarea preferă corecții foarte mici sau identitatea. Recomandarea de
experiment din această pagină este acum executată; rezultatul nu susține promovarea.
