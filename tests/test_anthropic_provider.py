"""T63: `_chat_with_anthropic` must only send keywords the installed anthropic SDK accepts. No network."""
import inspect
import sys
import types

import pytest

from job_hunt import llm_utils

MESSAGES = [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}]


def _reply(text="ok"):
    return types.SimpleNamespace(content=[types.SimpleNamespace(text=text)],
                                 usage=types.SimpleNamespace(input_tokens=1, output_tokens=1))


def test_call_binds_to_the_installed_sdks_real_signature(monkeypatch):
    """The installed SDK's own `Messages.create` signature is the oracle; its version decides the keywords."""
    pytest.importorskip("anthropic")
    from anthropic.resources.messages import Messages

    real_create = Messages.create

    def checked(self, **kwargs):
        inspect.signature(real_create).bind(self, **kwargs)     # TypeError if the SDK would reject a keyword
        return _reply("ok")

    monkeypatch.setattr(Messages, "create", checked)
    assert llm_utils._chat_with_anthropic({"anthropic_api_key": "k"}, MESSAGES, 0.1, 100) == "ok"


def _install_fake_sdk(monkeypatch, create):
    class Client:
        def __init__(self, **kwargs):
            self.messages = types.SimpleNamespace(create=create)

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))


def test_temperature_is_sent_when_the_sdk_accepts_it(monkeypatch):
    """Older SDKs (pyproject allows anthropic>=0.30.0) take temperature; keep the scorer's 0.1 there."""
    sent = {}

    def create(*, model, messages, max_tokens, temperature=None, system=None):
        sent.update(temperature=temperature, system=system, max_tokens=max_tokens)
        return _reply()

    _install_fake_sdk(monkeypatch, create)
    llm_utils._chat_with_anthropic({"anthropic_api_key": "k"}, MESSAGES, 0.1, 100)
    assert sent == {"temperature": 0.1, "system": "be brief", "max_tokens": 100}


def test_temperature_is_left_out_when_the_sdk_does_not_accept_it(monkeypatch):
    sent = {}

    def create(*, model, messages, max_tokens, system=None):
        sent.update(system=system)
        return _reply()

    _install_fake_sdk(monkeypatch, create)
    llm_utils._chat_with_anthropic({"anthropic_api_key": "k"}, MESSAGES, 0.1, 100)
    assert sent == {"system": "be brief"}
