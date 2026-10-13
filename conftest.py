"""Shared pytest fixtures for autopilot-jobs.

The suite must make **no** network or real-LLM calls. Every test that exercises
scanner/drafter stubs the one seam — `job_hunt.llm_utils.chat_with_llm`, imported
as a module-level name into `scanner` and `drafter`. `fake_llm` patches it in place;
`clean_env` strips host API keys so a developer's shell can't leak into assertions.
"""
import os
import shutil
import tempfile

import pytest

_LOG_DIR = None


def pytest_configure(config):
    """Point the DEBUG log at a temp dir. job_hunt opens its log file when it is first imported, so this
    runs before any test module imports it; otherwise every run appended megabytes to the repo's scan.log (T15)."""
    global _LOG_DIR
    _LOG_DIR = tempfile.mkdtemp(prefix="rolesight-test-log-")
    os.environ["ROLESIGHT_LOG"] = os.path.join(_LOG_DIR, "scan.log")


def pytest_unconfigure(config):
    if _LOG_DIR:
        shutil.rmtree(_LOG_DIR, ignore_errors=True)

# Every credential/config env var that could leak from the host shell into a test.
_ENV_KEYS = (
    "TINYFISH_API_KEY",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "LLM_PROVIDER",
    "TELEGRAM_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    """Every test starts without API keys and cannot leak environment changes to the next one.

    `main.load_config` runs `load_dotenv(override=True)`, which writes the real `.env` into os.environ
    for the rest of the session; a later scan test then reached the real Gemini API (quota spent).
    """
    saved = dict(os.environ)
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture(autouse=True)
def no_real_gemini(monkeypatch):
    """Constructing the real Gemini client fails loudly; tests that need a client stub it themselves."""
    def blocked(api_key):
        raise RuntimeError("a test tried to create a real Gemini client; stub llm_utils._get_genai_client_and_types")
    monkeypatch.setattr("job_hunt.llm_utils._get_genai_client_and_types", blocked)


@pytest.fixture(autouse=True)
def fresh_daily_quota_state():
    """llm_utils remembers models whose daily quota is gone (T64); one test's stub 429s must not leak into the next."""
    from job_hunt import llm_utils
    llm_utils._DAILY_QUOTA_EXHAUSTED.clear()
    yield
    llm_utils._DAILY_QUOTA_EXHAUSTED.clear()


@pytest.fixture(autouse=True)
def no_enrich_network(monkeypatch):
    """run_scan fetches full descriptions for survivors (adapters.enrich_job = HTTP).

    Stubbed for every test; a test that checks enrichment patches scanner.enrich_job itself.
    """
    monkeypatch.setattr("job_hunt.scanner.enrich_job", lambda job: job)


@pytest.fixture
def clean_env(monkeypatch):
    """Remove all autopilot env vars so tests assert on config.json/defaults only."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


@pytest.fixture
def fake_llm(monkeypatch):
    """Patch `chat_with_llm` in a target module with canned responses — no LLM calls.

    Usage:
        def test_x(fake_llm):
            calls = fake_llm("job_hunt.scanner", ['{"score": 9}'])
            ...
            assert calls[0]["messages"][0]["role"] == "system"

    Pass a single string (returned for every call) or a list (dequeued per call;
    the last item repeats once exhausted). Returns the recorded-calls list.
    """

    def _install(module_path, responses):
        queue = [responses] if isinstance(responses, str) else list(responses)
        calls: list[dict] = []

        def _fake(config, messages, temperature=0.1, max_tokens=4096):
            calls.append(
                {
                    "config": config,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
            )
            return queue.pop(0) if len(queue) > 1 else queue[0]

        monkeypatch.setattr(f"{module_path}.chat_with_llm", _fake)
        return calls

    return _install


@pytest.fixture
def sample_config():
    """Minimal valid config dict (Gemini provider, no key) for scanner/drafter tests."""
    return {
        "llm_provider": "gemini",
        "candidate": {
            "name": "Test Candidate",
            "resume_path": "resume/YOUR_RESUME.md",
        },
        "min_score": 7,
        "top_n": 5,
    }


@pytest.fixture
def sample_job():
    """One job record in the `state/last_scan.json` shape."""
    return {
        "url": "https://example.co/jobs/1",
        "title": "Senior ML Engineer",
        "extracted_title": "Senior ML Engineer",
        "company": "Example Co",
        "location": "Remote",
        "region": "Remote",
        "score": 9,
    }
