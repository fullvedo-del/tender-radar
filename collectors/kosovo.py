"""Kosovo: OCDS web servis Regulatorne komisije za javne nabavke (PPRC), preko e-Prokurimi.

PPRC objavljuje otvorene, mašinski čitljive podatke o nabavkama kao OCDS release pakete:
GET https://ocdskrpp.rks-gov.net/krppAPI/TenderRelease?endDateFrom=YYYY-MM-DD&endDateEnd=YYYY-MM-DD
filtrira po roku za ponude (tenderPeriod.endDate). Sajt nema robots.txt (vraća 404), pa ništa
nije zabranjeno. Svaki release ima naslov, naručioca, rok, vrstu, vrijednost i link na javnu
stranicu objave na e-prokurimi.

API je spor: server računa upit 40 do 60 s bez obzira na veličinu prozora (tako radi i Open
Contracting Kingfisher collector), pa se čita jedan dan po upitu. Prozor otvorenih rokova (od
danas do `days` dana unaprijed) dijeli se na komade od `chunk` dana (podrazumijevano 1). Svaki
dan se pročita onoliko dana koliko stane u `budget` sekundi, krećući od mjesta gdje se stalo;
ostali dani zadrže jučerašnje tendere iz cfg["_state"]. Tako se cijeli prozor napuni za desetak
dana i poslije održava, a izvor nikad ne premaši vremenski budžet. Dan koji padne pokušava se
ponovo pri sljedećem osvježavanju.
"""
from __future__ import annotations

import datetime as dt
import time

from collectors import base

META = {
    "key": "EPRK",
    "name": "e-Prokurimi (Kosovo)",
    "home": "https://e-prokurimi.rks-gov.net",
    "scope": "Objavljeni tenderi na Kosovu kojima rok za ponude nije prošao, preko OCDS servisa PPRC-a; "
             "naslovi su na albanskom.",
}
API = "https://ocdskrpp.rks-gov.net/krppAPI/TenderRelease"
CATEGORY = {"goods": base.GOODS, "services": base.SERVICES, "works": base.WORKS}
# Postupci u kojima ne može ponuditi ko god želi (OCDS procurementMethod).
CLOSED_METHODS = {"limited", "direct"}


def _records(payload) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("releases"), list):
        raise base.SourceChanged("Kosovo: odgovor nema OCDS oblik (releases)")
    out = []
    for rel in payload["releases"]:
        t = (rel or {}).get("tender") or {}
        if not t.get("title") or not t.get("id"):
            raise base.SourceChanged("Kosovo: release bez naziva ili ID-a tendera")
        if t.get("status") and t["status"] != "active":
            continue
        if t.get("procurementMethod") in CLOSED_METHODS:
            continue
        due = base.iso_date((t.get("tenderPeriod") or {}).get("endDate"))
        if not due:
            continue
        pe = t.get("procuringEntity") or {}
        buyer = (pe.get("party") or {}).get("name") or pe.get("name") or ""
        docs = [d for d in (t.get("documents") or []) if isinstance(d, dict) and d.get("url")]
        notice = next((d for d in docs if d.get("documentType") == "tenderNotice"), docs[0] if docs else None)
        if not notice:
            continue  # bez javne stranice objave nema šta otvoriti
        val = t.get("value") or {}
        out.append({
            "ocid": rel.get("ocid") or t["id"],
            "t": t["title"],
            "b": buyer,
            "u": notice["url"],
            "p": base.iso_date(rel.get("date")),
            "d": due,
            "dt": (t.get("tenderPeriod") or {}).get("endDate"),
            "k": CATEGORY.get(t.get("mainProcurementCategory")),
            "n": t.get("procurementMethodDetails") or None,
            "v": (val.get("amount") if isinstance(val.get("amount"), (int, float)) else None),
            "cur": val.get("currency"),
            "ref": t["id"],
        })
    return out


def _chunk(d: str, today: dt.date, chunk: int) -> int:
    return max(0, (dt.date.fromisoformat(d) - today).days) // chunk


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("kosovo", {})
    days = int(c.get("days", 30))           # koliko dana unaprijed (rok) gledati
    chunk = int(c.get("chunk", 1))          # veličina jednog komada u danima (API je spor, 1 dan po upitu)
    budget = float(c.get("budget", 200))    # najviše sekundi na čitanje po osvježavanju
    timeout = float(c.get("timeout", 75))   # najduže čekanje na jedan upit
    state = cfg.get("_state")
    if not isinstance(state, dict):
        state = {}
    open_t = dict(state.get("open") or {}) if isinstance(state.get("open"), dict) else {}
    windows = (days + chunk - 1) // chunk
    cursor = int(state.get("cursor") or 0) % windows if windows else 0

    today = base.today()
    s = base.session()
    t0 = time.time()
    got_any, done = False, []
    for step in range(windows):
        if time.time() - t0 > budget:
            break
        k = (cursor + step) % windows
        a = today + dt.timedelta(days=k * chunk)
        b = today + dt.timedelta(days=min(days, (k + 1) * chunk))  # gornja granica isključiva, kao kod Kingfishera
        try:
            r = base.fetch(s, "GET", API, tries=1, pause=3.0, timeout=timeout,
                           params={"endDateFrom": a.isoformat(), "endDateEnd": b.isoformat()})
            payload = r.json()
        except base.SourceBlocked:
            raise
        except Exception:
            continue  # spor ili pao upit: ovaj komad zadrži jučerašnje, ide dalje
        if isinstance(payload, dict) and "releases" not in payload and payload.get("message"):
            continue  # prolazna greška servera (npr. {"message": "An error has occurred."})
        fresh = _records(payload)  # struktura koja nije OCDS diže SourceChanged
        got_any = True
        done.append(k)
        open_t = {o: v for o, v in open_t.items() if _chunk(v["d"], today, chunk) != k}
        for rec in fresh:
            open_t[rec["ocid"]] = rec
        time.sleep(0.5)

    if not got_any and not open_t:
        raise base.SourceChanged(f"Kosovo: OCDS API nije odgovorio ni na jedan upit (budžet {int(budget)} s)")

    td = today.isoformat()
    open_t = {o: v for o, v in open_t.items() if v.get("d") and v["d"] >= td
              and _chunk(v["d"], today, chunk) < windows}
    state["open"] = open_t
    state["cursor"] = ((done[-1] + 1) if done else (cursor + 1)) % windows if windows else 0
    cfg["_state"] = state

    out = []
    for v in open_t.values():
        out.append(base.rec(
            META["key"], v["ocid"],
            title=v["t"], buyer=v.get("b", ""), url=v["u"],
            pub=v.get("p"), due=v.get("d"), due_time=v.get("dt"),
            countries=["XK"], ctype=v.get("k"), ntype=v.get("n"),
            value=v.get("v"), currency=v.get("cur"),
            ref=v.get("ref") if v.get("ref") != v["ocid"] else None,
        ))
    return out


if __name__ == "__main__":
    base.cli(collect, META)
