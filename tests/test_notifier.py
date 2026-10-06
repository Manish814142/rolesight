"""Telegram/WhatsApp senders — HTTP is mocked; assert graceful success/failure paths."""

from job_hunt import notifier


class _Resp:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


def test_send_telegram_success(monkeypatch, capsys):
    seen = {}

    def fake_post(url, json=None, timeout=None):
        seen["url"] = url
        seen["json"] = json
        return _Resp(200)

    monkeypatch.setattr(notifier.requests, "post", fake_post)
    assert notifier.send_telegram("tok", "chat", "hi") is True
    assert "bottok/sendMessage" in seen["url"]
    assert seen["json"]["parse_mode"] == "HTML"
    assert "Telegram sent." in capsys.readouterr().out


def test_send_telegram_http_error(monkeypatch):
    monkeypatch.setattr(notifier.requests, "post", lambda *a, **k: _Resp(400, "bad"))
    assert notifier.send_telegram("tok", "chat", "hi") is False


def test_send_telegram_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(notifier.requests, "post", boom)
    assert notifier.send_telegram("tok", "chat", "hi") is False


def test_format_job_alert():
    msg = notifier.format_job_alert(
        company="Razorpay",
        title="Senior Software Engineer",
        location="Bengaluru, India",
        url="https://razorpay.com/careers/123",
        score=88,
        score_reason="Strong match for backend Python and microservices.",
        headcount="1,001-5,000 employees",
    )
    assert "🎯 <b>New High Match Job (88/100)</b>" in msg
    assert "🏢 <b>Company:</b> Razorpay 🏷️ <i>[1,001-5,000 employees]</i>" in msg
    assert "💼 <b>Role:</b> Senior Software Engineer" in msg
    assert "📍 <b>Location:</b> Bengaluru, India" in msg
    assert "💡 <b>Match Reason:</b> Strong match for backend Python and microservices." in msg
    assert '🔗 <a href="https://razorpay.com/careers/123">Apply Here</a>' in msg


def test_format_job_alert_unknown_headcount():
    msg = notifier.format_job_alert(
        company="Sarvam AI",
        title="AI Engineer",
        location="Remote",
        url="https://sarvam.ai/jobs/1",
        score=95,
        score_reason="Direct LLM and generative AI fit.",
        headcount="Unknown",
    )
    assert "🏢 <b>Company:</b> Sarvam AI 🏷️ <i>[Unknown]</i>" in msg
