"""T142: every country. Hand-made packs for the USA, Canada and Australia, GeoNames packs for the rest, and a location read
part by part so that a city counts only when what qualifies it names no other country."""
import importlib.util
from pathlib import Path

import pytest

from job_hunt import places as pl
from job_hunt.models import JobPosting
from job_hunt.prefilter import should_evaluate_job

ROOT = Path(__file__).resolve().parent.parent


def _places(*countries):
    return pl.places_from_config({"candidate": {"countries": list(countries)}})


def _in(location, *countries):
    return [c.name for c in _places(*countries).countries_in(location)]


@pytest.fixture(autouse=True)
def _india_after():
    yield
    pl.configure_places(pl.INDIA)


# ── every country has a pack ─────────────────────────────────────────────────

@pytest.mark.parametrize("written, name", [
    ("USA", "United States"), ("U.S.", "United States"), ("america", "United States"), ("Canada", "Canada"), ("AUS", "Australia"),
    ("Brazil", "Brazil"), ("BR", "Brazil"), ("JPN", "Japan"), ("korea", "South Korea"), ("Türkiye", "Turkey"),
    ("czech republic", "Czechia"), ("New Zealand", "New Zealand"), ("viet nam", "Vietnam"), ("Ivory Coast", "Ivory Coast"),
])
def test_any_country_resolves_to_a_known_pack(written, name):
    c = pl.country(written)
    assert c.known and c.name == name


def test_every_geonames_country_is_built_in():
    countries = pl.all_countries()
    assert len(countries) >= 250 and len({c.code for c in countries}) == len(countries)
    assert {c.code for c in pl.PACKS} <= {c.code for c in countries}


def test_a_generated_pack_has_codes_cities_regions_and_search_terms():
    br = pl.country("Brazil")
    assert (br.code, br.iso2, br.iso3, br.workday_terms) == ("BR", "br", "BRA", ("Brazil",))
    assert br.names("São Paulo") and br.names("Sao Paulo, SP, br") and br.names("Rio de Janeiro, BRA")
    assert br.in_region("Remote - LATAM") and not br.in_region("Remote - EMEA")
    assert pl.country("Japan").in_region("APAC") and pl.country("Poland").in_region("CEE")
    assert pl.country("Saudi Arabia").in_region("GCC") and not pl.country("Saudi Arabia").in_region("APAC")


# ── the USA, Canada and Australia ────────────────────────────────────────────

@pytest.mark.parametrize("location, expected", [
    ("Austin, TX", ["United States"]), ("Seattle, WA", ["United States"]), ("New York, NY 10001", ["United States"]),
    ("San Francisco Bay Area", ["United States"]), ("Remote - USA", ["United States"]), ("US-CA-Dublin", ["United States"]),
    ("Atlanta, Georgia", ["United States"]), ("Baltimore, MD, us", ["United States"]), ("Washington D.C.", ["United States"]),
    ("Toronto, ON", ["Canada"]), ("Toronto, CA", ["Canada"]), ("London, Ontario", ["Canada"]), ("St. John's, NL", ["Canada"]),
    ("Montréal, Quebec, Canada", ["Canada"]), ("Yellowknife, NT", ["Canada"]), ("CAN - Remote", ["Canada"]),
    ("Sydney, NSW", ["Australia"]), ("Perth, WA", ["Australia"]), ("Darwin, NT", ["Australia"]), ("Melbourne VIC", ["Australia"]),
    ("AU-Melbourne", ["Australia"]), ("Canberra, ACT, au", ["Australia"]),
    ("San Jose, CA", ["United States"]), ("Melbourne, FL", ["United States"]), ("Sydney, NS", ["Canada"]),
    ("London, UK", []), ("Bengaluru, India", []),
])
def test_the_new_packs(location, expected):
    assert _in(location, "United States", "Canada", "Australia") == expected


# ── codes that are also states, countries that are also cities ───────────────

@pytest.mark.parametrize("location, expected", [
    ("Munich, DE", ["Germany"]), ("Wilmington, DE", ["United States"]), ("Berlin, DE (Hybrid)", ["Germany"]),
    ("Amsterdam, NL", ["Netherlands"]), ("Paris, FR", ["France"]),
    ("St. Gallen, SG, ch", ["Switzerland"]), ("Ho Chi Minh City, SG, vn", ["Vietnam"]),       # a region's code, not Singapore
    ("St. Gallen, SG, Switzerland", ["Switzerland"]),                    # a code in the middle is a region's, also with no suffix
    ("Magdeburg, SA, de", ["Germany"]), ("Eindhoven, NB, nl", ["Netherlands"]), ("Pozuelo de Alarcón, MD, es", ["Spain"]),
    ("Belfast, Northern Ireland, United Kingdom", ["United Kingdom"]),
])
def test_codes_that_are_states_or_countries(location, expected):
    assert _in(location, "Germany", "United States", "Netherlands", "France", "Switzerland", "Vietnam", "Singapore", "Spain",
               "Canada", "Australia", "United Kingdom", "Ireland") == expected


@pytest.mark.parametrize("location, expected", [
    ("London, Singapore", ["United Kingdom", "Singapore"]),              # a city-state is one more city
    ("New York, Dubai, London, Miami, Bangalore", ["United Kingdom", "United Arab Emirates", "United States"]),
    ("New York; London", ["United Kingdom", "United States"]), ("Chicago, New York, London or Bristol", ["United Kingdom", "United States"]),
    ("London, Ontario", ["Canada"]), ("Aberdeen, MD (Full-Time)", ["United States"]), ("Brighton Beach, NY", ["United States"]),
    ("Glasgow, Delaware, United States", ["United States"]), ("Cardiff, NSW, au", ["Australia"]),
    ("CA-ON-London", ["Canada"]), ("CA - London", ["Canada"]),            # a code prefix qualifies the city after it
    ("CA - Montreal, London", ["Canada"]),                               # ...and every city of its part
])
def test_a_city_counts_unless_what_qualifies_it_names_another_country(location, expected):
    assert _in(location, "United Kingdom", "Singapore", "United Arab Emirates", "United States", "Canada", "Australia") == expected


def test_the_filter_with_a_generated_country():
    p = _places("Brazil")
    job = lambda loc, remote=False: JobPosting("t:1", "gh", "A", "Backend Engineer", loc, remote, "u")  # noqa: E731
    assert should_evaluate_job(job("São Paulo, Brazil"), places=p)[0]
    assert should_evaluate_job(job("Remote - LATAM", True), places=p)[0]
    assert not should_evaluate_job(job("Remote - US", True), places=p)[0]
    assert not should_evaluate_job(job("Lisbon, Portugal"), places=p)[0]


def test_explicit_countries_reads_one_part():
    assert pl.explicit_countries("Austin, Texas, United States") == {"US"}
    assert pl.explicit_countries("Tbilisi, Georgia") == {"GE"} and pl.explicit_countries("Atlanta, GA") == {"US"}
    assert pl.explicit_countries("Remote - New England") == {"US"} and "GB" not in pl.explicit_countries("Sydney, New South Wales")
    # review: a mutant that let "NA - Remote" be Namibia passed every test (North America or n/a, not a country code)
    assert pl.explicit_countries("NA - Remote") == set() and pl.explicit_countries("NA – Remote (US)") == {"US"}


# ── the data file and its builder ────────────────────────────────────────────

SPEC = importlib.util.spec_from_file_location("bc", ROOT / "scripts" / "build_countries.py")
bc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bc)

INFO = ("# ISO\tISO3\tnum\tfips\tCountry\tCapital\tArea\tPopulation\tContinent\n"
        "ES\tESP\t724\tSP\tSpain\tMadrid\t504782\t46723749\tEU\n"
        "VE\tVEN\t862\tVE\tVenezuela\tCaracas\t912050\t28870195\tSA\n")


def _city(name, iso2, pop):
    return "\t".join(["1", name, name, "", "0", "0", "P", "PPL", iso2, "", "", "", "", "", str(pop), "", "", "", ""])


def test_a_city_name_belongs_to_the_country_with_its_biggest_instance():
    cities = "\n".join([_city("Madrid", "ES", 3_255_944), _city("Valencia", "ES", 814_208), _city("Valencia", "VE", 1_484_430),
                        _city("Caracas", "VE", 3_000_000)])
    out = bc.build(INFO, cities)
    assert out["ES"]["cities"] == ["Madrid"] and out["VE"]["cities"] == ["Caracas", "Valencia"]
    assert out["ES"]["regions"] == ["europe", "eu", "eea", "emea"] and "latam" in out["VE"]["regions"]
    assert out["ES"]["iso3"] == "ESP" and out["ES"]["name"] == "Spain"


def test_the_shipped_countries_file():
    import json
    data = json.loads((ROOT / "job_hunt" / "data" / "countries.json").read_text(encoding="utf-8"))
    assert data["source"]["licence"] == "CC BY 4.0" and len(data["countries"]) >= 250
    assert data["countries"]["US"]["iso3"] == "USA" and "Toronto" in data["countries"]["CA"]["cities"]


# ── T146: misreads found by T144's bulk check (boards accepted for Europe only on a US or Brazilian place) ──────

@pytest.mark.parametrize("location, expected", [
    ("Gulf Shores, AL", []), ("Gulf Breeze, FL", []), ("2082 Gulf To Bay Blvd Clearwater, FL", []),     # not the Gulf
    ("Gulf Region - Middle East (Remote)", ["United Arab Emirates"]), ("Remote - GCC", ["United Arab Emirates"]),
    ("Hybrid (NYC, MPK, DC, SEA)", []), ("SF, SEA, NYC", []),                                           # Seattle
    ("Remote - Southeast Asia", ["Singapore"]),
    ("New London", []), ("New Britain, CT", []), ("New Holland, Pennsylvania, United States", []),        # "New ..." elsewhere
    ("New Glasgow (Contract Full time)", []),
    ("4900 Florence Street, Denver, CO 80238", []), ("29300 Lyon Pines Drive, New Hudson, MI 48165", []),  # a street
    ("192 Adelaide St W, Toronto, ON M5H 0A4", []), ("10 Downing Street, London", ["United Kingdom"]),
    ("London, On", []), ("Dublin, Oh", []), ("Berlin, De", ["Germany"]),                                  # mixed-case codes
    ("Porto Alegre, Rio Grande do Sul, Brazil", []), ("Porto, Portugal", ["Portugal"]), ("Porto", ["Portugal"]),
    ("London, UK", ["United Kingdom"]), ("Amsterdam, Holland", ["Netherlands"]), ("Leeds, Great Britain", ["United Kingdom"]),
])
def test_misreads_found_by_the_bulk_check(location, expected):
    p = pl.places_from_config({"candidate": {"countries": [
        "United Kingdom", "Germany", "Netherlands", "Ireland", "United Arab Emirates", "Singapore", "France", "Italy", "Portugal",
        "Australia"]}})
    assert [c.name for c in p.countries_in(location)] + ([p.region_in(location).name] if p.region_in(location) and not
                                                          p.countries_in(location) else []) == expected


@pytest.mark.parametrize("location, code", [
    ("London, On", "CA"), ("Dublin, Oh", "US"), ("Perth, Wa", "AU"), ("New York, NY", "US"), ("Newark, New Jersey", "US"),
    ("Auckland, New Zealand", "NZ"), ("Papua New Guinea", "PG"), ("Nouméa, New Caledonia", "NC"), ("Remote in Brasil", "BR"),
    ("Albuquerque, New Mexico", "US"),
])
def test_what_the_new_rules_still_read(location, code):
    assert code in pl.explicit_countries(location)
    assert not pl.explicit_countries("New Guinea")                      # not Guinea


def test_the_builder_keeps_a_citys_longer_foreign_namesakes_out():
    cities = "\n".join([_city("Porto", "PT", 231_800), _city("Porto Alegre", "BR", 1_332_570), _city("Madrid", "ES", 3_255_944),
                        _city("Porto Salvo", "PT", 30_000),               # its own country's: "Porto" may stand before it
                        _city("Portoviejo", "EC", 200_000)])              # begins with the letters but is another word
    info = INFO + "PT\tPRT\t620\tPO\tPortugal\tLisbon\t92391\t10328900\tEU\nBR\tBRA\t076\tBR\tBrazil\tBrasilia\t8511965\t209469333\tSA\n"
    out = bc.build(info, cities)
    assert out["PT"]["not_followed_by"] == {"Porto": ["alegre"]} and "not_followed_by" not in out["ES"]
    assert "brasil" in out["BR"]["aliases"]
    assert "gulf" not in bc.REGIONS["gcc"][0].split("|") and "SEA" not in bc.REGIONS["sea"][0]


# ── T147: a department written like a country code (Personio: "office, department") ─────────────────────────────

@pytest.mark.parametrize("location, expected", [
    ("Hannover, IT", ["Germany"]), ("Gräfelfing, IT", []), ("Berlin, HR", ["Germany"]), ("Munich, QA", ["Germany"]),
    ("Gurugram, HR", []), ("Rome, IT", ["Italy"]), ("Milan, IT (Hybrid)", ["Italy"]), ("Zagreb, HR", ["Croatia"]),
    ("Doha, QA", ["Qatar"]), ("Hannover, PR", ["Germany"]), ("Hannover, AI", ["Germany"]), ("Hannover, BI", ["Germany"]), ("Paris, FR", ["France"]), ("Valencia, ES", ["Spain"]),        # other codes still end a location
    ("Bergamo, it", ["Italy"]), ("Hannover, Italy", ["Italy"]),
])
def test_a_department_is_not_a_country_code(location, expected):
    p = pl.places_from_config({"candidate": {"countries": ["Germany", "Italy", "Croatia", "Qatar", "France", "Spain"]}})
    assert sorted(c.name for c in p.countries_in(location)) == sorted(expected)
