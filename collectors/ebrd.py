"""EBRD: objave o nabavkama za projekte koje finansira EBRD, s www.ebrd.com.

Lista "Procurement notices" se na stranici puni iz JSON servleta koji sama
stranica poziva (bez prijave, kolačića i tokena). Za svaki otvoreni poziv čita
se i stranica objave: rok sa satom, referenca i klijent (naručilac).

Nije obuhvaćeno: portal ECEPP (ecepp.ebrd.com odgovara 403 na svaki zahtjev) i
korporativne i konsultantske nabavke EBRD-a na SMART by GEP (robots.txt: Disallow: /).
"""
from __future__ import annotations

import datetime as dt
import re
import time

from bs4 import BeautifulSoup

from . import base

META = {
    "key": "EBRD",
    "name": "EBRD",
    "home": "https://www.ebrd.com/home/work-with-us/project-procurement/procurement-notices.html",
    "scope": "Otvoreni pozivi s liste objava na ebrd.com za projekte koje finansira EBRD "
             "(tenderi, prijedlozi, izražavanje interesa, pretkvalifikacija); bez portala "
             "ECEPP i vlastitih korporativnih i konsultantskih nabavki EBRD-a.",
}

API = "https://www.ebrd.com/bin/ebrd_dxp/filterlistservlet"
# Isti parametri koje šalje JS stranice; bez nekih od njih servlet vraća 500.
PARAMS = {
    "parentPath": "/content/ebrd_dxp/uk/en/home/work-with-us/project-procurement/procurement-notices",
    "secondParentPath": "", "cardType": "procurement-notices", "searchKey": "",
    "eventSort": "", "sortBy": "newest-first", "filters": "", "countryFilters": "",
    "sectorFilters": "", "topicFilters": "", "statusFilters": "", "noticeTypeFilters": "",
    "pageTypeFilters": "", "startDate": "", "endDate": "",
}
NO_DEADLINE_DAYS = 60

# Pozivi (tender, prijedlozi, izražavanje interesa, pretkvalifikacija) ulaze.
# Opće objave (GPN: "Closing Date" je samo rok važenja, bez roka za ponude) i
# "Other Notices" (dodjele ugovora, liste pretkvalifikovanih) ne ulaze.
_NOTICE = re.compile(r"notice|invitation|expression|request|qualification|proposal|tender|bid", re.I)
_CALL = re.compile(r"invitation|expression|request for|qualification|proposal|tender|bid", re.I)
_NOT_CALL = re.compile(r"general procurement|\bother\b|award|cancel|\bplans?\b|prequalified|shortlist",
                       re.I)
_REF = re.compile(r"\b\d{4}-[A-Z]{3}-\d{4,6}\b")  # EBRD broj objave, npr. 9736-IFT-56767

# Klijent kako ga imenuje tekst objave na početku pasusa: "X (the Purchaser) intends",
# "X hereinafter referred to as the Purchaser, intends", "X has received financing".
# Tačka iza riječi od 4+ znaka je kraj rečenice; "d.o.o. Sarajevo" ostaje u imenu.
_HEREIN = r"hereinafter\s+(?:referred\s+to\s+as\s+|called\s+)?"
_ROLE = (r"[\"“”']?(?:the\s+)?[\"“”']?"
         r"(?:Purchaser|Employer|Client|Borrower|Contracting (?:Entity|Authority))[\"“”']?")
_CLIENT = re.compile(
    r"(?:\d+\.\s*)?(?:The\s+)?(?P<b>(?:(?!(?<=\w{4})\.\s+[A-Z])[^;:\n]){4,160}?)\s*,?\s*"
    r"(?:(?:\(\s*(?:" + _HEREIN + r")?" + _ROLE + r"\s*\)|" + _HEREIN + _ROLE + r")\s*,?\s*)?"
    r"(?:has\s+(?:received|applied|been\s+allocated)|intends|is\s+seeking|now\s+invites)")
_GENERIC = re.compile(
    r"(?:above[- ]named\s+)?(?:(?:purchaser|employer|client|borrower|bank|project)\W*)+", re.I)


def _open(due, pub, td: str, cutoff: str) -> bool:
    d = base.iso_date(due)
    if d:
        return d >= td
    p = base.iso_date(pub)
    return bool(p) and p >= cutoff


def _detail(s, url: str):
    """(polja zaglavlja, klijent) sa stranice objave; None ako stranice više nema."""
    r = base.fetch(s, "GET", url, ok=(200, 404))
    if r.status_code == 404:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    cards = {}
    for c in soup.select(".project-overview__main-card"):
        k = c.select_one(".project-overview__card-title")
        v = c.select_one(".project-overview__card-description")
        if k and v:
            cards[base.clean(k.get_text())] = base.clean(v.get_text())
    if not cards:
        raise base.SourceChanged("EBRD: stranica objave nema očekivana polja")
    pid = soup.select_one(".project-overview__projectID")
    cards["Project ID"] = base.clean(pid.get_text()) if pid else ""
    client = None
    for p in soup.select(".text-block__details p")[:12]:
        m = _CLIENT.match(base.clean(p.get_text()))
        if m and m["b"][0].isupper() and not _GENERIC.fullmatch(m["b"]):
            client = m["b"].strip(" ,")
            break
    return cards, client


def collect(cfg: dict) -> list[dict]:
    opt = cfg.get("ebrd", {})
    pause = max(0.5, float(opt.get("pause", 0.6)))
    max_pages = int(opt.get("max_pages", 10))  # 12 objava po stranici
    s = base.session()

    rows, total, page = [], 0, 1
    while page <= max_pages:
        r = base.fetch(s, "GET", API, params={**PARAMS, "currentPage": page})
        try:
            data = r.json()
            total = int(data["resultCount"][0]["resultCount"])
            batch = [dict(x) for x in data["searchResult"]]
        except (ValueError, KeyError, IndexError, TypeError):
            raise base.SourceChanged("EBRD: neočekivan odgovor liste objava") from None
        rows += batch
        if not batch or len(rows) >= total:
            break
        page += 1
        time.sleep(pause)
    if total and not rows:
        raise base.SourceChanged(f"EBRD: lista je prazna, a izvor navodi {total} objava")

    today = base.today()
    td = today.isoformat()
    cutoff = (today - dt.timedelta(days=NO_DEADLINE_DAYS)).isoformat()
    out, typed, tried, gone = [], 0, 0, 0
    for it in rows:
        title, url = base.clean(it.get("title")), it.get("projectUrl") or ""
        if not title or not url.startswith("http"):
            raise base.SourceChanged("EBRD: objava bez naslova ili linka")
        # Na nekim objavama su vrsta objave i vrsta ugovora zamijenjene.
        vals = [base.clean(it.get("projectNoticeType")), base.clean(it.get("projectContractType"))]
        ntype = next((v for v in vals if _NOTICE.search(v)), "")
        contract = next((v for v in vals if v and v != ntype), "")
        typed += bool(ntype)
        if not _CALL.search(ntype) or _NOT_CALL.search(ntype):
            continue
        if not _open(it.get("projectCloseDate"), it.get("projectIssueDate"), td, cutoff):
            continue
        time.sleep(pause)
        tried += 1
        det = _detail(s, url)
        if det is None:
            gone += 1
            continue
        cards, client = det
        due = cards.get("Closing Date") or it.get("projectCloseDate")
        pub = it.get("projectIssueDate") or cards.get("Issue Date")
        if not _open(due, pub, td, cutoff):
            continue
        sid = re.sub(r"[-_]+", "-", url.rsplit("/", 1)[-1].removesuffix(".html")).strip("-")
        # Izražavanje interesa se po pravilima EBRD-a koristi za konsultantske usluge.
        consult = re.search(r"expression|consult", f"{ntype} {contract}", re.I)
        m = _REF.search(title)
        out.append(base.rec(
            META["key"], sid, title=title, buyer=client or "EBRD", url=url,
            pub=pub, due=due, due_time=due, countries=[it.get("projectCountry")],
            ctype=base.SERVICES if consult else None,
            ntype=ntype if len(ntype) <= 60 else re.sub(r"\s*\([^)]*\)$", "", ntype),
            btype="ifi", btype_raw="Projekat koji finansira EBRD",
            ref=cards.get("Procurement Ref No.") or (m[0] if m else None) or cards["Project ID"]))
    if rows and not typed:
        raise base.SourceChanged("EBRD: objave nemaju prepoznatljivu vrstu objave")
    if tried and gone == tried:
        raise base.SourceChanged("EBRD: stranice objava s liste ne postoje (404)")
    return out


if __name__ == "__main__":
    base.cli(collect, META)
