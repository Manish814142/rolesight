"""T114: an HTTP 429 is asked again after a pause, not read as an empty board.

Measured 2026-10-16: Workable (Cloudflare) refuses about half the requests of a sustained burst (about 800 requests at 20 a second),
answers with an HTML body and `Retry-After: 0`, and takes about ten seconds to recover. The adapters returned an empty list on a 429
without a warning, and `discover` counted such boards as dead (13 of 100 sampled Workable "no live board" verdicts were alive).
No network: `requests` and the pause are stubbed.
"""
import logging
from unittest.mock import MagicMock, patch

import pytest

from job_hunt.adapters import base
from job_hunt.adapters.base import begin_fetch, fetch_incomplete, http_get
from job_hunt.adapters.workable import fetch_workable
from job_hunt.harvester import _probe


def _resp(status=200, payload=None, retry_after=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.headers = {"Retry-After": retry_after} if retry_after is not None else {}
    r.iter_content.return_value = [b"{}"]
    return r


@pytest.fixture
def pauses(monkeypatch):
    """The pauses asked for, recorded and not slept."""
    asked = []
    monkeypatch.setattr(base.time, "sleep", lambda s: asked.append(s))
    return asked


@patch("requests.get")
def test_a_429_is_asked_again_after_a_pause_and_the_answer_is_returned(mock_get, pauses):
    mock_get.side_effect = [_resp(429), _resp(429), _resp(200)]
    assert http_get("https://example.com/x").status_code == 200
    assert mock_get.call_count == 3 and pauses == [2.0, 5.0]


@patch("requests.get")
def test_the_last_429_is_returned_after_three_pauses(mock_get, pauses):
    mock_get.side_effect = [_resp(429)] * 10
    assert http_get("https://example.com/x").status_code == 429
    assert mock_get.call_count == 4 and pauses == [2.0, 5.0, 12.0]


@pytest.mark.parametrize("header, expected_first_pause", [
    ("0", 2.0),                                    # Workable's: asking again at once would be refused again
    ("20", 20.0), ("999", 30.0), (None, 2.0),     # a longer ask is honoured, up to a cap of 30 s
    ("Wed, 21 Oct 2026 07:28:00 GMT", 2.0), ("soon", 2.0),   # not a number of seconds: the scheduled pause
])
@patch("requests.get")
def test_the_servers_retry_after_is_a_floor_for_the_pause_never_the_pause_itself(mock_get, pauses, header, expected_first_pause):
    mock_get.side_effect = [_resp(429, retry_after=header), _resp(200)]
    http_get("https://example.com/x")
    assert pauses == [expected_first_pause]


@pytest.mark.parametrize("status", [200, 403, 404, 500, 503])
@patch("requests.get")
def test_other_answers_are_not_asked_again(mock_get, pauses, status):
    mock_get.return_value = _resp(status)
    assert http_get("https://example.com/x").status_code == status
    assert mock_get.call_count == 1 and pauses == []


@patch("requests.get")
def test_a_caller_with_its_own_429_handling_can_opt_out(mock_get, pauses):
    mock_get.side_effect = [_resp(429), _resp(200)]
    assert http_get("https://example.com/x", retry_429=False).status_code == 429
    assert mock_get.call_count == 1 and pauses == []


@patch("requests.post")
def test_post_is_asked_again_too(mock_post, pauses):
    mock_post.side_effect = [_resp(429), _resp(200)]
    assert base.http_post("https://example.com/x", json={}).status_code == 200
    assert mock_post.call_count == 2


@patch("requests.get")
def test_workable_gets_its_board_after_a_429(mock_get, pauses):
    mock_get.side_effect = [_resp(429), _resp(200, {"name": "Acme", "jobs": [{"title": "Backend Engineer", "shortcode": "A1", "city": "Pune",
                                                                             "country": "India"}]})]
    begin_fetch()
    jobs = fetch_workable("acme")
    assert [j.title for j in jobs] == ["Backend Engineer"] and fetch_incomplete() is None


@patch("requests.get")
def test_workable_still_rate_limited_after_the_retries_warns_by_name_and_marks_the_fetch_incomplete(mock_get, pauses, caplog):
    mock_get.side_effect = [_resp(429)] * 10
    begin_fetch()
    with caplog.at_level(logging.WARNING):
        assert fetch_workable("acme") == []
    assert any("acme" in r.getMessage() and "429" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)
    assert fetch_incomplete() and "429" in fetch_incomplete()


@patch("requests.get")
def test_workable_404_stays_quiet_and_complete(mock_get, pauses, caplog):
    mock_get.return_value = _resp(404)
    begin_fetch()
    with caplog.at_level(logging.WARNING):
        assert fetch_workable("gone") == []
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING] and fetch_incomplete() is None


@patch("requests.get")
def test_the_discovery_probe_asks_a_429_again_before_calling_the_board_dead(mock_get, pauses):
    ok_body = {"jobs": [{"title": "x"}]}
    mock_get.side_effect = [_resp(429), _resp(200, ok_body)]
    assert _probe("GET", "https://apply.workable.com/api/v1/widget/accounts/acme?details=true", None, ats="workable")[0] is True
    assert pauses == [2.0]


@patch("requests.get")
def test_the_discovery_probe_reports_a_429_that_persists(mock_get, pauses):
    mock_get.side_effect = [_resp(429)] * 10
    ok, status = _probe("GET", "https://apply.workable.com/api/v1/widget/accounts/acme?details=true", None, ats="workable")
    assert ok is False and status == 429
