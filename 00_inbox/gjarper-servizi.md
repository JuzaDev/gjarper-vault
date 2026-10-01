---
tipo: nota
zona: pubblica
tag: [rnd]
aggiornata: 2026-10-01
stato: FileBrowser, Immich e transcribe operativi; disco WD500 montato su
  /mnt/disco. Restano restic, prenotazione DHCP, autenticazione di transcribe,
  secondo utente iPhone e bulk fotografico
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
| Trascrizioni | `http://trascrizione.gjarper` | PC con la voce in `/etc/hosts` |
| Trascrizioni | `http://<ip-lan>:8000` | LAN - bypassa Caddy, vedi § Trascrizioni |
| Documenti | `http://gjarper.tail6cb7a3.ts.net` | qualsiasi device Tailscale, telefoni compresi |
| Foto | `http://<ip-lan>:2283` | LAN |
| Foto | `http://gjarper.tail6cb7a3.ts.net:2283` | qualsiasi device Tailscale |
| Foto | `http://foto.gjarper` | PC, **solo se** si aggiunge il blocco Caddy + hosts |

⚠️ Caddy fa match sull'**header Host**, quindi puntare il browser all'IP tailnet
nudo (`http://100.76.226.98`) **non** funziona: nessun blocco corrisponde. Dai
telefoni si usa il nome MagicDNS, non l'IP.

## Reverse proxy — Caddy

- **Compose: `~/infra/caddy/docker-compose.yml`** (corretto il 2026-10-01: la
  nota diceva `~/infra`, dove non c'è nessun file che Compose riconosca - un
  `docker compose up -d` da lì risponde `no configuration file provided`).
  Il container si chiama `infra-caddy-1` e non `caddy-caddy-1` perché nel file
  c'è un `name: infra` esplicito.
- Container `infra-caddy-1`, immagine `caddy:2`
- **`network_mode: host`** → ascolta direttamente su `*:80` e `*:443` e raggiunge
  gli altri container su `127.0.0.1:<porta>`
- Config: `~/infra/caddy/Caddyfile` → montato su `/etc/caddy/Caddyfile`
- Convenzione: un blocco per servizio, prefisso `http://` = niente auto-HTTPS
- Porte occupate: 3089 (anime-monitor), 5199/8099 (yt-analizer), 8000
  (transcribe-web), 8081 (filebrowser), 2283 (immich)
- Blocchi verso servizi **fermi, non inesistenti**: `sync.gjarper` → 8384
  (`~/syncthing/docker-compose.yml`) e `vault.gjarper` → 3300
  (`~/infra/silverbullet/docker-compose.yml`). ⚠️ Rettifica del 2026-10-01: non
  sono residui da cancellare al volo, sono due servizi installati e spenti.
  Syncthing in particolare è la risposta già individuata al problema della
  sincronizzazione continua dei documenti. Decidere prima se riaccenderli.
  (Entrambi hanno `restart: unless-stopped`: fermati a mano, **non** ripartono
  da soli al boot.)
- `vault.gjarper` è l'unico blocco senza prefisso `http://`, ma ha `tls internal`
  → certificato dalla CA interna di Caddy, non un certificato pubblico. Fa
  comparire nel log `server is listening only on the HTTPS port...`: è normale.

### Modificare il Caddyfile — la regola che è costata un'interruzione

```bash
# 1. backup
cp ~/infra/caddy/Caddyfile ~/infra/caddy/Caddyfile.bak
# 2. modifica
nano ~/infra/caddy/Caddyfile
# 3. VALIDA (funziona anche se il container è rotto: usa un container usa-e-getta)
docker run --rm -v ~/infra/caddy/Caddyfile:/etc/caddy/Caddyfile:ro caddy:2 \
  caddy validate --config /etc/caddy/Caddyfile
# 4. solo se dice "Valid configuration":
docker exec infra-caddy-1 caddy reload --config /etc/caddy/Caddyfile
```

**Guardare sempre l'esito del passo 3 o 4.** Un `reload` fallito non spegne
niente: il processo continua a servire la configurazione **vecchia, tenuta in
memoria**, e il file rotto su disco ti aspetta al primo riavvio - settimane
dopo, quando non ricordi più cosa avevi cambiato.

Formattazione (facoltativa, toglie il warning `input is not formatted`):

```bash
docker run --rm -v ~/infra/caddy:/work -w /work caddy:2 caddy fmt --overwrite Caddyfile
```

### Incidente del 2026-10-01 — `ambiguous site definition`

**Sintomo:** dopo lo spegnimento per montare il disco, `infra-caddy-1` in
`Restarting (1)` a ciclo continuo e **nessun** nome `.gjarper` raggiungibile dai
PC, mentre tutti gli altri container erano `Up`.

**Causa:** nel Caddyfile il blocco `http://foto.gjarper` compariva **due volte**,
identico (righe 35-37 e 39-41). Caddy non sceglie fra due definizioni dello
stesso sito: rifiuta l'intera configurazione ed esce con codice 1.

```
Error: adapting config using caddyfile: ambiguous site definition: http://foto.gjarper
```

**La lezione, che è il vero contenuto di questo paragrafo:** il file era rotto
**dal 28/09**, probabilmente dal setup di Immich. Caddy girava da 7 settimane
con la configurazione valida caricata in memoria, e nessuno se n'era accorto.
Il riavvio non ha causato il guasto - l'ha solo **rivelato**. Da cui la regola
del paragrafo precedente.

**Diagnosi in ordine**, per la prossima volta che "non si raggiunge niente":

1. `docker ps` - se gli altri container sono `Up` e solo Caddy è `Restarting`,
   il problema è il proxy, non la rete né la macchina.
2. `docker logs --tail 50 infra-caddy-1` - Caddy scrive in chiaro la riga che
   non gli torna.
3. Controprova a costo zero: **transcribe su `http://<ip-lan>:8000` bypassa
   Caddy**. Se quello risponde, i servizi stanno bene e manca solo il proxy.
4. Solo se anche SSH e `ping` falliscono, allora è rete: IP cambiato (è DHCP,
   vedi `gjarper-hardware.md`), cavo ethernet, o una **VPN attiva sul PC** che
   dirotta anche gli indirizzi di LAN.

**Riparazione:** rimosso il blocco duplicato, `caddy validate` → `Valid
configuration`, `docker restart infra-caddy-1` → `Up`.

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

## Archivio — disco WD500 su `/mnt/disco`

Dal 2026-10-01 nel bay 2.5" c'è un **WD Blue Mobile 500 GB** (dettagli e SMART in
`gjarper-hardware.md`). **Non era vuoto**: contiene 136 GB di backup di quattro
macchine - `backup_acer_chiara_30092026`, `backup_hitachi750`,
`BACKUP_victus_29092026`, `backup_WD500_29092026` - più `Film` e `Foto`.
Restano **331 GB liberi**.

Di conseguenza **NTFS è stato tenuto**, niente formattazione.

```
# /etc/fstab  (backup in /etc/fstab.bak)
UUID=1402C95602C93D8C  /mnt/disco  ntfs-3g  defaults,nofail,uid=1000,gid=1001,umask=0002,windows_names,big_writes,x-systemd.device-timeout=10  0  0
```

Verifica: `ls -ld /mnt/disco` deve dare `drwxrwxr-x 1 paolo vault`.

Perché ogni opzione, perché nessuna è decorativa:

- **`ntfs-3g` e non `ntfs3`** - il driver effettivamente in uso qui è ntfs-3g via
  FUSE. Si legge da `mount | grep sda2`: `type fuseblk` = ntfs-3g,
  `type ntfs3` = driver in kernel. Mettere il tipo sbagliato fa fallire il mount.
- **`uid=1000,gid=1001`** - NTFS **non ha permessi Unix**: il kernel se li
  inventa per tutto il volume. Senza istruzioni li inventa a favore di root
  (`user_id=0,group_id=0` nell'output di `findmnt`) e non ci scrivi senza
  `sudo`. Così invece il volume è di `paolo` e del gruppo **`vault` (GID 1001)**,
  lo stesso che FileBrowser ha già in `group_add`: esporre `Film` o `Foto`
  nell'interfaccia non richiederà di toccare i permessi.
- **`umask=0002`** - cartelle 775, file 664, invece del 777 di default.
- **`nofail`** - ⚠️ il pezzo che conta davvero. Senza, il giorno in cui questo
  disco muore **il server non completa il boot** e perdi anche Immich e i
  documenti per colpa di un disco secondario.
- **`0 0` finale** - niente `fsck` all'avvio: su NTFS non esiste, e un valore
  diverso da zero bloccherebbe il boot.

### Trappole incontrate

- **Primo mount sempre in sola lettura** (`mount -o ro /dev/sda2 /mnt/disco`).
  Se il disco è stato staccato da Windows con Fast Startup o ibernazione attivi,
  l'NTFS resta marcato *dirty*: montarlo in scrittura in quello stato è il modo
  classico di danneggiare la tabella dei file. Qui era pulito. Se non lo fosse,
  non si ripara da Linux: si rimette su un PC Windows, `chkdsk /f` o espulsione
  corretta.
- **La partizione da montare è `sda2`, non `sda1`.** `sda1` è la Microsoft
  Reserved Partition (16 MB, vuota per definizione): non si monta e non si tocca.
  È il layout normale di un disco GPT formattato da Windows.
- Dopo aver modificato `/etc/fstab`, `mount -a` avverte che systemd usa ancora la
  versione vecchia: `sudo systemctl daemon-reload`. Non è obbligatorio (al boot
  si riallinea da solo) ma toglie l'avviso.

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

## Trascrizioni — transcribe

- Progetto: `~/transcribe` (repo `github.com/takohemi/transcribe`), container
  `transcribe-web-1`, immagine costruita in locale
- Compose di produzione: `~/transcribe/docker/docker-compose.yml`
- Dati persistenti in `~/transcribe/data/` (uploads, outputs, modello Whisper,
  SQLite). Il `.env` tiene la configurazione.
- URL: `http://trascrizione.gjarper` dietro Caddy, **e anche**
  `http://<ip-lan>:8000` diretto, perché il container pubblica su `0.0.0.0:8000`

### Aggiornare

```bash
cd ~/transcribe && ./deploy.sh     # git pull --ff-only + rebuild + restart + health
```

- ⚠️ **Lanciarlo a coda vuota**: il restart marca `failed` i job in corso.
  Controllo: `curl -s http://localhost:8000/api/health` → `"queue_size":0`.
- **Anche una modifica alla sola UI richiede il rebuild**: il `Dockerfile` fa
  `COPY static/ static/` e il compose di produzione monta **solo** `../data`, non
  il codice. Niente `restart`, serve `up -d --build` - che è ciò che fa lo script.
- La working tree sul server riceve solo `git pull`; il `--ff-only` blocca il
  deploy se ci sono divergenze. Non modificarla a mano.
- Verifica utile dopo ogni deploy: `/api/health` deve riportare
  `"timezone":"Europe/Rome"` - è l'unico errore che non si manifesta come errore.

Ultimo deploy: **2026-10-01, commit `204cb25`** (paginazione client-side dei job,
layout più largo). Build ~2 minuti.

### ⚠️ Esposto senza autenticazione

`/api/health` riporta `"auth": false`: **`APP_TOKEN` non è impostato** nel
`.env`, e il container ascolta su `0.0.0.0:8000`. Chiunque sia sulla LAN apre
transcribe e scarica tutte le trascrizioni. Da chiudere su due fronti, che sono
complementari:

```bash
# A) token applicativo
cd ~/transcribe && nano .env        # APP_TOKEN=<stringa lunga casuale>
./deploy.sh

# B) togliere l'ascolto dalla LAN, come tutti gli altri servizi
#    docker/docker-compose.yml:  "8000:8000"  ->  "127.0.0.1:8000:8000"
#    il blocco trascrizione.gjarper nel Caddyfile esiste già
```

Nota: fatto il punto B, `http://<ip-lan>:8000` smette di funzionare e resta solo
`http://trascrizione.gjarper` - quindi non è più disponibile come controprova
"Caddy è giù ma i servizi stanno bene" descritta in § Incidente del 2026-10-01.

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
   - **Dal 2026-10-01 la destinazione locale esiste**: `/mnt/disco`, 331 GB
     liberi, SMART impeccabile. Manca solo `restic` - `sudo apt install restic`,
     `restic init --repo /mnt/disco/restic`, uno snapshot di `/srv` e un timer
     systemd.
   - ⚠️ **Ma il disco è dentro la stessa scatola.** Stesso alimentatore, stesso
     (non) UPS, stesso furto, stesso fulmine. Copre il guasto dell'NVMe e la
     cancellazione per sbaglio; **non** è l'offsite, che resta da fare. Vale
     anche al contrario: i 136 GB di backup di altre macchine che erano su quel
     disco adesso non hanno più una copia altrove.
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
7. **UPS** (~40-50 €) e i pacchetti di sistema arretrati (69 al 2026-10-01).
8. **Prenotazione DHCP** di `192.168.8.19` nel router: l'IP di gjarper è
   `dynamic`, e quando cambierà si romperanno i file hosts di tutti i PC.
9. **Autenticazione di transcribe** - vedi § Trascrizioni, `"auth": false`.
10. **Syncthing e SilverBullet**: decidere se riaccenderli o rimuovere i
    rispettivi blocchi dal Caddyfile.

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

- **2026-10-01** - sessione di manutenzione. (1) `transcribe` aggiornato a
  `204cb25` con `deploy.sh`. (2) Montato il **WD500** nel bay 2.5": SMART
  verificato (impeccabile), NTFS mantenuto coi 136 GB di backup preesistenti,
  `/mnt/disco` in `/etc/fstab` con `nofail` e `uid/gid` su `paolo:vault`.
  (3) Risolto il crash-loop di **Caddy** (`ambiguous site definition:
  http://foto.gjarper`, blocco duplicato) che teneva giù tutti i nomi
  `.gjarper`: era latente dal 28/09 e il riavvio l'ha solo rivelato.
  (4) Scoperto che il compose di Caddy sta in `~/infra/caddy/`, non in `~/infra`.
  (5) Scoperto che l'IP LAN è DHCP, non statico, e che transcribe gira senza
  `APP_TOKEN`.

- **2026-09-30** (seguito) — accesso dal telefono: verificato che la `2.0.9-beta`
  **non ha WebDAV** (nessuna rotta nello swagger, nessuna chiave `disableWebDAV`
  nella configurazione effettiva, nessuna voce nell'interfaccia), quindi niente
  file manager Android. Scelta la **scorciatoia Chrome** su
  `http://gjarper.tail6cb7a3.ts.net`. Creato l'API token `android-pixel10a`
  (scadenza 2028), che resta utile per l'API REST. Samba promossa da «rinviata» a
  candidata principale per il disco mappato su Windows.
