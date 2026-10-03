"""Workable direct ATS adapter."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from job_hunt.adapters.base import DEFAULT_HEADERS, strip_html
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)


def fetch_workable(slug: str) -> List[JobPosting]:
    """Fetch open jobs from Workable widget API.

    Endpoint: https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true
    """
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true"

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if resp.status_code in (404, 429):
            logger.debug("Workable fetch returned %s for %s", resp.status_code, slug)
            return []
        resp.raise_for_status()
        data: Dict[str, Any] = resp.json()
    except Exception as e:
        logger.warning("Workable fetch failed for %s: %s", slug, e)
        return []

    jobs: List[JobPosting] = []
    for item in data.get("jobs", []):
        shortcode = item.get("shortcode", "") or item.get("id", "")
        title = item.get("title", "").strip()
        city = item.get("city", "")
        country = item.get("country", "")
        state = item.get("state", "")
        location_parts = [p for p in [city, state, country] if p]
        location = ", ".join(location_parts) or "Not specified"

        is_remote = bool(
            item.get("telecommuting")
            or "remote" in location.lower()
            or "remote" in title.lower()
        )

        desc_raw = item.get("description", "")
        desc_text = strip_html(desc_raw) if desc_raw else ""

        job_url = item.get("url") or f"https://apply.workable.com/j/{shortcode}"

        jobs.append(
            JobPosting(
                global_id=f"workable:{slug}:{shortcode or title}",
                ats="workable",
                company=data.get("name") or slug,
                title=title,
                location=location,
                is_remote=is_remote,
                url=job_url,
                description_text=desc_text,
                posted_at=item.get("published_on", ""),
            )
        )

    return jobs
