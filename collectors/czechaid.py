"""CzechAid (Česká rozvojová agentura): tenderi (zadávací řízení) i pozivi za dotacije (dotační výzvy).

Agencija ih objavljuje kao vijesti na czechaid.gov.cz, bez RSS-a. Kolektor čita prve stranice
vijesti i listu dotacija, zadržava samo tendere i pozive, a rok čita sa stranice same objave.
"""
from __future__ import annotations

import datetime as dt
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from collectors import base

META = {
    "key": "CZA",
    "name": "CzechAid (Češka razvojna agencija)",
    "home": "https://czechaid.gov.cz/aktivity/aktuality",
    "scope": "Tenderi (zadávací řízení) i otvoreni pozivi za dotacije (dotační výzvy) Češke "
             "razvojne agencije, u svim zemljama u kojima radi.",
}
BASE = "https://czechaid.gov.cz"
NEWS = [BASE + "/aktivity/aktuality", BASE + "/aktivity/aktuality?page=1",
        BASE + "/aktivity/aktuality?page=2"]
GRANTS = BASE + "/dotace"
TENDER_RX = re.compile(r"zadávací řízení|veřejn\w* zakázk|tender procedure|call for tenders?|"
                       r"výběrové řízení|procurement", re.I)
GRANT_RX = re.compile(r"dotační výzv|výzva k předkládání|výzva k podávání|call for proposals", re.I)
SKIP_RX = re.compile(r"zrušen|cancel|výsledk|uzavřen|oznámení o výběru|rozhodnutí o|results?\b", re.I)
CZ_MONTHS = {"ledna": 1, "unora": 2, "brezna": 3, "dubna": 4, "kvetna": 5, "cervna": 6,
             "cervence": 7, "srpna": 8, "zari": 9, "rijna": 10, "listopadu": 11, "prosince": 12}
CZ_COUNTRIES = {"bosn": "BA", "srbsk": "RS", "kosov": "XK", "gruzi": "GE", "moldav": "MD",
                "ukrajin": "UA", "kambodz": "KH", "etiopi": "ET", "zambi": "ZM", "mongolsk": "MN",
                "palestin": "PS", "libanon": "LB", "irak": "IQ", "afghanist": "AF", "senegal": "SN"}
_DATE = r"(\d{1,2}\.\s?\d{1,2}\.\s?20\d\d)"
_EN_DATE = (r"((?:\d{1,2}(?:st|nd|rd|th)?\s+)?[A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+20\d\d|"
            r"\d{1,2}(?:st|nd|rd|th)?\s+[A-Z][a-z]+\s+20\d\d|\d{1,2}\.\s?\d{1,2}\.\s?20\d\d)")
DUE_RX = [
    re.compile(r"(?:lhůt\w*|termín\w*)\s+(?:pro|k)\s+(?:podání|předložení|doručení|podávání)\s+"
               r"(?:nabídek|žádostí|přihlášek|projektových žádostí|projektů)[^0-9]{0,140}?" + _DATE
               + r"(?:[^0-9]{0,25}(\d{1,2}[:.]\d{2}))?", re.I),
    re.compile(r"(?:submission deadline|deadline for (?:the )?submission[^.]{0,60}?|deadline)"
               r"[^0-9]{0,60}?" + _EN_DATE + r"(?:[^0-9]{0,25}(\d{1,2}[:.]\d{2}))?", re.I),
]


def _cz_date(text: str) -> str | None:
    t = base.norm(text)
    m = re.search(r"\b(\d{1,2}) ([a-z]+) (20\d\d)\b", t)
    if m and m[2] in CZ_MONTHS:
        return f"{m[3]}-{CZ_MONTHS[m[2]]:02d}-{int(m[1]):02d}"
    return base.iso_date(text)


def _due(text: str):
    t = base.clean(text)
    for rx in DUE_RX:
        m = rx.search(t)
        if m:
            raw = re.sub(r"(\d)(?:st|nd|rd|th)\b", r"\1", m[1])
            d = base.iso_date(re.sub(r"(?<=\.)\s+", "", raw))
            if d:
                return d, (m[2] or "").replace(".", ":") or None
    return None, None


def _countries(text: str) -> list[str]:
    t = base.norm(text)
    out = [c for k, c in CZ_COUNTRIES.items() if re.search(r"\b" + k, t)]
    return out + [c for c in base.countries_in(text) if c not in out]


def _ctype(title: str, grant: bool) -> str:
    t = base.norm(title)
    if grant:
        return base.OTHER
    if re.search(r"\bdodav|\bdodavk|\bsupply|\bdelivery|\bnakup", t):
        return base.GOODS
    if re.search(r"\bstavb|\bstavebn|\bvystavb|\brekonstrukc|\bconstruction|\bworks\b", t):
        return base.WORKS
    return base.SERVICES


def _cards(s) -> list[dict]:
    """Kandidati sa stranica vijesti i sa liste dotacija: naslov, link, datum, je li grant."""
    out: dict[str, dict] = {}
    for url in NEWS:
        soup = BeautifulSoup(base.fetch(s, "GET", url).text, "lxml")
        cards = soup.select("div.articleIn")
        if url == NEWS[0] and not cards:
            raise base.SourceChanged("CzechAid: stranica vijesti nema očekivanu strukturu (div.articleIn)")
        for c in cards:
            a = max(c.find_all("a", href=True), key=lambda x: len(x.get_text(strip=True)), default=None)
            if not a:
                continue
            title, link = base.clean(a.get_text(" ")), urljoin(url, a["href"])
            grant = bool(GRANT_RX.search(title))
            if not (grant or TENDER_RX.search(title)) or SKIP_RX.search(title):
                continue
            out.setdefault(link, {"title": title, "link": link, "pub": _cz_date(c.get_text(" ")),
                                  "grant": grant, "teaser": base.clean(c.get_text(" "))})
        time.sleep(0.8)
    soup = BeautifulSoup(base.fetch(s, "GET", GRANTS).text, "lxml")
    for a in soup.find_all("a", href=True):
        link, title = urljoin(GRANTS, a["href"]), base.clean(a.get_text(" "))
        if "/dotace/" not in link or not GRANT_RX.search(title) or SKIP_RX.search(title + " " + link):
            continue
        box = a.find_parent(["article", "li", "div"])
        upd = re.search(r"aktualizace ke dni\s*" + _DATE, box.get_text(" ")) if box else None
        out.setdefault(link, {"title": title, "link": link, "grant": True, "teaser": title,
                              "pub": base.iso_date(re.sub(r"\s", "", upd[1])) if upd else None})
    return list(out.values())


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("cza", {})
    max_details = int(c.get("max_details", 30))
    s = base.session()
    today = base.today()
    td, cutoff = today.isoformat(), (today - dt.timedelta(days=60)).isoformat()
    out = []
    for i, it in enumerate(_cards(s)):
        due, due_time = None, None
        if i < max_details:
            try:
                page = BeautifulSoup(base.fetch(s, "GET", it["link"]).text, "lxml")
                due, due_time = _due(page.get_text(" "))
            except (base.SourceBlocked, RuntimeError):
                pass
            time.sleep(0.8)
        if (due and due < td) or (not due and (it["pub"] or "") < cutoff):
            continue
        sid = it["link"].rstrip("/").rsplit("/", 1)[-1][:120]
        out.append(base.rec(
            META["key"], sid, title=it["title"], buyer="Česká rozvojová agentura (CzechAid)",
            url=it["link"], pub=it["pub"], due=due, due_time=due_time,
            countries=_countries(it["title"] + " " + it["teaser"]), btype="bilateral",
            ctype=_ctype(it["title"], it["grant"]),
            ntype="Dotační výzva" if it["grant"] else "Zadávací řízení",
            kind="P" if it["grant"] else None))
    return out


if __name__ == "__main__":
    base.cli(collect, META)
