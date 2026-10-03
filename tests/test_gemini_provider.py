"""Tests for Google Gemini LLM provider integration."""
import json
import types
from unittest.mock import MagicMock

import pytest

from job_hunt import llm_utils, main, scanner


@pytest.fixture
def clean_gemini_env(monkeypatch):
    for k in (
        "TINYFISH_API_KEY",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "LLM_PROVIDER",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
    ):
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


# --- 1. Config tests for GEMINI_API_KEY and GEMINI_MODEL ----------------------

def test_load_config_gemini_env_and_config_module(tmp_path, monkeypatch, clean_gemini_env):
    """Test job_hunt.config imports load_config and accepts GEMINI_API_KEY and GEMINI_MODEL."""
    from job_hunt import config as job_hunt_config

    monkeypatch.chdir(tmp_path)
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "tinyfish_api_key": "sk-real-tinyfish",
        "llm_provider": "gemini",
    }))

    monkeypatch.setenv("GEMINI_API_KEY", "real-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")

    cfg = job_hunt_config.load_config()
    assert cfg["gemini_api_key"] == "real-gemini-key"
    assert cfg["gemini_model"] == "gemini-2.5-pro"
    assert cfg["llm_provider"] == "gemini"


def test_load_config_gemini_placeholder_ignored(tmp_path, monkeypatch, clean_gemini_env):
    """Placeholder GEMINI_API_KEY from .env must not clobber real config."""
    monkeypatch.chdir(tmp_path)
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "tinyfish_api_key": "sk-real-tinyfish",
        "gemini_api_key": "real-key-in-config",
    }))

    monkeypatch.setenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

    cfg = main.load_config()
    assert cfg["gemini_api_key"] == "real-key-in-config"


def test_load_config_gemini_default_model(tmp_path, monkeypatch, clean_gemini_env):
    """When GEMINI_MODEL is not set, default model should be gemini-3.5-flash-lite."""
    monkeypatch.chdir(tmp_path)
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "tinyfish_api_key": "sk-real-tinyfish",
        "gemini_api_key": "real-key",
    }))

    cfg = main.load_config()
    assert cfg.get("gemini_model") == "gemini-3.5-flash-lite"


# --- 2. Gemini provider dispatch in llm_utils ---------------------------------

def test_chat_with_llm_routes_gemini(monkeypatch):
    """chat_with_llm routes to _chat_with_gemini when llm_provider is gemini."""
    monkeypatch.setattr(llm_utils, "_chat_with_gemini", lambda *a, **k: "GEMINI_OK")
    out = llm_utils.chat_with_llm({"llm_provider": "gemini"}, [{"role": "user", "content": "hi"}])
    assert out == "GEMINI_OK"


def test_chat_with_gemini_invokes_google_genai(monkeypatch):
    """_chat_with_gemini instantiates google.genai.Client and calls models.generate_content."""
    mock_client_cls = MagicMock()
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_resp = MagicMock()
    mock_resp.text = '{"score": 85, "reason": "Good match"}'
    mock_client.models.generate_content.return_value = mock_resp

    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = mock_client_cls
    fake_types = types.ModuleType("google.genai.types")
    fake_types.GenerateContentConfig = MagicMock()

    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types", lambda api_key: (mock_client, fake_types))

    config = {
        "gemini_api_key": "sk-gemini-test",
        "gemini_model": "gemini-2.5-flash",
    }
    messages = [
        {"role": "system", "content": "You are a job scorer."},
        {"role": "user", "content": "Score this role."},
    ]

    out = llm_utils._chat_with_gemini(config, messages, temperature=0.1, max_tokens=1024)
    assert out == '{"score": 85, "reason": "Good match"}'


# --- 3. Gemini scoring with JSON formatting and error fallback ----------------

def test_score_job_gemini_success(monkeypatch):
    """Scoring a job with Gemini formats prompt, requests JSON, and returns score and reason."""
    mock_client = MagicMock()
    mock_types = types.SimpleNamespace(GenerateContentConfig=MagicMock())
    mock_resp = MagicMock()
    mock_resp.text = '{"score": 92, "reason": "Direct experience with LLM orchestration and Python."}'
    mock_client.models.generate_content.return_value = mock_resp

    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types", lambda api_key: (mock_client, mock_types))

    config = {
        "llm_provider": "gemini",
        "gemini_api_key": "fake-gemini-key",
        "gemini_model": "gemini-2.5-flash",
    }
    job = {
        "company": "Google",
        "title": "Staff AI Engineer",
        "location": "Remote",
        "content": "Building next-gen AI agents.",
    }
    resume = "Experienced AI Engineer with Python and LLMs."

    res = llm_utils.score_job_with_gemini(job, resume, config)
    assert res == {
        "score": 92,
        "reason": "Direct experience with LLM orchestration and Python.",
    }


def test_score_job_gemini_error_fallback(monkeypatch):
    """When Gemini scoring raises an exception, return fallback {"score": 0, "reason": "Scoring failed"}."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Quota exceeded or connection error")

    mock_types = types.SimpleNamespace(GenerateContentConfig=MagicMock())
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types", lambda api_key: (mock_client, mock_types))

    config = {
        "llm_provider": "gemini",
        "gemini_api_key": "fake-gemini-key",
    }
    job = {"company": "TestCo", "title": "Dev", "location": "Remote"}

    res = llm_utils.score_job_with_gemini(job, "My resume", config)
    assert res == {"score": 0, "reason": "Scoring failed"}


def test_score_job_gemini_malformed_json_fallback(monkeypatch):
    """When Gemini returns non-JSON or invalid JSON, return fallback {"score": 0, "reason": "Scoring failed"}."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "This is not JSON at all."
    mock_client.models.generate_content.return_value = mock_resp

    mock_types = types.SimpleNamespace(GenerateContentConfig=MagicMock())
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types", lambda api_key: (mock_client, mock_types))

    config = {
        "llm_provider": "gemini",
        "gemini_api_key": "fake-gemini-key",
    }
    job = {"company": "TestCo", "title": "Dev", "location": "Remote"}

    res = llm_utils.score_job_with_gemini(job, "My resume", config)
    assert res == {"score": 0, "reason": "Scoring failed"}


# --- 4. Scanner integration without invoking Claude CLI or OpenRouter ----------

def test_scanner_scoring_with_gemini_does_not_invoke_openrouter_or_claude(monkeypatch):
    """Verify scanner uses GEMINI_API_KEY and doesn't invoke OpenRouter or Claude CLI."""
    # Ensure neither OpenRouter nor Claude CLI are invoked
    def openrouter_must_not_be_called(*a, **k):
        raise AssertionError("OpenRouter must not be called when provider is gemini")

    def claude_cli_must_not_be_called(*a, **k):
        raise AssertionError("Claude CLI must not be called when provider is gemini")

    def anthropic_must_not_be_called(*a, **k):
        raise AssertionError("Anthropic API must not be called when provider is gemini")

    monkeypatch.setattr(llm_utils, "chat_with_fallback", openrouter_must_not_be_called)
    monkeypatch.setattr(llm_utils, "_chat_with_claude_cli", claude_cli_must_not_be_called)
    monkeypatch.setattr(llm_utils, "_chat_with_anthropic", anthropic_must_not_be_called)

    # Mock score_job_with_gemini to return valid score
    scored_calls = []
    def fake_gemini_score(job, resume, cfg):
        scored_calls.append(job)
        return {"score": 85, "reason": "Matched backend skills perfectly."}

    monkeypatch.setattr(llm_utils, "score_job_with_gemini", fake_gemini_score)

    config = {
        "llm_provider": "gemini",
        "gemini_api_key": "test-gemini-key",
        "candidate": {"min_score": 60},
    }
    jobs = [
        {"company": "Acme Corp", "title": "Senior Python Engineer", "url": "https://acme.co/job/1", "location": "Remote"}
    ]

    out = scanner.score_jobs(jobs, "Resume content", config)

    assert len(scored_calls) == 1
    assert len(out) == 1
    assert out[0]["score"] == 85
    assert out[0]["reason"] == "Matched backend skills perfectly."


def test_score_job_gemini_raise_on_error(monkeypatch):
    """raise_on_error=True surfaces the failure instead of the score-0 fallback,
    so callers can tell 'failed' apart from 'scored 0'."""
    def _boom(api_key=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types", _boom)
    with pytest.raises(RuntimeError, match="network down"):
        llm_utils.score_job_with_gemini({"title": "t"}, "resume", {}, raise_on_error=True)
