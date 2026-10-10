"""Workday direct ATS adapter via client CXS endpoint."""
from __future__ import annotations

import logging
import re
import time
from typing import Any, List, Optional, Tuple
from urllib.parse import urlparse

from job_hunt.adapters.base import DEFAULT_HEADERS, http_get, http_post, mark_incomplete, strip_html
from job_hunt.models import JobPosting
from job_hunt.prefilter import title_is_candidate

logger = logging.getLogger(__name__)

# Workday caps a page at 20. Unfiltered, big tenants return their newest ~20 global
# (mostly US) postings, so we full-text search for India and page up to MAX_JOBS.
PAGE_SIZE = 20
MAX_JOBS = 2000  # Accenture has 2,000 India-search results, in arbitrary order (2026-10-06); Target had 302, Nvidia 276
SEARCH_TEXT = "India"

# Per-tenant wall-clock budget. Paging and the detail calls (only for "N Locations" jobs whose title can pass
# the pre-filter, T23) count against it; once spent, remaining multi-location items keep their list text and paging stops.
BOARD_BUDGET_SECONDS = 600.0

# List items with several locations show "5 Locations" instead of cities.
# List-API placeholders instead of a city; the detail call has the real location(s). "Location Negotiable":
# Accenture, 498 of its 2,000 India-search results, 8 of 12 sampled were in India (2026-10-07, T65).
_MULTI_LOCATION_RE = re.compile(r"^(\d+\s+Locations?|Location\s+Negotiable)$", re.IGNORECASE)


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
    """Fetch open India-matching jobs from Workday JSON CXS endpoint.

    Endpoint: POST https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
    """
    start = time.monotonic()
    base_domain = f"{tenant}.{dc}.myworkdayjobs.com"
    cxs_base = f"https://{base_domain}/wday/cxs/{tenant}/{site}"
    url = f"{cxs_base}/jobs"

    jobs: List[JobPosting] = []
    seen_paths: set[str] = set()
    total: int | None = None

    for offset in range(0, MAX_JOBS, PAGE_SIZE):
        if total is not None and offset >= total:
            break
        if time.monotonic() - start > budget:
            logger.warning("Workday %s/%s: %.0fs budget spent, stopping at %d jobs", tenant, site, budget, len(jobs))
            mark_incomplete(f"budget {budget:.0f}s spent at {len(jobs)} jobs")
            break
        payload: dict[str, Any] = {
            "appliedFacets": {},
            "limit": PAGE_SIZE,
            "offset": offset,
            "searchText": SEARCH_TEXT,
        }
        try:
            resp = http_post(url, headers=DEFAULT_HEADERS, json=payload, timeout=15)
            if resp.status_code == 404:
                logger.debug("Workday board not found for %s/%s (HTTP 404)", tenant, site)
                break
            resp.raise_for_status()
            data = resp.json()
            if total is None and "total" in data:
                try:
                    total = int(data["total"])
                except (ValueError, TypeError):
                    total = None
            postings = data.get("jobPostings", [])
        except Exception as e:
            # Keep whatever earlier pages returned.
            logger.warning("Workday fetch failed for %s/%s at offset %d: %s", tenant, site, offset, e)
            mark_incomplete(f"page failed at offset {offset}")
            break

        if not postings:
            break

        new_in_page = 0
        for item in postings:
            external_path = item.get("externalPath", "")
            if external_path:
                if external_path in seen_paths:
                    continue
                seen_paths.add(external_path)
            new_in_page += 1

            title = item.get("title", "").strip()
            location = item_location(item)
            posted_on = item.get("postedOn", "")
            description = ""

            # The detail call is one HTTP request per job; skip it when the title alone rules the job out (T23).
            if (external_path and _MULTI_LOCATION_RE.match(location) and title_is_candidate(title)
                    and time.monotonic() - start <= budget):
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
    return jobs
