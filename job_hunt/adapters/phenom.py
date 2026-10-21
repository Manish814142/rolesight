"""Phenom People careers-site adapter (the endpoints the careers page itself calls).

  POST https://{host}/widgets            (JSON body: ddoKey "refineSearch", selected_fields {"country": ["India"]},
                                          from, size up to 100)
      -> refineSearch.totalHits, refineSearch.data.jobs (jobId, title, location, multi_location, postedDate, ...)
  GET  https://{host}/{locale}/job/{jobId}   -> HTML whose JSON-LD `JobPosting` holds the full description

`locale` is the site's two-segment path prefix ("global/en", "us/en"); Phenom's search wants it as country + lang
("global", "en_global"). Most Phenom sites only front a Workday tenant (Cisco, DuPont, Fiserv, HPE, Philips: every
sampled job's apply URL was a Workday one, 2026-10-06) and are scanned through the Workday adapter; this one is for
the sites that hold their own jobs (BCG, 2026-10-10).
"""
from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from job_hunt.adapters.base import DEFAULT_HEADERS, http_get, http_post, mark_incomplete, strip_html
from job_hunt.models import JobPosting
from job_hunt.places import active_places

logger = logging.getLogger(__name__)

PAGE_SIZE = 100          # the widget honours sizes up to 100 (BCG, 2026-10-10)
MAX_JOBS = 1000

_LD_JSON_RE = re.compile(r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)


def _country_and_lang(locale: str) -> Optional[Tuple[str, str]]:
    parts = (locale or "").strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        return None
    return parts[0], f"{parts[1]}_{parts[0]}"


def _payload(country: str, lang: str, start: int) -> Dict[str, Any]:
    return {"lang": lang, "deviceType": "desktop", "country": country, "pageName": "search-results",
            "ddoKey": "refineSearch", "sortBy": "Most recent", "subsearch": "", "from": start, "jobs": True,
            "counts": True, "all_fields": ["category", "country", "state", "city", "type"], "size": PAGE_SIZE,
            "clearAll": False, "jdsource": "facets", "isSliderEnable": False, "pageId": "page11",
            "siteType": "external", "keywords": "", "global": True,
            "selected_fields": {"country": active_places().search_names()}, "locationData": {}}


def _location(item: Dict[str, Any]) -> str:
    """All locations of a job: `multi_location` is a stringified Python list ("['Pune, India', 'Mumbai, India']")."""
    raw = item.get("multi_location")
    if isinstance(raw, str) and raw.startswith("["):
        try:
            places = [str(p).strip() for p in ast.literal_eval(raw) if str(p).strip()]
        except (ValueError, SyntaxError):
            places = []
        if places:
            return "; ".join(places)
    return str(item.get("location") or item.get("city") or "")


def fetch_phenom(host: str, locale: str, company: str = "") -> List[JobPosting]:
    """Jobs of one Phenom careers site in the person's countries (scoped server-side; one search with the list of names,
    ["India"] unless config.json names others, T137)."""
    parsed = _country_and_lang(locale)
    if parsed is None:
        logger.warning("Phenom %s: locale %r is not 'country/lang' (e.g. global/en)", host, locale)
        return []
    country, lang = parsed
    short_lang = locale.strip("/").split("/")[1]
    url = f"https://{host}/widgets"
    jobs: List[JobPosting] = []
    seen: set = set()
    start = 0
    while start < MAX_JOBS:
        try:
            resp = http_post(url, headers={**DEFAULT_HEADERS, "Content-Type": "application/json"},
                             json=_payload(country, lang, start), timeout=30)
            resp.raise_for_status()
            search = resp.json().get("refineSearch") or {}
        except Exception as e:
            # Keep whatever earlier pages returned.
            logger.warning("Phenom fetch failed for %s at from=%d: %s", host, start, e)
            mark_incomplete(f"page failed at from={start}")
            break
        page = (search.get("data") or {}).get("jobs") or []
        new = 0
        for item in page:
            job_id = str(item.get("jobId") or item.get("reqId") or "")
            if not job_id or job_id in seen:
                continue
            seen.add(job_id)
            new += 1
            location = _location(item)
            jobs.append(JobPosting(
                global_id=f"phenom:{host}:{job_id}",
                ats="phenom",
                company=company or host,
                title=str(item.get("title") or "").strip(),
                location=location,
                is_remote="remote" in location.lower(),
                url=f"https://{host}/{country}/{short_lang}/job/{job_id}",
                posted_at=str(item.get("postedDate") or "")[:10],
            ))
        start += PAGE_SIZE
        total = search.get("totalHits")
        if new == 0 or len(page) < PAGE_SIZE or (isinstance(total, int) and start >= total):
            break
    else:  # stopped at MAX_JOBS with more jobs left
        mark_incomplete(f"cap {MAX_JOBS}")
    return jobs


def _job_posting_description(html_text: str) -> str:
    for block in _LD_JSON_RE.findall(html_text or ""):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for node in (data if isinstance(data, list) else data.get("@graph") or [data]):
            if isinstance(node, dict) and node.get("@type") == "JobPosting" and node.get("description"):
                return strip_html(str(node["description"]))
    return ""


def fetch_description(job: JobPosting) -> str:
    """Full description of one job from its public page ("" if unavailable)."""
    resp = http_get(job.url, headers=DEFAULT_HEADERS, timeout=30)
    if resp.status_code != 200:
        return ""
    return _job_posting_description(resp.text)
