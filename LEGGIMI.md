# Osservatorio Giornali

Monitora le homepage di 25 testate nazionali ogni 15 minuti e produce un pannello con:
prima fila adesso · rapporto del giorno · interazioni · modelli informativi · cadute.

## Dove gira
- **Motore**: GitHub Actions, repository pubblico `radiiusidea-blip/osservatorio-giornali`,
  workflow `Raccolta` ai minuti 4/19/34/49 di ogni ora. Non dipende dal Mac.
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
