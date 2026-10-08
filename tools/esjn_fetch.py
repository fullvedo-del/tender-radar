"""Kancelarijski preuzimač makedonskih nabavki (pokreće se na računaru na OBIČNOJ vezi, ne na GitHubu).

e-nabavki.gov.mk kroz Cloudflare odbija servere u podatkovnim centrima (GitHub), ali pušta obične
mreže. Ova skripta zato radi na kancelarijskom računaru: pozove javni servis
`Services/Procurements.asmx/GetGridData` (lista „Actual calls for bids“, bez prijave) i upiše
sirovi rezultat u `data/esjn_raw.json`. Kolektor `collectors/sjeverna_makedonija.py` na GitHubu
poslije samo pročita taj fajl. Fajl se piše SAMO ako je preuzimanje uspjelo, da se dobri podaci ne
pregaze greškom.

Koristi samo standardnu biblioteku (bez instalacija). Jedan pošten User-Agent; ne zaobilazi se
nikakva zaštita. Pokretanje:  python tools/esjn_fetch.py data/esjn_raw.json
"""
from __future__ import annotations

import datetime as dt
import json
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

URL = "https://e-nabavki.gov.mk/Services/Procurements.asmx/GetGridData"
UA = "TenderRadar/1.0 (dnevni indeks javnih objava o nabavkama; python-urllib)"
FIELDS = ("Id", "EntityId", "Name", "ProcureItem", "TypeOfProcurements", "TypeOfProcedure",
          "TypeOfProcedureId", "DateOfPublicAnnouncement", "DateOfPublicOpening", "DecisionNumber")
PAGE = 500
socket.setdefaulttimeout(90)


def _page(skip: int) -> dict:
    pairs = [("draw", "1"), ("start", str(skip)), ("length", str(PAGE)),
             ("search[value]", ""), ("search[regex]", "false")]
    for i in range(12):
        pairs += [(f"columns[{i}][data]", str(i)), (f"columns[{i}][searchable]", "true"),
                  (f"columns[{i}][orderable]", "false"),
                  (f"columns[{i}][search][value]", ""), (f"columns[{i}][search][regex]", "false")]
    pairs += [("Discriminator", "{}")]  # prazna pretraga = sve objave
    data = urllib.parse.urlencode(pairs).encode()
    req = urllib.request.Request(URL, data=data, headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req) as r:
                body = r.read()
            j = json.loads(body.decode("utf-8", "replace"))
            if not isinstance(j, dict) or "data" not in j:
                raise ValueError("odgovor nema 'data'")
            return j
        except (urllib.error.URLError, ValueError, OSError) as e:
            last = e
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f"ESJN: neuspješno preuzimanje (skip={skip}): {type(last).__name__}: {last}")


def main() -> int:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "data/esjn_raw.json"
    first = _page(0)
    total = int(first.get("recordsTotal") or 0)
    rows = list(first.get("data") or [])
    skip = PAGE
    while skip < total and skip < 20000:
        time.sleep(0.5)
        rows += _page(skip).get("data") or []
        skip += PAGE
    if not rows:
        raise SystemExit("ESJN: servis je vratio 0 zapisa; fajl se ne mijenja")
    slim = [{k: r.get(k) for k in FIELDS} for r in rows if isinstance(r, dict)]
    payload = {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "e-nabavki.gov.mk Services/Procurements.asmx/GetGridData",
        "count": len(slim),
        "rows": slim,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"ESJN: upisano {len(slim)} zapisa u {out_path} (recordsTotal {total}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
