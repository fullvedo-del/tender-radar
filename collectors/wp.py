"""Zajedničko za domaće izvore koji objave vode na WordPressu (RSS feed kategorije) i za
čitanje roka iz teksta poziva na bosanskom, hrvatskom i srpskom (latinica i ćirilica)."""
from __future__ import annotations

import datetime as dt
import re
import unicodedata

from lxml import etree

from collectors import base

NS = {"content": "http://purl.org/rss/1.0/modules/content/"}

# Rezultati, liste, odluke i slične objave nisu otvoreni pozivi.
SKIP_RX = re.compile(r"\b(?:lista|liste|rezultat\w*|odluk\w*|obrazac|obrasc\w*|potpis\w*|zatvaranj\w*|"
                     r"zatvoren\w*|izmjen\w*|pojašnjenj\w*|rang|obavje[sš]tenj\w*|ugovor\w*|izvje[sš]taj\w*|"
                     r"zapisnik\w*|poni[sš]tenj\w*|produ[zž]enj\w*|prijem radnika|zapo[sš]ljavanj\w*)\b", re.I)
CALL_RX = re.compile(r"\b(?:javn\w*\s+)?(?:poziv\w*|konkurs\w*|natje[cč]aj\w*)\b", re.I)


def feed_items(s, url: str) -> list[dict]:
    """Stavke RSS feeda: naslov, link, datum objave i tekst (bez HTML-a)."""
    r = base.fetch(s, "GET", url)
    try:
        root = etree.fromstring(r.content, etree.XMLParser(resolve_entities=False, no_network=True,
                                                           recover=True))
    except etree.XMLSyntaxError:
        raise base.SourceChanged(f"RSS feed nije ispravan XML: {url}") from None
    if root is None or root.find("channel") is None:
        raise base.SourceChanged(f"RSS feed nema očekivanu strukturu: {url}")
    out = []
    for it in root.iter("item"):
        body = it.findtext("content:encoded", default="", namespaces=NS) or it.findtext("description", default="")
        text = base.clean(re.sub(r"<[^>]+>", " ", body))
        out.append({"title": base.clean(it.findtext("title")), "link": base.clean(it.findtext("link")),
                    "pub": base.iso_date(it.findtext("pubDate")), "text": text})
    return out


_DATE = r"(\d{1,2}\.\s?\d{1,2}\.\s?(?:20)?\d{2})"
_DUE_RX = [
    # "rok za podnošenje prijava je do 15.10.2026", "prijave se podnose zaključno sa 15. 10. 2026."
    re.compile(r"(?:rok\w*|prijave se (?:podnose|primaju)|poziv (?:je )?otvoren|traje)[^.]{0,140}?"
               r"(?:do|zaklju[cč]no\s+(?:sa|s|do)?|najkasnije)\s*(?:dana\s*)?" + _DATE, re.I),
    re.compile(r"(?:рок\w*|пријаве се (?:подносе|примају)|конкурс (?:је )?отворен|траје)[^.]{0,140}?"
               r"(?:до|закључно\s+(?:са|с|до)?|најкасније)\s*(?:дана\s*)?" + _DATE, re.I),
]
_REL_RX = re.compile(r"(\d{1,3})\s*(?:\([^)]*\)\s*)?(?:dana|дана)\s+(?:od|од)\s+(?:dana|дана)\s+"
                     r"(?:objav|објав)", re.I)


# Mjeseci po početku riječi (bez kvačica): bosanski, hrvatski, srpski, engleski, u svim padežima.
_MONTH_STEMS = [("januar", 1), ("jan", 1), ("sijec", 1), ("februar", 2), ("feb", 2), ("veljac", 2),
                ("mart", 3), ("march", 3), ("mar", 3), ("ozuj", 3), ("april", 4), ("apr", 4), ("travanj", 4),
                ("travnj", 4), ("maj", 5), ("may", 5), ("svib", 5), ("jun", 6), ("lipanj", 6), ("lipnj", 6),
                ("jul", 7), ("srpanj", 7), ("srpnj", 7), ("avgust", 8), ("august", 8), ("aug", 8),
                ("kolovoz", 8), ("septemb", 9), ("sep", 9), ("rujan", 9), ("rujn", 9), ("oktob", 10),
                ("octob", 10), ("okt", 10), ("oct", 10), ("listopad", 10), ("novemb", 11), ("nov", 11),
                ("studen", 11), ("decemb", 12), ("dec", 12), ("prosin", 12)]
_KEY_RX = re.compile(r"\b(?:rok\w*|deadline|zakljucno|najkasnije|do dana|prijave? (?:su )?(?:otvorene |traju )?do|"
                     r"prijav\w* se (?:podnose|primaju|salju)|apply by|applications? (?:are )?(?:due|accepted until|open until)|"
                     r"closing date|submission)\b")
_NUM_RX = re.compile(r"\b(\d{1,2})\s?\.\s?(\d{1,2})\s?\.?\s?((?:20)?\d{2})?\b")
_NAME_RX = re.compile(r"\b(\d{1,2})\.?\s+([a-z]{3,10})\s*(\d{4})?\b|\b([a-z]{3,10})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?\b")


def _soft(text: str) -> str:
    """Mala slova bez kvačica, ali s tačkama i zarezima (trebaju za datume)."""
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in t if not unicodedata.combining(ch)).replace("đ", "dj")


def _month(word: str) -> int | None:
    return next((n for stem, n in _MONTH_STEMS if word.startswith(stem)), None)


def _pick(day: int, month: int, year: str | None, pub: str | None) -> str | None:
    """Datum; kad godina nije navedena, uzima se prva koja ne pada prije objave."""
    ref = dt.date.fromisoformat(pub) if pub else base.today()
    years = [int(year) + (2000 if len(year) == 2 else 0)] if year else [ref.year, ref.year + 1]
    for y in years:
        try:
            d = dt.date(y, month, day)
        except ValueError:
            return None
        if year or d >= ref - dt.timedelta(days=7):
            return d.isoformat()
    return None


def due_from(text: str, pub: str | None) -> str | None:
    """Rok iz teksta poziva: izričit datum, ili "N dana od dana objave" računato od datuma
    objave na stranici (objava u službenim novinama može biti dan-dva kasnije). Prepoznaje i
    rok bez godine ("prijave do 3.11.") i s nazivom mjeseca ("rok je 26. novembra 2026")."""
    t = base.clean(text)
    for rx in _DUE_RX:
        m = rx.search(t)
        if m:
            d = base.iso_date(re.sub(r"\s", "", m[1]))
            if d:
                return d
    low = _soft(t)
    for k in _KEY_RX.finditer(low):
        win = low[k.end():k.end() + 90]
        for m in _NAME_RX.finditer(win):
            day, mon, year = (m[1], m[2], m[3]) if m[1] else (m[5], m[4], m[6])
            if _month(mon):
                d = _pick(int(day), _month(mon), year, pub)
                if d:
                    return d
        m = _NUM_RX.search(win)
        if m and 1 <= int(m[2]) <= 12:
            d = _pick(int(m[1]), int(m[2]), m[3], pub)
            if d:
                return d
    m = _REL_RX.search(t)
    if m and pub:
        return (dt.date.fromisoformat(pub) + dt.timedelta(days=int(m[1]))).isoformat()
    return None


def calls_from_feeds(s, urls: list[str], *, key: str, buyer: str, btype: str, region: str,
                     ntype: str = "Javni poziv") -> list[dict]:
    """Otvoreni javni pozivi iz jednog ili više feedova kategorija (isti zapis se ne ponavlja)."""
    today = base.today()
    td, cutoff = today.isoformat(), (today - dt.timedelta(days=60)).isoformat()
    out, seen, total = [], set(), 0
    for url in urls:
        items = feed_items(s, url)
        total += len(items)
        for it in items:
            title, link = it["title"], it["link"]
            if not title or not link.startswith("http") or link in seen:
                continue
            seen.add(link)
            if not CALL_RX.search(title) or SKIP_RX.search(title):
                continue
            due = due_from(it["text"], it["pub"])
            if (due and due < td) or (not due and (it["pub"] or "") < cutoff):
                continue
            sid = link.rstrip("/").rsplit("/", 1)[-1][:120]
            out.append(base.rec(key, sid, title=title, buyer=buyer, url=link, pub=it["pub"], due=due,
                                countries=["BA"], region=region, ctype=base.OTHER, ntype=ntype,
                                btype=btype, kind="P"))
    if not total:
        raise base.SourceChanged("RSS feedovi nemaju nijednu objavu; vjerovatno su premješteni.")
    return out
