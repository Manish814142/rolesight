"""Local deterministic regex pre-filter to drop irrelevant roles before LLM scoring."""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Optional, Tuple

from job_hunt.models import JobPosting

# Word-bounded so e.g. 'java' does not hit "JavaScript", 'test' does not hit
# "Latest"/"Contest", 'intern' does not hit "Internal", 'india' does not hit "Indianapolis".
# Product startups often title backend roles "Product/Platform/Infrastructure Engineer".
TITLE_INCLUDE_PATTERN = re.compile(
    r"\b(back[\s-]?end|node(\.?js)?|sde\d*|software\s*engineer|software\s+development\s+engineer"
    r"|member\s+of\s+technical\s+staff|mts|computer\s+scientist|developer|full[\s-]*stack"
    r"|api|distributed(\s*systems)?|platform\s*engineer|product\s*engineer"
    r"|infrastructure\s*engineer|systems\s*engineer)\b",
    re.IGNORECASE,
)

# '.net' and 'c#' start/end with non-word chars, where \b does not apply,
# so they get their own boundary handling.
# "Senior"/"Sr." are deliberately NOT excluded: at Indian companies they often mean 3-6 YOE,
# so Gemini judges them against the resume (2026-10-05: 227 India jobs were blocked by
# that word alone). Staff/Principal/Lead/Manager stay excluded, except "Member of Technical
# Staff" (MTS), a standard mid-level engineer title.
# CRM / ERP / BI / RPA platform roles (T12) are configuration and integration work on someone
# else's product, not backend engineering: 82 of 1,191 survivors were scored for nothing. Matched on
# the title only, never the company, so "Software Engineer" at Salesforce or ServiceNow still passes.
# "crm" alone is left to the scorer: it is also a product domain at SaaS companies.
_PLATFORM_ROLE_WORDS = (
    r"salesforce|apex|servicenow|dynamics(\s*365)?|d365|sap|abap|netsuite|peoplesoft|coupa|workday"
    r"|cpq|zuora|mulesoft|boomi|informatica|tableau|bi|rpa|uipath|reltio|lims|mainframe|cobol"
    r"|sharepoint|siebel|pega|agentforce"
)
TITLE_EXCLUDE_PATTERN = re.compile(
    r"\b(lead|principal|(?<!technical\s)staff|manager|director|architect|front[\s-]?end"
    r"|react(\.?js)?|angular(js)?|vue(\.?js)?|ios|android|flutter|qa|test(er|ers|ing)?"
    r"|intern(s|ship)?|devops|sre|java|golang|python)\b"
    r"|\.net\b|\bc#(?!\w)"
    rf"|\b({_PLATFORM_ROLE_WORDS})\b"
    r"|\boracle\s+(ebs|fusion|hcm|erp|cpq|apps|cloud)\b|\bpower\s*(bi|platform|apps|automate)\b"
    r"|\bblue\s*prism\b|\bmarketing\s+cloud\b"
    # Languages and domains outside the target stack (T61): 56 of 1,191 survivors named one of these.
    r"|(?<![\w+])c\+\+|\b(embedded|firmware|kernel|gpu|cuda|fpga|verilog|rust|ruby|php)\b",
    re.IGNORECASE,
)

LOCATION_INDIA_PATTERN = re.compile(
    r"\b(bengaluru|bangalore|pune|gurugram|gurgaon|hyderabad|noida|mumbai|chennai|delhi|ncr"
    r"|kolkata|india)\b",
    re.IGNORECASE,
)

# SmartRecruiters appends a lowercase ISO country code ("Jaipur, RJ, in"). Deliberately
# case-sensitive: uppercase ", IN" is the US state code for Indiana ("Indianapolis, IN").
LOCATION_INDIA_COUNTRY_CODE = re.compile(r",\s*in\s*$")

LOCATION_GLOBAL_PATTERN = re.compile(r"\b(worldwide|anywhere|global)\b", re.IGNORECASE)

# Remote roles tied to another region (US/EU/UK/LATAM...) are not workable from India.
# State codes only count after a comma ("Santa Clara, CA") to avoid stray two-letter hits.
LOCATION_EXCLUDE_PATTERN = re.compile(
    r"\b(us|usa|united states|uk|united kingdom|canada|germany|europe|emea|latam"
    r"|san francisco|new york|austin|seattle|london|berlin)\b"
    r"|,\s*(ca|ny|tx|wa|il|ma)\b",
    re.IGNORECASE,
)

REMOTE_PATTERN = re.compile(r"\bremote\b", re.IGNORECASE)

# Workday gives relative text: "Posted Today", "Posted Yesterday", "Posted 5 Days Ago",
# "Posted 30+ Days Ago" (a lower bound).
_WORKDAY_POSTED_RE = re.compile(r"posted\s+(today|yesterday|(\d+)\+?\s+days?\s+ago)", re.IGNORECASE)


def posted_age_days(posted_at: str, today: Optional[date] = None) -> Optional[int]:
    """Days since a job was posted, from any adapter's posted_at; None if unknown."""
    s = (posted_at or "").strip()
    if not s:
        return None
    today = today or date.today()
    m = _WORKDAY_POSTED_RE.search(s)
    if m:
        word = m.group(1).lower()
        return 0 if word == "today" else 1 if word == "yesterday" else int(m.group(2))
    try:
        if s.isdigit() and len(s) >= 10:  # epoch seconds / milliseconds
            ts = int(s) / (1000 if len(s) >= 13 else 1)
            posted = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        else:
            posted = date.fromisoformat(s[:10])
    except (ValueError, OverflowError, OSError):
        return None
    return max(0, (today - posted).days)


def is_too_old(posted_at: str, max_age_days: Optional[int], today: Optional[date] = None) -> bool:
    """True only when the posted date is KNOWN and older than max_age_days.

    Undated jobs are never filtered — they are kept for manual review.
    """
    if max_age_days is None:
        return False
    age = posted_age_days(posted_at, today)
    return age is not None and age > max_age_days


def location_is_india(location: str) -> bool:
    """True when the location text names an Indian city/country (or SmartRecruiters' lowercase ', in')."""
    return bool(LOCATION_INDIA_PATTERN.search(location or "") or LOCATION_INDIA_COUNTRY_CODE.search(location or ""))


def should_evaluate_job(job: JobPosting) -> Tuple[bool, str]:
    """Evaluate whether a job posting matches candidate criteria.

    Returns:
        (True, "passed") if the job passes all criteria.
        (False, <reason>) if the job is rejected.
    """
    title = job.title or ""
    location = job.location or ""

    # 1. Exclude unwanted roles/seniority/stacks
    m_exclude = TITLE_EXCLUDE_PATTERN.search(title)
    if m_exclude:
        return False, f"Title matched exclude pattern: '{m_exclude.group(0)}'"

    # 2. Must match target include roles
    m_include = TITLE_INCLUDE_PATTERN.search(title)
    if not m_include:
        return False, "Title did not match include pattern"

    # 3. Location: India anywhere in the string wins; otherwise another region
    #    excludes; otherwise accept explicit worldwide/global or plain remote.
    if location_is_india(location):
        return True, "passed"

    m_region = LOCATION_EXCLUDE_PATTERN.search(location)
    if m_region:
        return False, f"Location '{location[:80]}' is tied to a non-India region: '{m_region.group(0).strip(', ')}'"

    if LOCATION_GLOBAL_PATTERN.search(location):
        return True, "passed"

    if job.is_remote or REMOTE_PATTERN.search(location):
        return True, "passed"

    return False, f"Location '{location[:80]}' does not match target locations"
