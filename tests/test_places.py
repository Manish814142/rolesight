"""T136 (T108 part 1): the person's countries from config.json, the built-in place packs, and the pre-filter's place rule."""
import pytest

from job_hunt import places as pl
from job_hunt.models import JobPosting
from job_hunt.prefilter import should_evaluate_job


def _job(location, title="Backend Engineer", remote=False):
    return JobPosting(global_id="t:1", ats="greenhouse", company="Acme", title=title, location=location, is_remote=remote,
                      url="https://example.com/1")


def _places(*countries, home="India"):
    return pl.places_from_config({"candidate": {"countries": list(countries), "home_country": home}})


@pytest.fixture(autouse=True)
def _india_after_each_test():
    yield
    pl.configure_places(pl.INDIA)


# ── config ───────────────────────────────────────────────────────────────────

def test_no_countries_means_india_only():
    for cfg in ({}, {"candidate": {}}, {"candidate": {"countries": []}}, {"candidate": {"countries": ["India"]}},
                {"candidate": {"countries": "india"}}):
        p = pl.places_from_config(cfg)
        assert p.india_only() and p.label() == "India" and p.home == "India", cfg


@pytest.mark.parametrize("written, name", [
    ("UK", "United Kingdom"), ("u.k.", "United Kingdom"), ("Britain", "United Kingdom"), ("united kingdom", "United Kingdom"),
    ("Deutschland", "Germany"), ("Holland", "Netherlands"), ("the Netherlands", "Netherlands"), ("Ireland", "Ireland"),
    ("UAE", "United Arab Emirates"), ("Dubai", "United Arab Emirates"), ("singapore", "Singapore"), ("Bharat", "India"),
])
def test_a_country_is_found_however_it_is_written(written, name):
    p = _places(written)
    assert [c.name for c in p.countries] == [name] and p.countries[0].known


def test_a_comma_separated_string_and_duplicates():
    p = pl.places_from_config({"candidate": {"countries": "UK, Germany, uk, Deutschland"}})
    assert p.label() == "United Kingdom, Germany" and not p.india_only()


def test_an_unknown_country_works_by_its_name_and_is_reported():
    p = _places("Atlantis")              # no country of that name (T142: every real one has a pack)
    assert p.unknown() == ["Atlantis"] and p.countries[0].workday_terms == ("Atlantis",)
    assert p.countries_in("Poseidonia, Atlantis") and not p.countries_in("Poseidonia")
    assert should_evaluate_job(_job("Poseidonia, Atlantis"), places=p)[0]


# ── which country a location names ───────────────────────────────────────────

@pytest.mark.parametrize("location, expected", [
    ("London, UK", "United Kingdom"), ("London, England, GBR", "United Kingdom"), ("Belfast, Northern Ireland", "United Kingdom"),
    ("Edinburgh", "United Kingdom"), ("Remote - USA; London, United Kingdom", "United Kingdom"),
    ("München, Germany", "Germany"), ("Muenchen", "Germany"), ("Berlin, de", "Germany"), ("Frankfurt, Hesse, DEU", "Germany"),
    ("Amsterdam, North Holland, Netherlands", "Netherlands"), ("NL - Amsterdam", "Netherlands"),
    ("Dublin, IRL", "Ireland"), ("Cork", "Ireland"),
    ("Dubai, ARE", "United Arab Emirates"), ("Abu Dhabi", "United Arab Emirates"), ("SGP", "Singapore"),
    ("Singapore, Singapore", "Singapore"),
    # North American twins and lookalikes are not the country
    ("London, Ontario", None), ("London, ON, Canada", None), ("Cambridge, MA", None), ("Dublin, OH", None),
    ("Dublin, CA 94568", None), ("US-CA-Dublin", None), ("Birmingham, AL", None), ("Berlin, NH", None), ("Amsterdam, New York", None),
    ("Wilmington, DE", None), ("Remote - New England", None), ("Sydney, New South Wales", None), ("Ukraine", None),
    ("Bengaluru, India", None),
])
def test_countries_in(location, expected):
    p = _places("UK", "Germany", "Netherlands", "Ireland", "UAE", "Singapore")
    found = p.countries_in(location)
    assert (found[0].name if found else None) == expected


def test_regions_of_your_countries():
    europe = _places("Germany")
    assert europe.region_in("Remote - EMEA") and europe.region_in("Europe") and europe.region_in("Remote (EU)")
    assert europe.region_in("DACH") and not europe.region_in("APAC") and not europe.region_in("Remote - LATAM")
    assert _places("Singapore").region_in("APAC") and _places("UAE").region_in("GCC")
    assert not _places("UK").region_in("Remote (EU)")         # the UK is not in the EU


def test_needs_visa_outside_the_home_country():
    p = _places("UK", "India")
    assert p.needs_visa("London, UK") and p.needs_visa("Remote - EMEA")
    assert not p.needs_visa("Bengaluru, India") and not p.needs_visa("Remote") and not p.needs_visa("London, UK; Pune, India")
    assert not _places("UK", home="United Kingdom").needs_visa("London, UK")


# ── the pre-filter with your places ──────────────────────────────────────────

@pytest.mark.parametrize("location, remote, kept", [
    ("Dubai, United Arab Emirates", False, True), ("Singapore", False, True), ("Dubai, ARE", False, True),
    ("Bengaluru, India", False, False), ("Remote - India", True, False), ("London, UK", False, False),
    ("Remote - EMEA", True, True), ("Remote - APAC", True, True), ("Remote", True, True), ("Worldwide", False, True),
    ("Remote - US", True, False), ("Remote, Germany", True, False), ("San Francisco, CA", False, False), ("", False, False),
    ("Remote", False, True),          # review: "Remote" written in the location, the board's flag off (India keeps it too)
])
def test_should_evaluate_job_with_uae_and_singapore(location, remote, kept):
    p = _places("UAE", "Singapore")
    ok, reason = should_evaluate_job(_job(location, remote=remote), places=p)
    assert ok is kept, reason
    if not ok:
        assert reason.startswith("Location") and "United Arab Emirates, Singapore" in reason


@pytest.mark.parametrize("location, kept", [
    ("EMEA", True), ("Remote - EMEA", True), ("Remote: EMEA", True), ("Middle East (Remote)", True),
    # found on the 2026-10-21 fetch: a region next to another named place is that place, not yours
    ("EMEA - UK", False), ("EMEA, USA", False), ("Novi Sad, South Bačka, Serbia, EMEA", False),
    ("EMEA; Amsterdam, Netherlands; Krakow, Poland", False),
])
def test_a_region_counts_only_when_it_names_no_other_place(location, kept):
    assert should_evaluate_job(_job(location, remote="Remote" in location), places=_places("UAE"))[0] is kept


def test_the_title_still_decides_first():
    ok, reason = should_evaluate_job(_job("Dubai", title="Java Developer"), places=_places("UAE"))
    assert not ok and reason.startswith("Title")


def test_cities_narrow_a_country_as_they_do_india():
    p = _places("UK")
    assert should_evaluate_job(_job("Manchester, UK"), cities=["Manchester"], places=p)[0]
    assert not should_evaluate_job(_job("Leeds, United Kingdom"), cities=["Manchester"], places=p)[0]
    assert should_evaluate_job(_job("Remote, United Kingdom", remote=True), cities=["Manchester"], places=p)[0]
    assert should_evaluate_job(_job("United Kingdom"), cities=["Manchester"], places=p)[0]   # no city named
    # review: a remote job in another of its cities stays, as "Remote - Pune, India" does for India with cities ["Bengaluru"]
    assert should_evaluate_job(_job("Remote - Leeds, UK", remote=True), cities=["Manchester"], places=p)[0]


def test_india_with_another_country_keeps_india_jobs():
    p = _places("India", "Germany")
    for loc in ("Bengaluru, India", "Coimbatore", "Remote - India", "Berlin, Germany", "IND - Remote"):
        assert should_evaluate_job(_job(loc, remote="Remote" in loc), places=p)[0], loc
    assert not should_evaluate_job(_job("Remote - US", remote=True), places=p)[0]
    assert not should_evaluate_job(_job("Coimbatore, Tamil Nadu"), cities=["Pune"], places=p)[0]   # India's cities too
    assert should_evaluate_job(_job("Pune, India"), cities=["Pune"], places=p)[0]


def test_apac_is_a_named_place_for_someone_not_looking_in_asia():
    assert not should_evaluate_job(_job("Remote - APAC", remote=True), places=_places("UK"))[0]
    assert should_evaluate_job(_job("Remote - APAC", remote=True), places=_places("Singapore"))[0]


INDIA_CASES = ["Bengaluru, India", "Pune", "Coimbatore, Tamil Nadu", "Remote - India", "IND - Remote", "Jaipur, RJ, in",
               "Indianapolis, IN", "Makati City, NCR, ph", "Remote", "Remote - US", "Worldwide", "London, UK", "Berlin",
               "Singapore", "Remote - APAC", "Remote (Full Time - Remote)", "Hybrid", "", "San Francisco, CA",
               "Paris, France", "Dubai", "Remote, Singapore", "Global", "EMEA", "Delhi NCR", "Gurgaon; London",
               "Remote - Europe", "Anywhere", "3 Locations", "Tokyo, Japan", "Remote, Canada", "New York, NY",
               "Kochi, Japan", "Remote - IST", "Remote, UTC+5:30", "Telecommute", "Home Office", "Hyderabad (Office)",
               "Noida, Uttar Pradesh", "Remote - LATAM"]


@pytest.mark.parametrize("cities", [None, ["Pune"]])
def test_india_only_gives_todays_answers(cities):
    """Configured India-only (or nothing configured) answers exactly what the filter answered before T136."""
    for loc in INDIA_CASES:
        for remote in (False, True):
            job = _job(loc, remote=remote)
            before = should_evaluate_job(job, cities=cities)          # places=None: the active one, India by default
            assert should_evaluate_job(job, cities=cities, places=pl.INDIA) == before, loc
            assert should_evaluate_job(job, cities=cities, places=_places("India")) == before, loc
    # ...and those answers are the original rules' own, not the new rule's ("not in your places")
    assert should_evaluate_job(_job("London, UK"), places=pl.INDIA) == (
        False, "Location 'London, UK' is tied to a non-India region: 'London'")
    assert should_evaluate_job(_job("Remote, Singapore", remote=True), places=pl.INDIA) == (
        False, "Location 'Remote, Singapore' is remote but names a non-India place: 'Singapore'")
    assert should_evaluate_job(_job("Remote - APAC", remote=True), places=pl.INDIA) == (True, "passed")


def test_the_active_places_are_what_the_scan_configured():
    assert pl.active_places().india_only()
    pl.configure_places({"candidate": {"countries": ["Singapore"]}})
    assert pl.active_places().label() == "Singapore"
    assert should_evaluate_job(_job("Singapore"))[0] and not should_evaluate_job(_job("Pune, India"))[0]
