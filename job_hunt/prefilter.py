"""Local deterministic regex pre-filter to drop irrelevant roles before LLM scoring."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
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

# Generic engineer titles (T96, T69 g; Manish 2026-10-14): companies name roles differently, and "Senior Engineer", "Engineer II" or
# "Engineer III, Software" can be a backend job, so a title that is only "Engineer" with a seniority or level, or that has "software"
# and "engineer" in any order, goes to Gemini, which judges the description. "Data Engineer", "Mechanical Engineer" and the like
# name a different role and still need an include word. The exclude words are checked first, so "Lead Engineer" stays out.
# Measured (fetch of 2026-10-13): 44 + 5 jobs posted in the last 7 days, most of them hardware or support roles that score low.
TITLE_GENERIC_ENGINEER_PATTERN = re.compile(
    r"^\s*(?:(?:senior|sr\.?|associate)\s+)?engineer\b|\bsoftware\b.*\bengineer\b",
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
# "quality" sits with qa/test (review of T96, 2026-10-14): T96's "software ... engineer" rule let "Software Quality Engineer"
# through, scored 75 on its first scan; on the 2026-10-13 fetch all 13 passing titles with the word were QA, test
# automation or construction quality.
TITLE_EXCLUDE_PATTERN = re.compile(
    r"\b(lead|principal|(?<!technical\s)staff|manager|director|architect|front[\s-]?end"
    r"|react(\.?js)?|angular(js)?|vue(\.?js)?|ios|android|flutter|qa|quality|test(er|ers|ing)?"
    r"|intern(s|ship)?|devops|sre|java|golang)\b"
    r"|\.net\b|\bc#(?!\w)"
    rf"|\b({_PLATFORM_ROLE_WORDS})\b"
    r"|\boracle\s+(ebs|fusion|hcm|erp|cpq|apps|cloud)\b|\bpower\s*(bi|platform|apps|automate)\b"
    r"|\bblue\s*prism\b|\bmarketing\s+cloud\b"
    # Languages and domains outside the target stack (T61): 56 of 1,191 survivors named one of these.
    r"|(?<![\w+])c\+\+|\b(embedded(?!\s+(?:finance|payments?|banking|insurance|lending)\b)|firmware|kernel|gpu|cuda|fpga|verilog|rust|ruby|php)\b",
    re.IGNORECASE,
)

_INDIA_CITIES_CORE = r"bengaluru|bangalore|pune|gurugram|gurgaon|hyderabad|noida|mumbai|chennai|delhi|ncr|kolkata"
LOCATION_INDIA_PATTERN = re.compile(rf"\b({_INDIA_CITIES_CORE}|india)\b", re.IGNORECASE)

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
    r"|locations?|negotiable|multiple|various|more|tbd"
    # Job-type, timezone and office words some boards put in the location (review of T77, 2026-10-11: 1,180 jobs on
    # the fetch of 2026-10-11, e.g. "Remote (Full Time - Remote)", "Singapore (Permanent)", "Hyderabad (Office)").
    r"|full|part|time|fulltime|permanent|temporary|contract(or)?|freelance|employee|employment|ist|utc|gmt|time\s*zone"
    r"|timezone|friendly|home|office|telecommute|telework|depending|region|any|on|in|at|per|for|with|to|a)\b",
    re.IGNORECASE,
)

# The rest of India (T84): states and union territories, and the cities boards write without "India" or a state after
# them. With LOCATION_INDIA_PATTERN this makes the check one on the country: Manish applies to all of India (2026-10-14).
# Left out on purpose: names that are also places elsewhere (Salem, Bilaspur, Punjab).
_INDIA_PLACES_MORE = (
    r"karnataka|maharashtra|telangana|tamil\s+nadu|haryana|uttar\s+pradesh|rajasthan|gujarat|kerala|west\s+bengal"
    r"|andhra\s+pradesh|odisha|orissa|madhya\s+pradesh|bihar|jharkhand|chhattisgarh|assam|goa|uttarakhand|himachal"
    r"|jammu|kashmir|ladakh|sikkim|manipur|meghalaya|mizoram|nagaland|tripura|arunachal|andaman"
    r"|chandigarh|puducherry|pondicherry|ahmedabad|jaipur|kochi|cochin|coimbatore|indore|trivandrum|thiruvananthapuram"
    r"|bhubaneswar|lucknow|nagpur|vadodara|baroda|surat|mysuru|mysore|mangaluru|mangalore|visakhapatnam|vizag|mohali"
    r"|kanpur|patna|ranchi|bhopal|vijayawada|faridabad|ghaziabad|navi\s+mumbai|greater\s+noida|thane"
    r"|jamshedpur|hubballi|hubli|dharwad|belagavi|belgaum|dehradun|guwahati|ludhiana|amritsar|jalandhar|srinagar"
    r"|madurai|tiruchirappalli|trichy|vellore|tirupati|warangal|guntur|nellore|rajkot|nashik|aurangabad|solapur"
    r"|kolhapur|pimpri|chinchwad|raipur|jabalpur|gwalior|jodhpur|udaipur|agra|varanasi|meerut|prayagraj|allahabad"
    r"|gandhinagar|sonipat|panipat|kozhikode|calicut|thrissur|kollam|cuttack|rourkela|durgapur|siliguri|gangtok"
    r"|imphal|shillong|aizawl|kohima|agartala|itanagar|panaji|shimla|haridwar|bhilai|manipal|udupi|tumakuru|hosur|erode"
)
LOCATION_INDIA_MORE_PATTERN = re.compile(
    rf"\b({_INDIA_PLACES_MORE}|bharat)\b"
    r"|(?-i:\bIND\b)",   # India's ISO code, upper case only: "IND - Remote", "IN - Remote - IND" (review of T77)
    re.IGNORECASE,
)
# Named Indian places, without the country words: whether a location names a city or state at all (the city filter below).
_INDIAN_PLACE_PATTERN = re.compile(rf"\b({_INDIA_CITIES_CORE}|{_INDIA_PLACES_MORE})\b", re.IGNORECASE)

# The usual alternative names of one city or area, lower case. A chosen city matches a location holding any name of its group.
_CITY_GROUPS = [
    {"bengaluru", "bangalore", "bengalooru"}, {"gurugram", "gurgaon"}, {"mumbai", "bombay"}, {"kolkata", "calcutta"},
    {"chennai", "madras"}, {"kochi", "cochin"}, {"thiruvananthapuram", "trivandrum"}, {"mysuru", "mysore"},
    {"mangaluru", "mangalore"}, {"visakhapatnam", "vizag"}, {"puducherry", "pondicherry"}, {"vadodara", "baroda"},
    {"hubballi", "hubli"}, {"belagavi", "belgaum"}, {"prayagraj", "allahabad"}, {"kozhikode", "calicut"},
    {"tiruchirappalli", "trichy"},
]
_NCR = {"delhi", "new delhi", "ncr", "noida", "greater noida", "gurugram", "gurgaon", "ghaziabad", "faridabad"}
_AREA_GROUPS = {"delhi ncr": _NCR, "ncr": _NCR, "national capital region": _NCR}


def _city_terms(city: str) -> set:
    key = re.sub(r"\s+", " ", city.strip().lower())
    if key in _AREA_GROUPS:
        return _AREA_GROUPS[key]
    for group in _CITY_GROUPS:
        if key in group:
            return group
    return {key}


def city_matches(location: str, cities) -> bool:
    """True when the location text holds any of the chosen cities (whole words, any case, usual alternative names)."""
    text = (location or "").lower()
    for city in cities or []:
        for term in _city_terms(str(city)) if str(city).strip() else ():
            if re.search(r"(?<!\w)" + r"\s+".join(map(re.escape, term.split())) + r"(?!\w)", text):
                return True
    return False


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


def posted_date_iso(posted_at: str, today: Optional[date] = None) -> Optional[str]:
    """The posting date as YYYY-MM-DD, from any adapter's posted_at; None if unknown (T99). Workday's "Posted 3 Days Ago"
    is relative to the day it is read, so it becomes a date now: stored as text it would age again from the day the row was
    scored (`current_age_days`)."""
    today = today or date.today()
    age = posted_age_days(posted_at, today)
    return None if age is None else (today - timedelta(days=age)).isoformat()


def current_age_days(posted_at: str, seen_on: date, today: Optional[date] = None) -> Optional[int]:
    """Age today of a posting whose `posted_at` was read on `seen_on` (T39). Workday's "Posted 5 Days Ago" was
    relative to the day it was fetched, so the days since then are added; a real date is just its age today, even when it
    is later than `seen_on` (a date stored afterwards, T99)."""
    if not _WORKDAY_POSTED_RE.search((posted_at or "").strip()):
        return posted_age_days(posted_at, today)
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
    """True when the location text names India, an Indian city or state (or SmartRecruiters' lowercase ', in')."""
    text = location or ""
    return bool(LOCATION_INDIA_PATTERN.search(text) or LOCATION_INDIA_MORE_PATTERN.search(text)
                or LOCATION_INDIA_COUNTRY_CODE.search(text))


def _title_rejection(title: str) -> str:
    """Why the title alone rejects a job, or "" when it can pass (location is checked after this)."""
    m_exclude = TITLE_EXCLUDE_PATTERN.search(title)
    if m_exclude:
        return f"Title matched exclude pattern: '{m_exclude.group(0)}'"
    if not (TITLE_INCLUDE_PATTERN.search(title) or TITLE_GENERIC_ENGINEER_PATTERN.search(title)):
        return "Title did not match include pattern"
    return ""


def title_is_candidate(title: str) -> bool:
    """True when the title can pass the pre-filter. A job that fails this is rejected whatever its location,
    so an adapter may skip paid per-job calls (Workday's detail request) for it."""
    return not _title_rejection(title or "")


def should_evaluate_job(job: JobPosting, cities=None) -> Tuple[bool, str]:
    """Evaluate whether a job posting matches candidate criteria.

    `cities` (config.json candidate.cities, T84) narrows India to those cities: a job in an Indian city or state that is not one
    of them is rejected, unless it is remote or names no city (just "India"). None or empty means all of India.

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
    chosen = [c.strip() for c in (cities or []) if str(c).strip()]
    if chosen and city_matches(location, chosen):
        return True, "passed"            # a chosen city counts as India even where the lists above do not know it
    if location_is_india(location):
        remote = job.is_remote or bool(REMOTE_PATTERN.search(location))
        if chosen and not remote and _INDIAN_PLACE_PATTERN.search(location):
            return False, f"Location '{location[:80]}' is in India but not in your cities ({', '.join(chosen)})"
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
