"""Le testate osservate.

fonte = "home": si legge la homepage e la posizione e' quella reale in pagina.
fonte = "rss":  la homepage non e' leggibile (blocco o pagina costruita in JavaScript);
                si usa il feed, l'ordine e' cronologico e NON entra nei calcoli di posizione.
tipo  = famiglia editoriale (solo descrittiva, non entra nei calcoli dei modelli).
declassa = indirizzi che stanno in alto ma non sono la gerarchia delle notizie
           (caroselli di rubriche, canali tematici).
"""

TESTATE = [
    # quotidiani nazionali storici
    {"id": "corriere", "nome": "Corriere della Sera", "url": "https://www.corriere.it/", "tipo": "Quotidiano storico"},
    {"id": "repubblica", "nome": "la Repubblica", "url": "https://www.repubblica.it/", "tipo": "Quotidiano storico",
     "declassa": r"/dossier/"},
    {"id": "lastampa", "nome": "La Stampa", "url": "https://www.lastampa.it/", "tipo": "Quotidiano storico"},
    {"id": "sole24ore", "nome": "Il Sole 24 Ore", "url": "https://www.ilsole24ore.com/", "tipo": "Quotidiano economico"},
    {"id": "messaggero", "nome": "Il Messaggero", "url": "https://www.ilmessaggero.it/", "tipo": "Quotidiano storico"},
    {"id": "giornale", "nome": "il Giornale", "url": "https://www.ilgiornale.it/", "tipo": "Quotidiano storico"},
    {"id": "libero", "nome": "Libero", "url": "https://www.liberoquotidiano.it/", "tipo": "Quotidiano storico",
     "fonte": "rss", "rss": "https://www.liberoquotidiano.it/rss.xml"},
    {"id": "fatto", "nome": "Il Fatto Quotidiano", "url": "https://www.ilfattoquotidiano.it/", "tipo": "Quotidiano storico"},
    {"id": "avvenire", "nome": "Avvenire", "url": "https://www.avvenire.it/", "tipo": "Quotidiano storico"},
    {"id": "foglio", "nome": "Il Foglio", "url": "https://www.ilfoglio.it/", "tipo": "Quotidiano d'opinione"},
    {"id": "manifesto", "nome": "il manifesto", "url": "https://ilmanifesto.it/", "tipo": "Quotidiano d'opinione"},
    {"id": "domani", "nome": "Domani", "url": "https://www.editorialedomani.it/", "tipo": "Quotidiano d'opinione"},
    {"id": "verita", "nome": "La Verità", "url": "https://www.laverita.info/", "tipo": "Quotidiano d'opinione"},
    {"id": "tempo", "nome": "Il Tempo", "url": "https://www.iltempo.it/", "tipo": "Quotidiano storico"},
    {"id": "qn", "nome": "QN Quotidiano Nazionale", "url": "https://www.quotidiano.net/", "tipo": "Quotidiano storico"},
    {"id": "mattino", "nome": "Il Mattino", "url": "https://www.ilmattino.it/", "tipo": "Quotidiano storico"},
    # nativi digitali
    {"id": "post", "nome": "Il Post", "url": "https://www.ilpost.it/", "tipo": "Nativo digitale"},
    {"id": "open", "nome": "Open", "url": "https://www.open.online/", "tipo": "Nativo digitale"},
    {"id": "huffpost", "nome": "HuffPost Italia", "url": "https://www.huffingtonpost.it/", "tipo": "Nativo digitale"},
    {"id": "today", "nome": "Today", "url": "https://www.today.it/", "tipo": "Nativo digitale"},
    # televisioni e agenzie
    {"id": "ansa", "nome": "ANSA", "url": "https://www.ansa.it/", "tipo": "Agenzia",
     "declassa": r"/canale_(lifestyle|saluteebenessere|tecnologia|viaggiart|motori|terraegusto|moda)"},
    {"id": "tgcom24", "nome": "TgCom24", "url": "https://www.tgcom24.mediaset.it/", "tipo": "Testata TV"},
    {"id": "skytg24", "nome": "Sky TG24", "url": "https://tg24.sky.it/", "tipo": "Testata TV"},
    {"id": "rainews", "nome": "RaiNews", "url": "https://www.rainews.it/", "tipo": "Testata TV",
     "fonte": "rss", "rss": "https://www.rainews.it/rss/tutti"},
    # sport
    {"id": "gazzetta", "nome": "La Gazzetta dello Sport", "url": "https://www.gazzetta.it/", "tipo": "Quotidiano sportivo"},
]

PER_ID = {t["id"]: t for t in TESTATE}
