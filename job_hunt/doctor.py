"""Lightweight diagnostics and sanity checks for Autopilot."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import warnings
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from dotenv import load_dotenv

from job_hunt.adapters.base import DEFAULT_HEADERS
from job_hunt.db import init_db

# Filter known benign SDK advisory from google-genai
warnings.filterwarnings("ignore", message=".*automatic function calling.*")

SAMPLE_ENDPOINTS: Dict[str, Dict[str, Any]] = {
    "Greenhouse": {
        "url": "https://boards-api.greenhouse.io/v1/boards/druva/jobs",
        "method": "GET",
    },
    "Lever": {
        "url": "https://api.lever.co/v0/postings/cred?mode=json",
        "method": "GET",
    },
    "Ashby": {
        "url": "https://api.ashbyhq.com/posting-api/job-board/sarvam?includeCompensation=true",
        "method": "GET",
    },
    "Workday": {
        "url": "https://pvh.wd1.myworkdayjobs.com/wday/cxs/pvh/PVH_Careers/jobs",
        "method": "POST",
        "json": {"limit": 1, "offset": 0},
    },
}

_PLACEHOLDERS = {
    "YOUR_GEMINI_API_KEY",
    "your_gemini_api_key_here",
    "YOUR_TELEGRAM_BOT_TOKEN",
    "your_telegram_bot_token_here",
    "YOUR_TELEGRAM_TOKEN",
    "your_telegram_token_here",
    "YOUR_TELEGRAM_CHAT_ID",
    "your_telegram_chat_id_here",
}


def _is_placeholder(val: Optional[str]) -> bool:
    if not val:
        return True
    val_clean = val.strip()
    return (
        val_clean in _PLACEHOLDERS
        or val_clean.startswith("YOUR_")
        or val_clean.endswith("_HERE")
        or val_clean.endswith("_here")
        or "your_" in val_clean
    )


def _get_gemini_client(api_key: str) -> Any:
    from google import genai
    return genai.Client(api_key=api_key)


def check_sqlite_write(db_path: str = "data/jobs.db") -> Tuple[bool, str]:
    """Check SQLite database connectivity, schema creation, and write permissions."""
    try:
        p = Path(db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        init_db(db_path)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Perform a test probe transaction
            test_hash = "__doctor_probe_hash__"
            cursor.execute(
                """
                INSERT OR REPLACE INTO jobs (canonical_hash, url_hash, global_id, title, company, ats, url, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (test_hash, test_hash, "doctor:probe", "Doctor Probe", "Doctor", "doctor", "http://probe", "test"),
            )
            conn.commit()
            cursor.execute("DELETE FROM jobs WHERE canonical_hash = ?;", (test_hash,))
            conn.commit()

        return True, f"Read/write verified ({db_path})"
    except Exception as e:
        return False, f"SQLite write failed: {e}"


def _configured_model() -> str:
    """The model a scan tries first: GEMINI_MODEL (from .env) over config.json's gemini_model, else the default (T92).

    Resolved the way load_config and llm_utils._gemini_models do, but without load_config: that exits when config.json
    is missing, and doctor is what people run before they have one."""
    from job_hunt.llm_utils import _gemini_models
    config: Dict[str, Any] = {}
    try:
        loaded = json.loads(Path("config.json").read_text())
        if isinstance(loaded, dict):
            config = loaded
    except (OSError, ValueError):
        pass
    env_model = os.getenv("GEMINI_MODEL")
    if env_model and not _is_placeholder(env_model):
        config["gemini_model"] = env_model
    return _gemini_models(config)[0]


def _mask(text: str, secret: str) -> str:
    """`text` with the secret replaced, so an error message can be printed or logged (T92)."""
    return text.replace(secret, "***") if secret and len(secret) >= 8 else text


def check_gemini_quota(api_key: Optional[str] = None, model: Optional[str] = None) -> Tuple[bool, str]:
    """Send a 1-token test prompt to Gemini via GEMINI_API_KEY to confirm quota health, on the model a scan would use first."""
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key or _is_placeholder(api_key):
        return False, "GEMINI_API_KEY is not configured or is a placeholder"

    model = model or _configured_model()
    t0 = time.time()
    try:
        try:
            client = _get_gemini_client(api_key)
            client.models.generate_content(
                model=model,
                contents="ping",
                config={"max_output_tokens": 1},
            )
        except (ImportError, AttributeError, ModuleNotFoundError):
            # Fallback to direct REST API probe. The key goes in a header: in the URL it would end up in any
            # error message that names the URL, which doctor prints and `RUN_PREFLIGHT_DOCTOR=1` writes to scan.log.
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            payload: Dict[str, Any] = {
                "contents": [{"parts": [{"text": "ping"}]}],
                "generationConfig": {"maxOutputTokens": 1},
            }
            resp = requests.post(url, json=payload, headers={"x-goog-api-key": api_key}, timeout=10)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:120]}")

        elapsed = time.time() - t0
        return True, f"Quota active (model: {model}, latency: {elapsed:.2f}s)"
    except Exception as e:
        err_msg = _mask(str(e), api_key)
        if "429" in err_msg or "ResourceExhausted" in err_msg or "quota" in err_msg.lower():
            return False, f"Quota exhausted (HTTP 429, model: {model}): {err_msg[:120]}"
        return False, f"Gemini API request failed (model: {model}): {err_msg[:120]}"


def check_telegram_credentials(
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """Validate Telegram Bot credentials via Telegram getMe endpoint."""
    if not bot_token:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    if not chat_id:
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or _is_placeholder(bot_token):
        return False, "Telegram token not configured or placeholder"

    try:
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        resp = requests.get(url, timeout=10)
        data = resp.json() if resp.status_code == 200 else {}
        if resp.status_code == 200 and data.get("ok"):
            bot_user = data.get("result", {}).get("username", "bot")
            chat_info = f", chat_id: {chat_id}" if chat_id and not _is_placeholder(chat_id) else " (chat_id missing)"
            return True, f"Connected to Telegram (@{bot_user}{chat_info})"
        return False, f"Telegram API returned HTTP {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        return False, f"Telegram network error: {e}"


def check_ats_egress() -> Dict[str, Tuple[bool, str]]:
    """Ping sample endpoints for Greenhouse, Lever, Ashby, and Workday to verify network egress."""
    results: Dict[str, Tuple[bool, str]] = {}

    for ats, spec in SAMPLE_ENDPOINTS.items():
        url = spec["url"]
        method = spec.get("method", "GET")
        t0 = time.time()
        try:
            if method == "POST":
                resp = requests.post(url, json=spec.get("json", {}), headers=DEFAULT_HEADERS, timeout=10)
            else:
                resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)

            elapsed = time.time() - t0
            if resp.status_code == 200:
                results[ats] = (True, f"HTTP 200 OK ({elapsed:.2f}s)")
            else:
                results[ats] = (False, f"HTTP {resp.status_code} ({elapsed:.2f}s)")
        except Exception as e:
            results[ats] = (False, f"Connection failed: {e}")

    return results


def run_doctor(db_path: str = "data/jobs.db", env_path: str = ".env") -> bool:
    """Execute all diagnostic checks and output a clean pass/fail checklist to the terminal."""
    load_dotenv(dotenv_path=Path(env_path), override=True)

    print("==================================================")
    print("            AUTOPILOT DOCTOR DIAGNOSTICS          ")
    print("==================================================")

    critical_failures = 0

    # 1. SQLite check
    db_ok, db_msg = check_sqlite_write(db_path)
    if db_ok:
        print(f"[PASS] SQLite Database: {db_msg}")
    else:
        print(f"[FAIL] SQLite Database: {db_msg}")
        critical_failures += 1

    # 2. Gemini Quota check
    gem_ok, gem_msg = check_gemini_quota()
    if gem_ok:
        print(f"[PASS] Gemini Quota: {gem_msg}")
    else:
        print(f"[FAIL] Gemini Quota: {gem_msg}")
        critical_failures += 1

    # 3. Telegram check (non-blocking warning if not configured, failure if configured but invalid)
    tg_ok, tg_msg = check_telegram_credentials()
    raw_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    if tg_ok:
        print(f"[PASS] Telegram Bot: {tg_msg}")
    elif not raw_token or _is_placeholder(raw_token):
        print(f"[WARN] Telegram Bot: {tg_msg} (alerts will be skipped)")
    else:
        print(f"[FAIL] Telegram Bot: {tg_msg}")

    # 4. ATS Egress checks
    egress_results = check_ats_egress()
    for ats, (eg_ok, eg_msg) in egress_results.items():
        if eg_ok:
            print(f"[PASS] Network Egress ({ats}): {eg_msg}")
        else:
            print(f"[FAIL] Network Egress ({ats}): {eg_msg}")
            critical_failures += 1

    print("==================================================")
    if critical_failures == 0:
        print("Status: All core systems operational.")
        return True
    else:
        print(f"Status: {critical_failures} critical check(s) failed.")
        return False
