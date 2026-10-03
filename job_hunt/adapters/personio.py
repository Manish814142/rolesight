"""Personio direct ATS adapter."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import List

import requests

from job_hunt.adapters.base import DEFAULT_HEADERS, strip_html
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)


def fetch_personio(slug: str) -> List[JobPosting]:
    """Fetch open jobs from Personio XML feed.

    Endpoint: https://{slug}.jobs.personio.de/xml?language=en
    """
    url = f"https://{slug}.jobs.personio.de/xml?language=en"

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if resp.status_code == 404:
            logger.debug("Personio board not found for %s (HTTP 404)", slug)
            return []
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        logger.warning("Personio fetch failed for %s: %s", slug, e)
        return []

    jobs: List[JobPosting] = []
    for pos in root.findall("position"):
        job_id = pos.findtext("id", "").strip()
        title = pos.findtext("name", "").strip()
        office = pos.findtext("office", "").strip()
        department = pos.findtext("department", "").strip()
        created_at = pos.findtext("createdAt", "").strip()

        location_parts = [office, department]
        location = ", ".join(p for p in location_parts if p) or "Not specified"
        is_remote = "remote" in location.lower() or "remote" in title.lower()

        desc_parts = []
        for jd in pos.findall(".//jobDescription"):
            sec_name = jd.findtext("name", "").strip()
            sec_val = jd.findtext("value", "").strip()
            if sec_val:
                clean = strip_html(sec_val)
                desc_parts.append(f"## {sec_name}\n{clean}" if sec_name else clean)

        job_url = f"https://{slug}.jobs.personio.de/job/{job_id}" if job_id else f"https://{slug}.jobs.personio.de/"

        jobs.append(
            JobPosting(
                global_id=f"personio:{slug}:{job_id or title}",
                ats="personio",
                company=slug,
                title=title,
                location=location,
                is_remote=is_remote,
                url=job_url,
                description_text="\n\n".join(desc_parts).strip(),
                posted_at=created_at,
            )
        )
    return jobs
