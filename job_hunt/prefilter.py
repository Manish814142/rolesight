"""Local deterministic regex pre-filter to drop irrelevant roles before LLM scoring."""
from __future__ import annotations

import re
from typing import Tuple

from job_hunt.models import JobPosting

# Word-bounded so e.g. 'java' does not hit "JavaScript", 'test' does not hit
# "Latest"/"Contest", 'intern' does not hit "Internal", 'india' does not hit "Indianapolis".
# Product startups often title backend roles "Product/Platform/Infrastructure Engineer".
TITLE_INCLUDE_PATTERN = re.compile(
    r"\b(back[\s-]?end|node(\.?js)?|sde\d*|software\s*engineer|developer|full[\s-]*stack"
    r"|api|distributed(\s*systems)?|platform\s*engineer|product\s*engineer"
    r"|infrastructure\s*engineer|systems\s*engineer)\b",
    re.IGNORECASE,
)

# '.net' and 'c#' start/end with non-word chars, where \b does not apply,
# so they get their own boundary handling.
TITLE_EXCLUDE_PATTERN = re.compile(
    r"\b(senior|sr|lead|principal|staff|manager|director|architect|front[\s-]?end"
    r"|react(\.?js)?|angular(js)?|vue(\.?js)?|ios|android|flutter|qa|test(er|ers|ing)?"
    r"|intern(s|ship)?|devops|sre|java|golang|python)\b"
    r"|\.net\b|\bc#(?!\w)",
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
    if LOCATION_INDIA_PATTERN.search(location) or LOCATION_INDIA_COUNTRY_CODE.search(location):
        return True, "passed"

    m_region = LOCATION_EXCLUDE_PATTERN.search(location)
    if m_region:
        return False, f"Location '{location[:80]}' is tied to a non-India region: '{m_region.group(0).strip(', ')}'"

    if LOCATION_GLOBAL_PATTERN.search(location):
        return True, "passed"

    if job.is_remote or REMOTE_PATTERN.search(location):
        return True, "passed"

    return False, f"Location '{location[:80]}' does not match target locations"
