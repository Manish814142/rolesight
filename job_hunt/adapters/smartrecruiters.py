"""SmartRecruiters direct ATS adapter."""
from __future__ import annotations

import logging
from typing import List

from job_hunt.adapters.base import DEFAULT_HEADERS, http_get
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)


def fetch_smartrecruiters(slug: str) -> List[JobPosting]:
    """Fetch open jobs from SmartRecruiters public posting API.

    Endpoint: https://api.smartrecruiters.com/v1/companies/{slug}/postings
    """
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"

    try:
        resp = http_get(url, headers=DEFAULT_HEADERS, params={"limit": 100}, timeout=15)
        if resp.status_code == 404:
            logger.debug("SmartRecruiters board not found for %s (HTTP 404)", slug)
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("SmartRecruiters fetch failed for %s: %s", slug, e)
        return []

    jobs: List[JobPosting] = []
    for item in data.get("content", []):
        job_id = str(item.get("id", ""))
        title = item.get("name", "").strip()

        loc = item.get("location", {}) or {}
        loc_parts = [loc.get("city"), loc.get("region"), loc.get("country")]
        location = ", ".join(p for p in loc_parts if p) or loc.get("fullLocation", "Not specified")

        is_remote = (
            bool(loc.get("remote"))
            or "remote" in location.lower()
            or "remote" in title.lower()
        )

        job_url = f"https://jobs.smartrecruiters.com/{slug}/{job_id}"
        posted_at = item.get("releasedDate") or ""

        jobs.append(
            JobPosting(
                global_id=f"smartrecruiters:{slug}:{job_id}",
                ats="smartrecruiters",
                company=slug,
                title=title,
                location=location,
                is_remote=is_remote,
                url=job_url,
                description_text="",  # List endpoint doesn't include full JD
                posted_at=posted_at,
            )
        )
    return jobs
