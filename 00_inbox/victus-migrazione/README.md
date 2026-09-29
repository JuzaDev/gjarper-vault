---
tipo: nota
zona: pubblica
tag: [rnd]
aggiornata: 2026-09-29
stato: fasi 1-2 pronte e testate · fase 3 (modello locale) da scrivere
---

# Victus → gjarper: svuotare il vecchio portatile

Obiettivo: portare documenti e foto personali dall'HP Victus (512 GB, Windows)
dentro i servizi di gjarper, senza cercare a mano e **senza rischiare di perdere
qualcosa nella selezione**.

## Il principio

Il Victus ha 512 GB di SSD, gjarper ne ha **821 liberi**. Ci sta tutto. Quindi la
migrazione **non è una selezione**: si copia tutto grezzo, e solo dopo si smista
sulla copia. Il modello locale non decide cosa sopravvive — produce un catalogo
che rivedi tu. Il fallimento tipico di un triage automatico non è il falso
positivo (ti porti dietro spazzatura, pazienza), è il **falso negativo
silenzioso**: il documento che serviva, marcato irrilevante, che non riguarderai
mai più. Se non si cancella niente, quel fallimento non esiste.

## Ordine delle operazioni

Conta, e non è l'ordine comodo:

1. **Backup di gjarper prima del bulk import** — decisione #7 di
   `gjarper-hardware.md`, rimandata al «momento in cui i dati diventano
   insostituibili». È questo. Finché le foto stanno anche sul Victus, gjarper è
   una copia; appena formatti il portatile, un solo NVMe senza ridondanza e
   senza UPS diventa l'unica casa di foto di famiglia. Gli HDD 500/750 GB con
   `restic` vanno collegati **prima**.
2. **Fasi 1-2-3 sul Victus** (sotto).
3. **Copia e import** su gjarper.
4. **Solo alla fine**: cannibalizzare il portatile. La decisione #6 prevede di
   spostare i 2 × 16 GB del Victus su gjarper — ma la 3060 e quella RAM servono
   per la fase 3. Prima si svuota, poi si smonta.

## Fase 1 — censimento (nessun modello)

```bash
python 01_inventory.py 'C:/Users/paolo' -o inventory.csv
```

Cammina sul disco, salta sistema/applicazioni/cache, classifica per estensione e
trova i duplicati per contenuto (hash parziale → hash completo solo sui gruppi
ancora in collisione, come fa `fclones`). Non sposta e non cancella: scrive
`inventory.csv` e stampa un riepilogo con le cartelle più pesanti.

Solo stdlib, Python 3.9+. Su 512 GB sono minuti, non ore.

Cosa salta e cosa no: esclude `Windows`, `Program Files`, `ProgramData`, cache,
`node_modules`, `venv`, `steamapps`. **Dentro `AppData` non scende, tranne** in
`Microsoft\Outlook` e `Thunderbird`: i `.pst`/`.ost` sono archivi di posta con
anni di allegati dentro, ed è il posto che non troveresti mai cercando
"documenti". Altri dischi/partizioni: passali come argomenti in più.

## Fase 2 — smistamento deterministico (ancora nessun modello)

```bash
python 02_triage.py inventory.csv
```

Produce `foto.csv`, `documenti.csv`, `report.md`.

Il criterio forte sulle foto è l'**EXIF**: se c'è `Make`/`Model`, lo scatto viene
da un telefono o da una macchina fotografica — è roba tua. Screenshot, immagini
scaricate e asset di applicazioni non ce l'hanno. Parser EXIF minimale incluso
nello script, nessuna dipendenza (testato: riconosce realme 9 e Galaxy S24 con
data di scatto). Ogni riga finisce in `porta` / `rivedi` / `scarta`, ma nessun
file viene toccato: le colonne sono una proposta.

**Per le foto qui finisce.** Immich rifà il dedup all'import, ricava le date,
riconosce i volti e indicizza con CLIP: l'AI per le foto è già nel piano, non
serve un secondo modello che guardi i pixel.

## Fase 3 — catalogo con modello locale (da scrivere)

Solo sul residuo `rivedi` dei documenti — qualche migliaio di file, non il disco.
Per ognuno: estrazione delle prime 1-2 pagine di testo → il modello restituisce
categoria (fattura / contratto / documento d'identità / lavoro / manuale
scaricato), titolo leggibile, anno. Output in CSV che rivedi tu; gli spostamenti
li fa uno script **dopo** la revisione.

Due vincoli tecnici:

- **OCR prima.** Buona parte dei documenti personali sono scansioni o foto di
  fogli. Senza `tesseract` + pacchetto `ita` il modello riceve una pagina vuota
  e la riempie di invenzioni.
- **Sulla 3060, 6 GB.** Un 8B q4 (~5 GB) entra con contesto 4-8k, sufficiente per
  due pagine. A ~3-5 s/documento, 3000 documenti sono una notte. È l'unica GPU
  in casa: gjarper ha solo la 680M e nessun AVX-512, e il prompt processing su
  1000 token a documento è esattamente ciò che la sua CPU fa male.

La scrivo quando i numeri della fase 2 dicono quanti file sono e in che formati.

## Aperto

- Il Victus si avvia ancora normalmente?
- La prima copia va su un HDD esterno o direttamente in rete verso gjarper?
- SMART dei due HDD 2.5" di recupero (già aperto in `gjarper-hardware.md`).
