"""Mreža za izgradnju mira (mreza-mira.net): pozivi za projekte, grantove i programe koje mreža
prenosi za organizacije iz BiH. Sadržaj sajta je pod licencom CC BY-SA 3.0; čuvaju se samo naziv,
datumi i link na objavu. Čita RSS feed kategorije, a rok traži u tekstu same objave."""
from __future__ import annotations

import datetime as dt
import re
import time

from bs4 import BeautifulSoup

from collectors import base, wp

META = {
    "key": "MM",
    "name": "Mreža mira (pozivi za projekte)",
    "home": "https://www.mreza-mira.net/kategorija/vijesti/pozivi-za-projekte/",
    "scope": "Pozivi za projekte, grantove i programe koje Mreža mira prenosi za organizacije iz BiH; "
             "bez info sesija i rezultata.",
}
FEED = "https://www.mreza-mira.net/kategorija/vijesti/pozivi-za-projekte/feed/"
SKIP = re.compile(r"info[ -]?sesij|info[ -]?session|webinar|rezultat|odabran|izabran", re.I)


def collect(cfg: dict) -> list[dict]:
    c = cfg.get("mm", {})
    pages = int(c.get("feed_pages", 3))  # po 10 objava; stariji pozivi mogu biti još otvoreni
    s = base.session()
    items, seen = [], set()
    for page in range(1, pages + 1):
        try:
            batch = wp.feed_items(s, FEED + (f"?paged={page}" if page > 1 else ""))
        except (RuntimeError, base.SourceChanged):
            if page == 1:
                raise
            break
        items += [it for it in batch if it["link"] not in seen and not seen.add(it["link"])]
        if len(batch) < 10:
            break
        time.sleep(0.8)
    if not items:
        raise base.SourceChanged("Mreža mira: feed poziva nema nijednu objavu.")
    today = base.today()
    td, cutoff = today.isoformat(), (today - dt.timedelta(days=60)).isoformat()
    out = []
    for it in items:
        if SKIP.search(it["title"]) or (it["pub"] or "") < (today - dt.timedelta(days=150)).isoformat():
            continue
        text = it["text"]
        try:
            page = BeautifulSoup(base.fetch(s, "GET", it["link"]).text, "lxml")
            body = page.find("article") or page.find("main") or page.body
            text = base.clean(body.get_text(" ")) if body else text
        except (base.SourceBlocked, RuntimeError):
            pass
        time.sleep(0.8)
        due = wp.due_from(text, it["pub"])
        if (due and due < td) or (not due and (it["pub"] or "") < cutoff):
            continue
        out.append(base.rec(
            META["key"], it["link"].rstrip("/").rsplit("/", 1)[-1][:120], title=it["title"],
            buyer="Prenosi Mreža mira", url=it["link"], pub=it["pub"], due=due,
            countries=base.countries_in(it["title"]) or ["BA"], ctype=base.OTHER,
            ntype="Poziv za projekte", btype="other", kind="P"))
    return out


if __name__ == "__main__":
    base.cli(collect, META)
