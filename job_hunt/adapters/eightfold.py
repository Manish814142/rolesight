"""Eightfold careers-site adapter (the PCSX endpoints the careers page itself calls).

  GET https://{host}/api/pcsx/search?domain={domain}&query=&location=India&start={n}&sort_by=timestamp   (one per country, T137)
      -> data.count, data.positions (10 per page: id, name, locations, postedTs, positionUrl, ...)
  GET https://{host}/api/pcsx/position_details?position_id={id}&domain={domain}&hl=en
      -> data.jobDescription (HTML)

`host` is the careers site's host (tenant.eightfold.ai, or a custom domain such as apply.ukg.com) and `domain`
the employer's domain that Eightfold keys the tenant on (micron.com). Not every site that mentions Eightfold
exposes this API; /api/apply/v2/jobs answers 403 ("Not authorized for PCSX") on the tenants checked, while
/api/pcsx/search answered 200 on Micron, UKG, Twilio and PayPal (2026-10-06).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests

from job_hunt.adapters.base import (
    DEFAULT_HEADERS,
    http_get,
    mark_incomplete,
    stop_at_window,
    strip_html,
)
from job_hunt.models import JobPosting
from job_hunt.places import active_places

logger = logging.getLogger(__name__)

PAGE_SIZE = 10
MAX_JOBS = 1000
# Not "relevance": that order shifts between requests, so pages overlap and some positions are never served
# (Qualcomm: 583 of 594 ids; a time-sorted traversal returned all 594, 2026-10-06).
SORT_BY = "timestamp"

# Eightfold answers HTTP 429 to a handful of quick requests (Qualcomm: the 3rd page, 2026-10-06; spaced requests
# then succeeded). A 429 is retried after these pauses (seconds); results pages are also spaced.
RETRY_DELAYS = (3, 6, 12, 24, 48)
PAGE_PAUSE = 1.0
BOARD_BUDGET_SECONDS = 600.0


def _get(url: str, params: Dict[str, Any]) -> requests.Response:
    """GET that pauses and retries on HTTP 429; any other response (or the last 429) is returned as is."""
    for delay in RETRY_DELAYS:
        resp = http_get(url, headers=DEFAULT_HEADERS, params=params, timeout=20, retry_429=False)
        if resp.status_code != 429:
            return resp
        time.sleep(delay)
    return http_get(url, headers=DEFAULT_HEADERS, params=params, timeout=20, retry_429=False)


def _posted(epoch: Any) -> str:
    try:
        return datetime.fromtimestamp(int(epoch), timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def fetch_eightfold(host: str, domain: str, company: str = "") -> List[JobPosting]:
    """Positions of one Eightfold careers site in the person's countries: one search per country name (the search is
    scoped server-side; "India" alone unless config.json names others, T137), sharing the seen set and the budget."""
    url = f"https://{host}/api/pcsx/search"
    jobs: List[JobPosting] = []
    seen: set = set()
    began = time.monotonic()
    for location in active_places().search_names():
        if not _search_location(location, url, host, domain, company, began, jobs, seen):
            break
    return jobs


def _search_location(location_name: str, url: str, host: str, domain: str, company: str, began: float,
                     jobs: List[JobPosting], seen: set) -> bool:
    """Page through one location's search, appending new positions; False once the budget is spent."""
    start = 0
    while start < MAX_JOBS:
        if time.monotonic() - began > BOARD_BUDGET_SECONDS:
            logger.warning("Eightfold %s: %.0fs budget spent, stopping at %d jobs", host, BOARD_BUDGET_SECONDS, len(jobs))
            mark_incomplete(f"budget {BOARD_BUDGET_SECONDS:.0f}s spent at {len(jobs)} jobs")
            return False
        params: Dict[str, Any] = {"domain": domain, "query": "", "location": location_name,
                                  "start": start, "sort_by": SORT_BY}
        try:
            resp = _get(url, params)
            resp.raise_for_status()
            data = resp.json().get("data") or {}
        except Exception as e:
            # Keep whatever earlier pages returned.
            logger.warning("Eightfold fetch failed for %s at start=%d: %s", host, start, e)
            mark_incomplete(f"page failed at start={start}")
            break
        positions = data.get("positions") or []
        new = 0
        for p in positions:
            pid = p.get("id")
            if pid is None or pid in seen:
                continue
            seen.add(pid)
            new += 1
            location = "; ".join(loc for loc in (p.get("locations") or []) if loc)
            path = p.get("positionUrl") or f"/careers/job/{pid}"
            jobs.append(JobPosting(
                global_id=f"eightfold:{domain}:{pid}",
                ats="eightfold",
                company=company or domain,
                title=(p.get("name") or "").strip(),
                location=location,
                is_remote=(p.get("workLocationOption") or "").lower() == "remote" or "remote" in location.lower(),
                url=path if path.startswith("http") else f"https://{host}{path}",
                posted_at=_posted(p.get("postedTs")),
            ))
        start += PAGE_SIZE
        total = data.get("count")
        if new == 0 or len(positions) < PAGE_SIZE or (isinstance(total, int) and start >= total):
            break
        if stop_at_window(j.posted_at for j in jobs[-new:]):   # sort_by=timestamp is newest first (T02)
            break
        time.sleep(PAGE_PAUSE)
    else:  # stopped at MAX_JOBS with more positions left
        mark_incomplete(f"cap {MAX_JOBS}")
    return True


def fetch_description(job: JobPosting) -> str:
    """Full description of one position from position_details ("" if unavailable). The employer domain and the
    position id are in global_id (eightfold:{domain}:{id}); the host is the job URL's."""
    parts = job.global_id.split(":")
    if len(parts) != 3 or parts[0] != "eightfold":
        return ""
    _, domain, position_id = parts
    host = job.url.split("/")[2] if job.url.startswith("http") else ""
    if not host:
        return ""
    resp = _get(f"https://{host}/api/pcsx/position_details", {"position_id": position_id, "domain": domain, "hl": "en"})
    if resp.status_code != 200:
        return ""
    return strip_html((resp.json().get("data") or {}).get("jobDescription") or "")
