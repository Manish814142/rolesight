"""Recruitee direct ATS adapter."""
from __future__ import annotations

import logging
from typing import List

import requests

from job_hunt.adapters.base import DEFAULT_HEADERS, strip_html
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)


def fetch_recruitee(slug: str) -> List[JobPosting]:
    """Fetch open jobs from Recruitee public offers API.

    Endpoint: https://{slug}.recruitee.com/api/offers
    """
    url = f"https://{slug}.recruitee.com/api/offers"

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if resp.status_code == 404:
            logger.debug("Recruitee board not found for %s (HTTP 404)", slug)
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Recruitee fetch failed for %s: %s", slug, e)
        return []

    jobs: List[JobPosting] = []
    for item in data.get("offers", []):
        job_id = str(item.get("id", ""))
        title = item.get("title", "").strip()
        location = item.get("location", "Not specified") or "Not specified"
        is_remote = "remote" in location.lower() or "remote" in title.lower()

        desc_html = item.get("description", "")
        req_html = item.get("requirements", "")
        desc_parts = [strip_html(desc_html), strip_html(req_html)]
        desc_text = "\n\n".join(p for p in desc_parts if p).strip()

        job_url = item.get("careers_url") or f"https://{slug}.recruitee.com/o/{item.get('slug', job_id)}"
        posted_at = item.get("published_at") or ""

        jobs.append(
            JobPosting(
                global_id=f"recruitee:{slug}:{job_id}",
                ats="recruitee",
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
