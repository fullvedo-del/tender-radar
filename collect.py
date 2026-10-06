#!/usr/bin/env python3
"""Tender radar: pokreće kolektore i piše data/tenders.json, data/status.json i,
za interne izvore, šifrirani data/private.json. Uz to: AI ocjena, prijevod i sažetak (ai_score.py),
dobitnici ugovora u data/awards.json (awards.py), slične reference u šifriranom data/refmatch.json
(refmatch.py, iz reference.enc.json) i preporučeni eksperti u šifriranom data/expertmatch.json
(experts.py, iz roster-a experts.enc.json).

    python collect.py                 # svi izvori
    python collect.py --only TED,WB   # samo navedeni; ostali zadržavaju zadnje podatke

Interni izvori (META["private"] u kolektoru ili lista private_sources u config.json) su oni
čiji uslovi dozvoljavaju samo internu upotrebu. Njihove objave se ne pišu u javni fajl, nego
se šifriraju šifrom iz varijable okruženja TR_PASSPHRASE (na GitHubu: secret istog imena).
Bez te šifre interni izvori se uopće ne preuzimaju.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import importlib
import json
import os
import re
import sys
import time
import traceback
import unicodedata
from collections import Counter

import ai_score
import awards
import experts
import refmatch
from collectors import base

# Redoslijed je ujedno prioritet kod duplikata: objavu zadržava izvor koji je prvi na listi.
# Interni izvori uvijek dolaze poslije javnih, pa istu objavu zadržava javni izvor.
# developmentaid.py i enabavki_mk.py ostaju u repozitoriju, ali se ne pokreću (vidi config.json, excluded).
MODULES = ["ejn", "ted", "eu_ft", "worldbank", "undp", "ebrd", "rcc", "expertise_france",
           "czechaid", "eu_grants", "fzofbih", "ekofondrs", "fmrpo", "mrezamira",
           "giz", "osce"]

KEEP_NO_DEADLINE_DAYS = 60   # objave bez roka ostaju ovoliko dana od objave
RUN_MINUTES = 25             # koliko smije trajati cijelo prikupljanje (posao na GitHubu ima 30 minuta)
REFS_FILE = "reference.enc.json"  # šifrirana lista referenci u glavnom folderu repozitorija
EXPERTS_FILE = "experts.enc.json"  # šifrirani roster eksperata (piše ga stranica, tab Eksperti)
SUSPICIOUS_EMPTY = 10        # 0 objava je sumnjivo ako ih je zadnji put bilo bar ovoliko
KDF_ITERATIONS = 250_000     # PBKDF2-SHA256; isti postupak radi i stranica u pregledniku

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


# --------------------------------------------------------------------------- šifriranje

def _key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    text = unicodedata.normalize("NFC", passphrase.strip()).encode("utf-8")
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=iterations).derive(text)


def encrypt_records(records: list, passphrase: str, stamp: str) -> dict:
    """AES-256-GCM; ključ iz šifre preko PBKDF2. Novi salt i IV pri svakom pisanju."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, iv = os.urandom(16), os.urandom(12)
    plain = json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sealed = AESGCM(_key(passphrase, salt, KDF_ITERATIONS)).encrypt(iv, plain, None)

    def b64(b: bytes) -> str:
        return base64.b64encode(b).decode("ascii")
    return {"v": 1, "kdf": "PBKDF2-SHA256", "iter": KDF_ITERATIONS, "cipher": "AES-256-GCM",
            "salt": b64(salt), "iv": b64(iv), "ct": b64(sealed), "generated": stamp}


def decrypt_json(blob, passphrase: str):
    """Sadržaj šifriranog fajla, ili None ako šifra ne odgovara ili fajl nije ispravan."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        d = base64.b64decode
        key = _key(passphrase, d(blob["salt"]), int(blob["iter"]))
        return json.loads(AESGCM(key).decrypt(d(blob["iv"]), d(blob["ct"]), None))
    except Exception:
        return None


def decrypt_records(blob, passphrase: str):
    """Lista zapisa, ili None ako šifra ne odgovara ili fajl nije ispravan."""
    out = decrypt_json(blob, passphrase)
    return out if isinstance(out, list) else None


# --------------------------------------------------------------------------- pomoćno

def capped(cfg: dict, keys: tuple, left: float) -> dict:
    """Kopija postavki za AI u kojoj nijedan vremenski okvir nije duži od preostalog vremena."""
    conf = {**ai_score.DEFAULTS, **(cfg.get("ai") or {})}
    for k in keys:
        conf[k] = max(0.0, min(float(conf[k]), left))
    return {**cfg, "ai": conf}


def find_refs(passphrase: str):
    """Lista referenci iz šifriranog fajla, ili (None, poruka) ako je nema ili se ne može otvoriti."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), REFS_FILE)
    if not os.path.exists(path):
        return None, f"lista referenci nije postavljena na GitHub (fajl {REFS_FILE})."
    if not passphrase:
        return None, "lista referenci se ne može otvoriti: nije postavljena šifra TR_PASSPHRASE."
    refs = decrypt_records(load_json(path, None), passphrase)
    if refs is None:
        return None, (f"fajl {REFS_FILE} se ne može otvoriti ovom šifrom; šifriraj ga ponovo na stranici "
                      "(Interni izvori) i zamijeni na GitHubu.")
    refs = [r for r in refs if isinstance(r, dict) and str(r.get("t") or "").strip()]
    if not refs:
        return None, f"fajl {REFS_FILE} ne sadrži nijednu referencu."
    return refs, None


def find_roster(passphrase: str):
    """Roster eksperata iz šifriranog fajla, ili (None, poruka)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), EXPERTS_FILE)
    if not os.path.exists(path):
        return None, "roster eksperata još nije spremljen (tab Eksperti na stranici)."
    if not passphrase:
        return None, "roster eksperata se ne može otvoriti: nije postavljena šifra TR_PASSPHRASE."
    roster = decrypt_records(load_json(path, None), passphrase)
    if roster is None:
        return None, f"fajl {EXPERTS_FILE} se ne može otvoriti ovom šifrom."
    roster = [x for x in roster if isinstance(x, dict) and x.get("id") is not None]
    return (roster, None) if roster else (None, "roster eksperata je prazan.")


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
    if r.get("keep"):  # najava: izvor kaže do kad je drži u listi
        return r["keep"] >= today
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
        # Broj projekta ispred naziva ("10030774-Naziv") neki izvori pišu, a neki ne.
        tkey = (base.norm(re.sub(r"^\s*\d{6,}\s*[-–:]?\s*", "", r["t"]))[:80], due)
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


# --------------------------------------------------------------------------- glavni tok

def main() -> int:
    t_start = time.time()
    ap = argparse.ArgumentParser(description="Tender radar: prikupljanje objava")
    ap.add_argument("--only", default="", help="ključevi izvora odvojeni zarezom, npr. TED,WB")
    ap.add_argument("--data", default="data", help="folder za izlazne fajlove")
    args = ap.parse_args()
    only = {k.strip().upper() for k in args.only.split(",") if k.strip()}

    cfg = load_json("config.json", {})
    os.makedirs(args.data, exist_ok=True)
    t_path = os.path.join(args.data, "tenders.json")
    s_path = os.path.join(args.data, "status.json")
    p_path = os.path.join(args.data, "private.json")
    a_path = os.path.join(args.data, "awards.json")
    m_path = os.path.join(args.data, "refmatch.json")
    x_path = os.path.join(args.data, "expertmatch.json")
    run_minutes = float(cfg.get("run_minutes") or RUN_MINUTES)

    def left() -> float:
        """Preostale minute, uz dvije minute rezerve za pisanje fajlova."""
        return run_minutes - (time.time() - t_start) / 60 - 2

    mods = [importlib.import_module(f"collectors.{name}") for name in MODULES]
    private = {m.META["key"] for m in mods if m.META.get("private")} \
        | {str(k).upper() for k in cfg.get("private_sources", [])}
    mods.sort(key=lambda m: m.META["key"] in private)  # javni prvi, redoslijed inače isti

    passphrase = (os.environ.get("TR_PASSPHRASE") or "").strip()
    locked_reason = None
    if private and not passphrase:
        locked_reason = ("Interni izvor se ne preuzima: na GitHubu nije postavljena šifra "
                         "(Settings, Secrets and variables, Actions: secret TR_PASSPHRASE).")
    elif private:
        try:
            importlib.import_module("cryptography")
        except ImportError:
            locked_reason = "Interni izvor se ne preuzima: nije instalirana biblioteka cryptography."

    prev = load_json(t_path, [])
    if private and not locked_reason:
        old_private = decrypt_records(load_json(p_path, None), passphrase)
        if old_private is None and os.path.exists(p_path):
            print("Raniji interni podaci se ne mogu otvoriti ovom šifrom; počinjem ispočetka.")
        prev = prev + (old_private or [])
    prev_status = {s["key"]: s for s in load_json(s_path, {}).get("sources", [])}
    prev_by_src: dict[str, list] = {}
    for r in prev:
        r.pop("also", None)
        r.pop("dup", None)
        prev_by_src.setdefault(r["src"], []).append(r)
    prev_fs = {r["id"]: r.get("fs") for r in prev}
    # AI ocjene se prenose, da se svaka objava ocjenjuje samo jednom. Kad se promijeni okvir za ocjenu
    # (ai_okvir.md), stare ocjene ostaju dok AI postepeno ne ocijeni objave po novom okviru (polje ak).
    _, okvir_id = ai_score.load_okvir(cfg)
    old_okvir = (load_json(s_path, {}).get("ai") or {}).get("okvir")
    ai_key = bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip())
    if ai_key and okvir_id and old_okvir != okvir_id:
        print("Okvir za AI ocjenu je promijenjen: objave se postepeno ocjenjuju ponovo.")
    prev_ai = {r["id"]: r for r in prev if "ai" in r}
    # AI prijevod naslova i AI sažetak opisa prenose se dok god je naslov isti.
    prev_en = {r["id"]: r for r in prev if "en" in r}
    prev_sm = {r["id"]: r for r in prev if r.get("sm")}
    # Rok koji je alat prvi put zabilježio, da se vidi kad ga naručilac pomjeri.
    first_due = {r["id"]: r.get("d0") or r.get("d") for r in prev}

    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now.date().isoformat()
    cutoff = (now.date() - dt.timedelta(days=KEEP_NO_DEADLINE_DAYS)).isoformat()
    # Objava koju alat prvi put vidi, a objavljena je prije više od sedmice (npr. novi izvor ili
    # proširen filter), ne računa se kao nova: kao "prvi put viđena" uzima se datum objave.
    stale = (now.date() - dt.timedelta(days=7)).isoformat()

    recs, statuses, any_ok = [], [], False
    for mod in mods:
        meta = mod.META
        key = meta["key"]
        old = prev_status.get(key, {})
        st = {"key": key, "name": meta["name"], "home": meta["home"],
              "scope": meta.get("scope", "")}
        if key in private:
            st["private"] = True
            if locked_reason:
                st.update(ok=False, off=True, error=locked_reason, last_ok=None)
                statuses.append(st)
                continue
        need = meta.get("env")  # izvor kojem treba poseban ključ (GitHub secret)
        if need and not (os.environ.get(need) or "").strip():
            st.update(ok=False, off=True, last_ok=None,
                      error=f"Izvor se ne preuzima: na GitHubu nije postavljen secret {need}.")
            statuses.append(st)
            continue
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

        new_source = not old.get("last_ok") or old.get("off")  # izvor koji još nije uspio
        for r in items:
            pub = r.get("p")
            r["fs"] = prev_fs.get(r["id"]) or (pub if pub and (new_source or pub < stale) else today)
            old_ai = prev_ai.get(r["id"])
            if "ai" not in r and old_ai and old_ai.get("ty") == r.get("ty"):  # tender ili javni poziv
                for f in ("ai", "air", "aiw", "ak"):
                    if f in old_ai:
                        r[f] = old_ai[f]
            old_en = prev_en.get(r["id"])
            if "en" not in r and old_en and old_en.get("t") == r["t"]:
                r["en"] = old_en["en"]
                if old_en.get("lg"):
                    r["lg"] = old_en["lg"]
            old_sm = prev_sm.get(r["id"])
            if "sm" not in r and old_sm and old_sm.get("t") == r["t"]:
                r["sm"] = old_sm["sm"]
        recs.extend(items)
        statuses.append(st)

    recs = dedup([r for r in recs if alive(r, today, cutoff)])
    # AI koraci i dobitnici, svaki u svom vremenskom okviru, ali ne duže od vremena koje je ostalo za ovo
    # osvježavanje. Redoslijed je prioritet: prijevod (treba ga AI ocjena), ocjena, dobitnici, sažeci.
    tr_info = ai_score.translate(recs, capped(cfg, ("translate_minutes",), left()), private)
    ai_info = ai_score.score(recs, capped(cfg, ("minutes",), left()), private)
    ai_info["tr"] = tr_info
    ai_info["okvir"] = okvir_id if ai_key else old_okvir  # bez ključa ostaje stari, da se kasnije ocijeni ponovo

    # Dobitnici ugovora (data/awards.json). U probnom pokretanju s --only samo ako je naveden AWD.
    aw_info = None
    if not only or "AWD" in only:
        try:
            aw_info = awards.run(cfg, a_path, left())
        except Exception as e:  # dobitnici ne smiju srušiti osvježavanje objava
            traceback.print_exc()
            aw_info = dict((load_json(s_path, {}) or {}).get("awards") or {"on": True}, error=f"{e}"[:300])
    elif os.path.exists(a_path):
        aw_info = (load_json(s_path, {}) or {}).get("awards")

    ai_info["sm"] = ai_score.summarize(recs, capped(cfg, ("summary_minutes",), left()), private)

    # Preporučeni eksperti za tendere s AI ocjenom 2 i 3: roster i rezultat su šifrirani.
    roster, ex_error = find_roster(passphrase)
    ex_info = {"on": False, "error": ex_error}
    if roster:
        prev_x = decrypt_json(load_json(x_path, None), passphrase) if os.path.exists(x_path) else None
        ex_cfg = {**cfg, "experts": {**experts.DEFAULTS, **(cfg.get("experts") or {})}}
        ex_cfg["experts"]["minutes"] = max(0.0, min(float(ex_cfg["experts"]["minutes"]), left()))
        found_x, ex_info = experts.recommend(recs, roster, ex_cfg, private, prev_x)
        with open(x_path, "w", encoding="utf-8") as f:
            json.dump(encrypt_records(found_x, passphrase, stamp), f)
    elif os.path.exists(x_path):
        os.remove(x_path)  # bez roster-a nema ni preporuka

    # Slične reference: lista je šifrirana, a rezultat se piše šifriran (vidi se tek nakon otključavanja).
    refs, ref_error = find_refs(passphrase)
    ref_info = {"on": False, "error": ref_error}
    if refs:
        found = refmatch.match(recs, refs)
        with open(m_path, "w", encoding="utf-8") as f:
            json.dump(encrypt_records(found, passphrase, stamp), f)
        ref_info = {"on": True, "n": len(refs), "matched": len(found["m"]), "error": None}
    elif os.path.exists(m_path):
        os.remove(m_path)  # stari rezultat ne smije ostati kad liste više nema
    recs.sort(key=lambda r: (r.get("d") or "9999", r.get("p") or ""))
    collected = Counter(r["src"] for r in recs)
    merged = Counter(r["src"] for r in recs if "dup" in r)
    for st in statuses:
        st["count"] = collected[st["key"]]   # otvorene objave s izvora
        st["merged"] = merged[st["key"]]     # od toga prikazane pod drugim izvorom

    # Javni i interni dio. U javnom ne smije ostati ni trag internih objava.
    public = [r for r in recs if r["src"] not in private]
    internal = [r for r in recs if r["src"] in private]
    for r in public:
        if "also" in r:
            r["also"] = [a for a in r["also"] if a["src"] not in private]
            if not r["also"]:
                del r["also"]
    total = sum(1 for r in public if "dup" not in r)
    total_private = sum(1 for r in internal if "dup" not in r)

    # Izvori koji su namjerno izostavljeni (npr. zabranjuju automatsko preuzimanje).
    for ex in cfg.get("excluded", []):
        statuses.append({"key": ex["key"], "name": ex["name"], "home": ex["home"],
                         "scope": "", "ok": False, "off": True, "count": 0,
                         "error": ex.get("reason", ""), "last_ok": None})

    fx, fx_date = exchange_rates()
    # Pomoćna polja (npr. _desc, opis za AI sažetak) se ne pišu u fajlove.
    for r in recs:
        for k in [k for k in r if k.startswith("_")]:
            del r[k]
    write_json_lines(t_path, public)
    if private and not locked_reason:
        with open(p_path, "w", encoding="utf-8") as f:
            json.dump(encrypt_records(internal, passphrase, stamp), f)
    with open(s_path, "w", encoding="utf-8") as f:
        json.dump({"generated": stamp, "total": total, "total_private": total_private,
                   "fx": fx, "fx_date": fx_date, "ai": ai_info, "awards": aw_info, "refs": ref_info, "experts": ex_info,
                   "sources": statuses}, f, ensure_ascii=False, indent=1)

    print(f"\nUkupno {total} javnih i {total_private} internih objava ({stamp})")
    print(f"AI ocjena: {ai_info['new']} novih, ukupno {ai_info['scored']}, čeka {ai_info['pending']}"
          + (f", po novom okviru čeka {ai_info['stale']}" if ai_info.get("stale") else "")
          + (f" ({ai_info['error']})" if ai_info["error"] else ""))
    print(f"AI sažetak: {ai_info['sm'].get('new', 0)} novih, ukupno {ai_info['sm'].get('done', 0)}"
          + (f" ({ai_info['sm']['error']})" if ai_info["sm"].get("error") else ""))
    if aw_info:
        print("Dobitnici:", json.dumps(aw_info, ensure_ascii=False)[:300])
    print("Slične reference:", f"{ref_info['matched']} objava" if ref_info["on"] else ref_info["error"])
    print("Eksperti:", f"{ex_info.get('n', 0)} u rosteru, preporuke za {ex_info.get('matched', 0)} tendera, "
          f"{ex_info.get('new', 0)} novih" + (f" ({ex_info['error']})" if ex_info.get("error") else "")
          if roster else ex_info["error"])
    print(f"Trajanje: {(time.time() - t_start) / 60:.1f} min")
    for st in statuses:
        flag = "isključen" if st.get("off") else ("OK" if st["ok"] else "GREŠKA")
        note = "interni" if st.get("private") and not st.get("off") else (st.get("error") or "")
        print(f"  {st['key']:5s} {flag:9s} {st['count']:6d}  {note}")
    if not only and not any_ok:
        print("Nijedan izvor nije uspio.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
