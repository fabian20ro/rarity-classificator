# Flux separat pentru corecții umane — 2026-11-03

Actualizare ulterioară: [integrarea PostgreSQL izolată a trecut](2026-11-03-postgres-integration.md).
Rezultatele de mai jos descriu etapa inițială offline. Nu s-a aplicat lotul în DB-ul proiectului.

**Implementat conform politicii aprobate; niciun scor aplicat în DB.**
`human-corrections-flow-v1` păstrează Jaccard obligatoriu, cu ancore raportate fără
blocare exclusiv pentru pachetul uman verificat. Step4 automat rămâne neschimbat;
auditul vechi continuă să declare că nu autorizează uploadul de unul singur.

## Interfață și protecții

`run_human_corrections(approval_path, policy_path, output_dir, action=...)`, respectiv
CLI separat `python -m classificator.human_correction_flow`. Acțiunea implicită:
`dry-run`, complet offline, fără citirea credentialelor sau deschiderea conexiunii.

Înregistrarea aprobării fixează hashul politicii și package_id, deci exact setul
și valorile aprobate. `apply` și `rollback` cer separat confirmarea package_id și
un DSN explicit; nu moștenesc automat configurația de DB a Step4. Aprobarea politicii
nu este o instrucțiune de a aplica datele în această sesiune.

Fluxul de execuție implementat, testat numai prin substituirea transportului:

1. Verifică aprobarea și reexecută auditul original, inclusiv proveniența umană.
2. Într-o singură tranzacție, blochează scrierile în words/ledger înainte de snapshot.
3. Reverifică toate233 precondițiile și membrii/POS ai celor200 forme evaluate.
4. Proiectează exclusiv165 corecții pe starea curentă. Jaccard≥0,70 față de starea
   curentă **și** referința originală; seed-ul rămâne diagnostic.
5. Compare-and-set secvențial cu scor și versiune de rând; număr/ID-uri exacte.
6. Verifică întregul post-state, apoi salvează recipisa în aceeași tranzacție.
7. Publică confirmarea locală numai după commit confirmat.

La commit incert: `attempt.json` rămâne unconfirmed. Reluarea cu același pachet,
într-un director nou, verifică ledger-ul și recuperează rezultatul fără reaplicare.
Un rezultat `already_applied` descrie operația istorică, nu validează starea actuală.

Rollback-ul cere recipisa DB, valorile/ID-urile originale și postcondițiile complete.
Versiunile rândurilor detectează editări A→B→A; intervalele de tranzacții ambigue sunt
refuzate. Restaurează doar ID-urile aplicate și păstrează editările fără legătură.
Rollback-ul este atomic și recuperabil; nu autorizează reaplicarea aceluiași pachet.
[Decizia arhitecturală și limitele](../adr/2026-11-03-human-correction-flow.md).

## Rezultate offline pe lotul existent

| Verificare | Rezultat |
|---|---:|
| Corecții / precondiții / referințe |165 /233 /200|
| Rânduri neatinse în simulare |77.533|
| Aplicare simulată vs candidat fixat |identică|
| Reluare simulată |fără reaplicare|
| Rollback simulat |toate valorile originale restaurate|
| Jaccard L1 |96,459%, PASS|
| Apartenență seed / recall |4,770% /42,969%, diagnostic|
| Fișiere protejate intacte |4.791|
| Fișiere preview identice la replay |14|

**TDD:13 teste noi +27 subcazuri. Ruff +976 teste și449 subteste PASS.**
Regresii pentru aprobări nepotrivite, guards pe rânduri neschimbate, POS/ID nou sau
lipsă, drift L1, eșec la update/recipisă/commit, efecte secundare, input schimbat în
tranzacție, commit incert, rollback fără dovadă, ABA, tranzacții prea vechi,
parametrizare SQL și dry-run fără rețea. Testele existente ale Step4 continuă să treacă.

**Nicio conexiune PostgreSQL deschisă; zero citiri/scrieri DB, DDL sau apeluri LLM.**
Runner-ul blochează procesele, rețeaua și psycopg.connect. Directorul `simulated-*`
folosește un store în memorie cu versiuni sintetice. Recipisele sale sunt marcate
prin `TEST-ONLY.txt`; nu sunt dovezi de aplicare reală. Nu am validat pe server
blocările, SQL-ul de schemă, rolurile, triggerele sau comportamentul xmin/commit.

## Utilizare reproductibilă

Preview real, fără conectare, din checkoutul PR:

```sh
PYTHONPATH=src python -m classificator.human_correction_flow \
  --approval docs/research/2026-11-03-human-flow/approval.json \
  --policy docs/research/2026-11-03-human-acceptance/policy.json \
  --output /Users/fabian/git/word-rarity-classifier/build/d1/human-flow-preview-new
```

Verificare complet offline cu replay și tranzacții simulate, fără DB:

```sh
PYTHONPATH=src:. python docs/research/2026-11-03-human-flow/run.py \
  --output /Users/fabian/git/word-rarity-classifier/build/d1/human-flow-replay-new
```

Folosiți un director nou; nu se suprascriu artefacte. Sursele originale locale sunt
necesare pentru replay; politica/aprobarea nu sunt semnături criptografice.
Artefacte păstrate în `build/d1/human-flow-2026-11-03/`.

## Ce mai rămâne

**Decizia de politică este aprobată și implementată; nu mai cerem aceeași aprobare.**
Următorul pas recomandat: testarea adaptorului într-un PostgreSQL izolat, cu două
conexiuni concurente, schema reală și cazuri de întrerupere/recuperare. Aceasta nu a
fost rulată acum, conform limitei fără DB.

Înaintea unei aplicări reale: autorizare pentru instalarea ledger-ului privat și
execuție; verificarea rolului/triggerelor, apoi revalidarea stării live în tranzacție.
[SQL-ul pregătit](../sql/2026-11-03-human-correction-receipts.sql) nu este instalat și
CLI-ul nu îl rulează automat. Schema/politica DB existentă nu a fost schimbată.

Cele50.724 de schimbări baseline provizorii rămân în afara fluxului; nu există o
nouă estimare a preciziei globale sau validare automată4/5. Nu cerem evaluări noi.

[Aprobare fixată](2026-11-03-human-flow/approval.json) ·
[Raport](2026-11-03-human-flow/report.json) ·
[Plan](../plans/2026-10-30-1000-form-risk-review.md).
