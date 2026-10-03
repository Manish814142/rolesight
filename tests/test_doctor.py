"""Unit tests for autopilot doctor diagnostics."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from job_hunt.doctor import (
    check_ats_egress,
    check_gemini_quota,
    check_sqlite_write,
    check_telegram_credentials,
    run_doctor,
)


def test_check_sqlite_write_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_jobs.db")
        passed, msg = check_sqlite_write(db_path)
        assert passed is True
        assert "verified" in msg.lower()


def test_check_sqlite_write_failure(monkeypatch):
    # Pass an invalid path that cannot be written
    invalid_path = "/nonexistent_root_dir_abc123/cannot_write.db"
    passed, msg = check_sqlite_write(invalid_path)
    assert passed is False
    assert "failed" in msg.lower()


def test_check_gemini_quota_missing_key():
    passed, msg = check_gemini_quota(api_key=None)
    assert passed is False
    assert "not configured" in msg.lower()


def test_check_gemini_quota_success(monkeypatch):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "pong"
    mock_client.models.generate_content.return_value = mock_resp

    monkeypatch.setattr("job_hunt.doctor._get_gemini_client", lambda key: mock_client)

    passed, msg = check_gemini_quota(api_key="valid_key")
    assert passed is True
    assert "active" in msg.lower()


def test_check_telegram_credentials_missing():
    passed, msg = check_telegram_credentials(bot_token=None, chat_id=None)
    assert passed is False
    assert "not configured" in msg.lower()


def test_check_telegram_credentials_valid(monkeypatch):
    class FakeResp:
        status_code = 200
        def json(self):
            return {"ok": True, "result": {"username": "job_alert_bot"}}

    monkeypatch.setattr("job_hunt.doctor.requests.get", lambda url, timeout: FakeResp())
    passed, msg = check_telegram_credentials(bot_token="123456:ABC-DEF", chat_id="12345")
    assert passed is True
    assert "@job_alert_bot" in msg


def test_check_ats_egress(monkeypatch):
    class FakeResp:
        status_code = 200

    monkeypatch.setattr("job_hunt.doctor.requests.get", lambda url, headers, timeout: FakeResp())
    monkeypatch.setattr("job_hunt.doctor.requests.post", lambda url, json, headers, timeout: FakeResp())

    results = check_ats_egress()
    assert len(results) == 4
    for ats, (passed, msg) in results.items():
        assert passed is True
        assert "200" in msg


def test_run_doctor_flow(monkeypatch, capsys):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        monkeypatch.setattr("job_hunt.doctor.check_sqlite_write", lambda p="data/jobs.db": (True, "OK"))
        monkeypatch.setattr("job_hunt.doctor.check_gemini_quota", lambda k=None: (True, "OK"))
        monkeypatch.setattr("job_hunt.doctor.check_telegram_credentials", lambda t=None, c=None: (False, "Not configured"))
        monkeypatch.setattr("job_hunt.doctor.check_ats_egress", lambda: {
            "Greenhouse": (True, "HTTP 200"),
            "Lever": (True, "HTTP 200"),
            "Ashby": (True, "HTTP 200"),
            "Workday": (True, "HTTP 200"),
        })

        success = run_doctor(db_path=db_path)
        assert success is True
        out = capsys.readouterr().out
        assert "[PASS] SQLite Database" in out
        assert "[PASS] Gemini Quota" in out
        assert "[WARN] Telegram Bot" in out
        assert "[PASS] Network Egress (Greenhouse)" in out
