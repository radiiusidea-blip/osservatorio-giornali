"""Categoria di un articolo: prima dall'indirizzo (le sezioni del giornale),
poi dalle parole del titolo. Le categorie sono le stesse per tutte le testate."""
import re

CATEGORIE = ["Politica", "Economia", "Cronaca", "Esteri", "Sport", "Cultura e spettacoli",
             "Scienza e tecnologia", "Salute", "Ambiente e meteo", "Religione", "Opinioni", "Stili di vita", "Altro"]

# sezione nell'indirizzo → categoria (l'ordine conta: vince la prima che si trova)
DA_URL = [
    (r"/(politica-estera|cronaca-internazionale|esteri|internazionale)", "Esteri"),
    (r"/(chiesa|papa|vaticano|religion)", "Religione"),
    (r"/(giustizia|cronaca-giudiziaria)", "Cronaca"),
    (r"/(oroscopo|lotto|estrazioni|ricette)", "Stili di vita"),
    (r"/(opinion[ie]|commenti|editorial[ie]|lettere|idee|blog|rubriche|analisi|il-punto|punti-di-vista|cartoline)/", "Opinioni"),
    (r"/(politica|interni|governo|parlamento|elezioni)/", "Politica"),
    (r"/(economia|finanza|mercati|soldi|lavoro|fisco|risparmio|impresa|aziende|borsa|norme-e-tributi|tasse|consumi|casa)/", "Economia"),
    (r"/(esteri|mondo|world|internazionale|europa|medio-oriente|ucraina|usa|guerra)/", "Esteri"),
    (r"/(sport|calcio|serie-a|tennis|formula-1|f1|motogp|basket|ciclismo|volley|olimpiadi|motomondiale|nba|champions-league)/", "Sport"),
    (r"/(cronaca|cronache|cronaca-giudiziaria|cronaca-nera|giudiziaria|attualita|italia|roma|milano|napoli|torino|bologna|firenze|genova|palermo|bari|venezia)/", "Cronaca"),
    (r"/(cultura|spettacoli|spettacolo|cinema|musica|tv|televisione|libri|arte|teatro|people|gossip|show|vip|sanremo)/", "Cultura e spettacoli"),
    (r"/(scienza|scienze|tecnologia|tech|hi-tech|innovazione|spazio|digitale|intelligenza-artificiale|canale_tecnologia|canale_scienza)/", "Scienza e tecnologia"),
    (r"/(salute|medicina|sanita|benessere|canale_saluteebenessere)/", "Salute"),
    (r"/(ambiente|meteo|clima|green|sostenibilita|animali|canale_ambiente)/", "Ambiente e meteo"),
    (r"/(lifestyle|moda|viaggi|cucina|food|motori|design|bellezza|oroscopo|gusto|canale_lifestyle|canale_motori|canale_viaggiart|canale_terraegusto)/", "Stili di vita"),
]

DA_TITOLO = [
    (r"\b(meloni|schlein|conte|salvini|tajani|governo|ministr[oa]|parlament|camera|senato|legge elettorale|"
     r"premierato|fiducia|decreto|manovra|pd|fdi|lega|forza italia|m5s|elezioni|referendum|quirinale|mattarella|vannacci|calenda|renzi)\b", "Politica"),
    (r"\b(pil|inflazione|bce|borsa|spread|tass[ei]|pension[ie]|bonus|stipendi|mutu[io]|bollett[ae]|carburant[ei]|"
     r"benzina|gasolio|sciopero|istat|imprese|banc[ah]e?|lavoratori|euro al litro|prezz[io]|debito|ocse|fmi|"
     r"crescita|petrolio|borse?|aziende|mercato|dazi|tim|stellantis|eni|affitt[io])\b", "Economia"),
    (r"\b(trump|putin|zelensky|netanyahu|hamas|israele|gaza|ucraina|russia|cina|usa|stati uniti|iran|francia|"
     r"germania|macron|ue|nato|onu|kiev|mosca|libano|siria|venezuela|cisgiordania|gran bretagna|brasile|"
     r"lula|bolsonaro|spagna|sánchez|sanchez|londra|parigi|washington|casa bianca|giappone|india|africa|"
     r"argentina|messico|turchia|erdogan|ohio|texas|california|starmer|merz|von der leyen)\b", "Esteri"),
    (r"\b(serie a|juventus|juve|inter|milan|napoli|roma|lazio|sinner|ferrari|gol|partita|allenatore|champions|"
     r"campionato|nazionale|mondiali|tennis|f1|motogp|figc|coni|calciomercato|basket|nba|eurolega|messi|"
     r"malagò|malago|atalanta|fiorentina|ct|scudetto|olimpiadi|pallavolo|ciclismo)\b", "Sport"),
    (r"\b(omicidio|uccis[oa]|morto|morta|morti|arrestat[oi]|indagat[oi]|incidente|carabinieri|polizia|"
     r"femminicidio|processo|procura|garlasco|condannat[oi]|rapina|furto|scomparsa|tragedia|inchiesta|"
     r"mafia|camorra|'ndrangheta|csm|pm|magistrat[io]|giudic[ei]|sequestr[oa]|truffa|violenz[ae]|aggression[ei]|"
     r"precipita|annegat[oi]|ferit[oi]|vittim[ae])\b", "Cronaca"),
    (r"\b(film|serie tv|cantante|concerto|album|festival|attore|attrice|libro|mostra|sanremo|netflix|x factor|"
     r"grande fratello|teatro|regista|libri|un posto al sole|fiction|tv|rai|mediaset|benigni|cantautore)\b", "Cultura e spettacoli"),
    (r"\b(papa|leone xiv|chiesa|vescov[oi]|vaticano|cattolic[ia]|santo|santa sede|fede)\b", "Religione"),
    (r"\b(oroscopo|lotto|superenalotto|ricetta|termosifoni|longevità)\b", "Stili di vita"),
    (r"\b(nobel|scienziat[ie]|ricerca|intelligenza artificiale|ia|ai|apple|google|spazio|nasa|smartphone|"
     r"chatgpt|scoperta|tecnologia|openai|anthropic|microsoft|meta|robot|satellit[ei])\b", "Scienza e tecnologia"),
    (r"\b(salute|tumore|cancro|virus|vaccino|ospedale|medic[io]|malattia|dieta|sanità|epidemia)\b", "Salute"),
    (r"\b(meteo|allerta|maltempo|temporal[ei]|caldo|clima|terremoto|alluvione|incendi?o?|neve|ciclone)\b", "Ambiente e meteo"),
]


def categoria_di(url, titolo, testata=None):
    u = url.lower()
    host = re.match(r"https?://([^/]+)", u)
    sotto = host.group(1).split(".")[0] if host else ""
    # sottodominio come sezione (sport.quotidiano.net, milano.corriere.it)
    path = "/" + sotto + "/" + re.sub(r"https?://[^/]+/?", "", u)
    path = re.sub(r"/([a-z_]+)-[a-z-]+(?=/)", lambda m: m.group(0) + "/" + m.group(1) + "/", path)
    if testata and testata.get("tipo") == "Quotidiano sportivo" and not re.search(r"/(cronaca|politica|economia)/", path):
        return "Sport"
    for rx, cat in DA_URL:
        if re.search(rx, path):
            return cat
    # poi il titolo, poi le parole dello slug (spesso più esplicite del titolo)
    slug = re.sub(r"[-_/]+", " ", u.rsplit("/", 2)[-2] if u.endswith("/") else u.rsplit("/", 1)[-1])
    for testo in ((titolo or "").lower(), slug):
        for rx, cat in DA_TITOLO:
            if re.search(rx, testo):
                return cat
    return "Altro"
