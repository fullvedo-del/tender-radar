"""Fond za zaštitu životne sredine i energetsku efikasnost Republike Srpske (Eko fond RS):
javni konkursi za dodjelu sredstava. Konkursi su godišnji i objavljeni na posebnim stranicama
(ćirilica); kolektor ih nalazi preko linkova „Јавни конкурс“ na naslovnoj stranici.
"""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from collectors import base, wp

META = {
    "key": "EKO",
    "name": "Eko fond RS",
    "home": "https://www.ekofondrs.org/ofondu/konkursi.html",
    "scope": "Javni konkursi Fonda za tekuću godinu (zaštita životne sredine, energetska "
             "efikasnost); rok se čita iz teksta konkursa kad je naveden.",
}
HOME = "https://www.ekofondrs.org/"
SKIP_RX = re.compile(r"извјешт|извешт|резултат|ранг|листа|одлук|коначн|izvje[sš]t|rezultat|rang|lista|odluk|kona[cč]n", re.I)


def _page(s, url: str) -> BeautifulSoup:
    r = base.fetch(s, "GET", url)
    r.encoding = "utf-8"  # stranice su u UTF-8, a server to ne kaže uvijek
    return BeautifulSoup(r.text, "lxml")


def collect(cfg: dict) -> list[dict]:
    s = base.session()
    home = _page(s, HOME)
    links = {}
    for a in home.find_all("a", href=True):
        text = base.clean(a.get_text(" "))
        if (re.search(r"јавни\s+конкурс|javni\s+konkurs", text, re.I) and not SKIP_RX.search(text)
                and not a["href"].lower().endswith(".pdf")):
            links.setdefault(urljoin(HOME, a["href"]), text)
    if not links:
        raise base.SourceChanged("Eko fond RS: na naslovnoj stranici nema linkova na javne konkurse.")
    year = base.today().year
    out = []
    for url, label in links.items():
        time.sleep(0.8)
        try:
            soup = _page(s, url)
        except (base.SourceBlocked, RuntimeError):
            continue
        main = soup.find("div", class_=re.compile("item-page")) or soup.find("article") or soup.body
        text = base.clean(main.get_text(" ")) if main else ""
        if not re.search(rf"\b(?:{year}|{year + 1})\b", text):
            continue  # stranica ne govori o konkursu za tekuću godinu
        m = re.search(r"Јавни конкурс за [^.]{10,220}?(?=\s+(?:Ј|J)авни|\s+Р?\s*конкурс|\.|$)", text)
        title = base.clean(m[0]) if m else label
        due = wp.due_from(text, None)
        if due and due < base.today().isoformat():
            continue
        out.append(base.rec(
            META["key"], url.rstrip("/").rsplit("/", 1)[-1][:120], title=title,
            buyer="Fond za zaštitu životne sredine i energetsku efikasnost Republike Srpske",
            url=url, due=due, countries=["BA"], region="Republika Srpska", ctype=base.OTHER,
            ntype="Javni konkurs", btype="pubinst", kind="P"))
    return out


if __name__ == "__main__":
    base.cli(collect, META)
