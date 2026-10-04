"""Workday direct ATS adapter via client CXS endpoint."""
from __future__ import annotations

import logging
import re
import time
from typing import Any, List, Tuple
from urllib.parse import urlparse

from job_hunt.adapters.base import DEFAULT_HEADERS, http_get, http_post, strip_html
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)

# Workday caps a page at 20. Unfiltered, big tenants return their newest ~20 global
# (mostly US) postings, so we full-text search for India and page up to MAX_JOBS.
PAGE_SIZE = 20
MAX_JOBS = 500  # Target had 302, Nvidia 276 India-search results (2026-10-05)
SEARCH_TEXT = "India"

# Per-tenant wall-clock budget. Detail calls dominate (~100 s for Nvidia/Salesforce);
# once spent, remaining multi-location items keep their list text and paging stops.
BOARD_BUDGET_SECONDS = 600.0

# List items with several locations show "5 Locations" instead of cities.
_MULTI_LOCATION_RE = re.compile(r"^\d+\s+Locations?$", re.IGNORECASE)


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
            location = item.get("locationsText", "Not specified") or "Not specified"
            posted_on = item.get("postedOn", "")
            description = ""

            if external_path and _MULTI_LOCATION_RE.match(location) and time.monotonic() - start <= budget:
                detail_locs, description = _fetch_detail(cxs_base, external_path)
                location = detail_locs or location

            is_remote = "remote" in location.lower() or "remote" in title.lower()

            # Job ID from bulletFields or external_path
            job_id = ""
            bullet_fields = item.get("bulletFields", [])
            if bullet_fields:
                job_id = str(bullet_fields[0])
            elif external_path:
                job_id = external_path.split("_")[-1] if "_" in external_path else external_path.strip("/")

            job_url = f"https://{base_domain}/{site}{external_path}" if external_path else f"https://{base_domain}/{site}"

            jobs.append(
                JobPosting(
                    global_id=f"workday:{tenant}:{job_id or title}",
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
    return jobs
