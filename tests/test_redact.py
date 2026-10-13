"""T95: a secret never reaches the terminal or data/scan.log through an error message.

Telegram puts the bot token in the URL path (`/bot<token>/sendMessage`), and `requests` names the URL in its connection
errors, so printing `str(e)` prints the token.
"""
from unittest.mock import MagicMock

import requests

from job_hunt import doctor, notifier
from job_hunt.log import redact

TOKEN = "123456789:AAEhBP0av28-FAKE-token-for-tests_xyz"
CONNECTION_ERROR = (f"HTTPSConnectionPool(host='api.telegram.org', port=443): Max retries exceeded with url: "
                    f"/bot{TOKEN}/sendMessage (Caused by NameResolutionError)")


def test_redact_replaces_every_occurrence_of_every_secret():
    assert redact(f"a {TOKEN} b {TOKEN}", TOKEN) == "a *** b ***"
    assert redact("key=ABCDEFGH12 and chat=987654321", "ABCDEFGH12", "987654321") == "key=*** and chat=***"


def test_redact_leaves_short_empty_and_missing_secrets_alone():
    """A one-letter "secret" would otherwise turn the whole message into asterisks."""
    assert redact("a b c", "a", "", None) == "a b c"
    assert redact("", TOKEN) == ""


def test_send_telegram_does_not_print_the_token_when_the_request_fails(monkeypatch, capsys):
    def boom(*a, **k):
        raise requests.ConnectionError(CONNECTION_ERROR)
    monkeypatch.setattr(notifier.requests, "post", boom)
    assert notifier.send_telegram(TOKEN, "42", "hi") is False
    out = capsys.readouterr().out
    assert "Telegram error" in out and TOKEN not in out and "/bot***/sendMessage" in out


def test_send_telegram_does_not_print_the_token_from_a_failed_response(monkeypatch, capsys):
    resp = MagicMock()
    resp.status_code = 401
    resp.text = f'{{"ok":false,"description":"Unauthorized: {TOKEN}"}}'
    monkeypatch.setattr(notifier.requests, "post", lambda *a, **k: resp)
    assert notifier.send_telegram(TOKEN, "42", "hi") is False
    assert TOKEN not in capsys.readouterr().out


def test_doctor_does_not_return_the_token_when_the_request_fails(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError(CONNECTION_ERROR)
    monkeypatch.setattr(doctor.requests, "get", boom)
    ok, msg = doctor.check_telegram_credentials(bot_token=TOKEN, chat_id="42")
    assert not ok and "network error" in msg and TOKEN not in msg


def test_doctor_does_not_return_the_token_from_a_failed_response(monkeypatch):
    resp = MagicMock()
    resp.status_code = 401
    resp.text = f"Unauthorized {TOKEN}"
    monkeypatch.setattr(doctor.requests, "get", lambda *a, **k: resp)
    ok, msg = doctor.check_telegram_credentials(bot_token=TOKEN, chat_id="42")
    assert not ok and TOKEN not in msg
