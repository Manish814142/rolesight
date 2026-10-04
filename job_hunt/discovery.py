"""Verify candidate companies against public ATS boards and build companies.json entries.

A company is added only when a board is proven to be (1) live — at least one open job,
(2) the right employer — board name matches, or the company is named in its job
descriptions, or the slug came from the company's own careers URL, and (3) hiring in
India — at least one job located in India. This avoids the failure modes seen before:
empty boards, and same-slug boards that belong to a different company (Navi, Bounce).

Usage:
    python -m job_hunt discover --seeds scripts/company_seeds.txt \\
        --report /tmp/discovery.csv --out /tmp/verified.json [--merge companies.json]

Seeds file, one company per line ('#' comments allowed):
    Stripe
    Jupiter Money | https://jobs.lever.co/jupiter
    BlackBerry | workday | bb | wd3 | BlackBerry
"""
from __future__ import annotations

import csv
import json
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from job_hunt.adapters import detect_ats, fetch_company_jobs
from job_hunt.adapters.base import DEFAULT_HEADERS
from job_hunt.company_builder import CORPORATE_SUFFIX_RE, load_linkedin_cache, match_headcount
from job_hunt.harvester import ATS_PROBES, DEFAULT_LINKEDIN, _probe
from job_hunt.models import JobPosting
from job_hunt.prefilter import (
    LOCATION_INDIA_COUNTRY_CODE,
    LOCATION_INDIA_PATTERN,
    should_evaluate_job,
)

logger = logging.getLogger(__name__)

# Boards proven to be wrong or useless (see CLAUDE.md): same-slug boards of a different
# employer, or third-party stub postings. Never accepted, whatever the probe says.
KNOWN_BAD_BOARDS = {
    ("ashby", "navi"), ("ashby", "bounce"), ("personio", "edelweiss"), ("personio", "josh"),
    ("workable", "eatclub"), ("lever", "porter"), ("smartrecruiters", "nobroker"),
    ("smartrecruiters", "upstox"), ("smartrecruiters", "turtlemint"), ("smartrecruiters", "whatfix"),
}

# A board whose newest posting is older than this is treated as abandoned. Seen in the
# wild: SmartRecruiters boards answering 200 with 1-2 postings from 2015-2020.
MAX_NEWEST_AGE_DAYS = 180

REPORT_FIELDS = [
    "seed", "verdict", "ats", "board", "jobs", "india_jobs", "prefilter_pass", "newest_age_days",
    "identity", "sample_titles",
]


# ── pure helpers ──────────────────────────────────────────────────────────────

def _words(name: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", name.lower())


def _core_words(name: str) -> List[str]:
    stripped = CORPORATE_SUFFIX_RE.sub(" ", name.lower())
    return _words(stripped) or _words(name)


def slug_candidates(name: str) -> List[str]:
    """Likely ATS slugs for a company name, most specific first, no duplicates."""
    full, core = _words(name), _core_words(name)
    cands = ["".join(full), "-".join(full), "".join(core), "-".join(core)]
    if len(core) > 1 and len(core[0]) >= 5:
        cands.append(core[0])  # "Tower Research Capital" -> "tower"; short words collide too often
    seen: List[str] = []
    for c in cands:
        if c and c not in seen:
            seen.append(c)
    return seen


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
        key = (name.lower(), is_workday)
        if not name or key in seen:
            continue
        seen.add(key)
        seed: Dict[str, Any] = {"name": name}
        if is_workday:
            seed["workday"] = {"tenant": parts[2], "dc": parts[3], "site": parts[4]}
        elif len(parts) >= 2 and parts[1]:
            seed["url"] = parts[1]
        seeds.append(seed)
    return seeds


def name_matches(seed_name: str, board_name: str) -> bool:
    """True when one name's core words are a leading run of the other's."""
    a, b = _core_words(seed_name), _core_words(board_name)
    if not a or not b:
        return False
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return long_[: len(short)] == short


def newest_age_days(jobs: List[JobPosting], now: Optional[datetime] = None) -> Optional[int]:
    """Days since the most recent parseable posted_at (ISO dates); None if none parse."""
    today = (now or datetime.now(timezone.utc)).date()
    dates: List[date] = []
    for j in jobs:
        try:
            dates.append(date.fromisoformat((j.posted_at or "")[:10]))
        except ValueError:
            continue
    return (today - max(dates)).days if dates else None


def accept_board(
    ats: str, slug: str, jobs: int, india_jobs: int, identity_ok: bool,
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
    if india_jobs <= 0:
        return False, "no India jobs"
    return True, "verified"


def merge_companies(existing: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Existing entries win; a new entry is dropped if its name or board is already present."""
    def board_key(c: Dict[str, Any]) -> Tuple[str, str]:
        ident = c.get("slug") or f"{c.get('tenant')}:{c.get('dc')}:{c.get('site')}"
        return c.get("ats", ""), str(ident).lower()

    def name_key(c: Dict[str, Any]) -> str:
        return " ".join(_core_words(c["name"]))  # "Mindtickle India" == "Mindtickle"

    out = list(existing)
    names = {name_key(c) for c in out}
    boards = {board_key(c) for c in out}
    for c in new:
        if name_key(c) in names or board_key(c) in boards:
            continue
        out.append(c)
        names.add(name_key(c))
        boards.add(board_key(c))
    return sorted(out, key=lambda c: (c.get("ats", ""), c["name"].lower()))


def _is_india(location: str) -> bool:
    return bool(LOCATION_INDIA_PATTERN.search(location or "") or LOCATION_INDIA_COUNTRY_CODE.search(location or ""))


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
    core = " ".join(_core_words(seed_name))
    pattern = re.compile(r"\b" + re.escape(core).replace(r"\ ", r"[\s\-]?") + r"\b", re.IGNORECASE)
    mentions = sum(1 for j in jobs if pattern.search(f"{j.title}\n{j.description_text}"))
    return mentions > 0, f"named in {mentions}/{len(jobs)} job descriptions"


def evaluate_board(seed_name: str, ats: str, slug: str, from_url: bool = False) -> Dict[str, Any]:
    jobs = fetch_company_jobs({"name": seed_name, "ats": ats, "slug": slug})
    india = sum(1 for j in jobs if _is_india(j.location))
    passing = [j for j in jobs if should_evaluate_job(j)[0]]
    identity_ok, how = _identity(seed_name, ats, slug, jobs, from_url) if jobs else (False, "no jobs")
    age = newest_age_days(jobs)
    ok, verdict = accept_board(ats, slug, len(jobs), india, identity_ok, age)
    return {
        "seed": seed_name, "verdict": verdict, "accepted": ok, "ats": ats, "board": slug,
        "jobs": len(jobs), "india_jobs": india, "prefilter_pass": len(passing),
        "newest_age_days": "" if age is None else age, "identity": how,
        "sample_titles": "; ".join(j.title[:50] for j in passing[:3]),
    }


def evaluate_workday(seed_name: str, tenant: str, dc: str, site: str) -> Dict[str, Any]:
    """Light check: first page of the India search (the adapter itself paginates to 100)."""
    url = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    row: Dict[str, Any] = {"seed": seed_name, "ats": "workday", "board": f"{tenant}.{dc}/{site}",
                           "identity": "curated tenant", "sample_titles": ""}
    try:
        r = requests.post(url, json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "India"},
                          headers=DEFAULT_HEADERS, timeout=15)
        posts = r.json().get("jobPostings", []) if r.status_code == 200 else []
        status = f"HTTP {r.status_code}"
    except Exception as e:
        posts, status = [], str(e)[:60]
    jobs = [JobPosting("", "workday", seed_name, p.get("title", ""), p.get("locationsText", ""), False, "")
            for p in posts]
    india = sum(1 for j in jobs if _is_india(j.location))
    passing = [j for j in jobs if should_evaluate_job(j)[0]]
    ok, verdict = accept_board("workday", f"{tenant}:{dc}:{site}", len(jobs), india, True)
    row.update({"verdict": verdict if posts else f"{verdict} ({status})", "accepted": ok, "jobs": len(jobs),
                "india_jobs": india, "prefilter_pass": len(passing),
                "sample_titles": "; ".join(j.title[:50] for j in passing[:3]),
                "entry": {"name": seed_name, "ats": "workday", "tenant": tenant, "dc": dc, "site": site}})
    return row


def _probe_pairs(seed: Dict[str, Any]) -> List[Tuple[str, str, bool]]:
    pairs: List[Tuple[str, str, bool]] = []
    detected = detect_ats(seed.get("url", "")) if seed.get("url") else None
    if detected and detected[0] in ATS_PROBES:
        pairs.append((detected[0], detected[1], True))
    for slug in slug_candidates(seed["name"]):
        for ats in ATS_PROBES:
            if (ats, slug, True) not in pairs:
                pairs.append((ats, slug, False))
    return pairs


def _probe_one(args: Tuple[Dict[str, Any], str, str, bool]) -> Optional[Tuple[Dict[str, Any], str, str, bool]]:
    seed, ats, slug, from_url = args
    method, url, body = ATS_PROBES[ats](slug)
    ok, _ = _probe(method, url, body, ats=ats)
    return (seed, ats, slug, from_url) if ok else None


def discover(seeds: List[Dict[str, Any]], workers: int = 40) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (verified companies.json entries, report rows for every seed)."""
    board_seeds = [s for s in seeds if "workday" not in s]
    tasks = [(s, ats, slug, fu) for s in board_seeds for ats, slug, fu in _probe_pairs(s)]
    print(f"Phase 1/3 — probing {len(tasks)} (ATS, slug) pairs for {len(board_seeds)} companies...")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        hits = [h for h in ex.map(_probe_one, tasks) if h]
    print(f"  {len(hits)} live board(s) found")

    print("Phase 2/3 — verifying live boards (jobs, identity, India presence)...")
    with ThreadPoolExecutor(max_workers=12) as ex:
        evaluated = list(ex.map(lambda h: evaluate_board(h[0]["name"], h[1], h[2], h[3]), hits))

    wd_seeds = [s for s in seeds if "workday" in s]
    print(f"Phase 3/3 — checking {len(wd_seeds)} curated Workday tenants...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        wd_rows = list(ex.map(lambda s: evaluate_workday(s["name"], **s["workday"]), wd_seeds))

    company_cache, slug_cache = load_linkedin_cache(DEFAULT_LINKEDIN)
    verified: List[Dict[str, Any]] = []
    rows: List[Dict[str, Any]] = []
    by_seed: Dict[str, List[Dict[str, Any]]] = {}
    for r in evaluated:
        by_seed.setdefault(r["seed"], []).append(r)
    for seed in board_seeds:
        cands = by_seed.get(seed["name"], [])
        rows.extend(cands)
        good = [r for r in cands if r["accepted"]]
        if not cands:
            rows.append({"seed": seed["name"], "verdict": "no live board on supported ATSs", "accepted": False})
        if good:
            best = max(good, key=lambda r: (r["identity"].startswith("slug from"), r["india_jobs"], r["prefilter_pass"]))
            verified.append({
                "name": seed["name"], "ats": best["ats"], "slug": best["board"],
                "headcount": match_headcount(seed["name"], best["board"], company_cache, slug_cache),
            })
    for r in wd_rows:
        rows.append(r)
        if r["accepted"]:
            verified.append({**r["entry"], "headcount": match_headcount(r["seed"], r["entry"]["tenant"], company_cache, slug_cache)})
    return verified, rows


def reverify_existing(entries: List[Dict[str, Any]], workers: int = 12) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Re-check current companies.json entries with the same rules; drop the ones that fail.

    Identity is trusted (these were curated), so only liveness, India presence,
    staleness and the known-bad list are re-tested.
    """
    def check(c: Dict[str, Any]) -> Dict[str, Any]:
        if c.get("ats") == "workday":
            return evaluate_workday(c["name"], c["tenant"], c["dc"], c["site"])
        return evaluate_board(c["name"], c["ats"], c["slug"], from_url=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(check, entries))
    kept = [c for c, r in zip(entries, rows) if r["accepted"]]
    return kept, rows


def write_report(rows: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=REPORT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in REPORT_FIELDS})


def main(argv: Optional[List[str]] = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    opts = {"--seeds": "scripts/company_seeds.txt", "--report": "discovery_report.csv",
            "--out": "verified_companies.json", "--merge": "", "--workers": "40"}
    for i, a in enumerate(argv):
        if a in opts and i + 1 < len(argv):
            opts[a] = argv[i + 1]
    seeds = parse_seeds(Path(opts["--seeds"]).read_text(encoding="utf-8"))
    verified, rows = discover(seeds, workers=int(opts["--workers"]))
    write_report(rows, opts["--report"])
    Path(opts["--out"]).write_text(json.dumps(verified, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{len(verified)}/{len(seeds)} companies verified -> {opts['--out']} (report: {opts['--report']})")
    if opts["--merge"]:
        target = Path(opts["--merge"])
        existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() else []
        kept, recheck_rows = reverify_existing(existing)
        for c, r in zip(existing, recheck_rows):
            if not r["accepted"]:
                print(f"  dropping existing {c['name']} ({c['ats']}): {r['verdict']}")
        write_report(rows + [{**r, "seed": f"[existing] {r['seed']}"} for r in recheck_rows], opts["--report"])
        merged = merge_companies(kept, verified)
        target.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Merged into {target}: {len(existing)} existing ({len(kept)} still valid) -> {len(merged)} companies")


if __name__ == "__main__":
    main()
