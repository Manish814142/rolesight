"""ATS slug validation and company pruning module."""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import requests

from job_hunt.adapters.base import DEFAULT_HEADERS

logger = logging.getLogger(__name__)

KNOWN_CORRECTIONS = {
    "razorpay": {
        "ats": "greenhouse",
        "slug": "razorpaysoftwareprivatelimited",
    },
    "freshworks": {
        "ats": "smartrecruiters",
        "slug": "freshworks",
    },
    "slice": {
        "ats": "lever",
        "slug": "sliceit",
    },
}

BROWSERSTACK_ENTRY = {
    "name": "BrowserStack",
    "ats": "workday",
    "tenant": "browserstack",
    "dc": "wd3",
    "site": "External",
    "headcount": "1,001-5,000 employees",
}


def apply_known_corrections(companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply known corrections for companies with changed ATS engines or slugs."""
    has_browserstack = False
    updated_list: List[Dict[str, Any]] = []

    for item in companies:
        c = dict(item)
        name_key = c.get("name", "").lower().strip()

        if name_key in KNOWN_CORRECTIONS:
            c.update(KNOWN_CORRECTIONS[name_key])

        if name_key == "browserstack":
            has_browserstack = True
            c["ats"] = "workday"
            c["tenant"] = "browserstack"
            c["dc"] = "wd3"
            c["site"] = "External"
            c.pop("slug", None)

        updated_list.append(c)

    if not has_browserstack:
        updated_list.append(dict(BROWSERSTACK_ENTRY))

    return updated_list


def probe_company(company: Dict[str, Any], timeout: float = 8.0) -> Tuple[bool, Union[int, str]]:
    """Probe an ATS company endpoint.

    Returns:
        (True, 200) if active board responds 200 OK.
        (False, status_code_or_error) if 404, 403, or connection failure.
    """
    ats = company.get("ats", "").lower().strip()
    slug = company.get("slug", "").strip()

    url: str | None = None
    method = "GET"
    body: Dict[str, Any] | None = None

    if ats == "greenhouse":
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    elif ats == "lever":
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    elif ats == "ashby":
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    elif ats == "smartrecruiters":
        url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    elif ats == "workday":
        tenant = company.get("tenant")
        dc = company.get("dc")
        site = company.get("site")
        if not (tenant and dc and site) and slug:
            parts = slug.split(":")
            if len(parts) >= 3:
                tenant, dc, site = parts[0], parts[1], parts[2]
        if tenant and dc and site:
            url = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
            method = "POST"
            body = {"limit": 1, "offset": 0}
    elif ats == "recruitee":
        url = f"https://{slug}.recruitee.com/api/offers"
    elif ats == "personio":
        url = f"https://{slug}.jobs.personio.de/xml?language=en"

    if not url:
        return False, "unsupported_ats_or_missing_slug"

    try:
        if method == "POST":
            resp = requests.post(url, json=body or {}, headers=DEFAULT_HEADERS, timeout=timeout)
        else:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)

        if resp.status_code == 200:
            return True, 200
        return False, resp.status_code
    except Exception as e:
        return False, str(e)


def validate_and_prune(
    companies_path: str = "companies.json",
    max_workers: int = 15,
) -> List[Dict[str, Any]]:
    """Load companies.json, apply corrections, probe endpoints, and prune 404/403 entries."""
    p = Path(companies_path)
    if not p.exists():
        raise FileNotFoundError(f"Companies file not found: {companies_path}")

    raw_companies = json.loads(p.read_text(encoding="utf-8"))
    corrected = apply_known_corrections(raw_companies)

    print(f"Validating {len(corrected)} companies against official ATS APIs...")

    def _worker(c: Dict[str, Any]) -> Tuple[Dict[str, Any], bool, Union[int, str]]:
        ok, status = probe_company(c)
        return c, ok, status

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_worker, corrected))

    valid_companies: List[Dict[str, Any]] = []
    pruned_count = 0

    for company, ok, status in results:
        name = company.get("name", "Unknown")
        ats = company.get("ats", "unknown")
        if ok:
            print(f"  [ACTIVE]  {name} ({ats}) -> HTTP 200")
            valid_companies.append(company)
        else:
            print(f"  [PRUNED]  {name} ({ats}) -> {status}")
            pruned_count += 1

    # Rewrite companies.json with verified list
    p.write_text(json.dumps(valid_companies, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nValidation complete: {len(valid_companies)} active companies retained, {pruned_count} pruned.")
    return valid_companies


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    validate_and_prune("companies.json")


if __name__ == "__main__":
    main()
