# Corecțiile umane aplicate și verificate — 2026-11-04

**APPLIED / VERIFIED.** Cele165 de corecții aprobate au fost aplicate în mediul
real, într-o singură tranzacție, cu recipisă durabilă. Verificarea ulterioară,
dintr-o conexiune READ ONLY separată, confirmă exact rezultatul tranzacției.
[Rezumat agregat](2026-11-04-human-application/report.json).

## Rezultat

- 77.698 rânduri:165 scoruri modificate,77.533 rânduri complet neschimbate.
- 233/233 postcondiții valide pentru200 forme umane și toate ID-urile/POS incluse.
- Toate celelalte coloane identice înainte/după, verificate prin hash peste întregul
  inventar; doar scorul și revizia de rând se schimbă pentru cele165 corecții.
- Recipisa recitită din DB coincide cu cea locală; toate versiunile post-apply corespund.
- 7.187 fișiere originale intacte. Răspunsurile/evaluările umane nu au fost editate.
- Zero apeluri LLM, DDL sau granturi noi în această etapă. Fără rollback/reaplicare.

Preflight-ul read-only a confirmat starea originală și ledger-ul gol. Auditul offline
al aprobării și provenienței a trecut. Fluxul existent a repetat verificările sub
lock, a executat CAS secvențial și a verificat întregul inventar după ultima scriere,
inclusiv după recipisă, înainte de commit. Citirea separată de după commit confirmă
persistența la21:44:36 Europe/Bucharest. Nu este o simulare sau doar un preview.

## Politica rămâne delimitată

Jaccard L1 față de referința originală și starea live:96,459%, peste pragul70%.
Ancorele legacy rămân diagnostice în politica umană deja aprobată; gate-ul automat
continuă să eșueze. Nu am relaxat gate-uri, recalibrat praguri sau aplicat cele50.724
de schimbări baseline. Rezultatul certifică acest lot uman; nu certifică precizia
clasificatorului pe întregul inventar ori discriminarea4/5.

## Reproducere și recuperare

Execuție prin CLI-ul existent `classificator.human_correction_flow`, cu `apply`,
confirmarea exactă a pachetului, aprobarea/politica fixate și conexiunea dedicată.
Comenzile, CSV-urile before/candidate/after/final, auditul și recipisa completă rămân
în arhiva locală a operației, împreună cu hash-urile. Credentialele și configurația
conexiunii nu sunt publicate. Nu s-a schimbat runtime-ul; testele deja trecute nu
au fost repetate fără modificări. Validarea acestei etape este execuția reală plus
citirea independentă a întregului rezultat.

Pachetul original, rollback.csv și recipisa rămân imutabile. Un rollback ulterior
necesită verificarea reviziilor post-apply și instrucțiune separată. Verificatorul
istoric de dinaintea aplicării cere ledger gol/scorurile vechi și acum trebuie să
refuze; nu îl relaxăm pentru a afișa PASS. Nu reinstala și nu regenera aprobarea.

**Următorul pas:** review și merge coordonat pentru PR-urile suprapuse85/86.
Lotul uman este închis; nicio altă operație DB necesară pentru aceste corecții.
Pentru inventarul automat rămâne o decizie separată privind validarea semantică
L1/ancorelor și erorile≥2, folosind evaluările existente; fără promovarea baseline-ului
pe baza acestui succes și fără alte evaluări cerute utilizatorului.
