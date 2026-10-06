"""Tests must never reach the real Gemini API or inherit the developer's keys."""
import os

import pytest

from job_hunt import llm_utils, main


def test_real_gemini_client_is_blocked_unless_a_test_stubs_it():
    """If this fails, a test would silently spend real API quota (it did once: 429s from Google in a run)."""
    with pytest.raises(RuntimeError, match="real Gemini"):
        llm_utils._get_genai_client_and_types("any-key")


def test_a_dotenv_loaded_by_one_test_does_not_leak_to_the_next(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text('GEMINI_API_KEY="from-dotenv-leak"\n')
    (tmp_path / "config.json").write_text("{}")
    main.load_config()                              # load_dotenv(override=True) sets os.environ for real
    assert os.environ["GEMINI_API_KEY"] == "from-dotenv-leak"


def test_the_previous_tests_dotenv_is_gone():
    assert "GEMINI_API_KEY" not in os.environ
