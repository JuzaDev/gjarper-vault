---
tipo: nota
zona: pubblica
tag: [rnd]
aggiornata: 2026-09-30
stato: FileBrowser e Immich operativi, documenti ora scrivibili anche
  dall'interfaccia; restano backup off-machine, secondo utente iPhone e bulk
  fotografico
---

# gjarper — servizi self-hosted

Hardware e capacità della macchina: `00_inbox/gjarper-hardware.md`.

## Principio di accesso

**Niente esposizione pubblica**: nessuna porta inoltrata sul router, nessun
dominio, nessun certificato pubblico. Si entra da LAN o da Tailscale.

Il punto chiave, che risolve il dubbio "LAN veloce a casa vs Tailscale fuori":
**Tailscale apre connessioni dirette fra peer sulla stessa rete locale**. Il
traffico resta sulla LAN, non esce su internet e non passa da un relay. L'unico
sovrapprezzo è la cifratura WireGuard, irrilevante su un Ryzen 7 7735HS. Quindi
un solo indirizzo va bene ovunque: a casa è già alla velocità della LAN.

Verifica: da un peer connesso, `tailscale status` deve mostrare
`direct 192.168.x.x:41641`. Se mostra `relay "..."` il traffico rimbalza su un
server Tailscale (di solito: isolamento client sull'access point, o UDP bloccato).

### Stato del tailnet

- `gjarper` → **100.76.226.98**, MagicDNS **`gjarper.tail6cb7a3.ts.net`**
- `pixel-10a` → 100.127.227.22 (riattivato il 2026-09-28)
- **I PC non sono nel tailnet**: sui PC i nomi `.gjarper` risolvono via
  `/etc/hosts` (su Windows `C:\Windows\System32\drivers\etc\hosts`)

### Tabella degli URL

| Servizio | URL | Dove funziona |
|---|---|---|
| Documenti | `http://documenti.gjarper` | PC con la voce in `/etc/hosts` |
| Documenti | `http://gjarper.tail6cb7a3.ts.net` | qualsiasi device Tailscale, telefoni compresi |
| Foto | `http://<ip-lan>:2283` | LAN |
| Foto | `http://gjarper.tail6cb7a3.ts.net:2283` | qualsiasi device Tailscale |
| Foto | `http://foto.gjarper` | PC, **solo se** si aggiunge il blocco Caddy + hosts |

⚠️ Caddy fa match sull'**header Host**, quindi puntare il browser all'IP tailnet
nudo (`http://100.76.226.98`) **non** funziona: nessun blocco corrisponde. Dai
telefoni si usa il nome MagicDNS, non l'IP.

## Reverse proxy — Caddy

- Progetto: `~/infra`, container `infra-caddy-1`, immagine `caddy:2`
- **`network_mode: host`** → ascolta direttamente su `*:80` e `*:443` e raggiunge
  gli altri container su `127.0.0.1:<porta>`
- Config: `~/infra/caddy/Caddyfile` → montato su `/etc/caddy/Caddyfile`
- Convenzione: un blocco per servizio, prefisso `http://` = niente auto-HTTPS
- Ricarica senza riavvio:
  `docker exec infra-caddy-1 caddy reload --config /etc/caddy/Caddyfile`
- Porte occupate: 3089 (anime-monitor), 5199/8099 (yt-analizer), 8000
  (transcribe-web), 8081 (filebrowser), 2283 (immich)
- Residui da ripulire: blocchi `sync.gjarper` (8384) e `vault.gjarper` (3300),
  che puntano a servizi non attivi

## Documenti — FileBrowser Quantum

**Perché questo e non FileBrowser**: il progetto originale è stato **archiviato
il 2026-08-31** (niente più release né patch di sicurezza). Il fork mantenuto è
FileBrowser Quantum (gtsteffaniak, Apache 2.0), che aggiunge OIDC, permessi per
utente/gruppo e thumbnail di video e PDF.

⚠️ **Il WebDAV no.** Verificato il 2026-09-30 sulla `2.0.9-beta`: nessuna voce
nell'interfaccia, nessuna chiave `disableWebDAV` nella configurazione effettiva
(*System & Admin → View configuration*), e nello swagger solo rotte `/api/*`.
Ogni `PROPFIND` risponde 404 **dal container**, non da Caddy. La documentazione
che lo elenca fra le feature non corrisponde a questa build.

- Progetto: `~/filebrowser` · immagine `ghcr.io/gtsteffaniak/filebrowser:beta`
  (v2.0.9-beta) · in ascolto su `127.0.0.1:8081` → porta 80 nel container
- Dati: `/srv/documenti`, montati in **lettura-scrittura** su `/documenti`
  (dal 2026-09-30; prima `:ro`, vedi § Dalla sola lettura alla scrittura)
- Config e database: `~/filebrowser/data/` (`config.yaml`, `filebrowser.sqlite`)

```yaml
# compose.yaml
services:
  filebrowser:
    image: ghcr.io/gtsteffaniak/filebrowser:beta
    group_add:
      - "1001"          # gruppo vault: dà scrittura su /srv/documenti
    container_name: filebrowser
    restart: unless-stopped
    ports:
      - "127.0.0.1:8081:80"
    volumes:
      - /srv/documenti:/documenti
      - ./data:/home/filebrowser/data
```

```yaml
# data/config.yaml  (chmod 600)
server:
  sources:
    - path: "/documenti"
      config:
        defaultEnabled: true
  database:
    path: "/home/filebrowser/data/filebrowser.sqlite"

auth:
  adminUsername: paolo
  adminPassword: "<in chiaro nel file>"
```

### Trappole incontrate

- **Lo schema v2 non ha `server.port` né `server.baseURL`.** La porta 80 è fissa
  dentro il container; con quelle chiavi il container esce in FATAL.
- `curl -I` (**HEAD**) risponde **404 anche a servizio sano**: verificare con GET.
- `auth.adminPassword` è in chiaro e sembra **riapplicata a ogni avvio**: la
  password va cambiata nel file, non dall'interfaccia.
- **Il mount era `:ro` e non lo è più** (2026-09-30): l'errore
  `mkdir /documenti/test: read-only file system` era il progetto che funzionava,
  non un guasto. Vedi § Dalla sola lettura alla scrittura.
- **Samba: da rinviata a candidata principale** (2026-09-30). Era stata scartata
  perché il WebDAV di Quantum non sostituiva l'unità di rete su Windows; ora che
  il WebDAV non c'è proprio, Samba resta l'unico modo per avere insieme il disco
  mappato su Windows e un'app di file manager sul telefono. Vedi § Consultare i
  documenti dal telefono.

### Dalla sola lettura alla scrittura (2026-09-30)

Il sintomo: dall'interfaccia, *New folder* rispondeva
`mkdir /documenti/test: read-only file system`.

La diagnosi utile e' nel **tipo** di errore. `read-only file system` e' `EROFS`,
l'errno che restituisce la syscall: e' il kernel a rifiutare, non
l'applicazione. Se fosse stato il `readOnly` interno di Quantum sulla source, il
messaggio sarebbe stato suo. Quindi il problema era il bind mount `:ro` — cioe'
la decisione #1 che funzionava come previsto.

Perche' e' stata rivista: `:ro` non era la protezione dei dati (quella e' il
backup, ancora aperto), e l'import in arrivo dal Victus richiede di poter
riordinare le cartelle senza passare ogni volta da SSH. Resta invece scartato
l'**editing online**: niente Collabora, niente suite office nel browser.

Non bastava togliere `:ro`. La cartella era `drwxr-xr-x 1000:1000`, scrittura al
solo proprietario, e il container gira come utente **non root** (`filebrowser`):
sarebbe finita in `permission denied`, lo stesso muro con un cartello diverso.
E un `chown` secco al container avrebbe creato proprieta' miste, perche' in
quella stessa cartella ci scrive anche `rsync` come `paolo`.

Soluzione: gruppo condiviso, lo stesso schema gia' usato per Immich con
`group_add: ["993", "44"]`.

```bash
sudo chgrp -R vault /srv/documenti     # gruppo vault = GID 1001
sudo chmod -R g+rwX /srv/documenti
sudo chmod g+s /srv/documenti          # -> drwxrwsr-x 1000 1001
```

Il **setgid** e' il pezzo che conta nel tempo: tutto cio' che nasce in quella
cartella eredita il gruppo `vault`, sia che lo crei FileBrowser sia che lo crei
`rsync`. Senza, i permessi divergono di nuovo al primo import.

Nel compose: `group_add: ["1001"]` sul servizio e `:ro` rimosso dal volume.
Validare con `docker compose config --quiet` prima di `up -d`.

⚠️ **Nota sui permessi applicativi**, da non confondere con quelli del
filesystem: i `defaultPermissions` della source sono `view`, `download` e
`configured`. `paolo` scrive perché è admin con scope `"documenti": "/"`. Un
secondo utente creato coi default attuali potrebbe leggere e scaricare ma **non**
modificare — da sapere prima di crearlo, altrimenti si va a cercare il problema
nei permessi Unix, che invece sono a posto.

Verifica se un giorno tornasse a rompersi:
- `permission denied` -> il container non ha preso il gruppo:
  `docker exec filebrowser id` deve mostrare 1001
- `read-only file system` -> e' tornato il `:ro`, oppure `/` si e' rimontato in
  sola lettura per un errore di I/O: `findmnt -no SOURCE,FSTYPE,OPTIONS /`

## Foto — Immich

- Progetto: `~/immich` · versione `IMMICH_VERSION=v3`
- Dati: `UPLOAD_LOCATION=/srv/immich/library`, `DB_DATA_LOCATION=/srv/immich/db`
- Porta 2283, **binding di default `0.0.0.0`** — deliberatamente *non* sull'IP
  tailnet: bindare su `100.76.226.98` creerebbe una dipendenza dall'ordine di
  avvio al reboot (Docker può partire prima che tailscaled assegni l'indirizzo)
- Installato dai file ufficiali (`docker-compose.yml`, `example.env`,
  `hwaccel.transcoding.yml`) scaricati dalla release
- **Operativo dal 2026-09-28: Immich v3.2.2**, 16 core rilevati, migrazioni
  completate, nessuno schema drift. Container: `immich_server`,
  `immich_machine_learning`, `immich_postgres`, `immich_redis`.
- Database: immagine ufficiale `ghcr.io/immich-app/postgres:14-vectorchord…`
  (VectorChord, non più pgvecto.rs). Redis è in realtà **Valkey 9**.
- Feature attive di serie: smart search, riconoscimento volti, rilevamento
  duplicati, mappa e reverse geocoding, **OCR**, cestino.

#### Primo avvio: `ECONNREFUSED …:5432` è normale

Al primissimo `up -d` il server parte prima che PostgreSQL abbia finito di
inizializzarsi ed esce con `Error: connect ECONNREFUSED <ip>:5432`. Ci pensa
`restart: always`: al tentativo successivo il database è pronto e l'avvio
prosegue. Non è un guasto e non si ripete ai riavvii successivi.

### Pinning della versione

`IMMICH_VERSION=v3` e non più fine. Immich dichiara semver con i breaking change
confinati alle **major**: il tag `v3` porta minor e patch senza sorprese e
protegge dal salto a v4, l'unico che richiede di leggere le note di rilascio.

### Transcodifica hardware (VAAPI sulla Radeon 680M)

Nel blocco `immich-server` di `docker-compose.yml`:

```yaml
    extends:
      file: hwaccel.transcoding.yml
      service: vaapi
    group_add:
      - "993"
```

- `993` è il GID del gruppo `render` su gjarper. Il file ufficiale non prevede
  `group_add` perché il container gira come root, che apre `/dev/dri/renderD128`
  in virtù del proprietario. È assicurazione a costo zero: con un UID/GID
  non-root, senza quello la transcodifica ricadrebbe **silenziosamente** su CPU.
- ⚠️ **Trappola del `sed`**: una sostituzione non ancorata scommenta anche il
  blocco `extends` di `immich-machine-learning`, che però estende un file diverso
  (`hwaccel.ml.yml`, servizi `cuda`/`rocm`/`openvino`/…) → errore
  `service "vaapi" not found`. Limitare sempre il range:
  `sed -i '/^  immich-server:/,/^  immich-machine-learning:/ { ... }'`
- Validare con `docker compose config --quiet` prima di `up -d`: risolve
  l'`extends` e fallisce subito se l'indentazione è sbagliata.
- **L'accelerazione va accesa anche in applicazione**: Admin → Video transcoding
  → hardware acceleration → **VAAPI**. Il compose espone solo il device.
- Verifica: `docker exec immich_server ls -l /dev/dri` deve mostrare `card0` e
  `renderD128`.

### Machine learning: resta su CPU

`hwaccel.ml.yml` offre `rocm` per AMD, ma ROCm non supporta ufficialmente
`gfx1035` (la 680M) e l'immagine pesa svariati GB. Con 16 thread CLIP e
riconoscimento volti vanno bene. L'accelerazione che conta — quella video —
è già coperta da VAAPI.

## Procedure

### Import massivo di documenti — da PC a gjarper via SSH

Dal 2026-09-30 l'upload dall'interfaccia web funziona, ma per il **bulk** resta
lo strumento sbagliato: un browser che carica decine di GB non riprende da dove
si è interrotto, `rsync` sì. I file entrano lato server, via SSH. Tutti i
comandi si lanciano da **Git Bash sul PC**, non su gjarper.

#### Prerequisiti

- Accesso SSH funzionante: `ssh paolo@<ip-lan-gjarper>`
- **L'IP LAN** di gjarper — lo stesso delle voci `.gjarper` nel file hosts.
  Non usare il nome tailnet: i PC non sono nel tailnet, e in LAN si va più veloce.
- Se serve una chiave dedicata, aggiungere `-i ~/.ssh/<nome-chiave>` a ogni
  comando, oppure — molto più comodo — definire una volta l'alias in
  `~/.ssh/config` sul PC:

  ```
  Host gjarper
      HostName 192.168.x.y
      User paolo
      IdentityFile ~/.ssh/<nome-chiave>
  ```

  Da quel momento basta `scp -r cartella gjarper:/srv/documenti/`.

#### Metodo 1 — `scp` (sempre disponibile)

```bash
scp -r "/c/Users/paolo/Documents/CartellaDaCopiare" \
    paolo@<ip-lan-gjarper>:/srv/documenti/
```

Semplice ma **non riprendibile**: se cade a metà, riparte da zero. Va bene per
poche centinaia di MB.

#### Metodo 2 — `rsync` (preferito, se c'è)

Verificare con `rsync --version`; se manca, resta `scp`.

```bash
# 1. prova a vuoto: elenca cosa farebbe senza copiare niente
rsync -avhn --progress \
      "/c/Users/paolo/Documents/CartellaDaCopiare/" \
      paolo@<ip-lan-gjarper>:/srv/documenti/CartellaDaCopiare/

# 2. copia vera, escludendo la spazzatura di Windows e i lock di Office
rsync -avh --progress --partial \
      --exclude='~$*' --exclude='Thumbs.db' \
      --exclude='desktop.ini' --exclude='.DS_Store' \
      "/c/Users/paolo/Documents/CartellaDaCopiare/" \
      paolo@<ip-lan-gjarper>:/srv/documenti/CartellaDaCopiare/
```

Note che fanno la differenza:

- **Lo slash finale conta.** `sorgente/` copia il *contenuto* dentro la
  destinazione; `sorgente` senza slash copia la *cartella stessa* dentro la
  destinazione, creando un livello di annidamento in più.
- `-n` è il dry-run: lanciarlo sempre prima su alberi grandi.
- `--partial` conserva i file parziali, così un rilancio riprende da lì.
- `--exclude='~$*'` salta i file di lock di Word/Excel (`~$documento.docx`), che
  altrimenti finiscono nell'archivio e confondono.
- **Niente `-z`** in LAN: la compressione costa CPU e non serve, perché `.docx`,
  `.xlsx` e `.pdf` sono già formati compressi.
- Rilanciare lo stesso comando è sicuro e trasferisce solo le differenze: è il
  modo giusto per aggiornare l'archivio in un secondo momento.
- I percorsi Windows in Git Bash si scrivono `/c/Users/...`; le virgolette
  servono se contengono spazi.
- I file arrivano di proprietà di `paolo`, già proprietario di `/srv/documenti`:
  nessun `chown` da fare dopo. Il **setgid** sulla cartella fa sì che ereditino
  anche il gruppo `vault`, lo stesso con cui ci scrive FileBrowser: è quello che
  tiene i permessi coerenti fra i due canali di scrittura.

#### Verifica

```bash
# sul PC
find "/c/Users/paolo/Documents/CartellaDaCopiare" -type f | wc -l

# su gjarper
ssh paolo@<ip-lan-gjarper> 'find /srv/documenti -type f | wc -l; du -sh /srv/documenti'
```

I due conteggi devono coincidere, al netto delle esclusioni.

#### Dopo l'import

Se l'interfaccia non mostra i file nuovi, forzare la re-indicizzazione:

```bash
ssh paolo@<ip-lan-gjarper> 'cd ~/filebrowser && docker compose restart'
```

#### Se serve sincronizzazione continua

`rsync` è un travaso: va rilanciato a mano ed è unidirezionale. Per una
sincronizzazione **continua e bidirezionale** lo strumento è Syncthing — non a
caso nel Caddyfile c'è già un blocco `sync.gjarper` residuo che lo prevedeva. È
un servizio in più da mantenere: da valutare solo se il rilancio periodico pesa.

### Aggiungere un secondo utente foto (es. iPhone)

Sono due passaggi **indipendenti**: l'accesso alla rete e l'account applicativo.

#### 1. Accesso alla rete — Tailscale

Il piano gratuito **Personal arriva a 6 utenti** con dispositivi illimitati,
quindi un secondo utente non comporta costi. Attenzione però: il **settimo**
utente farebbe passare l'intero tailnet a piano a pagamento, con *tutti* gli
utenti fatturati.

Due strade:

- **Consigliata — invitarlo come utente del tailnet.** Console Tailscale →
  *Users* → *Invite*. Riceve un invito, si registra con un proprio account
  (Google/Microsoft/GitHub/Apple) e aggiunge il suo iPhone. Identità separata,
  revocabile da sola, e nella console si vede a chi appartiene ogni dispositivo.
- **Sconsigliata — autenticare il suo iPhone con l'account di Paolo.** Più
  rapido, ma il dispositivo eredita la sua identità, non si revoca in modo
  selettivo e complica eventuali ACL future.

#### 2. Account applicativo — Immich

Dopo la creazione dell'amministratore la registrazione autonoma è chiusa: gli
utenti li crea l'admin da **Amministrazione → Utenti → Aggiungi utente** (email,
password, nome, ed eventuale quota di archiviazione).

Poi sull'iPhone: app Immich → indirizzo server
`http://gjarper.tail6cb7a3.ts.net:2283` → login con le sue credenziali →
*Backup* → selezione degli album → attivazione del backup.

#### Le librerie sono separate

Ogni utente Immich vede **solo le proprie foto**: non esiste un raccoglitore
comune. Per vedersi a vicenda ci sono due meccanismi distinti:

- **Partner** (*Condivisione → Partner*): condivisione continua dell'intera
  libreria fra due utenti. Va concessa da entrambi perché sia reciproca.
- **Album condivisi**: selezione puntuale, per singole raccolte.

#### Avvertenze iOS

- Il backup in background su iOS è **governato dal sistema operativo** e
  schedulato in modo imprevedibile: l'app va **aperta periodicamente** perché il
  caricamento avanzi. Non è un difetto di Immich e non si può aggirare.
- Tailscale su iOS: attivare **Connect On Demand** nelle impostazioni dell'app,
  l'equivalente dell'always-on di Android. Anche così iOS può sospendere la VPN
  in background — un motivo in più per aprire l'app di tanto in tanto.

### Consultare i documenti dal telefono

**Scelta del 2026-09-30: scorciatoia Chrome, niente app.** Su Android si apre
`http://gjarper.tail6cb7a3.ts.net` con Tailscale attivo, poi menu ⋮ → *Aggiungi
a schermata Home*. Quantum genera le icone PWA, quindi sul launcher compare
un'icona vera e non il quadratino della favicon.

**Limite noto, e non è un errore di configurazione.** Su HTTP semplice Chrome
non *installa* la PWA: la modalità standalone — finestra propria, senza barra
degli indirizzi — richiede un service worker, e i service worker girano solo in
contesto sicuro. La scorciatoia apre quindi una normale scheda di Chrome.
Su iOS il comportamento è diverso: Safari usa i propri meta tag e *Aggiungi a
Home* dà spesso la modalità standalone anche senza TLS. Da tenere presente per
il secondo utente.

#### Se un giorno si vuole la modalità standalone

Serve un certificato valido, che Tailscale emette senza esporre niente su
internet e senza un dominio proprio. Console Tailscale → *DNS → HTTPS
Certificates → Enable*, una volta sola. Poi su gjarper:

```bash
sudo tailscale cert gjarper.tail6cb7a3.ts.net
sudo tailscale serve --bg --https=443 http://127.0.0.1:8081
sudo tailscale serve status
```

⚠️ Caddy gira in `network_mode: host` e occupa già `*:443`. `tailscale serve`
intercetta il traffico diretto all'IP del tailnet a livello di interfaccia e non
fa un `bind` normale, quindi il conflitto potrebbe non esserci — ma se protesta
si usa `--https=8443` e l'URL diventa `https://gjarper.tail6cb7a3.ts.net:8443`.
Effetto collaterale desiderabile: chiude anche il traffico in chiaro verso i PC.

#### Alternative valutate e scartate

| Strada | Esito |
|---|---|
| App nativa di FileBrowser | Non esiste: il progetto è solo web. |
| WebDAV in un file manager (Material Files su Android, app *File* su iOS) | **Impossibile**: la `2.0.9-beta` non espone WebDAV. Vedi § Documenti — FileBrowser Quantum. |
| SFTP | Funzionerebbe subito, ma confinarlo a `/srv/documenti` richiede `ChrootDirectory` con la cartella di proprietà di `root`, in conflitto coi permessi del gruppo `vault`. Senza confinamento, il telefono porta in giro le credenziali dell'intera macchina. |
| Samba | Non scartata: resta la candidata per il **disco mappato su Windows**, che è un problema diverso da quello del telefono. |

#### API token `android-pixel10a`

Creato il 2026-09-30, scadenza 2028-09-19. **Non serve alla scorciatoia**: era
nato per autenticare il client WebDAV che poi si è scoperto non esistere. Si
tiene perché è la credenziale per l'**API REST** (`/api/resources` e il resto
dello swagger linkato in *Impostazioni → API Tokens*), utile il giorno in cui si
vorrà automatizzare qualcosa su quei file — per esempio dopo l'import dal Victus.

Da verificare prima di usarlo in scrittura: nella lista i permessi risultano
`✓✓✓✗`, uno dei quattro fra `admin`, `api`, `share` e `realtime` è negato.

## Aperti

1. **Backup — la lacuna più grave.** Nessuna copia fuori dalla macchina. Da
   chiudere **prima** del bulk import delle foto, che è il momento in cui i dati
   diventano insostituibili.
   - Buona notizia: **Immich v3 fa da sé i dump del database**, in automatico,
     dentro la cartella `backups/` di `UPLOAD_LOCATION` (quindi
     `/srv/immich/library/backups`), ed espone in interfaccia sia la gestione
     sia il "Ripristina da Backup" della schermata iniziale. Non serve quindi
     uno script `pg_dumpall` separato.
   - Ne consegue che il lavoro residuo è **solo portare `/srv/immich` e
     `/srv/documenti` fuori dalla macchina**: un repo `restic` sull'HDD interno
     per il restore veloce, più un repo remoto per l'offsite. Con volumi così
     piccoli (~30 GB) l'offsite su storage a oggetti costa pochi centesimi al
     mese ed evita di ruotare a mano un disco di dieci anni.
   - Da verificare che i dump automatici siano effettivamente attivi e con che
     periodicità: Amministrazione → Impostazioni → Backup del database.
2. **Secondo utente foto (iPhone)**: procedura documentata sopra in
   *Procedure → Aggiungere un secondo utente foto*. Da eseguire.
3. **Bulk fotografico** (20-30 GB): rinviato. Lo strumento dipende dalla
   provenienza — `immich-go` per un export Google Takeout (ricostruisce album,
   date e geolocalizzazione dai JSON), `immich-cli` per cartelle sparse.
   Sbagliare strumento con un Takeout significa perdere gli album.
4. **Verifica del collegamento diretto**: con il Pixel sul wifi di casa,
   `tailscale status` deve mostrare `direct 192.168.x.x:…` accanto a
   `pixel-10a`. Se mostra `relay`, il traffico rimbalza su un server Tailscale
   invece di restare in LAN e va sistemato sul router.
5. **Verifica della transcodifica VAAPI**: `docker exec immich_server ls -l
   /dev/dri` (devono comparire `card0` e `renderD128`) e interruttore
   Amministrazione → Transcodifica video → accelerazione hardware → VAAPI.
6. **Pulizia del Caddyfile**: rimuovere i blocchi residui `sync.gjarper` e
   `vault.gjarper`.
7. **UPS** (~40-50 €) e gli 82 pacchetti di sistema aggiornabili.

## Cronologia

- **2026-09-28** — sessione di setup: riattivato Tailscale (`tailscaled` era
  spento); installato FileBrowser Quantum su `documenti.gjarper` con
  `/srv/documenti` in sola lettura; installato Immich v3.2.2 su `foto.gjarper`
  e porta 2283 con transcodifica VAAPI configurata nel compose; primo backup
  dal Pixel avviato. Hardware e capacità già censiti in `gjarper-hardware.md`.

- **2026-09-30** — `/srv/documenti` da sola lettura a scrittura: rimosso `:ro`
  dal compose, aggiunto `group_add: ["1001"]` (gruppo `vault`), e sulla cartella
  `chgrp -R vault` + `chmod -R g+rwX` + `chmod g+s`. Creazione cartelle
  dall'interfaccia verificata. Aggiornata di conseguenza la decisione #1 in
  `gjarper-hardware.md`.

- **2026-09-30** (seguito) — accesso dal telefono: verificato che la `2.0.9-beta`
  **non ha WebDAV** (nessuna rotta nello swagger, nessuna chiave `disableWebDAV`
  nella configurazione effettiva, nessuna voce nell'interfaccia), quindi niente
  file manager Android. Scelta la **scorciatoia Chrome** su
  `http://gjarper.tail6cb7a3.ts.net`. Creato l'API token `android-pixel10a`
  (scadenza 2028), che resta utile per l'API REST. Samba promossa da «rinviata» a
  candidata principale per il disco mappato su Windows.
