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
        "model": "gemini-2.5-flash",          # the model that answered (T71)
        "rubric": llm_utils.rubric_id(),      # the prompt text sent (T97)
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

def test_scanner_scoring_with_gemini_does_not_invoke_claude_or_anthropic(monkeypatch):
    """Verify scanner uses GEMINI_API_KEY and doesn't invoke Anthropic or Claude CLI."""
    def claude_cli_must_not_be_called(*a, **k):
        raise AssertionError("Claude CLI must not be called when provider is gemini")

    def anthropic_must_not_be_called(*a, **k):
        raise AssertionError("Anthropic API must not be called when provider is gemini")

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


# --- 5. Full resume, batch scoring, fallback chain ------------------------------

LONG_RESUME = "# Manish Singh\n" + ("Node.js microservices, Kafka, MongoDB. " * 80) + "\n## Education\nB.Tech UNIQUE_TAIL_MARKER"


def _capturing_client(response_text):
    client = MagicMock()
    resp = MagicMock()
    resp.text = response_text
    client.models.generate_content.return_value = resp
    return client


def test_single_scoring_prompt_contains_full_resume(monkeypatch):
    assert len(LONG_RESUME) > 2500
    client = _capturing_client('{"score": 70, "reason": "ok"}')
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())))
    llm_utils.score_job_with_gemini({"title": "Backend Engineer"}, LONG_RESUME, {"gemini_api_key": "k"})
    prompt = client.models.generate_content.call_args.kwargs["contents"]
    assert "UNIQUE_TAIL_MARKER" in prompt


# Real survivors' clean descriptions run to ~10k chars (median 5.6k, 2026-10-04); the
# requirements usually come after the company blurb, past the old 2,000-char cut.
LONG_DESCRIPTION = "About us. " * 590 + "REQUIREMENTS_TAIL_MARKER Node.js, Kafka"


def test_single_scoring_prompt_contains_full_description(monkeypatch):
    assert len(LONG_DESCRIPTION) > 5900
    client = _capturing_client('{"score": 70, "reason": "ok"}')
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())))
    llm_utils.score_job_with_gemini({"title": "Backend Engineer", "content": LONG_DESCRIPTION},
                                    "resume", {"gemini_api_key": "k"})
    prompt = client.models.generate_content.call_args.kwargs["contents"]
    assert LONG_DESCRIPTION in prompt


def test_batch_scoring_prompt_contains_full_descriptions(monkeypatch):
    client = _capturing_client('[{"job_id": "a", "score": 50, "reason": "ok"}]')
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())))
    llm_utils.score_jobs_batch_with_gemini([{"id": "a", "title": "t", "content": LONG_DESCRIPTION}],
                                           "resume", {"gemini_api_key": "k"})
    prompt = client.models.generate_content.call_args.kwargs["contents"]
    assert LONG_DESCRIPTION in prompt


def test_runaway_description_is_bounded(monkeypatch):
    client = _capturing_client('{"score": 70, "reason": "ok"}')
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())))
    llm_utils.score_job_with_gemini({"title": "t", "content": "x" * 200_000}, "resume", {"gemini_api_key": "k"})
    prompt = client.models.generate_content.call_args.kwargs["contents"]
    import re
    # The description is the one long run of x's; counting every "x" broke when the rubric gained "example" (T73).
    assert max(len(run) for run in re.findall("x+", prompt)) == llm_utils.MAX_DESCRIPTION_CHARS


def test_batch_scoring_maps_ids_and_uses_json_schema(monkeypatch):
    client = _capturing_client(json.dumps([
        {"job_id": "j2", "score": 40, "reason": "partial"},
        {"job_id": "j1", "score": 88, "reason": "strong Node.js fit"},
        {"job_id": "zzz", "score": 99, "reason": "hallucinated id"},
    ]))
    cfg_cls = MagicMock()
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=cfg_cls)))
    jobs = [
        {"id": "j1", "company": "Plane", "title": "Software Engineer, Backend (Node.js)", "location": "India", "content": "Node"},
        {"id": "j2", "company": "Okta", "title": "ServiceNow Developer", "location": "Bengaluru", "content": "SNOW"},
        {"id": "j3", "company": "Stripe", "title": "Software Engineer", "location": "Bengaluru", "content": "Ruby"},
    ]
    out = llm_utils.score_jobs_batch_with_gemini(jobs, LONG_RESUME, {"gemini_api_key": "k"})

    m = llm_utils.GEMINI_DEFAULT_MODEL     # the model that answered (T71)
    r = llm_utils.rubric_id()              # the prompt text sent (T97)
    assert out == {"j1": {"score": 88, "reason": "strong Node.js fit", "model": m, "rubric": r},
                   "j2": {"score": 40, "reason": "partial", "model": m, "rubric": r}}  # j3 missing, zzz ignored
    assert client.models.generate_content.call_count == 1
    prompt = client.models.generate_content.call_args.kwargs["contents"]
    assert "UNIQUE_TAIL_MARKER" in prompt and prompt.count("UNIQUE_TAIL_MARKER") == 1
    for j in jobs:
        assert j["id"] in prompt
    cfg_kwargs = cfg_cls.call_args.kwargs
    assert cfg_kwargs["response_mime_type"] == "application/json"
    assert cfg_kwargs["response_json_schema"]["type"] == "array"


def test_batch_scoring_raises_on_unparseable_output(monkeypatch):
    client = _capturing_client("not json")
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())))
    with pytest.raises(Exception):
        llm_utils.score_jobs_batch_with_gemini([{"id": "a", "title": "t"}], "r", {"gemini_api_key": "k"})


def test_gemini_fallback_chain_skips_low_quota_models():
    """gemini-3.8-flash has a 20 requests/day free quota — never a fallback."""
    models = llm_utils._gemini_models({"gemini_model": "gemini-3.5-flash-lite"})
    assert models == ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
    assert llm_utils._gemini_models({"gemini_model": "gemini-x"})[0] == "gemini-x"


def test_scoring_temperature_defaults_to_0_1_and_is_configurable(monkeypatch):
    """T60: temperature is a config key so its effect on score variance can be measured."""
    captured = []
    client = _capturing_client('{"score": 70, "reason": "ok"}')
    cfg_cls = lambda **kw: captured.append(kw) or MagicMock()  # noqa: E731
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=cfg_cls)))
    llm_utils.score_job_with_gemini({"title": "t"}, "r", {"gemini_api_key": "k"})
    llm_utils.score_job_with_gemini({"title": "t"}, "r", {"gemini_api_key": "k", "gemini_temperature": 0})
    assert [c["temperature"] for c in captured] == [0.1, 0.0]


STRUCTURED_REPLY = ('{"stack_fit": 80, "role_fit": 80, "seniority_fit": 80, "location_fit": 80, "min_years": 3, '
                    '"accepts_candidate_stack": true, "onsite_outside_india": false, "aimed_at_freshers": false, "reason": "ok"}')


def test_structured_and_batch_scoring_honour_gemini_temperature_too(monkeypatch):
    """T69(a): only the single-job path read `gemini_temperature` (T60); the other two hard-coded 0.1."""
    captured = []
    cfg_cls = lambda **kw: captured.append(kw) or MagicMock()  # noqa: E731
    for reply, call in (
        (STRUCTURED_REPLY, lambda cfg: llm_utils.score_job_structured_with_gemini({"title": "t"}, "r", cfg)),
        ('[{"job_id": "0", "score": 70, "reason": "ok"}]', lambda cfg: llm_utils.score_jobs_batch_with_gemini([{"id": "0", "title": "t"}], "r", cfg)),
    ):
        client = _capturing_client(reply)
        monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                            lambda api_key, client=client: (client, types.SimpleNamespace(GenerateContentConfig=cfg_cls)))
        call({"gemini_api_key": "k"})
        call({"gemini_api_key": "k", "gemini_temperature": 0.3})
    assert [c["temperature"] for c in captured] == [0.1, 0.3, 0.1, 0.3]
