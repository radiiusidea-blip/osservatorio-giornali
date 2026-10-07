"""Analisi dopo ogni giro: raggruppa gli articoli in notizie, calcola classifiche,
rapporti, modelli editoriali e cadute, e scrive sito/dati.js per il pannello.

Uso: python3 analisi.py
"""
import datetime as dt
import json
import math
import re
import sqlite3
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

from categorie import CATEGORIE
from testate import PER_ID, TESTATE

QUI = Path(__file__).resolve().parent
DB = QUI / "dati" / "osservatorio.sqlite"
USCITA = QUI / "sito" / "dati.js"
GIORNI = 8                  # finestra di analisi
SOGLIA_STESSA_NOTIZIA = 0.32
GIORNI_PER_CADUTE = 3       # sotto questa soglia l'analisi delle cadute è preliminare
HOME = [t["id"] for t in TESTATE if t.get("fonte") != "rss"]

# ---------------------------------------------------------------- testo

STOP = set("""a ad al allo ai agli all alla alle anche ancora avere aveva c che chi ci coi col come con contro cosa così
cui da dal dallo dai dagli dall dalla dalle dei del dell della delle dello degli di dopo dove e è ecco era essere fa fra
gli ha hanno ho i il in io l la le lei li lo loro lui ma mai me meno mi molto ne nel nell nella nelle nello negli no noi
non nostro o oggi ogni oltre per perché più poi può qua quale quando quanto quella quelle quelli quello questa queste
questi questo qui se sarà secondo sempre senza si sia siamo solo sono su sua sue sugli sui sul sull sulla sulle sullo
suo suoi tra tre tutti tutto tutte tutta un una uno uno va vi video foto live diretta ultime ultim ora news dice detto
anni anno giorno giorni ieri domani mentre dalla fare fatto fino stato stata stati due primo prima nuovo nuova nuove
""".split())


def gettoni(testo):
    testo = testo.lower().replace("’", "'")
    out = []
    for w in re.findall(r"[a-zàèéìòù0-9]+", testo):
        if len(w) < 3 or w in STOP or w.isdigit():
            continue
        out.append(w[:6])
    return out


def slug_parole(url):
    u = url.rstrip("/").rsplit("/", 1)[-1]
    u = re.sub(r"\.(s?html?|php)$", "", u)
    u = re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27,}", "", u)
    return " ".join(p for p in re.split(r"[-_]+", u) if not re.fullmatch(r"\d+|[a-z]?\d+[a-z]*", p))


def vettore(toks, idf):
    c = Counter(toks)
    v = {t: (1 + math.log(n)) * idf.get(t, 1.0) for t, n in c.items()}
    norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: x / norma for t, x in v.items()}


def coseno(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


# ---------------------------------------------------------------- notizie

def raggruppa(con, ora):
    """Assegna una notizia agli articoli che non ce l'hanno: stesso fatto su testate diverse
    (o articoli successivi della stessa testata) finiscono nella stessa notizia."""
    da = ora - 48 * 3600
    righe = con.execute("SELECT url, titolo, notizia, prima FROM articoli WHERE ultima>=? ORDER BY prima",
                        (da,)).fetchall()
    if not righe:
        return
    docs = {u: gettoni(t + " " + slug_parole(u)) for u, t, _, _ in righe}
    df = Counter()
    for toks in docs.values():
        df.update(set(toks))
    n = len(docs)
    idf = {t: math.log((n + 1) / (k + 0.5)) for t, k in df.items()}
    vett = {u: vettore(toks, idf) for u, toks in docs.items()}
    # indice per gettone, per non confrontare tutto con tutto
    indice = defaultdict(set)
    assegnati = {}
    for u, _, nid, _ in righe:
        if nid:
            assegnati[u] = nid
            for t in vett[u]:
                indice[t].add(u)
    nuovi = 0
    for u, titolo, nid, prima in righe:
        if nid:
            continue
        v = vett[u]
        candidati = set()
        for t, peso in v.items():
            if peso > 0.12 and len(indice[t]) < 400:
                candidati |= indice[t]
        meglio, sim = None, 0.0
        for c in candidati:
            s = coseno(v, vett[c])
            if s > sim:
                meglio, sim = c, s
        if meglio and sim >= SOGLIA_STESSA_NOTIZIA:
            nid = assegnati[meglio]
        else:
            nid = con.execute("INSERT INTO notizie(etichetta, prima, ultima) VALUES(?,?,?)",
                              (titolo, prima, prima)).lastrowid
            nuovi += 1
        assegnati[u] = nid
        con.execute("UPDATE articoli SET notizia=? WHERE url=?", (nid, u))
        for t in v:
            indice[t].add(u)
    con.commit()
    return nuovi


# ---------------------------------------------------------------- caricamento

def carica(con, ora):
    da = ora - GIORNI * 86400
    giri = con.execute("SELECT id, ts FROM giri WHERE ts>=? ORDER BY ts", (da,)).fetchall()
    ts_giro = dict(giri)
    ids = [g for g, _ in giri]
    # durata rappresentata da ogni giro: fino al successivo, al massimo 30 minuti
    durata = {}
    for i, (g, t) in enumerate(giri):
        nxt = giri[i + 1][1] if i + 1 < len(giri) else min(ora, t + 900)
        durata[g] = max(60, min(nxt - t, 2700)) / 60.0
    primo = ids[0] if ids else 0
    # i tratti (dal..al) tornano una riga per giro, solo nei giri in cui la testata è stata letta
    ok_te = defaultdict(list)
    for g, te in con.execute("SELECT giro, testata FROM letture WHERE ok=1 AND giro>=? ORDER BY giro", (primo,)):
        ok_te[te].append(g)
    import bisect
    voci = []
    for te, u, r, e, dal, al in con.execute(
            "SELECT testata, url, rango, evidenza, dal, al FROM posizioni WHERE al>=?", (primo,)):
        lst = ok_te.get(te, [])
        for g in lst[bisect.bisect_left(lst, max(dal, primo)):bisect.bisect_right(lst, al)]:
            voci.append((g, te, u, r, e))
    letti = con.execute("SELECT giro, testata, url, pos FROM piu_letti WHERE giro>=?", (primo,)).fetchall()
    trends = con.execute("SELECT giro, termine, traffico, titoli FROM trends WHERE giro>=?", (primo,)).fetchall()
    letture = con.execute("SELECT giro, testata, ok, cambiata FROM letture WHERE giro>=?", (primo,)).fetchall()
    art = {}
    for u, te, ti, cat, p, ul, nid in con.execute(
            "SELECT url, testata, titolo, categoria, prima, ultima, notizia FROM articoli WHERE ultima>=?", (da,)):
        art[u] = {"testata": te, "titolo": ti, "cat": cat, "prima": p, "ultima": ul, "notizia": nid}
    return giri, ts_giro, durata, voci, letti, trends, letture, art


def giorno_di(ts):
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def hhmm(ts):
    return dt.datetime.fromtimestamp(ts).strftime("%H:%M")


# ---------------------------------------------------------------- analisi principale

def analizza():
    con = sqlite3.connect(DB)
    ora = int(dt.datetime.now().timestamp())
    raggruppa(con, ora)
    giri, ts_giro, durata, voci, letti, trends, letture, art = carica(con, ora)
    if not giri:
        print("nessun dato")
        return
    ultimo = giri[-1][0]

    # --- notizie: articoli, testate, categoria, etichetta
    notizia_art = defaultdict(list)
    for u, a in art.items():
        if a["notizia"]:
            notizia_art[a["notizia"]].append(u)

    per_giro = defaultdict(lambda: defaultdict(list))      # giro -> testata -> [(rango, url)]
    evid_url = defaultdict(float)
    for g, te, u, r, e in voci:
        per_giro[g][te].append((r, u))
        evid_url[u] += e * durata[g]

    def cat_notizia(nid):
        c = Counter(art[u]["cat"] for u in notizia_art[nid] if art[u]["cat"] not in ("Altro", "Opinioni"))
        if not c:
            c = Counter(art[u]["cat"] for u in notizia_art[nid])
        return c.most_common(1)[0][0] if c else "Altro"

    def etichetta(nid):
        us = notizia_art[nid]
        if not us:
            return ""
        return art[max(us, key=lambda u: (evid_url.get(u, 0), len(art[u]["titolo"])))]["titolo"]

    info_n = {}
    for nid, us in notizia_art.items():
        info_n[nid] = {
            "id": nid, "titolo": etichetta(nid), "categoria": cat_notizia(nid),
            "testate": sorted({art[u]["testata"] for u in us}),
            "articoli": len(us), "prima": min(art[u]["prima"] for u in us),
            "opinioni": sum(1 for u in us if art[u]["cat"] == "Opinioni"),
        }
    for nid, inf in info_n.items():
        con.execute("UPDATE notizie SET etichetta=?, categoria=?, ultima=? WHERE id=?",
                    (inf["titolo"], inf["categoria"], ora, nid))
    con.commit()

    def nid_di(u):
        return art.get(u, {}).get("notizia")

    # --- punteggio nazionale per giro: somma su testate di 1/rango della miglior voce della notizia
    punti = defaultdict(dict)        # giro -> notizia -> punteggio
    rango_n = defaultdict(dict)      # (giro, testata) -> notizia -> miglior rango
    for g, testate in per_giro.items():
        lette = [te for te in testate if te in HOME]
        for te, lst in testate.items():
            best = {}
            for r, u in lst:
                n = nid_di(u)
                if n and (n not in best or r < best[n]):
                    best[n] = r
            rango_n[(g, te)] = best
            if te not in HOME:
                continue
            for n, r in best.items():
                if r <= 15:
                    punti[g][n] = punti[g].get(n, 0) + 1.0 / r
        k = max(1, len(lette))
        for n in punti[g]:
            punti[g][n] = round(punti[g][n] / k * 10, 3)   # scala 0-10

    # ---------------------------------------------------- 1. ADESSO (prima fila)
    adesso_testate = []
    ultimo_ok = {}
    for g, te, ok, cambiata in letture:
        if ok:
            ultimo_ok[te] = g
    agg_oggi = Counter(te for g, te, ok, c in letture if c and giorno_di(ts_giro[g]) == giorno_di(ora))
    ultimo_cambio = {}
    for g, te, ok, c in letture:
        if c:
            ultimo_cambio[te] = ts_giro[g]
    for t in TESTATE:
        g = ultimo_ok.get(t["id"])
        lst = sorted(per_giro[g][t["id"]]) if g else []
        adesso_testate.append({
            "id": t["id"], "nome": t["nome"], "tipo": t["tipo"], "url": t["url"],
            "rss": t.get("fonte") == "rss",
            "letta": hhmm(ts_giro[g]) if g else None,
            "aggiornata": hhmm(ultimo_cambio[t["id"]]) if t["id"] in ultimo_cambio else None,
            "aggiornamenti_oggi": agg_oggi.get(t["id"], 0),
            "voci": [{"r": r, "t": art[u]["titolo"], "u": u, "c": art[u]["cat"], "n": nid_di(u),
                      "q": len(info_n.get(nid_di(u), {}).get("testate", []))} for r, u in lst[:8] if u in art],
        })
    nazionale = sorted(punti[ultimo].items(), key=lambda x: -x[1])[:25]
    adesso_naz = []
    for n, p in nazionale:
        inf = info_n.get(n)
        if not inf:
            continue
        aperture = [te for te in HOME if rango_n.get((ultimo, te), {}).get(n) == 1]
        adesso_naz.append({**pick(inf, "id titolo categoria"), "punti": p,
                           "testate": len([1 for te in HOME if n in rango_n.get((ultimo, te), {})]),
                           "aperture": [PER_ID[te]["nome"] for te in aperture]})

    # ---------------------------------------------------- 2. RAPPORTO DEL GIORNO (per ogni giorno)
    giorni = sorted({giorno_di(t) for _, t in giri})
    rapporti = {}
    for gg in giorni[-7:]:
        ids = [g for g, t in giri if giorno_di(t) == gg]
        rapporti[gg] = rapporto_giorno(ids, ts_giro, durata, per_giro, rango_n, punti, info_n, art, letture, nid_di)

    # ---------------------------------------------------- 3. INTERAZIONI
    interazioni = {}
    for gg in giorni[-7:]:
        ids = set(g for g, t in giri if giorno_di(t) == gg)
        interazioni[gg] = indice_interazioni(ids, durata, letti, trends, info_n, art, nid_di, notizia_art)

    # ---------------------------------------------------- 4. MODELLI
    modelli = modelli_editoriali(giri, ts_giro, durata, per_giro, rango_n, punti, info_n, art, letti,
                                 letture, nid_di)

    # ---------------------------------------------------- 5. CADUTE
    cadute = analisi_cadute(giri, ts_giro, durata, per_giro, rango_n, punti, info_n, art, letti,
                            interazioni, nid_di)

    stato = {
        "generato": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "ultimo_ts": ts_giro[ultimo],
        "ultimo_giro": dt.datetime.fromtimestamp(ts_giro[ultimo]).strftime("%d/%m/%Y %H:%M"),
        "giri": len(giri), "inizio": dt.datetime.fromtimestamp(giri[0][1]).strftime("%d/%m/%Y %H:%M"),
        "ore_dati": round((giri[-1][1] - giri[0][1]) / 3600, 1),
        "testate": len(TESTATE), "lette_ultimo": sum(1 for g, te, ok, c in letture if g == ultimo and ok),
        "notizie": len(info_n), "articoli": len(art),
    }
    dati = {"stato": stato, "categorie": CATEGORIE, "adesso": {"nazionale": adesso_naz, "testate": adesso_testate},
            "rapporti": rapporti, "interazioni": interazioni, "modelli": modelli, "cadute": cadute}
    USCITA.parent.mkdir(exist_ok=True)
    USCITA.write_text("window.DATI = " + json.dumps(dati, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"analisi: {len(info_n)} notizie, {len(giri)} giri, {USCITA.stat().st_size // 1024} KB")
    con.close()


def pick(d, chiavi):
    return {k: d[k] for k in chiavi.split()}


# ---------------------------------------------------------------- rapporto giornaliero

def rapporto_giorno(ids, ts_giro, durata, per_giro, rango_n, punti, info_n, art, letture, nid_di):
    tot = defaultdict(float)
    min_primo = defaultdict(float)
    for g in ids:
        if not punti[g]:
            continue
        for n, p in punti[g].items():
            tot[n] += p * durata[g] / 60.0
        top = max(punti[g].items(), key=lambda x: x[1])[0]
        min_primo[top] += durata[g]
    classifica = sorted(tot.items(), key=lambda x: -x[1])[:15]
    naz = [{**pick(info_n[n], "id titolo categoria"), "punti_ora": round(v, 1),
            "minuti_primo": round(min_primo.get(n, 0)), "testate": len(info_n[n]["testate"])}
           for n, v in classifica if n in info_n]
    # serie temporale delle prime 8 notizie
    top8 = [n for n, _ in classifica[:8] if n in info_n]
    serie = {"orari": [hhmm(ts_giro[g]) for g in ids],
             "linee": [{"id": n, "titolo": info_n[n]["titolo"], "valori": [punti[g].get(n, 0) for g in ids]}
                       for n in top8]}
    # per testata: quale notizia è rimasta di più in apertura e in prima fila (primi 5)
    per_testata = []
    cambi = Counter(te for g, te, ok, c in letture if c and g in set(ids))
    for t in TESTATE:
        te = t["id"]
        apert = defaultdict(float)
        fila = defaultdict(float)
        succ = []
        prec = None
        for g in ids:
            best = rango_n.get((g, te))
            if not best:
                continue
            for n, r in best.items():
                if r == 1:
                    apert[n] += durata[g]
                if r <= 5:
                    fila[n] += durata[g]
            a = min(best.items(), key=lambda x: x[1])[0] if best else None
            if a != prec and a in info_n:
                succ.append({"ora": hhmm(ts_giro[g]), "titolo": info_n[a]["titolo"], "id": a})
                prec = a
        if not fila:
            per_testata.append({"id": te, "nome": t["nome"], "rss": t.get("fonte") == "rss", "vuota": True})
            continue
        na = max(apert.items(), key=lambda x: x[1])[0] if apert else None
        tf = sorted(fila.items(), key=lambda x: -x[1])[:5]
        per_testata.append({
            "id": te, "nome": t["nome"], "rss": t.get("fonte") == "rss",
            "apertura": {**pick(info_n[na], "id titolo categoria"), "minuti": round(apert[na])} if na in info_n else None,
            "prima_fila": [{**pick(info_n[n], "id titolo categoria"), "minuti": round(m)} for n, m in tf if n in info_n],
            "aperture_diverse": len(apert), "aggiornamenti": cambi.get(te, 0),
            "successione": succ[-12:],
        })
    return {"nazionale": naz, "serie": serie, "testate": per_testata,
            "dalle": hhmm(ts_giro[ids[0]]), "alle": hhmm(ts_giro[ids[-1]]), "giri": len(ids)}


# ---------------------------------------------------------------- interazioni

def indice_interazioni(ids, durata, letti, trends, info_n, art, nid_di, notizia_art):
    """Click e discussione non sono pubblici: si usano tre segnali osservabili.
    lettura   = presenza e posizione nelle classifiche «più letti/visti» dei giornali
    ricerca   = picchi di ricerca su Google in Italia (Google Trends) collegati alla notizia
    dibattito = quante testate la riprendono, quanti articoli e commenti produce"""
    lettura = defaultdict(float)
    testate_letti = defaultdict(set)
    giri_letti = defaultdict(set)
    for g, te, u, pos in letti:
        if g not in ids:
            continue
        n = nid_di(u)
        if n:
            lettura[n] += (16 - min(pos, 15)) / 15 * durata[g] / 60
            testate_letti[n].add(te)
            giri_letti[g].add(te)
    # ricerche: un termine di tendenza è collegato a una notizia se i suoi gettoni stanno nel titolo
    tok_n = {n: set(gettoni(i["titolo"])) | set().union(*[set(gettoni(art[u]["titolo"])) for u in notizia_art[n][:6]])
             for n, i in info_n.items()}
    indice_tok = defaultdict(set)
    for n, ts in tok_n.items():
        for t in ts:
            indice_tok[t].add(n)
    ricerca = defaultdict(int)
    termini_n = defaultdict(set)
    visti, contesto = {}, {}
    for g, termine, traffico, titoli in trends:
        if g not in ids:
            continue
        visti[termine] = max(visti.get(termine, 0), traffico)
        contesto[termine] = set(gettoni(" ".join(json.loads(titoli or "[]"))))
    for termine, traffico in visti.items():
        tt = set(gettoni(termine))
        if not tt or (len(tt) == 1 and len(termine) < 5):
            continue
        cand = set.intersection(*[indice_tok.get(t, set()) for t in tt])
        # la ricerca va alle notizie più vicine ai titoli che Google collega al termine
        ctx = contesto.get(termine, set())
        punt = sorted(((len(tok_n[n] & ctx), n) for n in cand), reverse=True)
        if not punt:
            continue
        if ctx and punt[0][0] < 2:
            continue        # nessun titolo di Google somiglia: probabilmente un omonimo
        for sc, n in punt[:2]:
            if sc < max(2, punt[0][0] * 0.6) and ctx:
                break
            ricerca[n] = max(ricerca[n], traffico)
            termini_n[n].add(termine)
    # notizie attive quel giorno
    attive = set(lettura) | set(ricerca)
    giorno_art = defaultdict(int)
    for n, i in info_n.items():
        if i["articoli"] >= 2 or n in attive:
            attive.add(n)
    def norm(d):
        m = max(d.values()) if d else 0
        return {k: (v / m if m else 0) for k, v in d.items()}
    dib = {n: len(info_n[n]["testate"]) + 0.3 * info_n[n]["articoli"] + 0.5 * info_n[n]["opinioni"] for n in attive}
    L, R, D = norm(lettura), norm({k: math.log10(v + 1) for k, v in ricerca.items()}), norm(dib)
    tutte = []
    for n in attive:
        if n not in info_n:
            continue
        v = 100 * (0.45 * L.get(n, 0) + 0.25 * R.get(n, 0) + 0.30 * D.get(n, 0))
        tutte.append({**pick(info_n[n], "id titolo categoria"), "indice": round(v, 1),
                      "lettura": round(100 * L.get(n, 0)), "ricerca": round(100 * R.get(n, 0)),
                      "dibattito": round(100 * D.get(n, 0)), "testate": len(info_n[n]["testate"]),
                      "articoli": info_n[n]["articoli"], "nei_piu_letti": sorted(PER_ID[t]["nome"] for t in testate_letti[n]),
                      "ricerche": sorted(termini_n[n])[:4], "traffico": ricerca.get(n, 0)})
    tutte.sort(key=lambda x: -x["indice"])
    per_cat = defaultdict(list)
    for x in tutte:
        if len(per_cat[x["categoria"]]) < 6:
            per_cat[x["categoria"]].append(x)
    somma_cat = defaultdict(float)
    for x in tutte[:200]:
        somma_cat[x["categoria"]] += x["indice"]
    return {"classifica": tutte[:30], "per_categoria": per_cat,
            "peso_categorie": sorted(([k, round(v)] for k, v in somma_cat.items()), key=lambda x: -x[1]),
            "fonti_letti": sorted({PER_ID[te]["nome"] for g, te, u, p in letti if g in ids}),
            "termini": sorted(visti.items(), key=lambda x: -x[1])[:15]}


# ---------------------------------------------------------------- modelli editoriali

ETICHETTE_CAR = {
    "diversita": ("varietà di temi", "pochi temi dominanti"),
    "ricambio": ("homepage in flusso continuo", "homepage stabile"),
    "emivita": ("titoli che restano a lungo in alto", "titoli che ruotano in fretta"),
    "allineamento": ("allineato all'agenda nazionale", "agenda propria"),
    "anticipo": ("arriva dopo gli altri", "arriva prima degli altri"),
    "esclusivita": ("molte notizie esclusive", "notizie condivise con tutti"),
    "virgolettati": ("titoli a virgolettato", "titoli descrittivi"),
    "q_Politica": ("forte sulla politica", "poca politica"),
    "q_Cronaca": ("forte sulla cronaca", "poca cronaca"),
    "q_Esteri": ("forte sugli esteri", "pochi esteri"),
    "q_leggero": ("sport, spettacolo e stili di vita", "poco intrattenimento"),
    "q_Opinioni": ("molto commento", "poco commento"),
    "q_Economia": ("forte sull'economia", "poca economia"),
}
LEGGERO = {"Sport", "Cultura e spettacoli", "Stili di vita"}


def modelli_editoriali(giri, ts_giro, durata, per_giro, rango_n, punti, info_n, art, letti, letture, nid_di):
    ids = [g for g, _ in giri]
    car = {}
    mix = {}
    sopravvivenza = {}
    prima_vista_n = defaultdict(dict)     # notizia -> testata -> primo ts
    for g in ids:
        for te in HOME + [t["id"] for t in TESTATE if t["id"] not in HOME]:
            for n in rango_n.get((g, te), {}):
                if te not in prima_vista_n[n]:
                    prima_vista_n[n][te] = ts_giro[g]
    naz_top = {g: set(n for n, _ in sorted(punti[g].items(), key=lambda x: -x[1])[:10]) for g in ids}

    for t in TESTATE:
        te = t["id"]
        cat_peso = Counter()
        tit = []
        ricambi, prev = [], None
        dentro = {}           # url -> minuti nei primi 5 (permanenza continua)
        permanenze = []
        corrente = {}
        jacc, escl = [], []
        miei_giri = [g for g in ids if per_giro[g].get(te)]
        for g in miei_giri:
            lst = sorted(per_giro[g][te])
            for r, u in lst[:20]:
                if u in art:
                    cat_peso[art[u]["cat"]] += durata[g] / r ** 0.5
            top10 = set(u for r, u in lst[:10])
            if prev is not None:
                ore = max(0.25, (ts_giro[g] - ts_giro[prev[0]]) / 3600)
                ricambi.append(len(top10 - prev[1]) / 10 / ore)
            prev = (g, top10)
            top5 = set(u for r, u in lst[:5])
            for u in list(corrente):
                if u not in top5:
                    permanenze.append(corrente.pop(u))
            for u in top5:
                corrente[u] = corrente.get(u, 0) + durata[g]
            mie = set(n for n, r in rango_n[(g, te)].items() if r <= 10)
            if mie and naz_top[g]:
                jacc.append(len(mie & naz_top[g]) / len(mie | naz_top[g]))
            if mie:
                escl.append(sum(1 for n in mie if len(info_n.get(n, {}).get("testate", [])) <= 1) / len(mie))
        for u in set(u for g in miei_giri for r, u in per_giro[g][te][:30]):
            if u in art:
                tit.append(art[u]["titolo"])
        tot = sum(cat_peso.values()) or 1
        quote = {c: cat_peso.get(c, 0) / tot for c in CATEGORIE}
        mix[te] = {c: round(100 * q, 1) for c, q in quote.items()}
        H = -sum(q * math.log(q) for q in quote.values() if q > 0) / math.log(len(CATEGORIE))
        # anticipo: minuti rispetto alla mediana delle testate per notizie riprese da almeno 3
        anticipi = []
        for n, d in prima_vista_n.items():
            if te in d and len(d) >= 3:
                anticipi.append((d[te] - st.median(d.values())) / 60)
        virg = sum(1 for x in tit if re.search(r"[«“\"]", x)) / len(tit) if tit else 0
        domande = sum(1 for x in tit if "?" in x) / len(tit) if tit else 0
        sopravvivenza[te] = curva_sopravvivenza(permanenze + list(corrente.values()))
        car[te] = {
            "diversita": round(H, 3),
            "ricambio": round(st.mean(ricambi), 3) if ricambi else None,
            "emivita": round(st.median(permanenze), 0) if len(permanenze) >= 3 else None,
            "allineamento": round(st.mean(jacc), 3) if jacc else None,
            "anticipo": round(st.median(anticipi), 0) if len(anticipi) >= 3 else None,
            "esclusivita": round(st.mean(escl), 3) if escl else None,
            "virgolettati": round(virg, 3), "domande": round(domande, 3),
            "parole_titolo": round(st.mean(len(x.split()) for x in tit), 1) if tit else None,
            "aggiornamenti_ora": round(sum(1 for g, x, ok, c in letture if x == te and c) /
                                       max(1, (ts_giro[ids[-1]] - ts_giro[ids[0]]) / 3600), 2),
            "q_Politica": quote["Politica"], "q_Cronaca": quote["Cronaca"], "q_Esteri": quote["Esteri"],
            "q_Economia": quote["Economia"], "q_Opinioni": quote["Opinioni"],
            "q_leggero": sum(quote[c] for c in LEGGERO),
        }

    # coerenza con i lettori: quanto di ciò che è «più letto» la testata lo tiene nei primi 10
    coer = defaultdict(list)
    letti_g = defaultdict(lambda: defaultdict(set))
    for g, te, u, pos in letti:
        n = nid_di(u)
        if n:
            letti_g[(g, te)]["n"].add(n)
    for (g, te), d in letti_g.items():
        top = set(n for n, r in rango_n.get((g, te), {}).items() if r <= 10)
        if d["n"]:
            coer[te].append(len(d["n"] & top) / len(d["n"]))
    for te in car:
        car[te]["coerenza_lettori"] = round(st.mean(coer[te]), 3) if coer.get(te) else None

    # somiglianza di agenda fra testate: Jaccard delle notizie messe nei primi 10
    insiemi = defaultdict(set)
    for (g, te), best in rango_n.items():
        for n, r in best.items():
            if r <= 10:
                insiemi[te].add(n)
    ord_t = [t["id"] for t in TESTATE if insiemi.get(t["id"])]
    matrice = [[round(len(insiemi[a] & insiemi[b]) / max(1, len(insiemi[a] | insiemi[b])), 3) for b in ord_t]
               for a in ord_t]

    # mappa dei modelli: componenti principali + gruppi (k-medie) sulle caratteristiche standardizzate
    chiavi = ["diversita", "ricambio", "emivita", "allineamento", "anticipo", "esclusivita", "virgolettati",
              "q_Politica", "q_Cronaca", "q_Esteri", "q_Economia", "q_leggero", "q_Opinioni"]
    usabili = [te for te in HOME if te in car]
    X, nomi = [], []
    for te in usabili:
        riga = [car[te].get(k) for k in chiavi]
        X.append(riga)
        nomi.append(te)
    mappa, gruppi = [], []
    if len(X) >= 5:
        Z, medie, dev = standardizza(X)
        pc, var = pca2(Z)
        k = 4 if len(X) >= 12 else 3
        assegn, centri = kmedie(Z, k)
        for i, te in enumerate(nomi):
            mappa.append({"id": te, "nome": PER_ID[te]["nome"], "x": round(pc[i][0], 3), "y": round(pc[i][1], 3),
                          "gruppo": assegn[i]})
        for j, c in enumerate(centri):
            membri = [PER_ID[nomi[i]]["nome"] for i in range(len(nomi)) if assegn[i] == j]
            if not membri:
                continue
            tratti = sorted(range(len(chiavi)), key=lambda q: -abs(c[q]))[:3]
            descr = [ETICHETTE_CAR[chiavi[q]][0 if c[q] > 0 else 1] for q in tratti]
            gruppi.append({"gruppo": j, "nome": nome_modello(dict(zip(chiavi, c))), "tratti": descr,
                           "membri": membri, "centro": {chiavi[q]: round(c[q], 2) for q in range(len(chiavi))}})
        carichi = [{"car": chiavi[q], "x": round(var["v1"][q], 3), "y": round(var["v2"][q], 3)} for q in range(len(chiavi))]
    else:
        carichi = []
        var = {"spiegata": [0, 0]}
    return {"caratteristiche": {te: v for te, v in car.items()}, "mix": mix, "mappa": mappa, "gruppi": gruppi,
            "carichi": carichi, "varianza": var.get("spiegata"), "sopravvivenza": sopravvivenza,
            "matrice": {"testate": [PER_ID[t]["nome"] for t in ord_t], "valori": matrice},
            "nomi": {t["id"]: t["nome"] for t in TESTATE}}


def nome_modello(c):
    """Nome leggibile del gruppo a partire dal suo centro (valori standardizzati)."""
    tema = max(["q_Politica", "q_Cronaca", "q_Esteri", "q_Economia", "q_leggero", "q_Opinioni"], key=lambda k: c[k])
    temi = {"q_Politica": "Agenda politica", "q_Cronaca": "Cronaca e fatti", "q_Esteri": "Sguardo internazionale",
            "q_Economia": "Economia e mercati", "q_leggero": "Intrattenimento e sport", "q_Opinioni": "Commento e opinione"}
    ritmo = ("flusso continuo" if (c.get("ricambio") or 0) > 0.5 else
             "agenda propria" if (c.get("esclusivita") or 0) > 0.5 or (c.get("allineamento") or 0) < -0.5 else
             "allineato al mainstream" if (c.get("allineamento") or 0) > 0.5 else "generalista")
    return f"{temi[tema]} · {ritmo}"


def curva_sopravvivenza(permanenze):
    """Quota di titoli ancora tra i primi 5 dopo t ore (stima empirica)."""
    if not permanenze:
        return []
    n = len(permanenze)
    return [[h, round(sum(1 for p in permanenze if p >= h * 60) / n, 3)] for h in
            (0, 0.5, 1, 2, 3, 4, 6, 8, 12, 18, 24)]


def standardizza(X):
    cols = list(zip(*X))
    medie, dev = [], []
    for c in cols:
        v = [x for x in c if x is not None]
        m = st.mean(v) if v else 0
        s = st.pstdev(v) if len(v) > 1 else 1
        medie.append(m)
        dev.append(s or 1)
    Z = [[((x if x is not None else medie[j]) - medie[j]) / dev[j] for j, x in enumerate(r)] for r in X]
    return Z, medie, dev


def pca2(Z):
    n, p = len(Z), len(Z[0])
    C = [[sum(Z[i][a] * Z[i][b] for i in range(n)) / max(1, n - 1) for b in range(p)] for a in range(p)]
    tr = sum(C[a][a] for a in range(p)) or 1

    def potenza(M, iniz):
        v = iniz
        for _ in range(300):
            w = [sum(M[a][b] * v[b] for b in range(p)) for a in range(p)]
            nn = math.sqrt(sum(x * x for x in w)) or 1
            v = [x / nn for x in w]
        lam = sum(v[a] * sum(M[a][b] * v[b] for b in range(p)) for a in range(p))
        return v, lam
    v1, l1 = potenza(C, [1.0 / math.sqrt(p)] * p)
    C2 = [[C[a][b] - l1 * v1[a] * v1[b] for b in range(p)] for a in range(p)]
    v2, l2 = potenza(C2, [(-1) ** a / math.sqrt(p) for a in range(p)])
    pc = [[sum(z[j] * v1[j] for j in range(p)), sum(z[j] * v2[j] for j in range(p))] for z in Z]
    return pc, {"v1": v1, "v2": v2, "spiegata": [round(100 * l1 / tr, 1), round(100 * l2 / tr, 1)]}


def kmedie(Z, k):
    """k-medie deterministico: centri iniziali scelti col criterio del punto più lontano."""
    def d2(a, b):
        return sum((x - y) ** 2 for x, y in zip(a, b))
    centri = [max(Z, key=lambda z: sum(x * x for x in z))]
    while len(centri) < k:
        centri.append(max(Z, key=lambda z: min(d2(z, c) for c in centri)))
    assegn = [0] * len(Z)
    for _ in range(50):
        nuovo = [min(range(k), key=lambda j: d2(z, centri[j])) for z in Z]
        if nuovo == assegn and _ > 0:
            break
        assegn = nuovo
        for j in range(k):
            m = [Z[i] for i in range(len(Z)) if assegn[i] == j]
            if m:
                centri[j] = [st.mean(c) for c in zip(*m)]
    return assegn, centri


# ---------------------------------------------------------------- cadute

def analisi_cadute(giri, ts_giro, durata, per_giro, rango_n, punti, info_n, art, letti, interazioni, nid_di):
    """Titoli arrivati tra i primi 5 di una homepage che poi scivolano oltre il 20° posto
    (o spariscono), con le cause misurabili al momento della caduta."""
    ids = [g for g, _ in giri]
    ore_dati = (ts_giro[ids[-1]] - ts_giro[ids[0]]) / 3600
    letti_n = set(nid_di(u) for g, te, u, p in letti)
    ricercate = set()
    for gg, d in interazioni.items():
        for x in d["classifica"]:
            if x["ricerca"] > 0:
                ricercate.add(x["id"])
    picco_naz = defaultdict(float)
    for g in ids:
        for n, p in punti[g].items():
            picco_naz[n] = max(picco_naz[n], p)

    eventi = []
    durate_cat = defaultdict(list)
    for te in HOME:
        miei = [g for g in ids if per_giro[g].get(te)]
        storia = defaultdict(list)       # url -> [(giro, rango)]
        for g in miei:
            presenti = {u: r for r, u in per_giro[g][te]}
            for u, r in presenti.items():
                storia[u].append((g, r))
        pos_giro = {g: i for i, g in enumerate(miei)}
        for u, serie in storia.items():
            if u not in art or not art[u]["notizia"]:
                continue
            picco = min(r for _, r in serie)
            if picco > 5:
                continue
            g_picco = min(serie, key=lambda x: (x[1], x[0]))[0]
            min_top5 = sum(durata[g] for g, r in serie if r <= 5)
            # caduta: dopo il picco, primo giro con rango >= 20 o assente da 2 giri di fila
            dopo = [g for g in miei if g > g_picco]
            dove = dict(serie)
            g_caduta = None
            for i, g in enumerate(dopo):
                r = dove.get(g)
                if r is not None and r >= 20:
                    g_caduta = g
                    break
                if r is None and i + 1 < len(dopo) and dove.get(dopo[i + 1]) is None:
                    g_caduta = g
                    break
            n = art[u]["notizia"]
            cat = info_n.get(n, {}).get("categoria", art[u]["cat"])
            if g_caduta is None:
                continue
            durate_cat[cat].append(min_top5)
            ore = max(0.25, (ts_giro[g_caduta] - ts_giro[g_picco]) / 3600)
            # cause
            cause = []
            best = rango_n.get((g_caduta, te), {})
            altri = [v for r, v in per_giro[g_caduta][te] if v != u and art.get(v, {}).get("notizia") == n and r <= 10]
            if altri:
                cause.append(("aggiornamento", "Sostituita da un aggiornamento della stessa notizia"))
            nuove = [m for m, r in best.items() if r <= 3 and m != n and m in info_n
                     and info_n[m]["prima"] >= ts_giro[g_caduta] - 3 * 3600]
            if nuove:
                cause.append(("scalzata", "Scalzata da una notizia nuova: " + info_n[nuove[0]]["titolo"][:90]))
            if len(info_n.get(n, {}).get("testate", [])) <= 1:
                cause.append(("isolata", "Nessun'altra testata l'ha ripresa"))
            if n not in letti_n and n not in ricercate:
                cause.append(("senza_lettori", "Nessun segnale di lettura o di ricerca"))
            if picco_naz.get(n) and punti[g_caduta].get(n, 0) < 0.4 * picco_naz[n]:
                cause.append(("spenta", "La notizia si è spenta anche sulle altre testate"))
            if not cause:
                cause.append(("ciclo", "Fine del ciclo naturale: nessuna causa esterna evidente"))
            eventi.append({
                "testata": PER_ID[te]["nome"], "titolo": art[u]["titolo"], "url": u, "categoria": cat,
                "picco": picco, "minuti_top5": round(min_top5), "ore_alla_caduta": round(ore, 1),
                "velocita": round((20 - picco) / ore, 1), "quando": dt.datetime.fromtimestamp(ts_giro[g_caduta]).strftime("%d/%m %H:%M"),
                "cause": [c[1] for c in cause], "codici": [c[0] for c in cause],
                "testate_notizia": len(info_n.get(n, {}).get("testate", [])),
            })
    eventi.sort(key=lambda e: -e["velocita"])
    per_cat = []
    for c, lst in durate_cat.items():
        ev = [e for e in eventi if e["categoria"] == c]
        per_cat.append({"categoria": c, "cadute": len(lst), "mediana_minuti_top5": round(st.median(lst)),
                        "veloci": sum(1 for e in ev if e["ore_alla_caduta"] <= 3),
                        "cause": Counter(k for e in ev for k in e["codici"]).most_common()})
    per_cat.sort(key=lambda x: x["mediana_minuti_top5"])
    per_testata = []
    for te in HOME:
        ev = [e for e in eventi if e["testata"] == PER_ID[te]["nome"]]
        if ev:
            per_testata.append({"testata": PER_ID[te]["nome"], "cadute": len(ev),
                                "mediana_minuti_top5": round(st.median(e["minuti_top5"] for e in ev)),
                                "causa_tipica": Counter(k for e in ev for k in e["codici"]).most_common(1)[0][0]})
    per_testata.sort(key=lambda x: x["mediana_minuti_top5"])
    cause_tot = Counter(k for e in eventi for k in e["codici"])
    return {"preliminare": ore_dati < GIORNI_PER_CADUTE * 24, "ore_dati": round(ore_dati, 1),
            "giorni_richiesti": GIORNI_PER_CADUTE, "eventi": eventi[:150], "totale": len(eventi),
            "per_categoria": per_cat, "per_testata": per_testata, "cause": cause_tot.most_common()}


if __name__ == "__main__":
    analizza()
