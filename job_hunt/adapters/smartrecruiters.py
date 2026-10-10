"""SmartRecruiters direct ATS adapter."""
from __future__ import annotations

import logging
from typing import List

from job_hunt.adapters.base import DEFAULT_HEADERS, http_get, mark_incomplete, strip_html
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)


PAGE_SIZE = 100  # API maximum
MAX_JOBS = 2000  # ServiceNow had 706 (2026-10-04); bound runaway boards


def _fetch_all_postings(url: str, slug: str) -> List[dict]:
    """Page through ?limit=100&offset=N until totalFound; keeps earlier pages on error."""
    items: List[dict] = []
    offset = 0
    while offset < MAX_JOBS:
        try:
            resp = http_get(url, headers=DEFAULT_HEADERS, params={"limit": PAGE_SIZE, "offset": offset}, timeout=15)
            if resp.status_code == 404:
                logger.debug("SmartRecruiters board not found for %s (HTTP 404)", slug)
                break
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("SmartRecruiters fetch failed for %s at offset %d: %s", slug, offset, e)
            mark_incomplete(f"page failed at offset {offset}")
            break
        page = data.get("content", [])
        items.extend(page)
        offset += PAGE_SIZE
        if len(page) < PAGE_SIZE or offset >= int(data.get("totalFound") or 0):
            break
    else:  # stopped at MAX_JOBS with more postings left
        mark_incomplete(f"cap {MAX_JOBS}")
    return items


# Role first, company blurb last.
_SECTION_ORDER = ("jobDescription", "qualifications", "additionalInformation", "companyDescription")


def fetch_description(job: JobPosting) -> str:
    """Full description of one posting (the list endpoint has none).

    GET https://api.smartrecruiters.com/v1/companies/{slug}/postings/{id}; job.global_id
    is "smartrecruiters:{slug}:{id}".
    """
    _, slug, job_id = job.global_id.split(":", 2)
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{job_id}"
    resp = http_get(url, headers=DEFAULT_HEADERS, timeout=15)
    if resp.status_code != 200:
        return ""
    sections = (resp.json().get("jobAd") or {}).get("sections") or {}
    parts = []
    for key in _SECTION_ORDER:
        sec = sections.get(key) or {}
        text = strip_html(sec.get("text") or "")
        if text:
            parts.append(f"{sec.get('title') or key}:\n{text}")
    return "\n\n".join(parts)


def fetch_smartrecruiters(slug: str) -> List[JobPosting]:
    """Fetch open jobs from SmartRecruiters public posting API.

    Endpoint: https://api.smartrecruiters.com/v1/companies/{slug}/postings
    """
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"

    jobs: List[JobPosting] = []
    for item in _fetch_all_postings(url, slug):
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
