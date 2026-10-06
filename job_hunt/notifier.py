from typing import Any

import requests


def is_telegram_configured(bot_token: str | None, chat_id: str | None) -> bool:
    """True only when both values are set and neither is a template placeholder
    such as 'YOUR_TELEGRAM_CHAT_ID' or 'your_telegram_bot_token_here'."""
    for val in (bot_token, chat_id):
        if not val or not str(val).strip():
            return False
        v = str(val).strip().lower()
        if v.startswith("your_") or v.endswith("_here"):
            return False
    return True


def send_telegram(bot_token: str, chat_id: str, message: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: dict[str, Any] = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            print("Telegram sent.")
            return True
        print(f"Telegram failed: HTTP {resp.status_code} — {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def format_job_alert(
    company: str,
    title: str,
    location: str,
    url: str,
    score: int,
    score_reason: str,
    headcount: str = "Unknown",
) -> str:
    """Format Telegram alert message with headcount badge."""
    hc_badge = headcount if headcount and headcount.strip() else "Unknown"
    return (
        f"🎯 <b>New High Match Job ({score}/100)</b>\n"
        f"🏢 <b>Company:</b> {company} 🏷️ <i>[{hc_badge}]</i>\n"
        f"💼 <b>Role:</b> {title}\n"
        f"📍 <b>Location:</b> {location}\n"
        f"💡 <b>Match Reason:</b> {score_reason}\n"
        f'🔗 <a href="{url}">Apply Here</a>'
    )
