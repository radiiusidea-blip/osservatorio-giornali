#!/bin/zsh
# I giri ogni 15 minuti girano su GitHub (repository osservatorio-giornali), anche a Mac spento.
# Questo comando ne lancia uno subito, fuori programma.
cd "${0:A:h}"
gh workflow run raccolta.yml && echo "Giro avviato: il pannello si aggiorna entro un paio di minuti."
