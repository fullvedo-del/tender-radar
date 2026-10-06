"""Svjetska banka: otvoreni pozivi iz projekata koje finansira Svjetska banka.

Izvor je javni JSON API koji koristi i pretraga nabavki na projects.worldbank.org.
"""
from __future__ import annotations

import html
import re

import datetime as dt
import time

from collectors import base

META = {
    "key": "WB",
    "name": "Svjetska banka",
    "home": "https://projects.worldbank.org/en/projects-operations/procurement",
    "scope": "Svi otvoreni pozivi za ponude, izraze interesa i pretkvalifikaciju iz projekata "
             "Svjetske banke u cijelom svijetu; svi tipovi ugovora.",
}

API = "https://search.worldbank.org/api/v2/procnotices"
DETAIL = "https://projects.worldbank.org/en/projects-operations/procurement-detail/"
CALLS = ["Invitation for Bids", "Request for Expression of Interest",
         "Invitation for Prequalification"]
GPN = "General Procurement Notice"  # s rokom ulazi kao poziv, bez roka kao najava (samo Zapadni Balkan)
WB6 = {"BA", "RS", "ME", "MK", "AL", "XK"}
GPN_DAYS = 120  # najava (opšte obavještenje bez roka) ostaje ovoliko dana od objave
FIELDS = ("id,notice_type,submission_date,submission_deadline_date,submission_deadline_time,"
          "bid_description,bid_reference_no,project_name,project_ctry_name,agency_name,"
          "contact_organization,contact_ctry_name,procurement_group,procurement_method_code,"
          "bid_estimate_amount,bid_currency_code,notice_text")
CTYPE = {"CS": base.SERVICES, "NC": base.SERVICES, "GO": base.GOODS, "CW": base.WORKS}
PAGE = 1000  # najveća stranica koju API vraća


def _query(s, params: dict, max_pages: int) -> list[dict]:
    """Sve stranice jednog upita (sortirano po roku pa po ID-u, stabilno straničenje)."""
    out: list[dict] = []
    while True:
        r = base.fetch(s, "GET", API, params={
            "format": "json", "apilang": "en", "fl": FIELDS, "rows": PAGE, "os": len(out),
            "srt": "submission_deadline_date asc,id asc", **params})
        time.sleep(0.6)
        try:
            d = r.json()
            total, items = int(d["total"]), d["procnotices"]
        except (ValueError, KeyError, TypeError):
            raise base.SourceChanged("Svjetska banka: API je vratio neočekivan format.") from None
        if not isinstance(items, list):
            raise base.SourceChanged("Svjetska banka: API je vratio neočekivan format.")
        if total > PAGE * max_pages:  # filter je prestao djelovati
            raise base.SourceChanged(f"Svjetska banka: neočekivano mnogo objava ({total}); "
                                     "filter API-ja vjerovatno više ne radi.")
        out += items
        if len(out) >= total:
            return out
        if not items:
            raise base.SourceChanged("Svjetska banka: API je prekinuo listu prije kraja.")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rec(r: dict) -> dict | None:
    sid = r.get("id")
    if not sid:
        raise base.SourceChanged("Svjetska banka: objave u odgovoru nemaju ID.")
    title = r.get("bid_description") or r.get("project_name")
    if not base.clean(title):
        return None
    # Regionalni projekat nema jednu državu: tada država naručioca (kontakt organizacije).
    country = r.get("project_ctry_name")
    if not base.country_code(country):
        country = r.get("contact_ctry_name")
    t = r.get("submission_deadline_time")
    method = base.clean(r.get("procurement_method_code")).upper()
    return base.rec(
        META["key"], sid, title=title,
        buyer=r.get("contact_organization") or r.get("agency_name") or r.get("project_name"),
        url=DETAIL + sid, pub=r.get("submission_date"), due=r.get("submission_deadline_date"),
        due_time=t if t != "00:00" else None,  # 00:00 = vrijeme nije uneseno
        countries=[country], ctype=CTYPE.get(r.get("procurement_group")),
        ntype=r.get("notice_type"), btype="ifi",
        btype_raw="Projekat koji finansira Svjetska banka",
        value=_num(r.get("bid_estimate_amount")), currency=r.get("bid_currency_code"),
        ref=r.get("bid_reference_no"),
        # INDV = izbor individualnog konsultanta; ostale metode (QCBS, CQS, RFB, RFQ ...) su za firme
        bidder=("ind" if method == "INDV" else "org") if method else None) | _desc(r)


def _desc(r: dict) -> dict:
    """Tekst objave bez HTML-a, samo za AI sažetak (ne piše se u podatke)."""
    text = base.clean(re.sub(r"<[^>]+>", " ", html.unescape(str(r.get("notice_text") or ""))))
    return {"_desc": text[:3000]} if len(text) > 40 else {}


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("wb", {})
    max_pages = int(c.get("max_pages", 10))
    days = int(c.get("no_deadline_days", 60))
    today = base.today()
    s = base.session()

    # 1) svi pozivi s rokom od danas nadalje (opšte obavještenje samo ako ima rok)
    with_due = _query(s, {"notice_type_exact": "^".join(CALLS + [GPN]),
                          "deadline_strdate": today.isoformat()}, max_pages)
    if not with_due:
        raise base.SourceChanged("Svjetska banka: API ne vraća nijedan otvoren poziv; "
                                 "filter po roku vjerovatno ne radi.")
    if any(not r.get("submission_deadline_date") for r in with_due):
        raise base.SourceChanged("Svjetska banka: u odgovoru nema polja s rokom.")
    with_due = [r for r in with_due
                if (base.iso_date(r["submission_deadline_date"]) or "") >= today.isoformat()]

    # 2) pozivi bez roka, objavljeni u zadnjih `days` dana
    recent = _query(s, {"notice_type_exact": "^".join(CALLS),
                        "submission_strdate": (today - dt.timedelta(days=days)).isoformat()},
                    max_pages)
    no_due = [r for r in recent if not r.get("submission_deadline_date")]

    found: dict[str, dict] = {}
    for r in with_due + no_due:
        rec = _rec(r)
        if rec:
            found.setdefault(rec["id"], rec)

    # 3) najave: opšta obavještenja o nabavkama bez roka za projekte na Zapadnom Balkanu
    gpn = _query(s, {"notice_type_exact": GPN,
                     "submission_strdate": (today - dt.timedelta(days=GPN_DAYS)).isoformat()}, max_pages)
    for r in gpn:
        if r.get("submission_deadline_date"):
            continue
        rec = _rec(r)
        if rec and WB6 & set(rec.get("c") or []) and rec["id"] not in found:
            rec["n"] = "Najava (opšte obavještenje o nabavkama)"
            pub = dt.date.fromisoformat(rec["p"]) if rec.get("p") else today
            rec["keep"] = (pub + dt.timedelta(days=GPN_DAYS)).isoformat()
            found[rec["id"]] = rec
    if not found:
        raise base.SourceChanged("Svjetska banka: nijedna objava nije prepoznata.")
    return list(found.values())


if __name__ == "__main__":
    base.cli(collect, META)
