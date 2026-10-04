"""Amazon Jobs adapter (amazon.jobs public search JSON)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from job_hunt.adapters.base import DEFAULT_HEADERS, http_get, strip_html
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.amazon.jobs/en/search.json"
PAGE_SIZE = 100
MAX_JOBS = 4000  # India had 2,329 open roles on 2026-10-05


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
            break
        page = data.get("jobs", [])
        for item in page:
            location = item.get("normalized_location") or item.get("location") or "Not specified"
            title = (item.get("title") or "").strip()
            description = "\n\n".join(strip_html(item.get(k) or "") for k in
                                       ("description_short", "basic_qualifications", "preferred_qualifications"))
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
    return jobs
