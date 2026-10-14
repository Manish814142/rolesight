"""Gemini scoring pipeline with rate throttling and Telegram notifications."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from job_hunt.db import DEFAULT_DB_PATH, update_job_status
from job_hunt.llm_utils import (
    GeminiQuotaExhausted,
    score_job_structured_with_gemini,
    score_job_with_gemini,
    score_jobs_batch_with_gemini,
)
from job_hunt.models import JobPosting, job_key
from job_hunt.notifier import format_job_alert, is_telegram_configured, send_telegram

logger = logging.getLogger(__name__)

# Facts and sub-scores returned by structured scoring (T41); they reach the CSV, not the database.
SUBSCORE_FIELDS = ("stack_fit", "role_fit", "seniority_fit", "location_fit", "min_years", "capped_by")

THROTTLE_INTERVAL_SECONDS = 4.2


def send_telegram_notification(
    bot_token: Optional[str],
    chat_id: Optional[str],
    job: JobPosting,
    score: int,
    reason: str,
) -> bool:
    """Format and send a Telegram alert for a high-match job.

    Returns True only when Telegram accepted the message (HTTP 200).
    """
    if not is_telegram_configured(bot_token, chat_id):
        logger.debug("Telegram not configured — skipping alert for %s @ %s", job.title, job.company)
        return False
    assert bot_token is not None and chat_id is not None

    message = format_job_alert(
        company=job.company,
        title=job.title,
        location=job.location,
        url=job.url,
        score=score,
        score_reason=reason,
        headcount=job.headcount,
    )
    return send_telegram(bot_token, chat_id, message)


def score_and_process_job(
    job: JobPosting,
    resume_text: str,
    gemini_api_key: str,
    telegram_token: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
    min_notify_score: int = 70,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Score a job posting with Gemini, enforce rate throttling, update DB, and alert if match >= threshold.

    `config` supplies `gemini_model` and the `candidate` profile for the prompt.
    On a scoring failure the DB row is left untouched ('discovered') and the
    result has score=None, so the next scan retries the job.
    """
    # 1. Call Gemini scoring (model from config/env, see score_job_with_gemini)
    job_dict = {
        "company": job.company,
        "title": job.title,
        "location": job.location,
        "url": job.url,
        "content": job.description_text or "No full description provided.",
    }
    cfg = {**(config or {}), "gemini_api_key": gemini_api_key}
    structured = cfg.get("scoring_mode", "holistic") == "structured"
    try:
        if structured:
            scoring_result = score_job_structured_with_gemini(job_dict, resume_text, cfg)
        else:
            scoring_result = score_job_with_gemini(
                job=job_dict,
                resume=resume_text,
                config=cfg,
                raise_on_error=True,
            )
    except Exception as e:
        logger.error("Scoring failed for %s @ %s — left as 'discovered' for retry: %s",
                     job.title, job.company, e)
        time.sleep(THROTTLE_INTERVAL_SECONDS)
        return {"score": None, "reason": f"Scoring failed: {e}", "status": "discovered",
                "quota_exhausted": isinstance(e, GeminiQuotaExhausted)}

    # 2. Strict 4.2s sleep interval to respect 15 RPM cap
    time.sleep(THROTTLE_INTERVAL_SECONDS)

    score = int(scoring_result.get("score", 0))
    reason = str(scoring_result.get("reason", "No reason provided."))
    details = {k: scoring_result.get(k) for k in SUBSCORE_FIELDS} if structured else {}
    if details.get("capped_by"):
        reason = f"{reason} [capped at {score}: {details['capped_by']}]"
    model, rubric = scoring_result.get("model"), scoring_result.get("rubric")
    status = _record_score(job, score, reason, telegram_token, telegram_chat_id, db_path, min_notify_score, model, rubric)
    return {
        "score": score,
        "reason": reason,
        "status": status,
        "details": details,
        "model": model,
        "rubric": rubric,
    }


def _record_score(
    job: JobPosting,
    score: int,
    reason: str,
    telegram_token: Optional[str],
    telegram_chat_id: Optional[str],
    db_path: str,
    min_notify_score: int,
    model: Optional[str] = None,
    rubric: Optional[str] = None,
) -> str:
    """Alert if the score clears the threshold, persist score/status/model/rubric, return the status."""
    status = "scored"
    if score >= min_notify_score:
        if send_telegram_notification(telegram_token, telegram_chat_id, job=job, score=score, reason=reason):
            status = "notified"
    update_job_status(
        key=job_key(job),
        status=status,
        score=score,
        score_reason=reason,
        db_path=db_path,
        model=model,
        rubric=rubric,
    )
    return status


def score_and_process_batch(
    jobs: List[JobPosting],
    resume_text: str,
    gemini_api_key: str,
    telegram_token: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
    min_notify_score: int = 70,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Score `jobs` in a single Gemini call; returns one result per job, in order.

    Jobs the model did not answer (or all of them, if the call fails) get score=None
    and stay 'discovered' in the DB so the next scan retries them.
    """
    cfg = {**(config or {}), "gemini_api_key": gemini_api_key}
    quota_exhausted = False
    payload = [
        {
            "id": str(i),
            "company": job.company,
            "title": job.title,
            "location": job.location,
            "content": job.description_text or "No full description provided.",
        }
        for i, job in enumerate(jobs)
    ]
    try:
        scored = score_jobs_batch_with_gemini(payload, resume_text, cfg)
        failure = "model returned no score for this job"
    except Exception as e:
        logger.error("Batch scoring failed for %d job(s) — left as 'discovered' for retry: %s", len(jobs), e)
        scored, failure = {}, str(e)
        quota_exhausted = isinstance(e, GeminiQuotaExhausted)
    # One pacing sleep per API call keeps us under the 15 RPM free-tier cap.
    time.sleep(THROTTLE_INTERVAL_SECONDS)

    results: List[Dict[str, Any]] = []
    for i, job in enumerate(jobs):
        r = scored.get(str(i))
        if r is None:
            results.append({"score": None, "reason": f"Scoring failed: {failure}", "status": "discovered",
                            "quota_exhausted": quota_exhausted})
            continue
        status = _record_score(job, r["score"], r["reason"], telegram_token, telegram_chat_id, db_path, min_notify_score,
                               r.get("model"), r.get("rubric"))
        results.append({"score": r["score"], "reason": r["reason"], "status": status, "model": r.get("model"),
                        "rubric": r.get("rubric")})
    return results
