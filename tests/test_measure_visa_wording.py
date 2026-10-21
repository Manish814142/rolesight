"""T133: the classifiers behind scripts/measure_visa_wording.py (no network; hand-made postings)."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("mvw", Path(__file__).resolve().parent.parent / "scripts" / "measure_visa_wording.py")
mvw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mvw)


@pytest.mark.parametrize("location, expected", [
    ("London, UK", ["UK"]), ("Belfast, Northern Ireland", ["UK"]), ("Dublin, Ireland", ["Ireland"]), ("Berlin", ["Germany"]),
    ("München, Germany", ["Germany"]), ("Amsterdam, North Holland, Netherlands", ["Netherlands"]), ("Dubai, UAE", ["UAE"]),
    ("Singapore", ["Singapore"]), ("Remote - EMEA", ["Europe"]), ("Bengaluru, India", []),
    # a North American twin counts only when the country's own name is there too; since T143 it counts for its own country
    ("London, Ontario", ["Canada"]), ("Cambridge, MA", ["USA"]), ("Dublin, OH", ["USA"]), ("Reading, PA", ["USA"]),
    ("Remote - USA; London, United Kingdom", ["UK", "USA"]), ("New York, NY 10001; Berlin, Germany", ["Germany", "USA"]),
    ("Perth, WA", ["Australia"]), ("Auckland, New Zealand", ["New Zealand"]), ("Toronto, ON", ["Canada"]),
])
def test_countries_reads_the_target_places_and_skips_north_american_twins(location, expected):
    assert mvw.countries(location) == expected


@pytest.mark.parametrize("text, expected", [
    ("We are unable to sponsor visas for this role.", "refused"),
    ("We do not offer visa sponsorship.", "refused"),
    ("You must have the right to work in the UK.", "refused"),
    ("Candidates must already be authorized to work in Germany.", "refused"),
    # found by reading the first sample (2026-10-21): these were counted wrongly
    ("Eligibility to work in Germany required; this position is not eligible for employment visa sponsorship", "refused"),
    ("Please note this is a UK based role and requires individuals to have the right to work in this location", "refused"),
    ("Visa sponsorship is available.", "offered"),
    ("Competitive relocation packages and visa sponsorship where necessary for expats.", "offered"),
    ("Visa sponsorship: We do sponsor visas! However, we aren't able to successfully sponsor visas for every role and "
     "every candidate.", "offered"),                         # Anthropic's wording, as posted
    ("We sponsor visas for the right candidate.", "offered"),
    ("Relocation & visa support", "offered"),
    ("We will verify your right to work.", "mentioned"),
    ("Applicants must be authorized to work in the country in which they apply and will be required to provide proof.",
     "mentioned"),                                           # compliance boilerplate: no answer either way
    ("Lead our Fulham FC sponsorship activity locally.", "silent"),
    ("card scheme fees across Visa and Mastercard", "silent"),
    ("A great team and free lunch.", "silent"),
    ("", "silent"),
])
def test_visa_wording(text, expected):
    assert mvw.visa_wording(text)[0] == expected


def test_relocation_and_live_here_wording():
    assert mvw.relocation_wording("We offer a relocation package.") == "offered"
    assert mvw.relocation_wording("We can help you relocate to Berlin.") == "offered"
    assert mvw.relocation_wording("Relocation is not available for this role.") == "refused"
    assert mvw.relocation_wording("Hybrid, three days a week.") == "silent"
    assert mvw.residence_required("You must be based in the Netherlands.")
    assert not mvw.residence_required("Our office is based in Amsterdam.")


def test_analyse_counts_each_place_and_the_companies_offering():
    rows = [{"company": "A", "title": "Backend Engineer", "location": "London, UK", "description": "Visa sponsorship is available."},
            {"company": "A", "title": "Account Executive", "location": "London; Dublin", "description": "No visa sponsorship."},
            {"company": "B", "title": "Backend Engineer", "location": "Berlin, Germany", "description": "Nice team."},
            {"company": "C", "title": "Backend Engineer", "location": "Pune, India", "description": "Visa sponsorship is available."}]
    s = mvw.analyse(rows)
    assert s["UK"]["jobs"] == 2 and s["UK"]["visa"]["offered"] == 1 and s["UK"]["visa"]["refused"] == 1
    assert s["UK"]["offering"] == {"A"} and s["UK"]["companies"] == {"A"}
    assert s["Ireland"]["jobs"] == 1 and s["Germany"]["visa"]["silent"] == 1
    assert "India" not in s and set(s) == {"UK", "Ireland", "Germany"}
    titled = mvw.analyse(rows, titles_only=True)
    assert titled["UK"]["jobs"] == 1 and "Ireland" not in titled      # "Account Executive" names no engineering role
