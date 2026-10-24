"""Workable direct ATS adapter."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from job_hunt.adapters.base import (
    DEFAULT_HEADERS,
    RATE_LIMIT_PAUSES,
    failure_reason,
    http_get,
    mark_incomplete,
    strip_html,
)
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)


def fetch_workable(slug: str) -> List[JobPosting]:
    """Fetch open jobs from Workable widget API.

    Endpoint: https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true
    """
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true"

    try:
        resp = http_get(url, headers=DEFAULT_HEADERS, timeout=15)
        if resp.status_code == 404:
            logger.debug("Workable board not found for %s (HTTP 404)", slug)
            return []
        if resp.status_code == 429:         # still refused after the pauses of http_get (T114): say so, by name
            logger.warning("Workable board %s answered HTTP 429 (rate limited) after %d tries: its jobs are missing from this fetch",
                           slug, 1 + len(RATE_LIMIT_PAUSES))
            mark_incomplete("HTTP 429 from Workable (rate limited)")
            return []
        resp.raise_for_status()
        data: Dict[str, Any] = resp.json()
    except Exception as e:
        logger.warning("Workable fetch failed for %s: %s", slug, e)
        mark_incomplete(failure_reason(e, resp=locals().get("resp")))
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
