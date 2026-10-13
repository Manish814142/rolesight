"""T76: during Workday's maintenance every tenant answers the jobs POST with a 303 to community.workday.com/maintenance-page.

`requests` follows it, the HTML is not JSON, and each of 77 tenants logged "Expecting value: line 1 column 1" (measured
2026-10-10). The scan is not harmed (the board is incomplete, so T33 counts no miss), but nobody could tell why 77
boards came back empty. Now one clear line per scan says so.
"""
import logging
from types import SimpleNamespace

import pytest

from job_hunt.adapters import base, workday
from job_hunt.adapters.workday import fetch_workday

MAINTENANCE_URL = "https://community.workday.com/maintenance-page"


def _maintenance_response(tenant="acme"):
    """What `requests` hands back after following the 303: the final page, with the redirect in `history`."""
    def not_json():
        raise ValueError("Expecting value: line 1 column 1 (char 0)")
    return SimpleNamespace(status_code=200, url=MAINTENANCE_URL, history=[SimpleNamespace(status_code=303)],
                           json=not_json, raise_for_status=lambda: None)


def _jobs_response(tenant="acme"):
    payload = {"total": 1, "jobPostings": [{"title": "Backend Engineer", "locationsText": "Pune, India",
                                            "externalPath": "/job/Pune/Backend-Engineer_R1", "bulletFields": ["R1"],
                                            "postedOn": "Posted Today"}]}
    return SimpleNamespace(status_code=200, url=f"https://{tenant}.wd1.myworkdayjobs.com/wday/cxs/{tenant}/site/jobs",
                           history=[], json=lambda: payload, raise_for_status=lambda: None)


@pytest.fixture(autouse=True)
def _fresh_state():
    workday._maintenance_reported = False
    base.begin_fetch()
    yield
    workday._maintenance_reported = False


def test_a_redirect_to_the_maintenance_page_is_an_incomplete_empty_board_with_a_clear_reason(monkeypatch):
    monkeypatch.setattr(workday, "http_post", lambda *a, **k: _maintenance_response())
    assert fetch_workday("acme", "wd1", "site") == []
    assert "maintenance" in (base.fetch_incomplete() or "")


def test_the_scan_gets_one_clear_warning_not_one_cryptic_one_per_tenant(monkeypatch, caplog):
    monkeypatch.setattr(workday, "http_post", lambda *a, **k: _maintenance_response())
    caplog.set_level(logging.DEBUG, logger="job_hunt.adapters.workday")
    for tenant in ("a", "b", "c"):
        base.begin_fetch()
        fetch_workday(tenant, "wd1", "site")
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "maintenance" in warnings[0].lower() and MAINTENANCE_URL in warnings[0]
    assert not any("Expecting value" in r.getMessage() for r in caplog.records)


def test_a_normal_answer_is_unchanged(monkeypatch):
    monkeypatch.setattr(workday, "http_post", lambda *a, **k: _jobs_response())
    jobs = fetch_workday("acme", "wd1", "site")
    assert [j.title for j in jobs] == ["Backend Engineer"] and base.fetch_incomplete() is None


def test_a_redirect_that_stays_on_the_tenant_host_is_not_maintenance(monkeypatch):
    resp = _jobs_response()
    resp.history = [SimpleNamespace(status_code=301)]
    monkeypatch.setattr(workday, "http_post", lambda *a, **k: resp)
    assert len(fetch_workday("acme", "wd1", "site")) == 1 and base.fetch_incomplete() is None


# -- Review of T76 (2026-10-11): two gaps -----------------------------------------------------------------------------

def test_a_redirect_to_another_host_that_answers_with_jobs_still_counts(monkeypatch):
    """Before T76 a cross-host redirect that ended in JSON (say a tenant moved to another data centre) was followed and
    its jobs read. Only a non-JSON answer (the maintenance page) is a dead end."""
    resp = _jobs_response()
    resp.url = "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/site/jobs"
    resp.history = [SimpleNamespace(status_code=308)]
    resp.headers = {"Content-Type": "application/json;charset=UTF-8"}
    monkeypatch.setattr(workday, "http_post", lambda *a, **k: resp)
    assert len(fetch_workday("acme", "wd1", "site")) == 1 and base.fetch_incomplete() is None


def test_every_scan_gets_its_own_warning(monkeypatch, caplog):
    """The warn-once flag is per scan, not per process: the MCP server runs many scans in one process."""
    from job_hunt import scanner
    monkeypatch.setattr(workday, "http_post", lambda *a, **k: _maintenance_response())
    caplog.set_level(logging.WARNING, logger="job_hunt.adapters.workday")
    board = [{"name": "Acme", "ats": "workday", "tenant": "acme", "dc": "wd1", "site": "site"}]
    for _ in range(2):
        scanner._prefetch_jobs(board, 1)
    assert sum("maintenance" in r.getMessage().lower() for r in caplog.records if r.levelno == logging.WARNING) == 2
