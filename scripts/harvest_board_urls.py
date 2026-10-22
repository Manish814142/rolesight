#!/usr/bin/env python3
"""Candidate job boards from the Internet Archive's URL index, as seed lines for `autopilot discover` (T111).

    python scripts/harvest_board_urls.py --out /tmp/seeds.txt [--hosts lever,ashby] [--companies companies.json]
    autopilot discover --seeds /tmp/seeds.txt --report /tmp/r.csv --out /tmp/v.json --merge companies.json --no-recheck

The archive lists every job-board root page it ever saw (jobs.lever.co/<company>, boards.greenhouse.io/<company>, Workday sites,
...). Each URL is parsed by the project's own `detect_ats`; junk (template placeholders, file names, ids) and boards already in
companies.json are dropped. Output lines are `Name | board URL | exact`: `discover` then checks only that board (no slug guessing on
every other ATS) and names the company from the board where the ATS publishes a name. Workday sites carry `exact` too, so a
tenant's every site is checked (tenant, data centre and site are in the URL) and `discover` keeps the one with most India jobs.

Lever, SmartRecruiters and Workday run as smaller queries (by first letter, by data centre), because the archive times out on
the whole host; a chunk that does not answer is named and the others are kept (T144).

Most boards are dead or have no India job (about 3 in 100 pass `discover`, measured 2026-10-16), so run it on the whole list in
chunks and read the report. Network: the archive and, in `discover`, each board's public job API. No keys.
"""
import argparse
import html
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_hunt.adapters import detect_ats  # noqa: E402
from job_hunt.discovery import ATS_PROBES, _board_ident  # noqa: E402

CDX = "https://web.archive.org/cdx/search/cdx"
TRIES = 4


def _query(name: str, url: str, match: str, regex: str, split: Optional[List[str]] = None) -> Dict[str, Any]:
    """`split`: smaller queries (their `url`s) that together are this one. The archive times out on a big host (Lever, Workday,
    SmartRecruiters failed three times in a row on 2026-10-21, T144), and one that fails then costs a chunk, not the host."""
    return {"name": name, "url": url, "matchType": match, "regex": regex, "split": split}


_FIRST_CHARS = "0123456789abcdefghijklmnopqrstuvwxyz"            # a board name starts with one of these (the archive keys lower-case)
# Workday data centres: the 14 on the list on 2026-10-21 (wd1 ... wd504) and the numbers around them that exist or may.
_WORKDAY_DCS = [f"wd{n}" for n in (*range(1, 13), 25, *range(100, 131), *range(500, 511))]


_ORACLE_SITE = r"https?://[^/]+\.oraclecloud\.com/hcmUI/CandidateExperience/[^/]+/sites/[^/?#]+/?$"

# Root pages only (nothing after the company), so each board appears once however many job pages the archive holds.
ARCHIVE_QUERIES: Dict[str, Dict[str, Any]] = {q["name"]: q for q in [
    _query("greenhouse", "boards.greenhouse.io", "prefix", r"https?://boards\.greenhouse\.io/[^/?#]+/?$"),
    _query("greenhouse-new", "job-boards.greenhouse.io", "prefix", r"https?://job-boards\.greenhouse\.io/[^/?#]+/?$"),
    _query("lever", "jobs.lever.co", "prefix", r"https?://jobs\.lever\.co/[^/?#]+/?$",
           split=[f"jobs.lever.co/{c}" for c in _FIRST_CHARS]),
    _query("ashby", "jobs.ashbyhq.com", "prefix", r"https?://jobs\.ashbyhq\.com/[^/?#]+/?$"),
    _query("smartrecruiters", "jobs.smartrecruiters.com", "prefix", r"https?://jobs\.smartrecruiters\.com/[^/?#]+/?$",
           split=[f"jobs.smartrecruiters.com/{c}" for c in _FIRST_CHARS]),
    _query("smartrecruiters-careers", "careers.smartrecruiters.com", "prefix", r"https?://careers\.smartrecruiters\.com/[^/?#]+/?$"),
    _query("workable", "apply.workable.com", "prefix", r"https?://apply\.workable\.com/[^/?#]+/?$"),
    _query("recruitee", "recruitee.com", "domain", r"https?://[^./]+\.recruitee\.com/?$"),
    _query("personio", "jobs.personio.de", "domain", r"https?://[^./]+\.jobs\.personio\.de/?$"),
    _query("workday", "myworkdayjobs.com", "domain",
           r"https?://[^./]+\.wd[0-9]+\.myworkdayjobs\.com/([a-z]{2}-[A-Za-z]{2}/)?[^/?#]+/?$",
           split=[f"{dc}.myworkdayjobs.com" for dc in _WORKDAY_DCS]),
    # Oracle HCM (T112): one query per data centre, because the whole oraclecloud.com domain times out. The host is a customer
    # code (`cbcz.fa.us2.oraclecloud.com`); the employer's name comes from the site's page title (fetch_site_names).
    *[_query(f"oracle-{pod}", f"fa.{pod}.oraclecloud.com", "domain", _ORACLE_SITE)
      for pod in ("us2", "us6", "em2", "em3", "em4", "em5", "em8", "ap1", "ap2", "ap3", "sa1", "ocs")],
    _query("oracle-fa", "fa.oraclecloud.com", "domain", _ORACLE_SITE),
]}

_SLUG_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,59}$")      # no dot, percent, dollar or star: files and template placeholders
_ID = re.compile(r"^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-")
# Words that are paths of the job sites themselves, not a company's board: fine as a Workday site ("careers", "jobs" are common ones).
_NOT_A_SITE = {"wday", "assets", "static", "login", "api", "en-us", "undefined", "null", "signin", "logout", "oauth", "health", "status", "v1"}
_NOT_A_BOARD = _NOT_A_SITE | {"embed", "jobs", "careers", "career", "api", "static", "assets", "login", "search", "undefined", "null", "company",
                "test", "demo", "example", "www", "app", "apply", "wday", "en-us", "boards", "job", "v1", "oauth", "signin",
                "logout", "health", "status", "widget", "embedded"}
# A customer's test, development or staging instance is a copy of its production site under another host (`...-dev12`, `...-test-saasfaprod1`).
_TEST_INSTANCE = re.compile(r"(^|-)(dev|test|stage|stg|uat|sandbox|demo|train|training|preprod|pre-prod|poc|sit|qa)\d*(-|$)", re.IGNORECASE)
_BOARD_URL = {"greenhouse": "https://boards.greenhouse.io/{}", "lever": "https://jobs.lever.co/{}",
              "ashby": "https://jobs.ashbyhq.com/{}", "smartrecruiters": "https://jobs.smartrecruiters.com/{}",
              "workable": "https://apply.workable.com/{}", "recruitee": "https://{}.recruitee.com",
              "personio": "https://{}.jobs.personio.de"}


class ArchiveError(RuntimeError):
    """The archive did not answer; `urls` is what the chunks that did answer returned."""

    def __init__(self, message: str, urls: Optional[List[str]] = None):
        super().__init__(message)
        self.urls = urls or []


YEARS = list(range(2014, 2027))       # a chunk that still fails is asked again one year of captures at a time, then by half, quarter, month
FIRST_YEAR = YEARS[0]


def _month(i: int) -> str:
    """Month number i counted from January of FIRST_YEAR, as the archive writes a date: 0 -> '201401'."""
    year, month = divmod(i, 12)
    return f"{FIRST_YEAR + year}{month + 1:02d}"


def _fetch_one(query: Dict[str, Any], session: Any, tries: int = TRIES) -> List[str]:
    params = {"url": query["url"], "matchType": query["matchType"], "collapse": "urlkey", "fl": "original", "output": "text",
              "filter": ["statuscode:200", f"original:{query['regex']}"]}
    if query.get("from"):
        params["from"], params["to"] = query["from"], query["to"]
    for attempt in range(tries):
        try:
            resp = session.get(CDX, params=params, timeout=900)
            if resp.status_code == 200:
                return [ln.strip() for ln in resp.text.splitlines() if ln.strip()]
        except requests.RequestException:
            pass
        time.sleep(5 * (attempt + 1))
    raise ArchiveError(f"the Internet Archive did not answer for {query['name']} after {tries} tries")


def _fetch_span(query: Dict[str, Any], lo: int, hi: int, session: Any, got: List[str]) -> bool:
    """URLs captured in months lo..hi (counted from FIRST_YEAR) into `got`; a span the archive will not answer is split in two,
    down to one month. False when a month still fails (the rest of the span is kept)."""
    try:
        got += _fetch_one({**query, "from": _month(lo), "to": _month(hi)}, session, tries=2)
        return True
    except ArchiveError:
        if lo == hi:
            return False
        mid = (lo + hi) // 2
        first = _fetch_span(query, lo, mid, session, got)
        return _fetch_span(query, mid + 1, hi, session, got) and first


def fetch_urls(query: Dict[str, Any], session: Any = None, workers: int = 3) -> List[str]:
    """Root-page URLs the archive saw for one host, only those it archived with HTTP 200. A query with `split` runs as its
    chunks; the chunks that answer are kept even when others do not (`ArchiveError.urls`)."""
    session = session or requests
    if not query.get("split"):
        return _fetch_one(query, session)

    def chunk(url: str) -> Tuple[str, List[str], bool]:
        try:
            return url, _fetch_one({**query, "url": url}, session), True
        except ArchiveError:
            pass
        # Too big for one answer (wd1, wd3, wd5, Lever's commonest letters, 2026-10-21): one year of captures at a time, and a year
        # that still fails in halves, down to one month. A board captured in several years is listed once by `board_seeds`.
        got: List[str] = []
        ok = True
        for year in YEARS:
            lo = (year - FIRST_YEAR) * 12
            ok = _fetch_span(query, lo, lo + 11, session, got) and ok
        return url, got, ok

    with ThreadPoolExecutor(max_workers=workers) as ex:
        done = list(ex.map(chunk, query["split"]))
    urls = [u for _, got, _ in done for u in got]            # what a failed chunk did return is kept too
    failed = [url for url, _, ok in done if not ok]
    if failed:
        raise ArchiveError(f"the Internet Archive did not answer for {query['name']}: {len(failed)} of {len(done)} chunks "
                           f"({', '.join(failed[:4])}{', ...' if len(failed) > 4 else ''})", urls)
    return urls


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
    if ats == "oracle_hcm":
        host, _, site = ident.rpartition(":")
        good = bool(host and re.fullmatch(r"[A-Za-z0-9_-]{1,60}", site) and not _TEST_INSTANCE.search(host.split(".")[0]))
        return (ats, ident.lower()) if good else None
    if ats not in ATS_PROBES:
        return None
    if not _SLUG_OK.match(ident) or ident.lower() in _NOT_A_BOARD or _ID.match(ident.lower()) or ident.isdigit():
        return None
    return ats, ident.lower()


_TITLE_ERROR = re.compile(r"not\s+found|unavailable|outage|maintenance|\berror\b|forbidden|denied|suspen|sign\s*in|log\s*in", re.IGNORECASE)
_TITLE_GENERIC = {"", "careers", "career", "career site", "jobs", "job search", "home", "external", "website", "welcome",
                  "oracle recruiting cloud", "oracle cloud", "recruiting", "recruitment", "opportunities", "employment",
                  "job opportunities", "job openings", "open positions", "careers center", "career center", "join us", "work with us",
                  "employment opportunities", "current opportunities", "current openings", "vacancies", "careers home",
                  "hr", "human resources", "americas", "emea", "apac", "latam", "global", "international", "worldwide",
                  # an industry or a business unit, not an employer ("Aerospace" was Honeywell's aerospace unit, 2026-10-17)
                  "aerospace", "defense", "defence", "healthcare", "banking", "finance", "logistics", "energy", "retail", "technology",
                  "manufacturing", "insurance", "automotive", "pharma", "education", "hospitality"}
_TITLE_NOT_ENGLISH_GENERIC = re.compile("\u5019\u9009\u4eba|\u5019\u9078\u4eba|\u5019\u88dc\u8005|\u5e94\u8058|\u61c9\u8058")      # "candidate", "applicant" in Chinese and Japanese
_TITLE_SEPARATOR = re.compile(r"\s+[|\u2013\u2014-]\s+|\s*\|\s*")
_TITLE_LEADING = re.compile(
    r"^(?:(?:careers?|jobs?|work|join|welcome\s+to)\s+(?:at|with|for)\s+|careers?\s*@\s*"
    r"|sua\s+carreira\s+na\s+|opportunit\u00e9s\s+au\s+sein\s+(?:du|de\s+la|de|des)\s+(?:groupe\s+)?"      # Portuguese, French
    r"|site\s+carri\u00e8re(?:\s+externe)?\s+)", re.IGNORECASE)
_TITLE_GENERIC_THEN_NAME = re.compile(r"^(?:career\s+site|careers?|jobs?)\s*\((.+)\)$", re.IGNORECASE)      # "Career Site(Servify)"
_TITLE_TRAILING = re.compile(
    r"[\s\-\u2013\u2014|:,]*\b(?:(?:global|external|internal)\s+)?"
    r"(?:careers?(?:\s+(?:site|portal|page|website|opportunities))?|jobs?(?:\s+(?:site|portal|board|opportunities))?"
    r"|recruit(?:ment|ing)(?:\s+team)?|talent\s+acquisition|candidate\s+experience(?:\s+site)?|web\s*site)\s*$", re.IGNORECASE)


def clean_site_title(raw: Optional[str]) -> str:
    """The employer's name from the <title> of an Oracle candidate site, or "" when the title names none ("Page not found",
    "Candidate Experience site", "Careers"). "Hoya Global Career Site" -> "Hoya"; JSON escapes and entities are decoded."""
    if not raw:
        return ""
    t = html.unescape(raw)
    t = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), t).replace("\\'", "'").replace('\\"', '"')
    t = " ".join(t.split())
    if _TITLE_ERROR.search(t) or _TITLE_NOT_ENGLISH_GENERIC.search(t):
        return ""
    for part in _TITLE_SEPARATOR.split(t):                # "Careers | BXP", "Meezan Bank - Careers | Job Opportunities": the first part that names someone
        name = _strip_generic(part)
        if name:
            return name
    return ""


def _strip_generic(part: str) -> str:
    part = part.strip()
    wrapped = _TITLE_GENERIC_THEN_NAME.match(part)
    t = _TITLE_LEADING.sub("", wrapped.group(1).strip() if wrapped else part)
    previous = None
    while previous != t:                                  # "Acme Global Career Site" loses both suffixes in turn
        previous = t
        t = _TITLE_TRAILING.sub("", t).strip(" -\u2013\u2014|:,")
    if t.lower() in _TITLE_GENERIC or t.lower().startswith("candidate experience"):
        return ""
    return t


_ORACLE_URL = re.compile(r"https?://([^/]+\.oraclecloud\.com)/hcmUI/CandidateExperience/([^/]+)/sites/([^/?#]+)")
_TITLE_TAG = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def fetch_site_names(urls: List[str], session: Any = None, workers: int = 8) -> Dict[str, str]:
    """{"host:site": employer name} for the Oracle candidate sites in `urls` whose page title names an employer (T112)."""
    session = session or requests

    def one(url: str) -> Tuple[str, str]:
        m = _ORACLE_URL.match(url)
        if not m:
            return "", ""
        try:
            resp = session.get(f"https://{m.group(1)}/hcmUI/CandidateExperience/{m.group(2)}/sites/{m.group(3)}",
                               headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
            if resp.status_code != 200:
                return "", ""
            tag = _TITLE_TAG.search(resp.text)
            return f"{m.group(1)}:{m.group(3)}", clean_site_title(tag.group(1) if tag else "")
        except Exception:
            return "", ""
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        return {ident: name for ident, name in ex.map(one, urls) if ident and name}


def board_seeds(urls: List[str], existing: List[Dict[str, Any]], names: Optional[Dict[str, str]] = None) -> List[str]:
    """`discover` seed lines for the boards in `urls` that are not already in `existing` (companies.json entries)."""
    have = {(c.get("ats", ""), _board_ident(c).lower()) for c in existing}
    # On Oracle HCM the host is the employer and its sites are its career sites: a host already listed is not added again.
    have_oracle_hosts = {str(c.get("host", "")).lower() for c in existing if c.get("ats") == "oracle_hcm"}
    found: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for url in urls:
        detected = detect_ats(url) if url.startswith("http") else None
        if not detected:
            continue
        key = _usable(*detected)
        if key is None or key in have or (key[0] == "oracle_hcm" and key[1].rpartition(":")[0] in have_oracle_hosts):
            continue
        # one board written in two cases is one board; keep the spelling with capitals (a Workday site, a SmartRecruiters id)
        if key not in found or (detected[1] != detected[1].lower() and found[key][1] == found[key][1].lower()):
            found[key] = detected
    # Each Oracle site is named by its own page title (T117: the host's commonest title named Resideo's site "ADI" and McDermott's
    # "Lutech", and `discover` keeps a host's busiest site). A site whose own title names nobody takes the host's main title: the one
    # most of its sites carry (then the shorter, then the alphabetical one). `discover` keeps one entry per host, the busiest site, and on
    # a tie the first it was given, so a host's sites are written together, those with the main title first.
    titles: Dict[str, List[str]] = {}
    for ats, ident in found.values():
        if ats == "oracle_hcm":
            title = (names or {}).get(ident) or (names or {}).get(ident.lower())
            if title:
                titles.setdefault(ident.rpartition(":")[0].lower(), []).append(title)
    host_name = {host: sorted(Counter(ts).items(), key=lambda kv: (-kv[1], len(kv[0]), kv[0]))[0][0] for host, ts in titles.items()}
    lines = []
    order: Dict[str, Tuple[str, int, str]] = {}
    for ats, ident in found.values():
        if ats == "oracle_hcm":
            host, _, site = ident.rpartition(":")
            main = host_name.get(host.lower())
            if main is None:                                   # no site of this host names an employer: no seed
                continue
            own = (names or {}).get(ident) or (names or {}).get(ident.lower()) or main
            label = own.replace("|", "/")                      # `|` separates the fields of a seed line
            line = f"{label} | https://{host}/hcmUI/CandidateExperience/en/sites/{site} | exact"
            lines.append(line)
            order[line] = (main.lower(), 0 if own == main else 1, label.lower())
            continue
        if ats == "workday":
            tenant, dc, site = ident.split(":")
            lines.append(f"{pretty(tenant)} | https://{tenant}.{dc}.myworkdayjobs.com/{site} | exact")   # exact: one seed per site
        else:
            lines.append(f"{pretty(ident)} | {_BOARD_URL[ats].format(ident)} | exact")
    return sorted(lines, key=lambda ln: (*order.get(ln, (ln.split(" | ")[0].lower(), 0, "")), ln))


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
    failed: List[str] = []
    for name in names:
        try:
            got = fetch_urls(ARCHIVE_QUERIES[name])
        except RuntimeError as e:            # the archive is flaky: one query that never answers must not lose the others
            print(f"  {name}: {e}", file=sys.stderr)
            failed.append(name)
            urls += getattr(e, "urls", [])      # the chunks of a split query that did answer
            if getattr(e, "urls", []):
                print(f"  {name}: kept {len(e.urls)} url(s) from the chunks that answered")  # type: ignore[attr-defined]
            continue
        print(f"  {name}: {len(got)} url(s)")
        urls += got
    oracle_urls = [u for u in urls if "oraclecloud.com/hcmUI" in u]
    site_names = fetch_site_names(oracle_urls) if oracle_urls else {}
    if oracle_urls:
        print(f"  oracle: {len(site_names)} of {len(oracle_urls)} site(s) name an employer")
    lines = board_seeds(urls, existing, site_names)
    Path(args.out).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"{len(lines)} seed(s) -> {args.out}")
    if failed:
        print(f"the archive did not answer for: {', '.join(failed)}; run again with --hosts {','.join(failed)}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
