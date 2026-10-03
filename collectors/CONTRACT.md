# Collector contract (read fully before writing code)

Project: a daily index of **public procurement notices** for a consultancy in Sarajevo
(environment, energy, climate). It runs once a day on GitHub Actions (ubuntu, Python 3.12)
and publishes a static page. We store only basic notice metadata plus a link to the
original notice. No tender documents, no logins.

## Interface

- One file per source: `collectors/<name>.py`. Do **not** edit `base.py`, `CONTRACT.md`
  or other collectors. If you need a helper, keep it inside your module and mention it in
  your report.
- `META = {"key": "...", "name": "...", "home": "https://...", "scope": "..."}`
  - `key`: given in your task. `name`: short display name.
  - `scope`: ONE sentence in Bosnian (ijekavica) saying which subset of the source is
    collected, e.g. "Sve otvorene objave; svi tipovi ugovora."
- `def collect(cfg: dict) -> list[dict]` returning records built **only** with
  `base.rec(...)` (see its docstring for every field).
- Tunables: read them from `cfg.get("<key lowercase>", {})` with sensible defaults in
  code, so `collect({})` works.
- Last lines: `if __name__ == "__main__": base.cli(collect, META)`.
- Test with: `cd /home/claude/tender-radar && python3 -m collectors.<name>`

## What to collect

- Only **currently open calls**: invitations to tender / to submit proposals / requests
  for expression of interest / prequalification, with submission deadline >= today.
  If a notice has no deadline, include it only when published within the last 60 days.
- Exclude contract award notices, cancellations, procurement plans, and vacancies/jobs
  for individual staff positions (individual consultant assignments ARE wanted).
- Required per record: title, buyer (contracting authority), url, publication date and
  deadline whenever the source provides them. Fill as many optional fields as the source
  really gives (country, contract type, CPV, buyer type, notice/procedure type, value,
  reference). Never guess a value: leave the field out instead.
- `url` must be a public page a human can open for that notice (not an API endpoint),
  or the listing page if the source has no per-notice page.
- Dates: keep them as the source writes them (no timezone conversion).
- `sid` must be stable across days (publication number, reference, numeric id).

## Hard rules

1. Dependencies: `requests`, `beautifulsoup4`, `lxml`, `pycountry`, stdlib. Nothing else.
   No headless browser.
2. All HTTP through `base.session()` + `base.fetch()` (honest User-Agent, retries).
3. Be polite: sleep >= 0.5 s between requests to the same host, aim for <= 150 requests
   and < 4 minutes per run.
4. **Do not circumvent access controls.** If the source answers 401/403, shows a captcha
   or JS challenge, or needs a login, do not fake a browser User-Agent, do not replay
   browser cookies or tokens, do not use other tricks. Stop and report it as blocked.
5. For scraped HTML sources (no documented public API): read `robots.txt` and look for
   the site's terms of use. If robots.txt disallows the path for all agents, or the terms
   explicitly prohibit automated collection/scraping, **do not implement** the collector:
   report with the exact quote and URL. A documented public API/open-data endpoint is fine.
6. If the response structure is not what the code expects (missing table, missing JSON
   key, zero rows where rows are certain), `raise base.SourceChanged("...")` with a short
   Bosnian message. Never return `[]` silently for a broken parse. Returning `[]` is right
   only when the source clearly says there are no open notices.
7. Exception messages are shown to the end user: short, in Bosnian, no stack traces.
8. Keep the code compact and readable; brief comments; no dead code, no debug prints.

## Final report (your last message, max ~250 words, plain text)

- STATUS: OK / PARTIAL / NOT IMPLEMENTED (+ reason)
- Endpoint(s) used and whether documented/public
- robots.txt + terms finding (quote + URL) for scraped sources
- Volume (records), HTTP requests per run, runtime
- Field coverage (paste the percentages printed by `base.cli`)
- cfg keys you support
- Caveats / known limits / anything fragile
