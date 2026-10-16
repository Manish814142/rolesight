#!/usr/bin/env python3
"""Candidate job boards from the Internet Archive's URL index, as seed lines for `autopilot discover` (T111).

    python scripts/harvest_board_urls.py --out /tmp/seeds.txt [--hosts lever,ashby] [--companies companies.json]
    autopilot discover --seeds /tmp/seeds.txt --report /tmp/r.csv --out /tmp/v.json --merge companies.json --no-recheck

The archive lists every job-board root page it ever saw (jobs.lever.co/<company>, boards.greenhouse.io/<company>, Workday sites,
...). Each URL is parsed by the project's own `detect_ats`; junk (template placeholders, file names, ids) and boards already in
companies.json are dropped. Output lines are `Name | board URL | exact`: `discover` then checks only that board (no slug guessing on
every other ATS) and names the company from the board where the ATS publishes a name. Workday sites carry `exact` too, so a
tenant's every site is checked (tenant, data centre and site are in the URL) and `discover` keeps the one with most India jobs.

Most boards are dead or have no India job (about 3 in 100 pass `discover`, measured 2026-10-16), so run it on the whole list in
chunks and read the report. Network: the archive and, in `discover`, each board's public job API. No keys.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_hunt.adapters import detect_ats  # noqa: E402
from job_hunt.discovery import ATS_PROBES, _board_ident  # noqa: E402

CDX = "https://web.archive.org/cdx/search/cdx"
TRIES = 3


def _query(name: str, url: str, match: str, regex: str) -> Dict[str, str]:
    return {"name": name, "url": url, "matchType": match, "regex": regex}


# Root pages only (nothing after the company), so each board appears once however many job pages the archive holds.
ARCHIVE_QUERIES: Dict[str, Dict[str, str]] = {q["name"]: q for q in [
    _query("greenhouse", "boards.greenhouse.io", "prefix", r"https?://boards\.greenhouse\.io/[^/?#]+/?$"),
    _query("greenhouse-new", "job-boards.greenhouse.io", "prefix", r"https?://job-boards\.greenhouse\.io/[^/?#]+/?$"),
    _query("lever", "jobs.lever.co", "prefix", r"https?://jobs\.lever\.co/[^/?#]+/?$"),
    _query("ashby", "jobs.ashbyhq.com", "prefix", r"https?://jobs\.ashbyhq\.com/[^/?#]+/?$"),
    _query("smartrecruiters", "jobs.smartrecruiters.com", "prefix", r"https?://jobs\.smartrecruiters\.com/[^/?#]+/?$"),
    _query("smartrecruiters-careers", "careers.smartrecruiters.com", "prefix", r"https?://careers\.smartrecruiters\.com/[^/?#]+/?$"),
    _query("workable", "apply.workable.com", "prefix", r"https?://apply\.workable\.com/[^/?#]+/?$"),
    _query("recruitee", "recruitee.com", "domain", r"https?://[^./]+\.recruitee\.com/?$"),
    _query("personio", "jobs.personio.de", "domain", r"https?://[^./]+\.jobs\.personio\.de/?$"),
    _query("workday", "myworkdayjobs.com", "domain",
           r"https?://[^./]+\.wd[0-9]+\.myworkdayjobs\.com/([a-z]{2}-[A-Za-z]{2}/)?[^/?#]+/?$"),
]}

_SLUG_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,59}$")      # no dot, percent, dollar or star: files and template placeholders
_ID = re.compile(r"^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-")
# Words that are paths of the job sites themselves, not a company's board: fine as a Workday site ("careers", "jobs" are common ones).
_NOT_A_SITE = {"wday", "assets", "static", "login", "api", "en-us", "undefined", "null", "signin", "logout", "oauth", "health", "status", "v1"}
_NOT_A_BOARD = _NOT_A_SITE | {"embed", "jobs", "careers", "career", "api", "static", "assets", "login", "search", "undefined", "null", "company",
                "test", "demo", "example", "www", "app", "apply", "wday", "en-us", "boards", "job", "v1", "oauth", "signin",
                "logout", "health", "status", "widget", "embedded"}
_BOARD_URL = {"greenhouse": "https://boards.greenhouse.io/{}", "lever": "https://jobs.lever.co/{}",
              "ashby": "https://jobs.ashbyhq.com/{}", "smartrecruiters": "https://jobs.smartrecruiters.com/{}",
              "workable": "https://apply.workable.com/{}", "recruitee": "https://{}.recruitee.com",
              "personio": "https://{}.jobs.personio.de"}


def fetch_urls(query: Dict[str, str], session: Any = None) -> List[str]:
    """Root-page URLs the archive saw for one host, only those it archived with HTTP 200."""
    session = session or requests
    params = {"url": query["url"], "matchType": query["matchType"], "collapse": "urlkey", "fl": "original", "output": "text",
              "filter": ["statuscode:200", f"original:{query['regex']}"]}
    for attempt in range(TRIES):
        try:
            resp = session.get(CDX, params=params, timeout=900)
            if resp.status_code == 200:
                return [ln.strip() for ln in resp.text.splitlines() if ln.strip()]
        except requests.RequestException:
            pass
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"the Internet Archive did not answer for {query['name']} after {TRIES} tries")


def pretty(slug: str) -> str:
    """A readable label from a slug: acme-corp -> Acme Corp, ABB stays ABB."""
    return " ".join(w if (w.isupper() and len(w) > 1) else w.capitalize() for w in re.split(r"[-_]+", slug) if w)


def _usable(ats: str, ident: str) -> Optional[Tuple[str, str]]:
    """(ATS, normalised key) for a board worth probing, or None for junk and for an ATS `discover` cannot probe."""
    if ats == "workday":
        tenant, dc, site = ident.split(":")
        ok = (re.fullmatch(r"[a-z0-9-]+", tenant) and re.fullmatch(r"wd\d+", dc) and _SLUG_OK.match(site)
              and site.lower() not in _NOT_A_SITE)
        return (ats, ident.lower()) if ok else None
    if ats not in ATS_PROBES:
        return None
    if not _SLUG_OK.match(ident) or ident.lower() in _NOT_A_BOARD or _ID.match(ident.lower()) or ident.isdigit():
        return None
    return ats, ident.lower()


def board_seeds(urls: List[str], existing: List[Dict[str, Any]]) -> List[str]:
    """`discover` seed lines for the boards in `urls` that are not already in `existing` (companies.json entries)."""
    have = {(c.get("ats", ""), _board_ident(c).lower()) for c in existing}
    found: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for url in urls:
        detected = detect_ats(url) if url.startswith("http") else None
        if not detected:
            continue
        key = _usable(*detected)
        if key is None or key in have:
            continue
        # one board written in two cases is one board; keep the spelling with capitals (a Workday site, a SmartRecruiters id)
        if key not in found or (detected[1] != detected[1].lower() and found[key][1] == found[key][1].lower()):
            found[key] = detected
    lines = []
    for ats, ident in found.values():
        if ats == "workday":
            tenant, dc, site = ident.split(":")
            lines.append(f"{pretty(tenant)} | https://{tenant}.{dc}.myworkdayjobs.com/{site} | exact")   # exact: one seed per site
        else:
            lines.append(f"{pretty(ident)} | {_BOARD_URL[ats].format(ident)} | exact")
    return sorted(lines, key=lambda ln: (ln.split(" | ")[0].lower(), ln))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, help="seed file to write")
    ap.add_argument("--hosts", default=",".join(ARCHIVE_QUERIES), help="comma-separated, default all: " + ", ".join(ARCHIVE_QUERIES))
    ap.add_argument("--companies", default="companies.json", help="boards in this file are skipped (default companies.json)")
    args = ap.parse_args(argv)
    names = [h.strip() for h in args.hosts.split(",") if h.strip()]
    unknown = [h for h in names if h not in ARCHIVE_QUERIES]
    if unknown:
        print(f"unknown host name(s): {', '.join(unknown)}; choose from {', '.join(ARCHIVE_QUERIES)}", file=sys.stderr)
        return 2
    path = Path(args.companies)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    urls: List[str] = []
    for name in names:
        got = fetch_urls(ARCHIVE_QUERIES[name])
        print(f"  {name}: {len(got)} url(s)")
        urls += got
    lines = board_seeds(urls, existing)
    Path(args.out).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"{len(lines)} seed(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
