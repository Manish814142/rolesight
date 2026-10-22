"""T149: a `seeking` or `profile` that names India and none of your countries is warned about.

Measured 2026-10-21 (the review of T133-T143, Gemini 3.5 flash-lite, UK rubric): with Manish's `seeking` ("… Bengaluru / India")
postings in London that offer visa sponsorship scored 25 and 30 and a silent one 25, every reason citing work authorisation; the
same postings with a UK `seeking` scored 50, 45 and 75."""
import pytest

from job_hunt import llm_utils
from job_hunt import places as pl

INDIA_SEEKING = "Backend Engineer / Full Stack Engineer, Remote / Hybrid / Bengaluru / India"
INIT_SEEKING = ("Backend or platform roles in United Kingdom. I live in India; for a role outside India I need the employer to "
                "sponsor my work visa and relocation")                      # what `init --countries "United Kingdom"` writes


def _places(*countries):
    return pl.places_from_config({"candidate": {"countries": list(countries)}})


@pytest.mark.parametrize("candidate, countries, field", [
    ({"seeking": INDIA_SEEKING}, ["United Kingdom"], "seeking"),
    ({"profile": "3 YOE backend engineer based in Pune"}, ["United Kingdom"], "profile"),
    ({"seeking": "Backend roles, remote or hybrid in Bengaluru"}, ["Singapore", "United Arab Emirates"], "seeking"),
    ({"seeking": INIT_SEEKING}, ["United Kingdom"], None),                          # names your country, and home as home
    ({"seeking": "Backend roles in London; I live in Pune"}, ["United Kingdom"], None),
    ({"seeking": "Backend roles, remote in Europe; I live in India"}, ["Germany"], None),   # a region that includes yours
    ({"seeking": INDIA_SEEKING}, ["India"], None),                                  # India alone: the original rules
    ({"seeking": INDIA_SEEKING}, ["India", "United Kingdom"], None),                # India is one of your countries
    ({"seeking": "Backend roles, remote"}, ["United Kingdom"], None),               # names no place
    ({}, ["United Kingdom"], None),
])
def test_profile_warning(candidate, countries, field):
    warning = llm_utils.profile_warning({"candidate": candidate}, _places(*countries))
    if field is None:
        assert warning is None
    else:
        assert warning.startswith(f"candidate.{field} names India") and ", ".join(countries) in warning
        assert "Backend or platform roles in" in warning                            # it says what to write instead
