"""GIZ: otvoreni pozivi s GIZ-ove platforme za nabavke (ausschreibungen.giz.de).

Javna lista bez prijave; robots.txt dozvoljava sve. Uslovi korištenja platforme (§7) kažu da se
rezultati pretrage smiju koristiti samo interno i da se ne smiju prenositi trećim licima, pa se
ovaj izvor vodi kao interni (vidi META["private"]): objave se ne stavljaju u javni fajl.

Veći GIZ-ovi tenderi (iznad EU praga) nalaze se i na TED-u; ovdje su i manji (UVgO).
"""
from __future__ import annotations

import datetime as dt
import re
import time

from bs4 import BeautifulSoup

from . import base

META = {
    "key": "GIZ",
    "name": "GIZ (platforma za nabavke)",
    "home": "https://ausschreibungen.giz.de",
    "private": True,
    "scope": "Svi otvoreni pozivi s GIZ-ove platforme, uključujući manje tendere ispod EU praga "
             "kojih nema na TED-u; interni izvor, vidljiv samo uz šifru.",
}

LIST = "https://ausschreibungen.giz.de/Satellite/company/welcome.do"
HOST = "https://ausschreibungen.giz.de"
MAX_PAGES = 30
NO_DEADLINE_DAYS = 60
BUYER = "Deutsche Gesellschaft für Internationale Zusammenarbeit (GIZ) GmbH"
# Vrsta objave na platformi -> naziv u alatu. Dodjele ugovora i izmjene ugovora se ne uzimaju.
KINDS = (
    (r"vergebener auftrag|auftragsanderung|aufhebung", None),
    (r"beabsichtigte ausschreibung", "Najava tendera"),
    (r"\btnw\b|teilnahmewettbewerb", "Poziv za prijave učešća"),
    (r"ausschreibung", "Tender"),
)
RULES = (("uvgo", "ispod EU praga (UVgO)"), ("vgv", "EU postupak (VgV)"), ("vob", "radovi (VOB)"))
# Njemački i francuski nazivi zemalja Zapadnog Balkana; ostale države traže se po engleskom imenu.
LOCAL = (("bosnien", "BA"), ("bosnie", "BA"), ("serbien", "RS"), ("serbie", "RS"),
         ("nordmazedonien", "MK"), ("macedoine du nord", "MK"), ("albanien", "AL"),
         ("albanie", "AL"), ("montenegro", "ME"), ("kosovo", "XK"))
WB6 = ["AL", "BA", "XK", "ME", "MK", "RS"]


def _countries(title: str) -> list[str]:
    """Države koje naslov izričito imenuje."""
    low = base.norm(title)
    if re.search(r"\b(?:western balkans?|westbalkan|balkans occidentaux)\b", low):
        return list(WB6)
    found = base.countries_in(title)
    for key, code in LOCAL:
        if re.search(rf"\b{key}", low) and code not in found:
            found.append(code)
    return found


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("giz", {})
    s = base.session()
    today = base.today()
    cutoff = (today - dt.timedelta(days=NO_DEADLINE_DAYS)).isoformat()
    out: dict[str, dict] = {}
    seen_rows = pages = 0
    for page in range(1, int(c.get("max_pages", MAX_PAGES)) + 1):
        r = base.fetch(s, "GET", LIST, params={"method": "showTable", "fromSearch": 1,
                                                 "selectedTablePagePROJECT_RESULT": page})
        time.sleep(0.6)
        r.encoding = r.apparent_encoding or "ISO-8859-1"
        soup = BeautifulSoup(r.text, "lxml")
        table = soup.find("table")
        head = [base.norm(th.get_text()) for th in table.find_all("th")] if table else []
        if not table or not any("bezeichnung" in h for h in head):
            raise base.SourceChanged("GIZ: tabela s objavama nije prepoznata")
        if not pages:
            m = re.search(r"von\s+(\d+)", base.clean(soup.get_text(" ")))
            pages = int(m[1]) if m else 1
        for tr in table.find_all("tr")[1:]:
            td = [base.clean(x.get_text(" ")) for x in tr.find_all("td")]
            link = tr.select_one("a[href*='pid=']")
            if len(td) < 5 or link is None:
                continue
            seen_rows += 1
            pub, due, title, typ, buyer = base.iso_date(td[0]), base.iso_date(td[1]), td[2], td[3], td[4]
            low = base.norm(typ)  # bez umlauta: "Auftragsänderung" -> "auftragsanderung"
            kind = next((name for pat, name in KINDS if re.search(pat, low)), "?")
            if kind is None:
                continue  # dodjela ili izmjena ugovora
            if (due and due < today.isoformat()) or (not due and (pub or "") < cutoff):
                continue
            pid = re.search(r"pid=(\d+)", link["href"])[1]
            rule = next((label for key, label in RULES if key in low), "")
            num = re.match(r"\s*(\d{6,})\s*[-–]\s*(.+)", title)  # "10055375 - Naziv": broj projekta
            out[pid] = base.rec(
                META["key"], pid, title=num[2] if num else title, buyer=buyer or BUYER,
                url=f"{HOST}/Satellite/public/company/projectForwarding.do?pid={pid}",
                pub=pub, due=due, countries=_countries(title),
                ctype=base.WORKS if "vob" in low else None,
                ntype=(typ if kind == "?" else f"{kind}, {rule}" if rule else kind),
                btype="bilateral", ref=num[1] if num else None, bidder="org")
        if page >= pages:
            break
    if not seen_rows:
        raise base.SourceChanged("GIZ: lista objava je prazna")
    return list(out.values())


if __name__ == "__main__":
    base.cli(collect, META)
