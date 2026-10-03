#!/usr/bin/env python3
"""Tender radar: pokreće kolektore i piše data/tenders.json i data/status.json.

    python collect.py                 # svi izvori
    python collect.py --only TED,WB   # samo navedeni; ostali zadržavaju zadnje podatke
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import os
import re
import sys
import time
import traceback
from collections import Counter

from collectors import base

# Redoslijed je ujedno prioritet kod duplikata: objavu zadržava izvor koji je prvi na listi.
MODULES = ["ejn", "ted", "eu_ft", "worldbank", "undp", "ebrd", "rcc", "expertise_france"]

KEEP_NO_DEADLINE_DAYS = 60   # objave bez roka ostaju ovoliko dana od objave

# Kursevi za filter po vrijednosti: koliko KM vrijedi jedinica valute. KM je vezan za euro
# (1 EUR = 1,95583 KM), ostalo se računa iz dnevne liste ECB-a. Ovo su približne vrijednosti
# za valute kojih nema na listi ECB-a i rezerva kad lista nije dostupna.
ECB = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
KM_PER_EUR = 1.95583
FX_FALLBACK = {"BAM": 1.0, "EUR": KM_PER_EUR, "USD": 1.75, "GBP": 2.30, "CHF": 2.10, "SEK": 0.175,
               "MKD": 0.0318, "RSD": 0.0167, "ALL": 0.0198, "XOF": 0.00298, "XAF": 0.00298}


def exchange_rates():
    """(kursevi u KM, datum liste ECB-a ili None ako su ostali približni kursevi)."""
    fx = dict(FX_FALLBACK)
    try:
        xml = base.fetch(base.session(), "GET", ECB, tries=2).text
        day = re.search(r"time='(\d{4}-\d{2}-\d{2})'", xml)
        rates = re.findall(r"currency='([A-Z]{3})' rate='([0-9.]+)'", xml)
        if not day or len(rates) < 10:
            return fx, None
        for cur, rate in rates:
            if float(rate) > 0:
                fx[cur] = round(KM_PER_EUR / float(rate), 6)
        return fx, day[1]
    except Exception:  # kursna lista nije presudna
        traceback.print_exc()
        return fx, None
SUSPICIOUS_EMPTY = 10        # 0 objava je sumnjivo ako ih je zadnji put bilo bar ovoliko


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json_lines(path, records):
    """JSON niz s jednim zapisom po redu (male dnevne razlike u git-u)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("[\n")
        f.write(",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":"))
                           for r in records))
        f.write("\n]\n")
    os.replace(tmp, path)


def alive(r, today, cutoff):
    if r.get("d"):
        return r["d"] >= today
    return r.get("p") is None or r["p"] >= cutoff


def check(items, key):
    if not isinstance(items, list):
        raise base.SourceChanged("kolektor nije vratio listu")
    for r in items:
        if not isinstance(r, dict) or r.get("src") != key or not r.get("id") \
                or not r.get("t") or not str(r.get("u", "")).startswith("http"):
            raise base.SourceChanged("kolektor je vratio neispravan zapis")


def dedup(recs):
    """Ista objava na više izvora prikazuje se jednom.

    Zadržava se zapis izvora koji je prvi po prioritetu; on u polju 'also' dobija izvor i link
    duplikata, a duplikat dobija 'dup' (ID zadržanog zapisa) i stranica ga ne prikazuje.
    Duplikati ostaju u fajlu da bi se sutra, ako njihov izvor zakaže, mogli ponovo upariti."""
    out, seen, by_title, by_ref = [], set(), {}, {}
    for r in recs:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        due = r.get("d")
        tkey = (base.norm(r["t"])[:80], due)
        rkey = (base.norm(r.get("ref", "")), due)
        use_t = bool(due) and len(tkey[0]) >= 25
        use_r = bool(due) and len(rkey[0]) >= 8
        first = (by_title.get(tkey) if use_t else None) or (by_ref.get(rkey) if use_r else None)
        if first is not None and first["src"] != r["src"]:
            also = first.setdefault("also", [])
            if all(a["src"] != r["src"] for a in also):
                also.append({"src": r["src"], "u": r["u"]})
            r["dup"] = first["id"]
        else:
            if use_t:
                by_title.setdefault(tkey, r)
            if use_r:
                by_ref.setdefault(rkey, r)
        out.append(r)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Tender radar: prikupljanje objava")
    ap.add_argument("--only", default="", help="ključevi izvora odvojeni zarezom, npr. TED,WB")
    ap.add_argument("--data", default="data", help="folder za izlazne fajlove")
    args = ap.parse_args()
    only = {k.strip().upper() for k in args.only.split(",") if k.strip()}

    cfg = load_json("config.json", {})
    os.makedirs(args.data, exist_ok=True)
    t_path = os.path.join(args.data, "tenders.json")
    s_path = os.path.join(args.data, "status.json")

    prev = load_json(t_path, [])
    prev_status = {s["key"]: s for s in load_json(s_path, {}).get("sources", [])}
    prev_by_src: dict[str, list] = {}
    for r in prev:
        r.pop("also", None)
        r.pop("dup", None)
        prev_by_src.setdefault(r["src"], []).append(r)
    prev_fs = {r["id"]: r.get("fs") for r in prev}
    # Rok koji je alat prvi put zabilježio, da se vidi kad ga naručilac pomjeri.
    first_due = {r["id"]: r.get("d0") or r.get("d") for r in prev}

    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now.date().isoformat()
    cutoff = (now.date() - dt.timedelta(days=KEEP_NO_DEADLINE_DAYS)).isoformat()

    recs, statuses, any_ok = [], [], False
    for name in MODULES:
        mod = importlib.import_module(f"collectors.{name}")
        meta = mod.META
        key = meta["key"]
        old = prev_status.get(key, {})
        st = {"key": key, "name": meta["name"], "home": meta["home"],
              "scope": meta.get("scope", "")}
        kept = prev_by_src.get(key, [])

        if only and key not in only:
            items = kept
            st.update(ok=bool(old.get("ok")), error=old.get("error"),
                      last_ok=old.get("last_ok"))
        else:
            t0 = time.time()
            try:
                items = mod.collect(cfg)
                check(items, key)
                if not items and len(kept) >= SUSPICIOUS_EMPTY:
                    raise base.SourceChanged(
                        f"izvor je vratio 0 objava (zadnji put {len(kept)}); "
                        "vjerovatno je promijenio strukturu")
                for r in items:
                    was = first_due.get(r["id"])
                    if was and r.get("d") and was != r["d"]:
                        r["d0"] = was
                st.update(ok=True, error=None, last_ok=stamp)
                any_ok = True
            except Exception as e:  # jedan izvor ne smije srušiti ostale
                traceback.print_exc()
                items = kept
                st.update(ok=False, error=f"{e}"[:300] or type(e).__name__,
                          last_ok=old.get("last_ok"))
            st["sec"] = round(time.time() - t0, 1)

        new_source = key not in prev_status
        for r in items:
            r["fs"] = prev_fs.get(r["id"]) or ((r.get("p") or today) if new_source else today)
        recs.extend(items)
        statuses.append(st)

    recs = dedup([r for r in recs if alive(r, today, cutoff)])
    recs.sort(key=lambda r: (r.get("d") or "9999", r.get("p") or ""))
    collected = Counter(r["src"] for r in recs)
    merged = Counter(r["src"] for r in recs if "dup" in r)
    total = len(recs) - sum(merged.values())
    for st in statuses:
        st["count"] = collected[st["key"]]   # otvorene objave s izvora
        st["merged"] = merged[st["key"]]     # od toga prikazane pod drugim izvorom

    # Izvori koji su namjerno izostavljeni (npr. zabranjuju automatsko preuzimanje).
    for ex in cfg.get("excluded", []):
        statuses.append({"key": ex["key"], "name": ex["name"], "home": ex["home"],
                         "scope": "", "ok": False, "off": True, "count": 0,
                         "error": ex.get("reason", ""), "last_ok": None})

    fx, fx_date = exchange_rates()
    write_json_lines(t_path, recs)
    with open(s_path, "w", encoding="utf-8") as f:
        json.dump({"generated": stamp, "total": total, "fx": fx, "fx_date": fx_date,
                   "sources": statuses}, f, ensure_ascii=False, indent=1)

    print(f"\nUkupno {total} objava ({stamp})")
    for st in statuses:
        flag = "isključen" if st.get("off") else ("OK" if st["ok"] else "GREŠKA")
        print(f"  {st['key']:5s} {flag:9s} {st['count']:6d}  {st.get('error') or ''}")
    if not only and not any_ok:
        print("Nijedan izvor nije uspio.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
