# Vault pubblico — memoria di progetto per Claude Code

Questo è il **vault pubblico** dell'assistente personale su gjarper. Regole
vincolanti (master §1/§4/§10): leggile prima di operare.

## Confini (NON negoziabili)
- **`private/` non esiste per te.** Non leggerla, non scriverla, non nominarla nei
  prompt. È fuori dai tuoi permessi (Unix 700 + deny rules in `.claude/settings.json`),
  e le deny valgono in **ogni** modalità, anche bypassPermissions.
- **Non cancellare mai.** Un task fatto o una nota superata si **spostano** in
  `archivio/` (o `30_tasks/archivio/`), non si eliminano.
- **Ogni scrittura automatica è un commit atomico reversibile** su path in allowlist
  (`00_inbox/`, `30_tasks/`). Niente modifiche a `10_lavoro/`/`20_personale/` senza
  che sia una richiesta esplicita.

## Struttura delle zone
```
00_inbox/            capture grezze da smistare (coda del worker)
  da-smistare/       materiale importato in blocco, ancora da classificare
10_lavoro/{clienti,rnd}/
20_personale/{famiglia,burocrazia,riferimenti}/
  riferimenti/       MANIFEST: note-puntatore a contenuti sensibili (vedi sotto)
30_tasks/{lavoro.md,personale.md,archivio/}
_meta/               tassonomia, template, intents, master.md
```

## Formato task (Obsidian Tasks)
Solo task **aperti** con `- [ ]`. Esempio:
```
- [ ] Rinnovare SPID 📅 2026-11-30 ⏫ #burocrazia
```
- `📅 YYYY-MM-DD` scadenza · `⏳ YYYY-MM-DD` pianificato
- `⏫` alta · `🔼` media · `🔽` bassa
- Tag gerarchici: `#cliente/acme`, `#famiglia/salute`, `#rnd`, `#burocrazia`
Lo script `agenda` parserizza questo formato: non deviare dalla sintassi.

## Tassonomia
Fonte di verità dei tag ammessi: `_meta/tassonomia.md`. Usa quelli; se ne serve uno
nuovo, aggiungilo lì prima di usarlo.

## Pattern manifest (contenuti sensibili)
Il payload sensibile vive in `private/` (che non vedi) o nel password manager. In
`20_personale/riferimenti/` c'è una **nota-puntatore** (frontmatter `tipo: puntatore`)
che dice *cosa esiste* e *dove*, senza il dato. Così puoi rispondere "quando scade lo
SPID / dove sono i codici" senza aver mai letto i codici. Modello:
`_meta/template-puntatore.md`.

## Smistamento dell'inbox (quando richiesto)
Classifica l'item, estrai eventuali task nel formato standard, archivia nella cartella
giusta di `10_lavoro/`/`20_personale/`. Se qualcosa è sensibile: **non** portarlo in
`private/` (non puoi) — crea invece una nota-puntatore in `riferimenti/` e segnala che
il payload va messo a mano da Paolo.
