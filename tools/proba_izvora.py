"""Proba novih izvora sa GitHub servera (pokreće se ručno: Actions, „Proba izvora“, Run workflow).

Za svaki trag prvo čita robots.txt. Ako robots.txt zabranjuje putanju ili se ne može pročitati
zbog greške servera (5xx, isteklo vrijeme), zahtjev se ne šalje. Šalje se najviše nekoliko
zahtjeva, s jednim poštenim User-Agentom. Ništa se ne sprema u repozitorij: rezultat je u
zapisniku posla i u sažetku posla (Summary) na GitHubu, red po red, pa ostaje i ako posao
prekine.
"""
from __future__ import annotations

import json
import os
import re
import signal
import sys
import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

UA = "TenderRadar/1.0 (dnevni indeks javnih objava o nabavkama; python-requests)"
S = requests.Session()
S.headers["User-Agent"] = UA
S.headers["Accept"] = "application/json, text/html;q=0.9, */*;q=0.8"
SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY")
ROBOTS: dict[str, urllib.robotparser.RobotFileParser | tuple[bool, str]] = {}
MAX_BYTES = 5_000_000  # odgovor se čita najviše do ove veličine
MAX_SECS = 60          # cijeli zahtjev traje najviše ovoliko sekundi


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


def _show_json(data) -> None:
    res = data.get("result") if isinstance(data, dict) else None
    if isinstance(res, dict) and isinstance(res.get("results"), list):  # CKAN (data.gov.mk)
        say(f"- CKAN: pronađeno {res.get('count')} skupova; prvih 20 (naziv | organizacija | izmijenjeno):")
        for p in res["results"][:20]:
            say(f"  - {p.get('title')} | {(p.get('organization') or {}).get('title')} | {p.get('metadata_modified')}")
        return
    items = data if isinstance(data, list) else (
        next((v for v in data.values() if isinstance(v, list)), None) if isinstance(data, dict) else None)
    if isinstance(data, dict):
        say(f"- ključevi na vrhu: {list(data)[:15]}")
    if items is not None:
        say(f"- broj zapisa: {len(items)}")
        if items:
            say("- prvi zapis:")
            say("```")
            say(json.dumps(items[0], ensure_ascii=False, indent=1)[:2500])
            say("```")


def probe(name: str, url: str, method: str = "GET", show_json: bool = True, **kw):
    """Šalje jedan zahtjev ako robots.txt dozvoljava; vraća (odgovor, tekst) ili None."""
    ok, why = robots_ok(url)
    say(f"### {name}")
    say(f"- adresa: `{url}`" + (f" s parametrima {kw['params']}" if kw.get("params") else ""))
    say(f"- {why}; dozvoljeno: {'da' if ok else 'NE'}")
    if not ok:
        say("- zahtjev nije poslan")
        return None
    time.sleep(1)
    t0, r, buf, cut = time.monotonic(), None, bytearray(), False
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(MAX_SECS)  # tvrda granica za cijeli zahtjev, i kad server šalje kap po kap
    try:
        r = S.request(method, url, timeout=45, stream=True, **kw)
        for chunk in r.iter_content(8192):
            buf += chunk
            if len(buf) >= MAX_BYTES:
                cut = True
                break
    except _TooSlow:
        cut = True
    except requests.RequestException as e:
        say(f"- greška veze: {type(e).__name__}: {str(e)[:200]}")
        return None
    finally:
        signal.alarm(0)
        if r is not None:
            r.close()
    if r is None:
        say(f"- nema odgovora ni poslije {MAX_SECS} s")
        return None
    body = bytes(buf)
    enc = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"  # requests-ov podrazumijevani
    try:
        text = body.decode(enc, errors="replace")
    except LookupError:
        text = body.decode("utf-8", errors="replace")
    ct = r.headers.get("content-type", "?")
    say(f"- HTTP {r.status_code}, {ct}, {len(body)} bajta, {time.monotonic() - t0:.1f} s"
        + (f" (skraćeno: veće od 5 MB ili duže od {MAX_SECS} s)" if cut else "")
        + (f", Content-Length: {r.headers.get('content-length')}" if r.headers.get("content-length") else "")
        + (f", Location: `{r.headers.get('location')}`" if r.headers.get("location") else "")
        + (f", Last-Modified: {r.headers.get('last-modified')}" if r.headers.get("last-modified") else "")
        + (", Cloudflare" if "cf-ray" in r.headers else ""))
    if show_json and r.ok and "json" in ct and not cut:
        try:
            _show_json(json.loads(text))
            return r, text
        except ValueError:
            say("- odgovor nije ispravan JSON")
    if method != "HEAD" and text.strip():
        say("- prvih 1000 znakova odgovora:")
        say("```")
        say(text[:1000])
        say("```")
    return r, text


def main() -> int:
    say(f"# Proba izvora ({time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())})")
    say()
    # Kosovo: OCDS API Regulatorne komisije za javne nabavke (PPRC)
    base = "https://ocdskrpp.rks-gov.net/krppAPI/"
    iso = {"endDateFrom": "2026-10-01", "endDateEnd": "2026-10-08"}
    tries = [
        ("Kosovo, Tender bez parametara", "Tender", None),
        ("Kosovo, Tender, rok 2026-10-01 do 2026-10-08", "Tender", iso),
        ("Kosovo, Tender, rok 10/01/2026 do 10/08/2026", "Tender", {"endDateFrom": "10/01/2026", "endDateEnd": "10/08/2026"}),
        ("Kosovo, Tender, rok 01.10.2026 do 08.10.2026", "Tender", {"endDateFrom": "01.10.2026", "endDateEnd": "08.10.2026"}),
        ("Kosovo, Tender, rok 2026-10-01 do 2026-10-08, DataFormat=json", "Tender", {**iso, "DataFormat": "json"}),
        ("Kosovo, TenderRelease, rok 2026-10-01 do 2026-10-08, DataFormat=json", "TenderRelease", {**iso, "DataFormat": "json"}),
        ("Kosovo, TenderRelease, rok 2026-10-01 do 2026-10-08", "TenderRelease", iso),
    ]
    allowed = robots_ok(base + "Tender")[0]
    for name, path, params in tries:  # svaka varijanta se proba, i kad prethodna vrati grešku
        probe(name, base + path, **({"params": params} if params else {}))
        if not allowed:
            break  # robots.txt ne dozvoljava ili se ne može pročitati: ostale varijante se ne šalju
    # Sjeverna Makedonija: stranica otvorenih podataka ESJN
    got = probe("Sjeverna Makedonija, otvoreni podaci", "https://www.e-nabavki.gov.mk/opendata-announcements.aspx",
                show_json=False)
    if got is not None and got[0].ok:
        scripts = sorted(set(re.findall(r"""src=["']([^"']+\.js[^"']*)""", got[1])))[:20]
        services = sorted(set(re.findall(r"[\w/.-]+\.(?:asmx|svc|ashx)[\w/.-]*", got[1])))[:20]
        say(f"- skripte: {scripts}")
        say(f"- servisi u stranici: {services}")
    # Sjeverna Makedonija: državni portal otvorenih podataka (CKAN API)
    probe("Sjeverna Makedonija, data.gov.mk, skupovi o javnim nabavkama",
          "https://data.gov.mk/api/3/action/package_search", params={"q": "јавни набавки", "rows": 50})
    # Srbija: trajni link resursa na data.gov.rs (kuda vodi)
    got = probe("Srbija, data.gov.rs trajni link (bez praćenja)",
                "https://data.gov.rs/sr/datasets/r/50881b17-0d4a-4f6b-b9fc-26e148780f27",
                show_json=False, allow_redirects=False)
    loc = got[0].headers.get("location") if got is not None else None
    if loc:
        probe("Srbija, fajl na koji link vodi (samo zaglavlje)", loc, method="HEAD", show_json=False,
              allow_redirects=False)
    say()
    say("Kraj probe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
