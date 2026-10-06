"""e-Nabavke BiH: otvorena obavještenja o nabavci iz sistema e-Nabavke.

Izvor je dokumentovani javni OData API Agencije za javne nabavke BiH
(https://open.ejn.gov.ba, opis na https://open.ejn.gov.ba/docs/index.html); ključ nije potreban.
Skupovi s punim opisom (ProcurementNotices) daju najviše 50 redova po zahtjevu, a osnovni
(...Base, LotCpvCodeLinks) 1000, pa se lotovi i šifarnici čitaju iz osnovnih skupova.

Sam portal (next.ejn.gov.ba) se ne čita: njegovi uslovi korištenja dozvoljavaju automatsko
preuzimanje samo kanalom koji Agencija izričito omogući, a to je ovaj API. Na portal se samo
linkuje.
"""
from __future__ import annotations

import datetime as dt
import re
import textwrap
import time
from collections import defaultdict

from collectors import base

META = {
    "key": "EJN",
    "name": "e-Nabavke BiH",
    "home": "https://next.ejn.gov.ba",
    "scope": "Sva obavještenja o nabavci (robe, usluge, radovi) kojima rok za ponude ili zahtjeve "
             "za učešće nije istekao; bez poništenih postupaka, direktnih sporazuma i javnih "
             "poziva za usluge iz Aneksa II.",
}

API = "https://open.ejn.gov.ba/"
# Stranica "Pregled obavještenja o nabavci" na portalu; {id} je Id obavještenja iz API-ja.
PAGE = "https://next.ejn.gov.ba/bs-latn-ba/procurement-notices/{id}/overview"
PAUSE = 0.6
NOTICE = ("Number,ProcedureId,ProcedureName,ProcedureType,ContractType,ContractingAuthorityName,"
          "ContractingAuthorityCityName,ContractingAuthorityType,"
          "ContractingAuthorityActivityTypeName,ContractingAuthorityAdministrativeUnitType,"
          "ContractingAuthorityAdministrativeUnitName,ApplicationDeadlineDateTime,Announced")
LOT = "ProcedureId,No,Status,EstimatedValue,ApplicationDeadlineDateTime,Name,ShortDescription"

CTYPE = {"Goods": base.GOODS, "Services": base.SERVICES, "Works": base.WORKS}
PROCEDURE = {  # nazivi iz obrasca obavještenja (IV 1. Vrsta postupka)
    "OpenProcedure": "Otvoreni postupak",
    "RestrictedProcedure": "Ograničeni postupak",
    "NegotiatedProcedureWithProcurementNotice": "Pregovarački postupak sa objavom obavještenja",
    "CompetitiveDialog": "Takmičarski dijalog",
    "ConceptualDesign": "Konkurs za izradu idejnog rješenja",
    "CompetitiveRequest": "Konkurentski zahtjev",
}
AUTHORITY = {  # nazivi iz obrasca obavještenja (I 5.a. Vrsta ugovornog organa)
    "GovernmentInstitution": "Institucija vlasti",
    "PublicEntity": "Pravno lice iz čl. 4(1)b) ZJN",
    "SectoralContractingAuthority": "Sektorski ugovorni organ",
}
LOCAL = ("Municipality", "City")
LEVEL = {"Country": "central", "Entity": "regional", "Canton": "regional",
         "District": "regional", "City": "local", "Municipality": "local"}
# Pravno lice iz čl. 4(1)b) vodi se kao javno preduzeće ako u nazivu nosi oznaku preduzeća
# ili privrednog društva (JP, JKP, d.o.o., d.d., a.d. ...), inače kao javna ustanova.
COMPANY = re.compile(
    r"\b(jk?u?p|kjk?p|doo|dd|ad|јк?п|доо|ад)\b|(pre|po)duze[cć]|предузећ|"
    r"(akcionarsko|dioni[cč]ko|акционарско) (dru|дру)|ograni[cč]enom odgovorno", re.I)


class _Api:
    """Čitanje OData skupova uz pauzu između zahtjeva i gornje granice (zahtjevi, redovi)."""

    def __init__(self, c: dict):
        self.s = base.session()
        self.left = int(c.get("max_requests", 250))
        self.max_rows = int(c.get("max_rows", 30000))
        self.batch = int(c.get("batch", 150))

    def rows(self, entity: str, flt: str, select: str) -> list[dict]:
        """Svi redovi upita. Kad API odreže odgovor, dodaje @odata.nextLink; čitanje se tada
        nastavlja po ključu (Id), pa izmjene u bazi tokom čitanja ne pomjeraju stranice."""
        out: list[dict] = []
        last = 0
        while True:
            if self.left <= 0:
                raise base.SourceChanged("e-Nabavke: prekoračen dozvoljeni broj zahtjeva; "
                                         "API vraća neočekivano mnogo podataka.")
            self.left -= 1
            r = base.fetch(self.s, "GET", API + entity, tries=4, pause=5.0, params={
                "$filter": f"({flt}) and Id gt {last}", "$select": "Id," + select,
                "$orderby": "Id", "$count": "true"})
            time.sleep(PAUSE)
            try:
                d = r.json()
                page, more = d["value"], "@odata.nextLink" in d
                total = int(d.get("@odata.count") or 0)
                last = page[-1]["Id"] if page else last
            except (ValueError, KeyError, TypeError):
                raise base.SourceChanged("e-Nabavke: API je vratio neočekivan format.") from None
            if total > self.max_rows:  # filter je prestao djelovati
                raise base.SourceChanged(f"e-Nabavke: neočekivano mnogo redova ({total}) u skupu "
                                         f"{entity}; filter API-ja vjerovatno više ne radi.")
            out += page
            if not more:
                return out
            if not page:
                raise base.SourceChanged("e-Nabavke: API je prekinuo listu prije kraja.")

    def by_ids(self, entity: str, field: str, ids, select: str, size: int = 0) -> list[dict]:
        """Redovi kojima je `field` među `ids`. ID-evi idu u grupama jer server odbija
        upit duži od 2048 znakova."""
        ids, size = sorted(set(ids)), size or self.batch
        out: list[dict] = []
        for i in range(0, len(ids), size):
            chunk = ",".join(str(x) for x in ids[i:i + size])
            out += self.rows(entity, f"{field} in ({chunk})", select)
        return out


def _local(stamp: str) -> dt.datetime:
    """Vrijeme iz API-ja (UTC) u vrijeme po kojem BiH računa rok (CET/CEST), kako ga navodi
    i samo obavještenje. Ljetno vrijeme: od zadnje nedjelje marta do zadnje nedjelje oktobra,
    promjena u 01:00 UTC."""
    try:
        t = dt.datetime.fromisoformat(stamp)
        u = t.astimezone(dt.timezone.utc).replace(tzinfo=None) if t.tzinfo else None
    except (TypeError, ValueError):
        u = None
    if u is None:
        raise base.SourceChanged("e-Nabavke: neočekivan format datuma u API-ju.")

    def change(month: int) -> dt.datetime:
        d = dt.datetime(u.year, month, 31, 1)
        return d - dt.timedelta(days=(d.weekday() + 1) % 7)

    return u + dt.timedelta(hours=2 if change(3) <= u < change(10) else 1)


def _regions(api: _Api) -> dict:
    """(vrsta, naziv) općine ili grada -> kanton, entitet ili distrikt kojem pripada."""
    units = {u["Id"]: u for u in api.rows("AdministrativeUnitsBase", "Id gt 0",
                                          "Name,HigherUnitId,Type")}
    out = {}
    for u in units.values():
        top = u
        for _ in range(4):  # općina -> grad -> kanton ili entitet
            if top is None or top["Type"] not in LOCAL:
                break
            top = units.get(top["HigherUnitId"])
        if top is not None and top["Type"] not in LOCAL:
            out[(u["Type"], u["Name"])] = top["Name"]
    if not out:
        raise base.SourceChanged("e-Nabavke: šifarnik administrativnih jedinica je prazan.")
    return out


def _btype(n: dict) -> str | None:
    kind = n.get("ContractingAuthorityType")
    if kind == "GovernmentInstitution":
        return LEVEL.get(n.get("ContractingAuthorityAdministrativeUnitType"))
    if kind == "SectoralContractingAuthority":
        return "pubco"
    if kind == "PublicEntity":
        name = (n.get("ContractingAuthorityName") or "").replace(".", "")
        return "pubco" if COMPANY.search(name) else "pubinst"
    return None


def _open_until(n: dict, lots: list[dict], today: dt.date) -> dt.datetime | None:
    """Rok po vremenu BiH ako je obavještenje još otvoreno, inače None.

    Poništen lot ima status Terminated; postupak je otvoren dok je otvoren bar jedan lot.
    Ispravka roka kod postupka s lotovima upisuje se samo na lotove, pa rok lota ima prednost
    pred rokom iz obavještenja."""
    parts = [x for x in lots if x["No"] is not None] or lots
    live = [x for x in parts if x["Status"] == "Announced"]
    if lots and not live:
        return None
    stamps = [x["ApplicationDeadlineDateTime"] for x in live if x["ApplicationDeadlineDateTime"]]
    stamps = stamps or [n["ApplicationDeadlineDateTime"]]
    dues = sorted(d for d in (_local(x) for x in stamps if x) if d.date() >= today)
    return dues[0] if dues else None


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("ejn", {})
    link = c.get("url", PAGE)
    api = _Api(c)
    today = base.today()
    # Ponoć po vremenu BiH je 22:00 ili 23:00 UTC prethodnog dana.
    since = f"ApplicationDeadlineDateTime ge {today - dt.timedelta(days=1)}T22:00:00Z"

    notices = api.rows("ProcurementNotices", since, NOTICE)
    if not notices:
        raise base.SourceChanged("e-Nabavke: API ne vraća nijedno otvoreno obavještenje; "
                                 "filter po roku vjerovatno ne radi.")
    # Obavještenja kojima je rok produžen samo na lotovima (rok u obavještenju je ostao stari);
    # po 50 ID-eva, koliko redova ovaj skup i daje po zahtjevu.
    known = {n["ProcedureId"] for n in notices}
    late = {x["ProcedureId"] for x in api.rows("LotsBase", since, "ProcedureId")} - known
    notices += api.by_ids("ProcurementNotices", "ProcedureId", late, NOTICE, size=50)

    lots = defaultdict(list)
    for x in api.by_ids("LotsBase", "ProcedureId", [n["ProcedureId"] for n in notices], LOT):
        lots[x["ProcedureId"]].append(x)
    if not lots:
        raise base.SourceChanged("e-Nabavke: API ne vraća lotove otvorenih postupaka.")

    try:
        found = []  # (obavještenje, rok, lot koji predstavlja cijeli postupak)
        for n in notices:
            mine = lots.get(n["ProcedureId"], [])
            due = _open_until(n, mine, today)
            if due and base.clean(n["ProcedureName"]):
                found.append((n, due, next((x for x in mine if x["No"] is None), None)))
    except (KeyError, TypeError):
        raise base.SourceChanged(
            "e-Nabavke: u odgovoru API-ja nedostaju očekivana polja.") from None
    if not found:
        raise base.SourceChanged("e-Nabavke: nijedno obavještenje nije prepoznato kao otvoreno.")

    # CPV kodovi postupka vezani su za lot bez rednog broja; glavni kod ide prvi.
    links = api.by_ids("LotCpvCodeLinks", "LotId", [w["Id"] for _, _, w in found if w],
                       "LotId,CpvCodeId,IsMain")
    codes = {x["Id"]: x["Code"] for x in api.by_ids(
        "CpvCodesBase", "Id", [k["CpvCodeId"] for k in links], "Code")}
    if not codes:
        raise base.SourceChanged("e-Nabavke: API ne vraća CPV kodove otvorenih postupaka.")
    cpv = defaultdict(list)
    for k in sorted(links, key=lambda k: (not k["IsMain"], k["Id"])):
        cpv[k["LotId"]].append(codes.get(k["CpvCodeId"]))
    regions = _regions(api)

    out = []
    for n, due, whole in found:
        # opis za AI sažetak: kratki opis postupka i prvih lotova (ne piše se u podatke)
        parts = [whole.get("ShortDescription") if whole else None] + [
            f"{x.get('Name') or ''}: {x.get('ShortDescription') or ''}".strip(": ")
            for x in sorted(lots.get(n["ProcedureId"], []), key=lambda x: x.get("No") or 0) if x.get("No")][:5]
        desc = base.clean(" | ".join(p for p in parts if p))
        level = n.get("ContractingAuthorityAdministrativeUnitType")
        unit = n.get("ContractingAuthorityAdministrativeUnitName")
        kind = n.get("ContractingAuthorityType")
        value = whole["EstimatedValue"] if whole else None  # bez PDV-a, u KM
        out.append(base.rec(
            META["key"], n["Id"], title=n["ProcedureName"],
            buyer=n.get("ContractingAuthorityName"),
            url=link.format(id=n["Id"]),
            pub=_local(n["Announced"]) if n.get("Announced") else None,
            due=due, due_time=due, countries=["BA"],
            region=regions.get((level, unit)) if level in LOCAL else unit,
            place=n.get("ContractingAuthorityCityName"),
            ctype=CTYPE.get(n.get("ContractType")),
            ntype=PROCEDURE.get(n.get("ProcedureType"), n.get("ProcedureType")),
            cpv=cpv[whole["Id"]] if whole else None,
            btype=_btype(n),
            btype_raw=textwrap.shorten("; ".join(x for x in (
                AUTHORITY.get(kind, kind), n.get("ContractingAuthorityActivityTypeName")) if x),
                80, placeholder="…"),
            value=value, currency="BAM" if value else None,
            ref=n.get("Number")))
        if len(desc) > 40:
            out[-1]["_desc"] = desc[:3000]
    return out


if __name__ == "__main__":
    base.cli(collect, META)
