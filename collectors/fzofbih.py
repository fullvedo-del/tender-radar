"""Fond za zaštitu okoliša Federacije BiH (FZOFBiH): javni pozivi i konkursi za dodjelu sredstava,
revolving fond i posebne kategorije otpada.

Čita stranice kategorija na fzofbih.org.ba (njihovi RSS feedovi kategorija vraćaju grešku 502),
a rok traži u tekstu same objave.
"""
from __future__ import annotations

import datetime as dt
import re
import time

from bs4 import BeautifulSoup

from collectors import base, wp

META = {
    "key": "FZO",
    "name": "Fond za zaštitu okoliša FBiH",
    "home": "https://fzofbih.org.ba/kategorija/javni-konkursi/",
    "scope": "Otvoreni javni pozivi i konkursi za dodjelu sredstava, revolving fond i posebne "
             "kategorije otpada; bez natječaja za prijem radnika.",
}
PAGES = [
    "https://fzofbih.org.ba/kategorija/javni-konkursi/",
    "https://fzofbih.org.ba/",  # naslovna: tu su i obavijesti o zatvaranju poziva
    "https://fzofbih.org.ba/kategorija/javni-natjecaji-revolving-fond/",
    "https://fzofbih.org.ba/kategorija/javni-natjecaji-posebne-kategorije-otpada/",
]
POST_RX = re.compile(r"https://fzofbih\.org\.ba/(\d{4})/(\d{2})/(\d{2})/([^/?#]+)/?$")
# Fond poziv "privremeno zatvori" posebnom obaviješću kad se sredstva rezervišu.
CLOSE_RX = re.compile(r"zatvaranj|zatvoren|obustav|poni[sš]t", re.I)
STOP = {"javni", "javnog", "poziva", "konkurs", "konkursa", "dodjelu", "dodjele", "sredstava", "godinu",
        "godine", "privremeno", "zatvaranje", "realizaciju", "provodjenje", "provedbu", "objavljen"}


def _words(text: str) -> set[str]:
    return {w for w in base.norm(text).split() if len(w) >= 6 and w not in STOP}


def collect(cfg: dict) -> list[dict]:
    s = base.session()
    posts: dict[str, dict] = {}
    for url in PAGES:
        try:
            soup = BeautifulSoup(base.fetch(s, "GET", url).text, "lxml")
        except (base.SourceBlocked, RuntimeError):
            if url == PAGES[0]:
                raise
            continue  # sporedna kategorija povremeno vraća grešku; glavna je dovoljna
        for a in soup.find_all("a", href=True):
            m = POST_RX.match(a["href"])
            if not m:
                continue
            title = base.clean(a.get_text(" ")) or base.clean(a.get("title"))
            old = posts.get(a["href"])
            if not old or len(title) > len(old["title"]):
                posts[a["href"]] = {"title": title, "pub": f"{m[1]}-{m[2]}-{m[3]}", "slug": m[4]}
        time.sleep(0.8)
    if not posts:
        raise base.SourceChanged("FZOFBiH: stranice kategorija nemaju nijednu objavu.")
    today = base.today()
    td, cutoff = today.isoformat(), (today - dt.timedelta(days=60)).isoformat()
    oldest = (today - dt.timedelta(days=200)).isoformat()
    closed = [(p["pub"], _words(p["title"] + " " + p["slug"].replace("-", " ")))
              for p in posts.values() if CLOSE_RX.search(p["title"] + " " + p["slug"])]
    out = []
    for link, p in posts.items():
        title = p["title"]
        if p["pub"] < oldest or not wp.CALL_RX.search(title) or wp.SKIP_RX.search(title):
            continue
        mine = _words(title)
        if any(when >= p["pub"] and len(mine & words) >= 2 for when, words in closed):
            continue  # poziv je (privremeno) zatvoren
        due = None
        try:
            page = BeautifulSoup(base.fetch(s, "GET", link).text, "lxml")
            body = page.find("article") or page.find("main") or page.body
            due = wp.due_from(base.clean(body.get_text(" ")) if body else "", p["pub"])
        except (base.SourceBlocked, RuntimeError):
            pass
        time.sleep(0.8)
        if (due and due < td) or (not due and p["pub"] < cutoff):
            continue
        out.append(base.rec(
            META["key"], p["slug"][:120], title=title, buyer="Fond za zaštitu okoliša Federacije BiH",
            url=link, pub=p["pub"], due=due, countries=["BA"], region="Federacija BiH",
            ctype=base.OTHER, ntype="Javni poziv", btype="pubinst", kind="P"))
    return out


if __name__ == "__main__":
    base.cli(collect, META)
