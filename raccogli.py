"""Un giro di raccolta: legge tutte le testate e Google Trends, salva nel database.

Uso: python3 raccogli.py
Gira da solo ogni 15 minuti (vedi aggiorna.sh e il servizio launchd).
"""
import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import json
import re
import sqlite3
import ssl
import subprocess
import time
import urllib.request
from pathlib import Path

from categorie import categoria_di
from estrattore import estrai, estrai_rss
from testate import TESTATE

QUI = Path(__file__).resolve().parent
DB = QUI / "dati" / "osservatorio.sqlite"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
TRENDS = "https://trends.google.com/trending/rss?geo=IT"
TIENI = 40   # posizioni salvate per testata a ogni giro

SCHEMA = """
CREATE TABLE IF NOT EXISTS giri(id INTEGER PRIMARY KEY, ts INTEGER, quando TEXT);
CREATE TABLE IF NOT EXISTS letture(giro INTEGER, testata TEXT, ok INTEGER, n INTEGER,
    firma TEXT, cambiata INTEGER, errore TEXT, PRIMARY KEY(giro, testata));
-- una riga per ogni tratto in cui un titolo resta allo stesso rango (dal giro .. al giro):
-- le homepage cambiano poco fra un giro e l'altro, così l'archivio resta piccolo
CREATE TABLE IF NOT EXISTS posizioni(testata TEXT, url TEXT, rango INTEGER, pos INTEGER,
    peso REAL, evidenza REAL, dal INTEGER, al INTEGER);
CREATE INDEX IF NOT EXISTS posizioni_al ON posizioni(testata, al);
CREATE TABLE IF NOT EXISTS articoli(url TEXT PRIMARY KEY, testata TEXT, titolo TEXT,
    categoria TEXT, prima INTEGER, ultima INTEGER, notizia INTEGER);
CREATE INDEX IF NOT EXISTS articoli_notizia ON articoli(notizia);
CREATE TABLE IF NOT EXISTS piu_letti(giro INTEGER, testata TEXT, url TEXT, pos INTEGER);
CREATE INDEX IF NOT EXISTS letti_giro ON piu_letti(giro);
CREATE TABLE IF NOT EXISTS trends(giro INTEGER, termine TEXT, traffico INTEGER, titoli TEXT);
CREATE TABLE IF NOT EXISTS notizie(id INTEGER PRIMARY KEY, etichetta TEXT, categoria TEXT,
    prima INTEGER, ultima INTEGER);
"""


def scarica(url, timeout=25):
    """urllib e, se il certificato del sito non piace a Python, curl di sistema."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9", "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
            b = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                b = gzip.decompress(b)
            return b.decode(r.headers.get_content_charset() or "utf-8", "replace")
    except (ssl.SSLError, urllib.error.URLError) as e:
        if "CERTIFICATE" not in str(e):
            raise
        out = subprocess.run(["curl", "-sL", "--compressed", "-A", UA, "--max-time", str(timeout), url],
                             capture_output=True, check=True)
        return out.stdout.decode("utf-8", "replace")


def leggi_testata(t, oggi):
    if t.get("fonte") == "rss":
        voci, letti = estrai_rss(scarica(t["rss"]))
    else:
        voci, letti = estrai(scarica(t["url"]), t["url"], declassa=t.get("declassa"), oggi=oggi)
    # evidenza: peso grafico smorzato dalla posizione; il rango ordina per evidenza
    for v in voci:
        v["evidenza"] = round(v["peso"] / (1 + (v["pos"] - 1) / 6), 3)
    if t.get("fonte") == "rss":
        for v in voci:
            v["rango"] = v["pos"]
    else:
        for i, v in enumerate(sorted(voci, key=lambda x: -x["evidenza"]), 1):
            v["rango"] = i
    return voci, letti


def leggi_trends():
    xml = scarica(TRENDS)
    out = []
    for item in re.findall(r"<item>.*?</item>", xml, re.S):
        termine = re.search(r"<title>(.*?)</title>", item, re.S)
        traffico = re.search(r"<ht:approx_traffic>([\d,.]+)", item)
        titoli = re.findall(r"<ht:news_item_title>(.*?)</ht:news_item_title>", item, re.S)
        if termine:
            n = int(re.sub(r"\D", "", traffico.group(1))) if traffico else 0
            out.append((termine.group(1).strip(), n, json.dumps(titoli, ensure_ascii=False)))
    return out


def pota(con, ts, giorni=40):
    """Le posizioni e i segnali grezzi servono per 40 giorni; notizie e articoli restano."""
    vecchio = con.execute("SELECT MAX(id) FROM giri WHERE ts<?", (ts - giorni * 86400,)).fetchone()[0]
    if vecchio:
        con.execute("DELETE FROM posizioni WHERE al<=?", (vecchio,))
        con.execute("DELETE FROM piu_letti WHERE giro<=?", (vecchio,))
        con.execute("DELETE FROM trends WHERE giro<=?", (vecchio,))


def migra(con):
    """Vecchio formato (una riga per titolo per giro) → tratti."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='voci'").fetchone():
        return
    righe = con.execute("SELECT giro, testata, url, rango, pos, peso, evidenza FROM voci ORDER BY giro").fetchall()
    ok = {}
    for g, te in con.execute("SELECT giro, testata FROM letture WHERE ok=1 ORDER BY giro"):
        ok.setdefault(te, []).append(g)
    aperti = {}
    for g, te, u, r, p, pe, e in righe:
        lst = ok.get(te, [])
        i = lst.index(g) if g in lst else -1
        prec = lst[i - 1] if i > 0 else None
        k = (te, u, r)
        if k in aperti and aperti[k][7] == prec:
            aperti[k][7] = g
        else:
            if k in aperti:
                con.execute("INSERT INTO posizioni VALUES(?,?,?,?,?,?,?,?)", aperti[k])
            aperti[k] = [te, u, r, p, pe, e, g, g]
    for v in aperti.values():
        con.execute("INSERT INTO posizioni VALUES(?,?,?,?,?,?,?,?)", v)
    con.execute("DROP TABLE voci")
    con.commit()
    con.execute("VACUUM")


def giro():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    migra(con)
    adesso = dt.datetime.now()
    ts = int(adesso.timestamp())
    # due avvii ravvicinati (orologio di Supabase + quello di GitHub): il secondo non fa nulla
    ultimo = con.execute("SELECT MAX(ts) FROM giri").fetchone()[0]
    if ultimo and ts - ultimo < 8 * 60:
        print(f"giro saltato: l'ultimo è di {(ts - ultimo) // 60} minuti fa")
        con.close()
        return None
    gid = con.execute("INSERT INTO giri(ts, quando) VALUES(?,?)", (ts, adesso.isoformat(timespec="minutes"))).lastrowid

    risultati = {}
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        fut = {ex.submit(leggi_testata, t, adesso.date()): t for t in TESTATE}
        for f in cf.as_completed(fut):
            t = fut[f]
            try:
                risultati[t["id"]] = (f.result(), None)
            except Exception as e:
                risultati[t["id"]] = (([], []), f"{type(e).__name__}: {e}"[:200])

    for t in TESTATE:
        (voci, letti), err = risultati[t["id"]]
        if not voci and not err:
            err = "pagina letta ma nessun titolo riconosciuto (impaginazione cambiata?)"
        voci = sorted(voci, key=lambda v: v["rango"])[:TIENI]
        firma = hashlib.sha1("|".join(v["url"] for v in voci[:10]).encode()).hexdigest()[:12] if voci else ""
        prima = con.execute("SELECT firma FROM letture WHERE testata=? AND ok=1 ORDER BY giro DESC LIMIT 1",
                            (t["id"],)).fetchone()
        cambiata = int(bool(voci) and (prima is None or prima[0] != firma))
        con.execute("INSERT INTO letture VALUES(?,?,?,?,?,?,?)",
                    (gid, t["id"], int(bool(voci)), len(voci), firma, cambiata, err))
        for v in voci + letti:
            con.execute("""INSERT INTO articoli(url, testata, titolo, categoria, prima, ultima)
                           VALUES(?,?,?,?,?,?)
                           ON CONFLICT(url) DO UPDATE SET ultima=excluded.ultima""",
                        (v["url"], t["id"], v["titolo"], categoria_di(v["url"], v["titolo"], t), ts, ts))
        prec = con.execute("SELECT MAX(giro) FROM letture WHERE testata=? AND ok=1 AND giro<?",
                           (t["id"], gid)).fetchone()[0]
        for v in voci:
            aperto = con.execute("""SELECT rowid FROM posizioni WHERE testata=? AND url=? AND rango=? AND al=?""",
                                 (t["id"], v["url"], v["rango"], prec)).fetchone() if prec else None
            if aperto:
                con.execute("UPDATE posizioni SET al=? WHERE rowid=?", (gid, aperto[0]))
            else:
                con.execute("INSERT INTO posizioni VALUES(?,?,?,?,?,?,?,?)",
                            (t["id"], v["url"], v["rango"], v["pos"], v["peso"], v["evidenza"], gid, gid))
        con.executemany("INSERT INTO piu_letti VALUES(?,?,?,?)",
                        [(gid, t["id"], v["url"], v["pos"]) for v in letti])

    try:
        con.executemany("INSERT INTO trends VALUES(?,?,?,?)", [(gid,) + r for r in leggi_trends()])
    except Exception as e:
        print("Google Trends non letto:", e)

    pota(con, ts)
    con.commit()
    ok = sum(1 for t in TESTATE if risultati[t["id"]][0][0])
    cambi = con.execute("SELECT COUNT(*) FROM letture WHERE giro=? AND cambiata=1", (gid,)).fetchone()[0]
    print(f"{adesso:%d/%m %H:%M} giro {gid}: {ok}/{len(TESTATE)} testate lette, {cambi} homepage cambiate")
    for t in TESTATE:
        if risultati[t["id"]][1]:
            print(f"  ! {t['nome']}: {risultati[t['id']][1]}")
    con.close()
    return gid


if __name__ == "__main__":
    t0 = time.time()
    giro()
    print(f"  ({time.time() - t0:.0f}s)")
