"""T96: a generic engineer title goes to Gemini, which judges the description (T69 g, Manish 2026-10-14).

Companies name roles differently: "Senior Engineer", "Engineer II" or "Engineer III, Software" can be a backend job for someone
with 3.3 years. The title rule had only an include list of role words, so those never reached Gemini. Measured on the fetch of
2026-10-13: 310 India jobs start with "Engineer" (44 posted in the last 7 days) and 25 have "software" and "engineer" in some
other order (5 in the window). Most of the first group are hardware, support or IT roles, which the rubric scores low: the
price is a few scoring calls a day, the gain is the roles a title list cannot know.
"""
import pytest

from job_hunt.models import JobPosting
from job_hunt.prefilter import should_evaluate_job, title_is_candidate


def _job(title, location="Pune, India"):
    return JobPosting(global_id="t:1", ats="greenhouse", company="X", title=title, location=location, is_remote=False,
                      url="https://example.com/1")


@pytest.mark.parametrize("title", [
    "Engineer", "Senior Engineer", "Sr Engineer", "Sr. Engineer", "Engineer I", "Engineer II", "Engineer III", "Engineer IV",
    "Senior Engineer-I", "Associate Engineer", "ENGINEER II", "Engineer - Infrastructure Services N 4A",
    "Engineer III, Software", "Engineer II - Software Development", "Senior Engineer, Payments",
    "Software Integration Engineer-II", "Sr Software Application Engineer", "Senior Software Solutions Engineer",
    "Engineer, Product Applications",
])
def test_a_generic_engineer_title_reaches_gemini(title):
    assert should_evaluate_job(_job(title))[0], title
    assert title_is_candidate(title), title


@pytest.mark.parametrize("title", [
    "Lead Engineer", "Staff Engineer", "Principal Engineer", "Engineer Manager", "Senior Engineer - Embedded",
    "Engineer, Frontend", "Senior Engineer React", "Engineer II - Java", "Test Engineer", "Engineer - QA",
    "Engineer Intern", "Engineer, Salesforce", "Engineer - DevOps",
])
def test_the_exclude_words_still_win(title):
    assert not should_evaluate_job(_job(title))[0], title


@pytest.mark.parametrize("title", [
    "Data Engineer", "Senior Data Engineer", "Mechanical Engineer", "Field Service Engineer", "Sales Engineer",
    "Cloud Engineer", "Hardware Engineer", "Site Reliability Engineer", "Customer Success Engineer",
    "Business Analyst", "Account Executive", "Engineering Manager", "Marketing Engineer Intern",
])
def test_an_engineer_title_that_does_not_start_with_engineer_still_needs_an_include_word(title):
    """Only the titles that say nothing about the job are let through; "Data Engineer" names a different role."""
    assert not should_evaluate_job(_job(title))[0], title


def test_the_location_rules_still_apply_to_a_generic_title():
    assert should_evaluate_job(_job("Senior Engineer", "Coimbatore"))[0]
    assert not should_evaluate_job(_job("Senior Engineer", "Berlin, Germany"))[0]
    assert not should_evaluate_job(_job("Senior Engineer", "Austin, TX"))[0]


def test_the_words_a_title_must_not_start_with_are_not_enough_to_pass():
    """'Engineering' and 'Engineers' are not the word 'engineer'."""
    assert not should_evaluate_job(_job("Engineering Specialist"))[0]
    assert not should_evaluate_job(_job("Engineers Wanted"))[0]
