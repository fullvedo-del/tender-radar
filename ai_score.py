"""AI ocjena relevantnosti objava za profil firme (Claude API).

Pokreće je collect.py pri svakom osvježavanju. Ključ se čita iz varijable okruženja
ANTHROPIC_API_KEY (na GitHubu: secret istog imena). Bez ključa korak se preskače.

Ocjenjuju se samo objave koje još nemaju ocjenu, najnovije prve; ocjene se prenose iz dana u dan.
Polja u zapisu: ai (3 jako relevantno, 2 moguće, 1 slabo, 0 nije za firmu) i air (kratko
obrazloženje na bosanskom). AI ocjenjuje po okviru iz fajla ai_okvir.md (opis CETEOR-a i REIC-a,
pravila za ocjene, primjeri); izmjena okvira pokreće ponovno ocjenjivanje svih objava (collect.py).
Model i ograničenja su u config.json, dio "ai".

translate() daje kratak engleski prijevod naslova koji nisu na bosanskom, hrvatskom, srpskom,
crnogorskom ili engleskom: polje en (prijevod; prazno ako prijevod ne treba) i lg (jezik originala).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time

import requests

API = "https://api.anthropic.com/v1/messages"
DEFAULTS = {
    "model": "claude-haiku-4-5-20251001",
    "batch": 40,             # objava po jednom upitu
    "max_per_run": 2000,     # najviše novih ocjena po osvježavanju
    "minutes": 12,           # vremenski okvir za ocjenjivanje u jednom osvježavanju
    "include_private": False,
    "okvir": "ai_okvir.md",  # okvir za ocjenu; bez njega se koriste profile i profile_reic
    "profile": "",
    "profile_reic": "",
    "translate": True,       # prijevod stranih naslova na engleski
    "translate_batch": 80,
    "translate_max": 3000,   # najviše naslova po osvježavanju
    "translate_minutes": 6,
}
PROMPT_VERSION = "3"  # promjena načina ocjenjivanja u kodu; kao i izmjena okvira, pokreće ponovno ocjenjivanje
OUT_TENDER = """Za svaku objavu daj ocjenu s od 0 do 3 isključivo po okviru i kratko obrazloženje na bosanskom,
najviše 12 riječi (vrsta posla i razlog ocjene).
Odgovori isključivo JSON listom, bez ikakvog drugog teksta, s jednim elementom za svaku objavu.
U obrazloženju ne koristi navodnike.
[{"i": 1, "s": 2, "r": "obrazloženje"}]"""
OUT_CALL = """Za svaki javni poziv procijeni smije li CETEOR, REIC ili obje aplicirati, kao nosilac ili partner
(po vrsti organizacije i državi; BiH je zemlja kandidat za članstvo u EU), i koliko poziv odgovara
njihovom radu po okviru, posebno po dijelu o javnim pozivima. Ocjena s od 0 do 3 vrijedi za onu
organizaciju kojoj poziv bolje odgovara.
w = "C" ako je za CETEOR, "R" ako je za REIC, "CR" ako je za obje, "" ako ni za jednu.
Odgovori isključivo JSON listom, bez ikakvog drugog teksta, s jednim elementom za svaki poziv.
U obrazloženju (najviše 12 riječi, na bosanskom) ne koristi navodnike; ako je poznato, navedi ko smije aplicirati.
[{"i": 1, "s": 2, "w": "CR", "r": "obrazloženje"}]"""


def load_okvir(cfg: dict) -> tuple[str, str]:
    """Tekst okvira za ocjenu i kratki ID verzije (mijenja se s izmjenom teksta okvira)."""
    conf = {**DEFAULTS, **(cfg.get("ai") or {})}
    text = ""
    name = str(conf.get("okvir") or "").strip()
    if name:
        path = name if os.path.isabs(name) else os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()  # komentari su za ljude, ne za AI
    if not text:  # stari način: opisi u config.json
        parts = [("CETEOR: " + str(conf.get("profile") or "").strip()) if str(conf.get("profile") or "").strip() else "",
                 ("REIC: " + str(conf.get("profile_reic") or "").strip()) if str(conf.get("profile_reic") or "").strip() else ""]
        text = "\n\n".join(p for p in parts if p)
    oid = hashlib.sha1(f"{PROMPT_VERSION}\n{text}".encode("utf-8")).hexdigest()[:10] if text else ""
    return text, oid


def _system(okvir: str, calls: bool) -> str:
    who = ("Ti si analitičar javnih poziva (grantova) za CETEOR, firmu iz BiH, i REIC, nevladinu organizaciju iz BiH."
           if calls else "Ti si analitičar tendera za CETEOR, konsultantsku i inženjersku firmu iz BiH.")
    return f"{who} Ocjenjuj po okviru ispod.\n\n<okvir>\n{okvir}\n</okvir>\n\n" + (OUT_CALL if calls else OUT_TENDER)


KINDS = {"S": "usluge", "G": "robe", "W": "radovi"}
TRANSLATE = """You get numbered titles of public tenders and calls for proposals.
For every title that is NOT written in English, Bosnian, Croatian, Serbian or Montenegrin
(Latin or Cyrillic script), give a short, faithful English translation of at most 25 words and the
ISO 639-1 code of the title's language. Skip titles that are already in those languages.
Reply only with a JSON list and nothing else, for example:
[{"i": 2, "l": "mk", "e": "Maintenance of lifts in the ministry building"}]
Return [] when no title needs a translation. Do not use double quotes inside translations."""


class Fatal(Exception):
    """Greška zbog koje nema smisla nastavljati (npr. pogrešan ključ ili nema kredita)."""


def _post(key: str, body: dict):
    return requests.post(API, json=body, timeout=120, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})


def _call(key: str, body: dict, tries: int = 4) -> str:
    for t in range(tries):
        try:
            res = _post(key, body)
        except requests.RequestException:
            if t == tries - 1:
                raise
            time.sleep(5 * (t + 1))
            continue
        if res.status_code == 200:
            data = res.json()
            return "".join(c.get("text", "") for c in data.get("content", []) if c.get("type") == "text")
        try:
            msg = res.json().get("error", {}).get("message", "")
        except ValueError:
            msg = ""
        if res.status_code in (401, 403):
            raise Fatal(f"ključ ANTHROPIC_API_KEY nije prihvaćen (HTTP {res.status_code})")
        if res.status_code == 400:
            raise Fatal(f"AI servis je odbio zahtjev: {msg}"[:300])
        if res.status_code in (429, 500, 502, 503, 529) and t < tries - 1:
            time.sleep(min(60.0, float(res.headers.get("retry-after") or 10 * (t + 1))))
            continue
        raise RuntimeError(f"AI servis: HTTP {res.status_code} {msg}"[:300])
    raise RuntimeError("AI servis ne odgovara")


def _line(i: int, r: dict) -> str:
    value = ""
    if r.get("v"):
        cur = r.get("cur") or ""
        km = r["v"] if cur == "BAM" else r["v"] * 1.95583 if cur == "EUR" else None
        value = f"vrijednost {r['v']:,.0f} {cur}".replace(",", ".") + (f" (oko {km:,.0f} KM)".replace(",", ".") if km and cur != "BAM" else "")
    parts = [r["t"], f"EN: {r['en']}" if r.get("en") else "", r.get("b") or "", ", ".join(r.get("c") or []),
             KINDS.get(r.get("k"), ""), r.get("n") or "", f"CPV {r['cpv'][0]}" if r.get("cpv") else "", value, r["src"]]
    return f"{i}. " + " | ".join(p for p in parts if p)


# Rezervno čitanje kad AI vrati neispravan JSON (npr. navodnike unutar obrazloženja).
ITEM_RX = re.compile(r'"i"\s*:\s*(\d+)\s*,\s*"s"\s*:\s*(\d)\s*(?:,\s*"w"\s*:\s*"([CR]*)"\s*)?'
                     r'(?:,\s*"r"\s*:\s*"(.*?)"\s*)?\}', re.S)


def _parse(text: str, n: int) -> dict:
    items = []
    m = re.search(r"\[.*\]", text, re.S)
    if m:
        try:
            items = [(x.get("i"), x.get("s"), x.get("w"), x.get("r"))
                     for x in json.loads(m.group(0)) if isinstance(x, dict)]
        except ValueError:
            items = []
    if not items:
        items = ITEM_RX.findall(text)
    if not items:
        raise ValueError("AI nije vratio ocjene u očekivanom obliku")
    out = {}
    for i, sc, w, r in items:
        try:
            i, sc = int(i), int(sc)
        except (TypeError, ValueError):
            continue
        if 1 <= i <= n and 0 <= sc <= 3:
            w = "".join(x for x in "CR" if x in str(w or "").upper())
            out[i] = (sc, w, re.sub(r"\s+", " ", str(r or "")).replace('\\"', '"').strip()[:160])
    return out


TR_RX = re.compile(r'"i"\s*:\s*(\d+)\s*,\s*"l"\s*:\s*"([A-Za-z-]*)"\s*,\s*"e"\s*:\s*"(.*?)"\s*\}', re.S)


def _parse_tr(text: str, n: int) -> dict:
    """Odgovor na upit za prijevod: {broj: (prijevod, jezik)}. Prazna lista je ispravan odgovor."""
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise ValueError("AI nije vratio prijevode u očekivanom obliku")
    try:
        items = [(x.get("i"), x.get("l"), x.get("e")) for x in json.loads(m.group(0)) if isinstance(x, dict)]
    except ValueError:
        items = TR_RX.findall(text)
        if not items and m.group(0).strip("[] \n"):
            raise ValueError("AI nije vratio prijevode u očekivanom obliku") from None
    out = {}
    for i, lang, en in items:
        try:
            i = int(i)
        except (TypeError, ValueError):
            continue
        en = re.sub(r"\s+", " ", str(en or "")).replace('\\"', '"').strip()[:300]
        lang = str(lang or "").lower()
        if 1 <= i <= n and en:
            out[i] = (en, lang if re.fullmatch(r"[a-z]{2,3}", lang) else "")
    return out


HOME_LANGS = {"en", "bs", "hr", "sr", "sh", "cnr", "me"}


def _plain(text: str) -> str:
    return re.sub(r"[\W_]+", " ", str(text or "").lower()).strip()


def translate(recs: list, cfg: dict, private: set) -> dict:
    """Dodaje polja en i lg zapisima koji ih nemaju. Vraća stanje za status.json."""
    conf = {**DEFAULTS, **(cfg.get("ai") or {})}
    key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    pool = [r for r in recs if not r.get("dup")
            and (conf["include_private"] or r["src"] not in private)]
    info = {"on": bool(key and conf["translate"]), "new": 0, "error": None}
    if info["on"]:
        todo = [r for r in pool if "en" not in r]
        todo.sort(key=lambda r: r.get("fs") or r.get("p") or "", reverse=True)
        work = todo[:int(conf["translate_max"])]
        stop = time.time() + float(conf["translate_minutes"]) * 60
        size = max(1, int(conf["translate_batch"]))
        for k in range(0, len(work), size):
            if time.time() > stop:
                info["error"] = "isteklo vrijeme za prijevode; ostatak se prevodi pri sljedećem osvježavanju"
                break
            chunk = work[k:k + size]
            body = {"model": conf["model"], "max_tokens": 45 * len(chunk) + 200, "system": TRANSLATE,
                    "messages": [{"role": "user", "content": "\n".join(
                        f"{i}. {r['t'][:300]}" for i, r in enumerate(chunk, 1))}]}
            try:
                got = _parse_tr(_call(key, body), len(chunk))
            except Fatal as e:
                info["error"] = str(e)
                break
            except Exception as e:  # jedan neuspjeli upit ne zaustavlja ostale
                info["error"] = f"{e}"[:300] or type(e).__name__
                continue
            for i, r in enumerate(chunk, 1):
                en, lang = got.get(i, ("", ""))
                if lang in HOME_LANGS or _plain(en) == _plain(r["t"]):
                    en, lang = "", ""  # naslov je već na domaćem jeziku ili engleskom
                r["en"] = en
                if lang:
                    r["lg"] = lang
                info["new"] += 1 if en else 0
    info["done"] = sum(1 for r in pool if r.get("en"))
    info["pending"] = sum(1 for r in pool if "en" not in r) if info["on"] else 0
    return info


def _run(key: str, conf: dict, system: str, work: list, info: dict, stop: float, calls: bool) -> bool:
    """Ocjenjuje listu u grupama. Vraća False ako treba stati (pogrešan ključ, isteklo vrijeme)."""
    size = max(1, int(conf["batch"]))
    for k in range(0, len(work), size):
        if time.time() > stop:
            info["error"] = "isteklo vrijeme za ocjenjivanje; ostatak se ocjenjuje pri sljedećem osvježavanju"
            return False
        chunk = work[k:k + size]
        body = {"model": conf["model"], "max_tokens": 70 * len(chunk) + 200,
                "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                "messages": [{"role": "user", "content": "\n".join(
                    _line(i, r) for i, r in enumerate(chunk, 1))}]}
        try:
            got = _parse(_call(key, body), len(chunk))
        except Fatal as e:
            info["error"] = str(e)
            return False
        except Exception as e:  # jedan neuspjeli upit ne zaustavlja ostale
            info["error"] = f"{e}"[:300] or type(e).__name__
            continue
        for i, r in enumerate(chunk, 1):
            if i in got:
                r["ai"], w, r["air"] = got[i]
                if calls:
                    r["aiw"] = w
                info["new"] += 1
    return True


def score(recs: list, cfg: dict, private: set) -> dict:
    """Dodaje polja ai i air zapisima koji ih nemaju. Vraća stanje za status.json."""
    conf = {**DEFAULTS, **(cfg.get("ai") or {})}
    key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    pool = [r for r in recs if not r.get("dup")
            and (conf["include_private"] or r["src"] not in private)]
    todo = [r for r in pool if "ai" not in r]
    okvir, oid = load_okvir(cfg)
    info = {"model": conf["model"], "on": bool(key), "new": 0, "error": None, "okvir": oid}
    if not key:
        info["error"] = ("AI ocjena je isključena: na GitHubu nije postavljen secret "
                         "ANTHROPIC_API_KEY.")
    elif not okvir:
        info["error"] = "AI ocjena je isključena: nema okvira za ocjenu (fajl ai_okvir.md)."
    else:
        todo.sort(key=lambda r: r.get("fs") or r.get("p") or "", reverse=True)
        work = todo[:int(conf["max_per_run"])]
        stop = time.time() + float(conf["minutes"]) * 60
        tenders = [r for r in work if r.get("ty") != "P"]
        calls = [r for r in work if r.get("ty") == "P"]
        # Prvo javni pozivi (manje ih je), zatim tenderi; staje se na pogrešnom ključu ili isteku vremena.
        if _run(key, conf, _system(okvir, True), calls, info, stop, True):
            _run(key, conf, _system(okvir, False), tenders, info, stop, False)
    info["scored"] = sum(1 for r in pool if "ai" in r)
    info["pending"] = sum(1 for r in pool if "ai" not in r)
    return info
