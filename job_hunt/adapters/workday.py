"""Workday direct ATS adapter via client CXS endpoint."""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, List, Optional, Tuple
from urllib.parse import urlparse

from job_hunt.adapters.base import (
    DEFAULT_HEADERS,
    http_get,
    http_post,
    mark_incomplete,
    outside_window,
    strip_html,
)
from job_hunt.models import JobPosting
from job_hunt.places import active_places
from job_hunt.prefilter import title_is_candidate

logger = logging.getLogger(__name__)

# Workday caps a page at 20. Unfiltered, big tenants return their newest ~20 global
# (mostly US) postings, so we full-text search for the person's countries (India unless config.json names others: T137,
# `places.Places.workday_terms`) and page up to MAX_JOBS per search term.
PAGE_SIZE = 20
MAX_JOBS = 2000  # Accenture has 2,000 India-search results, in arbitrary order (2026-10-06); Target had 302, Nvidia 276

# Per-tenant wall-clock budget. Paging and the detail calls (only for "N Locations" jobs whose title can pass
# the pre-filter, T23) count against it; once spent, remaining multi-location items keep their list text and paging stops.
BOARD_BUDGET_SECONDS = 600.0

# List items with several locations show "5 Locations" instead of cities.
# List-API placeholders instead of a city; the detail call has the real location(s). "Location Negotiable":
# Accenture, 498 of its 2,000 India-search results, 8 of 12 sampled were in India (2026-10-07, T65).
_MULTI_LOCATION_RE = re.compile(r"^(\d+\s+Locations?|Location\s+Negotiable)$", re.IGNORECASE)


# During Workday's maintenance every tenant answers the jobs POST with a 303 to community.workday.com/maintenance-page;
# `requests` follows it and the HTML is not JSON. One warning per scan says so, the other tenants log at debug (T76).
_maintenance_reported = False
_maintenance_lock = threading.Lock()


def reset_redirect_report() -> None:
    """Called at the start of each scan's fetch, so every scan gets its own warning (the MCP server runs many)."""
    global _maintenance_reported
    with _maintenance_lock:
        _maintenance_reported = False


def _redirected_away(resp: Any, base_domain: str) -> str:
    """The final URL when a redirect took the answer to another host than the tenant's and that answer is not JSON (the
    maintenance page), else "". A cross-host redirect that ends in JSON (a tenant on another data centre) is read as before."""
    url = getattr(resp, "url", None)
    if not isinstance(url, str) or not getattr(resp, "history", None):
        return ""
    if "json" in str((getattr(resp, "headers", None) or {}).get("Content-Type", "")).lower():
        return ""
    host = urlparse(url).netloc
    return url if host and host != base_domain else ""


def redirected_away(resp: Any, base_domain: str) -> str:
    """Public name of `_redirected_away` for the discovery check (T113): the maintenance page's URL, else ""."""
    return _redirected_away(resp, base_domain)


def _report_redirect(tenant: str, site: str, url: str) -> str:
    """Log the redirect (once as a warning per process) and return the reason for mark_incomplete."""
    global _maintenance_reported
    label = "maintenance" if "maintenance" in url.lower() else "redirect"
    with _maintenance_lock:
        first, _maintenance_reported = not _maintenance_reported, True
    message = (f"Workday answered with a redirect to {url} ({label}), not with jobs: its boards that are redirected "
               "come back empty this scan; they are fetched next time and no job of theirs counts as missed")
    if first:
        logger.warning("%s (first seen at %s/%s)", message, tenant, site)
    else:
        logger.debug("Workday %s/%s: %s", tenant, site, message)
    return f"Workday {label}: redirected to {url}"


def workday_global_id(tenant: str, external_path: str, bullet_id: str = "", title: str = "") -> str:
    """Stable id of one posting: the requisition suffix of its externalPath.

    "/job/Noida/Software-Development-Engineer-2_R162019" -> "workday:adobe:R162019".
    The database migration re-derives stored ids from job URLs with this same function.
    """
    if external_path and "_" in external_path:
        job_id = external_path.split("_")[-1]
    elif external_path:
        job_id = external_path.strip("/")
    else:
        job_id = bullet_id
    return f"workday:{tenant}:{job_id or title}"


def workday_global_id_from_url(url: str) -> Optional[str]:
    """workday_global_id for a stored job URL (https://{tenant}.{dc}.myworkdayjobs.com/{site}{externalPath})."""
    parsed = urlparse(url or "")
    site, _, rest = parsed.path.lstrip("/").partition("/")
    if not (parsed.netloc.endswith("myworkdayjobs.com") and site and rest.startswith("job/")):
        return None
    return workday_global_id(parsed.netloc.split(".")[0], "/" + rest)


def item_location(item: dict) -> str:
    """Location of a list item. Accenture leaves `locationsText` empty and puts the city in the second
    bullet field ("Bengaluru, Bdc4C"). Never guessed from the URL: some tenants' slugs are the job title."""
    text = (item.get("locationsText") or "").strip()
    if text:
        return text
    bullets = [str(b).strip() for b in (item.get("bulletFields") or [])[1:] if b and str(b).strip()]
    return bullets[0] if bullets else "Not specified"


def _fetch_detail(cxs_base: str, external_path: str) -> Tuple[str, str]:
    """Return (locations, description_text) from the job detail endpoint, or ("", "")."""
    try:
        resp = http_get(f"{cxs_base}{external_path}", headers=DEFAULT_HEADERS, timeout=15)
        if resp.status_code != 200:
            return "", ""
        info = resp.json().get("jobPostingInfo", {})
    except Exception as e:
        logger.debug("Workday detail fetch failed for %s: %s", external_path, e)
        return "", ""
    locs = [info.get("location") or ""] + list(info.get("additionalLocations") or [])
    return "; ".join(loc for loc in locs if loc), strip_html(info.get("jobDescription", ""))


def is_multi_location(location: str) -> bool:
    """True for the list API's placeholders ("5 Locations", "Location Negotiable") that stand in for the real locations."""
    return bool(_MULTI_LOCATION_RE.match((location or "").strip()))


def fetch_detail_locations(cxs_base: str, external_path: str) -> str:
    """The real location(s) of one posting from its detail call, joined by "; ", or "" when the call fails (T113)."""
    return _fetch_detail(cxs_base, external_path)[0]


def fetch_description(job: JobPosting) -> str:
    """Full description of a single-location survivor ("" if it already has one).

    The list API has no description; "N Locations" items already got theirs from the
    detail call in fetch_workday. job.url is https://{tenant}.{dc}.myworkdayjobs.com/{site}{externalPath}.
    """
    if job.description_text:
        return ""
    u = urlparse(job.url)
    site, _, rest = u.path.lstrip("/").partition("/")
    if not (site and rest.startswith("job/")):
        return ""
    tenant = u.netloc.split(".")[0]
    return _fetch_detail(f"https://{u.netloc}/wday/cxs/{tenant}/{site}", "/" + rest)[1]


def fetch_workday(tenant: str, dc: str, site: str, budget: float = BOARD_BUDGET_SECONDS) -> List[JobPosting]:
    """Fetch open jobs in the person's countries from Workday JSON CXS endpoint: one full-text search per term of
    `active_places().workday_terms()` ("India" alone unless config.json names other countries), all terms sharing the
    seen-job set, the per-term MAX_JOBS cap and one `budget`. A failed term keeps what the others returned (T137).

    Endpoint: POST https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
    """
    start = time.monotonic()
    base_domain = f"{tenant}.{dc}.myworkdayjobs.com"
    cxs_base = f"https://{base_domain}/wday/cxs/{tenant}/{site}"
    url = f"{cxs_base}/jobs"

    jobs: List[JobPosting] = []
    seen_paths: set[str] = set()
    for term in active_places().workday_terms():
        if not _search_term(term, url, cxs_base, base_domain, tenant, site, start, budget, jobs, seen_paths):
            break
    return jobs


def _search_term(term: str, url: str, cxs_base: str, base_domain: str, tenant: str, site: str, start: float, budget: float,
                 jobs: List[JobPosting], seen_paths: set) -> bool:
    """Page through one search term, appending new jobs; False when the whole board is done (404, redirect, budget)."""
    total: int | None = None
    term_paths: set[str] = set()     # this term's own postings: the "a page adds nothing new" stop (T47) is per term (review)

    for offset in range(0, MAX_JOBS, PAGE_SIZE):
        if total is not None and offset >= total:
            break
        if time.monotonic() - start > budget:
            logger.warning("Workday %s/%s: %.0fs budget spent, stopping at %d jobs", tenant, site, budget, len(jobs))
            mark_incomplete(f"budget {budget:.0f}s spent at {len(jobs)} jobs")
            return False
        payload: dict[str, Any] = {
            "appliedFacets": {},
            "limit": PAGE_SIZE,
            "offset": offset,
            "searchText": term,
        }
        try:
            resp = http_post(url, headers=DEFAULT_HEADERS, json=payload, timeout=15)
            if resp.status_code == 404:
                logger.debug("Workday board not found for %s/%s (HTTP 404)", tenant, site)
                return False
            away = _redirected_away(resp, base_domain)
            if away:
                mark_incomplete(_report_redirect(tenant, site, away))
                return False
            resp.raise_for_status()
            data = resp.json()
            if total is None and "total" in data:
                try:
                    total = int(data["total"])
                except (ValueError, TypeError):
                    total = None
            postings = data.get("jobPostings", [])
        except Exception as e:
            # Keep whatever earlier pages (and terms) returned.
            logger.warning("Workday fetch failed for %s/%s at offset %d: %s", tenant, site, offset, e)
            mark_incomplete(f"page failed at offset {offset}")
            break

        if not postings:
            break

        new_in_page = 0
        for item in postings:
            external_path = item.get("externalPath", "")
            if external_path:
                if external_path in term_paths:
                    continue
                term_paths.add(external_path)
            new_in_page += 1
            if external_path:
                if external_path in seen_paths:     # an earlier term returned it ("United Kingdom", then "UK")
                    continue
                seen_paths.add(external_path)

            title = item.get("title", "").strip()
            location = item_location(item)
            posted_on = item.get("postedOn", "")
            description = ""

            # The detail call is one HTTP request per job; skip it when the title alone rules the job out (T23) or the
            # posting is older than the scan's posted-date window (T02; Workday's list is not sorted by date, so
            # the paging itself cannot stop early).
            if (external_path and _MULTI_LOCATION_RE.match(location) and title_is_candidate(title)
                    and not outside_window(posted_on) and time.monotonic() - start <= budget):
                detail_locs, description = _fetch_detail(cxs_base, external_path)
                location = detail_locs or location

            is_remote = "remote" in location.lower() or "remote" in title.lower()

            bullet_fields = item.get("bulletFields") or []
            global_id = workday_global_id(tenant, external_path, str(bullet_fields[0]) if bullet_fields else "", title)

            job_url = f"https://{base_domain}/{site}{external_path}" if external_path else f"https://{base_domain}/{site}"

            jobs.append(
                JobPosting(
                    global_id=global_id,
                    ats="workday",
                    company=tenant,
                    title=title,
                    location=location,
                    is_remote=is_remote,
                    url=job_url,
                    description_text=description,
                    posted_at=posted_on,
                )
            )

        if new_in_page == 0:
            break

        if len(postings) < PAGE_SIZE:
            break
    else:  # ran to MAX_JOBS without reaching the end: the tenant has more (Accenture, in arbitrary order)
        mark_incomplete(f"cap {MAX_JOBS}")
    return True
