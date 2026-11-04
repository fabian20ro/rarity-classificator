# Integrarea finală în main — 2026-11-04

PR81 a intrat în main înainte ca PR82 să intre în branch-ul lui81. Închiderea
PR82 nu a transportat automat în main schimbările82/85/86. Integrarea finală
propune branch-ul `codex/d1-evaluation-adapter` direct către main.

Bază main verificată: `36723fe`; head al stivei: `594e168`, incluzând merge86
`e26de0b`. Un worktree separat combină aceste istorii fără conflicte. Modificările
black/certifi deja intrate în main sunt păstrate. Niciun cod runtime/test/script
nu diferă față de head-ul revizuit `6a8f7bf`; completarea82 inițială a fost
inspectată separat: contract exact-form, numărare rebus, raport și adaptorD1.

## Problemă de integrare corectată

`uv lock --check` a eșuat: pyproject includea extras evaluation/frequency, dar
lockfile-ul enumera doar dev. Regenerare cu uv existent, fără upgrade global:
40pachete rezolvate; toate versiunile deja fixate în main păstrate. Wordfreq3.1.1
și PyArrow21.0.0 rămân exacte; noile dependențe respectă intervalele declarate.
Verificarea repetată `uv lock --check --offline` trece. S-au descărcat metadate
pentru rezoluție, nu corpusuri/modele; niciun pachet instalat în mediul proiectului.

## Verificare și limite

- `python scripts/check.py`: Ruff PASS,986teste+456subteste PASS,40teste DB opt-in omise.
- Rulare după combinarea cu main, în mediul Python existent, cu guard DB/network și
  fără credentiale moștenite. Nu pretindem că această rulare instalează toate
  versiunile din lock; verificarea lock și testele sunt dovezi distincte.
- CI-ul PR-ului trebuie să treacă pe head-ul final înainte de merge. Merge cu SHA
  așteptat, apoi verificarea ancestry/tree în main. Nu se șterg branch-uri/worktree-uri.
- Fără DB, LLM, reinstalare SQL sau aplicare de scoruri. CI are numai instalare
  dependențe și teste offline; merge-ul nu este o operație de deployment DB.

Lotul uman rămâne închis. Cele50.724schimbări baseline nu sunt autorizate de această
integrare. Rămâne separat contractul de promovare semantică L1/ancore/erori≥2.
Starea efectivă a merge-ului și a CI este în PR; acest raport păstrează verificările
pregătirii, nu deduce succesul din existența branch-ului.
