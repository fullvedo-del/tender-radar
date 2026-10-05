"""Sjeverna Makedonija: Elektronski sistem javnih nabavki (e-nabavki.gov.mk, Biro za javne nabavke).

Aktuelni oglasi iz javne tabele "Огласи" (PublicAccess, bez prijave). Ista tabela se puni preko
javnog servisa Services/Notices.asmx/GetGridData; robots.txt ga ne zabranjuje.
Zadano se uzimaju samo usluge (config.json, "mk": {"types": [...]}); naslovi su na makedonskom,
a AI prijevod (ai_score.translate) dodaje kratak engleski prijevod.
"""
from __future__ import annotations

import json
import re
import time

from collectors import base

META = {
    "key": "ESJN",
    "name": "e-Nabavki Sjeverna Makedonija",
    "home": "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices",
    "scope": "Aktuelni oglasi javnih nabavki u Sjevernoj Makedoniji (zadano samo usluge); naslovi "
             "su na makedonskom, uz AI prijevod na engleski.",
}
WEB = "https://e-nabavki.gov.mk/"
GRID = WEB + "Services/Notices.asmx/GetGridData"
COLUMNS = ["ProcessNumber", "ContractingInstitutionName", "Subject", "GoodsWorksServices",
           "EntityProcedureType", "AnnouncementDate", "FinalDay", "Documents"]
SEARCH = {"ContractingInstitution": "", "EauctionOnly": False, "TypeOfPublicContract": "",
          "Status": 1,  # 1 = aktuelni oglasi (rok nije prošao), 2 = završeni
          "OngoingComplitedStatus": "", "TypeOfProcedure": 0, "ProcessNumber": "",
          "IsSmallPublicProcurement": False, "EprocurementOnly": False, "PrivatePartnershipOnly": False,
          "ContractingInstitutionName": "", "Subject": "", "PeriodFrom": "", "PeriodTo": "",
          "SmallOnly": False, "BigOnly": False, "LotSubject": "", "OfferType": ""}
KIND = {"Services": base.SERVICES, "Goods": base.GOODS, "Works": base.WORKS}
PROCEDURE = {
    "Open": "Otvoreni postupak",
    "SimplifiedOpenProcedure": "Pojednostavljeni otvoreni postupak",
    "LowEstimatedValueProcedure": "Nabavka male vrijednosti",
    "QualificationSystem": "Kvalifikacioni sistem",
    "ProcedureForTalkingWithPreviousAnnouncement": "Pregovarački postupak s objavom",
    "BidForChoosingIdealSolution": "Konkurs za idejno rješenje",
    "RequestForProposal": "Zahtjev za prijedloge",
    "CompetitiveDialogue": "Konkurentni dijalog",
}
PAGE = 100
# Vrsta naručioca po početku naziva (makedonski); ostalo je "nepoznato".
BUYER_RX = [
    ("central", re.compile(r"^(Министерство|Влада|Агенција|Управа|Дирекција|Државн|Собрание|Биро|"
                           r"Фонд|Народна банка|Царинска|Комисија|Завод|Инспекторат)", re.I)),
    ("local", re.compile(r"^(Општина|Град )", re.I)),
    ("pubco", re.compile(r"^(ЈП|Јавно претпријатие|АД |Акционерско друштво|ЈКП)", re.I)),
    ("pubinst", re.compile(r"^(ЈОУ|ЈЗУ|ЈУ |ООУ|СОУ|ОУ |Јавна установа|Универзитет|Факултет|"
                           r"Клиника|Општа болница|Здравствен|Национална установа|НУ )", re.I)),
]


def _form(start: int) -> dict:
    """Parametri koje šalje tabela na stranici (DataTables), najnoviji oglasi prvi."""
    d = {"draw": "1", "start": str(start), "length": str(PAGE), "search[value]": "",
         "search[regex]": "false", "order[0][column]": "5", "order[0][dir]": "desc",
         "Discriminator": json.dumps(SEARCH)}
    for i, c in enumerate(COLUMNS):
        d.update({f"columns[{i}][data]": c, f"columns[{i}][name]": "",
                  f"columns[{i}][searchable]": "true", f"columns[{i}][orderable]": "true",
                  f"columns[{i}][search][value]": "", f"columns[{i}][search][regex]": "false"})
    return d


def _label(code: str) -> str:
    return PROCEDURE.get(code) or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", code or "").strip()


def _buyer(name) -> str:
    name = base.clean(name).lstrip("„\"' ")
    return next((k for k, rx in BUYER_RX if rx.search(name)), "other")


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("mk", {})
    types = set(c.get("types") or ["Services"])
    max_pages = int(c.get("max_pages", 30))
    s = base.session()
    out: dict[str, dict] = {}
    total, seen = None, 0
    for page in range(max_pages):
        r = s.post(GRID, data=_form(page * PAGE), timeout=base.TIMEOUT)
        if r.status_code in (401, 403):
            raise base.SourceBlocked(f"portal je odbio pristup (HTTP {r.status_code})")
        r.raise_for_status()
        try:
            d = r.json()
            total, rows = int(d["recordsFiltered"]), d["data"]
        except (ValueError, KeyError, TypeError):
            raise base.SourceChanged("e-Nabavki MK: tabela oglasa je promijenila format.") from None
        for x in rows:
            seen += 1
            if x.get("GoodsWorksServices") not in types:
                continue
            num, iid, title = x.get("ProcessNumber"), x.get("Id"), x.get("Subject")
            if not num or not iid or not title:
                continue
            final = str(x.get("FinalDay") or "")
            out[num] = base.rec(
                META["key"], num, title=title, buyer=x.get("ContractingInstitutionName") or "",
                url=f"{WEB}PublicAccess/home.aspx#/dossie/{iid}/{x.get('ProcedureType') or ''}",
                pub=str(x.get("AnnouncementDate") or "")[:10] or None, due=final[:10] or None,
                due_time=final[11:16] if len(final) >= 16 and final[11:16] != "00:00" else None,
                countries=["MK"], ctype=KIND.get(x.get("GoodsWorksServices")),
                ntype=_label(x.get("EntityProcedureType")), btype=_buyer(x.get("ContractingInstitutionName")),
                ref=num)
        if seen >= total or not rows:
            break
        time.sleep(1.0)
    if total is None:
        raise base.SourceChanged("e-Nabavki MK: tabela oglasa nije vratila podatke.")
    today = base.today().isoformat()
    return [r for r in out.values() if not r.get("d") or r["d"] >= today]


if __name__ == "__main__":
    base.cli(collect, META)
