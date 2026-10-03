"""Zajedničke funkcije za sve kolektore (izvore tendera).

Svaki kolektor je modul u ovom paketu koji izlaže:

    META = {"key": "TED", "name": "TED (EU)", "home": "https://ted.europa.eu"}
    def collect(cfg: dict) -> list[dict]   # zapisi napravljeni preko base.rec()

Kolektor NE smije tiho vratiti praznu listu ako ne prepozna strukturu izvora:
u tom slučaju diže SourceChanged, da kvar bude vidljiv na stranici.
"""
from __future__ import annotations

import datetime as dt
import html
import re
import sys
import time
import unicodedata

import pycountry
import requests

# Jedan, pošten User-Agent. Ako ga izvor odbije, izvor se prijavljuje kao
# nedostupan; ne zaobilazimo blokade lažnim predstavljanjem.
UA = "TenderRadar/1.0 (dnevni indeks javnih objava o nabavkama; python-requests)"
TIMEOUT = 45


class SourceChanged(RuntimeError):
    """Izvor odgovara, ali struktura nije ona koju kolektor očekuje."""


class SourceBlocked(RuntimeError):
    """Izvor odbija automatski pristup (403, captcha, robots.txt)."""


# --------------------------------------------------------------------------- HTTP

def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept-Language": "en,bs;q=0.8,hr;q=0.7,sr;q=0.6",
    })
    return s


def fetch(s: requests.Session, method: str, url: str, *, tries: int = 3,
          pause: float = 2.0, ok=(200,), **kw) -> requests.Response:
    """HTTP zahtjev s ponavljanjem na mrežne greške, 429 i 5xx.

    403/401 se ne ponavlja: diže SourceBlocked.
    """
    kw.setdefault("timeout", TIMEOUT)
    last = None
    for i in range(tries):
        try:
            r = s.request(method, url, **kw)
        except requests.RequestException as e:  # mreža, timeout, TLS
            last = e
            time.sleep(pause * (i + 1))
            continue
        if r.status_code in ok:
            return r
        if r.status_code in (401, 403):
            raise SourceBlocked(f"{r.status_code} za {url}")
        if r.status_code == 429 or r.status_code >= 500:
            wait = pause * (i + 1)
            ra = r.headers.get("Retry-After", "")
            if ra.isdigit():
                wait = min(int(ra), 60)
            last = RuntimeError(f"HTTP {r.status_code} za {url}")
            time.sleep(wait)
            continue
        raise RuntimeError(f"HTTP {r.status_code} za {url}")
    raise RuntimeError(f"Neuspješno nakon {tries} pokušaja: {last}")


# --------------------------------------------------------------------------- tekst

def clean(text) -> str:
    """Skida HTML entitete i višak razmaka."""
    if text is None:
        return ""
    t = html.unescape(str(text))
    t = t.replace(" ", " ").replace("​", "")
    return re.sub(r"\s+", " ", t).strip()


def norm(text) -> str:
    """Mala slova, bez dijakritike, samo slova i cifre (za poređenje/dedup)."""
    t = unicodedata.normalize("NFKD", clean(text).lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace("đ", "dj").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


# --------------------------------------------------------------------------- datumi

_MONTHS = {}
for _i, _names in enumerate([
    ("jan", "january", "januar", "sijecanj", "janvier", "januar"),
    ("feb", "february", "februar", "veljaca", "fevrier", "fev"),
    ("mar", "march", "mart", "ozujak", "mars"),
    ("apr", "april", "travanj", "avril", "avr"),
    ("may", "maj", "svibanj", "mai"),
    ("jun", "june", "juni", "lipanj", "juin"),
    ("jul", "july", "juli", "srpanj", "juillet", "juil"),
    ("aug", "august", "avgust", "kolovoz", "aout"),
    ("sep", "sept", "september", "septembar", "rujan", "septembre"),
    ("oct", "october", "okt", "oktobar", "listopad", "octobre"),
    ("nov", "november", "novembar", "studeni", "novembre"),
    ("dec", "december", "decembar", "prosinac", "decembre"),
], start=1):
    for _n in _names:
        _MONTHS[_n] = _i


def today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def _mk(y: int, m: int, d: int) -> str | None:
    if y < 100:
        y += 2000
    try:
        return dt.date(y, m, d).isoformat()
    except ValueError:
        return None


def iso_date(value, dayfirst: bool = True) -> str | None:
    """Vraća 'YYYY-MM-DD' ili None. Datum se uzima kako ga izvor piše
    (bez preračunavanja vremenskih zona)."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, (int, float)):
        v = float(value)
        if v > 1e11:  # milisekunde
            v /= 1000.0
        if v > 1e8:
            return dt.datetime.fromtimestamp(v, dt.timezone.utc).date().isoformat()
        return None
    s = clean(value)
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return _mk(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        return _mk(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"/Date\((\d{10,13})", s)  # .NET JSON
    if m:
        return iso_date(int(m[1]))
    m = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})\b", s)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        d, mo = (a, b) if dayfirst else (b, a)
        if mo > 12 and d <= 12:
            d, mo = mo, d
        return _mk(y, mo, d)
    m = re.search(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b", s)
    if m:
        return _mk(int(m[1]), int(m[2]), int(m[3]))
    low = norm(s)
    # "2 October 2026", "02 Oct 26", "2. oktobar 2026"
    m = re.search(r"\b(\d{1,2}) ([a-z]{3,10}) (\d{4}|\d{2})\b", low)
    if m and m[2] in _MONTHS:
        return _mk(int(m[3]), _MONTHS[m[2]], int(m[1]))
    # "October 2, 2026", "Oct 2 2026"
    m = re.search(r"\b([a-z]{3,10}) (\d{1,2}) (\d{4})\b", low)
    if m and m[1] in _MONTHS:
        return _mk(int(m[3]), _MONTHS[m[1]], int(m[2]))
    return None


def iso_time(value) -> str | None:
    """Vraća 'HH:MM' ako se u tekstu nalazi vrijeme."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.strftime("%H:%M")
    s = clean(value)
    m = re.search(r"(?:T|\s|^)(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm|AM|PM)?", s)
    if not m:
        return None
    h, mi = int(m[1]), int(m[2])
    ap = (m[3] or "").lower()
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if h > 23 or mi > 59:
        return None
    return f"{h:02d}:{mi:02d}"


# --------------------------------------------------------------------------- države

_COUNTRY_FIX = {
    "kosovo": "XK", "xkx": "XK", "xks": "XK", "xk": "XK", "1a": "XK", "kos": "XK",
    "kosovo under unscr 1244": "XK", "kosovo unscr 1244": "XK", "republic of kosovo": "XK",
    "turkey": "TR", "turkiye": "TR", "republic of turkiye": "TR",
    "moldova": "MD", "republic of moldova": "MD", "russia": "RU",
    "iran": "IR", "syria": "SY", "laos": "LA", "lao pdr": "LA", "vietnam": "VN",
    "tanzania": "TZ", "bolivia": "BO", "venezuela": "VE", "south korea": "KR",
    "korea republic of": "KR", "republic of korea": "KR", "north korea": "KP",
    "dr congo": "CD", "drc": "CD", "congo drc": "CD", "congo democratic republic of": "CD",
    "democratic republic of the congo": "CD", "democratic republic of congo": "CD",
    "congo dem rep": "CD", "congo dem republic": "CD", "congo rep": "CG",
    "republic of congo": "CG",
    "republic of the congo": "CG", "congo republic of": "CG",
    "cote d ivoire": "CI", "ivory coast": "CI", "cape verde": "CV", "cabo verde": "CV",
    "czech republic": "CZ", "macedonia": "MK", "north macedonia": "MK",
    "fyr macedonia": "MK", "republic of north macedonia": "MK",
    "the former yugoslav republic of macedonia": "MK",
    "bosnia herzegovina": "BA", "bosnia": "BA", "bih": "BA",
    "bosna i hercegovina": "BA", "bosnia and herzegovina": "BA",
    "palestine": "PS", "west bank and gaza": "PS", "state of palestine": "PS",
    "occupied palestinian territory": "PS", "gambia the": "GM", "the gambia": "GM",
    "egypt arab republic of": "EG", "yemen republic of": "YE", "kyrgyz republic": "KG",
    "slovak republic": "SK", "micronesia": "FM", "st lucia": "LC", "swaziland": "SZ",
    "st vincent and the grenadines": "VC", "st kitts and nevis": "KN",
    "sao tome and principe": "ST", "timor leste": "TL", "east timor": "TL",
    "brunei": "BN", "bahamas the": "BS", "the bahamas": "BS", "uk": "GB",
    "united kingdom": "GB", "great britain": "GB", "usa": "US", "united states": "US",
    "united states of america": "US", "serbia": "RS", "srbija": "RS",
    "montenegro": "ME", "crna gora": "ME", "albania": "AL", "croatia": "HR",
    "hrvatska": "HR", "slovenia": "SI", "netherlands": "NL", "the netherlands": "NL",
    "macao": "MO", "hong kong": "HK", "taiwan": "TW", "eswatini": "SZ",
}


def country_code(value) -> str | None:
    """Ime države (engl.), ISO2 ili ISO3 -> ISO2. Kosovo = 'XK'. Nepoznato -> None."""
    if not value:
        return None
    raw = clean(value)
    key = norm(raw)
    if not key:
        return None
    if key in _COUNTRY_FIX:
        return _COUNTRY_FIX[key]
    try:
        if len(raw) == 2 and raw.isalpha():
            c = pycountry.countries.get(alpha_2=raw.upper())
            return c.alpha_2 if c else None
        if len(raw) == 3 and raw.isalpha():
            c = pycountry.countries.get(alpha_3=raw.upper())
            if c:
                return c.alpha_2
        c = pycountry.countries.lookup(raw)
        return c.alpha_2
    except LookupError:
        pass
    # "Egypt, Arab Republic of" -> "Egypt"
    if "," in raw:
        return country_code(raw.split(",")[0])
    return None


_NAMES_RX = None
_NAMES_CODE: dict[str, str] = {}


def countries_in(text) -> list[str]:
    """ISO2 kodovi država čija se (engleska) imena izričito pojavljuju u tekstu, redom
    pojavljivanja. Služi izvorima koji državu navode samo u naslovu ili nazivu ureda."""
    global _NAMES_RX
    if _NAMES_RX is None:
        for c in pycountry.countries:
            for attr in ("name", "common_name"):
                n = getattr(c, attr, None)
                if n and "," not in n:
                    _NAMES_CODE[norm(n)] = c.alpha_2
        for k, v in _COUNTRY_FIX.items():
            if len(k) >= 5 or k == "bih":  # bez kratkih skraćenica (uk, usa, drc ...)
                _NAMES_CODE[k] = v
        for word in ("jersey", "reunion"):  # obične engleske riječi
            _NAMES_CODE.pop(word, None)
        alt = "|".join(sorted(map(re.escape, _NAMES_CODE), key=len, reverse=True))
        _NAMES_RX = re.compile(rf"(?<![a-z0-9])(?:{alt})(?![a-z0-9])")
    out: list[str] = []
    for m in _NAMES_RX.finditer(norm(text)):
        code = _NAMES_CODE[m.group(0)]
        if code not in out:
            out.append(code)
    return out


# --------------------------------------------------------------------------- zapis

# Vrsta ugovora
SERVICES, GOODS, WORKS, OTHER = "S", "G", "W", "O"

# Vrsta naručioca (zajednička taksonomija za sve izvore)
BUYER_TYPES = {
    "central": "Državni / centralni nivo",
    "regional": "Entitet, kanton, regija",
    "local": "Općina, grad",
    "pubco": "Javno preduzeće",
    "pubinst": "Javna ustanova",
    "eu": "EU institucija ili agencija",
    "un": "UN agencija",
    "ifi": "Međunarodna finansijska institucija",
    "intorg": "Međunarodna ili regionalna organizacija",
    "bilateral": "Bilateralna razvojna agencija",
    "other": "Ostalo / nepoznato",
}


def rec(src: str, sid, *, title, buyer, url, pub=None, due=None, due_time=None,
        countries=None, region=None, place=None, ctype=None, ntype=None,
        cpv=None, btype=None, btype_raw=None, value=None, currency=None,
        ref=None, bidder=None) -> dict:
    """Pravi normalizovan zapis o objavi.

    src        ključ izvora (META["key"])
    sid        stabilan ID objave unutar izvora (broj objave, referenca, slug URL-a)
    title      naziv objave / predmet nabavke
    buyer      ugovorni organ / naručilac
    url        javni link na objavu (stranica koju čovjek može otvoriti)
    pub, due   datum objave i rok za ponude (bilo koji format koji iso_date razumije)
    due_time   'HH:MM' roka, ako ga izvor daje
    countries  lista država izvršenja (ISO2/ISO3/engl. ime); ako nema, država naručioca
    region     za BiH: entitet/kanton; inače regija ako je izvor daje
    place      grad / mjesto
    ctype      SERVICES | GOODS | WORKS | OTHER
    ntype      vrsta objave ili postupka kako je izvor zove (kratko)
    cpv        lista CPV kodova (8 cifara, bez kontrolne cifre), glavni prvi
    btype      ključ iz BUYER_TYPES
    btype_raw  vrsta naručioca kako je izvor zove
    value, currency  procijenjena vrijednost, ako je objavljena
    ref        referentni broj koji naručilac koristi (ako se razlikuje od sid)
    bidder     ko može ponuditi, samo ako izvor to izričito kaže: 'org' (firma, organizacija),
               'ind' (pojedinac) ili 'both'
    """
    title = clean(title)
    if not title:
        raise ValueError(f"{src}:{sid} bez naziva")
    if not url or not str(url).startswith("http"):
        raise ValueError(f"{src}:{sid} bez ispravnog linka: {url!r}")
    if ctype not in (SERVICES, GOODS, WORKS, OTHER, None):
        raise ValueError(f"{src}:{sid} nepoznata vrsta ugovora {ctype!r}")
    if btype is not None and btype not in BUYER_TYPES:
        raise ValueError(f"{src}:{sid} nepoznata vrsta naručioca {btype!r}")
    if bidder not in ("org", "ind", "both", None):
        raise ValueError(f"{src}:{sid} nepoznata vrsta ponuđača {bidder!r}")

    cc: list[str] = []
    for c in (countries or []):
        code = country_code(c)
        if code and code not in cc:
            cc.append(code)

    codes: list[str] = []
    for c in (cpv or []):
        m = re.match(r"(\d{8})", clean(c))
        if m and m[1] not in codes:
            codes.append(m[1])

    r = {
        "id": f"{src}:{clean(sid)}",
        "src": src,
        "t": title[:400],
        "b": clean(buyer)[:200],
        "p": iso_date(pub),
        "d": iso_date(due),
        "dt": iso_time(due_time) if due_time else None,
        "c": cc,
        "reg": clean(region) or None,
        "loc": clean(place) or None,
        "k": ctype or OTHER,
        "n": clean(ntype)[:60] or None,
        "cpv": codes,
        "bt": btype or "other",
        "btr": clean(btype_raw)[:80] or None,
        "u": str(url).strip(),
        "v": float(value) if isinstance(value, (int, float)) and value > 0 else None,
        "cur": clean(currency)[:3].upper() or None,
        "ref": clean(ref)[:80] or None,
        "w": bidder,
    }
    return {k: v for k, v in r.items() if v not in (None, "", [])}


# --------------------------------------------------------------------------- CLI za testiranje

def cli(collect, meta: dict, cfg: dict | None = None) -> None:
    """python -m collectors.<modul>  -> ispis broja zapisa, pokrivenosti polja i uzoraka."""
    import json
    t0 = time.time()
    items = collect(cfg or {})
    n = len(items)
    print(f"{meta['key']}: {n} zapisa za {time.time() - t0:.1f}s")
    if not n:
        return
    td = today().isoformat()
    for label, key in [("datum objave", "p"), ("rok", "d"), ("država", "c"),
                       ("CPV", "cpv"), ("regija", "reg"), ("mjesto", "loc"),
                       ("vrsta objave", "n"), ("vrijednost", "v")]:
        k = sum(1 for r in items if r.get(key))
        print(f"  {label:14s} {100 * k // n:3d}%")
    for label, fn in [
        ("vrsta ugovora poznata", lambda r: r.get("k") != OTHER),
        ("vrsta naručioca poznata", lambda r: r.get("bt") != "other"),
        ("rok u budućnosti", lambda r: (r.get("d") or "") >= td),
    ]:
        print(f"  {label:24s} {100 * sum(1 for r in items if fn(r)) // n:3d}%")
    ids = [r["id"] for r in items]
    print(f"  duplih ID-eva: {len(ids) - len(set(ids))}")
    step = max(1, n // 3)
    for r in items[::step][:3]:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":  # brzi samotest pomoćnih funkcija
    assert iso_date("2026-10-28+01:00") == "2026-10-28"
    assert iso_date("28.10.2026. 12:00") == "2026-10-28"
    assert iso_date("02-Oct-26") == "2026-10-02"
    assert iso_date("October 2, 2026") == "2026-10-02"
    assert iso_date("2 octobre 2026") == "2026-10-02"
    assert iso_date("10/02/2026", dayfirst=False) == "2026-10-02"
    assert iso_date(1790899200000) == "2026-10-02"
    assert iso_time("28.10.2026. 12:00") == "12:00"
    assert iso_time("2026-10-28T09:30:00Z") == "09:30"
    assert iso_time("5:00 PM") == "17:00"
    assert country_code("BIH") == "BA" and country_code("Kosovo") == "XK"
    assert country_code("Türkiye") == "TR" and country_code("Egypt, Arab Republic of") == "EG"
    assert norm("Čišćenje – OKOLIŠ/đubre") == "ciscenje okolis djubre"
    print("OK", file=sys.stderr)
