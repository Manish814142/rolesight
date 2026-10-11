"""T77: the ATS's "remote" flag no longer carries a job whose location names a place outside India.

OpenAI's Ashby board flags its Paris, Tokyo, Singapore, Seoul, Madrid, Sydney and Washington DC offices as remote;
the exclude list (US, UK, Europe, London, …) knew none of those names, so about 3.4% of the pre-filter's survivors were
jobs in named non-India places that rubric rule 1 then capped, after a ~5 s Gemini call each. A remote job whose location
is only "Remote", "Worldwide", "Anywhere" or names India still passes.
"""
import pytest

from job_hunt.models import JobPosting
from job_hunt.prefilter import should_evaluate_job


def _job(location, is_remote=True, title="Backend Engineer"):
    return JobPosting(global_id="t:1", ats="ashby", company="X", title=title, location=location, is_remote=is_remote,
                      url="https://example.com/1")


@pytest.mark.parametrize("location", [
    "Paris", "Paris, France", "Tokyo", "Tokyo, Japan", "Singapore", "Seoul", "Seoul, South Korea", "Madrid", "Sydney",
    "Washington, DC", "Remote - Poland", "Remote, Brazil", "Amsterdam, Netherlands", "Dublin", "Toronto, Ontario",
])
def test_a_remote_flagged_job_in_a_named_non_india_place_is_rejected(location):
    passed, reason = should_evaluate_job(_job(location))
    assert not passed and "non-India" in reason, reason


@pytest.mark.parametrize("location", [
    "Remote", "remote", "", "Fully Remote", "Remote (Anywhere)", "Worldwide", "Remote - Global", "Work from home",
    "Remote - India", "India (Remote)", "Remote, Bengaluru",
])
def test_a_remote_job_with_no_place_or_an_india_place_still_passes(location):
    assert should_evaluate_job(_job(location))[0], location


@pytest.mark.parametrize("location", [
    "3 Locations", "51 Locations", "Location Negotiable", "Multiple Locations", "Various locations", "TBD",
    "Remote Work, More...", "Remote-first", "Hybrid", "Flexible", "Remote (APAC)", "Remote - Asia Pacific",
])
def test_a_placeholder_is_not_a_place(location):
    """Workday says "3 Locations" or "Location Negotiable" for a job whose real locations come from a later call (T23),
    and some boards say "Remote Work, More...": the remote flag keeps its benefit of the doubt there."""
    assert should_evaluate_job(_job(location))[0], location


@pytest.mark.parametrize("location", [
    "Remote - Karnataka", "Remote, Telangana", "Ahmedabad", "Kochi (Remote)", "Coimbatore, Tamil Nadu", "Remote - Goa",
])
def test_an_indian_place_the_main_city_list_lacks_is_not_a_non_india_place(location):
    """LOCATION_INDIA_PATTERN has 11 cities; a remote-flagged job in another Indian place must not be dropped."""
    assert should_evaluate_job(_job(location))[0], location


@pytest.mark.parametrize("location", ["Illinois Remote Work, More...", "California Southern Remote Work, More...", "Remote-Mexico City"])
def test_a_place_inside_a_placeholder_still_counts(location):
    assert not should_evaluate_job(_job(location))[0], location


def test_the_remote_word_in_the_text_counts_as_before_when_the_flag_is_off():
    assert should_evaluate_job(_job("Remote", is_remote=False))[0]
    assert not should_evaluate_job(_job("Paris (Remote)", is_remote=False))[0]


def test_a_non_remote_job_in_a_named_place_was_and_stays_rejected():
    assert not should_evaluate_job(_job("Paris", is_remote=False))[0]


# -- Review of T77 (2026-10-11): words that are not places, and India's own country code ----------------------------
# Measured on the fetch of 2026-10-11 with a passing title: "IND - Remote" and "IN - Remote - IND" (India's ISO code)
# and "Remote (Full Time - Remote)" were rejected as non-India places; boards put employment type, timezone and office
# words in the location field (1,180 jobs, e.g. "Bangalore (Fulltime)", "Singapore (Permanent)", "Hyderabad (Office)").
# A wrongly kept job costs one scoring call that rule 1 caps; a wrongly rejected one is never shown, so these pass.

@pytest.mark.parametrize("location", [
    "IND - Remote", "IN - Remote - IND", "Remote (Full Time - Remote)", "Remote - Full time", "Remote (Contract)",
    "Remote (Permanent)", "Remote - IST", "Remote (IST timezone)", "Remote, UTC+5:30", "Remote Friendly",
    "Home Office", "Telecommute", "Remote or Office (Depending on Region)", "Remote (Part-time)",
])
def test_words_that_are_not_places_and_indias_code_keep_the_benefit_of_the_doubt(location):
    assert should_evaluate_job(_job(location))[0], location


@pytest.mark.parametrize("location", [
    "Singapore (Permanent)", "Paris, France (Full-Time)", "Toronto/North America (Remote) (Full Time - Remote)",
    "Remote, Any, Sweden", "Remote - Paris Office",
])
def test_a_foreign_place_next_to_those_words_is_still_rejected(location):
    assert not should_evaluate_job(_job(location))[0], location
