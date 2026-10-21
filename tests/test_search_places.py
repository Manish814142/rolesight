"""T137 (T108 part 2): the five connectors that ask a board for one country search the person's countries."""
from unittest.mock import MagicMock, patch

import pytest

from job_hunt import places as pl
from job_hunt.adapters import fetch_company_jobs
from job_hunt.adapters import workday as wd
from job_hunt.adapters.base import begin_fetch, fetch_incomplete
from job_hunt.adapters.eightfold import fetch_eightfold
from job_hunt.adapters.oracle_hcm import fetch_oracle_hcm
from job_hunt.adapters.phenom import fetch_phenom


@pytest.fixture
def uk_sg():
    pl.configure_places({"candidate": {"countries": ["United Kingdom", "Singapore"]}})
    begin_fetch(None)
    yield
    pl.configure_places(pl.INDIA)


def _resp(data, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data
    r.raise_for_status.return_value = None
    r.headers = {}
    return r


def test_india_alone_asks_what_it_asked_before():
    assert pl.INDIA.workday_terms() == ["India"] and pl.INDIA.search_names() == ["India"]
    assert pl.INDIA.amazon_codes() == ["IND"]


def test_the_search_terms_of_several_countries():
    p = pl.places_from_config({"candidate": {"countries": ["UK", "UAE", "India", "Canada", "Brazil", "Atlantis"]}})
    assert p.workday_terms() == ["United Kingdom", "UK", "United Arab Emirates", "Dubai", "India", "Canada", "Brazil", "Atlantis"]
    assert p.search_names() == ["United Kingdom", "United Arab Emirates", "India", "Canada", "Brazil", "Atlantis"]
    assert p.amazon_codes() == ["GBR", "ARE", "IND", "CAN", "BRA"]        # Atlantis has no code


# ── Workday ──────────────────────────────────────────────────────────────────

def _wd_page(ids, loc):
    return _resp({"total": len(ids), "jobPostings": [
        {"title": f"Backend Engineer {i}", "locationsText": loc, "externalPath": f"/job/{i}", "bulletFields": [i]} for i in ids]})


@patch("requests.post")
def test_workday_searches_every_term_and_keeps_each_job_once(mock_post, uk_sg):
    pages = {"United Kingdom": _wd_page(["a", "b"], "London, UK"), "UK": _wd_page(["b", "c"], "Manchester, UK"),
             "Singapore": _wd_page(["d"], "Singapore")}
    mock_post.side_effect = lambda url, **kw: pages[kw["json"]["searchText"]]
    jobs = wd.fetch_workday("acme", "wd5", "ext")
    assert [c.kwargs["json"]["searchText"] for c in mock_post.call_args_list] == ["United Kingdom", "UK", "Singapore"]
    assert [j.url.rsplit("/", 1)[1] for j in jobs] == ["a", "b", "c", "d"]
    assert fetch_incomplete() is None


@patch("requests.post")
def test_workday_a_term_whose_first_page_repeats_an_earlier_term_reads_on(mock_post, uk_sg):
    """Review (ABB, 2026-10-21): "United Kingdom" found 44 jobs and "UK" 64, 74 distinct, but the adapter returned 44: "UK"'s
    first page held only jobs "United Kingdom" had returned, and T47's "a page adds nothing new" stop counted them as repeats.
    That stop is about a term repeating itself; a job another term returned is kept once and the term reads on."""
    first, more = [f"u{i}" for i in range(20)], [f"k{i}" for i in range(20)]

    def answer(url, **kw):
        term, offset = kw["json"]["searchText"], kw["json"]["offset"]
        ids = {"United Kingdom": first if offset == 0 else [], "UK": first if offset == 0 else more,
               "Singapore": ["s"] if offset == 0 else []}[term]
        return _resp({"total": {"United Kingdom": 20, "UK": 40, "Singapore": 1}[term], "jobPostings": [
            {"title": "Backend Engineer", "locationsText": "London, UK", "externalPath": f"/job/{i}", "bulletFields": [i]}
            for i in ids]})
    mock_post.side_effect = answer
    jobs = wd.fetch_workday("acme", "wd5", "ext")
    assert [j.url.rsplit("/", 1)[1] for j in jobs] == first + more + ["s"]


@patch("requests.post")
def test_workday_a_failed_term_keeps_the_others(mock_post, uk_sg):
    def answer(url, **kw):
        if kw["json"]["searchText"] == "UK":
            raise ConnectionError("HTTP 429 after retries")
        return _wd_page(["x"] if kw["json"]["searchText"] == "United Kingdom" else ["y"], "London, UK")
    mock_post.side_effect = answer
    jobs = wd.fetch_workday("acme", "wd5", "ext")
    assert len(jobs) == 2 and fetch_incomplete() == "page failed at offset 0"


@patch("requests.post")
def test_workday_a_missing_board_stops_every_term(mock_post, uk_sg):
    mock_post.return_value = _resp({}, status=404)
    assert wd.fetch_workday("gone", "wd5", "ext") == [] and mock_post.call_count == 1


@patch("requests.post")
def test_workday_the_budget_is_shared_by_the_terms(mock_post, uk_sg, monkeypatch):
    clock = iter([0.0, 1.0, 10_000.0, 10_000.0, 10_000.0])
    monkeypatch.setattr(wd.time, "monotonic", lambda: next(clock))
    mock_post.side_effect = lambda url, **kw: _wd_page(["a"], "London, UK")
    jobs = wd.fetch_workday("slow", "wd5", "ext", budget=600)
    assert len(jobs) == 1 and mock_post.call_count == 1
    assert fetch_incomplete().startswith("budget 600s spent")


# ── Eightfold, Phenom ────────────────────────────────────────────────────────

@patch("requests.get")
def test_eightfold_searches_each_country(mock_get, uk_sg):
    mock_get.side_effect = lambda url, **kw: _resp({"data": {"count": 1, "positions": [
        {"id": 1 if kw["params"]["location"] == "United Kingdom" else 2, "name": "Backend Engineer", "locations": ["x"]}]}})
    jobs = fetch_eightfold("acme.eightfold.ai", "acme.com", "Acme")
    assert [c.kwargs["params"]["location"] for c in mock_get.call_args_list] == ["United Kingdom", "Singapore"]
    assert [j.global_id for j in jobs] == ["eightfold:acme.com:1", "eightfold:acme.com:2"]


@patch("requests.get")
def test_eightfold_a_country_whose_first_page_another_country_returned_reads_on(mock_get, uk_sg):
    """Review: as for Workday's terms, a page of positions listed in both of your countries ("London; Singapore") is no reason
    to stop the second country's search; each position is kept once."""
    def answer(url, **kw):
        loc, start = kw["params"]["location"], kw["params"]["start"]
        ids = list(range(1, 11)) if loc == "United Kingdom" or start == 0 else list(range(11, 21))
        return _resp({"data": {"count": 10 if loc == "United Kingdom" else 20, "positions": [
            {"id": i, "name": "Backend Engineer", "locations": ["London", "Singapore"]} for i in ids]}})
    mock_get.side_effect = answer
    jobs = fetch_eightfold("acme.eightfold.ai", "acme.com", "Acme")
    assert [int(j.global_id.rsplit(":", 1)[1]) for j in jobs] == list(range(1, 21))


@patch("requests.post")
def test_phenom_selects_the_list_of_countries(mock_post, uk_sg):
    mock_post.return_value = _resp({"refineSearch": {"totalHits": 0, "data": {"jobs": []}}})
    fetch_phenom("careers.acme.com", "global/en", "Acme")
    assert mock_post.call_args.kwargs["json"]["selected_fields"] == {"country": ["United Kingdom", "Singapore"]}


# ── Oracle HCM ───────────────────────────────────────────────────────────────

def _facets(*names):
    return _resp({"items": [{"locationsFacet": [{"Name": n, "Id": 100 + i} for i, n in enumerate(names)]}]})


def _reqs(ids):
    return _resp({"items": [{"TotalJobsCount": len(ids), "requisitionList": [
        {"Id": i, "Title": "Backend Engineer", "PrimaryLocation": "London, United Kingdom", "PostedDate": "2026-10-20"} for i in ids]}]})


@patch("requests.get")
def test_oracle_reads_one_facet_per_country(mock_get, uk_sg):
    finders = []

    def answer(url, **kw):
        finders.append(kw["params"]["finder"])
        if "facetsList" in kw["params"]["finder"]:
            return _facets("United States", "United Kingdom", "Singapore")
        return _reqs([7, 8] if "=101," in kw["params"]["finder"] else [8, 9])
    mock_get.side_effect = answer
    jobs = fetch_oracle_hcm("x.fa.oraclecloud.com", "CX_1", "Acme")
    assert any("selectedLocationsFacet=101," in f for f in finders) and any("selectedLocationsFacet=102," in f for f in finders)
    assert [j.global_id.rsplit(":", 1)[1] for j in jobs] == ["7", "8", "9"]


@patch("requests.get")
def test_oracle_without_a_facet_for_one_country_reads_the_site_newest_first(mock_get, uk_sg):
    finders = []

    def answer(url, **kw):
        finders.append(kw["params"]["finder"])
        return _facets("United States", "Singapore") if "facetsList" in kw["params"]["finder"] else _reqs([1])
    mock_get.side_effect = answer
    jobs = fetch_oracle_hcm("x.fa.oraclecloud.com", "CX_1", "Acme")
    reads = [f for f in finders if "facetsList" not in f]
    assert len(reads) == 1 and "selectedLocationsFacet" not in reads[0] and "sortBy=POSTING_DATES_DESC" in reads[0]
    assert len(jobs) == 1


@patch("requests.get")
def test_oracle_for_india_still_returns_nothing_without_an_india_facet(mock_get):
    mock_get.return_value = _facets("United States", "Germany")
    assert fetch_oracle_hcm("x.fa.oraclecloud.com", "CX_1", "Acme") == [] and mock_get.call_count == 1


# ── Amazon ───────────────────────────────────────────────────────────────────

@patch("requests.get")
def test_amazon_searches_each_country_code_once_per_job(mock_get, uk_sg):
    def answer(url, **kw):
        code = kw["params"]["country"]
        return _resp({"hits": 2, "jobs": [{"id_icims": f"{code}1", "title": "SDE", "normalized_location": f"x, {code}"},
                                          {"id_icims": "shared", "title": "SDE", "normalized_location": "y"}]})
    mock_get.side_effect = answer
    jobs = fetch_company_jobs({"name": "Amazon", "ats": "amazon"})
    assert [c.kwargs["params"]["country"] for c in mock_get.call_args_list] == ["GBR", "SGP"]
    assert sorted(j.global_id for j in jobs) == ["amazon:GBR1", "amazon:SGP1", "amazon:shared"]


@patch("requests.get")
def test_amazon_skips_a_country_without_a_code(mock_get):
    pl.configure_places({"candidate": {"countries": ["Atlantis"]}})
    try:
        assert fetch_company_jobs({"name": "Amazon", "ats": "amazon"}) == [] and mock_get.call_count == 0
    finally:
        pl.configure_places(pl.INDIA)
