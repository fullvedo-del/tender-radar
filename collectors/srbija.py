"""Srbija: Portal javnih nabavki (jnportal.ujn.gov.rs), javni servis koji puni sam portal.

Javna lista postupaka (tab „Огласи/Поступци“) učitava se bez prijave preko DevExtreme servisa:
GET api/searchgrid/TendersAll/get?skip=&take=&filter=&sort=&requireTotalCount=true
Portal svakom posjetiocu (i neprijavljenom) u stranicu upiše token u skrivenom polju
`uiUserToken`; taj token se šalje kao zaglavlje `UserToken`. Zato kolektor prvo otvori stranicu
(pokupi kolačiće i token), pa poziva servis. Robots.txt portala zabranjuje robote, ali po odluci
naručioca to ovdje nije prepreka; tehnička zaštita (prijava, Cloudflare) se ne zaobilazi.

Uzimaju se samo postupci kojima rok za ponude nije prošao (filter po SubmissionDeadline), bez
pregovaračkih postupaka bez objave javnog poziva. Naslovi su na srpskom (ćirilica).
"""
from __future__ import annotations

import datetime as dt
import re
import time

from collectors import base

META = {
    "key": "JNRS",
    "name": "Portal JN (Srbija)",
    "home": "https://jnportal.ujn.gov.rs",
    "scope": "Objavljeni postupci javnih nabavki u Srbiji kojima rok za ponude nije prošao, bez "
             "pregovaračkih postupaka bez objave; naslovi su na srpskom.",
}
PAGE = "https://jnportal.ujn.gov.rs/postupci-svi"
API = "https://jnportal.ujn.gov.rs/api/searchgrid/TendersAll/get"
VIEW = "https://jnportal.ujn.gov.rs/tender-eo/{}"
KIND = {"добра": base.GOODS, "услуге": base.SERVICES, "радови": base.WORKS}
PAUSE = 0.5


def _token(s) -> str:
    html = base.fetch(s, "GET", PAGE).text
    m = re.search(r'id="uiUserToken"\s+value="([^"]+)"', html)
    if not m:
        raise base.SourceChanged("Srbija: stranica nema token uiUserToken (portal je promijenjen)")
    return m.group(1)


def _buyer(name: str) -> str:
    return re.sub(r",?\s*ПИБ:\s*\d+\s*$", "", name or "").strip()


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("srbija", {})
    take = int(c.get("take", 100))  # servis ograničava stranicu na 100, ma koliko tražili
    max_pages = int(c.get("max_pages", 60))

    today = base.today().isoformat()
    s = base.session()
    headers = {"UserToken": _token(s)}
    flt = f'["SubmissionDeadline",">=","{today}"]'
    srt = '[{"selector":"NoticePublishDate","desc":true}]'

    rows: list[dict] = []
    total, skip, pages = None, 0, 0
    while True:
        params = {"skip": skip, "take": take, "filter": flt, "sort": srt}
        if total is None:
            params["requireTotalCount"] = "true"
        j = base.fetch(s, "GET", API, headers=headers, params=params).json()
        if not isinstance(j, dict) or not isinstance(j.get("data"), list):
            raise base.SourceChanged("Srbija: odgovor servisa nema očekivani oblik (data)")
        data = j["data"]
        if total is None:
            total = int(j.get("totalCount") or 0)
        rows += data
        pages += 1
        if not data or len(rows) >= total or pages >= max_pages:
            break
        skip += len(data)  # pomjeri za stvarno vraćen broj (servis vraća najviše 100 po strani)
        time.sleep(PAUSE)

    if total and not rows:
        raise base.SourceChanged("Srbija: servis javlja postupke, ali nijedan nije vraćen")

    out, seen = [], set()
    for r in rows:
        tid = r.get("Id")
        if tid in seen:  # ista nabavka zna doći više puta (lista se pomjera dok stižu nove objave)
            continue
        proc = r.get("ProcedureType") or ""
        if "без објављивања" in proc:  # pregovarački bez objave javnog poziva: nije otvoren za sve
            continue
        due = r.get("SubmissionDeadline")
        if base.iso_date(due) is None or base.iso_date(due) < today:
            continue
        seen.add(tid)
        cpv = re.findall(r"\b(\d{8})\b", r.get("CPVExtended") or "")
        val = r.get("EstimatedValue")
        out.append(base.rec(
            META["key"], tid,
            title=r.get("Name"),
            buyer=_buyer(r.get("ContractingBody") or r.get("BusinessEntityName") or ""),
            url=VIEW.format(tid),
            pub=r.get("NoticePublishDate"),
            due=due, due_time=due,
            countries=["RS"],
            region=r.get("Nuts"),
            ctype=KIND.get((r.get("TypeContract") or "").strip().lower()),
            ntype=proc,
            cpv=cpv,
            value=val if isinstance(val, (int, float)) and val > 0 else None,
            currency="RSD" if isinstance(val, (int, float)) and val > 0 else None,
            ref=r.get("ReferenceNumber"),
        ))
    return out


if __name__ == "__main__":
    base.cli(collect, META)
