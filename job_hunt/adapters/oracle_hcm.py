"""Oracle Recruiting Cloud (Oracle HCM "CandidateExperience") adapter.

Public REST endpoint used by the candidate site itself:
  GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions
      ?onlyData=true&finder=findReqs;siteNumber={site},...
The India location facet id differs per tenant, so it is looked up first.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from job_hunt.adapters.base import (
    DEFAULT_HEADERS,
    http_get,
    mark_incomplete,
    stop_at_window,
    strip_html,
)
from job_hunt.models import JobPosting
from job_hunt.places import active_places

logger = logging.getLogger(__name__)

PAGE_SIZE = 100
MAX_JOBS = 2000


def _api(host: str) -> str:
    return f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"


def _india_facet_id(host: str, site: str) -> Optional[int]:
    return _location_facets(host, site).get("india")


def _location_facets(host: str, site: str) -> Dict[str, int]:
    """The site's location facets, lower-case name -> id. Measured 2026-10-21 (T137): sites list only their biggest
    locations (10 on ACI Worldwide, American Express, Akamai, Adani; 50 on APLL), so a country can be missing."""
    params = {"onlyData": "true", "expand": "locationsFacet",
              "finder": f"findReqs;siteNumber={site},facetsList=LOCATIONS,limit=1"}
    resp = http_get(_api(host), headers=DEFAULT_HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    items = resp.json().get("items") or [{}]
    facets: Dict[str, int] = {}
    for loc in items[0].get("locationsFacet") or []:
        name = (loc.get("Name") or "").strip().lower()
        if name and name not in facets:
            facets[name] = loc.get("Id")
    return facets


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
    """Requisitions of one Oracle HCM career site in the person's countries (T137). India alone: the India facet, or
    nothing when the site has none (as before). Other countries: one read per country facet; when one of them has no facet
    on the site, a single read without a facet instead, newest first, which the posted-date window stops."""
    places = active_places()
    try:
        if places.india_only():
            india = _india_facet_id(host, site)
            if india is None:
                logger.debug("Oracle HCM %s/%s has no India location facet", host, site)
                return []
            facet_ids: List[Optional[int]] = [india]
        else:
            facets = _location_facets(host, site)
            ids = [facets.get(name.lower()) for name in places.search_names()]
            facet_ids = list(ids) if all(i is not None for i in ids) else [None]
    except Exception as e:
        logger.warning("Oracle HCM facet lookup failed for %s/%s: %s", host, site, e)
        return []
    jobs: List[JobPosting] = []
    seen: set = set()
    for facet in facet_ids:
        _read(host, site, company, facet, jobs, seen if len(facet_ids) > 1 else None)
    return jobs


def _read(host: str, site: str, company: str, facet: Optional[int], jobs: List[JobPosting], seen: Optional[set]) -> None:
    """Page through one facet (None: the whole site), newest first; `seen` skips requisitions an earlier facet returned."""
    offset = 0
    while offset < MAX_JOBS:
        where = f"selectedLocationsFacet={facet}," if facet is not None else ""
        finder = (f"findReqs;siteNumber={site},{where}"
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
            if seen is not None:
                if req.get("Id") in seen:
                    continue
                seen.add(req.get("Id"))
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
        if stop_at_window(req.get("PostedDate") or "" for req in page):   # sortBy=POSTING_DATES_DESC (T02)
            break
    else:  # stopped at MAX_JOBS with more requisitions left
        mark_incomplete(f"cap {MAX_JOBS}")
