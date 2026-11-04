# Instalare structurală în producție — 2026-11-04

**INSTALLED_VERIFIED.** Pachetul original instalat pe `pdliedweugywbiczajxn`, după
instrucțiunea utilizatorului de continuare.17/17 prechecks repetate,16/16 postchecks
PASS pe conexiuni separate. **Zero corecții de scor aplicate; executor NOLOGIN.**

Recipisa instalării:2026-11-04T07:10:27Z / **09:10:27 Europe/Bucharest**.
Citirea de confirmare:07:11:36Z /09:11:36 local. Timpul recipisei este înaintea
verificărilor finale/COMMIT; nu reprezintă durata sau ora exactă a COMMIT-ului.

## Ce s-a instalat

Într-o singură tranzacție, ca `postgres`, prin conexiunea Supabase MCP verificată:

- Schema privată `classificator_private` și ledger-ul `human_correction_receipts`.
- Coloana `words.classificator_revision`, secvență privată, contract UUID și trigger
  ALWAYS BEFORE INSERT/UPDATE. Inițializare77.698 revizii pozitive, unice,1..77.698.
- Executor `classificator_human_executor`: NOLOGIN, BYPASSRLS, fără SUPERUSER,
  CREATEDB/CREATEROLE/REPLICATION/INHERIT. Granturi exact ca în pachet; fără parolă
  provisionată, activare login sau test de DSN dedicat.
- Recipisă privată de instalare legată de pachet, UUID și hash-urile datelor.

Instalator SHA-256 neschimbat:
`7d61f282b0fb5cfc6fa1ff747b554e6e6e5d040e87900172e714193c3d9ab7a7`.
A rulat exact `02-install.sql` din arhiva verificată; fără regenerare, relaxarea
precondițiilor, instalarea separată a componentelor sau retry al DDL-ului.
Transaction lock ACCESS EXCLUSIVE; timeout lock5s, statement120s; precondiții
repetate sub lock și verificări finale după ultima scriere înainte de COMMIT.

## Dovezi după COMMIT

| Verificare | Rezultat |
|---|---|
| Preflight repetat |17/17 PASS|
| Postflight, conexiune separată |16/16 PASS|
| Rânduri / revizii unice |77.698 /77.698|
| Toate coloanele existente, inclusiv scorurile |Hash înainte=după; confirmat și după COMMIT|
| RLS, politici, granturi existente words, hook-uri DDL |Neschimbate|
| Executor |NOLOGIN; drepturi limitate|
| Apartenență creată automat |Numai postgres ADMIN; INHERIT=false, SET=false|
| Acces privat anon/authenticated/service_role/authenticator |USAGE=false pentru toate|
| Ledger corecții |0recipise;165corecții încă neaplicate|

Hash-ul tuturor coloanelor existente, excluzând noua revizie:
`6d1052a2d85f283d277e98a68a5007cca8c22189dad804c6c7fdccfad690f8a3`.
Proiecția ID/grafie/POS/scor păstrează SHA-256:
`0d69e5c92a45c52e85afe6fd903388009d408ebda54bb97c1d9818c0672f6fc0`.
UUID instalare: `f7256150-4123-4170-88b0-41c8a5e5b387`.

[Raport agregat](2026-11-04-production-installation/report.json) ·
[Prechecks](2026-11-04-production-installation/preflight.json) ·
[Postchecks](2026-11-04-production-installation/postflight.json) ·
[Verificare artefacte](2026-11-04-production-installation/verification.json).

Security Advisor consultat după DDL: niciun finding pentru schema privată.
Raportează5 obiecte publice vizibile în GraphQL pentru anon, inclusiv words;
instalatorul a păstrat granturile existente words și nu a modificat celelalte
obiecte. Această observație nu certifică întreaga configurație API și nu a declanșat
schimbări de acces în afara pachetului.
[Explicația verificării GraphQL](https://supabase.com/docs/guides/database/database-linter?lint=0026_pg_graphql_anon_table_exposed).

## Artefacte și limite

O tranzacție de instalare reală, trei tranzacții READ ONLY: preflight, postflight,
recipisă/configurație. Niciun apel LLM. Nu s-a rulat apply165/rollback sau un update
rarity_level. Bootstrap-ul reviziilor a actualizat structural toate rândurile, cu
verificarea păstrării celorlalte coloane; nu pretindem zero modificări DB.

7.155fișiere originale protejate intacte. Nicio schimbare de runtime sau SQL.
Nu s-au repetat testele unitare/server deja trecute; această etapă validează
instalarea reală prin checks și recipisa durabilă. Arhiva originală rămâne imutabilă;
textul ei istoric „NOT executed” descrie pregătirea, nu starea curentă din acest raport.

Capturi brute, SQL exact, autorizare, recipisă completă, advisor și manifest:
`/Users/fabian/git/word-rarity-classifier/build/d1/human-production-installation-2026-11-04`.
Recipisa DB este dovada instalării; un fișier local singur nu certifică succesul.
Nu rula din nou instalatorul: absența schemei/rolului este acum intenționat falsă.
Nu folosi rollback.csv pentru dezinstalare; acesta privește numai scorurile viitoare.

## Următorul pas

Configurarea și verificarea conexiunii dedicate a executorului, cu activare
controlată numai la instrucțiune explicită. Inițial, verificări read-only ale
contractului, permisiunilor și lotului. **Aplicarea165 rămâne separată și neexecutată**;
va cere revalidarea în tranzacție a lotului și a versiunilor. Politica umană este
aprobată; nicio evaluare nouă necesară. Baseline50.724 și gate-urile automate intacte.

Postflight-ul instalării descrie starea înainte de apply; ledger-ul gol și hash-ul
întregului inventar nu rămân condiții universale după scrieri legitime. Păstrează
UUID-ul/secvența și recipisele; restore/reload sau resetarea istoricului necesită
reconciliere explicită, nu reinstalare automată.
