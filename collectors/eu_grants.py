"""EU Funding & Tenders portal: otvoreni i najavljeni pozivi za grantove EU programa
(Horizon Europe, LIFE, Erasmus+, Digital Europe, CERV, Interreg i drugi).

Isti javni Search i Facet API kao eu_ft.py (tenderi), samo drugi tipovi objava.
"""
from __future__ import annotations

import re

from collectors import base
from collectors.eu_ft import _post, _v

META = {
    "key": "EUG",
    "name": "EU programi (grantovi)",
    "home": "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/"
            "opportunities/calls-for-proposals",
    "scope": "Otvoreni i najavljeni pozivi za grantove EU programa (Horizon Europe, LIFE, Erasmus+ "
             "i drugi); ko smije aplicirati piše u samom pozivu.",
}
QUERY = {"bool": {"must": [
    {"terms": {"type": ["1", "2", "8"]}},              # 1 tema poziva, 2 ostali grantovi, 8 kaskadno
    {"terms": {"status": ["31094501", "31094502"]}},   # najavljen, otvoren
    {"terms": {"DATASOURCE": ["SEDIA"]}},
]}}
FIELDS = ["identifier", "title", "callIdentifier", "callTitle", "deadlineDate", "startDate",
          "frameworkProgramme", "type", "url", "status"]
PORTAL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/"
TYPES = {"1": "Poziv za prijedloge", "2": "Grant", "8": "Kaskadno finansiranje"}
FORTHCOMING = "31094501"
PAGE = 100


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("eug", {})
    max_pages = int(c.get("max_pages", 20))
    s = base.session()
    facets = _post(s, "facet", {}, query=QUERY, languages=["en"])
    try:
        progs = {v["rawValue"]: v["value"] for f in facets["facets"] if f["name"] == "frameworkProgramme"
                 for v in f["values"]}
    except (KeyError, TypeError):
        progs = {}
    today = base.today().isoformat()
    out: dict[str, dict] = {}
    total, got = None, 0
    for page in range(1, max_pages + 1):
        d = _post(s, "search", {"pageSize": PAGE, "pageNumber": page}, query=QUERY, languages=["en"],
                  displayFields=FIELDS, sort={"field": "identifier", "order": "ASC"})
        try:
            total, res = int(d["totalResults"]), d["results"]
        except (KeyError, TypeError, ValueError):
            raise base.SourceChanged("EU grantovi: Search API je promijenio format.") from None
        for r in res:
            m = r.get("metadata") or {}
            got += 1
            ident, title = _v(m, "identifier"), _v(m, "title")
            if not ident or not title:
                continue
            dues = sorted(x for x in (base.iso_date(v) for v in (m.get("deadlineDate") or [])) if x)
            future = [x for x in dues if x >= today]
            if dues and not future:
                continue  # svi rokovi su prošli
            typ, url = _v(m, "type") or "1", _v(m, "url") or ""
            if typ == "1" or "portal/screen" not in url:
                url = PORTAL + "topic-details/" + ident
            cs = re.search(r"competitive-calls-cs/(\d+)", url)
            sid = ident + (f"-{cs[1]}" if cs else "")
            prog = progs.get(_v(m, "frameworkProgramme"), "")
            kind = TYPES.get(typ, "Grant") + (" (najavljen)" if _v(m, "status") == FORTHCOMING else "")
            out[sid] = base.rec(
                META["key"], sid, title=title, buyer=prog or "Evropska komisija", url=url,
                pub=_v(m, "startDate"), due=future[0] if future else None, btype="eu",
                ctype=base.OTHER, ntype=kind, ref=_v(m, "callIdentifier") or ident, kind="P")
        if got >= total or not res:
            break
    if not total:
        raise base.SourceChanged("EU grantovi: API ne vraća nijedan poziv; provjeriti filter.")
    return list(out.values())


if __name__ == "__main__":
    base.cli(collect, META)
