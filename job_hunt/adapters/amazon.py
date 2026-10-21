"""Amazon Jobs adapter (amazon.jobs public search JSON)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from job_hunt.adapters.base import DEFAULT_HEADERS, http_get, mark_incomplete, strip_html
from job_hunt.models import JobPosting
from job_hunt.places import active_places

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.amazon.jobs/en/search.json"
PAGE_SIZE = 100
MAX_JOBS = 4000  # India had 2,329 open roles on 2026-10-04


def _iso_date(posted: str) -> str:
    """'October  1, 2026' -> '2026-10-01'; unparseable text is returned unchanged."""
    try:
        return datetime.strptime(" ".join(posted.split()), "%B %d, %Y").date().isoformat()
    except ValueError:
        return posted or ""


def fetch_amazon(country: str = "IND") -> List[JobPosting]:
    """All open Amazon roles in one country, newest first."""
    jobs: List[JobPosting] = []
    offset = 0
    while offset < MAX_JOBS:
        params = {"country": country, "result_limit": PAGE_SIZE, "offset": offset, "sort": "recent"}
        try:
            resp = http_get(SEARCH_URL, headers=DEFAULT_HEADERS, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("Amazon fetch failed at offset %d: %s", offset, e)
            mark_incomplete(f"page failed at offset {offset}")
            break
        page = data.get("jobs", [])
        for item in page:
            location = item.get("normalized_location") or item.get("location") or "Not specified"
            title = (item.get("title") or "").strip()
            # `description_short` is cut mid-sentence at ~200 chars; `description` is the whole text.
            body = item.get("description") or item.get("description_short")
            description = "\n\n".join(strip_html(part or "") for part in
                                       (body, item.get("basic_qualifications"), item.get("preferred_qualifications")))
            jobs.append(JobPosting(
                global_id=f"amazon:{item.get('id_icims') or item.get('id')}",
                ats="amazon",
                company="Amazon",
                title=title,
                location=location,
                is_remote="remote" in location.lower() or "virtual" in location.lower(),
                url=f"https://www.amazon.jobs{item.get('job_path', '')}",
                description_text=description.strip(),
                posted_at=_iso_date(item.get("posted_date", "")),
            ))
        offset += PAGE_SIZE
        if len(page) < PAGE_SIZE or offset >= int(data.get("hits") or 0):
            break
        # No stop at the posted-date window (T02): `sort=recent` is only roughly by date. On 2026-10-10 the 2,338 Indian
        # postings had 980 places where a later job was newer than the one before (by up to 192 days); a stop at the
        # first all-older page (page 18 of 24 for a 7-day window) would have lost 3 jobs of a 14-day window.
    else:  # stopped at MAX_JOBS with more hits left
        mark_incomplete(f"cap {MAX_JOBS}")
    return jobs


def fetch_amazon_places() -> List[JobPosting]:
    """Amazon roles in the person's countries: one search per country code (measured 2026-10-21, T137: GBR 759, DEU 663,
    NLD 34, IRL 227, ARE 64, SGP 134 open roles), "IND" alone unless config.json names other countries. A country with
    no built-in code (one matched by its name only) is skipped."""
    codes = active_places().amazon_codes()
    if len(codes) == 1:
        return fetch_amazon(codes[0])
    if not codes:
        logger.debug("Amazon: none of your countries has a country code, nothing to search")
    jobs: List[JobPosting] = []
    seen: set = set()
    for code in codes:
        for job in fetch_amazon(code):
            if job.global_id not in seen:
                seen.add(job.global_id)
                jobs.append(job)
    return jobs
