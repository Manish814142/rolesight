import pytest

from job_hunt.models import JobPosting
from job_hunt.prefilter import should_evaluate_job


def test_prefilter_accepts_good_backend_job():
    job = JobPosting(
        global_id="gh:test:1",
        ats="greenhouse",
        company="Razorpay",
        title="Software Engineer - Backend",
        location="Bengaluru, India",
        is_remote=False,
        url="https://example.com/1",
    )
    passed, reason = should_evaluate_job(job)
    assert passed is True
    assert reason == "passed"

def test_prefilter_accepts_node_remote_job():
    job = JobPosting(
        global_id="lever:test:2",
        ats="lever",
        company="Startup",
        title="Node Developer",
        location="Worldwide",
        is_remote=True,
        url="https://example.com/2",
    )
    passed, reason = should_evaluate_job(job)
    assert passed is True
    assert reason == "passed"

def test_prefilter_rejects_excluded_seniority():
    job = JobPosting(
        global_id="gh:test:3",
        ats="greenhouse",
        company="Acme",
        title="Staff Backend Engineer",
        location="Bangalore",
        is_remote=False,
        url="https://example.com/3",
    )
    passed, reason = should_evaluate_job(job)
    assert passed is False
    assert "exclude pattern" in reason.lower()

def test_prefilter_rejects_frontend_and_mobile():
    for title in ["Frontend Developer", "React Engineer", "iOS Developer", "QA Automation Tester"]:
        job = JobPosting(
            global_id="gh:test:4",
            ats="greenhouse",
            company="Acme",
            title=title,
            location="Pune, India",
            is_remote=False,
            url="https://example.com/4",
        )
        passed, reason = should_evaluate_job(job)
        assert passed is False, f"Expected {title} to fail prefilter"

def test_prefilter_rejects_non_tech_or_unmatched_include():
    job = JobPosting(
        global_id="gh:test:5",
        ats="greenhouse",
        company="Acme",
        title="Account Executive",
        location="Bengaluru",
        is_remote=False,
        url="https://example.com/5",
    )
    passed, reason = should_evaluate_job(job)
    assert passed is False
    assert "include pattern" in reason.lower()

def test_prefilter_rejects_unmatched_location_when_not_remote():
    job = JobPosting(
        global_id="gh:test:6",
        ats="greenhouse",
        company="Acme",
        title="Software Engineer",
        location="San Francisco, CA",
        is_remote=False,
        url="https://example.com/6",
    )
    passed, reason = should_evaluate_job(job)
    assert passed is False
    assert "location" in reason.lower()


def _job(title, location="Bengaluru, India", is_remote=False):
    return JobPosting(
        global_id="gh:test:wb",
        ats="greenhouse",
        company="Acme",
        title=title,
        location=location,
        is_remote=is_remote,
        url="https://example.com/wb",
    )


@pytest.mark.parametrize("title", [
    "Backend Engineer (JavaScript)",          # 'java' must not match JavaScript
    "Backend Engineer, Latest Products",      # 'test' must not match latest
    "Software Engineer - Contest Platform",   # 'test' must not match contest
    "Software Engineer, Internal Platform",   # 'intern' must not match internal
    "Software Engineer - International Payments",
    "NodeJS Engineer",
    "Node.js Engineer",
    "Back-end Engineer",
    "Full-Stack Developer",
    "SDE-2",
    "SDE2 - Payments",
    "API Platform Engineer",
    "Python Backend Developer",               # T62 (Manish, 2026-10-10): python is allowed in titles
])
def test_prefilter_word_boundaries_accept(title):
    passed, reason = should_evaluate_job(_job(title))
    assert passed is True, f"{title!r} rejected: {reason}"


@pytest.mark.parametrize("title", [
    "Java Developer",
    "Backend Engineer - Java",
    "Software Test Engineer",
    "Software Engineer in Test",
    "Software Engineer - Testing",
    ".NET Developer",
    "ASP.NET Backend Developer",
    "C# Developer",
    "Software Engineer Intern",
    "Software Engineering Internship - Backend",
    "Front-end Developer",
    "ReactJS Developer",
    "Tech Lead - Backend",
])
def test_prefilter_word_boundaries_reject(title):
    passed, reason = should_evaluate_job(_job(title))
    assert passed is False, f"{title!r} unexpectedly passed"
    assert "exclude pattern" in reason.lower()


def test_prefilter_location_does_not_match_inside_other_words():
    passed, reason = should_evaluate_job(_job("Software Engineer", location="Indianapolis, IN"))
    assert passed is False
    assert "location" in reason.lower()


@pytest.mark.parametrize("location", ["Remote - India", "Pune/Hyderabad", "Gurugram, Haryana", "BANGALORE"])
def test_prefilter_location_accepts_target_cities(location):
    passed, _ = should_evaluate_job(_job("Software Engineer", location=location))
    assert passed is True


@pytest.mark.parametrize("title", [
    "Product Engineer",
    "Product Engineer - Backend",
    "Platform Engineer - AI Infrastructure",
    "Core Platform Engineer",
    "Infrastructure Engineer",
    "Systems Engineer",
    "Distributed Systems Engineer",
])
def test_prefilter_accepts_startup_backend_titles(title):
    passed, reason = should_evaluate_job(_job(title))
    assert passed is True, f"{title!r} rejected: {reason}"


@pytest.mark.parametrize("title", ["Staff Product Engineer", "Product Manager", "Product Designer"])
def test_prefilter_new_include_terms_do_not_bypass_rules(title):
    passed, _ = should_evaluate_job(_job(title))
    assert passed is False


# Exact locations string of the Salesforce false positive from the 2026-10-04 Workday scan.
SALESFORCE_US_REMOTE = (
    "California - San Francisco; California - Palo Alto; Illinois - Chicago; Massachusetts - Boston; "
    "Massachusetts - Burlington; Washington - Bellevue; West Virginia - Washington DC Metro - Remote; "
    "District of Columbia - Washington; New Jersey - New York City Metro - Remote; North Carolina - Raleigh; "
    "Indiana - Indianapolis; New York - New York; Virginia - Washington DC Metro - Remote; Washington - Seattle; "
    "Maryland - Washington DC Metro - Remote; Texas - Dallas; New York - New York City Metro - Remote; "
    "Colorado - Denver; Georgia - Atlanta; Virginia - Mclean; Texas - Austin"
)


@pytest.mark.parametrize("location", [
    SALESFORCE_US_REMOTE,
    "Remote-US",
    "Remote - EMEA",
    "Remote, Canada",
    "London, UK (Remote)",
    "Santa Clara, CA - Remote",
    "Remote - LATAM",
    "Global (US only)",
])
def test_prefilter_rejects_non_india_remote(location):
    passed, reason = should_evaluate_job(_job("Software Engineer", location=location, is_remote=True))
    assert passed is False, f"{location[:40]!r} unexpectedly passed"
    assert "location" in reason.lower()


@pytest.mark.parametrize("location,is_remote", [
    ("Bengaluru; San Francisco, CA", False),   # India mentioned -> exclusion overridden
    ("India, Remote", True),
    ("Remote", True),
    ("Worldwide", False),
    ("Anywhere", False),
    ("Remote - Global", True),
    ("Mumbai, MH, in", False),
    ("Chennai", False),
])
def test_prefilter_accepts_india_and_truly_global(location, is_remote):
    passed, reason = should_evaluate_job(_job("Software Engineer", location=location, is_remote=is_remote))
    assert passed is True, f"{location!r} rejected: {reason}"


@pytest.mark.parametrize("location", [
    "New Delhi, in",          # SmartRecruiters lowercase country code
    "Gurgaon, in",
    "Kolkata, WB, in",
    "Delhi NCR",
    "New Delhi",
    "Kolkata",
    "Gurugram / Noida",
    "Jaipur, RJ, in",         # any Indian city via the country code
])
def test_prefilter_accepts_delhi_kolkata_and_in_country_code(location):
    passed, reason = should_evaluate_job(_job("Software Engineer", location=location))
    assert passed is True, f"{location!r} rejected: {reason}"


@pytest.mark.parametrize("location", [
    "Indianapolis, IN",       # US state code for Indiana — must not read as India
    "Carmel, IN",
    "Fort Wayne, IN, us",
])
def test_prefilter_indiana_state_code_is_not_india(location):
    passed, _ = should_evaluate_job(_job("Software Engineer", location=location))
    assert passed is False


@pytest.mark.parametrize("title", [
    "Senior Software Engineer",
    "Senior Backend Engineer, Vision",
    "Sr. Software Engineer",
    "Sr Backend Developer",
])
def test_prefilter_lets_senior_titles_through_for_gemini_to_judge(title):
    """At Indian companies "Senior" often means 3-6 YOE; 2026-10-04 measurement: 227 India
    jobs (38 in 7 days) were blocked by this word alone. Gemini scores them against the
    resume's experience instead of a regex dropping them."""
    passed, reason = should_evaluate_job(_job(title))
    assert passed is True, f"{title!r} rejected: {reason}"


@pytest.mark.parametrize("title", ["Staff Software Engineer", "Lead Backend Engineer",
                                   "Principal Engineer, Platform", "Senior Staff Software Engineer"])
def test_prefilter_still_blocks_staff_lead_principal(title):
    assert should_evaluate_job(_job(title))[0] is False


@pytest.mark.parametrize("title", [
    "Software Development Engineer II, Prime Video",   # Amazon: 202/202 India SDE titles were rejected
    "Senior Software Development Engineer",
    "Member of Technical Staff",                       # Salesforce/Oracle-style engineer title
    "Senior Member of Technical Staff - Backend",
    "MTS 2, Platform",
    # T72: Amazon also spells it "Software Dev Engineer": 55 India jobs never reached Gemini (fetch of 2026-10-06)
    "Software Dev Engineer II, FinTech Tax",
    "Software Dev Engineer-II, Infra Supply Chain Automation",
    "Sr. Software Dev Engineer, Amazon Freight",
    "Software Dev Engineer 2, AFT Inventory",
])
def test_prefilter_accepts_sde_and_mts_titles(title):
    passed, reason = should_evaluate_job(_job(title))
    assert passed is True, f"{title!r} rejected: {reason}"


@pytest.mark.parametrize("title", ["Principal Member of Technical Staff", "Lead Member of Technical Staff",
                                   "Staff Software Development Engineer", "Software Dev Engineer, Frontend",
                                   "Principal Software Dev Engineer", "Software Dev Manager, Alexa"])
def test_prefilter_mts_rules_keep_principal_lead_staff_blocked(title):
    assert should_evaluate_job(_job(title))[0] is False


# T12: CRM / ERP / BI-platform roles are not backend engineering and were scored for nothing
# (82 of 1,191 survivors, measured on 34,416 jobs fetched 2026-10-06). Titles only, never the company.
def _india(title, company="Acme"):
    return JobPosting(global_id="g", ats="workday", company=company, title=title,
                      location="Bengaluru, India", is_remote=False, url="u")


@pytest.mark.parametrize("title", [
    "Salesforce Developer",
    "Senior Salesforce Developer, Service Cloud",
    "Software Engineer III - Salesforce Platform Developer",
    "ServiceNow Developer SAM",
    "ServiceNow Platform & ITSM Developer",
    "Senior Developer(SAP DM Support) - ECF2",
    "Software Engineer - SAP ABAP",
    "SAP BTP Full Stack Developer",
    "Workday Extend Developer",
    "Senior Workday Integration Developer",
    "Software Development Engineer 3 - Microsoft Dynamics Developer",
    "D365 Finance Developer",
    "Senior Developer (Oracle EBS)",
    "SR PROGRAMMER 10001 - Oracle CPQ (BigMachines) Developer",
    "Informatica Developer",
    "Power Platform Developer",
    "BI Developer (Power BI + Tableau)",
    "Seniore Power BI developer",
    "RPA Developer",
    "Zuora Billing- Senior Developer",
    "Mainframe Developer",
    "Boomi Integration Developer",
])
def test_prefilter_rejects_crm_erp_bi_platform_roles(title):
    ok, reason = should_evaluate_job(_india(title))
    assert not ok and "exclude" in reason


@pytest.mark.parametrize("title", [
    "Software Engineer, Backend (Node.js)",
    "Senior Software Engineer - Cybersecurity Integrations",   # ServiceNow's own role, no platform word
    "Software Engineer III - Data Engineer",
    "Backend Engineer",
    "Software Development Engineer II, Payments",
    "Specialist CRM Software Engineer",                         # CRM alone is left to the scorer
    "Software Engineer, Sapient Platform",                      # 'sap' only as a whole word
    "Full Stack Developer - Dynamic Pricing",                   # 'dynamic' is not 'dynamics'
    "API Developer (Biometrics)",                               # 'bi' only as a whole word
])
def test_prefilter_keeps_real_backend_titles_near_the_platform_words(title):
    assert should_evaluate_job(_india(title))[0], title


def test_prefilter_platform_exclusion_ignores_the_company_field():
    """A role at Salesforce or ServiceNow is judged by its title; only the title is matched."""
    for company in ("Salesforce", "ServiceNow", "SAP", "Workday"):
        assert should_evaluate_job(_india("Software Engineer, Backend", company=company))[0], company


# T61: titles that name a language or domain outside the target stack (C++, embedded, kernel, GPU,
# Rust, Ruby, PHP) were 56 of 1,191 survivors (4.7%, measured 2026-10-06); every labelled example is a `no`.
@pytest.mark.parametrize("title", [
    "Software Engineer (C++)",
    "Senior Software Engineer - C/C++, Linux/ Unix, Cloud",
    "Senior Software Engineer - Layer1 - C++",
    "Sr. Software Development Engineer (Backend Dev - C/C++)",
    "Embedded SDE - Security, Silicon & Systems Group",
    "Senior SDE- Kernel Engineer, SSG",
    "SDE IV - GPU Engineer",
    "CUDA Software Engineer",
    "Firmware Engineer",
    "Low Latency FPGA Developer",
    "Senior Backend Engineer (Ruby), Production Engineering",
    "Software Engineer, Backend (Rust)",
    "Full Stack Developer (PHP)",
])
def test_prefilter_rejects_non_target_stack_titles(title):
    ok, reason = should_evaluate_job(_india(title))
    assert not ok and "exclude" in reason


@pytest.mark.parametrize("title", [
    "Software Engineer, Backend (Node.js)",
    "Backend Engineer - Distributed Systems",
    "Software Engineer - Payments",
    "Software Engineer, Rustic Analytics",       # whole words only
    "Backend Engineer, Cpp-free Platform",       # not C++
    "Software Engineer (TypeScript, Kafka)",
])
def test_prefilter_keeps_titles_that_only_resemble_the_new_words(title):
    assert should_evaluate_job(_india(title))[0], title


# T11: Adobe's engineering ladder is "Computer Scientist"; 13 of its 14 India postings were rejected for
# having no include word (measured 2026-10-06), though MTS titles at other firms already pass.
@pytest.mark.parametrize("title", [
    "Computer Scientist",
    "Computer Scientist 2",
    "Computer Scientist II",
    "Computer Scientist - II",
    "Senior Computer Scientist - Agentic AI",
])
def test_prefilter_accepts_computer_scientist_titles(title):
    assert should_evaluate_job(_india(title))[0], title


@pytest.mark.parametrize("title", [
    "Computer Scientist I (Frontend)",
    "Senior Computer Scientist (Architect)",
    "Computer Scientist- C++",
    "Computer Scientist - Java, Microservices, Agentic AI",
    "Principal Computer Scientist",
    "Staff Computer Scientist",
])
def test_prefilter_computer_scientist_still_obeys_the_exclusions(title):
    assert not should_evaluate_job(_india(title))[0], title


def test_measure_prefilter_counts_jobs_blocked_only_by_a_language_word():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path("scripts").resolve()))
    import measure_prefilter as mp

    rows = [
        {"company": "A", "ats": "x", "title": "Software Engineer, Backend (Golang)", "location": "Bengaluru, India", "posted_at": "2026-10-05"},
        {"company": "A", "ats": "x", "title": "Senior Java Developer", "location": "Pune, India", "posted_at": ""},
        {"company": "A", "ats": "x", "title": "Staff Java Developer", "location": "Pune, India", "posted_at": ""},       # two blockers
        {"company": "A", "ats": "x", "title": "Golang Developer", "location": "London, UK", "posted_at": ""},            # not India
        {"company": "A", "ats": "x", "title": "Software Engineer, Backend (Node.js)", "location": "Bengaluru, India", "posted_at": ""},
    ]
    costs = mp.exclusion_costs(rows)
    assert costs["golang"] == {"only": 1, "recent": 0 if mp.posted_age_days("2026-10-05") > 30 else 1}
    assert costs["java"]["only"] == 1 and "python" not in costs
    assert [r["title"] for r in mp.survivors(rows)] == ["Software Engineer, Backend (Node.js)"]


def test_measure_prefilter_counts_a_job_posted_today_as_recent():
    """Age 0 is falsy: `(age or 9999) <= 30` counted every job posted on the day of the fetch as old
    (407 of the 34,416 jobs fetched 2026-10-06), so T62's '<= 30 days' column was understated."""
    import sys
    from datetime import date
    from pathlib import Path
    sys.path.insert(0, str(Path("scripts").resolve()))
    import measure_prefilter as mp

    rows = [{"company": "A", "ats": "x", "title": "Software Engineer, Backend (Golang)",
             "location": "Bengaluru, India", "posted_at": date.today().isoformat()},
            {"company": "A", "ats": "x", "title": "Golang Developer", "location": "Pune, India", "posted_at": ""}]
    assert mp.exclusion_costs(rows)["golang"] == {"only": 2, "recent": 1}   # undated is not recent


# -- T62: "python" is allowed in titles (Manish, 2026-10-10: allow for now, decide again on the results). Java and
# golang stay excluded: he only named python. -----------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Python Developer",
    "Senior Python Developer",
    "Software Engineer, Backend (Python)",
    "Software Engineer III - Python LLM Engineer",
    "Backend Python Engineer",
    "Python Backend Developer with AWS and SQL",
    "Software Engineer - Python/Django",
])
def test_python_titles_pass_the_prefilter(title):
    assert should_evaluate_job(_india(title))[0], title


@pytest.mark.parametrize("title", [
    "Staff Python Engineer",              # seniority words still reject
    "Python Lead Developer",
    "Python Architect",
    "Python Developer Intern",
    "Python Data Scientist",              # no include word: the title names no backend role
    "Java Python Developer",              # java is still excluded
    "Golang / Python Backend Developer",  # so is golang
    "Python Test Engineer",
    "Python Django Frontend Developer",
])
def test_python_does_not_open_the_door_to_other_exclusions(title):
    assert not should_evaluate_job(_india(title))[0], title
