"""ATS Adapters package for direct zero-browser job fetching."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from job_hunt.adapters.ashby import fetch_ashby
from job_hunt.adapters.greenhouse import fetch_greenhouse
from job_hunt.adapters.lever import fetch_lever
from job_hunt.adapters.personio import fetch_personio
from job_hunt.adapters.recruitee import fetch_recruitee
from job_hunt.adapters.smartrecruiters import fetch_smartrecruiters
from job_hunt.adapters.workable import fetch_workable
from job_hunt.adapters.workday import fetch_workday
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)


def detect_ats(careers_url: str) -> Optional[Tuple[str, str]]:
    """Detect ATS type and identifier from a company career URL.

    Returns:
        (ats_name, identifier) or None if unsupported/custom.
    """
    if not careers_url:
        return None

    url = careers_url.strip()

    # Greenhouse EU
    m_gh_eu = re.search(r"boards\.eu\.greenhouse\.io/([^/?#]+)", url)
    if m_gh_eu:
        return "greenhouse_eu", m_gh_eu.group(1)

    # Greenhouse US
    m_gh = re.search(r"(?:boards|boards-api)\.greenhouse\.io/(?:v1/boards/)?([^/?#]+)", url)
    if m_gh:
        return "greenhouse", m_gh.group(1)

    # Lever
    m_lever = re.search(r"jobs\.lever\.co/([^/?#]+)", url)
    if m_lever:
        return "lever", m_lever.group(1)

    # Ashby
    m_ashby = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)", url)
    if m_ashby:
        return "ashby", m_ashby.group(1)

    # SmartRecruiters
    m_sr = re.search(r"(?:jobs|careers)\.smartrecruiters\.com/([^/?#]+)", url)
    if m_sr:
        return "smartrecruiters", m_sr.group(1)

    # Workday: {tenant}.{dc}.myworkdayjobs.com/{site}
    m_wd = re.search(r"https?://([^.]+)\.([^.]+)\.myworkdayjobs\.com/([^/?#]+)", url)
    if m_wd:
        tenant = m_wd.group(1)
        dc = m_wd.group(2)
        site = m_wd.group(3)
        return "workday", f"{tenant}:{dc}:{site}"

    # Recruitee: {slug}.recruitee.com
    m_recruitee = re.search(r"https?://([^.]+)\.recruitee\.com", url)
    if m_recruitee and m_recruitee.group(1) not in ("api", "app", "www"):
        return "recruitee", m_recruitee.group(1)

    # Personio: {slug}.jobs.personio.de
    m_personio = re.search(r"https?://([^.]+)\.jobs\.personio\.de", url)
    if m_personio:
        return "personio", m_personio.group(1)

    # Workable: apply.workable.com/{slug}
    m_workable = re.search(r"apply\.workable\.com/([^/?#]+)", url)
    if m_workable:
        return "workable", m_workable.group(1)

    return None


def fetch_company_jobs(company_info: Dict[str, Any]) -> List[JobPosting]:
    """Fetch jobs for a company using direct ATS adapters.

    Accepts company info dict containing either:
      - 'ats' and 'slug' keys explicitly
      - or 'careers_url' which gets auto-detected
    """
    ats = company_info.get("ats")
    slug = company_info.get("slug")
    careers_url = company_info.get("careers_url", "")
    company_name = company_info.get("name", slug or "Company")

    if not ats and careers_url:
        detected = detect_ats(careers_url)
        if detected:
            ats, slug = detected

    if not ats:
        return []

    if ats == "workday":
        if not (company_info.get("tenant") and company_info.get("dc") and company_info.get("site")) and not slug:
            return []
    elif not slug:
        return []

    slug_str = str(slug or "")

    jobs: List[JobPosting] = []
    if ats == "greenhouse":
        jobs = fetch_greenhouse(slug_str, eu=False)
    elif ats == "greenhouse_eu":
        jobs = fetch_greenhouse(slug_str, eu=True)
    elif ats == "lever":
        jobs = fetch_lever(slug_str)
    elif ats == "ashby":
        jobs = fetch_ashby(slug_str)
    elif ats == "smartrecruiters":
        jobs = fetch_smartrecruiters(slug_str)
    elif ats == "workday":
        tenant = company_info.get("tenant")
        dc = company_info.get("dc")
        site = company_info.get("site")
        if tenant and dc and site:
            jobs = fetch_workday(tenant, dc, site)
        elif slug:
            parts = str(slug).split(":")
            if len(parts) >= 3:
                jobs = fetch_workday(parts[0], parts[1], parts[2])
    elif ats == "recruitee":
        jobs = fetch_recruitee(slug_str)
    elif ats == "personio":
        jobs = fetch_personio(slug_str)
    elif ats == "workable":
        jobs = fetch_workable(slug_str)

    # Overwrite company display name and attach headcount if configured
    headcount = company_info.get("headcount", "Unknown")
    for j in jobs:
        if company_name:
            j.company = company_name
        if headcount:
            j.headcount = headcount

    return jobs


__all__ = [
    "detect_ats",
    "fetch_company_jobs",
    "fetch_greenhouse",
    "fetch_lever",
    "fetch_ashby",
    "fetch_smartrecruiters",
    "fetch_workday",
    "fetch_recruitee",
    "fetch_personio",
    "fetch_workable",
]
