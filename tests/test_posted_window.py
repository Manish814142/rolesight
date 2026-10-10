"""T02: the posted-date window is on by default (7 days) and reaches the adapters, so a job older than the window costs
no API call that a newest-first list or a per-job detail request would otherwise spend on it. No network."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from job_hunt import main, scanner
from job_hunt.adapters import base
from job_hunt.settings import DEFAULT_MAX_POSTED_AGE_DAYS, max_posted_age_of


def _ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _resp(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    r.iter_content.return_value = iter([b""])
    return r


# -- the setting ----------------------------------------------------------------------------------------------

def test_default_window_is_seven_days_and_can_be_changed_or_switched_off():
    assert DEFAULT_MAX_POSTED_AGE_DAYS == 7
    assert max_posted_age_of({}) == 7
    assert max_posted_age_of({"candidate": {}}) == 7
    assert max_posted_age_of({"candidate": {"max_posted_age_days": 3}}) == 3
    assert max_posted_age_of({"candidate": {"max_posted_age_days": None}}) is None      # JSON null = no window


def test_a_scan_with_no_setting_logs_the_default_window(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [])
    (tmp_path / "resume.md").write_text("Node.js")
    caplog.set_level(logging.INFO, logger="autopilot")
    scanner.run_scan({"candidate": {"resume_path": "resume.md"}, "gemini_api_key": "k", "telegram": {}},
                     [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    line = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("Posted-date filter"))
    assert "last 7 day(s)" in line and "without a posted date are kept" in line


def test_a_null_window_logs_no_filter(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [])
    (tmp_path / "resume.md").write_text("Node.js")
    caplog.set_level(logging.INFO, logger="autopilot")
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "max_posted_age_days": None},
                      "gemini_api_key": "k", "telegram": {}}, [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    assert not any(r.getMessage().startswith("Posted-date filter") for r in caplog.records)


@pytest.mark.parametrize("argv, expected", [(["--posted-within", "3"], 3), (["--posted-within", "all"], None),
                                            ([], 7)])
def test_the_command_line_overrides_the_window(monkeypatch, tmp_path, argv, expected):
    """`--posted-within all` switches the window off for one run; no flag keeps the configured/default window."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text('{"gemini_api_key": "k", "candidate": {}}')
    (tmp_path / "companies.json").write_text("[]")
    seen = {}
    monkeypatch.setattr(scanner, "run_scan", lambda config, comps: seen.update(config))
    monkeypatch.setattr("sys.argv", ["autopilot", "scan", *argv])
    main.main()
    assert max_posted_age_of(seen) == expected


# -- the adapters' share of the window ------------------------------------------------------------------------

def test_the_window_is_per_fetch_and_resets():
    base.begin_fetch(3)
    assert base.fetch_window() == 3
    base.begin_fetch()
    assert base.fetch_window() is None


def test_a_page_past_the_window_stops_a_newest_first_fetch_and_marks_it_incomplete():
    base.begin_fetch(7)
    assert base.stop_at_window([_ago(8), _ago(20)]) is True
    assert base.fetch_incomplete() == "posted-date window"
    base.begin_fetch(7)
    assert base.stop_at_window([_ago(8), _ago(2)]) is False     # one job still inside: keep paging
    assert base.stop_at_window([_ago(8), ""]) is False          # an undated job is never treated as old
    assert base.stop_at_window([]) is False
    assert base.fetch_incomplete() is None
    base.begin_fetch(None)
    assert base.stop_at_window([_ago(400)]) is False            # no window, no stop


def _amazon_page(n, posted_days_ago, first_id):
    stamp = (date.today() - timedelta(days=posted_days_ago)).strftime("%B %d, %Y")
    return _resp({"hits": 300, "jobs": [{"title": f"SDE {first_id + i}", "normalized_location": "Pune, IND",
                                         "posted_date": stamp, "job_path": f"/en/jobs/{first_id + i}", "id_icims": str(first_id + i),
                                         "description": "<p>Node</p>"} for i in range(n)]})


@patch("requests.get")
def test_amazon_reads_every_page_even_with_a_window(mock_get):
    """Amazon's `sort=recent` is only roughly by date (2026-10-10: 980 places where a later job was newer than the
    previous one, by up to 192 days; 3 jobs of a 14-day window sat after the first all-older page), so it is never cut."""
    from job_hunt.adapters.amazon import fetch_amazon
    mock_get.side_effect = [_amazon_page(100, 1, 0), _amazon_page(100, 12, 100), _amazon_page(100, 30, 200)]
    base.begin_fetch(7)
    assert len(fetch_amazon()) == 300 and mock_get.call_count == 3
    assert base.fetch_incomplete() is None


def _oracle(url, params=None, **kw):
    finder = params["finder"]
    if "facetsList=LOCATIONS" in finder:
        return _resp({"items": [{"locationsFacet": [{"Id": 777, "Name": "India"}]}]})
    off = int(finder.split("offset=")[1].split(",")[0])
    age = 1 if off == 0 else 15
    return _resp({"items": [{"TotalJobsCount": 300, "requisitionList": [
        {"Id": str(off + i), "Title": "Software Engineer", "PostedDate": _ago(age),
         "PrimaryLocation": "Pune, India"} for i in range(100)]}]})


@patch("requests.get")
def test_oracle_hcm_stops_paging_once_a_whole_page_is_older_than_the_window(mock_get):
    from job_hunt.adapters.oracle_hcm import fetch_oracle_hcm
    mock_get.side_effect = _oracle
    base.begin_fetch(7)
    jobs = fetch_oracle_hcm("h.oraclecloud.com", "CX_1")
    # facet lookup + page 0 + page 1 (all old); page 2 not requested
    assert mock_get.call_count == 3 and len(jobs) == 200
    assert base.fetch_incomplete() == "posted-date window"


@patch("job_hunt.adapters.eightfold.time.sleep", lambda s: None)
@patch("requests.get")
def test_eightfold_stops_paging_once_a_whole_page_is_older_than_the_window(mock_get):
    from job_hunt.adapters.eightfold import fetch_eightfold

    def page(url, params=None, **kw):
        start = params["start"]
        day = date.today() - timedelta(days=1 if start == 0 else 20)
        ts = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
        return _resp({"data": {"count": 100, "positions": [
            {"id": start + i, "name": "Software Engineer", "locations": ["Pune, India"], "postedTs": ts,
             "positionUrl": f"/careers/job/{start + i}"} for i in range(10)]}})
    mock_get.side_effect = page
    base.begin_fetch(7)
    jobs = fetch_eightfold("h.eightfold.ai", "h.com")
    assert [c.kwargs["params"]["start"] for c in mock_get.call_args_list] == [0, 10]
    assert len(jobs) == 20
    assert base.fetch_incomplete() == "posted-date window"


@patch("requests.get")
def test_smartrecruiters_stops_paging_once_a_whole_page_is_older_than_the_window(mock_get):
    from job_hunt.adapters.smartrecruiters import fetch_smartrecruiters

    def page(url, params=None, **kw):
        off = params["offset"]
        released = _ago(1 if off == 0 else 25) + "T00:00:00.000Z"
        return _resp({"totalFound": 300, "content": [
            {"id": f"j{off + i}", "name": "Backend Engineer", "location": {"city": "Pune", "country": "in"},
             "releasedDate": released} for i in range(100)]})
    mock_get.side_effect = page
    base.begin_fetch(7)
    assert len(fetch_smartrecruiters("acme")) == 200 and mock_get.call_count == 2
    assert base.fetch_incomplete() == "posted-date window"


def _wd_page(posted):
    return _resp({"total": 1, "jobPostings": [
        {"title": "Backend Engineer", "locationsText": "5 Locations", "externalPath": "/job/X/J_0",
         "bulletFields": ["R0"], "postedOn": posted}]})


@pytest.mark.parametrize("posted, window, detail_calls", [
    ("Posted 30+ Days Ago", 7, 0),      # outside the window: the per-job request is not made
    ("Posted 3 Days Ago", 7, 1),
    ("Posted Today", 7, 1),
    ("Posted 30+ Days Ago", None, 1),   # no window: as before
    ("", 7, 1),                         # undated is never treated as old
])
@patch("requests.get")
@patch("requests.post")
def test_workday_makes_no_detail_call_for_a_job_outside_the_window(mock_post, mock_get, posted, window, detail_calls):
    from job_hunt.adapters.workday import fetch_workday
    mock_post.return_value = _wd_page(posted)
    mock_get.return_value = _resp({"jobPostingInfo": {"location": "Pune, India", "additionalLocations": [],
                                                      "jobDescription": "<p>Node.js</p>"}})
    base.begin_fetch(window)
    [job] = fetch_workday("t", "wd1", "site")
    assert mock_get.call_count == detail_calls
    assert job.posted_at == posted
    assert base.fetch_incomplete() is None     # Workday's order is not by date: it is never cut short


# -- the scanner hands the window to the fetch ------------------------------------------------------------------

def test_prefetch_gives_each_fetch_the_window(monkeypatch):
    seen = []
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: seen.append(base.fetch_window()) or [])
    scanner._prefetch_jobs([{"name": "A"}, {"name": "B"}], 2, max_age_days=5)
    assert seen == [5, 5]
    seen.clear()
    scanner._prefetch_jobs([{"name": "A"}], 1)
    assert seen == [None]


def test_a_board_cut_at_the_window_closes_no_job(monkeypatch, tmp_path, caplog):
    """T33: jobs the cut-off page never returned are old, not gone -- the board is partial for closing purposes."""
    from job_hunt.db import init_db, save_job
    from job_hunt.models import JobPosting
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js")
    init_db(str(tmp_path / "data" / "jobs.db"))
    old = JobPosting(global_id="amazon:old", ats="amazon", company="Amazon", title="SDE II", location="Pune, India",
                     is_remote=False, url="https://a/old", posted_at=_ago(40))
    save_job(old, status="skipped")

    def fake_fetch(company):
        base.mark_incomplete("posted-date window")
        return [JobPosting(global_id="amazon:new", ats="amazon", company="Amazon", title="SDE II", location="Pune, India",
                           is_remote=False, url="https://a/new", posted_at=_ago(1), description_text="Node.js")]
    monkeypatch.setattr(scanner, "fetch_company_jobs", fake_fetch)
    monkeypatch.setattr(scanner, "score_and_process_job", lambda job, **kw: {"score": 80, "reason": "r", "status": "scored"})
    cfg = {"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k", "telegram": {},
           "closed_after_missed_scans": 1}
    scanner.run_scan(cfg, [{"name": "Amazon", "ats": "amazon"}])
    from job_hunt.db import get_job
    assert get_job("amazon:old")["closed_at"] is None
