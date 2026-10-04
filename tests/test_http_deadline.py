"""Total-download deadline for ATS HTTP calls and the Workday per-board budget."""
from __future__ import annotations

import io
import itertools
from unittest.mock import MagicMock, patch

import pytest
import requests

from job_hunt.adapters import base


def _real_response(body: bytes, status: int = 200) -> requests.Response:
    r = requests.models.Response()
    r.status_code = status
    r.raw = io.BytesIO(body)
    return r


@patch("requests.get")
def test_http_get_returns_fully_read_response(mock_get):
    mock_get.return_value = _real_response(b'{"jobs": [1, 2]}')
    resp = base.http_get("https://x", timeout=5)
    assert resp.json() == {"jobs": [1, 2]}
    assert mock_get.call_args.kwargs["stream"] is True


@patch("requests.get")
def test_http_get_aborts_slow_drip_download(mock_get, monkeypatch):
    """A response that keeps trickling bytes never trips requests' per-read timeout;
    the total deadline must."""
    slow = MagicMock()
    slow.iter_content.return_value = iter([b"x"] * 1000)
    mock_get.return_value = slow
    clock = itertools.count(0, 10)  # each check advances 10 s
    monkeypatch.setattr(base.time, "monotonic", lambda: next(clock))
    with pytest.raises(base.DeadlineExceeded):
        base.http_get("https://slow", deadline=60)
    slow.close.assert_called_once()


@patch("requests.get")
def test_adapter_returns_empty_when_deadline_hit(mock_get, monkeypatch):
    from job_hunt.adapters.lever import fetch_lever
    slow = MagicMock()
    slow.iter_content.return_value = iter([b"x"] * 1000)
    mock_get.return_value = slow
    clock = itertools.count(0, 100)
    monkeypatch.setattr(base.time, "monotonic", lambda: next(clock))
    assert fetch_lever("extremenetworks") == []


@patch("requests.get")
@patch("requests.post")
def test_workday_budget_stops_detail_calls(mock_post, mock_get, monkeypatch):
    """Over budget, remaining 'N Locations' items keep their list text instead of
    triggering more detail calls, so one tenant cannot stall a scan."""
    from job_hunt.adapters import workday
    page = MagicMock()
    page.status_code = 200
    page.json.return_value = {"jobPostings": [
        {"title": f"SE {i}", "locationsText": "3 Locations", "externalPath": f"/job/x/SE_{i}"} for i in range(3)]}
    mock_post.return_value = page
    detail = MagicMock()
    detail.status_code = 200
    detail.json.return_value = {"jobPostingInfo": {"location": "India, Pune"}}
    mock_get.return_value = detail
    clock = itertools.count(0, 100)  # 0, 100, 200, ... seconds
    monkeypatch.setattr(workday.time, "monotonic", lambda: next(clock))

    jobs = workday.fetch_workday("nvidia", "wd5", "site", budget=250)

    assert len(jobs) == 3
    assert mock_get.call_count < 3
    assert jobs[-1].location == "3 Locations"
