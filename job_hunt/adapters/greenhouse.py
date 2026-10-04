"""Greenhouse direct ATS adapter."""
from __future__ import annotations

import logging
from typing import List

from job_hunt.adapters.base import DEFAULT_HEADERS, http_get, strip_html
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)


def fetch_greenhouse(slug: str, eu: bool = False) -> List[JobPosting]:
    """Fetch all open jobs from Greenhouse official board API.

    Endpoint:
      US: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
      EU: https://boards.eu.greenhouse.io/v1/boards/{slug}/jobs?content=true
    """
    domain = "boards.eu.greenhouse.io" if eu else "boards-api.greenhouse.io"
    url = f"https://{domain}/v1/boards/{slug}/jobs?content=true"

    try:
        resp = http_get(url, headers=DEFAULT_HEADERS, timeout=15)
        if resp.status_code == 404:
            logger.debug("Greenhouse board not found for %s (HTTP 404)", slug)
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Greenhouse fetch failed for %s: %s", slug, e)
        return []

    jobs: List[JobPosting] = []
    for item in data.get("jobs", []):
        job_id = str(item.get("id", ""))
        title = item.get("title", "").strip()
        loc_data = item.get("location", {})
        location = loc_data.get("name", "").strip() if isinstance(loc_data, dict) else str(loc_data)

        # Check if remote in location or offices
        is_remote = "remote" in location.lower() or "remote" in title.lower()
        content = item.get("content", "")
        desc_text = strip_html(content)
        job_url = item.get("absolute_url") or f"https://boards.greenhouse.io/{slug}/jobs/{job_id}"
        # first_published is the posting date; updated_at moves on every edit.
        posted_at = item.get("first_published") or item.get("updated_at") or ""

        jobs.append(
            JobPosting(
                global_id=f"greenhouse:{slug}:{job_id}",
                ats="greenhouse",
                company=slug,
                title=title,
                location=location or "Not specified",
                is_remote=is_remote,
                url=job_url,
                description_text=desc_text,
                posted_at=posted_at,
            )
        )
    return jobs
