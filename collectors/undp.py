"""UNDP: otvorene objave s procurement-notices.undp.org.

robots.txt tog sajta zabranjuje automatski pristup svim stranicama ("Disallow: /"),
pa HTML tabelu ne čitamo. Koristimo zvanični, dokumentovani RSS 1.0 feed
"All UNDP Procurement Notices" (vidi /proc_notices_rss_feed.cfm): jedan zahtjev
po pokretanju. Feed ne daje vrstu postupka (RFP, RFQ ...) ni sat roka.
"""
from __future__ import annotations

import datetime as dt
import re

from lxml import etree

from . import base

META = {
    "key": "UNDP",
    "name": "UNDP",
    "home": "https://procurement-notices.undp.org/",
    "scope": "Sve otvorene objave s UNDP-ovog portala nabavki (UNDP, UNCDF, UNV) "
             "u cijelom svijetu, iz zvaničnog RSS feeda.",
}

FEED = "https://procurement-notices.undp.org/rss_feeds/rss.xml"
NS = {"r": "http://purl.org/rss/1.0/",
      "dc": "http://purl.org/dc/elements/1.1/",
      "u": "http://procurement-notices.undp.org/rss_feed/spec/"}

# Feed je deklarisan kao ISO-8859-1, a sadrži Windows-1252 znakove (’ – “ ” Š).
_CP1252 = {i: bytes([i]).decode("cp1252", "ignore") for i in range(0x80, 0xA0)}
# UNDP nazivi država koje base.country_code ne prepoznaje ili pogrešno mapira.
_CC = {"congo dem republic": "CD", "palestinian territories": "PS",
       "korea democratic people s republic of": "KP", "saint vincent grenadines": "VC",
       "virgin islands uk": "VG", "saint helena": "SH"}
# Objave koje nisu poziv za nabavku: otkazivanja, dodjele, info-sesije, prodaja vozila.
_SKIP = re.compile(r"cancel|annul|contract award|award notice|webinar|information session"
                   r"|supplier profile|s.enregistrer|sale of (used )?vehicle", re.I)
_REF = re.compile(r"[A-Z]{2,6}(-[A-Z0-9]+)*-\d{3,}[\w,-]*")
_AGENCY = re.compile(r"(UN|PNUD)[A-Za-z ]{0,10}")


def _t(item, tag: str) -> str:
    return base.clean((item.findtext(tag, "", NS) or "").translate(_CP1252))


def _title(s: str) -> str:
    """Briše '?' koje feed upisuje umjesto ćirilice i sl.; '' ako naziv nije čitljiv."""
    s = re.sub(r"(?<!\S)[^\w\s]*\?[^\w\s]*(?!\S)", " ", s)
    s = base.clean(re.sub(r"(?<!\S)\?+(?=\w)", "", s))
    return s if len(re.findall(r"[^\W\d_]", _REF.sub("", s))) >= 4 else ""


def _nice(name: str) -> str:
    """'BOSNIA AND HERZEGOVINA' -> 'Bosnia and Herzegovina'; mješovita slova ostaju."""
    if re.search(r"[a-z]", name.replace("d'", "")):
        return name

    def word(m):
        w = m[0]
        if w in ("PDR", "UK"):
            return w
        small = m.start() and w.lower() in ("and", "of", "the", "d", "s")
        return w.lower() if small else w.capitalize()
    return re.sub(r"[A-Za-z]+", word, name)


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("undp", {})
    want = {x.upper() for x in c.get("countries", [])}  # ISO2; prazno = sve države
    r = base.fetch(base.session(), "GET", FEED)
    try:
        root = etree.fromstring(r.content, etree.XMLParser(resolve_entities=False,
                                                           no_network=True))
    except etree.XMLSyntaxError:
        raise base.SourceChanged("UNDP: RSS feed nije ispravan XML") from None
    items = root.findall("r:item", NS)
    if root.find("r:channel", NS) is None or not items:
        raise base.SourceChanged("UNDP: RSS feed nema očekivanu strukturu ni objave")

    today = base.today()
    td, cutoff = today.isoformat(), (today - dt.timedelta(days=60)).isoformat()
    out, parsed, dated = [], 0, 0
    for it in items:
        link, sub, cty = _t(it, "r:link"), _t(it, "dc:subject"), _t(it, "u:duty_station_cty")
        m = re.search(r"(nego|notice)_id=(\d+)", link)
        if not m or not sub:
            continue
        parsed += 1
        if m[1] == "nego":  # Quantum: "<ref> - <naziv> - <agencija> - <DRŽAVA>"
            head, _, tail = sub.rpartition(" - ")
            title, agency = (head, tail) if head and _AGENCY.fullmatch(tail) else (sub, "UNDP")
            ref = _t(it, "r:title").split(" - ", 1)[0]
            ref = ref if _REF.fullmatch(ref) else None
        else:  # starije objave: "<naziv> - <kancelarija>"
            ds = _t(it, "u:duty_station")
            title = sub[:-len(ds) - 3] if ds and sub.endswith(" - " + ds) else sub
            agency, ref = ("UN Women" if "un women" in ds.lower() else "UNDP"), None
        due = base.iso_date(_t(it, "u:deadline")) or base.iso_date(_t(it, "r:description"))
        pub = base.iso_date(_t(it, "dc:date"))
        dated += bool(due)
        title = _title(title) or "(naziv nije čitljiv u RSS feedu; otvorite objavu)"
        code = _CC.get(base.norm(cty)) or base.country_code(cty)
        if (_SKIP.search(title) or (want and code not in want)
                or (due and due < td) or (not due and (pub or "") < cutoff)):
            continue
        out.append(base.rec(
            META["key"], f"{m[1]}-{m[2]}", title=title, url=link, pub=pub, due=due,
            buyer=f"{agency} {_nice(cty)}".strip(), countries=[code] if code else None,
            btype="un", ref=ref))

    if not parsed or not dated:
        raise base.SourceChanged("UNDP: RSS feed je promijenjen (nema naslova ili rokova)")
    if not out and not want:
        raise base.SourceChanged("UNDP: feed nema nijednu otvorenu objavu; vjerovatno je zastario")
    return out


if __name__ == "__main__":
    base.cli(collect, META)
