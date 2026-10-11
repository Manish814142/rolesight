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
    r"\b(back[\s-]?end|node(\.?js)?|sde\d*|software\s*engineer|software\s+dev(elopment)?\s+engineer"
    r"|member\s+of\s+technical\s+staff|mts|computer\s+scientist|developer|full[\s-]*stack"
    r"|api|distributed(\s*systems)?|platform\s*engineer|product\s*engineer"
    r"|infrastructure\s*engineer|systems\s*engineer"
    # AI / Forward Deployed Engineer titles (T74, Manish 2026-10-10): the scoring rubric rejects the ones that need heavy AI.
    r"|(gen(erative)?[\s-]*ai|agentic[\s-]+ai|applied[\s-]+ai|ai|llm)[\s-]+engineer|forward[\s-]*deployed[\s-]+engineer)\b",
    re.IGNORECASE,
)

# '.net' and 'c#' start/end with non-word chars, where \b does not apply,
# so they get their own boundary handling.
# "Senior"/"Sr." are deliberately NOT excluded: at Indian companies they often mean 3-6 YOE,
# so Gemini judges them against the resume (2026-10-04: 227 India jobs were blocked by
# that word alone). Staff/Principal/Lead/Manager stay excluded, except "Member of Technical
# Staff" (MTS), a standard mid-level engineer title.
# "python" is not excluded (T62, Manish 2026-10-10): his resume lists it, 33 India titles named it and 9 of 32
# scored 80+ when read in full. "java" and "golang" stay excluded.
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
    r"|intern(s|ship)?|devops|sre|java|golang)\b"
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

# A remote-flagged job passes only when its location names no place (T77). OpenAI's Ashby board flags its Paris, Tokyo,
# Singapore, Seoul, Madrid, Sydney and Washington DC offices as remote, and the exclude list above knew none of them:
# 63 of 1,878 survivors (3.4%, fetch of 2026-10-11) passed on the flag alone, 61 of them naming a place outside India.
# Words that are not places ("Remote", "Hybrid", "Work from home", "APAC", and the placeholders Workday gives for a job
# whose real locations come from a later call: "3 Locations", "Location Negotiable", "Remote Work, More...");
# what is left after removing them is a place.
_LOCATION_FILLER_PATTERN = re.compile(
    r"\b(remote(ly)?|hybrid|flexible|first|work(\s+from\s+home)?|wfh|home[\s-]*based|virtual|distributed|fully|only|based"
    r"|within|apac|asia(\s+pacific)?|area|or|and|the|of|anywhere|worldwide|global(ly)?"
    r"|locations?|negotiable|multiple|various|more|tbd)\b",
    re.IGNORECASE,
)

# Indian places LOCATION_INDIA_PATTERN lacks (states, union territories, cities): never a "named non-India place".
# Used only for the rule above, so it changes nothing for jobs the flag did not carry (T84 asks whether the main
# India check should know them too).
LOCATION_INDIA_MORE_PATTERN = re.compile(
    r"\b(karnataka|maharashtra|telangana|tamil\s+nadu|haryana|uttar\s+pradesh|rajasthan|gujarat|kerala|west\s+bengal"
    r"|andhra\s+pradesh|odisha|orissa|madhya\s+pradesh|bihar|jharkhand|chhattisgarh|assam|goa|uttarakhand|himachal"
    r"|chandigarh|puducherry|pondicherry|ahmedabad|jaipur|kochi|cochin|coimbatore|indore|trivandrum|thiruvananthapuram"
    r"|bhubaneswar|lucknow|nagpur|vadodara|surat|mysuru|mysore|mangaluru|mangalore|visakhapatnam|vizag|mohali|kanpur"
    r"|patna|ranchi|bhopal|vijayawada|faridabad|ghaziabad|navi\s+mumbai|thane|bharat)\b",
    re.IGNORECASE,
)


def named_place(location: str) -> str:
    """The words of a location that name a place, or "" when it names none ("Remote", "Hybrid", "") or names an
    Indian one. Only meant for locations the filter already found no India term in."""
    text = location or ""
    if LOCATION_INDIA_MORE_PATTERN.search(text):
        return ""
    return " ".join(re.findall(r"[^\W\d_]+", _LOCATION_FILLER_PATTERN.sub(" ", text)))

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


def current_age_days(posted_at: str, seen_on: date, today: Optional[date] = None) -> Optional[int]:
    """Age today of a posting whose `posted_at` was read on `seen_on` (T39). Workday's "Posted 5 Days Ago" was
    relative to the day it was fetched, so the days since then are added; for a real date this is just its age."""
    at_fetch = posted_age_days(posted_at, seen_on)
    if at_fetch is None:
        return None
    return at_fetch + max(0, ((today or date.today()) - seen_on).days)


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


def _title_rejection(title: str) -> str:
    """Why the title alone rejects a job, or "" when it can pass (location is checked after this)."""
    m_exclude = TITLE_EXCLUDE_PATTERN.search(title)
    if m_exclude:
        return f"Title matched exclude pattern: '{m_exclude.group(0)}'"
    if not TITLE_INCLUDE_PATTERN.search(title):
        return "Title did not match include pattern"
    return ""


def title_is_candidate(title: str) -> bool:
    """True when the title can pass the pre-filter. A job that fails this is rejected whatever its location,
    so an adapter may skip paid per-job calls (Workday's detail request) for it."""
    return not _title_rejection(title or "")


def should_evaluate_job(job: JobPosting) -> Tuple[bool, str]:
    """Evaluate whether a job posting matches candidate criteria.

    Returns:
        (True, "passed") if the job passes all criteria.
        (False, <reason>) if the job is rejected.
    """
    title = job.title or ""
    location = job.location or ""

    # 1-2. The title decides first: exclude unwanted roles/seniority/stacks, then require a target role
    reason = _title_rejection(title)
    if reason:
        return False, reason

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
        place = named_place(location)
        if place:
            return False, f"Location '{location[:80]}' is remote but names a non-India place: '{place[:60]}'"
        return True, "passed"

    return False, f"Location '{location[:80]}' does not match target locations"
