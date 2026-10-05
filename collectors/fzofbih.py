"""Fond za zaštitu okoliša Federacije BiH (FZOFBiH): javni pozivi i natječaji za dodjelu sredstava,
revolving fond i posebne kategorije otpada. Čita RSS feedove kategorija na fzofbih.org.ba."""
from __future__ import annotations

from collectors import base, wp

META = {
    "key": "FZO",
    "name": "Fond za zaštitu okoliša FBiH",
    "home": "https://fzofbih.org.ba/kategorija/javni-konkursi/",
    "scope": "Otvoreni javni pozivi i natječaji za dodjelu sredstava, revolving fond i posebne "
             "kategorije otpada; bez natječaja za prijem radnika.",
}
FEEDS = [
    "https://fzofbih.org.ba/kategorija/javni-konkursi/feed/",
    "https://fzofbih.org.ba/kategorija/javni-natjecaji-revolving-fond/feed/",
    "https://fzofbih.org.ba/kategorija/javni-natjecaji-posebne-kategorije-otpada/feed/",
]


def collect(cfg: dict) -> list[dict]:
    return wp.calls_from_feeds(base.session(), FEEDS, key=META["key"],
                               buyer="Fond za zaštitu okoliša Federacije BiH",
                               btype="pubinst", region="Federacija BiH")


if __name__ == "__main__":
    base.cli(collect, META)
