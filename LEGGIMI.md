# Osservatorio Giornali

Monitora le homepage di 25 testate nazionali ogni 15 minuti e produce un pannello con:
prima fila adesso · rapporto del giorno · interazioni · modelli informativi · cadute.

- Pannello: apri `sito/index.html` (si ricarica da solo ogni 5 minuti)
- Giro a mano: `./aggiorna.sh`
- Automatico: launchd `com.radiius.osservatorio-giornali` (ogni 900 s, il Mac deve essere acceso)
  - fermare: `launchctl unload ~/Library/LaunchAgents/com.radiius.osservatorio-giornali.plist`
- Registro: `dati/registro.log` · Database: `dati/osservatorio.sqlite`

File: `testate.py` (elenco) · `estrattore.py` (lettura homepage) · `categorie.py` ·
`raccogli.py` (un giro) · `analisi.py` (notizie, rapporti, modelli, cadute → sito/dati.js).
Solo Python di sistema, nessuna libreria da installare.
