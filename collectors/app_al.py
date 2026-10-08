"""Albanija: Agjencia e Prokurimit Publik (APP), javna lista objavljenih tendera
„Njoftimi i kontratës së shpallur“ (www.app.gov.al/njoftimi-i-kontratës-së-shpallur/).

Lista je javna i bez prijave. robots.txt zabranjuje samo putanje /GetData/ (preuzimanje
dokumenata i CSV izvoz), koje ovaj kolektor ne koristi (provjereno 8.10.2026.). API ne
postoji: stranica se lista POST formama same stranice (pretraga po datumu objave, pa dugmad za
stranice; 10 objava po stranici, najnovije prve). Podaci su u bloku na listi i u prozoru
„Më shumë Info“ na istoj stranici.

Prvo osvježavanje čita sve objave iz zadnjih `days` dana (oko 130 stranica). Poslije se
čitaju samo nove stranice, dok se ne naiđe na stranicu bez novih objava, a otvorene objave se
pamte u cfg["_state"] (data/state.json). Poništenje ili obustava starije objave vidi se samo
dok je objava na stranicama koje se ponovo čitaju.
"""
from __future__ import annotations

import datetime as dt
import re
import time

from bs4 import BeautifulSoup

from collectors import base

META = {
    "key": "APP",
    "name": "APP Albanija",
    "home": "https://www.app.gov.al/njoftimi-i-kontrat%C3%ABs-s%C3%AB-shpallur/",
    "scope": "Objavljeni tenderi u Albaniji kojima rok nije prošao, bez poništenih i obustavljenih; "
             "naslovi su na albanskom.",
}
URL = META["home"]
KIND = {"Shërbime": base.SERVICES, "Mallra": base.GOODS, "Punë": base.WORKS}
PROCEDURE = {
    "E hapur": "Otvoreni postupak",
    "E hapur, mbi kufirin e lartë monetar": "Otvoreni postupak (iznad visokog praga)",
    "E hapur, e thjeshtuar": "Pojednostavljeni otvoreni postupak",
    "E kufizuar": "Ograničeni postupak",
    "Kërkesë për propozim": "Zahtjev za prijedloge",
}
# Postupci koji nisu otvoreni za sve: dinamična kupovina avionskih karata i pregovori bez objave.
CLOSED = ("biletave", "pa shpallje")
PAUSE = 0.5
PAGES_RX = re.compile(r"<span>Faqe</span>\s*(\d+)\s*<span>nga</span>\s*(\d+)")


def _inputs(form) -> dict:
    return {i.get("name"): i.get("value") or "" for i in form.find_all("input") if i.get("name")}


def _pairs(node, sep=":") -> dict:
    """Oznaka -> vrijednost iz bloka na listi (b + span) ili iz prozora (dvije kolone)."""
    out = {}
    for li in node.select("ul.list-inline > li"):
        b = li.find("b")
        if b:
            vals = [x.get_text(" ", strip=True) for x in li.find_all(["span", "i", "small"])
                    if x.find("b") is None and x.get_text(strip=True)]
            out[b.get_text(" ", strip=True).rstrip(sep).strip()] = vals
    return out


def _modal(page, cn: str) -> dict:
    out = {}
    box = page.find(id=f"mainData_{cn}")
    if box is None:
        return out
    for li in box.select("li.list-group-item"):
        cols = li.select("div.row > div")
        if len(cols) >= 2:
            out[cols[0].get_text(" ", strip=True).rstrip(":").strip()] = cols[1].get_text(" ", strip=True)
    return out


def _value(text: str):
    m = re.search(r"([\d.,]+)", text or "")
    if not m:
        return None, None
    try:
        v = float(m[1].replace(",", ""))
    except ValueError:
        return None, None
    return v, ("ALL" if "lek" in (text or "").lower() else None)


def _parse(html: str) -> list[dict]:
    page = BeautifulSoup(html, "lxml")
    items = page.select("div.list-group-item.list-group-item-result")
    out = []
    for it in items:
        a = it.select_one('a[href^="#myModal_CN-"]')
        if a is None:
            raise base.SourceChanged("APP: objava na listi nema link na detalje (myModal_CN-)")
        cn = a["href"][len("#myModal_"):]
        lst, mod = _pairs(it), _modal(page, cn)
        if not mod.get("Objekti i tenderit") or "Data e mbylljes" not in lst:
            raise base.SourceChanged("APP: objava nema naziv ili rok na očekivanom mjestu")
        close = lst["Data e mbylljes"]
        m = re.search(r"/(\d{2})(\d{2})(\d{4})$", mod.get("Numri i Njoftimit", ""))  # CN/77656/10082026
        pub = base._mk(int(m[3]), int(m[1]), int(m[2])) if m else None
        v, cur = _value(" ".join(lst.get("Fondi limit", [])))
        out.append({
            "cn": cn,
            "ref": mod.get("Numri i referencës") or " ".join(lst.get("Numri i referencës", [])),
            "t": mod["Objekti i tenderit"],
            "b": mod.get("Autoriteti kontraktues", ""),
            "proc": mod.get("Proçedura", ""),
            "k": KIND.get(mod.get("Tipi i kontratës", "")),
            "cpv": [c for c in re.findall(r"\b\d{8}\b", mod.get("Kodi CPV", ""))],
            "open": base.iso_date(lst.get("Data e hapjes", [""])[0]),
            "p": pub,
            "d": base.iso_date(close[0]) if close else None,
            "dt": base.iso_time(close[1]) if len(close) > 1 else None,
            "v": v, "cur": cur,
            "off": any(" ".join(lst.get(k, [])).strip().lower().startswith("po")
                       for k in ("Anulluar", "Pezulluar")),
        })
    return out


def _next(html: str, n: int):
    for form in BeautifulSoup(html, "lxml").find_all("form"):
        if [b.get_text(strip=True) for b in form.find_all("button")] == [str(n)]:
            return _inputs(form)
    return None


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("app", {})
    days = int(c.get("days", 40))            # koliko dana unazad gledati datume objave
    first_pages = int(c.get("first_pages", 160))  # najviše stranica u prvom osvježavanju
    daily_pages = int(c.get("daily_pages", 30))   # najviše stranica poslije toga
    state = cfg.get("_state")
    if not isinstance(state, dict):
        state = {}
    full = not isinstance(state.get("open"), dict) or not isinstance(state.get("seen"), dict)
    opened = {} if full else dict(state["open"])
    seen = {} if full else dict(state["seen"])

    today = base.today()
    s = base.session()
    page = BeautifulSoup(base.fetch(s, "GET", URL).text, "lxml")
    form = next((f for f in page.find_all("form") if f.find("input", {"name": "DateFrom"})), None)
    if form is None:
        raise base.SourceChanged("APP: nema forme za pretragu po datumu objave")
    data = _inputs(form)
    data.update(DateFrom=(today - dt.timedelta(days=days)).strftime("%d.%m.%Y"), DateTo="30.12.9999", CPV="")
    time.sleep(PAUSE)
    html = base.fetch(s, "POST", URL, data=data).text
    m = PAGES_RX.search(html)
    if not m:
        raise base.SourceChanged("APP: lista nema oznaku broja stranica (Faqe N nga M)")
    total = int(m[2])
    limit = first_pages if full else daily_pages

    n = 1
    while True:
        rows = _parse(html)
        if not rows and total:
            raise base.SourceChanged("APP: stranica liste nema nijednu objavu")
        new = 0
        for r in rows:
            new += r["cn"] not in seen
            seen[r["cn"]] = r["open"] or r["p"] or today.isoformat()
            key = r["ref"] or r["cn"]
            if r["off"] or any(x in r["proc"].lower() for x in CLOSED):
                opened.pop(key, None)
                continue
            old = opened.get(key)
            if old is None or (r["p"] or "") >= (old.get("p") or ""):
                opened[key] = {k: v for k, v in r.items() if k not in ("off", "open") and v not in (None, "", [])}
        if n >= total or n >= limit or (not full and n >= 2 and new == 0):
            break
        nxt = _next(html, n + 1)
        if nxt is None:
            raise base.SourceChanged(f"APP: nema dugmeta za stranicu {n + 1}")
        time.sleep(PAUSE)
        html = base.fetch(s, "POST", URL, data=nxt).text
        n += 1

    since = (today - dt.timedelta(days=days + 5)).isoformat()
    state["seen"] = {k: v for k, v in seen.items() if v >= since}
    state["open"] = {k: v for k, v in opened.items() if (v.get("d") or "") >= today.isoformat()}
    cfg["_state"] = state

    out = []
    for key, r in state["open"].items():
        out.append(base.rec(
            META["key"], key,
            title=r["t"], buyer=r.get("b", ""), url=URL,
            pub=r.get("p"), due=r.get("d"), due_time=r.get("dt"),
            countries=["AL"], ctype=r.get("k"),
            ntype=PROCEDURE.get(r.get("proc", ""), r.get("proc")),
            cpv=r.get("cpv"), value=r.get("v"), currency=r.get("cur"),
            ref=r.get("ref") if r.get("ref") != key else None,
        ))
    return out


if __name__ == "__main__":
    base.cli(collect, META)
