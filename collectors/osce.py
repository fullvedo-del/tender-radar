"""OSCE: otvoreni tenderi sa stranice procurement.osce.org/tenders.

Javna lista bez prijave; robots.txt je ne zabranjuje. OSCE-ova pravila o autorskim pravima
dozvoljavaju upotrebu sadržaja bez pisane dozvole samo za lične i obrazovne svrhe, pa se ovaj
izvor vodi kao interni (vidi META["private"]): objave se ne stavljaju u javni fajl.
"""
from __future__ import annotations

import datetime as dt
import re
import time

from bs4 import BeautifulSoup

from . import base

META = {
    "key": "OSCE",
    "name": "OSCE",
    "home": "https://procurement.osce.org/tenders",
    "private": True,
    "scope": "Svi otvoreni tenderi OSCE-a (sekretarijat, institucije i misije na terenu); "
             "interni izvor, vidljiv samo uz šifru.",
}

URL = "https://procurement.osce.org/tenders"
HOST = "https://procurement.osce.org"
MAX_PAGES = 10
NO_DEADLINE_DAYS = 60
NOT_A_CALL = re.compile(r"^\s*sale of\b", re.I)  # prodaja rashodovanih vozila i opreme
# Sjedišta OSCE struktura koje u nazivu nemaju državu.
SEATS = (("dushanbe", "TJ"), ("bishkek", "KG"), ("astana", "KZ"), ("ashgabat", "TM"),
         ("skopje", "MK"), ("secretariat", "AT"), ("vienna", "AT"), ("odihr", "PL"),
         ("democratic institutions", "PL"), ("warsaw", "PL"), ("national minorities", "NL"),
         ("the hague", "NL"), ("freedom of the media", "AT"), ("prague", "CZ"))


def _country(title: str, office: str) -> list[str]:
    """Država iz naslova ako je imenuje, inače država ureda koji nabavlja."""
    found = base.countries_in(title) or base.countries_in(office)
    if found:
        return found
    low = base.norm(office)
    return [code for key, code in SEATS if key in low][:1]


def _field(item, label: str):
    """<dd> uz <dt> sa zadatim natpisom."""
    for dtag in item.find_all("dt"):
        if base.norm(dtag.get_text()) == label:
            return dtag.find_next_sibling("dd")
    return None


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("osce", {})
    s = base.session()
    today = base.today()
    cutoff = (today - dt.timedelta(days=NO_DEADLINE_DAYS)).isoformat()
    out: dict[str, dict] = {}
    for page in range(int(c.get("max_pages", MAX_PAGES))):
        soup = BeautifulSoup(base.fetch(s, "GET", URL, params={"page": page}).text, "lxml")
        time.sleep(0.6)
        if page == 0 and "open tenders" not in base.norm(soup.title.get_text() if soup.title else ""):
            raise base.SourceChanged("OSCE: stranica s otvorenim tenderima nije prepoznata")
        items = soup.select("article.node--type-tender")
        if not items:
            if page == 0 and not re.search(r"\bno (?:open )?tenders\b|no results", soup.get_text(" "), re.I):
                raise base.SourceChanged("OSCE: lista tendera je prazna, a nema poruke da tendera nema")
            break
        for it in items:
            link = it.select_one("a[href^='/tenders/']")
            if link is None or not base.clean(link.get_text()):
                raise base.SourceChanged("OSCE: tender bez naslova ili linka; struktura se promijenila")
            office = base.clean(_field(it, "on behalf of").get_text(" ")) if _field(it, "on behalf of") else ""
            pub_dd, due_dd = _field(it, "launch date"), _field(it, "deadline")
            pub = base.iso_date(pub_dd.get_text(" ")) if pub_dd else None
            due_txt = base.clean(due_dd.get_text(" ")) if due_dd else ""  # "2 October 2026 - 23:59 , Asia/Dushanbe"
            due = base.iso_date(due_txt)
            if (due and due < today.isoformat()) or (not due and (pub or "") < cutoff):
                continue
            if NOT_A_CALL.search(link.get_text()):
                continue
            sid = link["href"].rsplit("/", 1)[-1]
            out[sid] = base.rec(
                META["key"], sid, title=link.get_text(), buyer=office or "OSCE",
                url=HOST + link["href"], pub=pub, due=due, due_time=due_txt,
                countries=_country(link.get_text(), office), btype="intorg")
        if not soup.select_one(f"a[href*='page={page + 1}']"):
            break
    return list(out.values())


if __name__ == "__main__":
    base.cli(collect, META)
