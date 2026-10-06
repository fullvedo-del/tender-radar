"""Dobitnici: ko dobija ugovore za usluge i po kojoj cijeni (dugme "Dobitnici" na stranici).

Pokreće ga collect.py pri svakom osvježavanju; piše data/awards.json. Izvori:

  e-Nabavke BiH, javni OData API (open.ejn.gov.ba), skup Awards: dodijeljeni ugovori za usluge
     iz kategorija u config.json ("awards": "ejn_categories"), a iz kategorija "ejn_word_categories"
     (zadano: Ostale usluge) samo oni čiji naziv sadrži neku od riječi iz "ejn_words".
     Direktni sporazumi (mali ugovori bez nadmetanja) se zadano ne uzimaju ("ejn_direct").
     Dobitnik: grupa ponuđača kojoj je dodijeljen lot (SupplierGroups), njeni članovi
     (SupplierGroupSupplierLinks) i nazivi dobavljača (SuppliersBase, UnregisteredSuppliersBase).
  TED (EU), API v3: obavještenja o dodjeli ugovora (form-type = result) za usluge s mjestom
     izvršenja ili naručiocem u državama iz config.json (ted.countries) i CPV kodovima "ted_cpv".

e-Nabavke daje najviše 50 dodjela po zahtjevu, pa se prvih 12 mjeseci preuzima od najnovijih
naniže i, ako ne stane u vrijeme jednog osvježavanja, nastavlja sutra. Poslije toga se svaki dan
preuzimaju samo dodjele izmijenjene od zadnjeg puta. TED se svaki dan čita cijeli (nekoliko
stotina objava). Ako izvor ne radi, ostaju zadnji preuzeti podaci.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import time
import traceback
from collections import defaultdict

from collectors import base, ejn, ted

DEFAULTS = {
    "on": True,
    "days": 365,           # koliko unazad (po datumu ugovora)
    "minutes": 8,          # vremenski okvir u jednom osvježavanju
    # e-Nabavke, kategorije usluga (Id iz šifarnika ContractCategories):
    # 59 istraživanje i razvoj, 61 istraživanje tržišta i javnog mnijenja, 62 konsalting u menadžmentu,
    # 63 arhitektonske, inženjerske i naučno-tehničke konsultantske usluge, 77 ostale usluge
    "ejn_categories": [59, 61, 62, 63],
    "ejn_word_categories": [77],
    "ejn_words": ["okoli", "životne sredine", "energetsk", "energijsk", "zagađ", "stakleničk", "klimatsk",
                  "otpadom", "otpadnih voda", "studija", "studije", " buke", "zraka", "održiv"],
    "ejn_direct": False,   # i direktni sporazumi
    "ted_cpv": ["71", "73", "793", "794", "907"],
}
EJN_SELECT = ("LotName,Value,ContractDate,ContractingAuthorityName,ProcedureId,ProcedureName,"
              "ProcedureType,NoticeNumber,NumberOfReceivedOffers,LowestAcceptableOfferValue,"
              "HighestAcceptableOfferValue")
WORDS_PER_QUERY = 7    # API odbija filter s više od 100 čvorova
PAGE_SHARE = 0.75      # dio vremena za stranice dodjela; ostatak je za dobitnike i linkove
TED_FIELDS = ["publication-number", "publication-date", "notice-type", "title-proc", "notice-title",
              "buyer-name", "buyer-country", "winner-name", "result-value-notice",
              "result-value-cur-notice", "tender-value", "tender-value-cur", "tender-value-lowest",
              "tender-value-highest", "received-submissions-type-code", "received-submissions-type-val",
              "contract-conclusion-date", "place-of-performance-country-proc",
              "place-of-performance-country-lot", "main-classification-proc"]


def _conf(cfg: dict) -> dict:
    return {**DEFAULTS, **(cfg.get("awards") or {})}


def _q(text) -> str:
    """Tekst kao OData konstanta."""
    return "'" + str(text).replace("'", "''") + "'"


def _stamp(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _short(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


# --------------------------------------------------------------------------- e-Nabavke

def _ejn_queries(api, conf: dict) -> list[str]:
    """Filteri za skup Awards (bez datuma), po jedan za kategorije i za svaku grupu riječi."""
    cats = {c["Id"]: c["Name"] for c in api.rows("ContractCategories", "Type eq 'Services'", "Name")}
    want = [int(x) for x in conf["ejn_categories"]]
    by_word = [int(x) for x in conf["ejn_word_categories"]]
    missing = [x for x in want + by_word if x not in cats]
    if missing:
        raise base.SourceChanged(f"e-Nabavke: u šifarniku nema kategorija usluga {missing}")
    head = "ContractType eq 'Services'"
    if not conf["ejn_direct"]:
        head += " and ProcedureType ne 'DirectAgreement'"
    out = []
    if want:
        out.append(f"{head} and ContractCategoryName in ({','.join(_q(cats[x]) for x in want)})")
    words = [str(w).lower() for w in conf["ejn_words"] if str(w).strip()]
    for x in by_word:
        for i in range(0, len(words), WORDS_PER_QUERY):
            part = " or ".join(f"contains(tolower(ProcedureName),{_q(w)})" for w in words[i:i + WORDS_PER_QUERY])
            out.append(f"{head} and ContractCategoryName eq {_q(cats[x])} and ({part})")
    return out


def _page(s, flt: str, below: int | None) -> tuple[list, bool]:
    """Jedna stranica dodjela (najviše 50), od najvećeg Id-a naniže; below: samo Id manji od toga."""
    r = base.fetch(s, "GET", ejn.API + "Awards", tries=4, pause=5.0, params={
        "$filter": f"({flt})" + (f" and Id lt {below}" if below else ""),
        "$select": "Id," + EJN_SELECT, "$orderby": "Id desc"})
    time.sleep(ejn.PAUSE)
    try:
        d = r.json()
        page = d["value"]
        if not isinstance(page, list) or not all(isinstance(x, dict) and "Id" in x for x in page):
            raise TypeError
        return page, "@odata.nextLink" in d
    except (ValueError, KeyError, TypeError):
        raise base.SourceChanged("e-Nabavke: API za dodjele ugovora je vratio neočekivan format.") from None


def _in(api, entity: str, field: str, ids, select: str, extra: str = "") -> list[dict]:
    """Redovi kojima je field među ids, u grupama (server odbija upit duži od 2048 znakova)."""
    ids, out = sorted(set(ids)), []
    for i in range(0, len(ids), api.batch):
        chunk = ",".join(str(x) for x in ids[i:i + api.batch])
        out += api.rows(entity, f"{field} in ({chunk}){extra}", select)
    return out


def _winners(api, lots) -> dict:
    """Id lota (= Id dodjele) -> nazivi dobitnika, vodeći član grupe prvi."""
    groups = _in(api, "SupplierGroups", "LotId", lots, "LotId", " and IsAwarded eq true")
    lot_of = {g["Id"]: g["LotId"] for g in groups}
    links = _in(api, "SupplierGroupSupplierLinks", "SupplierGroupId", lot_of,
                "SupplierGroupId,SupplierId,IsLead")
    other = _in(api, "SupplierGroupUnregisteredSupplierLinks", "SupplierGroupId", lot_of,
                "SupplierGroupId,UnregisteredSupplierId,IsLead")
    names = {x["Id"]: x["Name"] for x in _in(api, "SuppliersBase", "Id",
                                             {k["SupplierId"] for k in links}, "Name")}
    names2 = {x["Id"]: x["Name"] for x in _in(api, "UnregisteredSuppliersBase", "Id",
                                              {k["UnregisteredSupplierId"] for k in other}, "Name")}
    members = defaultdict(list)  # lot -> [(nije vodeći, Id veze, naziv)]
    for k in links:
        members[lot_of[k["SupplierGroupId"]]].append((not k["IsLead"], k["Id"], names.get(k["SupplierId"])))
    for k in other:
        members[lot_of[k["SupplierGroupId"]]].append((not k["IsLead"], k["Id"], names2.get(k["UnregisteredSupplierId"])))
    out = {}
    for lot, ms in members.items():
        out[lot] = list(dict.fromkeys(base.clean(n) for _, _, n in sorted(ms) if base.clean(n)))
    return out


def _notices(api, procedures) -> dict:
    """Id postupka -> Id obavještenja o nabavci (za link na portal); direktni sporazumi i
    pregovarački postupci bez objave nemaju obavještenje."""
    return {x["ProcedureId"]: x["Id"] for x in _in(api, "ProcurementNoticesBase", "ProcedureId",
                                                   procedures, "ProcedureId")}


def _ejn_rec(x: dict, wins: list, linked: dict) -> dict | None:
    if not x.get("ContractDate"):
        return None
    title = base.clean(x.get("ProcedureName"))
    rec = {"id": f"EJN-{x['Id']}", "s": "EJN", "d": ejn._local(x["ContractDate"]).date().isoformat(),
           "c": "BA", "b": base.clean(x.get("ContractingAuthorityName")), "t": _short(title, 300)}
    lot = base.clean(x.get("LotName"))
    if lot and base.norm(lot) != base.norm(title):
        rec["l"] = _short(lot, 200)
    if x.get("Value"):
        rec["v"], rec["cur"] = round(float(x["Value"]), 2), "BAM"
    if wins:
        rec["w"] = wins
    if x.get("NumberOfReceivedOffers"):
        rec["n"] = int(x["NumberOfReceivedOffers"])
    lo, hi = x.get("LowestAcceptableOfferValue"), x.get("HighestAcceptableOfferValue")
    if lo and hi and float(hi) > float(lo):
        rec["lo"], rec["hi"] = round(float(lo), 2), round(float(hi), 2)
    if x.get("ProcedureId") in linked:  # link na obavještenje o nabavci; stranica ga slaže iz urls
        rec["pn"] = linked[x["ProcedureId"]]
    elif x.get("NoticeNumber"):  # bez obavještenja: broj obavještenja o dodjeli, za pretragu na portalu
        rec["ref"] = base.clean(x["NoticeNumber"])
    if x.get("ProcedureType") == "DirectAgreement":
        rec["dir"] = 1
    return rec if rec["t"] else None


def _ejn(conf: dict, state: dict, stop: float) -> tuple[list, dict, dict]:
    """(nove ili izmijenjene dodjele, novo stanje, info). Stanje pamti dokle se stiglo.
    info["reset"]: kategorije ili riječi su promijenjene, pa ranije dodjele s e-Nabavki ne važe."""
    api = ejn._Api({"max_requests": 3000, "batch": 150})
    s = base.session()
    queries = _ejn_queries(api, conf)
    key = hashlib.sha1(json.dumps([queries, conf["days"]]).encode("utf-8")).hexdigest()[:10]
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = (base.today() - dt.timedelta(days=int(conf["days"]))).isoformat()
    since_date = f"ContractDate ge {cutoff}T00:00:00Z"
    reset = state.get("key") != key
    if reset:  # prvi put ili su promijenjene kategorije ili riječi: ispočetka
        state = {"key": key, "t0": _stamp(now), "pos": [None] * len(queries)}
    page_stop = time.time() + max(0.0, stop - time.time()) * PAGE_SHARE
    rows: dict[int, dict] = {}
    complete = True
    if "pos" in state:  # prvo preuzimanje 12 mjeseci, od najnovijih naniže
        for i, q in enumerate(queries):
            below, fresh, got = state["pos"][i], state["pos"][i] is None, 0
            while below != "done":
                if time.time() > page_stop:
                    complete = False
                    break
                page, more = _page(s, f"{q} and {since_date}", below)
                for x in page:
                    rows[x["Id"]] = x
                got += len(page)
                below = page[-1]["Id"] if page and more else "done"
            if i == 0 and fresh and below == "done" and not got and conf["ejn_categories"]:
                raise base.SourceChanged("e-Nabavke: API ne vraća nijednu dodjelu ugovora za izabrane "
                                         "kategorije usluga; filter vjerovatno više ne radi.")
            state["pos"][i] = below
            if not complete:
                break
        if complete:
            state = {"key": key, "upd": state["t0"]}
    else:  # svaki dan: dodjele izmijenjene od zadnjeg osvježavanja (s dva dana preklapanja)
        upd = dt.datetime.fromisoformat(state["upd"].replace("Z", "+00:00")) - dt.timedelta(days=2)
        for q in queries:
            below = None
            while below != "done":
                if time.time() > page_stop:
                    complete = False
                    break
                page, more = _page(s, f"{q} and {since_date} and LastUpdated ge {_stamp(upd)}", below)
                for x in page:
                    rows[x["Id"]] = x
                below = page[-1]["Id"] if page and more else "done"
            if not complete:
                break
        if complete:
            state["upd"] = _stamp(now)
    wins = _winners(api, list(rows)) if rows else {}
    linked = _notices(api, {x["ProcedureId"] for x in rows.values()}) if rows else set()
    recs = [r for r in (_ejn_rec(x, wins.get(x["Id"], []), linked) for x in rows.values()) if r]
    info = {"new": len(recs), "done": "pos" not in state, "reset": reset}
    return recs, state, info


# --------------------------------------------------------------------------- TED

def _num(value) -> float | None:
    try:
        v = float(value)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _first(value):
    return value[0] if isinstance(value, list) and value else value if isinstance(value, str) else None


def _ted_rec(n: dict) -> dict | None:
    sid = n.get("publication-number")
    names = n.get("winner-name") or {}
    wins = list(dict.fromkeys(base.clean(x) for x in (next(iter(names.values()), []) if isinstance(names, dict) else [])
                              if base.clean(x)))
    value, cur = _num(n.get("result-value-notice")), _first(n.get("result-value-cur-notice"))
    if value is None:  # zbir vrijednosti ugovora (lotova), ako su u istoj valuti
        parts = [v for v in map(_num, n.get("tender-value") or []) if v]
        curs = set(n.get("tender-value-cur") or [])
        if parts and len(curs) == 1:
            value, cur = sum(parts), curs.pop()
    if not isinstance(sid, str) or not (wins or value):  # postupak bez dodjele (npr. obustavljen)
        return None
    title = (ted._texts(n.get("title-proc")) or [""])[0]
    if not title:  # stara šema: "Država – CPV – naslov"
        title = (ted._texts(n.get("notice-title")) or [""])[0].split(" – ")[-1]
    buyers = ted._texts(n.get("buyer-name"))
    places = (n.get("place-of-performance-country-proc") or n.get("place-of-performance-country-lot")
              or n.get("buyer-country") or [])
    cc = "XK" if places and places[0] in ted.KOSOVO else base.country_code(places[0]) if places else None
    # Datum objave dodjele: ugovor je ponekad zaključen mnogo ranije, a upit ide po datumu objave.
    rec = {"id": f"TED-{sid}", "s": "TED", "d": base.iso_date(n.get("publication-date")),
           "c": cc or "", "b": (buyers[0] + (f" (+{len(buyers) - 1})" if len(buyers) > 1 else "")) if buyers else "",
           "t": _short(base.clean(title), 300)}
    if value:
        rec["v"], rec["cur"] = round(value, 2), cur or "EUR"
    if wins:
        rec["w"] = wins[:12]
    codes, vals = n.get("received-submissions-type-code") or [], n.get("received-submissions-type-val") or []
    offers = [int(v) for c, v in zip(codes, vals) if c == "tenders" and str(v).isdigit()]
    if len(offers) == 1 and offers[0] > 0:
        rec["n"] = offers[0]
    elif len(offers) > 1:
        rec["lots"] = len(offers)
    lo, hi = [_num(_first(n.get(f))) for f in ("tender-value-lowest", "tender-value-highest")]
    if lo and hi and hi > lo and len(offers) <= 1:
        rec["lo"], rec["hi"] = lo, hi
    cpv = _first(n.get("main-classification-proc"))
    if cpv:
        rec["cpv"] = cpv
    return rec if rec["t"] and rec["d"] else None


def _ted(conf: dict, cfg: dict) -> list:
    t = cfg.get("ted", {})
    since = (base.today() - dt.timedelta(days=int(conf["days"]))).strftime("%Y%m%d")
    codes = " ".join(dict.fromkeys(c for x in t.get("countries") or ted.COUNTRIES for c in ted._ted_countries(x)))
    geo = " OR ".join(f"{f} IN ({codes})" for f in (
        "place-of-performance-country-proc", "place-of-performance-country-lot", "buyer-country"))
    cpv = " ".join(f"{str(p).strip()}*" for p in conf["ted_cpv"] if str(p).strip().isdigit())
    query = (f"form-type = result AND publication-date >= {since} AND NOT notice-type IN (can-modif)"
             " AND contract-nature = services AND NOT contract-nature-main-proc IN (supplies works)"
             f" AND ({geo})" + (f" AND classification-cpv IN ({cpv})" if cpv else ""))
    out = []
    for n in ted._search(base.session(), query, TED_FIELDS):
        try:
            rec = _ted_rec(n)
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            raise base.SourceChanged(f"TED dodjela {n.get('publication-number')}: neočekivan oblik polja") from e
        if rec:
            out.append(rec)
    return out


# --------------------------------------------------------------------------- glavni tok

def write(path: str, meta: dict, recs: list) -> None:
    """Jedna dodjela po redu, da su dnevne razlike u git-u male."""
    tmp = path + ".tmp"
    head = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(head[:-1] + ',"a":[\n')
        f.write(",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in recs))
        f.write("\n]}\n")
    os.replace(tmp, path)


def run(cfg: dict, path: str, minutes: float | None = None) -> dict:
    """Osvježava data/awards.json. Vraća stanje za status.json."""
    conf = _conf(cfg)
    try:
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
    except (OSError, ValueError):
        old = {}
    if not isinstance(old, dict):
        old = {}
    budget = float(conf["minutes"]) if minutes is None else min(float(conf["minutes"]), minutes)
    if not conf["on"]:
        return {"on": False}
    now = dt.datetime.now(dt.timezone.utc)
    stamp = _stamp(now)
    stop = time.time() + max(0.0, budget) * 60
    cutoff = (base.today() - dt.timedelta(days=int(conf["days"]))).isoformat()
    recs = {r["id"]: r for r in old.get("a") or [] if isinstance(r, dict) and r.get("id")}
    state = old.get("state") or {}
    src = old.get("src") or {}
    for key, name in (("TED", "TED (EU)"), ("EJN", "e-Nabavke BiH")):
        before = src.get(key) or {}
        if time.time() > stop - 20:
            src[key] = dict(before, name=name, error="nije stiglo na red u ovom osvježavanju (isteklo vrijeme)")
            continue
        st = {"name": name, "last_ok": before.get("last_ok"), "done": before.get("done", False)}
        t0 = time.time()
        try:
            if key == "TED":
                fresh = _ted(conf, cfg)
                info = {"new": len(fresh), "done": True, "reset": True}  # TED se čita cijeli
            else:
                fresh, state["EJN"], info = _ejn(conf, state.get("EJN") or {}, stop)
            if info.pop("reset"):
                for k in [k for k, r in recs.items() if r["s"] == key]:
                    del recs[k]
            for r in fresh:
                recs[r["id"]] = r
            st.update(info, ok=True, error=None, last_ok=stamp)
        except Exception as e:  # izvor ne radi: ostaju zadnji podaci
            traceback.print_exc()
            st.update(ok=False, error=f"{e}"[:300] or type(e).__name__)
        st["sec"] = round(time.time() - t0, 1)
        src[key] = st
    out = sorted((r for r in recs.values() if (r.get("d") or "") >= cutoff),
                 key=lambda r: (r.get("d") or "", r["id"]), reverse=True)
    for key in src:
        src[key]["count"] = sum(1 for r in out if r["s"] == key)
    urls = {"EJN": (cfg.get("ejn") or {}).get("url", ejn.PAGE),  # {id}: Id obavještenja (pn)
            "TED": ted.META["home"] + "/en/notice/-/detail/{id}"}  # {id}: broj objave (id bez "TED-")
    write(path, {"v": 1, "generated": stamp, "days": int(conf["days"]), "since": cutoff, "urls": urls,
                 "src": src, "state": state}, out)
    return {"on": True, "count": len(out), "done": all(s.get("done", False) for s in src.values()),
            "sources": {k: {x: s.get(x) for x in ("ok", "count", "done", "error", "last_ok", "sec")}
                        for k, s in src.items()}}


if __name__ == "__main__":  # ručna proba: python awards.py [folder] [minuta]
    import sys
    folder = sys.argv[1] if len(sys.argv) > 1 else "data"
    os.makedirs(folder, exist_ok=True)
    print(json.dumps(run(json.load(open("config.json", encoding="utf-8")), os.path.join(folder, "awards.json"),
                         float(sys.argv[2]) if len(sys.argv) > 2 else None), ensure_ascii=False, indent=1))
