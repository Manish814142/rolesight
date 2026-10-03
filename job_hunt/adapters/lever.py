"""Lever direct ATS adapter."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

import requests

from job_hunt.adapters.base import DEFAULT_HEADERS, strip_html
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)


def fetch_lever(slug: str) -> List[JobPosting]:
    """Fetch open jobs from Lever public postings API.

    Endpoint: https://api.lever.co/v0/postings/{slug}?mode=json
    """
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if resp.status_code == 404:
            logger.debug("Lever board not found for %s (HTTP 404)", slug)
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Lever fetch failed for %s: %s", slug, e)
        return []

    jobs: List[JobPosting] = []
    for item in data:
        job_id = str(item.get("id", ""))
        title = item.get("text", "").strip()
        cats = item.get("categories", {}) or {}
        location = cats.get("location", "Not specified")
        workplace_type = cats.get("workplaceType", "").lower()
        commitment = cats.get("commitment", "")

        is_remote = (
            "remote" in location.lower()
            or "remote" in workplace_type
            or "remote" in title.lower()
        )

        # Assemble full description from descriptionPlain and lists
        desc_parts = []
        if item.get("descriptionPlain"):
            desc_parts.append(item["descriptionPlain"])
        for sec in item.get("lists", []):
            sec_title = sec.get("text", "")
            sec_content = strip_html(sec.get("content", ""))
            if sec_title:
                desc_parts.append(f"## {sec_title}\n{sec_content}")
            else:
                desc_parts.append(sec_content)

        created_at_ms = item.get("createdAt")
        posted_at = ""
        if created_at_ms:
            try:
                posted_at = datetime.fromtimestamp(
                    created_at_ms / 1000, tz=timezone.utc
                ).isoformat()
            except Exception:
                posted_at = str(created_at_ms)

        jobs.append(
            JobPosting(
                global_id=f"lever:{slug}:{job_id}",
                ats="lever",
                company=slug,
                title=title,
                location=f"{location} ({commitment})" if commitment else location,
                is_remote=is_remote,
                url=item.get("hostedUrl", f"https://jobs.lever.co/{slug}/{job_id}"),
                description_text="\n\n".join(desc_parts).strip(),
                posted_at=posted_at,
            )
        )
    return jobs
