"""AI ocjena relevantnosti objava za profil firme (Claude API).

Pokreće je collect.py pri svakom osvježavanju. Ključ se čita iz varijable okruženja
ANTHROPIC_API_KEY (na GitHubu: secret istog imena). Bez ključa korak se preskače.

Ocjenjuju se samo objave koje još nemaju ocjenu, najnovije prve; ocjene se prenose iz dana u dan.
Polja u zapisu: ai (3 jako relevantno, 2 moguće, 1 slabo, 0 nije za firmu) i air (kratko
obrazloženje na bosanskom). Profil firme i model su u config.json, dio "ai".
"""
from __future__ import annotations

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
    "profile": "",
    "profile_reic": "",
}
INSTRUCTIONS = """Ti si analitičar tendera za konsultantsku firmu. Profil firme:
{profile}

Za svaku objavu procijeni koliko je relevantna za firmu, kao posao na koji bi firma mogla ponuditi:
3 = jasno u oblastima firme, vrijedi pogledati odmah
2 = moguće relevantno, ili samo dijelom u oblastima firme
1 = slabo relevantno
0 = nije za firmu (npr. nabavka robe, građevinski radovi, oprema ili usluge izvan oblasti firme)

Odgovori isključivo JSON listom, bez ikakvog drugog teksta, s jednim elementom za svaku objavu.
U obrazloženju ne koristi navodnike.
[{{"i": 1, "s": 2, "r": "obrazloženje na bosanskom, najviše 12 riječi"}}]"""
# Javni pozivi (grantovi) ocjenjuju se za dvije organizacije, uz procjenu ko smije aplicirati.
CALLS = """Ti si analitičar javnih poziva (grantova) za dvije organizacije iz Bosne i Hercegovine.

CETEOR, privatna konsultantska firma: {profile}

REIC, nevladina organizacija: {profile_reic}

Za svaki javni poziv procijeni smije li CETEOR, REIC ili obje aplicirati, kao nosilac ili partner
(po vrsti organizacije i državi; BiH je zemlja kandidat za članstvo u EU), i koliko poziv odgovara
njihovom radu. Ocjena s vrijedi za onu koja bolje odgovara:
3 = jasno relevantno i prihvatljivo, vrijedi pogledati odmah
2 = moguće relevantno ili prihvatljivost nije sigurna
1 = slabo relevantno
0 = nije za njih (npr. samo za građane, općine, poljoprivrednike ili organizacije iz drugih zemalja)
w = "C" ako je za CETEOR, "R" ako je za REIC, "CR" ako je za obje, "" ako ni za jednu.

Odgovori isključivo JSON listom, bez ikakvog drugog teksta, s jednim elementom za svaki poziv.
U obrazloženju ne koristi navodnike; ako je poznato, navedi ko smije aplicirati.
[{{"i": 1, "s": 2, "w": "CR", "r": "obrazloženje na bosanskom, najviše 12 riječi"}}]"""
KINDS = {"S": "usluge", "G": "robe", "W": "radovi"}


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
    parts = [r["t"], r.get("b") or "", ", ".join(r.get("c") or []), KINDS.get(r.get("k"), ""),
             r.get("n") or "", r["src"]]
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


def _run(key: str, conf: dict, system: str, work: list, info: dict, stop: float, calls: bool) -> bool:
    """Ocjenjuje listu u grupama. Vraća False ako treba stati (pogrešan ključ, isteklo vrijeme)."""
    size = max(1, int(conf["batch"]))
    for k in range(0, len(work), size):
        if time.time() > stop:
            info["error"] = "isteklo vrijeme za ocjenjivanje; ostatak se ocjenjuje pri sljedećem osvježavanju"
            return False
        chunk = work[k:k + size]
        body = {"model": conf["model"], "max_tokens": 70 * len(chunk) + 200, "system": system,
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
    info = {"model": conf["model"], "on": bool(key), "new": 0, "error": None}
    if not key:
        info["error"] = ("AI ocjena je isključena: na GitHubu nije postavljen secret "
                         "ANTHROPIC_API_KEY.")
    elif not str(conf["profile"]).strip():
        info["error"] = "AI ocjena je isključena: u config.json nema profila firme (ai, profile)."
    else:
        todo.sort(key=lambda r: r.get("fs") or r.get("p") or "", reverse=True)
        work = todo[:int(conf["max_per_run"])]
        stop = time.time() + float(conf["minutes"]) * 60
        tenders = [r for r in work if r.get("ty") != "P"]
        calls = [r for r in work if r.get("ty") == "P"]
        profile = str(conf["profile"]).strip()
        reic = str(conf["profile_reic"]).strip() or "nevladina organizacija iz BiH (opis nije unesen)"
        # Prvo javni pozivi (manje ih je), zatim tenderi; staje se na pogrešnom ključu ili isteku vremena.
        if _run(key, conf, CALLS.format(profile=profile, profile_reic=reic), calls, info, stop, True):
            _run(key, conf, INSTRUCTIONS.format(profile=profile), tenders, info, stop, False)
    info["scored"] = sum(1 for r in pool if "ai" in r)
    info["pending"] = sum(1 for r in pool if "ai" not in r)
    return info
