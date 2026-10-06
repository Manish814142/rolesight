"""LLM dispatch + fallback — every provider path mocked; no network, no subprocess."""
import subprocess
import sys
import types

import pytest

from job_hunt import llm_utils

# --- provider dispatch ---------------------------------------------------------

def test_openrouter_was_removed_with_a_clear_message():
    with pytest.raises(ValueError, match="openrouter' was removed"):
        llm_utils.chat_with_llm({"llm_provider": "openrouter"}, [])


def test_unknown_provider_is_an_error_not_a_silent_fallback():
    with pytest.raises(ValueError, match="Unsupported llm_provider"):
        llm_utils.chat_with_llm({"llm_provider": "nonsense"}, [])
    with pytest.raises(ValueError, match="Unsupported llm_provider"):
        llm_utils.chat_with_llm({}, [])


def test_chat_with_llm_routes_anthropic(monkeypatch):
    monkeypatch.setattr(llm_utils, "_chat_with_anthropic", lambda *a, **k: "ANT")
    assert llm_utils.chat_with_llm({"llm_provider": "anthropic"}, []) == "ANT"


def test_chat_with_llm_routes_claude_cli(monkeypatch):
    monkeypatch.setattr(llm_utils, "_chat_with_claude_cli", lambda *a, **k: "CLI")
    assert llm_utils.chat_with_llm({"llm_provider": "claude_cli"}, []) == "CLI"


# --- Anthropic ----------------------------------------------------------------

def test_chat_with_anthropic(monkeypatch):
    created = {}

    class FakeMessages:
        def create(self, **kwargs):
            created.update(kwargs)
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(text="hello from claude")],
                usage=types.SimpleNamespace(input_tokens=3, output_tokens=4),
            )

    class FakeAnthropic:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    fake_mod = types.ModuleType("anthropic")
    fake_mod.Anthropic = FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake_mod)

    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "u"}]
    out = llm_utils._chat_with_anthropic({"anthropic_api_key": "k"}, msgs, 0.1, 100)
    assert out == "hello from claude"
    assert created["system"] == "sys"
    assert created["messages"] == [{"role": "user", "content": "u"}]


# --- Claude CLI ---------------------------------------------------------------

def _run_ok(stdout):
    return lambda *a, **k: types.SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def test_claude_cli_dict_output(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _run_ok('{"result": "dict answer"}'))
    out = llm_utils._chat_with_claude_cli({"claude_cli_model": "sonnet"},
                                          [{"role": "user", "content": "hi"}], 0.1, 100)
    assert out == "dict answer"


def test_claude_cli_list_output(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        _run_ok('[{"type": "other"}, {"type": "result", "result": "list answer"}]'))
    out = llm_utils._chat_with_claude_cli({}, [{"role": "system", "content": "s"},
                                               {"role": "user", "content": "hi"}], 0.1, 100)
    assert out == "list answer"


def test_claude_cli_nonzero_exit(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(returncode=2, stdout="", stderr="nope"))
    with pytest.raises(RuntimeError, match="exited 2"):
        llm_utils._chat_with_claude_cli({}, [{"role": "user", "content": "x"}], 0.1, 100)


def test_claude_cli_bad_json(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _run_ok("not json"))
    with pytest.raises(RuntimeError, match="unexpected output"):
        llm_utils._chat_with_claude_cli({}, [{"role": "user", "content": "x"}], 0.1, 100)


def test_claude_cli_binary_missing(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(RuntimeError, match="claude binary not found"):
        llm_utils._chat_with_claude_cli({}, [{"role": "user", "content": "x"}], 0.1, 100)


def test_claude_cli_timeout(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=300)

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(RuntimeError, match="timed out"):
        llm_utils._chat_with_claude_cli({}, [{"role": "user", "content": "x"}], 0.1, 100)
