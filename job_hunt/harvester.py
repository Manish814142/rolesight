"""Multi-ATS matrix harvester.

Reads candidate company slugs from india.yml and the LinkedIn headcount cache,
probes all 7 single-slug ATS engines concurrently plus a fixed set of Workday
tenants, and writes only verified active boards to companies.json.

Usage:
    python -m job_hunt harvest [--yaml PATH] [--linkedin PATH] [--out PATH]
    autopilot harvest
"""
from __future__ import annotations

import json
import logging
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import requests
import yaml

from job_hunt.adapters.base import DEFAULT_HEADERS
from job_hunt.company_builder import load_linkedin_cache, match_headcount
from job_hunt.validator import KNOWN_CORRECTIONS

logger = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_YAML = "/home/user/Downloads/india.yml"
DEFAULT_LINKEDIN = "/home/user/Downloads/linkedin-size-filter-backup-2026-10-03.json"
DEFAULT_OUT = "companies.json"

# Same-slug boards that belong to another employer, or are abandoned stubs: removed from companies.json on
# evidence (CLAUDE.md), so a harvest must not bring them back. (ats, slug), compared in lower case.
EXCLUDED_BOARDS = {
    ("ashby", "navi"),               # San Francisco company, not Navi Technologies
    ("ashby", "bounce"),             # Lisbon / San Francisco, not Bounce (India)
    ("personio", "edelweiss"),       # German / UK postings
    ("personio", "josh"),
    ("smartrecruiters", "nobroker"),    # abandoned stubs
    ("smartrecruiters", "upstox"),
    ("smartrecruiters", "turtlemint"),
    ("smartrecruiters", "whatfix"),
}


def is_excluded_board(entry: Dict[str, Any]) -> bool:
    return (str(entry.get("ats", "")).lower(), str(entry.get("slug", "")).lower()) in EXCLUDED_BOARDS
PROBE_TIMEOUT = 8

# ── Workday tenants (known India-relevant MNCs) ───────────────────────────────
WORKDAY_TENANTS: List[Dict[str, str]] = [
    {"name": "Target India", "tenant": "target", "dc": "wd5", "site": "targetcareers"},
    {"name": "Walmart Global Tech", "tenant": "walmart", "dc": "wd5", "site": "WalmartExternal"},
    {"name": "BrowserStack", "tenant": "browserstack", "dc": "wd3", "site": "External"},
    {"name": "Adobe India", "tenant": "adobe", "dc": "wd5", "site": "external_experienced"},
    {"name": "Salesforce", "tenant": "salesforce", "dc": "wd12", "site": "External_Career_Site"},
    {"name": "Autodesk", "tenant": "autodesk", "dc": "wd1", "site": "Ext"},
    {"name": "Nvidia", "tenant": "nvidia", "dc": "wd5", "site": "NVIDIAExternalCareerSite"},
]

_WD_RE = re.compile(
    r"https?://([a-zA-Z0-9_\-]+)\.(wd[0-9]+)\.myworkdayjobs\.com"
    r"/(?:[a-zA-Z_\-]+/)?([a-zA-Z0-9_\-]+)"
)

# ── ATS probe factories ───────────────────────────────────────────────────────
ATS_PROBES: Dict[str, Any] = {
    "greenhouse": lambda slug: (
        "GET", f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", None
    ),
    "lever": lambda slug: (
        "GET", f"https://api.lever.co/v0/postings/{slug}?mode=json", None
    ),
    "ashby": lambda slug: (
        "GET", f"https://api.ashbyhq.com/posting-api/job-board/{slug}", None
    ),
    "smartrecruiters": lambda slug: (
        "GET", f"https://api.smartrecruiters.com/v1/companies/{slug}/postings", None
    ),
    "recruitee": lambda slug: (
        "GET", f"https://{slug}.recruitee.com/api/offers", None
    ),
    "workable": lambda slug: (
        "GET", f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true", None
    ),
    "personio": lambda slug: (
        "GET", f"https://{slug}.jobs.personio.de/xml?language=en", None
    ),
}


def _has_jobs(ats: Optional[str], resp: requests.Response) -> bool:
    """Verify that a response from an ATS platform contains at least one real job."""
    if resp.status_code != 200:
        return False
    if ats is None:
        return True
    try:
        if ats in ("greenhouse", "ashby", "workable"):
            data = resp.json()
            return isinstance(data, dict) and len(data.get("jobs", [])) > 0
        elif ats == "lever":
            data = resp.json()
            return isinstance(data, list) and len(data) > 0
        elif ats == "smartrecruiters":
            data = resp.json()
            return (
                isinstance(data, dict)
                and len(data.get("content", [])) > 0
                and data.get("totalFound", 0) > 0
            )
        elif ats == "recruitee":
            data = resp.json()
            return isinstance(data, dict) and len(data.get("offers", [])) > 0
        elif ats == "personio":
            text = resp.text
            if "<position" in text:
                try:
                    root = ET.fromstring(resp.content)
                    return len(root.findall("position")) > 0
                except Exception:
                    return "<position>" in text or "<position " in text
            return False
        elif ats == "workday":
            data = resp.json()
            return isinstance(data, dict) and len(data.get("jobPostings", [])) > 0
    except Exception:
        return False
    return False


def _probe(
    method: str,
    url: str,
    body: Optional[Dict[str, Any]],
    timeout: int = PROBE_TIMEOUT,
    ats: Optional[str] = None,
) -> Tuple[bool, Union[int, str]]:
    try:
        if method == "POST":
            resp = requests.post(url, json=body, headers=DEFAULT_HEADERS, timeout=timeout)
        else:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        has_jobs = _has_jobs(ats, resp)
        status_info: Union[int, str] = (
            resp.status_code
            if has_jobs
            else (f"{resp.status_code} (0 jobs)" if resp.status_code == 200 else resp.status_code)
        )
        return has_jobs, status_info
    except Exception as exc:
        return False, str(exc)[:80]


def probe_slug_first_active_ats(
    name: str, slug: str, headcount: str, preferred_ats: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Probe ATS engines and stop at the first working ATS with active jobs.

    The declared (india.yml) ATS is tried first. A hit on any other ATS is a
    same-slug guess that may belong to a different company, so it is tagged
    with `ats_fallback_from` for manual review.
    """
    order = list(ATS_PROBES)
    if preferred_ats in ATS_PROBES:
        order.remove(preferred_ats)
        order.insert(0, preferred_ats)
    for ats in order:
        method, url, body = ATS_PROBES[ats](slug)
        ok, status = _probe(method, url, body, timeout=PROBE_TIMEOUT, ats=ats)
        if ok:
            logger.debug("[ACTIVE] %s @ %s (%s) -> active jobs found", name, ats, slug)
            entry: Dict[str, Any] = {"name": name, "ats": ats, "slug": slug, "headcount": headcount}
            if preferred_ats and ats != preferred_ats:
                entry["ats_fallback_from"] = preferred_ats
            return entry
        else:
            logger.debug("[SKIP]   %s @ %s (%s) -> %s", name, ats, slug, status)
    return None


def probe_slug_across_all_ats(
    name: str, slug: str, headcount: str
) -> List[Dict[str, Any]]:
    """Single-ATS probe wrapper for backward compatibility."""
    entry = probe_slug_first_active_ats(name, slug, headcount)
    return [entry] if entry else []


def probe_workday_tenant(
    tenant_info: Dict[str, str], headcount: str
) -> Optional[Dict[str, Any]]:
    name = tenant_info["name"]
    tenant = tenant_info["tenant"]
    dc = tenant_info["dc"]
    site = tenant_info["site"]
    url = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    payload: Dict[str, Any] = {
        "appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""
    }
    ok, status = _probe("POST", url, payload, timeout=PROBE_TIMEOUT, ats="workday")
    if ok:
        return {
            "name": name,
            "ats": "workday",
            "tenant": tenant,
            "dc": dc,
            "site": site,
            "headcount": headcount,
        }
    logger.debug("[SKIP]   %s (workday) -> %s", name, status)
    return None


def parse_workday_url(url: str) -> Optional[Tuple[str, str, str]]:
    m = _WD_RE.search(url)
    return (m.group(1), m.group(2), m.group(3)) if m else None


def load_candidates(
    yaml_path: str, linkedin_path: str
) -> List[Tuple[str, str, str, str]]:
    """Return (name, slug, headcount, declared_ats) for every company in the YAML.

    validator.KNOWN_CORRECTIONS (ATS migrations / renamed slugs) override india.yml.
    """
    p = Path(yaml_path)
    if not p.exists():
        raise FileNotFoundError(f"YAML not found: {yaml_path}")

    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    company_cache, slug_cache = load_linkedin_cache(linkedin_path)
    seen: set = set()
    candidates: List[Tuple[str, str, str, str]] = []

    for declared_ats, items in raw.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "").strip()
            slug = item.get("slug", "").strip()
            if not name or not slug:
                continue
            ats = declared_ats
            correction = KNOWN_CORRECTIONS.get(name.lower())
            if correction:
                ats, slug = correction["ats"], correction["slug"]
            dedup_key = f"{name.lower()}:{slug.lower()}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Headcount is badge metadata only: the LinkedIn cache is stale
            # (Sigmoid/Fractal tagged 11-50), so it never excludes a company.
            headcount = match_headcount(name, slug, company_cache, slug_cache)
            candidates.append((name, slug, headcount, ats))

    return candidates


def run_harvest(
    yaml_path: str = DEFAULT_YAML,
    linkedin_path: str = DEFAULT_LINKEDIN,
    out_path: str = DEFAULT_OUT,
    max_workers: int = 30,
) -> List[Dict[str, Any]]:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    candidates = load_candidates(yaml_path, linkedin_path)
    # Deduplicate candidate list by company name
    unique_candidates: List[Tuple[str, str, str, str]] = []
    seen_cand_names: Set[str] = set()
    for name, slug, hc, ats in candidates:
        norm = name.strip().lower()
        if norm not in seen_cand_names:
            seen_cand_names.add(norm)
            unique_candidates.append((name, slug, hc, ats))
    candidates = unique_candidates
    print(f"Loaded {len(candidates)} candidate companies (after name deduplication)")

    verified: List[Dict[str, Any]] = []
    seen_companies: Set[str] = set()

    # ── Phase 1: 7 single-slug ATS engines (stops at first working ATS) ────
    print(
        f"\nPhase 1/2 — Probing {len(candidates)} companies across {len(ATS_PROBES)} ATS engines "
        f"({max_workers} workers, stopping at first working ATS with active jobs)..."
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(probe_slug_first_active_ats, name, slug, headcount, ats): name
            for name, slug, headcount, ats in candidates
        }
        done = 0
        for future in as_completed(futures):
            done += 1
            company_name = futures[future]
            try:
                entry = future.result()
                if entry and is_excluded_board(entry):
                    print(f"  [EXCLUDED] {entry['name']:<28} {entry['ats']}/{entry['slug']} was removed on evidence")
                    entry = None
                if entry:
                    comp_key = entry["name"].strip().lower()
                    if comp_key not in seen_companies:
                        seen_companies.add(comp_key)
                        verified.append(entry)
                        fallback = entry.get("ats_fallback_from")
                        print(
                            f"  [ACTIVE] {entry['name']:<30} "
                            f"{entry['ats']:<16} slug={entry['slug']}"
                            + (f"  (FALLBACK: india.yml says {fallback})" if fallback else "")
                        )
            except Exception as exc:
                logger.warning("Error probing %s: %s", company_name, exc)
            if done % 25 == 0 or done == len(candidates):
                print(f"  Progress: {done}/{len(candidates)} companies probed")

    # ── Phase 2: Workday tenants ───────────────────────────────────────────
    print(f"\nPhase 2/2 — Probing {len(WORKDAY_TENANTS)} Workday tenants...")
    company_cache, slug_cache = load_linkedin_cache(linkedin_path)

    from concurrent.futures import Future  # noqa: PLC0415

    with ThreadPoolExecutor(max_workers=10) as executor:
        wd_futures: Dict[Future[Optional[Dict[str, Any]]], str] = {}
        for wt in WORKDAY_TENANTS:
            if wt["name"].strip().lower() in seen_companies:
                continue
            hc = match_headcount(wt["name"], wt["tenant"], company_cache, slug_cache)
            wd_futures[executor.submit(probe_workday_tenant, wt, hc)] = wt["name"]

        for wd_future in as_completed(wd_futures):
            wt_name = wd_futures[wd_future]
            try:
                wd_entry = wd_future.result()
                if wd_entry:
                    comp_key = wd_entry["name"].strip().lower()
                    if comp_key not in seen_companies:
                        seen_companies.add(comp_key)
                        verified.append(wd_entry)
                        print(
                            f"  [ACTIVE] {wd_entry['name']:<30} workday  "
                            f"tenant={wd_entry['tenant']}.{wd_entry['dc']}/{wd_entry['site']}"
                        )
                else:
                    print(f"  [SKIP]   {wt_name} (workday)")
            except Exception as exc:
                logger.warning("Error probing Workday %s: %s", wt_name, exc)

    # ── Write output ───────────────────────────────────────────────────────
    verified.sort(key=lambda e: (e["ats"], e["name"].lower()))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(verified, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ats_counts = Counter(e["ats"] for e in verified)
    print(f"\n{'=' * 55}")
    print(f"Harvest complete — {len(verified)} verified active companies")
    print("Breakdown by ATS:")
    for ats, count in sorted(ats_counts.items()):
        print(f"  {ats:<20} {count:>3}")
    print(f"Output: {out_path}")
    print(f"{'=' * 55}")
    return verified


def main(argv: Optional[List[str]] = None) -> None:
    argv = argv or sys.argv[1:]
    yaml_path = DEFAULT_YAML
    linkedin_path = DEFAULT_LINKEDIN
    out_path = DEFAULT_OUT
    workers = 30
    force = "--force" in argv

    i = 0
    while i < len(argv):
        if argv[i] == "--yaml" and i + 1 < len(argv):
            yaml_path = argv[i + 1]
            i += 2
        elif argv[i] == "--linkedin" and i + 1 < len(argv):
            linkedin_path = argv[i + 1]
            i += 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            out_path = argv[i + 1]
            i += 2
        elif argv[i] == "--workers" and i + 1 < len(argv):
            workers = int(argv[i + 1])
            i += 2
        else:
            i += 1

    if Path(out_path).exists() and not force:
        print(
            f"Refusing to overwrite {out_path}: harvest rebuilds the list from scratch and would drop curated entries.\n"
            "Write to a scratch file (--out /tmp/x.json) and diff it, add companies with `autopilot discover --add-file`, "
            "or pass --force.",
            file=sys.stderr,
        )
        sys.exit(2)

    run_harvest(yaml_path, linkedin_path, out_path, max_workers=workers)


if __name__ == "__main__":
    main()
