"""Sjeverna Makedonija: ESJN (e-nabavki.gov.mk), lista „Actual calls for bids“.

Zaštita od robota (Cloudflare) na e-nabavki odbija servere u podatkovnim centrima (pa i GitHub),
ali pušta obične mreže. Zato makedonske podatke NE preuzima GitHub, nego kancelarijski računar na
običnoj vezi (skripta `tools/esjn_fetch.py`) jednom dnevno pozove javni servis
`Services/Procurements.asmx/GetGridData` i upiše sirovi rezultat u `data/esjn_raw.json`, pa taj
fajl gurne u repozitorij. Ovaj kolektor onda samo pročita taj fajl i napravi zapise; ne gađa
e-nabavki. Ako fajla nema (kancelarijski računar još nije poslao), zadrže se jučerašnje objave.

Uzimaju se samo pozivi kojima datum javnog otvaranja (rok) nije prošao, osim pregovaračkih bez
objave. Naslovi su na makedonskom (ćirilica).
"""
from __future__ import annotations

import datetime as dt
import json
import os

from collectors import base

META = {
    "key": "ESJN",
    "name": "ESJN (Sj. Makedonija)",
    "home": "https://e-nabavki.gov.mk",
    "scope": "Objavljeni pozivi za ponude u Sjevernoj Makedoniji kojima rok (javno otvaranje) nije "
             "prošao, bez pregovaračkih bez objave; naslovi su na makedonskom.",
}
RAW = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "esjn_raw.json")
VIEW = "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/{}/{}"
KIND = {1: base.GOODS, 2: base.SERVICES, 3: base.WORKS}  # TypeOfProcurements
PROCEDURE = {
    "Open": "Otvoreni postupak",
    "SimplifiedOpenProcedure": "Pojednostavljeni otvoreni postupak",
    "LowEstimatedValueProcedure": "Nabavka male vrijednosti",
    "SpecialServices": "Posebne usluge",
    "QualificationSystem": "Kvalifikacioni sistem",
    "BidForChoosingIdealSolution": "Konkurs za idejno rješenje",
    "ProcedureForTalkingWithPreviousAnnouncement": "Pregovarački postupak s objavom",
}
# Pregovarački postupak bez prethodne objave: nije otvoren za sve.
CLOSED_PROCEDURES = {"ProcedureForTalkingWithoutPreviousAnnouncement"}


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("makedonija", {})
    path = c.get("raw_file") or RAW
    if not os.path.exists(path):
        raise base.SourceChanged("Makedonija: nema data/esjn_raw.json; kancelarijski računar još "
                                 "nije poslao podatke (vidi tools/esjn_fetch.py)")
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        raise base.SourceChanged(f"Makedonija: data/esjn_raw.json se ne može pročitati ({type(e).__name__})")
    rows = raw.get("rows") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise base.SourceChanged("Makedonija: data/esjn_raw.json nema listu zapisa (rows)")

    today = base.today().isoformat()
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if r.get("TypeOfProcedure") in CLOSED_PROCEDURES:
            continue
        due = base.iso_date(r.get("DateOfPublicOpening"))
        if not due or due < today:  # bez roka ili rok prošao
            continue
        if not r.get("ProcureItem") or not r.get("EntityId"):
            continue
        proc = r.get("TypeOfProcedure") or ""
        out.append(base.rec(
            META["key"], r.get("Id") or r.get("EntityId"),
            title=r.get("ProcureItem"),
            buyer=r.get("Name", ""),
            url=VIEW.format(r.get("EntityId"), r.get("TypeOfProcedureId")),
            pub=r.get("DateOfPublicAnnouncement"),
            due=r.get("DateOfPublicOpening"), due_time=r.get("DateOfPublicOpening"),
            countries=["MK"],
            ctype=KIND.get(r.get("TypeOfProcurements")),
            ntype=PROCEDURE.get(proc, proc),
            ref=r.get("DecisionNumber"),
        ))
    return out


if __name__ == "__main__":
    base.cli(collect, META)
