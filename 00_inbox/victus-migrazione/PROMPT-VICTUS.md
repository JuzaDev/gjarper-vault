# Prompt da incollare in Claude Code sul Victus

> Tutto quello che sta sotto la riga è il messaggio da incollare come **primo
> messaggio** di una sessione nuova sul portatile. È autosufficiente: non serve
> aver già clonato niente.

---

Sei la mia sessione di lavoro su questo portatile, un **HP Victus 16-d1007sl**
(i7-12700H, 16 GB DDR5, SSD 512 GB, RTX 3060 6 GB, Windows 11) che sto per
svuotare e dismettere. Non conosci il contesto: te lo do qui sotto per intero.

## Come voglio che lavori

Questa è una **sessione di studio**, non un'esecuzione a testa bassa. Voglio
capire cosa succede sul mio disco, non solo vedere dei numeri alla fine.

Quindi, per ogni passo:

1. **Spiega prima di eseguire.** Cosa stai per lanciare, cosa si aspetta di
   trovare, e cosa cambierebbe nel piano se trovasse qualcosa di diverso.
2. **Un passo alla volta.** Aspetta il mio ok prima di passare al successivo.
   Non incatenare cinque comandi per portarti avanti.
3. **Commenta l'output.** Non incollarmelo e basta: dimmi cosa significa e se è
   quello che ti aspettavi. Se un numero è sorprendente, dillo.
4. **Se qualcosa non torna, fermati e chiedi.** Preferisco una domanda in più
   che un'assunzione sbagliata su dove stanno i miei file.
5. Parlami in italiano. I comandi che mi passi da eseguire a mano devono essere
   in sintassi **bash** (uso Git Bash), non PowerShell.

## Vincoli non negoziabili

- **Non spostare, non copiare, non rinominare, non cancellare nessun file** di
  questo disco. Nemmeno "per provare", nemmeno in una cartella temporanea.
  Questa fase produce solo file CSV in `C:\migrazione`.
- Gli script che userai **non toccano i file**: leggono e basta. Se li modifichi
  per correggere un errore, quel principio resta.
- **Non installare niente senza chiedermelo.** Dimmi il comando, lo lancio io.
- **Nessun `git commit` e nessun `git push`**, mai, di tua iniziativa.
- Non leggere `.env`, `config.py`, né niente dentro `~/.ssh/`.

## Il contesto

Ho un server di casa, **gjarper** (Minisforum UM773 Lite, Ubuntu Server 24.04,
NVMe da 1 TB con **821 GB liberi**), dove sto montando due servizi: un cloud
documenti in sola lettura e **Immich** per le foto. L'accesso è solo via
Tailscale, niente esposizione pubblica.

Su questo portatile ho anni di documenti e foto sparsi ovunque e non ho nessuna
intenzione di cercarli a mano.

**Il principio che regge tutto il piano:** questo disco è da 512 GB, su gjarper
ce ne sono 821 liberi. Ci sta tutto. Quindi la migrazione **non è una
selezione**: si copia tutto e si smista dopo, sulla copia. Niente e nessuno —
nessuno script, nessun modello — decide cosa sopravvive. Il fallimento tipico di
un triage automatico non è il falso positivo (mi porto dietro spazzatura,
pazienza), è il **falso negativo silenzioso**: il documento che serviva, marcato
irrilevante, che non riguarderò mai più. Se non si cancella niente, quel
fallimento non esiste.

Il piano completo è in 4 fasi. **Oggi facciamo la 0, la 1 e la 2.**

- **Fase 0** — verifiche preliminari (sotto).
- **Fase 1** — censimento del disco: cosa c'è e dov'è. Nessun modello.
- **Fase 2** — smistamento deterministico: foto vere contro screenshot,
  documenti per zona di provenienza. Ancora nessun modello.
- **Fase 3** (un'altra volta) — un modello locale sulla 3060 che cataloga solo
  il residuo ambiguo dei documenti. Non oggi: il prompt della fase 3 si scrive
  sui numeri che escono oggi.

---

# FASE 0 — Preliminari

Sei tu a guidarmi. Ognuno di questi punti può cambiare il piano, quindi
spiegami cosa cerchi prima di cercarlo.

### 0.1 — Portare qui gli script

Servono tre file: `01_inventory.py`, `02_triage.py`, `README.md`. Stanno nel mio
vault su GitHub, in `00_inbox/victus-migrazione/`:

```bash
git clone --depth 1 https://github.com/JuzaDev/gjarper-vault.git /c/migrazione-src &&
mkdir -p /c/migrazione &&
cp /c/migrazione-src/00_inbox/victus-migrazione/* /c/migrazione/
```

Se il clone chiede credenziali o fallisce, **fermati e dimmelo**: li porto a
mano con una chiavetta, non è un problema.

`C:\migrazione` sta **fuori** da `C:\Users\paolo` di proposito, così i CSV che
produciamo non finiscono dentro l'albero che stiamo scansionando. Spiegami
perché conta prima di procedere — voglio verificare che abbiamo capito la
stessa cosa.

Poi leggi `C:\migrazione\README.md` e dimmi con parole tue cosa fanno i due
script, così so che stiamo lavorando sulla stessa idea.

### 0.2 — Python

Serve Python 3.9 o superiore. Gli script usano **solo la libreria standard**:
nessun `pip install`, nessun ambiente virtuale.

```bash
python --version
```

Se manca, il comando è `winget install -e --id Python.Python.3.12` e poi riapro
il terminale — ma lo lancio io, non tu.

### 0.3 — Chi altro abita questo disco

```bash
ls /c/Users/
```

Se ci sono altri profili utente oltre a `paolo` (vecchi account, un profilo
`Administrator`, il nome di qualcun altro), dimmelo: potrebbero avere roba mia
dentro, e il censimento va allargato.

### 0.4 — Quanti dischi e quante partizioni

Guarda se oltre a `C:` c'è altro: una partizione dati, un disco secondario, una
chiavetta o un disco esterno collegato adesso.

Se c'è un `D:` con dentro roba mia, va censito anche quello — gli script
accettano più cartelle di partenza in un colpo solo.

### 0.5 — OneDrive: il punto che può mordere

**Questo è il controllo più importante della fase 0.** Verifica se OneDrive su
questa macchina è in modalità **"File su richiesta"** (*Files On-Demand*).

Se lo è, nella cartella OneDrive ci sono **segnaposto** da pochi KB invece dei
file veri. Il problema: il censimento li legge — per calcolare l'hash dei
duplicati e per leggere l'EXIF delle foto — e **leggere un segnaposto lo scarica
da internet**. Con qualche decina di GB in cloud significa ore di banda e un
disco che si riempie a sorpresa mentre non guardo.

Come capirlo: nella cartella OneDrive i file hanno un'icona a nuvola (solo
cloud), una spunta grigia (disponibile ma liberabile) o una spunta verde piena
(sempre su questo dispositivo). Guarda anche se la dimensione su disco della
cartella è molto minore di quella dichiarata.

**Se sono segnaposto, fermati e dimmelo.** La risposta *non* è escludere
OneDrive — quei file mi servono comunque. Le opzioni sono due e le valuto io:
idratarli in blocco prima (tasto destro sulla cartella → *Mantieni sempre su
questo dispositivo*), oppure scaricarli direttamente su gjarper per un'altra
strada e tenerli fuori da questo giro. Dimmi quanto spazio servirebbe nel primo
caso.

### 0.6 — Salute del disco

```bash
wmic diskdrive get model,status,size
```

Se lo stato non è `OK` cambia l'urgenza di tutto il piano: si copia prima e si
ragiona dopo. Se hai un modo migliore di leggere lo SMART su Windows senza
installare niente, proponimelo.

### 0.7 — Le miniere nascoste

Prima di lanciare il censimento, controlla se esistono questi posti, che sono i
classici serbatoi dimenticati di una macchina vecchia:

- `C:\Windows.old` — residuo di un aggiornamento o di una migrazione da un PC
  precedente. Può contenere un profilo utente intero.
- Cartelle tipo `Backup`, `Vecchio PC`, `Roba da sistemare`, `Da ordinare` in
  giro per il disco o sul Desktop.
- File `.pst` / `.ost` fuori dalle posizioni standard di Outlook — sono archivi
  di posta con anni di allegati dentro.
- Immagini disco o backup: `.vhd`, `.vhdx`, `.wim`, `.iso` di grosse dimensioni.

Dimmi cosa trovi. Alcune di queste vanno aggiunte come cartelle di partenza
della fase 1, altre sono da gestire a parte.

### 0.8 — Chiudi la fase 0

Prima di lanciare qualsiasi cosa, fammi un riepilogo: quali cartelle di partenza
useremo, cosa abbiamo deciso su OneDrive, e se c'è qualcosa che ti preoccupa.
Poi aspetta il mio ok.

---

# FASE 1 — Censimento

```bash
cd /c/migrazione && python 01_inventory.py 'C:/Users/paolo' -o inventory.csv
```

(più le eventuali altre cartelle emerse dalla fase 0, come argomenti in più)

**Cosa fa.** Cammina su tutto l'albero, salta sistema, applicazioni e cache,
classifica ogni file per estensione, e trova i duplicati per contenuto. Il
dedup funziona in due passate: prima un hash parziale (dimensione + primi e
ultimi 64 KB), poi l'hash completo solo sui gruppi ancora in collisione — così
non si legge mezzo disco per niente. Scrive `inventory.csv` e stampa un
riepilogo.

**Un dettaglio che vale la pena capire:** dentro `AppData` lo script non scende,
tranne che nei rami `Microsoft\Outlook` e `Thunderbird`. Chiedimi perché, o
dimmelo tu se l'hai già capito leggendo il README.

**Cosa guardare nell'output:**

- Quanti file, quanto spazio, divisi per tipo.
- Quanti duplicati e quanto spazio occupano — di solito è tanto, ed è la prima
  cosa che fa scendere i numeri.
- La classifica delle cartelle più pesanti: è lì che di solito si scopre "ah,
  quella roba stava lì".

Su un SSD da 512 GB sono minuti, non ore. Se sembra bloccato, aspetta: stampa
un avanzamento ogni 25.000 file.

Commentami i numeri prima di andare avanti.

---

# FASE 2 — Smistamento deterministico

```bash
cd /c/migrazione && python 02_triage.py inventory.csv
```

**Cosa fa.** Produce `foto.csv`, `documenti.csv` e `report.md`.

Il criterio forte sulle foto è l'**EXIF**: se un file ha i campi `Make` e
`Model`, quello scatto viene da un telefono o da una macchina fotografica,
quindi è roba mia. Screenshot, immagini scaricate dal web e asset di
applicazioni non ce l'hanno. Lo script si porta dentro un parser EXIF minimale,
senza dipendenze.

Ogni riga esce marcata `porta`, `rivedi` o `scarta`. **Sono colonne di un CSV,
non azioni**: nessun file viene toccato.

**Cosa guardare:**

- Quante foto finiscono in `fotocamera` (alta confidenza) contro quante in
  `rivedi`. Se le `rivedi` sono tantissime, la regola va tarata meglio.
- Quanti documenti restano dopo aver tolto i duplicati, e come si distribuiscono
  per zona (documenti, desktop, download, onedrive, posta).
- Se qualche numero è assurdo — zero foto, o 40.000 documenti in `download` —
  probabilmente è un bug o un'esclusione sbagliata, non la realtà. Dimmelo.

Per le foto qui finisce: Immich rifà il dedup all'import, ricava le date,
riconosce i volti e indicizza con CLIP. Non serve un secondo modello che guardi
i pixel.

---

# Chiusura della sessione

Scrivimi un riepilogo che possa portare via da qui e usare per preparare la
fase 3:

1. Cartelle di partenza effettivamente censite.
2. Totale file e spazio, divisi per tipo.
3. Duplicati: quanti file ridondanti, quanto spazio.
4. Foto: quante `porta`, quante `rivedi`, quante `scarta`.
5. Documenti: quanti in totale e quanti in `rivedi` — **è questo il numero che
   dimensiona la fase 3**, perché è su quel residuo che accenderemo il modello
   sulla 3060.
6. Estensioni dei documenti in `rivedi`, con i conteggi: quanti PDF, quanti
   `.docx`, quanti `.txt`. Serve a sapere se servirà l'OCR e quanto peserà.
7. Quante scansioni sospette: PDF o immagini che probabilmente contengono testo
   fotografato invece che testo digitale, se riesci a stimarlo.
8. Sorprese, anomalie e cose che secondo te ho dimenticato.

Non cancellare i CSV: restano in `C:\migrazione` e servono alla prossima fase.

## Cosa NON facciamo oggi

Non copiamo ancora niente su gjarper. Prima va sistemato il backup del server —
finché le foto stanno anche su questo portatile, gjarper è una copia; appena
formatto il Victus, un solo NVMe senza ridondanza e senza UPS diventa l'unica
casa di foto di famiglia. E non smontiamo la RAM di questo portatile: serve,
insieme alla 3060, per la fase 3.
