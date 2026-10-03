"""Ashby direct ATS adapter."""
from __future__ import annotations

import logging
from typing import List

import requests

from job_hunt.adapters.base import DEFAULT_HEADERS, strip_html
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)


def fetch_ashby(slug: str) -> List[JobPosting]:
    """Fetch open jobs from Ashby HQ public job board API.

    Endpoint: https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
    """
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if resp.status_code == 404:
            logger.debug("Ashby board not found for %s (HTTP 404)", slug)
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Ashby fetch failed for %s: %s", slug, e)
        return []

    jobs: List[JobPosting] = []
    for item in data.get("jobs", []):
        job_id = str(item.get("id", ""))
        title = item.get("title", "").strip()
        location = item.get("location", "Not specified") or "Not specified"
        is_remote = bool(item.get("isRemote")) or "remote" in location.lower() or "remote" in title.lower()

        desc_plain = item.get("descriptionPlain", "").strip()
        desc_html = item.get("descriptionHtml", "")
        desc_text = desc_plain if desc_plain else strip_html(desc_html)

        job_url = item.get("jobUrl") or f"https://jobs.ashbyhq.com/{slug}/{job_id}"
        posted_at = item.get("publishedAt") or ""

        jobs.append(
            JobPosting(
                global_id=f"ashby:{slug}:{job_id}",
                ats="ashby",
                company=slug,
                title=title,
                location=location,
                is_remote=is_remote,
                url=job_url,
                description_text=desc_text,
                posted_at=posted_at,
            )
        )
    return jobs
