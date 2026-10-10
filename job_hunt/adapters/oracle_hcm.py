"""Oracle Recruiting Cloud (Oracle HCM "CandidateExperience") adapter.

Public REST endpoint used by the candidate site itself:
  GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions
      ?onlyData=true&finder=findReqs;siteNumber={site},...
The India location facet id differs per tenant, so it is looked up first.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from job_hunt.adapters.base import (
    DEFAULT_HEADERS,
    http_get,
    mark_incomplete,
    stop_at_window,
    strip_html,
)
from job_hunt.models import JobPosting

logger = logging.getLogger(__name__)

PAGE_SIZE = 100
MAX_JOBS = 2000


def _api(host: str) -> str:
    return f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"


def _india_facet_id(host: str, site: str) -> Optional[int]:
    params = {"onlyData": "true", "expand": "locationsFacet",
              "finder": f"findReqs;siteNumber={site},facetsList=LOCATIONS,limit=1"}
    resp = http_get(_api(host), headers=DEFAULT_HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    items = resp.json().get("items") or [{}]
    for loc in items[0].get("locationsFacet") or []:
        if (loc.get("Name") or "").strip().lower() == "india":
            return loc.get("Id")
    return None


_JOB_URL_RE = re.compile(r"https://([^/]+)/hcmUI/CandidateExperience/[^/]+/sites/([^/]+)/job/([^/?#]+)")

# The list API only has ShortDescriptionStr (~20-120 chars). Tenants split the role across
# these fields: EXL and Kotak keep most of it in Responsibilities/Qualifications (2026-10-04).
_DETAIL_FIELDS = (
    ("ExternalDescriptionStr", "Description"),
    ("ExternalResponsibilitiesStr", "Responsibilities"),
    ("ExternalQualificationsStr", "Qualifications"),
    ("OrganizationDescriptionStr", "About the organisation"),
    ("CorporateDescriptionStr", "About the company"),
)


def fetch_description(job: JobPosting) -> str:
    """Full description of one requisition from recruitingCEJobRequisitionDetails ("" if none)."""
    m = _JOB_URL_RE.match(job.url)
    if not m:
        return ""
    host, site, req_id = m.groups()
    resp = http_get(f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails",
                    headers=DEFAULT_HEADERS, timeout=20,
                    params={"onlyData": "true", "finder": f'ById;Id="{req_id}",siteNumber={site}'})
    if resp.status_code != 200:
        return ""
    items = resp.json().get("items") or []
    if not items:
        return ""
    parts = []
    for field, label in _DETAIL_FIELDS:
        text = strip_html(items[0].get(field) or "")
        if text:
            parts.append(f"{label}:\n{text}")
    return "\n\n".join(parts)


def fetch_oracle_hcm(host: str, site: str, company: str = "") -> List[JobPosting]:
    """India requisitions of one Oracle HCM career site (all jobs if no India facet)."""
    try:
        india = _india_facet_id(host, site)
    except Exception as e:
        logger.warning("Oracle HCM facet lookup failed for %s/%s: %s", host, site, e)
        return []
    if india is None:
        logger.debug("Oracle HCM %s/%s has no India location facet", host, site)
        return []

    jobs: List[JobPosting] = []
    offset = 0
    while offset < MAX_JOBS:
        finder = (f"findReqs;siteNumber={site},selectedLocationsFacet={india},"
                  f"limit={PAGE_SIZE},offset={offset},sortBy=POSTING_DATES_DESC")
        try:
            resp = http_get(_api(host), headers=DEFAULT_HEADERS, timeout=20,
                            params={"onlyData": "true", "expand": "requisitionList.secondaryLocations",
                                    "finder": finder})
            resp.raise_for_status()
            item = (resp.json().get("items") or [{}])[0]
        except Exception as e:
            logger.warning("Oracle HCM fetch failed for %s/%s at offset %d: %s", host, site, offset, e)
            mark_incomplete(f"page failed at offset {offset}")
            break
        page = item.get("requisitionList") or []
        for req in page:
            location = req.get("PrimaryLocation") or "Not specified"
            jobs.append(JobPosting(
                global_id=f"oracle_hcm:{host}:{req.get('Id')}",
                ats="oracle_hcm",
                company=company or host.split(".")[0],
                title=(req.get("Title") or "").strip(),
                location=location,
                is_remote="remote" in location.lower() or "remote" in (req.get("WorkplaceType") or "").lower(),
                url=f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{req.get('Id')}",
                description_text=req.get("ShortDescriptionStr") or "",
                posted_at=req.get("PostedDate") or "",
            ))
        offset += PAGE_SIZE
        if len(page) < PAGE_SIZE or offset >= int(item.get("TotalJobsCount") or 0):
            break
        if stop_at_window(j.posted_at for j in jobs[-len(page):]):   # sortBy=POSTING_DATES_DESC (T02)
            break
    else:  # stopped at MAX_JOBS with more requisitions left
        mark_incomplete(f"cap {MAX_JOBS}")
    return jobs
