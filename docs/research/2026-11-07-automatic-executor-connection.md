# Executor automat activat și conexiune verificată — 2026-11-07

**VERIFIED.** Utilizatorul a autorizat activarea executorului și verificarea
conexiunii dedicate, fără aplicarea scorurilor. Loginul și parola independentă au
fost configurate; autentificarea reală și citirile au trecut. **Zero scoruri aplicate,
zero apeluri LLM.** Ledgerul automat rămâne gol.

Înainte de activare,39/39postchecks ale instalării treceau. Activarea a schimbat doar
LOGIN/parola rolului automat, într-o tranzacție cu verificarea stării NOLOGIN și a
recipisei instalării. Fără granturi noi sau schimbarea executorului uman. Parola
aleatoare a fost generată local; serverului i s-a trimis verifierul SCRAM produs de
libpq. Parola nu apare în argv,rapoarte,Git sau output. SQL-ul temporar cu verifierul
a fost eliminat după confirmarea conexiunii.

Conexiune prin session pooler și TLS `verify-full`, cu CA-ul oficial deja verificat.
Configurație libpq service/passfile dedicată, în director0700,fișiere0600,exclus din Git.
Fișierele executorului uman verificate prin hash:nicio modificare. Nicio dependență
nouă și nicio modificare a trust store-ului global.

## Verificarea conexiunii

Autentificare confirmată la **2026-11-07 01:19:21 Europe/Bucharest**. Verificatorul
folosește explicit `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY` și confirmă
`transaction_read_only=on`; nu se bazează pe startup options ale poolerului.
Nu instanțiază tranzacția apply/rollback și nu solicită lock-uri de scriere.

| Verificare | Rezultat |
|---|---|
| current_user/session_user |Identitatea executorului automat|
| TLS |Activ,verify-full|
| Rol activ |LOGIN/BYPASSRLS;fără SUPERUSER/INHERIT/CREATE/REPLICATION|
| Privilegii efective/memberships |9/9checks PASS;fără ledger uman/secvență/scriere contract|
| Contract revizii/epoch |Identic celui instalat|
| Inventar77.698rânduri |ID/grafie/POS/scor/revizie identice snapshotului aprobat|
| Toate coloanele words |Digest identic recipisei instalării|
| Evaluări protejate |233/233rânduri intacte|
| Ledger automat |0recipise|

Verificare administrativă independentă după activare:38/39postchecks istorice PASS.
Singurul check fals este `executor_disabled`, intenționat: cere NOLOGIN. Atributele
rolului activ sunt verificate separat. Nu modificăm instalatorul sau recipisa istorică
pentru a ascunde această tranziție; toate condițiile de date/granturi umane rămân PASS.

Prima încercare libpq a refuzat local fișierul service înainte de conectare:
ConfigParser scria spații în jurul `=`. Corectat cu `space_around_delimiters=False`;
a doua încercare a autentificat și a verificat complet conexiunea. Fără afișarea
parolei sau schimbarea TLS. Configurația finală folosește sintaxa `key=value`.

Dry-run separat, cu accesul DB/rețea blocat: replay complet al CSV-urilor acceptate,
50.724schimbări planificate (7.537wordfreq/43.187fallback),`applied=false`. Gate-urile
Jaccard/ancore rămân FAIL vizibil, diagnostice în politica provizorie deja acceptată.
Conexiunea funcțională nu certifică precizia scorurilor și nu autorizează aplicarea.

[Raport agregat](2026-11-07-automatic-executor-connection/report.json).

## Reutilizare și pas următor

Credențiale locale:`build/d1/private-automatic-executor/connection.env`.
Definește `PGSERVICEFILE` și `AUTOMATIC_PROMOTION_DSN=service=automatic_promotion`;
parola este citită de libpq din passfile. Configurația este write-capable conform
granturilor aprobate; READ ONLY este impus explicit de verificator,nu permanent de DSN.

Runbook local,scriptul de verificare și capturile:
`build/d1/automatic-executor-connection-2026-11-07/`.
`verify_read_only.py --output <director-nou>` repetă citirile și exportă snapshotul
CSV. Este checkpoint înainte de aplicare; va refuza legitim driftul după schimbări
ulterioare. Capturile/credențialele nu sunt publicate;PR-ul conține doar agregate.

Fără schimbări de runtime;nu am repetat suita fără modificări de cod. Verificarea
relevantă aici este autentificarea reală,cele9checks de privilegii,toate rândurile și
postflight-ul administrativ;dry-run-ul a rulat separat offline.

**Următorul pas:** aplicarea separat autorizată a pachetului înghețat,cu revalidare
sub lock,confirmare exactă pachet/epoch,postcheck și recipisă atomică pentru rollback.
Nu mai există configurări restante pe baza acestei verificări. Nu sunt necesare
alte evaluări umane sau apeluri LLM. Până la instrucțiunea de apply,scorurile rămân
cele existente.
