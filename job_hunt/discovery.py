"""Verify candidate companies against public ATS boards and build companies.json entries.

A company is added only when a board is proven to be (1) live — at least one open job,
(2) the right employer — board name matches, or the company is named in its job
descriptions, or the slug came from the company's own careers URL, and (3) hiring in
India — at least one job located in India (or in the countries of --places / config.json's candidate.countries, T139). This avoids the failure modes seen before:
empty boards, and same-slug boards that belong to a different company (Navi, Bounce).

Usage:
    # whole seed list (slow: ~800 names, 5-20 min)
    python -m job_hunt discover --seeds scripts/company_seeds.txt \\
        --report /tmp/discovery.csv --out /tmp/verified.json [--merge companies.json]
    # verify only a pasted list (any format: plain, "Name = url", tables, legal names);
    # new names are appended to the seeds file for the record
    python -m job_hunt discover --add-file /tmp/paste.txt --merge companies.json [--no-recheck]
    python -m job_hunt discover --add "Plane, BitGo, Groww" --merge companies.json
    # periodic health check of the existing list (run monthly/quarterly): re-verify every
    # entry; boards that fail are re-discovered by name (ATS migration) or removed
    python -m job_hunt discover --recheck --merge companies.json --report /tmp/recheck.csv --out /tmp/recheck.json
    # ATS census: which platform do careers pages use? ("Name | careers URL" lines)
    python -m job_hunt discover --census scripts/careers_urls.txt --report /tmp/census.csv \\
        [--emit-seeds /tmp/census_seeds.txt]   # then: discover --add-file /tmp/census_seeds.txt --merge ...

Seeds file, one company per line ('#' comments allowed):
    Stripe
    Jupiter Money | https://jobs.lever.co/jupiter
    BlackBerry | workday | bb | wd3 | BlackBerry
    Qualcomm | eightfold | qualcomm.eightfold.ai | qualcomm.com     (host of the careers site | employer domain)
    BCG | phenom | careers.bcg.com | global/en                      (host of the careers site | locale path of its URLs)
    Acme | https://jobs.lever.co/acme | exact                       (only this board; the name comes from the board:
                                                                   what scripts/harvest_board_urls.py writes, T111)

Options: --report FILE, --out FILE, --merge FILE (add the verified entries to it), --no-recheck (do not re-check the
entries already in the --merge file), --workers N (parallel probes, default 40; use 3 for Workable and Recruitee seeds,
which refuse bursts), --places "United Kingdom, Germany" (the countries a board needs a job in; default config.json's
candidate.countries, else India; an entry accepted for other countries records them as "places", T139). Run it from the
repository folder (the paths are relative); no API key is needed.
Guide: docs/04-companies-and-scanning.md, "Growing the list".
"""
from __future__ import annotations

import csv
import json
import logging
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urljoin

import requests

from job_hunt.adapters import detect_ats, fetch_company_jobs
from job_hunt.adapters.base import DEFAULT_HEADERS, begin_fetch, fetch_incomplete
from job_hunt.adapters.workday import (
    _fetch_detail,
    fetch_detail_locations,
    is_multi_location,
    item_location,
    redirected_away,
)
from job_hunt.company_builder import CORPORATE_SUFFIX_RE, load_linkedin_cache, match_headcount
from job_hunt.harvester import ATS_PROBES, _probe, default_linkedin_cache
from job_hunt.models import JobPosting
from job_hunt.places import (
    Places,
    active_places,
    configure_places,
    entry_places,
    places_from_config,
    using,
)
from job_hunt.prefilter import (
    LOCATION_INDIA_COUNTRY_CODE,
    LOCATION_INDIA_PATTERN,
    should_evaluate_job,
    without_philippine_ncr,
)

logger = logging.getLogger(__name__)

# Boards proven to be wrong or useless (see CLAUDE.md): same-slug boards of a different
# employer, or third-party stub postings. Never accepted, whatever the probe says.
KNOWN_BAD_BOARDS = {
    ("ashby", "navi"), ("ashby", "bounce"), ("personio", "edelweiss"), ("personio", "josh"),
    ("workable", "eatclub"), ("lever", "porter"), ("smartrecruiters", "nobroker"),
    ("smartrecruiters", "upstox"), ("smartrecruiters", "turtlemint"), ("smartrecruiters", "whatfix"),
    # T142, read by hand: another company with the name ("named in N/N job descriptions" proves nothing for a common word).
    # The lists mean Lightspeed (Auckland), Clark (Berlin insurance) and Sunday (Berlin); these boards are LightSpeed Build
    # Technologies (Illinois), an AI audit start-up (New York) and a home-robotics company (Redwood City).
    ("ashby", "lightspeed"), ("ashby", "clark"), ("ashby", "sunday"),
}

# A board whose newest posting is older than this is treated as abandoned. Seen in the
# wild: SmartRecruiters boards answering 200 with 1-2 postings from 2015-2020.
MAX_NEWEST_AGE_DAYS = 180

# How many "N Locations" postings the Workday light check resolves, at most, when the first page shows no India job (T113).
WORKDAY_DETAIL_CALLS = 8

REPORT_FIELDS = [
    "seed", "verdict", "ats", "board", "jobs", "place_jobs", "prefilter_pass", "newest_age_days",
    "identity", "sample_titles",
]


# ── pure helpers ──────────────────────────────────────────────────────────────

def _words(name: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", name.lower())


_LEGAL_SUFFIX_RE = re.compile(r"\b(llp|llc|co|company|group|holdings)\b", re.IGNORECASE)


def _core_words(name: str) -> List[str]:
    stripped = _LEGAL_SUFFIX_RE.sub(" ", CORPORATE_SUFFIX_RE.sub(" ", name.lower()))
    return _words(stripped) or _words(name)


def name_variants(name: str) -> List[str]:
    """Outside-parentheses name plus each parenthesised part.

    Pasted lists mix brands and legal entities: "OLA (ANI Technologies Private Limited)",
    "FASHNEAR TECHNOLOGIES PRIVATE LTD (Meesho)". Either side may be the ATS brand.
    """
    parts = [re.sub(r"\([^)]*\)", " ", name)] + re.findall(r"\(([^)]*)\)", name)
    out: List[str] = []
    for v in parts:
        v = " ".join(v.split()).strip(" -,")
        if v and v.lower() not in ("intern", "fte", "intern + fte") and v not in out:
            out.append(v)
    return out or [name]


def display_name(name: str) -> str:
    """Variant with the fewest words — the brand, not the legal entity
    ("Meesho" over "FASHNEAR TECHNOLOGIES PRIVATE LTD", "OLA", "Quadeye")."""
    return min(name_variants(name), key=lambda v: len(_words(v)))


def slug_candidates(name: str) -> List[str]:
    """Likely ATS slugs for a company name, most specific first, no duplicates."""
    cands: List[str] = []
    for variant in name_variants(name):
        full, core = _words(variant), _core_words(variant)
        cands += ["".join(full), "-".join(full), "".join(core), "-".join(core)]
        if len(core) > 1 and len(core[0]) >= 5:
            cands.append(core[0])  # "Tower Research Capital" -> "tower"; short words collide too often
    seen: List[str] = []
    for c in cands:
        if c and c not in seen:
            seen.append(c)
    return seen


_MONTH_TAIL_RE = re.compile(
    r"\s+(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|june?|july?|aug(ust)?|sep(t(ember)?)?"
    r"|oct(ober)?|nov(ember)?|dec(ember)?)\b([/ ].*)?$",
    re.IGNORECASE,
)
_HEADER_CELLS = {"company", "company name", "index no", "name", "s.no", "sr no"}


def extract_company_names(text: str) -> List[Tuple[str, str]]:
    """Pull (company, url) pairs out of a free-form paste.

    Handles plain names, "F = Facebook = url", "10. Codenation = url", campus-calendar
    lines ("Sahaj August/sept", "Amazon(intern)    september"), "𝐃𝐢𝐫𝐞𝐜𝐭𝐢: Basic …"
    salary lines, tab-separated tables (with or without an index column), and HTML
    <a href=…>Name</a> list items. Duplicates (case-insensitive) are dropped.
    """
    out: List[Tuple[str, str]] = []
    seen = set()
    for raw in text.splitlines():
        line = unicodedata.normalize("NFKC", raw).strip()
        if not line or line.startswith("#"):
            continue
        url = ""
        link = re.search(r'href="([^"]+)"[^>]*>([^<]+)</a>', line)
        if link:
            url, name = link.group(1), link.group(2)
        elif line.startswith("<"):
            continue
        elif "\t" in line:
            cells = [c.strip() for c in line.split("\t") if c.strip()]
            if cells and re.fullmatch(r"\d+", cells[0]):
                cells = cells[1:]
            if not cells or cells[0].lower() in _HEADER_CELLS:
                continue
            name = cells[0]
        else:
            parts = re.split(r"\s+=\s+", line)
            if len(parts) >= 2 and re.match(r"https?://", parts[-1]):
                url, parts = parts[-1], parts[:-1]
            if len(parts) >= 2 and len(parts[0]) <= 2:
                parts = parts[1:]  # "F = Facebook"
            name = re.sub(r"^\d+[\.\)]\s*", "", parts[0])
            name = name.split(":")[0]
            name = re.split(r"\s{2,}|\s+-+>", name)[0]
            name = re.sub(r"\((intern|fte)[^)]*\)", "", name, flags=re.IGNORECASE)
            name = _MONTH_TAIL_RE.sub("", name)
        name = " ".join(name.split()).strip(" -:,")
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append((name, url))
    return out


def parse_seeds(text: str) -> List[Dict[str, Any]]:
    seeds: List[Dict[str, Any]] = []
    seen = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        name = parts[0]
        is_workday = len(parts) >= 5 and parts[1].lower() == "workday"
        is_eightfold = len(parts) >= 4 and parts[1].lower() == "eightfold"
        is_phenom = len(parts) >= 4 and parts[1].lower() == "phenom"
        workday_auto = len(parts) == 3 and parts[1].lower() == "workday" and parts[2].lower() == "auto"      # T148
        # "Name | board URL | exact" (T111): a harvested board. Its name is only a label, so two boards may share one.
        exact = len(parts) >= 3 and parts[2].lower() == "exact" and not (is_workday or is_eightfold or is_phenom)
        key = (name.lower(), "workday" if is_workday else "eightfold" if is_eightfold else "phenom" if is_phenom else
               "workday-auto" if workday_auto else "", parts[1].lower() if exact else "")
        if not name or key in seen:
            continue
        seen.add(key)
        seed: Dict[str, Any] = {"name": name}
        if workday_auto:
            seed["workday_auto"] = True
        elif is_workday:
            seed["workday"] = {"tenant": parts[2], "dc": parts[3], "site": parts[4]}
        elif is_eightfold:
            seed["eightfold"] = {"host": parts[2], "domain": parts[3]}
        elif is_phenom:
            seed["phenom"] = {"host": parts[2], "locale": parts[3]}
        elif len(parts) >= 2 and parts[1]:
            detected = detect_ats(parts[1])
            if detected and detected[0] == "workday":
                tenant, dc, site = detected[1].split(":")
                seed["workday"] = {"tenant": tenant, "dc": dc, "site": site}
            elif detected and detected[0] == "oracle_hcm":
                host, site = detected[1].rsplit(":", 1)
                seed["oracle_hcm"] = {"host": host, "site": site}
            else:
                seed["url"] = parts[1]
                if exact:
                    seed["exact"] = True
        seeds.append(seed)
    return seeds


def name_matches(seed_name: str, board_name: str) -> bool:
    """True when, for some variant of the seed, one name's core words are a leading
    run of the other's."""
    b = _core_words(board_name)
    for variant in name_variants(seed_name):
        a = _core_words(variant)
        if not a or not b:
            continue
        short, long_ = (a, b) if len(a) <= len(b) else (b, a)
        if long_[: len(short)] == short:
            return True
    return False


def newest_age_days(jobs: List[JobPosting], now: Optional[datetime] = None) -> Optional[int]:
    """Days since the most recent parseable posted_at (ISO dates); None if none parse."""
    today = now.astimezone().date() if now else date.today()     # local days, as every other age (T110)
    dates: List[date] = []
    for j in jobs:
        try:
            dates.append(date.fromisoformat((j.posted_at or "")[:10]))
        except ValueError:
            continue
    return (today - max(dates)).days if dates else None


def accept_board(
    ats: str, slug: str, jobs: int, place_jobs: int, identity_ok: bool,
    newest_age_days: Optional[int] = None,
) -> Tuple[bool, str]:
    if (ats, slug.lower()) in KNOWN_BAD_BOARDS:
        return False, "known bad board"
    if jobs <= 0:
        return False, "no open jobs"
    if newest_age_days is not None and newest_age_days > MAX_NEWEST_AGE_DAYS:
        return False, f"stale board (newest posting {newest_age_days} days old)"
    if not identity_ok:
        return False, "identity not confirmed"
    if place_jobs <= 0:
        places = active_places()
        return False, "no India jobs" if places.india_only() else f"no jobs in {places.label()}"
    return True, "verified"


def merge_companies(existing: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Existing entries win; a new entry is dropped if its name or board is already present (and, for Oracle HCM, its host)."""
    def board_key(c: Dict[str, Any]) -> Tuple[str, str]:
        return c.get("ats", ""), _board_ident(c).lower()

    def name_key(c: Dict[str, Any]) -> str:
        return " ".join(_core_words(c["name"]))  # "Mindtickle India" == "Mindtickle"

    def oracle_host(c: Dict[str, Any]) -> str:
        return str(c.get("host", "")).lower() if c.get("ats") == "oracle_hcm" else ""

    out = list(existing)
    names = {name_key(c) for c in out}
    boards = {board_key(c) for c in out}
    # An Oracle HCM host is one employer's tenant and its sites are its career sites: one entry per host, the first given (T117).
    oracle_hosts = {oracle_host(c) for c in out} - {""}
    for c in new:
        if name_key(c) in names or board_key(c) in boards or (oracle_host(c) and oracle_host(c) in oracle_hosts):
            continue
        out.append(c)
        names.add(name_key(c))
        boards.add(board_key(c))
        oracle_hosts.add(oracle_host(c))
    return sorted(out, key=lambda c: (c.get("ats", ""), c["name"].lower()))


def _board_ident(c: Dict[str, Any]) -> str:
    """Stable board identifier across ATS kinds (slug, Workday tenant:dc:site, Oracle host:site, Eightfold host:domain, Phenom host:locale)."""
    if c.get("slug"):
        return str(c["slug"])
    if c.get("ats") == "oracle_hcm":
        return f"{c.get('host')}:{c.get('site')}" if c.get("site") else str(c.get("host", ""))
    if c.get("ats") == "workday":
        return f"{c.get('tenant')}:{c.get('dc')}:{c.get('site')}"
    if c.get("ats") == "eightfold":
        return f"{c.get('host')}:{c.get('domain')}"
    if c.get("ats") == "phenom":
        return f"{c.get('host')}:{c.get('locale')}"
    return str(c.get("ats", ""))


def name_collisions(existing: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Report new companies whose name key reduces to an existing one's on a different board.

    Same-board duplicates stay silent.
    """
    def board_key(c: Dict[str, Any]) -> Tuple[str, str]:
        return c.get("ats", ""), _board_ident(c).lower()

    def name_key(c: Dict[str, Any]) -> str:
        return " ".join(_core_words(c["name"]))

    existing_boards = {board_key(c) for c in existing}
    existing_by_name: Dict[str, Dict[str, Any]] = {}
    for c in existing:
        k = name_key(c)
        if k and k not in existing_by_name:
            existing_by_name[k] = c

    collisions: List[Dict[str, Any]] = []
    seen_new_boards: Set[Tuple[str, str]] = set()
    for c in new:
        b_key = board_key(c)
        if b_key in existing_boards or b_key in seen_new_boards:
            continue
        seen_new_boards.add(b_key)
        nk = name_key(c)
        if nk in existing_by_name:
            ex = existing_by_name[nk]
            ex_ats = ex.get("ats", "")
            ex_board = _board_ident(ex)
            ex_board_full = f"{ex_ats}/{ex_board}"
            verdict = f"name collision: not added; existing {ex['name']} ({ex_board_full})"
            collisions.append({
                "seed": c["name"],
                "verdict": verdict,
                "ats": c.get("ats", ""),
                "board": _board_ident(c),
                "accepted": False,
                "existing_name": ex["name"],
                "existing_ats": ex_ats,
                "existing_board": ex_board,
                "existing_board_full": ex_board_full,
            })
    return collisions


def _is_india(location: str) -> bool:
    text = without_philippine_ncr(location)     # "Makati City, NCR, ph" is Manila, not Delhi (T115)
    return bool(LOCATION_INDIA_PATTERN.search(text) or LOCATION_INDIA_COUNTRY_CODE.search(text))


def _in_places(location: str) -> bool:
    """A job in the places being checked (T139): India alone counts as before; other countries by their packs."""
    places = active_places()
    return _is_india(location) if places.india_only() else places.names_place(location)


# ── network checks ────────────────────────────────────────────────────────────

def _board_name(ats: str, slug: str) -> Optional[str]:
    """Employer name published by the board itself, where the ATS exposes one."""
    try:
        if ats == "greenhouse":
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}", headers=DEFAULT_HEADERS, timeout=10)
            return r.json().get("name") if r.status_code == 200 else None
        if ats == "smartrecruiters":
            r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                             headers=DEFAULT_HEADERS, params={"limit": 1}, timeout=10)
            content = r.json().get("content", []) if r.status_code == 200 else []
            return content[0].get("company", {}).get("name") if content else None
        if ats == "workable":
            r = requests.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}",
                             headers=DEFAULT_HEADERS, timeout=10)
            return r.json().get("name") if r.status_code == 200 else None
    except Exception as e:
        logger.debug("board name lookup failed for %s/%s: %s", ats, slug, e)
    return None


def _identity(seed_name: str, ats: str, slug: str, jobs: List[JobPosting], from_url: bool) -> Tuple[bool, str]:
    if from_url:
        return True, "slug from company careers URL"
    board = _board_name(ats, slug)
    if board:
        return name_matches(seed_name, board), f"board name '{board}'"
    patterns = [
        re.compile(r"\b" + re.escape(" ".join(_core_words(v))).replace(r"\ ", r"[\s\-]?") + r"\b", re.IGNORECASE)
        for v in name_variants(seed_name)
    ]
    mentions = sum(1 for j in jobs if any(p.search(f"{j.title}\n{j.description_text}") for p in patterns))
    return mentions > 0, f"named in {mentions}/{len(jobs)} job descriptions"


def evaluate_board(seed_name: str, ats: str, slug: str, from_url: bool = False) -> Dict[str, Any]:
    begin_fetch()
    jobs = fetch_company_jobs({"name": seed_name, "ats": ats, "slug": slug})
    inc = fetch_incomplete()
    if not jobs and inc:
        return {
            "seed": seed_name, "verdict": f"not checked: {inc}", "accepted": False, "ats": ats, "board": slug,
            "jobs": 0, "place_jobs": 0, "prefilter_pass": 0,
            "newest_age_days": "", "identity": "not checked",
            "sample_titles": "", "seen_places": [],
        }
    india = sum(1 for j in jobs if _in_places(j.location))
    passing = [j for j in jobs if should_evaluate_job(j)[0]]
    identity_ok, how = _identity(seed_name, ats, slug, jobs, from_url) if jobs else (False, "no jobs")
    age = newest_age_days(jobs)
    ok, verdict = accept_board(ats, slug, len(jobs), india, identity_ok, age)
    return {
        "seed": seed_name, "verdict": verdict, "accepted": ok, "ats": ats, "board": slug,
        "jobs": len(jobs), "place_jobs": india, "prefilter_pass": len(passing),
        "newest_age_days": "" if age is None else age, "identity": how,
        "sample_titles": "; ".join(j.title[:50] for j in passing[:3]),
        "seen_places": [] if active_places().india_only() else active_places().seen_in(j.location for j in jobs),
    }


def evaluate_entry(seed_name: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a board that needs no slug probing (Oracle HCM, Amazon, ...) through its real
    adapter. Identity is trusted: the entry came from the company's own careers URL."""
    begin_fetch()
    jobs = fetch_company_jobs({**entry, "name": seed_name})
    inc = fetch_incomplete()
    ident = _board_ident(entry)
    if not jobs and inc:
        return {
            "seed": seed_name, "verdict": f"not checked: {inc}", "accepted": False, "ats": entry["ats"], "board": ident,
            "jobs": 0, "place_jobs": 0, "prefilter_pass": 0,
            "newest_age_days": "", "identity": "careers URL / curated entry",
            "sample_titles": "",
            "entry": {"name": seed_name, **entry},
        }
    india = sum(1 for j in jobs if _in_places(j.location))
    passing = [j for j in jobs if should_evaluate_job(j)[0]]
    age = newest_age_days(jobs)
    ok, verdict = accept_board(entry["ats"], ident, len(jobs), india, True, age)
    return {
        "seed": seed_name, "verdict": verdict, "accepted": ok, "ats": entry["ats"], "board": ident,
        "jobs": len(jobs), "place_jobs": india, "prefilter_pass": len(passing),
        "newest_age_days": "" if age is None else age, "identity": "careers URL / curated entry",
        "sample_titles": "; ".join(j.title[:50] for j in passing[:3]),
        "entry": {"name": seed_name, **entry},
    }


# ── Workday tenants found by name (T148) ──────────────────────────────────────

# Data centres, most employers first (Europe's are mostly wd3 and wd103, measured 2026-10-22 on 58 well-known employers).
WORKDAY_DCS = ("wd3", "wd1", "wd5", "wd103", "wd12", "wd501", "wd502", "wd503", "wd108", "wd102", "wd115", "wd10", "wd107", "wd504",
               "wd2", "wd4")
# Workday answers a plain request with 406: it wants a language. The file a tenant serves at /robots.txt lists every career
# site it has ("Sitemap: https://<tenant>.<dc>.myworkdayjobs.com/<Site>/siteMap.xml"), and a tenant that does not exist on that
# data centre answers 422, so the tenant, its data centre and all its sites come from the company name alone.
_WORKDAY_ROBOTS_HEADERS = {**DEFAULT_HEADERS, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
_WORKDAY_SITE_RE = re.compile(r"myworkdayjobs\.com/([^/\s]+)/siteMap\.xml", re.IGNORECASE)
MAX_WORKDAY_SITES = 12


_LEGAL_TOKENS = {"ag", "se", "sa", "nv", "bv", "gmbh", "plc", "inc", "ltd", "llc", "limited", "corp", "corporation", "co", "company",
                 "private", "pvt", "the", "kg", "oy", "ab", "as", "spa", "srl", "sas", "sarl"}
_GROUP_TOKENS = {"group", "holdings", "holding"}


def workday_tenant_slugs(name: str) -> List[str]:
    """Tenant names a company might use: its name run together, without its legal form, and without "Group" or "Holdings" too
    ("Lloyds Banking Group" -> lloydsbankinggroup, lloydsbanking; "Deutsche Bank AG" -> deutschebankag, deutschebank). Never a
    first word alone: "standard" was not Standard Chartered's tenant and "lloyds" was Lloyd's of London (prototype, 2026-10-22)."""
    out: List[str] = []
    for v in name_variants(name):
        words = _words(v)
        plain = [w for w in words if w not in _LEGAL_TOKENS] or words
        short = [w for w in plain if w not in _GROUP_TOKENS] or plain
        for tokens in (words, plain, short):
            slug = "".join(tokens)
            if re.fullmatch(r"[a-z0-9]{3,40}", slug) and slug not in out:
                out.append(slug)
    return out[:4]


def _workday_robots(slug: str, dc: str) -> List[str]:
    """The career sites a tenant lists on one data centre; none when it is not there (422) or the request fails twice."""
    for attempt in range(2):
        try:
            r = requests.get(f"https://{slug}.{dc}.myworkdayjobs.com/robots.txt", headers=_WORKDAY_ROBOTS_HEADERS, timeout=15)
        except requests.RequestException:
            continue
        if r.status_code == 200:
            return list(dict.fromkeys(_WORKDAY_SITE_RE.findall(r.text)))[:MAX_WORKDAY_SITES]
        if r.status_code in (404, 422):
            return []
    return []


def workday_tenant_for(name: str) -> List[Tuple[str, str, str]]:
    """[(tenant, data centre, site)] for the Workday tenant named like the company: the first slug and data centre that answer."""
    for slug in workday_tenant_slugs(name):
        for dc in WORKDAY_DCS:
            sites = _workday_robots(slug, dc)
            if sites:
                return [(slug, dc, site) for site in sites]
    return []


def _workday_names_company(seed_name: str, cxs_base: str, posts: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """Whether the company's name appears in the text of up to 3 of the tenant's postings (those in your places first): a
    tenant called "delta" is not necessarily Delta Air Lines."""
    pool = [q for q in posts if q.get("externalPath")]
    pool.sort(key=lambda q: not _in_places(item_location(q)))
    patterns = [re.compile(r"\b" + re.escape(" ".join(_core_words(v))).replace(r"\ ", r"[\s\-]?") + r"\b", re.IGNORECASE)
                for v in name_variants(seed_name)]
    asked = 0
    for q in pool[:3]:
        asked += 1
        _, text = _fetch_detail(cxs_base, q["externalPath"])
        if any(pt.search(f"{q.get('title', '')}\n{text}") for pt in patterns):
            return True, f"named in a job description ({asked} read)"
    return False, f"not named in {asked} job description(s) read"


def evaluate_workday(seed_name: str, tenant: str, dc: str, site: str, confirm_name: bool = False) -> Dict[str, Any]:
    """Light check: first page of the India search (the adapter itself paginates to 100). When that page shows no India
    job, a few "N Locations" postings are resolved with the detail call, as the adapter does (T113: Northern Trust's
    search has 99 hits but its first 20 read "2 Locations", "Chicago, IL", "Luxembourg")."""
    cxs_base = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"
    url = f"{cxs_base}/jobs"
    row: Dict[str, Any] = {"seed": seed_name, "ats": "workday", "board": f"{tenant}.{dc}/{site}",
                           "identity": "curated tenant", "sample_titles": ""}
    posts: List[Dict[str, Any]] = []
    status = ""
    for term in active_places().workday_terms():     # "India" alone unless other places are checked (T139)
        try:
            r = requests.post(url, json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": term},
                              headers=DEFAULT_HEADERS, timeout=15)
            away = redirected_away(r, f"{tenant}.{dc}.myworkdayjobs.com")
            if away:        # Workday's maintenance page: the board is not dead, it cannot be read right now (T113)
                row.update({"verdict": f"error: Workday answered with a redirect to {away}, not with jobs (maintenance?)",
                            "accepted": False, "jobs": 0, "place_jobs": 0, "prefilter_pass": 0})
                return row
            page = r.json().get("jobPostings", []) if r.status_code == 200 else []
            status = f"HTTP {r.status_code}"
            if r.status_code in (404, 422):      # no such board or site: every other search term answers the same (T144)
                break
        except Exception as e:
            page, status = [], str(e)[:60]
        known = {q.get("externalPath") for q in posts}
        posts += [q for q in page if not q.get("externalPath") or q.get("externalPath") not in known]
        if any(_in_places(item_location(q)) for q in page):
            break
    jobs = [JobPosting("", "workday", seed_name, p.get("title", ""), item_location(p), False, "")
            for p in posts]
    india = sum(1 for j in jobs if _in_places(j.location))
    if not india:
        asked = 0
        for p, job in zip(posts, jobs):
            if asked >= WORKDAY_DETAIL_CALLS:
                break
            if p.get("externalPath") and is_multi_location(job.location):
                asked += 1
                job.location = fetch_detail_locations(cxs_base, p["externalPath"]) or job.location
                if _in_places(job.location):
                    india = 1
                    break
    passing = [j for j in jobs if should_evaluate_job(j)[0]]
    ok, verdict = accept_board("workday", f"{tenant}:{dc}:{site}", len(jobs), india, True)
    if ok and confirm_name:                  # a tenant found by guessing its name: say whose it is from the postings themselves
        named, how = _workday_names_company(seed_name, cxs_base, posts)
        row["identity"] = how
        if not named:
            ok, verdict = False, "identity not confirmed"
    row.update({"verdict": verdict if posts else f"{verdict} ({status})", "accepted": ok, "jobs": len(jobs),
                "place_jobs": india, "prefilter_pass": len(passing),
                "sample_titles": "; ".join(j.title[:50] for j in passing[:3]),
                "entry": {"name": seed_name, "ats": "workday", "tenant": tenant, "dc": dc, "site": site}})
    return row


def _probe_pairs(seed: Dict[str, Any]) -> List[Tuple[str, str, bool]]:
    pairs: List[Tuple[str, str, bool]] = []
    detected = detect_ats(seed.get("url", "")) if seed.get("url") else None
    if detected and detected[0] in ATS_PROBES:
        pairs.append((detected[0], detected[1], True))
    if seed.get("exact"):
        return pairs                      # the URL names the board; guessing the name on every ATS would only add noise and load
    for slug in slug_candidates(seed["name"]):
        for ats in ATS_PROBES:
            if (ats, slug, True) not in pairs:
                pairs.append((ats, slug, False))
    return pairs


def _probe_one(args: Tuple[Dict[str, Any], str, str, bool]) -> Tuple[Dict[str, Any], str, str, bool, bool, Union[int, str]]:
    seed, ats, slug, from_url = args
    method, url, body = ATS_PROBES[ats](slug)
    ok, status_info = _probe(method, url, body, ats=ats)
    return seed, ats, slug, from_url, ok, status_info


def _tidy_name(name: str) -> str:
    """A board's own name without the stray spaces and invisible marks boards carry ("Deliveroo ", "\u200eConnectWise")."""
    return " ".join("".join(ch for ch in name if unicodedata.category(ch) != "Cf").split())


def _or_error(fn: Any, seed_name: str, ats: str, board: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Run one board check; if it raises (a payload with a null field, say), return a rejected report row instead of ending
    the whole run (T111: a harvested board did exactly that, 8 minutes into a Greenhouse run)."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.warning("checking %s/%s for %s failed: %s", ats, board, seed_name, e)
        return {"seed": seed_name, "verdict": f"error: {type(e).__name__}: {str(e)[:80]}", "accepted": False, "ats": ats,
                "board": board}


def _under(places: Places, fn: Any, *args: Any) -> Any:
    """Run `fn` in this worker thread with `places` as its places (`places.using`)."""
    with using(places):
        return fn(*args)


def _is_refused_or_failed_probe(status_info: Union[int, str]) -> bool:
    if status_info in (404, "404", 200, "200"):
        return False
    if str(status_info).startswith("200"):
        return False
    return True


def discover(seeds: List[Dict[str, Any]], workers: int = 40,
             places: Optional[Places] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (verified companies.json entries, report rows for every seed). A board is accepted for `places` (default the
    active ones, India unless configured): it needs a job there, and its entry records them when they are not India (T139)."""
    places = places or active_places()
    tag = {} if places.india_only() else {"places": places.search_names()}   # Workday, Oracle HCM, Eightfold, Phenom: all checked
    board_seeds = [s for s in seeds if not {"workday", "oracle_hcm", "eightfold", "phenom", "workday_auto"} & s.keys()]
    tasks = [(s, ats, slug, fu) for s in board_seeds for ats, slug, fu in _probe_pairs(s)]
    print(f"Phase 1/3 — probing {len(tasks)} (ATS, slug) pairs for {len(board_seeds)} companies...")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        probe_results = list(ex.map(_probe_one, tasks))
    hits = [(s, a, sl, fu) for s, a, sl, fu, ok, st in probe_results if ok]

    # One more pass on failed probes: 2 at a time
    retry_probes = [(idx, tasks[idx]) for idx, res in enumerate(probe_results)
                    if not res[4] and _is_refused_or_failed_probe(res[5])]
    if retry_probes:
        with ThreadPoolExecutor(max_workers=2) as ex:
            retried = list(ex.map(_probe_one, [t for _, t in retry_probes]))
            for (idx, _), new_res in zip(retry_probes, retried):
                probe_results[idx] = new_res
                if new_res[4]:
                    hits.append((new_res[0], new_res[1], new_res[2], new_res[3]))

    print(f"  {len(hits)} live board(s) found")

    print(f"Phase 2/3 — verifying live boards (jobs, identity, {places.label()} presence)...")
    with ThreadPoolExecutor(max_workers=max(1, min(12, workers))) as ex:     # --workers bounds this phase too (T111)
        evaluated = list(ex.map(lambda h: _under(places, _or_error, evaluate_board, h[0]["name"], h[1], h[2], h[0]["name"],
                                                 h[1], h[2], h[3]), hits))
    # One more pass on not checked evaluated boards: 2 at a time
    again_eval = [i for i, r in enumerate(evaluated) if str(r.get("verdict", "")).startswith("not checked")]
    if again_eval:
        with ThreadPoolExecutor(max_workers=2) as ex:
            retried_eval = list(ex.map(lambda h: _under(places, _or_error, evaluate_board, h[0]["name"], h[1], h[2],
                                                        h[0]["name"], h[1], h[2], h[3]), [hits[i] for i in again_eval]))
            for i, new_r in zip(again_eval, retried_eval):
                evaluated[i] = new_r

    wd_seeds = [s for s in seeds if "workday" in s]
    auto_rows: List[Dict[str, Any]] = []
    auto = [s for s in seeds if s.get("workday_auto")]
    if auto:
        print(f"Looking for the Workday tenants of {len(auto)} companies by name (robots.txt of <name>.<data centre>.myworkdayjobs.com)...")
        with ThreadPoolExecutor(max_workers=workers) as ex:
            found = list(ex.map(lambda s: workday_tenant_for(s["name"]), auto))
        for s, sites in zip(auto, found):
            if not sites:
                auto_rows.append({"seed": s["name"], "verdict": "no Workday tenant named like it", "accepted": False,
                                  "ats": "workday"})
            wd_seeds += [{"name": s["name"], "workday": {"tenant": t, "dc": dc, "site": site}, "confirm_name": True}
                         for t, dc, site in sites]
        print(f"  {sum(1 for f in found if f)} of {len(auto)} have a tenant, {len(wd_seeds) - len([s for s in seeds if 'workday' in s])} sites")
    oracle_seeds = [s for s in seeds if "oracle_hcm" in s]
    eightfold_seeds = [s for s in seeds if "eightfold" in s]
    phenom_seeds = [s for s in seeds if "phenom" in s]
    print(f"Phase 3/3 — checking {len(wd_seeds)} Workday tenants, {len(oracle_seeds)} Oracle HCM sites, "
          f"{len(eightfold_seeds)} Eightfold sites and {len(phenom_seeds)} Phenom sites...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        wd_rows = list(ex.map(lambda s: _under(places, _or_error, evaluate_workday, s["name"], "workday", s["workday"]["tenant"],
                                               s["name"], s["workday"]["tenant"], s["workday"]["dc"], s["workday"]["site"],
                                               *([True] if s.get("confirm_name") else [])),      # T148: a tenant found by name
                              wd_seeds))
        for ats, group in (("oracle_hcm", oracle_seeds), ("eightfold", eightfold_seeds), ("phenom", phenom_seeds)):
            wd_rows += list(ex.map(lambda s, a=ats: _under(places, _or_error, evaluate_entry, s["name"], a,
                                                           str(s[a].get("host", "")), s["name"], {"ats": a, **s[a]}), group))

    company_cache, slug_cache = load_linkedin_cache(default_linkedin_cache())
    verified: List[Dict[str, Any]] = []
    rows: List[Dict[str, Any]] = []
    by_seed: Dict[str, List[Dict[str, Any]]] = {}
    for r in evaluated:
        by_seed.setdefault(r["seed"], []).append(r)
    probes_by_seed: Dict[str, List[Tuple[str, str, bool, Union[int, str]]]] = {}
    for s, ats, slug, fu, ok, status_info in probe_results:
        probes_by_seed.setdefault(s["name"], []).append((ats, slug, ok, status_info))

    for seed in board_seeds:
        cands = by_seed.get(seed["name"], [])
        if seed.get("exact"):             # rows are grouped by name, which exact seeds may share: keep this seed's own board
            own = detect_ats(seed["url"])
            cands = [r for r in cands if own and (r["ats"], r["board"]) == tuple(own)]
        rows.extend(cands)
        good = [r for r in cands if r["accepted"]]
        if not cands:
            pairs = probes_by_seed.get(seed["name"], [])
            if seed.get("exact"):
                own = detect_ats(seed["url"])
                pairs = [p for p in pairs if own and (p[0], p[1]) == tuple(own)]
            failed = [p for p in pairs if not p[2] and _is_refused_or_failed_probe(p[3])]
            if failed:
                f_ats, f_slug, _, f_status = next((p for p in failed if str(p[3]).startswith("429") or "429" in str(p[3])), failed[0])
                logger.warning("probe of %s/%s for %s was refused or failed: %s", f_ats, f_slug, seed["name"], f_status)
                status_desc = f"HTTP {f_status}" if isinstance(f_status, int) or str(f_status).isdigit() else str(f_status)
                rows.append({"seed": seed["name"], "verdict": f"not checked: {status_desc} on {f_ats}/{f_slug}", "accepted": False,
                             "ats": f_ats, "board": f_slug})
            else:
                rows.append({"seed": seed["name"], "verdict": "no live board on supported ATSs", "accepted": False})
        if good:
            best = max(good, key=lambda r: (r["identity"].startswith("slug from"), r["place_jobs"], r["prefilter_pass"]))
            name = display_name(seed["name"])
            if seed.get("exact"):         # the board's own name where the ATS publishes one, else the label we gave it
                name = _tidy_name(_board_name(best["ats"], best["board"]) or name)
            # A board lists its jobs whole, so its entry records only the countries where it has one (T144); the others'
            # light checks read the first page of a search, which cannot say where else there are jobs.
            seen = {"places": best["seen_places"]} if tag and best.get("seen_places") else tag
            verified.append({
                "name": name, "ats": best["ats"], "slug": best["board"],
                "headcount": match_headcount(seed["name"], best["board"], company_cache, slug_cache), **seen,
            })
    rows.extend(wd_rows)
    rows.extend(auto_rows)
    # A tenant may have several sites (Careers, Campus, ...) and merge_companies keeps one entry per company, the first it
    # meets: put the site with the most India jobs first (a stable sort, so ties keep the seed order). T111.
    for r in sorted((r for r in wd_rows if r["accepted"]), key=lambda r: -(r.get("place_jobs") or 0)):
        ident = r["entry"].get("tenant") or r["entry"].get("host", "").split(".")[0]
        verified.append({**r["entry"], "headcount": match_headcount(r["seed"], ident, company_cache, slug_cache), **tag})
    return verified, rows


def reverify_existing(entries: List[Dict[str, Any]], workers: int = 12) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Re-check current companies.json entries with the same rules; drop the ones that fail.

    Identity is trusted (these were curated), so only liveness, India presence,
    staleness and the known-bad list are re-tested.
    """
    def check_one(c: Dict[str, Any]) -> Dict[str, Any]:
        if c.get("ats") == "workday":
            return evaluate_workday(c["name"], c["tenant"], c["dc"], c["site"])
        if c.get("ats") in ("oracle_hcm", "amazon", "eightfold", "phenom"):
            return evaluate_entry(c["name"], {k: v for k, v in c.items() if k not in ("name", "headcount")})
        return evaluate_board(c["name"], c["ats"], c["slug"], from_url=True)

    def check(c: Dict[str, Any]) -> Dict[str, Any]:
        # A board that makes our fetch raise is not known to be dead: keep it and say so, never crash the monthly check (T111).
        # Each entry is checked against the places it was accepted for: India, or its "places" (T139).
        row = _under(entry_places(c, active_places().home), _or_error, check_one, c["name"], c.get("ats", ""), _board_ident(c), c)
        if str(row.get("verdict", "")).startswith(("error", "not checked")):
            row["accepted"] = True
        return row

    # The entries are sorted by ATS, so 12 workers would hit one host with a dozen requests at once; Workable and Recruitee
    # answer that with HTTP 429, which the adapters read as an empty board (T111: 34 of 86 Workable boards "dead").
    order = _spread_by_ats(entries)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        done = list(ex.map(check, [entries[i] for i in order]))
    rows: List[Dict[str, Any]] = [{} for _ in entries]
    for i, r in zip(order, done):
        rows[i] = r
    # An empty answer may be a rate limit: ask once more, two at a time. A real answer ("no India jobs") is final.
    again = [i for i, r in enumerate(rows) if str(r.get("verdict", "")).startswith("not checked")
             or (not r.get("accepted") and str(r.get("verdict", "")).startswith("no open jobs"))]
    if again:
        with ThreadPoolExecutor(max_workers=2) as ex:
            for i, r in zip(again, ex.map(check, [entries[i] for i in again])):
                rows[i] = r
    kept = [c for c, r in zip(entries, rows) if r["accepted"]]
    return kept, rows


def _spread_by_ats(entries: List[Dict[str, Any]]) -> List[int]:
    """Indices of `entries` in an order where neighbours rarely share an ATS (round-robin over the ATS groups)."""
    groups: Dict[str, List[int]] = {}
    for i, c in enumerate(entries):
        groups.setdefault(c.get("ats", ""), []).append(i)
    queues = list(groups.values())
    order: List[int] = []
    while any(queues):
        for q in queues:
            if q:
                order.append(q.pop(0))
    return order


def recheck_companies(entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Re-verify every entry; re-discover failures by name (handles ATS migrations).

    Returns (new company list, report rows). A failing entry is replaced when its
    company verifies on another board (headcount kept), otherwise it is removed — the
    name stays in scripts/company_seeds.txt, so a later full discover can re-add it.
    """
    kept, rows = reverify_existing(entries)
    failed = [(c, r) for c, r in zip(entries, rows) if not r["accepted"]]
    found: List[Dict[str, Any]] = []
    disc_rows: List[Dict[str, Any]] = []
    groups: Dict[Tuple[str, ...], List[Dict[str, Any]]] = {}
    for c, _ in failed:                   # re-discovered for the places each was accepted for (T139)
        groups.setdefault(tuple(c.get("places") or ()), []).append(c)
    for names, group in groups.items():
        f, d = discover([{"name": c["name"]} for c in group], places=entry_places({"places": list(names)}, active_places().home))
        found += f
        disc_rows += d
    by_name = {f["name"].lower(): f for f in found}
    replacements: List[Dict[str, Any]] = []
    summary: List[Dict[str, Any]] = []
    for c, r in failed:
        new = by_name.get(display_name(c["name"]).lower()) or by_name.get(c["name"].lower())
        old_board = f"{c['ats']}/{c.get('slug') or c.get('tenant') or _board_ident(c)}"
        if new:
            new = {**new, "name": c["name"], "headcount": c.get("headcount", new.get("headcount", "Unknown"))}
            replacements.append(new)
            summary.append({"seed": c["name"], "verdict": f"REPLACED {old_board} ({r['verdict']}) -> "
                                                          f"{new['ats']}/{new.get('slug') or new.get('tenant')}"})
        else:
            summary.append({"seed": c["name"], "verdict": f"REMOVED {old_board}: {r['verdict']}"})
    return merge_companies(kept, replacements), summary + rows + disc_rows


# Careers-page fingerprints, used to measure which ATS platforms the target companies
# use (and so which adapters are worth building). Order = tie-break priority.
ATS_FINGERPRINTS: List[Tuple[str, re.Pattern]] = [(name, re.compile(rx, re.IGNORECASE)) for name, rx in [
    ("workday", r"myworkdayjobs\.com|myworkdaysite\.com"),
    ("greenhouse", r"greenhouse\.io"),
    ("lever", r"jobs\.lever\.co|api\.lever\.co"),
    ("ashby", r"ashbyhq\.com"),
    ("smartrecruiters", r"smartrecruiters\.com"),
    ("workable", r"apply\.workable\.com|workable\.com/"),
    ("recruitee", r"recruitee\.com"),
    ("personio", r"jobs\.personio\.(de|com)"),
    ("oracle_hcm", r"oraclecloud\.com/hcmUI|\.fa\.[a-z0-9]+\.oraclecloud\.com|CandidateExperience"),
    ("taleo", r"taleo\.net"),
    ("successfactors", r"successfactors\.(com|eu)|sapsf\.(com|eu)"),
    ("eightfold", r"eightfold\.ai"),
    ("phenom", r"phenompeople\.com"),
    ("icims", r"icims\.com"),
    ("avature", r"avature\.net"),
    ("jobvite", r"jobvite\.com"),
    ("brassring", r"brassring\.com"),
    ("darwinbox", r"darwinbox\.(in|com)"),
    ("keka", r"\.keka\.com"),
    ("zoho_recruit", r"zohorecruit\.(com|in)"),
    ("freshteam", r"freshteam\.com"),
    ("skillate", r"skillate\.com"),
    ("peoplestrong", r"peoplestrong\.com"),
    ("param", r"param\.ai"),
    ("recruiterflow", r"recruiterflow\.com"),
    ("breezy", r"breezy\.hr"),
    ("bamboohr", r"bamboohr\.com"),
    ("teamtailor", r"teamtailor\.com"),
    ("kula", r"kula\.ai"),
]]
JOB_BOARD_FINGERPRINTS: List[Tuple[str, re.Pattern]] = [(name, re.compile(rx, re.IGNORECASE)) for name, rx in [
    ("instahyre", r"instahyre\.com"),
    ("naukri", r"naukri\.com"),
    ("linkedin", r"linkedin\.com/(jobs|company/[^\"' ]+/jobs)"),
    ("wellfound", r"wellfound\.com|angel\.co/company"),
    ("cutshort", r"cutshort\.io"),
]]


def fingerprint_ats(text: str) -> List[str]:
    """ATS platforms referenced in a careers page (most-referenced first), then job boards
    as "job_board:<name>". Empty when nothing recognisable is found."""
    hits = [(len(rx.findall(text)), -i, name) for i, (name, rx) in enumerate(ATS_FINGERPRINTS)]
    found = [name for n, _, name in sorted(hits, reverse=True) if n]
    found += [f"job_board:{name}" for name, rx in JOB_BOARD_FINGERPRINTS if rx.search(text)]
    return found


_LINK_RE = re.compile(r"""href=["']([^"'#]+)["']""", re.IGNORECASE)
_STRONG_JOB_WORD_RE = re.compile(r"open|position|job|vacanc|requisition", re.IGNORECASE)
_JOB_WORD_RE = re.compile(r"open|position|job|vacanc|requisition|career|hiring|join|work-with-us", re.IGNORECASE)
_ASSET_RE = re.compile(r"\.(css|js|png|jpe?g|gif|svg|ico|woff2?|pdf)(\?|$)", re.IGNORECASE)


def _job_links(base_url: str, html: str, limit: int = 3) -> List[str]:
    """Links on a careers landing page that probably lead to the job list."""
    links: List[str] = []
    for href in _LINK_RE.findall(html):
        full = urljoin(base_url, href)
        if (not full.startswith("http") or full.rstrip("/") == base_url.rstrip("/")
                or not _JOB_WORD_RE.search(href) or _ASSET_RE.search(full)
                or any(rx.search(full) for _, rx in JOB_BOARD_FINGERPRINTS)):
            continue
        if full not in links:
            links.append(full)
    links.sort(key=lambda u: not _STRONG_JOB_WORD_RE.search(u))  # "open positions" before "careers"
    return links[:limit]


def ats_census(entries: List[Dict[str, Any]], workers: int = 16) -> List[Dict[str, Any]]:
    """Fetch each entry's careers URL and fingerprint the ATS behind it, following up to
    three job-looking links one level deep when the landing page names no ATS."""
    headers = {**DEFAULT_HEADERS, "Accept": "text/html,application/xhtml+xml,*/*"}

    def one(e: Dict[str, Any]) -> Dict[str, Any]:
        row = {"seed": e["name"], "url": e.get("url", "")}
        try:
            r = requests.get(e["url"], headers=headers, timeout=20, allow_redirects=True)
            page_text = f"{r.url}\n{r.text[:3_000_000]}"
            found = fingerprint_ats(page_text)
            verdict = f"HTTP {r.status_code}"
            if not [f for f in found if not f.startswith("job_board:")] and r.status_code == 200:
                for link in _job_links(r.url, r.text):
                    try:
                        r2 = requests.get(link, headers=headers, timeout=15, allow_redirects=True)
                    except Exception:
                        continue
                    deeper_text = f"{r2.url}\n{r2.text[:3_000_000]}"
                    deeper = [f for f in fingerprint_ats(deeper_text) if not f.startswith("job_board:")]
                    if deeper:
                        found = deeper + found
                        page_text = deeper_text
                        verdict += f" via {link}"
                        break
            platform = found[0] if found else "unknown/custom"
            row.update({"platform": platform, "all_platforms": ",".join(found),
                        "board_url": evidence_url(page_text, platform),
                        "final_url": r.url, "verdict": verdict})
        except Exception as ex:
            row.update({"platform": "fetch failed", "all_platforms": "", "board_url": "", "final_url": "",
                        "verdict": str(ex)[:80]})
        return row

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one, entries))


CENSUS_FIELDS = ["seed", "platform", "all_platforms", "board_url", "url", "final_url", "verdict"]

# Platforms with an adapter: census hits on these can be fed straight into discover.
SEEDABLE_PLATFORMS = {"greenhouse", "lever", "ashby", "smartrecruiters", "workable", "recruitee",
                      "personio", "workday", "oracle_hcm"}
_URL_RE = re.compile(r"""https?://[^\s"'<>\\]+""")  # stops at JSON-escape backslashes


def evidence_url(text: str, platform: str) -> str:
    """First absolute URL in `text` that matches `platform`'s fingerprint ("" if none)."""
    rx = dict(ATS_FINGERPRINTS).get(platform)
    if rx is None:
        return ""
    for m in _URL_RE.finditer(text):
        if rx.search(m.group(0)):
            return m.group(0).rstrip(".,;)")
    return ""


def census_seed_lines(rows: List[Dict[str, Any]]) -> List[str]:
    """"Name | board URL" seed lines for census hits on platforms we have adapters for."""
    return [f"{r['seed']} | {r['board_url']}" for r in rows
            if r.get("platform") in SEEDABLE_PLATFORMS and r.get("board_url") and detect_ats(r["board_url"])]


def write_report(rows: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=REPORT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in REPORT_FIELDS})


def append_seeds(seeds_path: Path, pasted: List[Tuple[str, str]], raw_lines: Optional[List[str]] = None) -> int:
    """Append pasted names (and raw seed-format lines) not already in the seeds file;
    returns how many lines were added."""
    text = seeds_path.read_text(encoding="utf-8") if seeds_path.exists() else ""
    existing = parse_seeds(text)
    known = {s["name"].lower() for s in existing}
    present = {ln.strip() for ln in text.splitlines()}
    new_lines = [ln.strip() for ln in (raw_lines or []) if ln.strip() and ln.strip() not in present]
    for name, url in pasted:
        if name.lower() in known:
            continue
        known.add(name.lower())
        new_lines.append(f"{name} | {url}" if url and detect_ats(url) else name)
    if new_lines:
        with seeds_path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n# ── added via discover --add ({date.today().isoformat()}) ──\n" + "\n".join(new_lines) + "\n")
    return len(new_lines)


def main(argv: Optional[List[str]] = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    opts = {"--seeds": "scripts/company_seeds.txt", "--report": "discovery_report.csv",
            "--out": "verified_companies.json", "--merge": "", "--workers": "40", "--places": "",
            "--add": "", "--add-file": ""}
    # Unknown arguments used to be ignored, so `--help` or a mistyped flag ran a full discovery of every seed (T67).
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        sys.exit(0)
    value_flags, bool_flags = set(opts) | {"--census", "--emit-seeds"}, {"--recheck", "--no-recheck"}
    i = 0
    while i < len(argv):
        if argv[i] in value_flags and i + 1 < len(argv):
            i += 2
        elif argv[i] in bool_flags:
            i += 1
        else:
            sys.exit(f"discover: unknown or incomplete argument {argv[i]!r}; see `autopilot discover --help`")
    for i, a in enumerate(argv):
        if a in opts and i + 1 < len(argv):
            opts[a] = argv[i + 1]
    recheck = "--no-recheck" not in argv
    config = {}
    if Path("config.json").is_file():
        try:
            config = json.loads(Path("config.json").read_text(encoding="utf-8"))
        except ValueError:
            config = {}
    candidate = dict(config.get("candidate") or {})
    if opts["--places"]:
        candidate["countries"] = opts["--places"]
    places = configure_places(places_from_config({"candidate": candidate}))
    if not places.india_only():
        print(f"Places: a board needs a job in {places.label()} (new entries record them; existing ones are checked against "
              f"their own)")

    if "--census" in argv:
        path = argv[argv.index("--census") + 1]
        entries = [e for e in parse_seeds(Path(path).read_text(encoding="utf-8")) if e.get("url")]
        rows = ats_census(entries)
        with open(opts["--report"], "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=CENSUS_FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        from collections import Counter
        for platform, n in Counter(r["platform"] for r in rows).most_common():
            print(f"  {platform:<24}{n:>4}")
        print(f"Census of {len(rows)} careers pages -> {opts['--report']}")
        if "--emit-seeds" in argv:
            out_path = Path(argv[argv.index("--emit-seeds") + 1])
            lines = census_seed_lines(rows)
            out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"{len(lines)} seed line(s) for supported platforms -> {out_path} "
                  f"(verify with: discover --add-file {out_path} --merge companies.json)")
        return

    if "--recheck" in argv:
        target = Path(opts["--merge"] or "companies.json")
        existing = json.loads(target.read_text(encoding="utf-8"))
        updated, report_rows = recheck_companies(existing)
        write_report(report_rows, opts["--report"])
        changes = [r for r in report_rows if r["verdict"].startswith(("REPLACED", "REMOVED"))]
        Path(opts["--out"]).write_text(json.dumps(changes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        target.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for r in changes:
            print(f"  {r['seed']}: {r['verdict']}")
        not_checked = sum(1 for r in report_rows if str(r.get("verdict", "")).startswith("not checked"))
        nc_text = f", {not_checked} not checked" if not_checked else ""
        print(f"Recheck: {len(existing)} -> {len(updated)} companies ({len(changes)} changed{nc_text}). "
              f"Review with: git diff {target}")
        return

    seeds_path = Path(opts["--seeds"])
    asked_to_add = "--add" in argv or "--add-file" in argv     # given at all: an empty value ("$NAMES" unset) still asks to add
    add_text = opts["--add"].replace(",", "\n")
    if opts["--add-file"]:
        add_text += "\n" + Path(opts["--add-file"]).read_text(encoding="utf-8")
    if asked_to_add and not [ln for ln in add_text.splitlines() if ln.strip() and not ln.strip().startswith("#")]:
        # An empty paste (a census that found no board) must not fall through to the whole seeds file: hours of network (T132).
        sys.exit("discover: the --add / --add-file input holds no company name, so there is nothing to check "
                 f"(without --add / --add-file, discover checks every line of {seeds_path}).")
    if add_text.strip():
        # "Name | url" / "Name | workday | tenant | dc | site" lines are already seed format.
        seed_lines = [ln for ln in add_text.splitlines() if "|" in ln and not ln.strip().startswith("<")]
        free_text = "\n".join(ln for ln in add_text.splitlines() if ln not in seed_lines)
        pasted = extract_company_names(free_text)
        added = append_seeds(seeds_path, pasted, raw_lines=seed_lines)
        seeds = parse_seeds("\n".join(seed_lines)) + [
            {"name": n, **({"url": u} if u and detect_ats(u) else {})} for n, u in pasted]
        print(f"{len(seeds)} companies parsed from paste; {added} new line(s) appended to {seeds_path}")
    else:
        seeds = parse_seeds(seeds_path.read_text(encoding="utf-8"))
    verified, rows = discover(seeds, workers=int(opts["--workers"]))
    write_report(rows, opts["--report"])
    Path(opts["--out"]).write_text(json.dumps(verified, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    companies = len({v["name"].lower() for v in verified})     # a Workday tenant's sites are one company; --merge keeps one
    not_checked = sum(1 for r in rows if str(r.get("verdict", "")).startswith("not checked"))
    nc_text = f", {not_checked} not checked" if not_checked else ""
    print(f"\n{companies}/{len(seeds)} companies verified ({len(verified)} boards or sites{nc_text}) -> {opts['--out']} "
          f"(report: {opts['--report']})")
    if opts["--merge"]:
        target = Path(opts["--merge"])
        existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() else []
        if recheck:
            kept, recheck_rows = reverify_existing(existing)
        else:
            kept, recheck_rows = existing, [{"seed": c["name"], "accepted": True, "verdict": "not rechecked"} for c in existing]
        for c, r in zip(existing, recheck_rows):
            if not r["accepted"]:
                print(f"  dropping existing {c['name']} ({c['ats']}): {r['verdict']}")
        collisions = name_collisions(kept, verified)
        for col in collisions:
            print(f"  name collision: {col['seed']} ({col['ats']}/{col['board']}) not added; "
                  f"existing {col['existing_name']} ({col['existing_board_full']})")
        write_report(rows + collisions + [{**r, "seed": f"[existing] {r['seed']}"} for r in recheck_rows], opts["--report"])
        merged = merge_companies(kept, verified)
        target.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Merged into {target}: {len(existing)} existing ({len(kept)} still valid) -> {len(merged)} companies")


if __name__ == "__main__":
    main()
