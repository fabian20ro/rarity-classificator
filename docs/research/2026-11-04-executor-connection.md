# Conexiunea dedicată configurată și verificată — 2026-11-04

**VERIFIED.** Autentificarea executorului dedicat funcționează; verificările sale
au rulat într-o tranzacție READ ONLY explicită. Contractul de revizii și toate
precondițiile umane corespund. Scorurile au rămas neschimbate;165corecții neaplicate.
[Rezumat agregat](2026-11-04-executor-connection/report.json).

Au fost configurate parola dedicată și loginul, fără granturi noi sau schimbarea
credentialelor administrative existente. Secret aleator generat local; verifier
SCRAM produs de libpq. Parola nu a fost afișată, inclusă în argumentele procesului,
rapoarte sau Git. Fișiere locale0600 într-un director0700, exclus din Git.

Conexiunea folosește session pooling și TLS `verify-full`, cu CA-ul din sursa
oficială. Nu s-au dezactivat verificarea hostname-ului, TLS sau setările serverului.
Nu a fost schimbat trust store-ul global. Configurația folosește mecanisme libpq
standard: fișier service și passfile, fără o nouă implementare de management parole.
[Documentație conexiuni](https://supabase.com/docs/guides/database/connecting-to-postgres) ·
[Verificarea TLS](https://supabase.com/docs/guides/platform/ssl-enforcement).

Endpointul direct nu s-a rezolvat local; s-a folosit endpointul session pooler din
configurația existentă, cu identitatea proiectului verificată. Trust store-ul public
nu accepta CA-ul serviciului; certificatul a fost identificat în codul oficial și
validat prin conexiunea reală. Nicio dependență nouă instalată.

**Observație verificată:** opțiunea read-only trimisă la conectare nu a fost aplicată
de pooler. Verificarea folosește `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY`
și verifică `transaction_read_only=on`. Un DSN/config de conectare nu trebuie
confundat cu o barieră permanentă read-only; executorul păstrează granturile aprobate.

Rezultate: identitatea sesiunii dedicată, TLS verificat, contract identic, vizibilitate
completă a inventarului,233/233precondiții și ledger gol. Cele165corecții rămân
necesare,68rânduri revizuite deja corecte. Hash-ul proiecției coincide cu originalul.
Validarea contractului reutilizează logica existentă, fără tranzacția de apply și
fără lock-uri de scriere.7.172fișiere originale protejate intacte; zero apeluri LLM.
Nu s-au repetat testele runtime fără schimbări de cod; conexiunea reală a fost
verificată înainte și după configurare.

Check-ul istoric de instalare care cere NOLOGIN devine intenționat fals după
activare; celelalte15checks de instalare trec. Atributele rolului activ au fost
verificate separat. Pachetul SQL rămâne imutabil, nu se relaxează pentru noua etapă.

Pentru reutilizare se încarcă fișierul local `connection.env`: definește
`PGSERVICEFILE` și `HUMAN_CORRECTIONS_DSN`, fără parola în variabilele afișate.
Runbook-ul local al operației include calea exactă și comanda de verificare
read-only cu director nou de output. Detaliile conexiunii și credentialele nu
sunt publicate în PR.

**Următorul pas:** aplicarea separată a celor165de corecții, numai la instrucțiune
explicită, prin fluxul aprobat: revalidare sub lock, compare-and-set, verificarea
întregului rezultat și recipisă în aceeași tranzacție. Conexiunea este pregătită;
nu mai sunt necesare configurări sau evaluări umane pe baza constatărilor curente.
Baseline50.724 și gate-urile automate rămân în afara acestui lot.
