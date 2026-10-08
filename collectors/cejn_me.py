"""Crna Gora: CeJN, elektronski sistem javnih nabavki (cejn.gov.me).

Javna aplikacija sajta puni listu tendera preko javnog API-ja istog sajta, bez prijave:
POST api/cadocuments/GetTenders (objavljeni tenderi, filter po vrsti predmeta i datumu objave)
i GET api/caDocuments/getTenderRounds?tenderId=... (krug tendera s rokom za ponude).
Sajt nema robots.txt (provjereno 8.10.2026.).

U listi nema roka, pa se rok čita posebno za svaki tender. Pročitani rokovi se pamte u
cfg["_state"] (collect.py ga čuva u data/state.json), pa se svaki dan čitaju samo novi tenderi
i oni kojima je rok blizu (zbog mogućeg produženja). Uzimaju se samo naziv, naručilac, vrsta
predmeta, postupak i datumi; lični podaci službenika za nabavke iz API-ja se ne uzimaju.
"""
from __future__ import annotations

import datetime as dt
import time

from collectors import base

META = {
    "key": "CEJN",
    "name": "CeJN Crna Gora",
    "home": "https://cejn.gov.me",
    "scope": "Objavljeni tenderi u Crnoj Gori kojima rok za ponude nije prošao (zadano samo usluge); "
             "naslovi su na crnogorskom.",
}
API = "https://cejn.gov.me/api/"
VIEW = "https://cejn.gov.me/tenders/view-tender/{}"
PUBLISHED = "64"  # ProcedureStatuses: Tender_Published ("U toku")
SUBJECT = {"G": "1", "S": "2", "W": "3"}  # ProcurementSubjectType
KIND = {"Goods": base.GOODS, "Services": base.SERVICES, "Works": base.WORKS}
PROCEDURE = {
    "Small procurement": "Jednostavna nabavka",
    "Open procedure": "Otvoreni postupak",
    "Restricted procedure": "Ograničeni postupak",
    "Competitive procedure with negotiation": "Konkurentni postupak s pregovaranjem",
    "Negotiation procedure with prior publication": "Pregovarački postupak s objavom",
    "Partnership for innovation": "Partnerstvo za inovacije",
    "Competitive dialogue": "Konkurentni dijalog",
}
# Postupci u kojima ne može ponuditi ko god želi: bez objave i mini konkursi okvirnih sporazuma.
CLOSED_PROCEDURES = {"Negotiation procedure without prior", "Framework agreement mini call-off"}
PAGE = 500
PAUSE = 0.5


def _list(s, subject: str | None, since: dt.date, until: dt.date) -> list[dict]:
    out, skip = [], 0
    while True:
        body = {"skip": skip, "top": PAGE, "pageIndex": skip // PAGE, "pageSize": PAGE,
                "statuses": PUBLISHED, "tenderStatuses": [PUBLISHED],
                "dateFrom": f"{since.isoformat()}T00:00:00", "dateTo": f"{until.isoformat()}T23:59:59"}
        if subject:
            body["subjectType"] = subject
        j = base.fetch(s, "POST", API + "cadocuments/GetTenders", json=body).json()
        if not isinstance(j, dict) or not isinstance(j.get("value"), list) or "totalCount" not in j:
            raise base.SourceChanged("CeJN: lista tendera nema očekivani oblik (value, totalCount)")
        page = j["value"]
        for t in page:
            if not all(k in t for k in ("id", "title", "publishDate", "contractAuthority",
                                        "typeOfContractCaption", "typeOfProcedureCaption")):
                raise base.SourceChanged("CeJN: zapis u listi tendera nema očekivana polja")
        out += page
        skip += PAGE
        if len(page) < PAGE or skip >= int(j["totalCount"] or 0):
            return out
        time.sleep(PAUSE)


def _deadline(s, tender_id) -> str:
    """Rok za ponude ('YYYY-MM-DDTHH:MM:SS') iz zadnjeg objavljenog kruga; '' ako ga nema."""
    j = base.fetch(s, "GET", API + "caDocuments/getTenderRounds", params={"tenderId": tender_id}).json()
    if not isinstance(j, dict) or not isinstance(j.get("value"), list):
        raise base.SourceChanged("CeJN: krugovi tendera nemaju očekivani oblik")
    ends = [r.get("endOfSubmissions") or "" for r in j["value"]
            if isinstance(r, dict) and str(r.get("roundStatusValue")) == PUBLISHED]
    return max(ends, default="")


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("cejn", {})
    types = [t for t in c.get("types", ["S"]) if t in SUBJECT]
    days = int(c.get("days", 60))           # koliko unazad gledati datume objave
    budget = int(c.get("max_rounds", 150))  # najviše čitanja rokova po osvježavanju
    recheck = int(c.get("recheck_days", 2))  # rok ovoliko dana unaprijed se čita ponovo
    state = cfg.get("_state")
    if not isinstance(state, dict):
        state = {}
    known = state.get("rokovi") if isinstance(state.get("rokovi"), dict) else {}

    today = base.today()
    s = base.session()
    subjects = [None] if set(types) == set(SUBJECT) else [SUBJECT[t] for t in types]
    listed: list[dict] = []
    for subject in subjects:
        listed += _list(s, subject, today - dt.timedelta(days=days), today)
        time.sleep(PAUSE)
    if not listed:
        raise base.SourceChanged(f"CeJN je vratio 0 objavljenih tendera za zadnjih {days} dana")
    listed.sort(key=lambda t: str(t["publishDate"]), reverse=True)  # novi prvi dobijaju čitanje roka

    soon = (today + dt.timedelta(days=recheck)).isoformat()
    keep, out, read = {}, [], 0
    for t in listed:
        if t["typeOfProcedureCaption"] in CLOSED_PROCEDURES:
            continue
        tid = str(t["id"])
        due, checked = (known.get(tid) or ["", ""])[:2]
        # čita se: novi tender, tender bez roka i tender kojem je rok blizu (moguće produženje);
        # tender kojem je rok prošao se više ne čita
        day = base.iso_date(due) or ""
        stale = not checked or (checked < today.isoformat()
                                and (not due or today.isoformat() <= day <= soon))
        if stale and read < budget:
            if read:
                time.sleep(PAUSE)
            due, checked = _deadline(s, tid), today.isoformat()
            day = base.iso_date(due) or ""
            read += 1
        elif not checked:
            continue  # rok još nije pročitan; dolazi na red u sljedećem osvježavanju
        keep[tid] = [due, checked]
        if day < today.isoformat():
            continue
        out.append(base.rec(
            META["key"], tid,
            title=t["title"],
            buyer=t["contractAuthority"],
            url=VIEW.format(tid),
            pub=t["publishDate"],
            due=due,
            due_time=due,
            countries=["ME"],
            ctype=KIND.get(t["typeOfContractCaption"]),
            ntype=PROCEDURE.get(t["typeOfProcedureCaption"], t["typeOfProcedureCaption"]),
        ))
    state["rokovi"] = keep  # samo tenderi koji su još na listi (stariji se brišu)
    cfg["_state"] = state
    return out


if __name__ == "__main__":
    base.cli(collect, META)
