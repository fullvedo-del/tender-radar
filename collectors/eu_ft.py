"""EU Funding & Tenders portal: pozivi za tendere (javne nabavke) institucija i agencija EU.

Javni Search i Facet API portala, opisani na
https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time

from collectors import base

META = {
    "key": "EU",
    "name": "EU Funding & Tenders",
    "home": "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/"
            "opportunities/calls-for-tenders",
    "scope": "Otvoreni i najavljeni pozivi za tendere institucija i agencija EU; "
             "bez poziva za grantove.",
}

API = "https://api.tech.ec.europa.eu/search-api/prod/rest/"
DETAIL = ("https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/"
          "opportunities/tender-details/")
QUERY = {"bool": {"must": [
    {"terms": {"type": ["0"]}},                        # 0 = tender (1, 2, 8 = grantovi)
    {"terms": {"status": ["31094501", "31094502"]}},   # najavljen, otvoren
    {"terms": {"DATASOURCE": ["SEDIA"]}},              # bez zastarjelih kopija starog sistema
]}}
FIELDS = ["cftId", "identifier", "title", "startDate", "deadlineDate", "twoStageDeadlineDate",
          "closingDate", "cftEXARegistrationDeadline", "procedureType", "contractType",
          "mainCpvCode", "mainCpv", "placesOfDeliveryOrPerformance",
          "cftLeadContractingAuthorityCode", "cftPartyLegalEntityId", "cftContractNoticeLink",
          "callIdentifier", "cftEstimatedTotalProcedureValue"]
CTYPE = {"Services": base.SERVICES, "Supplies": base.GOODS, "Works": base.WORKS}
PAGE = 100  # API ne vraća više od 100 po stranici


def _post(s, what: str, params: dict, **parts) -> dict:
    """POST s JSON dijelovima u multipart obrascu, kao što ih šalje portal."""
    files = {k: (None, json.dumps(v), "application/json") for k, v in parts.items()}
    r = base.fetch(s, "POST", API + what, files=files,
                   params={"apiKey": "SEDIA", "text": "***", **params})
    time.sleep(0.6)
    try:
        return r.json()
    except ValueError:
        raise base.SourceChanged("EU F&T: API nije vratio JSON.") from None


def _labels(s) -> dict[str, dict[str, str]]:
    """Nazivi za šifre (vrsta postupka, vrsta ugovora, naručilac) iz Facet API-ja."""
    d = _post(s, "facet", {}, query=QUERY, languages=["en"])
    try:
        out = {f["name"]: {v["rawValue"]: v["value"] for v in f["values"]} for f in d["facets"]}
    except (KeyError, TypeError):
        out = {}
    if not {"procedureType", "contractType"} <= out.keys():
        raise base.SourceChanged("EU F&T: Facet API više ne daje nazive šifri.")
    return out


def _search(s, max_pages: int) -> list[dict]:
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        d = _post(s, "search", {"pageSize": PAGE, "pageNumber": page}, query=QUERY,
                  languages=["en"], displayFields=FIELDS,
                  sort={"field": "identifier", "order": "ASC"})
        try:
            total, res = int(d["totalResults"]), d["results"]
            out += [r["metadata"] for r in res]
        except (KeyError, TypeError, ValueError):
            raise base.SourceChanged("EU F&T: Search API je promijenio format.") from None
        if not total:
            raise base.SourceChanged("EU F&T: API ne vraća nijedan tender; "
                                     "vjerovatno su promijenjene šifre filtera.")
        if len(out) >= total:
            return out
        if not res:
            raise base.SourceChanged("EU F&T: API je prekinuo listu prije kraja.")
    raise base.SourceChanged(f"EU F&T: više od {max_pages * PAGE} tendera; provjeriti filter.")


def _v(m: dict, key: str):
    """Prva stvarna vrijednost polja (API daje liste; prazno je i "null", "[]")."""
    for v in m.get(key) or []:
        if v not in ("", "null", "[]", "{}", "[null,null]"):
            return v
    return None


def _buyer(m: dict, labels: dict):
    """Naručilac kako ga imenuje filter portala (engleski); inače vodeći naručilac
    iz same objave (na jeziku objave)."""
    name = labels.get("cftPartyLegalEntityId", {}).get(_v(m, "cftPartyLegalEntityId"))
    if name:
        return name
    try:
        cas = json.loads(_v(m, "cftLeadContractingAuthorityCode") or "[]")
        lead = next((c for c in cas if c.get("isLeadAuthority")), cas[0] if cas else {})
        return lead.get("name")
    except (ValueError, TypeError, AttributeError):
        return None


def _ted(m: dict):
    """TED broj objave ('680891-2026'), ako tender ima objavu u TED-u."""
    hit = re.search(r'TED:NOTICE:0*(\d+-\d{4})|"0*(\d+-\d{4})"',
                    _v(m, "cftContractNoticeLink") or "")
    return hit and (hit[1] or hit[2])


def _due(m: dict, ident: str):
    if ident.endswith("-PIN"):  # prethodna informacija: rok još nije određen
        return None
    if ident.endswith("-EXA"):  # ex-ante objava: rok za prijavu interesa
        return _v(m, "cftEXARegistrationDeadline")
    return _v(m, "deadlineDate") or _v(m, "twoStageDeadlineDate") or _v(m, "closingDate")


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("eu", {})
    max_pages = int(c.get("max_pages", 30))
    days = int(c.get("no_deadline_days", 60))
    today = base.today().isoformat()
    cutoff = (base.today() - dt.timedelta(days=days)).isoformat()
    s = base.session()
    labels = _labels(s)

    found = _search(s, max_pages)
    idents = {_v(m, "identifier") for m in found}
    out: dict[str, dict] = {}
    for m in found:
        ident = _v(m, "identifier") or ""
        if ident.endswith("-PIN") and ident[:-4] + "-CN" in idents:  # već raspisan (CN)
            continue
        sid, title, due = _v(m, "cftId") or ident, _v(m, "title"), _due(m, ident)
        d, p = base.iso_date(due), base.iso_date(_v(m, "startDate"))
        if not sid or not title or not (d >= today if d else (p or "") >= cutoff):
            continue
        val = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([A-Z]{3})",
                           _v(m, "cftEstimatedTotalProcedureValue") or "")
        proc = labels["procedureType"].get(_v(m, "procedureType"), "")
        places = m.get("placesOfDeliveryOrPerformance") or []  # NUTS ili ISO; EL = Grčka
        out[sid] = base.rec(
            META["key"], sid, title=title, buyer=_buyer(m, labels), url=DETAIL + sid,
            pub=p, due=d, due_time=due, countries=[{"EL": "GR"}.get(x[:2], x[:2]) for x in places],
            ctype=CTYPE.get(labels["contractType"].get(_v(m, "contractType"))),
            ntype=proc.replace("Call for Expression of Interest (CEI)", "CEI"),  # do 60 znakova
            cpv=re.findall(r"\d{8}", _v(m, "mainCpvCode") or "") + (m.get("mainCpv") or []),
            btype="eu", value=float(val[1]) if val else None, currency=val and val[2],
            ref=_ted(m) or _v(m, "callIdentifier"))
    if not any("d" in r for r in out.values()):
        raise base.SourceChanged("EU F&T: nijedan tender nema rok od danas nadalje; "
                                 "vjerovatno su promijenjena polja s rokom.")
    return list(out.values())


if __name__ == "__main__":
    base.cli(collect, META)
