"""T115: "NCR" is also Metro Manila's abbreviation (National Capital Region of the Philippines).

SmartRecruiters writes `Makati City, NCR, ph`; the pre-filter read the word NCR as Delhi NCR, so Philippine jobs passed the location
filter, and `discover` admitted 21 boards whose only "India" jobs were in Metro Manila (found by the review of T111, 2026-10-16).
NCR still counts as India unless the same location names the Philippines; any other Indian term in the location still counts.
"""
import pytest

import job_hunt.discovery as disc
from job_hunt.models import JobPosting
from job_hunt.prefilter import location_is_india, should_evaluate_job


def _job(location, title="Backend Engineer"):
    return JobPosting(global_id="t:1", ats="smartrecruiters", company="X", title=title, location=location, is_remote=False,
                      url="https://example.com/1")


@pytest.mark.parametrize("location", [
    "Makati City, NCR, ph", "Quezon City, NCR, ph", "Taguig, NCR, ph", "Manila, NCR, Philippines", "NCR, Philippines",
    "NCR, ph", "NCR, PH",                                                       # each marker on its own, so each one is tested
    "Makati, NCR", "Quezon City, NCR", "Taguig, NCR", "Pasig City, NCR", "Metro Manila, NCR", "Mandaluyong, NCR", "Pasay City, NCR",
    "Paranaque City, NCR", "Muntinlupa, NCR", "Caloocan, NCR", "Marikina, NCR",
])
def test_ncr_in_a_philippine_location_is_not_india(location):
    assert not location_is_india(location), location
    assert not disc._is_india(location), location
    assert not should_evaluate_job(_job(location))[0], location


@pytest.mark.parametrize("location", [
    "Delhi NCR", "NCR", "Gurgaon, NCR", "Noida, NCR, India", "New Delhi, NCR", "Delhi NCR, in", "Hybrid - NCR",
    "Gurugram, Haryana, India",
])
def test_ncr_in_an_indian_or_unnamed_place_is_still_india(location):
    assert location_is_india(location), location
    assert disc._is_india(location), location


@pytest.mark.parametrize("location", [
    "Makati City, NCR, ph; Pune, India", "Manila, Philippines | Hyderabad", "Makati, NCR, ph, Bengaluru", "Manila, Philippines; Mumbai, in",
])
def test_a_location_that_names_both_a_philippine_office_and_an_indian_one_is_india(location):
    assert location_is_india(location), location
    assert disc._is_india(location), location


def test_the_title_filter_is_untouched_by_the_location_rule():
    assert not should_evaluate_job(_job("Delhi NCR", title="Java Developer"))[0]
    assert should_evaluate_job(_job("Delhi NCR"))[0]
