# Repetiția pachetului complet pe OrioleDB — 2026-11-04

**12/12 teste reale PASS.** Arhiva originală din2026-11-03 executată nemodificat,
numai pe serverul izolat, cu cele9 hook-uri DDL capturate și inventarul77.698.
Preflight17/17 și postflight16/16 PASS; restart și recuperare verificate.
Niciun acces la DB-ul real, nicio schimbare a evaluărilor, niciun apel LLM.

## Ce a rulat

`scripts/check_postgres.py --installation-bundle` reutilizează harness-ul existent:
imagine Supabase PostgreSQL17.9/OrioleDB1.8 fixată prin digest, container/volum proprii,
port numai127.0.0.1,512MiB RAM/1CPU. Imaginea exista local; fără download/instalări de
dependențe. Harness-ul nu acceptă DSN de aplicație. Containerul și volumul eliminate;
imaginea cache păstrată. Inventarele Docker etichetate: goale la final.

Două tipuri de probe:

- Fixture mic, regenerat prin aceeași interfață publică CSV/captură→pachet, cu hook
  reprezentativ pentru RLS/contor DDL și injectarea erorilor. Verifică eșecuri fără
  a modifica arhiva fixată sau datele utilizatorului.
- Inventar complet: pachet generat pentru fixture și fluxul executorului; separat,
  **SQL-ul original din `human-installation-2026-11-03/verified`**, fără patch-uri,
  cu politica, ACL-urile și definițiile/ownerii/tagurile celor9 event triggers
  reproduse din captura locală. Toate verificările originale trec.

SQL original SHA-256:
`7d61f282b0fb5cfc6fa1ff747b554e6e6e5d040e87900172e714193c3d9ab7a7`.
Arhiva/manifestul și cele6.175 fișiere protejate au rămas intacte. Nu s-a regenerat
arhiva pentru a înlocui precondițiile care ar fi eșuat.

Instalatorul rulează ca `postgres`, **NOSUPERUSER CREATEROLE BYPASSRLS**. Rolul executor
este creat NOLOGIN și rămâne astfel la postflight. Pentru testarea apply/rollback,
numai într-o bază separată de test, administratorul activează loginul cu o parolă
exclusiv locală; executorul folosește granturile generate, fără suplimente.

## Cazuri verificate

| Caz | Rezultat |
|---|---|
| Instalare non-superuser, pre/postchecks, restart |PASS; reinstalarea refuzată|
| Excepție DDL înaintea recipisei |Rollback complet; retry reușit|
| Hook DDL modifică o coloană fără scor |Detectat; datele și schema restaurate atomic|
| Terminarea backend-ului înainte de COMMIT |Nicio instalare parțială; retry reușit|
| Inventar schimbat înainte de instalare |Refuz înainte de crearea schemei/rolului|
| Lock conflict, timeout5s |Anulare; instalare reușită după eliberare|
| ACK pierdut după COMMIT real |Recipisă/postchecks identifică succesul; fără reinstalare|
| Instalare completă +apply165 +retry +rollback |165schimbate;77.533păstrate; rollback exact|
| Arhiva originală +9hook-uri +77.698rânduri |17/17 înainte,16/16 după; persistă după restart|
| Acces privat acordat ulterior rolului anon |Postflight refuză|
| Trigger de revizie dezactivat ulterior |Postflight refuză|
| Coloană fără scor modificată ulterior |Postflight refuză, deși scorurile coincid|

[Raport server](2026-11-04-installation-rehearsal/report.json),
[prechecks originale](2026-11-04-installation-rehearsal/original-bundle-prechecks.json),
[postchecks originale](2026-11-04-installation-rehearsal/original-bundle-postchecks.json),
[verificare și durate](2026-11-04-installation-rehearsal/verification.json).
Suita server:24,23s total; proba originală4,01s include fixture/setup/restart/cleanup,
nu este un benchmark al timpului de lock în producție.

## TDD și corecții

Au fost folosite interfețele deja aprobate: pachetul și SQL-ul public de instalare/
verificare, apoi fluxul tranzacțional al corecțiilor. Instalatorul existent a trecut
probele; **nicio corecție de runtime sau modificare de SQL nu a fost necesară**.
Testele negative sunt acum regresii reproductibile, fără a inventa un defect.

Prima încercare a fixture-ului cu hook-uri reale a eșuat: PostgreSQL cere SUPERUSER
pentru atribuirea ownerului unui event trigger, deși captura reală îl arată pe
postgres fără acest privilegiu. Fixture-ul reproduce istoricul: privilegii temporare
la setup, apoi NOSUPERUSER înaintea instalării. Nu s-a relaxat instalatorul și nu
s-a schimbat rolul real. Acesta a fost un defect al setup-ului de test, nu al pachetului.

Ruff și suita offline: **986 teste +456 subteste PASS**,40 integrări skip implicit
(28 existente +12 noi). Cele12 noi au rulat separat toate. Fluxul runtime, scorurile,
politica și gate-urile Step4/Step5 neschimbate. Hash-urile implementării și artefactelor
rundei complete reverificate; proiecția rollback identică snapshotului inițial.

## Reproducere

Din checkout, cu mediul Python existent și imaginea deja disponibilă:

```sh
PYTHONPATH=src python scripts/check_postgres.py \
  --engine orioledb --installation-bundle --full-inventory \
  --output <director-nou>
python scripts/check.py
```

Fără `--full-inventory`, cele2 probe ce cer artefacte locale sunt omise, rămân10
cazuri fixture. `--installation-bundle --engine heap` este refuzat. Fără opt-in,
suita normală nu pornește serverul. Nu folosi DSN-ul producției în aceste teste.

Artefacte locale complete, inclusiv JUnit, capturi fixture, CSV-uri, recipise și
manifest: `/Users/fabian/git/word-rarity-classifier/build/d1/installation-rehearsal-2026-11-04-verified`.
Recipisele aparțin bazelor eliminate; nu autorizează rollback în producție.

## Limite și următorul pas

Fixture-ul are proiecția reală ID/grafie/POS/scor și o coloană suplimentară sintetică
pentru verificarea datelor fără scor. Nu este backup-ul tuturor coloanelor/indexurilor
sau întregii infrastructuri găzduite. Cele9 funcții de hook au fost reproduse;
extensiile externe și serviciile lor complete nu sunt clonate. NOTIFY-urile sunt
locale. Pierderea ACK-ului este simulată după COMMIT real; deconectarea backend-ului
și restartul sunt reale. Fără teste de cădere fizică a discului sau mașinii.

**Următorul pas:** preflight read-only actualizat pe conexiunea efectivă și alegerea
ferestrei de lock; apoi instalarea structurală numai la instrucțiune explicită,
cu verificările originale înainte/după. Instalația lasă executorul NOLOGIN și nu
aplică scoruri. Activarea executorului și apply165 rămân separat autorizate, cu
revalidare tranzacțională. Politica este deja aprobată; nu sunt necesare noi evaluări.
Orice drift real cere oprire și revizuire, nu slăbirea verificărilor. Baseline-ul cu
50.724modificări rămâne exclus.
