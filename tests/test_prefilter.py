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
        title="Senior Backend Engineer",
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
    "Sr. Software Engineer",
    "Software Engineer Intern",
    "Software Engineering Internship - Backend",
    "Front-end Developer",
    "ReactJS Developer",
    "Python Backend Developer",
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


@pytest.mark.parametrize("title", ["Senior Product Engineer", "Product Manager", "Product Designer"])
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
