"""T25: Eightfold careers sites (PCSX search + position_details). Fixtures follow the real responses of
micron.eightfold.ai and apply.ukg.com recorded 2026-10-06; no network."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from job_hunt.adapters import ENRICHERS, enrich_job, fetch_company_jobs
from job_hunt.adapters.eightfold import PAGE_SIZE, fetch_description, fetch_eightfold


@pytest.fixture(autouse=True)
def sleeps(monkeypatch):
    """Never really sleep; the list records every pause the adapter asks for."""
    recorded: list = []
    monkeypatch.setattr("job_hunt.adapters.eightfold.time.sleep", lambda s: recorded.append(s))
    return recorded


def _position(i: int, name: str = "", locations=None, posted: int = 1775692800, remote: str = "onsite") -> dict:
    return {"id": 41220000 + i, "displayJobId": f"JR{i}", "name": name or f"Backend Engineer {i}",
            "locations": locations if locations is not None else ["Bengaluru, Karnataka, India"],
            "standardizedLocations": ["Bengaluru, KA, IN"], "postedTs": posted, "department": "HIG",
            "workLocationOption": remote, "atsJobId": f"JR{i}", "positionUrl": f"/careers/job/{41220000 + i}"}


def _page(positions: list, count: int, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"status": 200, "data": {"count": count, "positions": positions}}
    resp.raise_for_status.return_value = None
    resp.iter_content.return_value = iter([b""])
    return resp


@patch("requests.get")
def test_fields_are_mapped(mock_get):
    mock_get.return_value = _page([_position(1, "MTS - ESD Design Engineer", ["Bengaluru, Karnataka, India", "Hyderabad, India"])], 1)
    [job] = fetch_eightfold("micron.eightfold.ai", "micron.com", company="Micron")
    assert job.ats == "eightfold" and job.company == "Micron"
    assert job.title == "MTS - ESD Design Engineer"
    assert job.global_id == "eightfold:micron.com:41220001"
    assert job.url == "https://micron.eightfold.ai/careers/job/41220001"
    assert job.location == "Bengaluru, Karnataka, India; Hyderabad, India"
    assert job.posted_at == "2026-04-09"            # postedTs 1775692800 is epoch seconds, UTC
    assert job.is_remote is False and job.description_text == ""   # the list has no description


@patch("requests.get")
def test_remote_work_location_option_sets_is_remote(mock_get):
    mock_get.return_value = _page([_position(1, remote="remote")], 1)
    assert fetch_eightfold("h.eightfold.ai", "h.com")[0].is_remote is True


@patch("requests.get")
def test_search_is_scoped_to_india_and_pages_by_ten(mock_get):
    mock_get.side_effect = [_page([_position(i) for i in range(PAGE_SIZE)], 12), _page([_position(10), _position(11)], 12)]
    jobs = fetch_eightfold("micron.eightfold.ai", "micron.com")
    assert len(jobs) == 12 and PAGE_SIZE == 10
    calls = [c for c in mock_get.call_args_list]
    assert [c.kwargs["params"]["start"] for c in calls] == [0, 10]
    assert all(c.args[0] == "https://micron.eightfold.ai/api/pcsx/search" for c in calls)
    assert all(c.kwargs["params"]["domain"] == "micron.com" and c.kwargs["params"]["location"] == "India" for c in calls)
    # relevance order shifts between requests, so pages overlap and positions are skipped (Qualcomm: 583 of 594 ids,
    # 2026-10-06); a time sort is stable (594 of 594)
    assert all(c.kwargs["params"]["sort_by"] == "timestamp" for c in calls)


@patch("requests.get")
def test_stops_when_a_page_repeats_earlier_jobs(mock_get):
    """Same guard as Workday (T47): a tenant that keeps returning page 1 must not loop to the cap."""
    page = [_position(i) for i in range(PAGE_SIZE)]
    mock_get.side_effect = [_page(page, 500), _page(page, 500), _page(page, 500)]
    assert len(fetch_eightfold("h.eightfold.ai", "h.com")) == PAGE_SIZE
    assert mock_get.call_count == 2


@patch("requests.get")
def test_keeps_earlier_pages_when_a_later_page_fails(mock_get):
    mock_get.side_effect = [_page([_position(i) for i in range(PAGE_SIZE)], 40), Exception("timeout")]
    assert len(fetch_eightfold("h.eightfold.ai", "h.com")) == PAGE_SIZE


@patch("requests.get")
def test_unauthorised_tenant_returns_nothing(mock_get):
    """A tenant that does not expose PCSX answers 403/404; that is an empty board, not a crash."""
    resp = MagicMock()
    resp.status_code = 403
    resp.raise_for_status.side_effect = Exception("403")
    resp.iter_content.return_value = iter([b""])
    mock_get.return_value = resp
    assert fetch_eightfold("h.eightfold.ai", "h.com") == []


@patch("requests.get")
def test_description_comes_from_position_details(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"status": 200, "data": {"jobDescription": "<p>Build <b>Node.js</b> services</p><ul><li>3+ years</li></ul>"}}
    resp.iter_content.return_value = iter([b""])
    mock_get.return_value = resp
    [job] = [fetch_eightfold_job()]
    text = fetch_description(job)
    assert "Node.js" in text and "3+ years" in text and "<p>" not in text
    call = mock_get.call_args
    assert call.args[0] == "https://micron.eightfold.ai/api/pcsx/position_details"
    assert call.kwargs["params"]["position_id"] == "41220001" and call.kwargs["params"]["domain"] == "micron.com"


def fetch_eightfold_job():
    from job_hunt.models import JobPosting
    return JobPosting(global_id="eightfold:micron.com:41220001", ats="eightfold", company="Micron", title="t",
                      location="Bengaluru, India", is_remote=False, url="https://micron.eightfold.ai/careers/job/41220001")


@patch("requests.get")
def test_description_is_empty_on_http_error(mock_get):
    resp = MagicMock()
    resp.status_code = 500
    resp.iter_content.return_value = iter([b""])
    mock_get.return_value = resp
    assert fetch_description(fetch_eightfold_job()) == ""


def test_enricher_is_registered_and_never_raises(monkeypatch):
    assert "eightfold" in ENRICHERS
    job = fetch_eightfold_job()
    monkeypatch.setitem(ENRICHERS, "eightfold", lambda j: (_ for _ in ()).throw(RuntimeError("boom")))
    assert enrich_job(job) is job and job.description_text == ""


@patch("requests.get")
def test_fetch_company_jobs_dispatches_on_host_and_domain(mock_get):
    mock_get.return_value = _page([_position(1)], 1)
    jobs = fetch_company_jobs({"name": "UKG", "ats": "eightfold", "host": "apply.ukg.com", "domain": "ukg.com"})
    assert [(j.company, j.url) for j in jobs] == [("UKG", "https://apply.ukg.com/careers/job/41220001")]


def test_fetch_company_jobs_needs_host_and_domain():
    assert fetch_company_jobs({"name": "UKG", "ats": "eightfold", "host": "apply.ukg.com"}) == []
    assert fetch_company_jobs({"name": "UKG", "ats": "eightfold", "domain": "ukg.com"}) == []


# -- rate limiting: Eightfold answers HTTP 429 to a few quick requests (Qualcomm: 429 on the 3rd page, 2026-10-06) --

def _status(code: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = code
    resp.raise_for_status.side_effect = Exception(f"HTTP {code}")
    resp.iter_content.return_value = iter([b""])
    return resp


@patch("requests.get")
def test_a_429_is_retried_after_a_pause_and_the_page_is_not_lost(mock_get, sleeps):
    from job_hunt.adapters.eightfold import RETRY_DELAYS
    mock_get.side_effect = [_status(429), _status(429), _page([_position(1)], 1)]
    jobs = fetch_eightfold("qualcomm.eightfold.ai", "qualcomm.com")
    assert [j.global_id for j in jobs] == ["eightfold:qualcomm.com:41220001"]
    assert sleeps == list(RETRY_DELAYS[:2])


@patch("requests.get")
def test_it_gives_up_after_the_retry_budget_and_keeps_earlier_pages(mock_get, sleeps):
    from job_hunt.adapters.eightfold import RETRY_DELAYS
    mock_get.side_effect = [_page([_position(i) for i in range(PAGE_SIZE)], 40)] + [_status(429)] * (len(RETRY_DELAYS) + 1)
    jobs = fetch_eightfold("qualcomm.eightfold.ai", "qualcomm.com")
    assert len(jobs) == PAGE_SIZE
    assert mock_get.call_count == 1 + len(RETRY_DELAYS) + 1
    assert sleeps.count(RETRY_DELAYS[0]) == 1 and sleeps[-1] == RETRY_DELAYS[-1]


@patch("requests.get")
def test_it_pauses_between_pages_but_not_after_the_last(mock_get, sleeps):
    from job_hunt.adapters.eightfold import PAGE_PAUSE
    mock_get.side_effect = [_page([_position(i) for i in range(PAGE_SIZE)], 12), _page([_position(10), _position(11)], 12)]
    fetch_eightfold("h.eightfold.ai", "h.com")
    assert sleeps == [PAGE_PAUSE]


@patch("requests.get")
def test_description_fetch_also_retries_a_429(mock_get, sleeps):
    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {"data": {"jobDescription": "<p>Node.js</p>"}}
    ok.iter_content.return_value = iter([b""])
    mock_get.side_effect = [_status(429), ok]
    assert "Node.js" in fetch_description(fetch_eightfold_job())
    assert len(sleeps) == 1
