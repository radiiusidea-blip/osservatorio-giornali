# Osservatorio Giornali

Monitora le homepage di 25 testate nazionali ogni 15 minuti e produce un pannello con:
prima fila adesso · rapporto del giorno · interazioni · modelli informativi · cadute.

## Dove gira
- **Motore**: GitHub Actions, repository pubblico `radiiusidea-blip/osservatorio-giornali`,
  workflow `Raccolta`. Non dipende dal Mac.
- **Orologio**: pg_cron su Supabase «atelier» (job `osservatorio-giornali`, minuti 4/19/34/49)
  chiama `orologio.avvia_osservatorio()`, che avvia il workflow con il token del Vault
  `github_osservatorio` (fine-grained, solo Actions di questo repository). L'orologio di GitHub,
  inaffidabile, resta come riserva; i giri a meno di 8 minuti dal precedente vengono saltati.
  Quando il token scade: crearne uno nuovo e sostituire il segreto nel Vault.
- **Archivio tra un giro e l'altro**: cache di GitHub; Supabase ne tiene la copia di sicurezza.
- **Archivio**: Supabase progetto «atelier», bucket privato `osservatorio-archivio`
  (osservatorio.sqlite.gz), accesso solo tramite la funzione edge `osservatorio-archivio`
  con la chiave segreta (file `.chiave` qui, secret `OSSERVATORIO_CHIAVE` su GitHub).
- **Pannello**: `sito/index.html` legge `dati.js` dal bucket pubblico `osservatorio-pannello`
  (se il cloud non risponde usa la copia locale). Avvisa se l'ultima lettura ha più di 45 minuti.

## Comandi
- Giro subito, fuori programma: `./aggiorna.sh`
- Copia locale dell'archivio: `python3 archivio.py scarica` (poi `python3 analisi.py`)
- Stato dei giri: `gh run list --repo radiiusidea-blip/osservatorio-giornali`

Non far girare raccogli.py in locale e poi `archivio.py carica`: sovrascriveresti i giri fatti in cloud nel frattempo.

File: `testate.py` (elenco) · `estrattore.py` (lettura homepage) · `categorie.py` ·
`raccogli.py` (un giro) · `analisi.py` (notizie, rapporti, modelli, cadute → sito/dati.js) · `archivio.py`.
Solo Python standard, nessuna libreria da installare.
