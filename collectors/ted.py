"""TED (Tenders Electronic Daily, dodatak Službenom listu EU): otvoreni pozivi na nadmetanje.

Dokumentovan javni API bez prijave, TED Search API v3:
    POST https://api.ted.europa.eu/v3/notices/search
    https://docs.ted.europa.eu/api/latest/search.html
    https://api.ted.europa.eu/api-v3.yaml (OpenAPI: parametri, polja, ograničenja)

TED objavljuje hiljade objava dnevno, pa se uzima unija dva upita (bez duplikata po broju objave):
  A  pozivi svih vrsta ugovora kojima je mjesto izvršenja ili naručilac u državama iz
     cfg["ted"]["countries"] (zadano: Zapadni Balkan)
  B  pozivi za usluge koje raspisuju EU institucije i međunarodne organizacije (TED vrsta
     naručioca) ili razvojne agencije i banke tražene po imenu (cfg["ted"]["buyer_names"]);
     cfg["ted"]["cpv_divisions"] po želji sužava B na CPV odjele (true = CPV_DIVISIONS),
     cfg["ted"]["strict_eu"] izbacuje državne organe koji se pogrešno vode kao EU institucije

Ispravka objave (corrigendum) je na TED-u nova objava s novim brojem. API s onlyLatestVersions
vraća samo zadnju verziju svake objave, pa objava s pomjerenim rokom zamjenjuje staru; objave
poništene ispravkom (change-reason-code = cancel) se ne uzimaju.
"""
from __future__ import annotations

import datetime as dt
import re
import time

import pycountry

from . import base

META = {
    "key": "TED",
    "name": "TED (EU)",
    "home": "https://ted.europa.eu",
    "scope": "Otvoreni pozivi (rok nije istekao): svi tipovi ugovora za Zapadni Balkan "
             "(mjesto izvršenja ili naručilac) te usluge koje naručuju EU institucije, "
             "međunarodne organizacije i razvojne agencije i banke (GIZ, KfW, EIB, AFD, "
             "Enabel i dr.).",
}

API = "https://api.ted.europa.eu/v3/notices/search"
PAGE = 250       # API: najviše 250 objava po stranici i (broj polja + 1) x limit <= 10 000
PIN_KEEP_DAYS = 120  # najava bez očekivanog datuma poziva ostaje ovoliko dana od objave
MAX_PAGES = 40   # kočnica: najviše 10 000 objava po upitu

COUNTRIES = ["BA", "RS", "ME", "MK", "AL", "XK"]
KOSOVO = ["XKX", "1A0"]  # TED za Kosovo koristi obje šifre (1A0 u starijim objavama)

# Naručioci koji se za upit B traže po imenu (fraza u nazivu naručioca) -> vrsta naručioca.
# "Ime@SE" važi samo za naručioce iz te države: "Sida" je inače i dio drugih naziva.
AGENCIES = {
    "Deutsche Gesellschaft für Internationale Zusammenarbeit": "bilateral",
    "KfW": "bilateral",
    "European Investment Bank": "ifi",
    "Banque européenne d'investissement": "ifi",
    "European Bank for Reconstruction and Development": "ifi",
    "Expertise France": "bilateral",
    "Agence Française de Développement": "bilateral",
    "Enabel": "bilateral",
    "LuxDev": "bilateral",
    "Lux-Development": "bilateral",
    "Austrian Development Agency": "bilateral",
    "Sida@SE": "bilateral",
    "Swedish International Development Cooperation Agency": "bilateral",
}
CPV_DIVISIONS = ["71", "73", "79", "80", "90", "72", "75", "98", "09", "65", "66", "85"]
DIRECTIVES = "32014L0023 32014L0024 32014L0025 32009L0081"  # nabavke država članica (legal-basis)

# TED vrsta naručioca (eForms šifarnik buyer-legal-type) -> (naša vrsta, naziv kako ga daje TED).
# Bez naše vrste ostaju one koje ne odgovaraju jednoznačno nijednoj našoj kategoriji.
LEGAL = {
    "cga": ("central", "Central government authority"),
    "ra": ("regional", "Regional authority"),
    "la": ("local", "Local authority"),
    "rl-aut": (None, "Regional or local authority"),
    "body-pl": ("pubinst", "Body governed by public law"),
    "body-pl-cga": ("pubinst",
                    "Body governed by public law, controlled by a central government authority"),
    "body-pl-ra": ("pubinst", "Body governed by public law, controlled by a regional authority"),
    "body-pl-la": ("pubinst", "Body governed by public law, controlled by a local authority"),
    "pub-undert": ("pubco", "Public undertaking"),
    "pub-undert-cga": ("pubco", "Public undertaking, controlled by a central government authority"),
    "pub-undert-ra": ("pubco", "Public undertaking, controlled by a regional authority"),
    "pub-undert-la": ("pubco", "Public undertaking, controlled by a local authority"),
    "eu-ins-bod-ag": ("eu", "EU institution, body or agency"),
    "int-org": ("intorg", "International organisation"),
    "eu-int-org": ("intorg", "European Institution/Agency or International Organisation"),
    "grp-p-aut": (None, "Group of public authorities"),
    "org-sub": (None, "Organisation awarding a contract subsidised by a contracting authority"),
    "org-sub-cga": (None, "Organisation awarding a contract subsidised by a central government "
                          "authority"),
    "org-sub-ra": (None, "Organisation awarding a contract subsidised by a regional authority"),
    "org-sub-la": (None, "Organisation awarding a contract subsidised by a local authority"),
    "def-cont": (None, "Defence contractor"),
    "spec-rights-entity": (None, "Entity with special or exclusive rights"),
}
NATURE = {"services": base.SERVICES, "supplies": base.GOODS, "works": base.WORKS}
# Vrsta postupka (eForms šifarnik procurement-procedure-type); duži nazivi su skraćeni.
PROCEDURE = {
    "open": "Open",
    "restricted": "Restricted",
    "neg-w-call": "Negotiated with prior call for competition",
    "neg-wo-call": "Negotiated without prior call for competition",
    "comp-dial": "Competitive dialogue",
    "comp-tend": "Competitive tendering",
    "innovation": "Innovation partnership",
    "oth-single": "Other single stage procedure",
    "oth-mult": "Other multiple stage procedure",
    "exp-int-rail": "Request for expression of interest (rail)",
}
# Vrsta objave (podvrsta CEI ili notice-type), za objave koje nemaju vrstu postupka.
NOTICE = {
    "CEI": "Call for expressions of interest",
    "pin-cfc-standard": "Prior information notice used as a call for competition",
    "pin-cfc-social": "Prior information notice used as a call for competition",
    "qu-sy": "Qualification system",
    "cn-desg": "Design contest",
}
DEADLINES = ("tender", "request", "expressions")  # ponude, zahtjevi za učešće, iskazi interesa

FIELDS = [
    "publication-number", "publication-date", "notice-type", "notice-subtype", "title-proc",
    "notice-title", "buyer-name", "buyer-country", "buyer-legal-type",
    *(f"deadline-receipt-{kind}-{part}-lot" for kind in DEADLINES for part in ("date", "time")),
    "deadline-receipt-request",  # zbirni rok (datum i vrijeme); jedini u objavama po staroj šemi
    "contract-nature-main-proc", "contract-nature", "main-classification-proc",
    "classification-cpv", "place-of-performance-country-proc", "place-of-performance-country-lot",
    "place-of-performance-city-proc", "procedure-type",
    "estimated-value-proc", "estimated-value-cur-proc",
    "future-notice",  # kod najave: kad se očekuje poziv
    "description-proc",  # opis postupka, za AI sažetak
]


def _ted_countries(value) -> list[str]:
    """Država iz konfiguracije (ISO2, ISO3 ili engl. ime) -> šifre koje TED koristi u upitu."""
    iso2 = base.country_code(value)
    if iso2 == "XK":
        return KOSOVO
    country = pycountry.countries.get(alpha_2=iso2) if iso2 else None
    if not country:
        raise ValueError(f"TED: nepoznata država u konfiguraciji: {value!r}")
    return [country.alpha_3]


def _names(t: dict) -> list[tuple[str, list[str], str | None]]:
    """cfg buyer_names -> [(fraza, TED šifre države ili [], naša vrsta naručioca ili None)]."""
    out = []
    for entry in t.get("buyer_names") or AGENCIES:
        phrase, _, country = str(entry).partition("@")
        phrase = base.clean(re.sub(r'["\\]', " ", phrase))  # navodnik bi prekinuo frazu u upitu
        if phrase:
            out.append((phrase, _ted_countries(country) if country.strip() else [],
                        AGENCIES.get(entry)))
    return out


def _queries(t: dict, day: str, names: list, since: str | None = None) -> list[str]:
    """Ekspertni upiti A (geografija) i B (institucije); day je 'YYYYMMDD'.
    Sa since ('YYYYMMDD') upiti traže najave (prethodna obavještenja) objavljene od tog dana."""
    # Poziv na nadmetanje (bez dodjela i najava), rok od danas nadalje, objava nije poništena.
    head = (f"form-type = competition AND deadline-receipt-request >= {day}"
            " AND NOT change-reason-code = cancel")
    if since:
        head = f"form-type = planning AND publication-date >= {since} AND NOT change-reason-code = cancel"
    codes = " ".join(dict.fromkeys(
        c for x in t.get("countries") or COUNTRIES for c in _ted_countries(x)))
    geo = " OR ".join(f"{field} IN ({codes})" for field in (
        "place-of-performance-country-proc", "place-of-performance-country-lot", "buyer-country"))

    who = ["buyer-legal-type IN (eu-ins-bod-ag int-org eu-int-org)"]
    if t.get("strict_eu"):
        # Dio državnih organa (npr. slovenska ministarstva) navodi vrstu "EU institucija": ta se
        # vrsta tada priznaje samo uz šifru EU tijela ili pravni osnov koji nije direktiva EU.
        who = ["(buyer-legal-type = eu-ins-bod-ag AND (corporate-body = * OR NOT legal-basis IN"
               f" ({DIRECTIVES})))", "buyer-legal-type IN (int-org eu-int-org)"]
    plain = " ".join(f'"{phrase}"' for phrase, cc, _ in names if not cc)
    if plain:
        who.append(f"buyer-name IN ({plain})")
    who += [f'(buyer-name = "{phrase}" AND buyer-country IN ({" ".join(cc)}))'
            for phrase, cc, _ in names if cc]
    # contract-nature pokriva i staru šemu; glavna vrsta ugovora ne smije biti roba ili radovi.
    b = (f"{head} AND contract-nature = services AND NOT contract-nature-main-proc IN"
         f" (supplies works) AND ({' OR '.join(who)})")
    div = t.get("cpv_divisions")
    if div:
        div = [str(d).zfill(2) for d in (CPV_DIVISIONS if div is True else div)]
        if not all(re.fullmatch(r"\d\d", d) for d in div):
            raise ValueError("TED: cpv_divisions mora biti lista dvocifrenih CPV odjela")
        b += f" AND classification-cpv IN ({' '.join(d + '*' for d in div)})"
    return [f"{head} AND ({geo})", b]


def _search(s, query: str, fields: list | None = None) -> list[dict]:
    """Sve objave za upit, stranicu po stranicu (ITERATION: token vodi na sljedeću stranicu)."""
    body = {"query": query, "fields": fields or FIELDS, "limit": PAGE, "scope": "ALL",
            "paginationMode": "ITERATION",
            "onlyLatestVersions": True}  # samo zadnja verzija svake objave (ispravke, vidi gore)
    out: list[dict] = []
    for _ in range(MAX_PAGES):
        time.sleep(0.6)
        r = base.fetch(s, "POST", API, json=body, ok=(200, 400))
        try:
            j = r.json()
        except ValueError:
            j = None
        if not isinstance(j, dict):
            raise base.SourceChanged("TED API nije vratio JSON objekat")
        if r.status_code == 400:  # nepoznato polje, vrijednost ili sintaksa upita
            raise base.SourceChanged(f"TED API odbija upit: {base.clean(j.get('message'))[:160]}")
        page, total = j.get("notices"), j.get("totalNoticeCount")
        if not isinstance(page, list) or not isinstance(total, int) \
                or not all(isinstance(n, dict) for n in page):
            raise base.SourceChanged("TED API: odgovor nema listu objava i ukupan broj")
        if j.get("timedOut"):
            raise RuntimeError("TED pretraga je istekla prije kraja; rezultat nije potpun")
        out += page
        if len(out) >= total:
            return out
        body["iterationNextToken"] = j.get("iterationNextToken")
        if not page or not body["iterationNextToken"]:
            raise base.SourceChanged(f"TED API je prekinuo listu na {len(out)} od {total} objava")
    raise RuntimeError(f"TED: upit vraća više od {MAX_PAGES * PAGE} objava; suziti konfiguraciju")


def _texts(field) -> list[str]:
    """Višejezično polje {jezik: tekst ili lista tekstova}: engleski, inače prvi jezik."""
    if not isinstance(field, dict) or not field:
        return []
    v = field.get("eng") or next(iter(field.values()))
    return [x for x in map(base.clean, v if isinstance(v, list) else [v]) if x]


def _due(n: dict, today: str) -> tuple[str | None, str | None]:
    """Rok (datum, vrijeme). Rokovi su po lotovima: uzima se najraniji koji nije prošao, inače
    zadnji; rok za ponude ima prednost nad rokom za zahtjeve za učešće i za iskaze interesa."""
    found = []  # (prednost vrste roka, datum, vrijeme)
    for rank, kind in enumerate(DEADLINES):
        dates = n.get(f"deadline-receipt-{kind}-date-lot") or []
        times = n.get(f"deadline-receipt-{kind}-time-lot") or []
        paired = len(times) == len(dates)
        found += [(rank, d, (times[i] or "") if paired else "")
                  for i, d in enumerate(map(base.iso_date, dates)) if d]
    if not found:  # stara šema: samo zbirno polje; ponoć u njemu znači da vrijeme nije navedeno
        found = [(0, d, "" if "T00:00:00" in v else v)
                 for v in n.get("deadline-receipt-request") or [] if (d := base.iso_date(v))]
    if not found:
        return None, None
    live = [f for f in found if f[1] >= today]
    first = min(f[0] for f in found)
    _, date, when = min(live) if live else max(f for f in found if f[0] == first)
    return date, when or None


def _record(n: dict, today: str, names: list, pin: bool = False) -> dict:
    sid = n.get("publication-number")
    buyers = _texts(n.get("buyer-name"))
    due, due_time = (None, None) if pin else _due(n, today)
    if not isinstance(sid, str) or not buyers or not (due or pin):  # upit garantuje rok
        raise base.SourceChanged(
            f"TED objava {sid or '?'} nema broj, naručioca ili rok u očekivanim poljima")

    buyer_cc = n.get("buyer-country") or []
    legal = (n.get("buyer-legal-type") or [None])[0]  # kod više naručilaca: prvi (vodeći)
    btype, btype_raw = LEGAL.get(legal, (None, legal))
    lead = f" {base.norm(buyers[0])} "
    for phrase, cc, kind in names:  # agencije tražene po imenu: naša vrsta ima prednost
        if kind and f" {base.norm(phrase)} " in lead and (not cc or set(buyer_cc[:1]) & set(cc)):
            btype = kind
            break

    nature = n.get("contract-nature-main-proc")
    if not nature:  # stara šema: jedna vrsta u zbirnom polju
        kinds = set(n.get("contract-nature") or [])
        nature = kinds.pop() if len(kinds) == 1 else None
    places = (n.get("place-of-performance-country-proc") or []) + \
             (n.get("place-of-performance-country-lot") or [])
    cities = {base.norm(c): c for c in n.get("place-of-performance-city-proc") or []
              if any(ch.isalpha() for ch in c or "")}  # u polju zna biti samo poštanski broj
    try:
        value = float(n.get("estimated-value-proc") or 0)
    except (TypeError, ValueError):
        value = 0.0

    rec = base.rec(
        META["key"], sid,
        # Čist naslov postupka (isti kao na drugim izvorima, npr. EU F&T); objave po staroj
        # šemi imaju samo TED-ov složeni naslov "Država – CPV – naslov".
        title=(_texts(n.get("title-proc")) or _texts(n.get("notice-title")) or [""])[0],
        buyer=buyers[0] + (f" (+{len(buyers) - 1})" if len(buyers) > 1 else ""),
        url=f"{META['home']}/en/notice/-/detail/{sid}",
        pub=n.get("publication-date"), due=due, due_time=due_time,
        countries=["XK" if c in KOSOVO else c for c in places or buyer_cc],
        place=next(iter(cities.values())) if len(cities) == 1 else None,
        ctype=NATURE.get(nature),
        ntype="Najava (prethodno obavještenje)" if pin else PROCEDURE.get(n.get("procedure-type"))
        or NOTICE.get(n.get("notice-subtype")) or NOTICE.get(n.get("notice-type")),
        cpv=(n.get("main-classification-proc") or []) + (n.get("classification-cpv") or []),
        btype=btype, btype_raw=btype_raw,
        value=value, currency=n.get("estimated-value-cur-proc") if value > 0 else None,
        ref=sid)
    desc = (_texts(n.get("description-proc")) or [""])[0]
    if desc:
        rec["_desc"] = desc[:3000]  # samo za AI sažetak; ne piše se u podatke
    return rec


def _pin_extra(rec: dict, n: dict, today: dt.date) -> dict:
    """Najava: očekivani datum poziva (fn) i do kad se objava drži u listi (keep)."""
    raw = n.get("future-notice") or []
    fn = next((d for d in map(base.iso_date, [raw] if isinstance(raw, str) else raw) if d), None)
    if fn:
        rec["fn"] = fn
    pub = dt.date.fromisoformat(rec["p"]) if rec.get("p") else today
    until = dt.date.fromisoformat(fn) + dt.timedelta(days=30) if fn else pub + dt.timedelta(days=PIN_KEEP_DAYS)
    rec["keep"] = until.isoformat()
    return rec


def collect(cfg: dict) -> list[dict]:
    t = cfg.get("ted", {})
    today = base.today()
    names = _names(t)
    s = base.session()
    out: dict[str, dict] = {}
    for query in _queries(t, today.strftime("%Y%m%d"), names):
        for n in _search(s, query):
            sid = n.get("publication-number")
            if sid in out:
                continue
            try:
                out[sid] = _record(n, today.isoformat(), names)
            except (AttributeError, KeyError, TypeError) as e:
                raise base.SourceChanged(f"TED objava {sid}: neočekivan oblik polja") from e
    if not out:  # TED uvijek ima otvorene pozive EU institucija
        raise base.SourceChanged("TED nije vratio nijednu otvorenu objavu za zadane upite")
    if t.get("pins", True):  # najave (prethodna obavještenja) za iste države i institucije
        since = (today - dt.timedelta(days=PIN_KEEP_DAYS)).strftime("%Y%m%d")
        for query in _queries(t, today.strftime("%Y%m%d"), names, since=since):
            for n in _search(s, query):
                sid = n.get("publication-number")
                if sid in out:
                    continue
                try:
                    rec = _pin_extra(_record(n, today.isoformat(), names, pin=True), n, today)
                except (AttributeError, KeyError, TypeError, ValueError) as e:
                    raise base.SourceChanged(f"TED najava {sid}: neočekivan oblik polja") from e
                if rec["keep"] >= today.isoformat():
                    out[sid] = rec
    return list(out.values())


if __name__ == "__main__":
    base.cli(collect, META)
