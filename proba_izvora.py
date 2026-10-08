"""Proba novih izvora sa GitHub servera (pokreće se ručno: Actions, „Proba izvora“, Run workflow).

Za svaki trag prvo čita robots.txt. Ako robots.txt zabranjuje putanju ili se ne može pročitati
zbog greške servera (5xx, isteklo vrijeme), zahtjev se ne šalje. Šalje se najviše nekoliko
zahtjeva, s jednim poštenim User-Agentom. Ništa se ne sprema u repozitorij: rezultat je u
zapisniku posla i u sažetku posla (Summary) na GitHubu, red po red, pa ostaje i ako posao
prekine. Kontakt podaci (imena, e-mail, telefon) se ne ispisuju.

Ova proba: Kosovo OCDS API (opis API-ja, koliko traje, koja polja daje) i jedna pretraga
data.gov.mk.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import signal
import sys
import time
import urllib.robotparser
from collections import Counter
from urllib.parse import urlsplit

import requests

UA = "TenderRadar/1.0 (dnevni indeks javnih objava o nabavkama; python-requests)"
S = requests.Session()
S.headers["User-Agent"] = UA
S.headers["Accept"] = "application/json, text/html;q=0.9, */*;q=0.8"
SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY")
ROBOTS: dict[str, urllib.robotparser.RobotFileParser | tuple[bool, str]] = {}
HIDE = re.compile(r"contact|email|telephone|phone|fax|person", re.I)  # ovo se ne ispisuje
KS = "https://ocdskrpp.rks-gov.net/krppAPI/"
MK = "https://data.gov.mk/api/3/action/package_search"


def say(line: str = "") -> None:
    print(line, flush=True)
    if SUMMARY:
        with open(SUMMARY, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def robots_ok(url: str) -> tuple[bool, str]:
    """(smije li se, opis stanja robots.txt)."""
    p = urlsplit(url)
    host = f"{p.scheme}://{p.netloc}"
    if host not in ROBOTS:
        try:
            r = S.get(host + "/robots.txt", timeout=30, allow_redirects=True)
            if r.status_code >= 500:
                ROBOTS[host] = (False, f"robots.txt: greška servera {r.status_code}")
            elif r.status_code >= 400:  # RFC 9309: nedostupan robots.txt (4xx) znači bez ograničenja
                ROBOTS[host] = (True, f"robots.txt nije dostupan ({r.status_code})")
            else:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(r.text.splitlines())
                ROBOTS[host] = rp
        except requests.RequestException as e:
            ROBOTS[host] = (False, f"robots.txt se ne može pročitati ({type(e).__name__})")
    st = ROBOTS[host]
    if isinstance(st, tuple):
        return st
    return st.can_fetch(UA, url), "robots.txt pročitan"


class _TooSlow(Exception):
    pass


def _alarm(*_):
    raise _TooSlow


def fetch(name: str, url: str, secs: int = 60, max_mb: int = 5, **kw):
    """Jedan GET ako robots.txt dozvoljava; vraća (odgovor, tekst, skraćeno) ili None."""
    ok, why = robots_ok(url)
    say(f"### {name}")
    say(f"- adresa: `{url}`" + (f" s parametrima {kw['params']}" if kw.get("params") else ""))
    say(f"- {why}; dozvoljeno: {'da' if ok else 'NE'}")
    if not ok:
        say("- zahtjev nije poslan")
        return None
    time.sleep(1)
    t0, r, head, buf, cut = time.monotonic(), None, 0.0, bytearray(), False
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(secs)  # tvrda granica za cijeli zahtjev, i kad server šalje kap po kap
    try:
        r = S.get(url, timeout=(30, 120), stream=True, **kw)
        head = time.monotonic() - t0
        for chunk in r.iter_content(16384):
            buf += chunk
            if len(buf) >= max_mb * 1_000_000:
                cut = True
                break
    except _TooSlow:
        cut = True
    except requests.RequestException as e:
        say(f"- greška veze poslije {time.monotonic() - t0:.0f} s: {type(e).__name__}: {str(e)[:160]}")
        return None
    finally:
        signal.alarm(0)
        if r is not None:
            r.close()
    if r is None:
        say(f"- nema odgovora ni poslije {secs} s")
        return None
    total = time.monotonic() - t0
    size = r.headers.get("content-length")
    say(f"- HTTP {r.status_code}, {r.headers.get('content-type', '?')}, {len(buf)} bajta"
        + (f" od {size}" if size else "")
        + f"; zaglavlje stiglo za {head:.1f} s, ukupno {total:.1f} s,"
        + f" prijenos {len(buf) / 1024 / max(total - head, 0.1):.1f} KB/s"
        + (f" (skraćeno: granica {secs} s ili {max_mb} MB)" if cut else "")
        + (", Cloudflare" if "cf-ray" in r.headers else ""))
    enc = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"  # requests-ov podrazumijevani
    try:
        text = bytes(buf).decode(enc, errors="replace")
    except LookupError:
        text = bytes(buf).decode("utf-8", errors="replace")
    return r, text, cut


def show(text: str, n: int = 800) -> None:
    if text.strip():
        say(f"- prvih {n} znakova odgovora:")
        say("```")
        say(text[:n])
        say("```")


def records(got) -> list | None:
    """Lista zapisa iz JSON odgovora, ili None (uz ispis razloga)."""
    if got is None:
        return None
    r, text, cut = got
    if cut or not r.ok:
        show(text)
        return None
    try:
        data = json.loads(text)
    except ValueError:
        say("- odgovor nije ispravan JSON")
        show(text)
        return None
    recs = data if isinstance(data, list) else (
        next((v for v in data.values() if isinstance(v, list)), None) if isinstance(data, dict) else None)
    if recs is None:
        say(f"- JSON bez liste zapisa; ključevi: {list(data)[:15] if isinstance(data, dict) else type(data).__name__}")
        return None
    say(f"- broj zapisa: {len(recs)}")
    return recs


def _leaves(x, path: str, out: dict) -> None:
    if isinstance(x, dict):
        for k, v in x.items():
            _leaves(v, f"{path}.{k}" if path else str(k), out)
    elif isinstance(x, list):
        for v in x[:5]:
            _leaves(v, path + "[]", out)
    elif x not in (None, ""):
        out.setdefault(path, []).append(x)


def digest(recs: list, paths: bool = True) -> None:
    """Polja s popunjenošću i primjerom, vrijednosti statusa i vrsta, rasponi datuma."""
    fill, example, first, lo, hi = Counter(), {}, {}, {}, {}
    for rec in recs:
        leaves: dict = {}
        _leaves(rec, "", leaves)
        for p, vals in leaves.items():
            fill[p] += 1
            example.setdefault(p, vals[0])
            first.setdefault(p, Counter())[str(vals[0])] += 1
            if "date" in p.rsplit(".", 1)[-1].lower():
                lo[p] = min([lo.get(p, str(vals[0]))] + [str(v) for v in vals])
                hi[p] = max([hi.get(p, str(vals[0]))] + [str(v) for v in vals])
    if paths:
        say(f"- polja (u koliko zapisa od {len(recs)} je popunjeno, primjer):")
        for p in sorted(fill)[:160]:
            say(f"  - `{p}`: {fill[p]}, npr. {'(skriveno)' if HIDE.search(p) else str(example[p])[:70]}")
    for p in sorted(fill):
        last = p.rsplit(".", 1)[-1].lower()
        if not HIDE.search(p) and re.search(r"status|method|category|currency", last) and len(first[p]) <= 25:
            say(f"- vrijednosti `{p}`: " + ", ".join(f"{v} ({n})" for v, n in first[p].most_common(12)))
    for p in sorted(lo):
        say(f"- raspon `{p}`: {lo[p]} do {hi[p]}")


def api_help() -> None:
    got = fetch("Kosovo, opis API-ja (Help)", KS + "Help")
    if got is not None and got[0].ok:
        names = [html.unescape(n).strip()
                 for n in re.findall(r'class="api-name"[^>]*>\s*<a[^>]*>([^<]+)</a>', got[1])]
        if names:
            say(f"- metode ({len(names)}):")
            for n in names[:80]:
                say(f"  - `{n}`")
            return
        show(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", got[1])))
        return
    got = fetch("Kosovo, opis API-ja (swagger)", KS + "swagger/docs/v1")
    if got is not None and got[0].ok and not got[2]:
        try:
            spec = json.loads(got[1])
        except ValueError:
            show(got[1])
            return
        for path, ops in (spec.get("paths") or {}).items():
            for method, op in (ops or {}).items():
                params = [q.get("name") for q in (op or {}).get("parameters", []) if isinstance(q, dict)]
                say(f"  - `{method.upper()} {path}` {params}")


def main() -> int:
    say(f"# Proba izvora ({time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())})")
    say()
    today = dt.date.today()
    api_help()
    # Kosovo: tenderi s rokom od danas do +7 dana; sva polja i koliko traje
    week = fetch("Kosovo, Tender, rok od danas do +7 dana", KS + "Tender", secs=300, max_mb=20,
                 params={"endDateFrom": today.isoformat(), "endDateEnd": (today + dt.timedelta(days=7)).isoformat()})
    recs = records(week)
    if recs:
        digest(recs)
        uri = next((x.get("uri") for x in recs if isinstance(x, dict) and x.get("uri")), None)
        if uri:  # da li je stranica tendera (link za čovjeka) javna
            got = fetch("Kosovo, stranica tendera na e-prokurimi (uri iz API-ja)", uri)
            if got is not None:
                m = re.search(r"<title[^>]*>(.*?)</title>", got[1], re.S | re.I)
                say(f"- naslov stranice: {html.unescape(m[1]).strip()[:120] if m else '(nema)'}")
    # Sjeverna Makedonija: najnoviji skupovi s riječju „огласи“ (oglasi) na data.gov.mk
    got = fetch("Sjeverna Makedonija, data.gov.mk, skupovi „огласи“, najnoviji prvi", MK,
                params={"q": "огласи", "sort": "metadata_modified desc", "rows": 20})
    if got is not None and got[0].ok and not got[2]:
        try:
            res = json.loads(got[1]).get("result") or {}
        except (ValueError, AttributeError):
            res = {}
        say(f"- pronađeno {res.get('count')} skupova (naziv | organizacija | izmijenjeno | formati):")
        for p in res.get("results") or []:
            fmts = sorted({(x.get("format") or "?") for x in p.get("resources") or []})
            say(f"  - {p.get('title')} | {(p.get('organization') or {}).get('title') or ''} | "
                f"{p.get('metadata_modified')} | {', '.join(fmts)}")
    # Kosovo: rok od danas do +45 dana (otprilike svi otvoreni tenderi); samo trajanje i rasponi
    if week is None or week[2]:
        say("### Kosovo, Tender, rok od danas do +45 dana: preskočeno, jer ni 7 dana nije stiglo na vrijeme")
    else:
        recs = records(fetch("Kosovo, Tender, rok od danas do +45 dana (mjerenje)", KS + "Tender", secs=360,
                             max_mb=40, params={"endDateFrom": today.isoformat(),
                                                "endDateEnd": (today + dt.timedelta(days=45)).isoformat()}))
        if recs:
            digest(recs, paths=False)
    say()
    say("Kraj probe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
