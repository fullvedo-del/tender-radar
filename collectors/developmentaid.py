"""DevelopmentAid: tenderi za Zapadni Balkan i grantovi za koje mogu aplicirati organizacije iz
BiH, preko DevelopmentAid External API-ja (https://www.developmentaid.org/api/external).

Pristup daje članarina korisnika; ključ je u varijabli okruženja DA_API_KEY (GitHub secret).
Uslovi DevelopmentAid-a dozvoljavaju podatke iz API-ja samo za internu upotrebu, zato je izvor
interni: objave se čuvaju šifrovane i vide se tek nakon unosa šifre.
"""
from __future__ import annotations

import os
import time

import requests

from collectors import base

META = {
    "key": "DA",
    "name": "DevelopmentAid",
    "home": "https://www.developmentaid.org",
    "scope": "Tenderi za Zapadni Balkan i grantovi za koje mogu aplicirati organizacije iz BiH, "
             "preko API-ja uz članarinu; samo za internu upotrebu.",
    "private": True,
    "env": "DA_API_KEY",
}
API = "https://www.developmentaid.org/api/external"
WEB = "https://www.developmentaid.org"
WB6 = [265, 280, 276, 272, 262, 270]   # BiH, Srbija, Crna Gora, Sjeverna Makedonija, Albanija, Kosovo
BIH = 265
OPEN = [2, 3]                          # najava (forecast), otvoreno
PAGE = 100


def _search(s, key: str, what: str, flt: dict, max_pages: int) -> list[dict]:
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        for attempt in range(3):
            try:
                r = s.post(f"{API}/{what}/search", timeout=60, json={
                    "page": page, "size": PAGE, "sort": "posted_date.desc", "filter": flt},
                    headers={"X-API-KEY": key, "Accept": "application/json"})
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code >= 500 and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            break
        if r.status_code in (401, 403):
            try:
                msg = r.json().get("message", "")
            except ValueError:
                msg = ""
            if "permission" in msg.lower():
                raise base.SourceBlocked(
                    "ključ radi, ali nema pravo pretrage tendera i grantova. Zatraži od svog "
                    "DevelopmentAid Business Development Managera pristup pretrazi preko API-ja.")
            raise base.SourceBlocked(f"ključ DA_API_KEY nije prihvaćen (HTTP {r.status_code})")
        if r.status_code == 429:
            raise RuntimeError("potrošeno dnevno ograničenje pristupa DevelopmentAid-a; nastavlja se sutra")
        if r.status_code != 200:
            raise RuntimeError(f"DevelopmentAid API: HTTP {r.status_code}")
        try:
            d = r.json()
            items, total = d.get("items") or [], int(d.get("total") or 0)
        except (ValueError, TypeError, AttributeError):
            raise base.SourceChanged("DevelopmentAid API je promijenio format odgovora.") from None
        out += items
        if len(out) >= total or not items:
            break
        time.sleep(1.0)
    return out


def _rec(it: dict, what: str):
    iid, name = it.get("id"), it.get("name")
    if not iid or not name:
        return None
    status = str(it.get("status") or "")
    return base.rec(
        META["key"], f"{'G' if what == 'grants' else 'T'}{iid}", title=name, buyer="",
        url=f"{WEB}/{what}/view/{iid}", pub=it.get("postedDate"), due=it.get("deadline"),
        ctype=base.OTHER, ntype="najava" if status == "forecast" else None, btype="other",
        kind="P" if what == "grants" else None)


def collect(cfg: dict) -> list[dict]:
    key = (os.environ.get("DA_API_KEY") or "").strip()
    if not key:
        raise base.SourceBlocked("nije postavljen ključ DA_API_KEY")
    c = cfg.get("da", {})
    max_pages = int(c.get("max_pages", 10))
    s = base.session()
    found: dict[str, dict] = {}
    queries = [
        ("tenders", {"statuses": OPEN, "locations": WB6}),
        ("grants", {"statuses": OPEN, "applicantNationalities": [BIH]}),
        ("grants", {"statuses": OPEN, "locations": WB6}),
    ]
    for what, flt in queries:
        for it in _search(s, key, what, flt, max_pages):
            r = _rec(it, what)
            if r:
                found.setdefault(r["id"], r)
    today = base.today().isoformat()
    return [r for r in found.values() if not r.get("d") or r["d"] >= today]


if __name__ == "__main__":
    base.cli(collect, META)
