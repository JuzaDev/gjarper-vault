---
tipo: nota
zona: pubblica
tag: [rnd]
aggiornata: 2026-09-30
stato: compilata — resta lo SMART dei 2 HDD e l'ispezione del bay 2.5"
---

# gjarper — inventario hardware

Fonte: `00_inbox/archivio/serverino-hardware.txt` + report di sistema del
2026-09-28 (`/tmp/gjarper-report.txt` sulla macchina) + schede tecniche
Minisforum/AMD. **[DA VERIFICARE]** = ancora aperto.

## Macchina

- **Modello:** MINISFORUM **UM773 Lite** (barebone, comprato senza RAM né SSD)
- **Hostname:** `gjarper` · utente `paolo` (uid 1000)
- **Alimentazione:** alimentatore esterno 19 V (~120 W) · **UPS: assente**
- **I/O:** 2 × HDMI · 1 × USB4 · 1 × USB-C · 4 × USB 3.2 · Wi-Fi 6 · BT 5.2
- **Età reale:** **31 ore di accensione** al 2026-09-28 → macchina quasi nuova

## CPU / GPU

- **CPU:** AMD **Ryzen 7 7735HS** — Zen 3+ "Rembrandt-R"
  - **8 core / 16 thread** (confermato), base 3,20 GHz, boost 4,75 GHz
  - TDP configurabile 35–54 W · a riposo scaling ~33%
  - **ISA:** AVX, AVX2 — **nessun AVX-512** · livello **x86-64-v3**
    → soddisfa il requisito `x86-64-v2` della ML di Immich
- **iGPU:** AMD **Radeon 680M** (`34:00.0`, Rembrandt rev 0a) — RDNA 2, 12 CU
  - **`/dev/dri/card0` e `/dev/dri/renderD128` presenti**
  - Gruppi: **`render` = GID 993**, **`video` = GID 44**
  - `paolo` non è in nessuno dei due → per Immich serve
    `group_add: ["993", "44"]` nel compose; non serve modificare l'utente
  - `vainfo` **[DA VERIFICARE]**: primo test fallito perché lanciato senza
    display DRM. Rifare con `vainfo --display drm --device /dev/dri/renderD128`
- **Temperature a riposo:** Tctl **41,8 °C**, temp1 36 °C → ampia riserva termica

## RAM

- **Installata:** **2 × 8 GB DDR5 SODIMM** — CHANNEL A + CHANNEL B,
  Configured Memory Speed **4800 MT/s** → **dual channel confermato**, banda piena
- **Slot:** 2 × SODIMM · **massimo 64 GB** (2 × 32 GB)
- **Banda teorica:** **76,8 GB/s**
- **RAM visibile al sistema: 13 GiB, non 16.** Circa 2 GiB sono riservati al
  frame buffer dell'iGPU (UMA Frame Buffer, impostazione BIOS). Su un server
  headless si recuperano portando l'UMA a 512 MB: amdgpu su Linux usa comunque
  la GTT dinamicamente per VAAPI/Vulkan, quindi la transcodifica resta.
- **Occupazione attuale:** ~3,0 GiB usati dai container esistenti, ~10 GiB
  disponibili · swap 4 GiB mai toccato
- **Upgrade a costo zero:** 2 × 16 GB DDR5-4800 attualmente sul Victus
  - **Rinviato** (2026-09-28): già in dual channel, lo swap darebbe solo
    capacità. Da fare con l'eventuale AI locale, in quell'occasione anche
    UMA Frame Buffer → 512 MB.

## Storage

| Device | Tipo | Capacità | Interfaccia | Stato |
|---|---|---|---|---|
| `nvme0n1` | Lexar NM790 | **1 TB** (953,9 G) | PCIe **Gen4 x4** | installato, disco di sistema |
| 2.5" bay | — | — | SATA 3.0 (max 2 TB) | **LIBERO** |
| M.2 2230 | Wi-Fi + BT | — | — | occupato dalla scheda wireless |

- **Nessun secondo slot M.2**: l'unico alloggiamento libero è **2.5" SATA**.
- **Salute NVMe: ottima** — `SMART overall-health: PASSED`, **Percentage Used 0%**,
  159 GB scritti, 31 ore accese, 31 °C.
- **Partizionamento** — la trappola LVM di Ubuntu **non** si è verificata:

  | Partizione | Dim. | FS | Mount |
  |---|---|---|---|
  | `nvme0n1p1` | 1 G | vfat | `/boot/efi` |
  | `nvme0n1p2` | 2 G | ext4 | `/boot` |
  | `nvme0n1p3` | 950,8 G | LVM2 → `ubuntu-vg/ubuntu-lv` ext4 | `/` |

  - `VG ubuntu-vg: VFree = 0` → **tutto il TB è allocato al root**
  - Quindi `/` ha **935 G, 67 G usati, 821 G liberi (8%)**
  - Rovescio: **VFree 0 = nessuno spazio per snapshot LVM.** Irrilevante con
    `restic`, ma da sapere se un giorno servissero.
- **Dischi a magazzino:** 1 × HDD 500 GB, 1 × HDD 750 GB, 2.5" **da 7 mm**
  (compatibili col bay) — **[DA VERIFICARE]** SMART, non ancora collegati
- **[DA VERIFICARE]** presenza di **cavo/staffa SATA** nel coperchio inferiore

## Sistema

- **OS:** **Ubuntu Server 24.04.4 LTS** (Noble Numbat), kernel **6.8.0-139-generic**
- **Filesystem root:** ext4 su LVM
- **Docker:** **29.6.1** già installato · `paolo` nel gruppo `docker` (GID 988)
- **Gruppo `vault`** presente (GID 1001)
- **82 pacchetti aggiornabili** al 2026-09-28
- **Repo apt aggiunti:** Docker, NodeSource (node 24.x), Tailscale

### Container già attivi

| Container | Porte | Esposizione |
|---|---|---|
| `infra-caddy-1` (caddy:2) | `*:80`, `*:443` | tutte le interfacce — è il reverse proxy |
| `anime-monitor-anime-monitor-1` | `127.0.0.1:3089` | solo loopback |
| `yt-analizer-yt-frontend-1` | `127.0.0.1:5199` | solo loopback |
| `yt-analizer-yt-backend-1` | `127.0.0.1:8099` | solo loopback |
| `transcribe-web-1` | `0.0.0.0:8000` | **tutte le interfacce** — vedi § Rischi |

- Altri listener: `sshd` su 22, `systemd-resolve` su 53 (loopback)
- **Porta 2283 (Immich) libera**, nessun conflitto previsto

### Rete

- **Tailscale 1.102.2 installato ma `tailscaled` NON in esecuzione**
  → blocca l'intero piano di accesso, vedi § Prossimi passi
- **[DA VERIFICARE]** IP LAN statico, IP tailnet (dopo il riavvio del daemon)

---

## Capacità derivate

- **Servizi cloud richiesti:** sovradimensionata. 8C/16T, 821 GB liberi e 10 GiB
  di RAM disponibile, per 2 utenti foto e 20-30 GB di bulk iniziale.
- **Immich:** import iniziale con ML (CLIP + volti) su 16 thread → ore, non
  giorni. Transcodifica accelerata dalla 680M via VAAPI (`renderD128` presente).
- **Reverse proxy già presente** (Caddy in `infra-caddy-1`): i nuovi servizi si
  appendono alla configurazione esistente, niente da installare.
- **AI locale** — la banda è già piena (~77 GB/s teorici, ~55-65 reali); i 32 GB
  servirebbero per **capienza**, non per velocità:
  - denso 8B q4 (~5 GB) → ~10-12 tok/s — **entra già** nei 10 GiB disponibili
  - denso 14B q4 (~9 GB) → ~6-7 tok/s — al limite, con Immich acceso non ci sta
  - **MoE ~30B / ~3B attivi** q4 (~18-20 GB) → 20+ tok/s, **impossibile oggi**
    (13 GiB visibili, 3 già occupati): è l'unico scenario che giustifica lo swap
  - prompt processing: lento su CPU, migliorabile col backend **Vulkan** sulla
    680M (ROCm su gfx1035 non è ufficialmente supportato)

## Decisioni prese (2026-09-28)

1. **Documenti: niente editing online** → stack leggero dietro il Caddy
   esistente, niente Nextcloud/PHP/Collabora.
   - ⚠️ **Rivista il 2026-09-30.** Nata come «sola lettura/download» e attuata
     con un bind mount `:ro`, che impediva anche solo di creare una cartella
     dal browser. Il mount è ora in scrittura (gruppo `vault` + setgid, vedi
     `gjarper-servizi.md`): resta scartata la *suite di editing*, non la
     gestione dei file. Quel `:ro` non era il livello di protezione dei dati —
     quello è il backup, tuttora aperto al punto 7.
   - ⚠️ **FileBrowser originale archiviato il 2026-08-31**: non usarlo.
     Si usa il fork mantenuto **FileBrowser Quantum**
     (`ghcr.io/gtsteffaniak/filebrowser`, tag `stable` = v1.5.x, `beta` = v2.0.x).
   - **Samba rinviata**, poi rivalutata il 2026-09-30: la `2.0.9-beta` **non ha
     WebDAV** (verificato), quindi non esiste un modo di montare i documenti né
     su Windows né da un'app Android. Samba diventa la candidata principale.
     Dettagli in `gjarper-servizi.md`.
2. **Foto: Immich**, 2 utenti (uno poco attivo), bulk iniziale 20-30 GB.
3. **Nessun acquisto di dischi:** 821 GB liberi sull'NVMe bastano per anni.
4. **Accesso: solo Tailscale.** Niente esposizione pubblica, niente dominio.
5. **HDD vecchi → backup**, non storage primario.
6. **Upgrade RAM rinviato**: già in dual channel. Si farà con l'AI locale,
   assieme all'abbassamento dell'UMA Frame Buffer a 512 MB.
7. **HDD e strategia di backup rinviati** (2026-09-28): si procede prima con i
   servizi. ⚠️ Da riprendere **prima del bulk import delle foto**, che è il
   momento in cui i dati diventano insostituibili.
8. **Tailscale riattivato** il 2026-09-28: `tailscaled` abilitato, nodo
   riautenticato, IP tailnet ottenuto.

## Rischi noti

- **Single point of failure:** tutto su un solo NVMe, nessuna redundancy. Il
  disco è nuovo e sano (0% di usura), ma il backup non è opzionale.
- **`transcribe-web-1` è in ascolto su `0.0.0.0:8000`**, quindi raggiungibile da
  tutta la LAN, a differenza degli altri container che stanno su loopback dietro
  Caddy. Da uniformare a `127.0.0.1:8000` se non è intenzionale.
- **Nessun UPS:** PostgreSQL (Immich) + blackout è il modo classico di scoprire
  che i backup non funzionavano. ~40-50 €.
- **HDD di recupero:** età reale ignota. Ok come copia ridondante, mai come unica.
- **82 pacchetti aggiornabili** e `unattended-upgrades` non verificato.
- **Calore:** margine ampio (Tctl 41,8 °C a riposo), un HDD nel bay non preoccupa.

## Stato implementazione

Spostato in **`00_inbox/gjarper-servizi.md`**: architettura di accesso, tabella
degli URL, configurazione di Caddy, FileBrowser Quantum e Immich, procedure
operative e punti aperti. Qui resta solo l'hardware.

Riferimenti rapidi: tailnet `100.76.226.98`, MagicDNS `gjarper.tail6cb7a3.ts.net`.

## Prossimi passi / verifiche aperte

1. **Riattivare Tailscale** — precondizione di tutto il resto:
   `sudo systemctl enable --now tailscaled && sudo tailscale up`
2. **Confermare VAAPI:** `vainfo --display drm --device /dev/dri/renderD128`
   (cercare `VAProfileH264*` e `VAProfileHEVC*` fra encode e decode)
3. **SMART dei 2 HDD**, da collegare via USB uno alla volta
4. **Ispezione fisica:** cavo/staffa SATA nel coperchio inferiore?
