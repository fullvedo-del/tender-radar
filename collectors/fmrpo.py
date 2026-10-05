"""Federalno ministarstvo razvoja, poduzetništva i obrta (FMRPO): javni pozivi i konkursi
(poticaji i grantovi za firme, obrte i udruženja). Čita RSS feed kategorije na fmrpo.gov.ba."""
from __future__ import annotations

from collectors import base, wp

META = {
    "key": "FMRPO",
    "name": "FMRPO (Federalno ministarstvo razvoja, poduzetništva i obrta)",
    "home": "https://fmrpo.gov.ba/category/javni-natjecajikonkursi/",
    "scope": "Otvoreni javni pozivi i konkursi ministarstva (poticaji i grantovi); bez rang-lista, "
             "rezultata i odluka.",
}
FEEDS = ["https://fmrpo.gov.ba/category/javni-natjecajikonkursi/feed/"]


def collect(cfg: dict) -> list[dict]:
    return wp.calls_from_feeds(base.session(), FEEDS, key=META["key"],
                               buyer="Federalno ministarstvo razvoja, poduzetništva i obrta",
                               btype="regional", region="Federacija BiH")


if __name__ == "__main__":
    base.cli(collect, META)
