"""T148: Workday employers found by name. The tenant, its data centre and its career sites come from the tenant's robots.txt;
the employer is confirmed from the postings' own text. No network: requests is stubbed."""
from unittest.mock import MagicMock

import pytest

from job_hunt import discovery as disc
from job_hunt import places as pl

EU = pl.places_from_config({"candidate": {"countries": ["United Kingdom", "Germany"]}})


@pytest.fixture(autouse=True)
def _india_after():
    yield
    pl.configure_places(pl.INDIA)


def _resp(status=200, text="", data=None):
    r = MagicMock()
    r.status_code, r.text, r.headers = status, text, {}
    r.json.return_value = data if data is not None else {}
    return r


ROBOTS = ("Sitemap: https://barclays.wd3.myworkdayjobs.com/External_Career_Site_Barclays/siteMap.xml\n"
          "Sitemap: https://barclays.wd3.myworkdayjobs.com/Early_Careers/siteMap.xml\nUser-agent: *\nAllow: /External_Career_Site_Barclays/\n")


@pytest.mark.parametrize("name, expected", [
    ("Barclays", ["barclays"]),
    ("Lloyds Banking Group", ["lloydsbankinggroup", "lloydsbanking"]),         # with and without "Group"; never "lloyds"
    ("Standard Chartered", ["standardchartered"]),                             # never "standard" (another company's tenant)
    ("Rolls-Royce", ["rollsroyce"]), ("Deutsche Bank AG", ["deutschebankag", "deutschebank"]),
    ("OLA (ANI Technologies Private Limited)", ["ola", "anitechnologiesprivatelimited", "anitechnologies"]),   # either side of a pasted brand
    ("Zalando SE", ["zalandose", "zalando"]),
])
def test_the_tenant_names_a_company_might_use(name, expected):
    assert disc.workday_tenant_slugs(name) == expected


def test_robots_txt_lists_the_sites_and_422_means_no_such_tenant(monkeypatch):
    calls = []
    def get(url, **kw):
        calls.append(url)
        assert kw["headers"]["Accept-Language"]                                 # without a language Workday answers 406
        return _resp(200, ROBOTS) if "barclays.wd3" in url else _resp(422)
    monkeypatch.setattr(disc.requests, "get", get)
    assert disc.workday_tenant_for("Barclays") == [("barclays", "wd3", "External_Career_Site_Barclays"), ("barclays", "wd3", "Early_Careers")]
    assert calls[0].startswith("https://barclays.wd3.") and len(calls) == 1      # wd3 first: Europe's, and the search stops there
    assert disc.workday_tenant_for("Nobody") == [] and all("nobody" in c for c in calls[1:])


def test_a_failing_request_is_asked_twice_then_skipped(monkeypatch):
    n = {"calls": 0}
    def get(url, **kw):
        n["calls"] += 1
        raise disc.requests.ConnectionError("reset")
    monkeypatch.setattr(disc.requests, "get", get)
    assert disc.workday_tenant_for("Zed") == [] and n["calls"] == 2 * len(disc.WORKDAY_DCS)


def test_the_seed_line_workday_auto():
    seeds = disc.parse_seeds("Barclays | workday | auto\nBarclays | workday | auto\nIntel | workday | intel | wd1 | External\nStripe\n")
    assert [s["name"] for s in seeds] == ["Barclays", "Intel", "Stripe"]          # a repeated line is one seed
    assert seeds[0] == {"name": "Barclays", "workday_auto": True} and seeds[1]["workday"]["site"] == "External"
    assert "url" not in seeds[0] and "workday_auto" not in seeds[2]


def _cxs(posts, detail_text):
    """requests.post (search) and requests.get (robots.txt and the detail call) for one tenant."""
    def post(url, **kw):
        return _resp(200, data={"total": len(posts), "jobPostings": posts})
    def get(url, **kw):
        if url.endswith("/robots.txt"):
            return _resp(200, ROBOTS) if "barclays.wd3" in url else _resp(422)
        return _resp(200, data={"jobPostingInfo": {"location": "London, UK", "jobDescription": detail_text}})
    return post, get


def _stub(monkeypatch, detail_text):
    posts = [{"title": "Java Developer", "locationsText": "London, UK", "externalPath": "/job/London/Java-Developer_1"}]
    post, get = _cxs(posts, detail_text)
    monkeypatch.setattr(disc.requests, "post", post)
    monkeypatch.setattr(disc.requests, "get", get)
    monkeypatch.setattr("job_hunt.adapters.workday.http_get", lambda url, **kw: get(url, **kw))
    monkeypatch.setattr(disc, "load_linkedin_cache", lambda path: ({}, {}))


def test_discover_finds_a_company_by_name_and_names_it_from_the_postings(monkeypatch):
    _stub(monkeypatch, "<p>Barclays is a British universal bank.</p>")
    verified, rows = disc.discover(disc.parse_seeds("Barclays | workday | auto\n"), workers=2, places=EU)
    assert [(v["name"], v["tenant"], v["dc"]) for v in verified] == [("Barclays", "barclays", "wd3")] * 2
    assert {v["site"] for v in verified} == {"External_Career_Site_Barclays", "Early_Careers"}
    assert verified[0]["places"] == ["United Kingdom", "Germany"]               # Workday keeps every place checked
    assert all(r["accepted"] and r["identity"].startswith("named in a job description") for r in rows)


def test_a_tenant_whose_postings_do_not_name_the_company_is_not_accepted(monkeypatch):
    _stub(monkeypatch, "<p>We are a family-run air conditioning firm.</p>")
    verified, rows = disc.discover(disc.parse_seeds("Barclays | workday | auto\n"), workers=2, places=EU)
    assert verified == [] and {r["verdict"] for r in rows} == {"identity not confirmed"}
    assert all("not named in 1 job description" in r["identity"] for r in rows)


def test_a_company_with_no_tenant_gets_a_report_row(monkeypatch):
    _stub(monkeypatch, "x")
    verified, rows = disc.discover(disc.parse_seeds("Nobody Ltd | workday | auto\n"), workers=2, places=EU)
    assert verified == [] and rows == [{"seed": "Nobody Ltd", "verdict": "no Workday tenant named like it", "accepted": False,
                                        "ats": "workday"}]


def test_a_seed_with_its_tenant_is_not_asked_about_a_name(monkeypatch):
    _stub(monkeypatch, "Barclays hires.")
    monkeypatch.setattr(disc, "workday_tenant_for", lambda name: pytest.fail("a seed with a tenant needs no search by name"))
    verified, _ = disc.discover(disc.parse_seeds("Barclays | workday | barclays | wd3 | Early_Careers\n"), workers=2, places=EU)
    assert [v["site"] for v in verified] == ["Early_Careers"] and "identity" not in verified[0]


def test_at_most_four_tenant_names_are_tried_per_company():
    assert len(disc.workday_tenant_slugs("Alpha Group (Beta Holdings Ltd) (Gamma Inc) (Delta Corp)")) == 4


def test_the_tenant_is_found_on_whichever_data_centre_it_is(monkeypatch):
    seen = []
    def get(url, **kw):
        seen.append(url.split(".")[1])
        return _resp(200, ROBOTS.replace("wd3", "wd5")) if "barclays.wd5" in url else _resp(422)
    monkeypatch.setattr(disc.requests, "get", get)
    assert disc.workday_tenant_for("Barclays")[0][:2] == ("barclays", "wd5") and seen == ["wd3", "wd1", "wd5"]


def test_a_plain_name_and_its_auto_seed_are_two_seeds():
    seeds = disc.parse_seeds("Barclays\nBarclays | workday | auto\n")
    assert [("workday_auto" in s) for s in seeds] == [False, True]


def _posts(*locations):
    return [{"title": "Engineer", "locationsText": loc, "externalPath": f"/job/{loc}/Engineer_{i}"} for i, loc in enumerate(locations)]


def _details(monkeypatch, naming):
    """The detail call answers with the company's name only for the postings whose path contains `naming`."""
    reads = []
    def fetch(cxs_base, path):
        reads.append(path)
        return "", ("Barclays is a bank." if naming in path else "A job.")
    monkeypatch.setattr(disc, "_fetch_detail", fetch)
    return reads


def test_the_postings_in_your_places_are_read_first(monkeypatch):
    pl.configure_places(EU)
    reads = _details(monkeypatch, "London")
    named, _ = disc._workday_names_company("Barclays", "https://x/cxs", _posts("Austin, TX", "Dallas, TX", "Miami, FL", "London, UK"))
    assert named and "London" in reads[0]                                   # the 4th posting, but the one in your places


def test_three_postings_are_read_and_no_more(monkeypatch):
    pl.configure_places(EU)
    reads = _details(monkeypatch, "Edinburgh")
    named, how = disc._workday_names_company("Barclays", "https://x/cxs", _posts("London, UK", "Leeds, UK", "Edinburgh, UK", "Bristol, UK"))
    assert named and len(reads) == 3                                        # the 3rd names it
    reads.clear()
    named, how = disc._workday_names_company("Barclays", "https://x/cxs", _posts("London, UK", "Leeds, UK", "Bristol, UK", "Edinburgh, UK"))
    assert not named and len(reads) == 3 and how == "not named in 3 job description(s) read"      # the 4th is never read


def test_a_name_of_two_letters_is_not_searched_for():
    assert disc.workday_tenant_slugs("GP") == [] and disc.workday_tenant_slugs("ING") == ["ing"]      # too short to be told from others
