"""Scambio dell'archivio con Supabase (progetto «atelier»), tramite la funzione edge
osservatorio-archivio. La chiave sta nella variabile OSSERVATORIO_CHIAVE o nel file .chiave.

python3 archivio.py scarica   → dati/osservatorio.sqlite (se in cloud non c'è ancora, non fa nulla)
python3 archivio.py carica    → salva l'archivio e pubblica sito/dati.js per il pannello
"""
import gzip
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

QUI = Path(__file__).resolve().parent
DB = QUI / "dati" / "osservatorio.sqlite"
DATI = QUI / "sito" / "dati.js"
FUNZIONE = "https://dpnafvyugzqqwicvenwp.supabase.co/functions/v1/osservatorio-archivio"
PUBBLICO = "https://dpnafvyugzqqwicvenwp.supabase.co/storage/v1/object/public/osservatorio-pannello/dati.js"


def chiave():
    k = os.environ.get("OSSERVATORIO_CHIAVE") or (QUI / ".chiave").read_text()
    return k.strip()


def chiama(metodo, f, corpo=None):
    req = urllib.request.Request(f"{FUNZIONE}?f={f}", data=corpo, method=metodo,
                                 headers={"x-chiave": chiave(), "Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def scarica():
    try:
        dati = chiama("GET", "db")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("archivio in cloud ancora vuoto: si parte da quello locale")
            return
        raise
    DB.parent.mkdir(exist_ok=True)
    DB.write_bytes(gzip.decompress(dati))
    print(f"archivio scaricato: {DB.stat().st_size // 1024} KB")


def carica():
    import sqlite3
    sqlite3.connect(DB).execute("PRAGMA wal_checkpoint(TRUNCATE)").connection.close()
    gz = gzip.compress(DB.read_bytes(), 6)
    print("archivio:", chiama("PUT", "db", gz).decode(), "byte")
    if DATI.exists():
        print("pannello:", chiama("PUT", "dati", DATI.read_bytes()).decode(), "byte")


if __name__ == "__main__":
    {"scarica": scarica, "carica": carica}[sys.argv[1]]()
