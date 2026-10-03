"""Expertise France: otvorene nabavke na državnoj platformi PLACE (marches-publics.gouv.fr).

Expertise France sve pozive objavljuje na PLACE. Koristi se javna napredna pretraga (PRADO
forma, bez prijave): entitet „Autres organismes“, jedinica „… EXPERTISE FRANCE“ (sjedište)
uz uključene podjedinice (terenski uredi, tehnički odjeli). Za puni naziv i CPV kodove
otvara se javna stranica svake konsultacije. robots.txt platforme ništa ne zabranjuje.
"""
from __future__ import annotations

import datetime as dt
import gettext
import re
import time

import pycountry
from bs4 import BeautifulSoup

from . import base

META = {
    "key": "EF",
    "name": "Expertise France",
    "home": "https://www.expertisefrance.fr/fr/marches-publics-appels-doffres-expertise-france",
    "scope": "Otvorene nabavke Expertise France (sjedište i sve njegove jedinice) objavljene "
             "na francuskoj državnoj platformi PLACE; svi tipovi ugovora.",
}

HOST = "https://www.marches-publics.gouv.fr/"
SEARCH = HOST + "?page=Entreprise.EntrepriseAdvancedSearch&searchAnnCons"
A = "ctl0$CONTENU_PAGE$AdvancedSearch$"
R = "ctl0$CONTENU_PAGE$resultSearch$"
BUYER = "Expertise France"
CTYPES = {"services": base.SERVICES, "fournitures": base.GOODS, "travaux": base.WORKS}
MONTHS = (("jan", 1), ("fev", 2), ("mar", 3), ("avr", 4), ("mai", 5), ("juin", 6),
          ("juil", 7), ("aou", 8), ("sep", 9), ("oct", 10), ("nov", 11), ("dec", 12))
# Stari ISO nazivi koje PLACE koristi, a kojih nema u francuskim nazivima iz pycountry.
LEGACY = {"centrafricaine republique": "CF", "congo": "CG", "kosovo": "XK",
          "congo la republique democratique du": "CD", "libyenne jamahiriya arabe": "LY",
          "macedoine l ex republique yougoslave de": "MK", "el salvador": "SV",
          "reunion": "RE", "turquie": "TR"}


def _country_names() -> dict:
    fr = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["fr"], fallback=True)
    names = {}
    for c in pycountry.countries:
        for attr in ("name", "official_name", "common_name"):
            if getattr(c, attr, None):
                names[base.norm(fr.gettext(getattr(c, attr)))] = c.alpha_2
    names.update(LEGACY)
    return names


COUNTRIES = _country_names()


def _countries(text: str) -> list[str]:
    """'BRÉSIL, CENTRAFRICAINE, RÉPUBLIQUE, (75) Paris' -> ['BR', 'CF', 'FR'].

    I sami nazivi sadrže zareze, pa se traži najduže poklapanje uzastopnih dijelova."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    out, i = [], 0
    while i < len(parts):
        for k in (3, 2, 1):
            code = COUNTRIES.get(base.norm(" ".join(parts[i:i + k]))) if i + k <= len(parts) else None
            if code:
                break
        else:  # francuski departman „(974) Réunion“, „(75) Paris“
            k, dep = 1, re.match(r"\(\d+[AB]?\)\s*(.*)", parts[i])
            code = (COUNTRIES.get(base.norm(dep[1])) or "FR") if dep else None
        if code and code not in out:
            out.append(code)
        i += k
    return out


def _date(el) -> str | None:
    """Datum iz blokova dan / mjesec / godina, npr. '1' 'Oct.' '2026'."""
    if el is None:
        return None
    d, m, y = (base.clean(x.get_text()) if (x := el.select_one(c)) else ""
               for c in (".day", ".month", ".year"))
    mon = next((n for p, n in MONTHS if base.norm(m).startswith(p)), None)
    try:
        return dt.date(int(y), mon, int(d)).isoformat() if mon else None
    except ValueError:
        return None


def _req(s, method: str, url: str, **kw):
    time.sleep(0.6)  # pristojan razmak prema istom hostu
    return base.fetch(s, method, url, **kw)


def _form(soup) -> dict:
    """Polja PRADO forme onako kako bi ih poslao preglednik."""
    form = soup.find("form", id="ctl0_ctl1")
    if form is None:
        raise base.SourceChanged("PLACE: nije pronađen obrazac pretrage")
    data = {}
    for inp in form.find_all("input"):
        n, t = inp.get("name"), (inp.get("type") or "text").lower()
        box = t in ("checkbox", "radio")
        if n and t not in ("submit", "button", "image", "file") and not inp.has_attr("disabled") \
                and (not box or inp.has_attr("checked")):
            data[n] = inp.get("value", "on" if box else "")
    for sel in form.find_all("select"):
        opt = sel.find("option", selected=True) or sel.find("option")
        if sel.get("name") and opt is not None and not sel.has_attr("disabled"):
            data[sel["name"]] = opt.get("value", "")
    return data


def _detail(s, url: str) -> tuple[dict, list[str]]:
    """Polja 'Oznaka : vrijednost' i CPV kodovi sa stranice konsultacije."""
    soup = BeautifulSoup(_req(s, "GET", url).text, "lxml")
    fields = {}
    for lab in soup.find_all("label"):
        val = lab.find_next_sibling(["span", "div"])
        key = base.clean(lab.get_text()).rstrip(" :")
        if key and val is not None:
            fields.setdefault(key, base.clean(val.get_text(" ")))
    return fields, [x["data-code-cpv"] for x in soup.select("[data-code-cpv]") if x["data-code-cpv"]]


def _search(s, c: dict) -> tuple[str, list]:
    """Pretraga po jedinici Expertise France; vraća akronim entiteta i redove rezultata."""
    soup = BeautifulSoup(_req(s, "GET", SEARCH).text, "lxml")
    data = _form(soup)
    org = next((o["value"] for o in soup.select(f"select[name='{A}organismesNames'] option")
                if base.clean(o.get_text()).startswith("Autres organismes")), None)
    if not org:
        raise base.SourceChanged("PLACE: u listi nema entiteta „Autres organismes“")
    data[A + "organismesNames"] = org
    # PRADO callback puni listu jedinica izabranog entiteta i vraća novo stanje stranice.
    r = _req(s, "POST", SEARCH, data=dict(data, PRADO_CALLBACK_TARGET=A + "organismesNames",
                                          PRADO_CALLBACK_PARAMETER="null"))
    state = re.search(r"<!--X-PRADO-PAGESTATE-->(.*?)<!--//X-PRADO-PAGESTATE-->", r.text, re.S)
    units = [(o["value"], o.get_text()) for o in BeautifulSoup(r.text, "lxml").select(
        f"select[name='{A}entityPurchaseNames'] option") if "EXPERTISE FRANCE" in o.get_text().upper()]
    if not state or not units:
        raise base.SourceChanged("PLACE: nije pronađena jedinica Expertise France")
    today, fmt = base.today(), (lambda d: d.strftime("%d/%m/%Y"))
    data.update({
        "PRADO_PAGESTATE": state[1],
        A + "type_rechercheEntite": "exact",  # izbor jedinice iz liste
        A + "entityPurchaseNames": min(units, key=lambda u: u[1].count("/"))[0],  # sjedište
        A + "choixInclusionDescendancesServices": A + "inclureDescendances",
        A + "dateMiseEnLigneStart": fmt(today),  # rok za ponude: od danas ...
        A + "dateMiseEnLigneEnd": fmt(today + dt.timedelta(days=c.get("due_days", 1825))),
        A + "dateMiseEnLigneCalculeStart": fmt(today - dt.timedelta(days=c.get("pub_days", 1095))),
        A + "dateMiseEnLigneCalculeEnd": fmt(today),  # ... objavljeno do danas
        "PRADO_POSTBACK_TARGET": A + "lancerRecherche", A + "lancerRecherche": "Lancer la recherche",
    })
    data.pop(A + "inclureConsultationExterieur", None)  # samo konsultacije sa PLACE
    soup = BeautifulSoup(_req(s, "POST", SEARCH, data=data).text, "lxml")
    if soup.select_one("#ctl0_CONTENU_PAGE_resultSearch_panelNoElementFound"):
        return org, []
    count = soup.select_one("#ctl0_CONTENU_PAGE_resultSearch_nombreElement")
    pages = soup.select_one("#ctl0_CONTENU_PAGE_resultSearch_nombrePageTop")
    if count is None or pages is None:
        raise base.SourceChanged("PLACE: nema liste rezultata ni poruke da rezultata nema")
    last = min(int(re.sub(r"\D", "", pages.get_text()) or 1), c.get("max_pages", 15))
    rows = soup.select("div.item_consultation")
    for page in range(2, last + 1):  # PRADO postback „idi na stranicu N“
        data = dict(_form(soup), PRADO_POSTBACK_TARGET=R + "DefaultButtonTop")
        data[R + "numPageTop"] = str(page)
        soup = BeautifulSoup(_req(s, "POST", SEARCH, data=data).text, "lxml")
        rows += soup.select("div.item_consultation")
    if not rows and base.clean(count.get_text()) != "0":
        raise base.SourceChanged("PLACE: ima rezultata, ali nijedan red nije prepoznat")
    return org, rows


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("ef", {})
    s = base.session()
    org, rows = _search(s, c)
    today = base.today().isoformat()
    left = c.get("max_details", 100) if c.get("details", True) else 0
    out = []
    for row in rows:
        cid, rorg = (row.select_one(f"input[name$='${n}']") for n in ("refCons", "orgCons"))
        if cid is None or rorg is None:
            raise base.SourceChanged("PLACE: red rezultata bez identifikatora konsultacije")
        if rorg["value"] != org:
            raise base.SourceChanged("PLACE: filter po naručiocu nije primijenjen")
        url = f"{HOST}app.php/entreprise/consultation/{cid['value']}?orgAcronyme={org}"
        due = _date(row.select_one(".cons_dateEnd .date"))
        if due and due < today:
            continue
        ref, title = (base.clean(x.get_text(" ")) if (x := row.select_one(sel)) else None
                      for sel in (".objet-line .small.pull-left", ".objet-line .truncate"))
        cpv = []
        if left > 0:
            left -= 1
            fields, cpv = _detail(s, url)
            unit = fields.get("Entité d'Achat", "").upper()
            if unit and "EF-SIEGE" not in unit and "EXPERTISE FRANCE" not in unit:
                continue  # zaštita: nije jedinica Expertise France
            title = fields.get("Intitulé") or title
        proc, cat, when = (row.select_one(sel) for sel in (
            ".cons_procedure abbr", ".cons_categorie", ".cons_dateEnd .time"))
        places = row.select_one(".lieux-exe [data-content]") or row.select_one(".lieux-exe")
        out.append(base.rec(
            META["key"], cid["value"], title=title, buyer=BUYER, url=url,
            pub=_date(row.select_one(".cons_ref .date")), due=due,
            due_time=base.clean(when.get_text()) if when else None,
            countries=_countries(places.get("data-content") or places.get_text(" ")) if places else [],
            ctype=CTYPES.get(base.norm(cat.get_text())) if cat else None,
            ntype=proc.get("title") if proc else None, cpv=cpv, btype="bilateral", ref=ref))
    return out


if __name__ == "__main__":
    base.cli(collect, META)
