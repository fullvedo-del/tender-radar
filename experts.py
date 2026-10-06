"""Preporuka eksperata iz roster-a za tendere s AI ocjenom 2 ili 3 za CETEOR (Claude API).

Roster je u fajlu experts.enc.json u glavnom folderu repozitorija, šifriran istom šifrom kao interni
izvori; stranica ga piše preko GitHub API-ja (tab „Eksperti“). collect.py ga dešifruje i ovdje AI za
svaki tender s ocjenom 2 ili 3 bira do tri eksperta. Rezultat se piše šifriran u
data/expertmatch.json, pa se na stranici vidi tek nakon unosa šifre.

Preporuka se računa jednom po tenderu i prenosi iz dana u dan. Kad se roster promijeni (podaci koje
AI vidi), preporuke se postepeno računaju ponovo, poslije novih tendera; do tada vrijede stare.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import time

import ai_score

DEFAULTS = {
    "on": True,
    "batch": 8,           # tendera po jednom upitu
    "max_per_run": 400,   # najviše preporuka po osvježavanju
    "minutes": 4,         # vremenski okvir u jednom osvježavanju
    "top": 3,             # najviše eksperata po tenderu
}
PROMPT = """Ti si menadžer ponuda u CETEOR-u, konsultantskoj i inženjerskoj firmi iz BiH (okoliš, energija, klima).
Za svaki tender iz poruke izaberi do {top} eksperta iz roster-a ispod koji bi bili najbolji u timu za taj posao:
po stručnim oblastima, vrsti posla, fakultetu, iskustvu, profilu iz CV-ja, znanju engleskog i drugih jezika
za međunarodne naručioce i mjestu rada. Biraj samo one koji stvarno odgovaraju; ako nijedan ne odgovara, vrati praznu listu.
Uz podjednaku stručnost prednost imaju uposlenici, pa vanjski saradnici s kojima je saradnja lagana.
Razlog napiši na bosanskom, najviše 12 riječi, bez navodnika.
Odgovori isključivo JSON listom, bez ikakvog drugog teksta, s jednim elementom za svaki tender:
[{{"i": 1, "e": [{{"id": 12, "r": "razlog"}}]}}]

<roster>
{roster}
</roster>"""
ITEM_RX = re.compile(r'"i"\s*:\s*(\d+)\s*,\s*"e"\s*:\s*\[(.*?)\]\s*\}', re.S)
PICK_RX = re.compile(r'"id"\s*:\s*"?(\d+)"?\s*(?:,\s*"r"\s*:\s*"(.*?)"\s*)?\}', re.S)


def _conf(cfg: dict) -> dict:
    return {**ai_score.DEFAULTS, **(cfg.get("ai") or {}), **DEFAULTS, **(cfg.get("experts") or {})}


def _start(x: dict) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(x.get("pocetak"))[:10])
    except ValueError:
        return None


def years(x: dict, today: dt.date | None = None) -> float | None:
    start = _start(x)
    return None if start is None else max(0.0, round(((today or dt.date.today()) - start).days / 365.25, 1))


def name(x: dict) -> str:
    return " ".join(p for p in (str(x.get("ime") or "").strip(), str(x.get("prezime") or "").strip()) if p) or f"Ekspert {x.get('id')}"


def digest(roster: list, stable: bool = False) -> str:
    """Roster u obliku za AI: jedan red po ekspertu, samo ono što je važno za izbor (bez kontakata,
    dnevnica i poznanstava). stable: početak karijere umjesto godina iskustva, koje rastu same od sebe."""
    lines = []
    for x in sorted(roster, key=lambda x: int(x.get("id") or 0)):
        start = _start(x)
        exp = "" if start is None else f"u struci od {start:%m.%Y}." if stable else f"{int(years(x))} god. iskustva"
        parts = [f"{x.get('id')}. {name(x)}", x.get("sprema") or "", exp,
                 "oblasti: " + ", ".join(x.get("oblasti") or []) if x.get("oblasti") else "",
                 "posao: " + ", ".join(x.get("tip") or []) if x.get("tip") else "",
                 "fakultet: " + ", ".join(x.get("fakultet") or []) if x.get("fakultet") else "",
                 f"engleski {x['engleski']}" if x.get("engleski") else "",
                 "ostali jezici: " + ", ".join(x.get("jezici") or []) if x.get("jezici") else "",
                 ", ".join(p for p in (x.get("grad"), x.get("drzava")) if p),
                 x.get("kategorija") or "", f"saradnja {x['saradnja'].lower()}" if x.get("saradnja") else "",
                 "profil: " + str(x.get("profil"))[:400] if x.get("profil") else "",
                 "napomene: " + re.sub(r"\s+", " ", str(x.get("napomene")))[:200] if x.get("napomene") else ""]
        lines.append(" | ".join(p for p in parts if p))
    return "\n".join(lines)


def version(roster: list) -> str:
    """Oznaka verzije roster-a: mijenja se samo kad se u roster-u promijeni ono što AI vidi, a ne kad
    ekspertima protokom vremena poraste iskustvo."""
    return hashlib.sha1(f"{PROMPT}\n{digest(roster, stable=True)}".encode("utf-8")).hexdigest()[:10]


def _line(i: int, r: dict) -> str:
    parts = [r.get("t") or "", f"EN: {r['en']}" if r.get("en") else "", r.get("b") or "", ", ".join(r.get("c") or []),
             f"sažetak: {r['sm']}" if r.get("sm") else "", f"AI: {r['air']}" if r.get("air") else ""]
    return f"{i}. " + " | ".join(p for p in parts if p)


def _parse(text: str, n: int, ids: set, top: int) -> dict:
    """{redni broj tendera: [(id eksperta, razlog), ...]}; nepoznati ID-evi se odbacuju."""
    items = []
    m = re.search(r"\[.*\]", text, re.S)
    if m:
        try:
            for x in json.loads(m.group(0)):
                if isinstance(x, dict):
                    items.append((x.get("i"), [(e.get("id"), e.get("r")) for e in x.get("e") or [] if isinstance(e, dict)]))
        except ValueError:
            items = []
    if not items:
        items = [(i, PICK_RX.findall(body)) for i, body in ITEM_RX.findall(text)]
    if not items and not re.search(r"\[\s*\]", text):
        raise ValueError("AI nije vratio preporuke u očekivanom obliku")
    out = {}
    for i, picks in items:
        try:
            i = int(i)
        except (TypeError, ValueError):
            continue
        if not 1 <= i <= n:
            continue
        chosen = []
        for eid, why in picks:
            try:
                eid = int(eid)
            except (TypeError, ValueError):
                continue
            if eid in ids and eid not in [c[0] for c in chosen]:
                chosen.append((eid, re.sub(r"\s+", " ", str(why or "")).replace('\\"', '"').strip()[:140]))
        out[i] = chosen[:top]
    return out


def recommend(recs: list, roster: list, cfg: dict, private: set, prev: dict | None) -> tuple[dict, dict]:
    """(rezultat za data/expertmatch.json, stanje za status.json)."""
    conf = _conf(cfg)
    key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    roster = [x for x in roster if isinstance(x, dict) and x.get("id") is not None]
    by_id = {int(x["id"]): x for x in roster}
    rv = version(roster)
    pool = [r for r in recs if not r.get("dup") and r.get("ty") != "P" and r.get("ai") in (2, 3)
            and (conf["include_private"] or r["src"] not in private)]
    prev = prev if isinstance(prev, dict) else {}
    old_m, old_v = prev.get("m") or {}, prev.get("v") or {}
    out_m, out_v = {}, {}
    for r in pool:  # prenose se preporuke za tendere koji su još u listi
        if r["id"] in old_m:
            out_m[r["id"]], out_v[r["id"]] = old_m[r["id"]], old_v.get(r["id"])
    info = {"on": bool(key and conf["on"] and roster), "n": len(roster), "new": 0, "error": None}
    if not key:
        info["error"] = "preporuka eksperata treba AI ključ (secret ANTHROPIC_API_KEY)"
    elif info["on"]:
        newest = lambda r: r.get("fs") or r.get("p") or ""  # noqa: E731
        todo = sorted((r for r in pool if r["id"] not in out_m), key=newest, reverse=True)
        todo += sorted((r for r in pool if r["id"] in out_m and out_v.get(r["id"]) != rv), key=newest, reverse=True)
        todo = todo[:int(conf["max_per_run"])]
        top = max(1, int(conf["top"]))
        system = [{"type": "text", "text": PROMPT.format(top=top, roster=digest(roster)), "cache_control": {"type": "ephemeral"}}]
        stop = time.time() + float(conf["minutes"]) * 60
        size = max(1, int(conf["batch"]))
        for k in range(0, len(todo), size):
            if time.time() > stop:
                info["error"] = "isteklo vrijeme za preporuke; ostatak se radi pri sljedećem osvježavanju"
                break
            chunk = todo[k:k + size]
            body = {"model": conf["model"], "max_tokens": 160 * len(chunk) + 200, "system": system,
                    "messages": [{"role": "user", "content": "\n".join(_line(i, r) for i, r in enumerate(chunk, 1))}]}
            try:
                got = _parse(ai_score._call(key, body), len(chunk), set(by_id), top)
            except ai_score.Fatal as e:
                info["error"] = str(e)
                break
            except Exception as e:  # jedan neuspjeli upit ne zaustavlja ostale
                info["error"] = f"{e}"[:300] or type(e).__name__
                continue
            for i, r in enumerate(chunk, 1):
                if i in got:
                    out_m[r["id"]] = [[eid, name(by_id[eid]), why] for eid, why in got[i]]
                    out_v[r["id"]] = rv
                    info["new"] += 1
    # Obrisan ekspert ne ostaje u preporukama, a ime je uvijek iz trenutnog roster-a.
    out_m = {k: [[e[0], name(by_id[e[0]]), e[2]] for e in v if e and e[0] in by_id] for k, v in out_m.items()}
    info["matched"] = sum(1 for v in out_m.values() if v)
    info["pending"] = sum(1 for r in pool if r["id"] not in out_m or out_v.get(r["id"]) != rv) if info["on"] else 0
    return {"rv": rv, "m": out_m, "v": out_v}, info
