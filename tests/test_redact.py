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


# -- review 2026-10-14: the secret is masked before the text is cut, so a token that straddles the cut leaves no part behind --

def _straddling(n):
    """A response body whose token starts n characters before the place the message is cut."""
    return "x" * n + TOKEN


def test_doctor_masks_a_token_that_straddles_the_cut(monkeypatch):
    resp = MagicMock()
    resp.status_code = 401
    resp.text = _straddling(80)              # doctor keeps 100 characters
    monkeypatch.setattr(doctor.requests, "get", lambda *a, **k: resp)
    ok, msg = doctor.check_telegram_credentials(bot_token=TOKEN, chat_id="42")
    assert not ok and TOKEN[:20] not in msg


def test_send_telegram_masks_a_token_that_straddles_the_cut(monkeypatch, capsys):
    resp = MagicMock()
    resp.status_code = 401
    resp.text = _straddling(180)             # send_telegram keeps 200 characters
    monkeypatch.setattr(notifier.requests, "post", lambda *a, **k: resp)
    notifier.send_telegram(TOKEN, "42", "hi")
    assert TOKEN[:20] not in capsys.readouterr().out


def test_the_gemini_rest_fallback_masks_a_key_that_straddles_the_cut(monkeypatch, tmp_path):
    key = "AIza" + "k" * 35
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(doctor, "_get_gemini_client", lambda k: (_ for _ in ()).throw(ImportError("no sdk")))
    resp = MagicMock()
    resp.status_code = 400
    resp.text = "y" * 90 + key               # "HTTP 400: " + 90 + the start of the key: the message keeps 120 characters
    monkeypatch.setattr(doctor.requests, "post", lambda *a, **k: resp)
    ok, msg = doctor.check_gemini_quota(api_key=key)
    assert not ok and key[:12] not in msg
