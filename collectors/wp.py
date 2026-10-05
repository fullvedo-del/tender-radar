"""Zajedničko za domaće izvore koji objave vode na WordPressu (RSS feed kategorije) i za
čitanje roka iz teksta poziva na bosanskom, hrvatskom i srpskom (latinica i ćirilica)."""
from __future__ import annotations

import datetime as dt
import re

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


def due_from(text: str, pub: str | None) -> str | None:
    """Rok iz teksta poziva: izričit datum, ili "N dana od dana objave" računato od datuma
    objave na stranici (objava u službenim novinama može biti dan-dva kasnije)."""
    t = base.clean(text)
    for rx in _DUE_RX:
        m = rx.search(t)
        if m:
            d = base.iso_date(re.sub(r"\s", "", m[1]))
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
