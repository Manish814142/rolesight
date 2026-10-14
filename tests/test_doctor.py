"""Unit tests for autopilot doctor diagnostics."""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import requests

from job_hunt import doctor
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


# -- T92: the model doctor pings is the one a scan would use first, and the API key never travels in a URL ------------

KEY = "AIza" + "-test-key-0123456789abcdef"   # built at run time, so the secret scan does not read a key


def _client_that_records(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(doctor, "_get_gemini_client", lambda key: client)
    return client


def test_doctor_pings_the_model_in_config_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    (tmp_path / "config.json").write_text(json.dumps({"gemini_model": "gemini-config-model"}))
    client = _client_that_records(monkeypatch)
    ok, msg = check_gemini_quota(api_key=KEY)
    assert ok and "gemini-config-model" in msg
    assert client.models.generate_content.call_args.kwargs["model"] == "gemini-config-model"


def test_gemini_model_in_the_environment_beats_config_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"gemini_model": "gemini-config-model"}))
    monkeypatch.setenv("GEMINI_MODEL", "gemini-env-model")
    client = _client_that_records(monkeypatch)
    ok, msg = check_gemini_quota(api_key=KEY)
    assert client.models.generate_content.call_args.kwargs["model"] == "gemini-env-model" and "gemini-env-model" in msg


def test_doctor_runs_without_a_config_json_and_pings_the_default_model(monkeypatch, tmp_path):
    """doctor is the command people run before they have a config; it must not exit like load_config does."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    client = _client_that_records(monkeypatch)
    ok, msg = check_gemini_quota(api_key=KEY)
    assert ok and client.models.generate_content.call_args.kwargs["model"] == "gemini-3.5-flash-lite"


def test_a_placeholder_model_in_the_environment_is_ignored(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"gemini_model": "gemini-config-model"}))
    monkeypatch.setenv("GEMINI_MODEL", "YOUR_MODEL_here")
    client = _client_that_records(monkeypatch)
    check_gemini_quota(api_key=KEY)
    assert client.models.generate_content.call_args.kwargs["model"] == "gemini-config-model"


def _no_sdk(monkeypatch):
    def boom(key):
        raise ImportError("google-genai is not installed")
    monkeypatch.setattr(doctor, "_get_gemini_client", boom)


def test_the_rest_fallback_sends_the_key_in_a_header_not_in_the_url(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    (tmp_path / "config.json").write_text(json.dumps({"gemini_model": "gemini-config-model"}))
    _no_sdk(monkeypatch)
    seen = {}

    def fake_post(url, **kwargs):
        seen["url"], seen["headers"] = url, kwargs.get("headers") or {}
        resp = MagicMock()
        resp.status_code = 200
        return resp
    monkeypatch.setattr(doctor.requests, "post", fake_post)
    ok, msg = check_gemini_quota(api_key=KEY)
    assert ok
    assert KEY not in seen["url"] and "key=" not in seen["url"]
    assert seen["headers"].get("x-goog-api-key") == KEY
    assert "gemini-config-model:generateContent" in seen["url"], "the REST probe asks for the configured model too"


def test_a_failing_fallback_request_shows_no_part_of_the_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _no_sdk(monkeypatch)

    def failing_post(url, **kwargs):
        # what requests puts into its message when the URL carried the key, and when a proxy echoes the header back
        raise requests.ConnectionError(f"HTTPSConnectionPool: Max retries exceeded with url: /v1beta/models/m:generateContent?key={KEY}")
    monkeypatch.setattr(doctor.requests, "post", failing_post)
    ok, msg = check_gemini_quota(api_key=KEY)
    assert not ok and KEY not in msg and KEY[:12] not in msg


def test_an_sdk_error_that_echoes_the_key_is_masked_too(monkeypatch):
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError(f"400 INVALID_ARGUMENT for key {KEY}")
    monkeypatch.setattr(doctor, "_get_gemini_client", lambda key: client)
    ok, msg = check_gemini_quota(api_key=KEY)
    assert not ok and KEY not in msg


def test_no_source_file_builds_a_url_with_the_key_in_the_query():
    root = Path(__file__).resolve().parent.parent / "job_hunt"
    offenders = [str(f.relative_to(root)) for f in root.rglob("*.py") if "?key=" in f.read_text()]
    assert not offenders, offenders


def test_a_failure_names_the_model_that_failed(monkeypatch, tmp_path):
    """A 503 or a 429 on the configured model is only useful if the message says which model it was."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    (tmp_path / "config.json").write_text(json.dumps({"gemini_model": "gemini-config-model"}))
    client = MagicMock()
    monkeypatch.setattr(doctor, "_get_gemini_client", lambda key: client)
    client.models.generate_content.side_effect = RuntimeError("503 UNAVAILABLE. high demand")
    ok, msg = check_gemini_quota(api_key=KEY)
    assert not ok and "gemini-config-model" in msg
    client.models.generate_content.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED quota")
    ok, msg = check_gemini_quota(api_key=KEY)
    assert not ok and "gemini-config-model" in msg and "429" in msg
