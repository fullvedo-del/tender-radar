"""RCC (Regional Cooperation Council, Sarajevo): stranica „Open Calls“.

Svi otvoreni pozivi (konsultantske usluge, individualni konsultanti, nabavke) su na jednoj
stranici; pozivi nemaju vlastitu stranicu, pa je link zapisa sama lista. Oglasi za posao
su na /vacancies i nisu uključeni. Nema RSS-a ni API-ja; robots.txt ništa ne zabranjuje.
"""
from __future__ import annotations

import datetime as dt
import re
import time

from bs4 import BeautifulSoup

from . import base

META = {
    "key": "RCC",
    "name": "RCC (Regional Cooperation Council)",
    "home": "https://www.rcc.int/open_calls",
    "scope": "Svi otvoreni pozivi sa RCC stranice „Open Calls“ (konsultantske usluge, "
             "individualni konsultanti, druge nabavke); oglasi za zapošljavanje nisu uključeni. "
             "Poziv koji ne imenuje državu vodi se pod svih šest zemalja Zapadnog Balkana.",
}

URL = "https://www.rcc.int/open_calls"
BUYER = "Regional Cooperation Council (RCC) Secretariat"
REGION = "Regionalno (Zapadni Balkan)"
WB6 = ["AL", "BA", "XK", "ME", "MK", "RS"]  # područje rada RCC-a za pozive koji ne imenuju državu
IND_RE = re.compile(r"\bindividual (?:consultant|expert)s?\b", re.I)
ORG_RE = re.compile(r"\b(?:consult(?:ancy|ing) (?:compan|firm)|compan(?:y|ies)\b|legal entit|consorti|firms?\b)", re.I)
NO_DEADLINE_DAYS = 60
# Države koje se u RCC pozivima mogu pojaviti (SEECP i susjedstvo); grupe poput „WB6“ se ne razlažu.
COUNTRY_RE = re.compile(r"\b(Albania|Bosnia and Herzegovina|Bulgaria|Croatia|Cyprus|Greece|Kosovo|"
                        r"Moldova|Montenegro|(?:North )?Macedonia|Romania|Serbia|Slovenia|"
                        r"Türkiye|Turkey|Ukraine)\b")
CALL_RE = re.compile(r"\b(?:call for (?:expressions? of interest|proposals|tenders?|applications)|"
                     r"request for (?:proposals|quotations?|expressions? of interest)|"
                     r"invitation to (?:tender|bid)|expressions? of interest)\b", re.I)
KINDS = ((base.SERVICES, r"consult\w*|experts?|services?"),
         (base.GOODS, r"supply|goods|equipment"),
         (base.WORKS, r"works|construction|renovation"))


def _ctype(text: str) -> str | None:
    """Vrsta ugovora po riječi koja se u naslovu/opisu javlja prva."""
    hits = [(m.start(), k) for k, pat in KINDS
            for m in [re.search(rf"\b(?:{pat})\b", text, re.I)] if m]
    return min(hits)[1] if hits else None


def _page(s, url: str) -> BeautifulSoup:
    # Sajt povremeno vrati HTTP 200 s porukom o padu baze; tada sačekati i pokušati ponovo.
    for _ in range(3):
        r = base.fetch(s, "GET", url)
        if "Could not connect to DB" not in r.text:
            return BeautifulSoup(r.text, "lxml")
        time.sleep(10)
    raise RuntimeError("RCC: sajt javlja grešku baze podataka, pokušati kasnije")


def collect(cfg: dict) -> list[dict]:
    url = cfg.get("rcc", {}).get("url", URL)
    box = _page(base.session(), url).select_one("main div.calls")
    if box is None or "open calls" not in base.norm(box.h2.get_text() if box.h2 else ""):
        raise base.SourceChanged("RCC: nije pronađena lista otvorenih poziva")
    items = box.select("div.doc-item")
    if not items:
        if re.search(r"\bno (?:open|active|current)\b|\bcurrently no\b", box.get_text(" "), re.I):
            return []
        raise base.SourceChanged("RCC: lista poziva je prazna, a nema poruke da poziva nema")

    today = base.today()
    oldest = (today - dt.timedelta(days=NO_DEADLINE_DAYS)).isoformat()
    out = []
    for it in items:
        head = base.clean(it.select_one("p.title").get_text(" ")) if it.select_one("p.title") else ""
        m = re.match(r"(\d{2,4}[-/]\d{2,4})\s+(.+)", head)  # „065-026 Naziv poziva“
        ref, title = (m[1], m[2]) if m else (None, head)
        spans = {base.norm(b.get_text()): b.find_next_sibling("span")
                 for b in it.select("p.bg-light strong")}
        pub, due = (base.iso_date(spans[k].get_text()) if spans.get(k) else None
                    for k in ("published", "deadline"))
        if not title or not (pub or due):
            raise base.SourceChanged("RCC: poziv bez naslova ili datuma; struktura se promijenila")
        if (due and due < today.isoformat()) or (not due and pub < oldest):
            continue
        desc = next((base.clean(p.get_text(" ")) for p in it.find_all("p", class_=False)
                     if not p.find("a")), "")
        link = it.select_one("a[href*='call_id=']")
        cid = re.search(r"call_id=(\d+)", link["href"])[1] if link else (ref or base.norm(title)[:80])
        text = f"{title} {desc}"
        countries = list(dict.fromkeys(COUNTRY_RE.findall(text)))
        ind, org = bool(IND_RE.search(text)), bool(ORG_RE.search(text))
        call = CALL_RE.search(title)
        out.append(base.rec(
            META["key"], cid, title=title, buyer=BUYER, url=url, pub=pub, due=due,
            countries=countries or WB6, region=None if countries else REGION,
            bidder="both" if ind and org else "ind" if ind else "org" if org else None,
            ctype=_ctype(f"{title}. {desc.split('. ')[0]}"),
            ntype=call[0] if call else "Open Call", btype="intorg", ref=ref))
    return out


if __name__ == "__main__":
    base.cli(collect, META)
