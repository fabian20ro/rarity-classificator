# Pachet automat de instalare și repetiție — 2026-11-07

**Pachet pregătit și verificat; neinstalat în DB-ul real.** Generator offline,
ledger automat separat, recipisă de instalare și executor NOLOGIN. Refolosește
schema/reviziile existente; păstrează scorurile, epoch-ul, recipisele și granturile
fluxului uman. Politica automată acceptată și candidatul sunt neschimbate.

## Contract și verificare

- CSV-uri/acceptare/captură fixate prin hash → preflight, instalare atomică,
  postflight, instrucțiuni și manifest. Default fără conexiuni; CLI fără DSN/execute.
- **28 verificări înainte,39 după.** Condițiile sunt repetate sub lock; postcondițiile
  se execută după ultima scriere. Recipisa identifică instalarea și pachetul acceptat.
- Inventar și toate coloanele păstrate; recitire revizii/epoch, RLS, politici,
  triggere, granturi/memberships și recipise umane. Rolul rămâne NOLOGIN/BYPASSRLS,
  fără privilegii de creare, secvență, scriere contract sau acces la ledgerul uman.
- Runtime-ul uman reutilizează același SQL de validare a reviziilor, mutat într-o
  constantă comună. Comparație AST: expresia SQL identică versiunii anterioare.
- Nicio schimbare Step5, gate-uri, scoruri automate sau etichete umane.

**TDD:** RED→GREEN pentru preparare offline, drift/incompatibilități, instrucțiuni
și integritate; teste reale pentru instalare, secvență și concurență. **1.008teste
+479subteste PASS**, Ruff PASS;78integrări omise implicit. **20/20 probe separate
OrioleDB17.9/1.8 PASS**, fără skip. Docker cu imagine fixată,512MiB,loopback,
fără DSN extern acceptat; containerul și volumul eliminate.

Repetiția pachetului exact a reconstruit pe serverul propriu snapshotul aprobat,
reviziile, epoch-ul și recipisele umane, cu cele9definiții de hook-uri DDL capturate.
Toate77.698rândurile păstrate la instalare. După activare **doar în fixture**, noul
executor a aplicat50.724schimbări, a recunoscut retry-ul și a restaurat exact scorurile
și coloanele fără revizii la rollback. Cele233rânduri umane protejate și recipisa
umană intacte. Reviziile rândurilor automat modificate avansează legitim la rollback.

Eșecuri acoperite: DDL respins, modificări auxiliare/recipisă umană/granturi din hook,
conexiune terminată, reset de secvență, lock timeout pe words și recipisa umană,
confirmare de commit pierdută, reexecutare, drift de revizii/trigger/rol/ACL.
Resetul secvenței este detectat; testul repară explicit doar fixture-ul. SQL rollback
nu restaurează secvențele sau efectele externe ale hook-urilor.

Surpriză în fixture-ul istoric: ramura pentru pachetul uman imutabil încerca întâi
să regenereze alt pachet, apoi îl ignora. Eliminată doar acea regenerare inutilă;
repetiția execută originalul verificat. Nicio schimbare în instalatorul uman.

## Artefacte și reproducere

Pachet local: `build/d1/automatic-installation-2026-11-07/verified/`.
Manifest SHA-256: `5c12270627b079aa7edfd8a392a315646401d4ec99287d54431b809d0dc8488b`.
Installer SHA-256: `bb6557c6d38132a429f080d66182c9d8507158552868dbd82721c7520f3d17cd`.
**24artefacte reproduse identic**, inclusiv manifest.9surse/pini verificate înainte/după
repetiție. Capturi și recipise individuale rămân local; PR-ul conține agregate.

Din checkout, cu mediul Python al proiectului și `PYTHONPATH=src`:

```sh
python -m classificator.automatic_installation \
  --acceptance docs/research/2026-11-06-automatic-flow/acceptance.json \
  --package ../automatic-promotion-audit-2026-11-06/final \
  --capture ../automatic-installation-2026-11-07/capture.json \
  --output ../automatic-installation-2026-11-07/new-bundle
python scripts/check_automatic_installation.py \
  --output ../automatic-installation-2026-11-07/new-rehearsal --full-inventory
```

Directorul de ieșire trebuie să fie nou. Proba completă folosește intenționat
`verified/`, pachetul imutabil verificat, plus sursele locale fixate; generarea în
alt director nu schimbă ținta repetiției. Fără `--full-inventory`, probele mici
funcționează fără capturile locale. Imaginea Docker trebuie să existe local;
runnerul folosește pull=never. Rulează cu mediu curat PATH/HOME/TMPDIR, fără
credențiale de aplicație. Scriptul construiește intern mediul copiilor.

[Pregătire](2026-11-07-automatic-installation/preparation.json) ·
[Repetiție](2026-11-07-automatic-installation/rehearsal.json) ·
[Reproducere](2026-11-07-automatic-installation/verification.json) ·
[Decizie arhitecturală](../adr/2026-11-07-automatic-installation.md).

## Acces real și limite

O singură captură suplimentară prin Supabase MCP, explicit READ ONLY/ROLLBACK,
cu timeout30s/2s. Necesită formatul complet de granturi/recipise al instalatorului;
confirmă snapshotul aprobat. Niciun DDL/DML sau nextval real. Zero cereri LLM,
încărcări de modele sau evaluări noi. Toate instalările/apply/rollback din această
iterație au fost pe servere izolate, create și eliminate de harness.

Repetiția validează SQL-ul și recuperarea, nu instalarea în serviciul găzduit sau
precizia scorurilor. Fereastra de lock, endpoint-ul și neexpunerea schemei private
prin API se verifică la instalare. Capturile nu rezervă starea viitoare. Preflight-ul
refuză orice drift; nu slăbim condițiile pentru a aplica un pachet învechit.

**Pas următor:** instalarea structurală reală, separat autorizată, cu pre/postchecks
și executor lăsat NOLOGIN. Apoi activarea/conexiunea dedicată verificată și aplicarea
separat autorizată a celor50.724schimbări. Politica nu necesită reaprobare, iar
utilizatorul nu mai are evaluări de făcut. Până atunci, niciun scor automat nou în DB.
