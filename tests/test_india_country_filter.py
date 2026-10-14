"""T84: the location filter works on the country, and an optional `candidate.cities` list narrows it to cities.

Manish (2026-10-14) applies to jobs anywhere in India, so a job whose location is only "Coimbatore" or "Bhubaneswar" (no "India",
no state code) must pass. Before, only 11 cities and the word "india" counted: on the fetch of 2026-10-11, 362 jobs in other Indian
places were rejected, 26 of them with a title that passes. Anyone who wants fewer places lists their cities.
"""
import pytest

from job_hunt.models import JobPosting
from job_hunt.prefilter import city_matches, location_is_india, should_evaluate_job
from job_hunt.settings import cities_of


def _job(location, title="Backend Engineer", is_remote=False):
    return JobPosting(global_id="t:1", ats="greenhouse", company="X", title=title, location=location, is_remote=is_remote,
                      url="https://example.com/1")


@pytest.mark.parametrize("location", [
    "Coimbatore", "Indore", "Nagpur", "Bhubaneswar", "Lucknow", "Kochi, Kerala", "Jamshedpur", "Hubballi", "Dehradun",
    "Guwahati, Assam", "Telangana", "Goa", "Chandigarh", "Thiruvananthapuram", "Ludhiana", "Visakhapatnam", "Srinagar",
    "Greater Noida", "Madurai", "Nashik", "Raipur", "Vadodara, Gujarat", "Mysuru", "IND - Remote", "Bharat",
])
def test_any_indian_place_counts_as_india(location):
    assert location_is_india(location), location
    assert should_evaluate_job(_job(location))[0], location


@pytest.mark.parametrize("location", [
    "Indianapolis, IN", "London", "Austin, TX", "Lahore, Pakistan", "Dubai", "Springfield, Illinois", "Remote - Poland",
    "Indiana", "Singapore", "",
])
def test_places_outside_india_still_do_not(location):
    assert not location_is_india(location), location


def test_a_title_that_fails_still_fails_in_an_indian_city():
    assert not should_evaluate_job(_job("Coimbatore", title="Java Developer"))[0]


# -- the optional city filter ---------------------------------------------------------------------------------------

def test_no_cities_means_all_of_india():
    for location in ("Pune, India", "Coimbatore", "Hyderabad"):
        assert should_evaluate_job(_job(location), cities=None)[0]
        assert should_evaluate_job(_job(location), cities=[])[0]


def test_with_cities_only_those_cities_pass():
    cities = ["Pune", "Hyderabad"]
    assert should_evaluate_job(_job("Pune, Maharashtra, India"), cities=cities)[0]
    assert should_evaluate_job(_job("Hyderabad"), cities=cities)[0]
    kept, reason = should_evaluate_job(_job("Chennai, India"), cities=cities)
    assert not kept and "not in your cities" in reason and "Pune" in reason


def test_a_job_in_several_places_passes_when_one_of_them_is_chosen():
    assert should_evaluate_job(_job("Mumbai / Pune / Chennai"), cities=["pune"])[0]
    assert not should_evaluate_job(_job("Mumbai / Chennai"), cities=["pune"])[0]


@pytest.mark.parametrize("chosen,location", [
    ("Bangalore", "Bengaluru, Karnataka"), ("Bengaluru", "Bangalore"), ("Gurgaon", "Gurugram, Haryana"),
    ("Mumbai", "Navi Mumbai"), ("Cochin", "Kochi"), ("Trivandrum", "Thiruvananthapuram"), ("Madras", "Chennai"),
    ("Delhi NCR", "Noida, Uttar Pradesh"), ("Delhi NCR", "Gurugram"), ("Delhi NCR", "New Delhi"), ("Delhi NCR", "Faridabad"),
])
def test_the_usual_alternative_names_of_a_city_match(chosen, location):
    assert city_matches(location, [chosen]), (chosen, location)


def test_a_chosen_city_is_matched_as_a_whole_word_and_ignoring_case():
    assert city_matches("PUNE, INDIA", ["pune"])
    assert not city_matches("Pune", ["Pun"])
    assert not city_matches("Hyderabad, Pakistan", ["Pune"])


def test_remote_jobs_and_jobs_with_no_city_pass_whatever_the_cities_are():
    cities = ["Pune"]
    assert should_evaluate_job(_job("Remote - India"), cities=cities)[0]
    assert should_evaluate_job(_job("Hyderabad (Remote)", is_remote=True), cities=cities)[0]
    assert should_evaluate_job(_job("Remote", is_remote=True), cities=cities)[0]
    assert should_evaluate_job(_job("India"), cities=cities)[0], "no city named: benefit of the doubt, as for '3 Locations'"
    assert should_evaluate_job(_job("3 Locations", is_remote=True), cities=cities)[0]


def test_a_chosen_city_the_lists_do_not_know_still_counts_as_india():
    assert should_evaluate_job(_job("Anand"), cities=["Anand"])[0]
    assert not should_evaluate_job(_job("Anand"))[0], "without the choice it is an unknown place"


def test_cities_do_not_let_a_foreign_job_in():
    assert not should_evaluate_job(_job("London"), cities=["Pune"])[0]


# -- settings --------------------------------------------------------------------------------------------------------

def test_cities_of_reads_a_list_or_a_comma_separated_string():
    assert cities_of({}) == []
    assert cities_of({"candidate": {}}) == []
    assert cities_of({"candidate": {"cities": None}}) == []
    assert cities_of({"candidate": {"cities": ["Pune", " Hyderabad ", "", "Pune"]}}) == ["Pune", "Hyderabad"]
    assert cities_of({"candidate": {"cities": "Pune, Hyderabad"}}) == ["Pune", "Hyderabad"]
