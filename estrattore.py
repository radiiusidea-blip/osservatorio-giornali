"""Legge la homepage di una testata e restituisce i titoli nell'ordine in cui
compaiono, con un peso che dice quanto sono in evidenza.

Niente librerie esterne: un piccolo albero DOM costruito con html.parser.
La posizione in pagina e' l'ordine del primo link a quell'articolo; il peso
viene da h1/h2/h3, dalla lunghezza del titolo e dalle classi «apertura/top».
"""
import html
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

VUOTI = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
         "meta", "source", "track", "wbr"}
SALTA = {"script", "style", "noscript", "svg", "template", "iframe"}
TITOLI = {"h1": 3.0, "h2": 2.0, "h3": 1.4, "h4": 1.1}
CLASSI_FORTI = re.compile(r"(apertura|opening|hero|main-?news|primo-?piano|top-?story|lead|big|first)", re.I)
CLASSI_DEBOLI = re.compile(r"(footer|menu|nav|sidebar|ticker|breaking|ultim|flash|banner|adv|sponsor|newsletter|cookie|social|related)", re.I)
PIU_LETTI = re.compile(r"pi[uù]\s+(lett[ie]|vist[ie]|cliccat[ie]|condivis[ie]|commentat[ie]|popolari)|most\s+(read|viewed|popular)|trending|top\s*10", re.I)


class Nodo:
    __slots__ = ("tag", "attr", "figli", "padre", "testo")

    def __init__(self, tag, attr, padre):
        self.tag, self.attr, self.padre = tag, attr, padre
        self.figli, self.testo = [], []

    def classi(self):
        return (self.attr.get("class") or "") + " " + (self.attr.get("id") or "")


class Albero(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.radice = Nodo("root", {}, None)
        self.cur = self.radice
        self.salta = 0

    def handle_starttag(self, tag, attrs):
        if self.salta:
            if tag in SALTA:
                self.salta += 1
            return
        if tag in SALTA:
            self.salta = 1
            return
        n = Nodo(tag, {k: (v or "") for k, v in attrs}, self.cur)
        self.cur.figli.append(n)
        if tag not in VUOTI:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        if not self.salta and tag not in SALTA:
            self.cur.figli.append(Nodo(tag, {k: (v or "") for k, v in attrs}, self.cur))

    def handle_endtag(self, tag):
        if self.salta:
            if tag in SALTA:
                self.salta -= 1
            return
        n = self.cur
        while n is not self.radice and n.tag != tag:
            n = n.padre
        if n is not self.radice:
            self.cur = n.padre

    def handle_data(self, data):
        if not self.salta and data.strip():
            self.cur.figli.append(data)


def testo_di(n):
    out = []
    pila = [n]
    while pila:
        x = pila.pop()
        if isinstance(x, str):
            out.append(x)
        else:
            pila.extend(reversed(x.figli))
    return re.sub(r"\s+", " ", html.unescape(" ".join(out))).strip()


def pezzi_di(n):
    """Testi dei singoli blocchi dentro il link, nell'ordine (occhiello, titolo, sommario...)."""
    out = []
    for f in n.figli:
        if isinstance(f, str):
            t = f.strip()
        elif f.tag in ("span", "div", "p", "strong", "b", "em", "h1", "h2", "h3", "h4", "h5"):
            sub = pezzi_di(f)
            if sub:
                out.extend(sub)
                continue
            t = testo_di(f)
        else:
            continue
        t = re.sub(r"\s+", " ", html.unescape(t)).strip()
        if t:
            out.append(t)
    return out


def primo_titolo(n):
    pila = list(reversed(n.figli))
    while pila:
        x = pila.pop()
        if isinstance(x, str):
            continue
        if x.tag in TITOLI:
            return x
        pila.extend(reversed(x.figli))
    return None


def pulisci_titolo(t):
    t = re.sub(r"\s+", " ", t).strip(" |·-–—")
    t = re.sub(r"^\+?\s*leggi tutto\s*:?\s*", "", t, flags=re.I)
    t = re.sub(r"^[Vv]ai alla pagina dell['’]articolo\s*:?\s*", "", t)
    t = re.sub(r"^[Ll]eggi\s+(?=[A-ZÀ-Ü«“\"])", "", t)
    t = re.sub(r"^(video|foto|live|diretta|esclusivo|l'intervista|il commento|ascolta)\s*[|:·-]\s*", "", t, flags=re.I)
    return t


def url_articolo(url, dominio):
    p = urlparse(url)
    host = p.netloc.lower()
    if not host.endswith(dominio):
        return False
    path = p.path.rstrip("/")
    if path.count("/") < 1 or re.search(r"\.(jpg|png|webp|pdf|mp3)$", path, re.I) \
            or re.search(r"/(autori|autore|author|tag|tags|podcast|newsletter|abbonamenti|speciali)/", path + "/", re.I):
        return False
    ultimo = path.rsplit("/", 1)[-1]
    # un articolo ha uno slug lungo o un identificativo numerico
    return ultimo.count("-") >= 3 or bool(re.search(r"\d{5,}", path)) or len(ultimo) > 40


def estrai(html_testo, base_url, max_voci=60, declassa=None, oggi=None):
    """Ritorna (titoli, piu_letti). titoli = [{url, titolo, pos, peso, livello}]."""
    a = Albero()
    try:
        a.feed(html_testo)
    except Exception:
        pass
    dominio = urlparse(base_url).netloc.lower().replace("www.", "")
    visti, voci, letti = {}, [], []

    # visita in ordine di documento tenendo il contesto (titolo, classi, sezione «più letti»)
    def visita(n, ctx):
        if isinstance(n, str):
            return
        ctx = dict(ctx)
        cls = n.classi()
        if n.tag in TITOLI:
            ctx["h"] = max(ctx.get("h", 0), TITOLI[n.tag])
        if cls.strip():
            if CLASSI_FORTI.search(cls):
                ctx["forte"] = True
            if CLASSI_DEBOLI.search(cls):
                ctx["debole"] = True
            if PIU_LETTI.search(cls.replace("-", " ").replace("_", " ")):
                ctx["letti"] = True
        if n.tag in ("section", "div", "aside", "ul", "ol") and not ctx.get("letti"):
            # intestazione della sezione: primi testi brevi del contenitore
            for f in n.figli[:4]:
                if isinstance(f, str):
                    t = f
                elif f.tag in ("h2", "h3", "h4", "span", "div", "p", "header", "strong"):
                    t = testo_di(f)[:60]
                else:
                    continue
                if PIU_LETTI.search(t) and len(t) < 60:
                    ctx["letti"] = True
                    break
        if n.tag == "a" and n.attr.get("href"):
            url = urljoin(base_url, n.attr["href"]).split("#")[0].split("?")[0]
            if url_articolo(url, dominio):
                t = pulisci_titolo(testo_di(n))
                pz = [x for x in pezzi_di(n) if len(x.split()) >= 4]
                if len(pz) > 1:
                    t = pulisci_titolo(pz[0])
                h = ctx.get("h", 0)
                # titolo dentro il link (<a><article><h2>...): il primo titolo discendente
                tit = primo_titolo(n)
                if tit is not None:
                    h = max(h, TITOLI[tit.tag])
                    t = pulisci_titolo(testo_di(tit)) or t
                elif n.attr.get("aria-label") and len(n.attr["aria-label"].split()) >= 4:
                    t = pulisci_titolo(n.attr["aria-label"])
                if len(t) >= 25 and len(t.split()) >= 4 and len(t) < 300 \
                        and not re.match(r"vai alla pagina", t, re.I):
                    if ctx.get("letti"):
                        if url not in [x["url"] for x in letti]:
                            letti.append({"url": url, "titolo": t, "pos": len(letti) + 1})
                    elif url not in visti:
                        peso = 1.0 + h
                        if ctx.get("forte"):
                            peso += 1.0
                        if ctx.get("debole"):
                            peso -= 1.5
                        voce = {"url": url, "titolo": t, "peso": peso, "_h": h}
                        visti[url] = voce
                        voci.append(voce)
                    else:
                        # stesso articolo linkato due volte (foto, titolo, sommario):
                        # vale il link che sta in un titolo
                        v = visti[url]
                        if h > v["_h"]:
                            v["peso"] += h - v["_h"]
                            v["_h"] = h
                            v["titolo"] = t
            return
        for f in n.figli:
            visita(f, ctx)

    import sys
    sys.setrecursionlimit(20000)
    visita(a.radice, {})

    # articoli vecchi (data nell'indirizzo oltre 4 giorni fa) e rubriche declassate
    import datetime as _dt
    oggi = oggi or _dt.date.today()
    tenute = []
    for v in voci:
        m = re.search(r"/(20\d\d)/(\d\d)/(\d\d)/", v["url"]) or re.search(r"/(20\d\d)/(\d\d)/", v["url"])
        if m:
            try:
                solo_mese = m.re.groups == 2
                d = _dt.date(int(m.group(1)), int(m.group(2)), 28 if solo_mese else int(m.group(3)))
                if (oggi - d).days > (35 if solo_mese else 4):
                    continue
            except ValueError:
                pass
        if declassa and re.search(declassa, v["url"]):
            v["peso"] = min(v["peso"], 0.5)
        tenute.append(v)
    voci = tenute

    # i link «deboli» (menu, ticker) restano ma scendono in fondo
    buoni = [v for v in voci if v["peso"] > 0.5]
    deboli = [v for v in voci if v["peso"] <= 0.5]
    ordinate = buoni + deboli
    for i, v in enumerate(ordinate[:max_voci], 1):
        v["pos"] = i
        v.pop("_h", None)
    return ordinate[:max_voci], letti[:15]


def estrai_rss(xml_testo, max_voci=40):
    voci = []
    for i, item in enumerate(re.findall(r"<item\b.*?</item>", xml_testo, re.S)[:max_voci], 1):
        t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item, re.S)
        l = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", item, re.S)
        if t and l:
            voci.append({"url": l.group(1).strip(), "titolo": pulisci_titolo(html.unescape(t.group(1))),
                         "peso": 1.0, "pos": i})
    return voci, []
