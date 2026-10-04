from unittest.mock import patch

import pytest

from job_hunt.db import get_job, init_db, save_job
from job_hunt.models import JobPosting, canonical_hash
from job_hunt.scorer import score_and_process_job


@pytest.fixture
def test_db(tmp_path):
    path = str(tmp_path / "test_scoring.db")
    init_db(path)
    return path

@patch("job_hunt.scorer.score_job_with_gemini")
@patch("job_hunt.scorer.send_telegram_notification")
@patch("job_hunt.scorer.time.sleep")
def test_score_and_process_job_high_score(mock_sleep, mock_notify, mock_gemini, test_db):
    mock_gemini.return_value = {"score": 85, "reason": "Great fit for Node.js"}
    mock_notify.return_value = True
    
    job = JobPosting(
        global_id="gh:stripe:101",
        ats="greenhouse",
        company="Stripe",
        title="Software Engineer, Backend",
        location="Bengaluru, India",
        is_remote=False,
        url="https://boards.greenhouse.io/stripe/jobs/101",
        description_text="Building backend APIs with Node.js and distributed systems.",
    )
    save_job(job, status="discovered", db_path=test_db)
    
    result = score_and_process_job(
        job=job,
        resume_text="Experienced Node.js developer",
        gemini_api_key="fake-key",
        telegram_token="fake-token",
        telegram_chat_id="fake-chat",
        db_path=test_db,
    )
    
    assert result["score"] == 85
    mock_sleep.assert_called_with(4.2)
    mock_notify.assert_called_once()
    
    chash = canonical_hash(job.title, job.company, job.location)
    rec = get_job(chash, db_path=test_db)
    assert rec["status"] == "notified"
    assert rec["score"] == 85

@patch("job_hunt.scorer.score_job_with_gemini")
@patch("job_hunt.scorer.send_telegram_notification")
@patch("job_hunt.scorer.time.sleep")
def test_score_and_process_job_low_score(mock_sleep, mock_notify, mock_gemini, test_db):
    mock_gemini.return_value = {"score": 50, "reason": "Requires other languages"}
    
    job = JobPosting(
        global_id="gh:stripe:102",
        ats="greenhouse",
        company="Stripe",
        title="Software Engineer, Platform",
        location="Bengaluru, India",
        is_remote=False,
        url="https://boards.greenhouse.io/stripe/jobs/102",
        description_text="Ruby on Rails",
    )
    save_job(job, status="discovered", db_path=test_db)
    
    result = score_and_process_job(
        job=job,
        resume_text="Experienced Node.js developer",
        gemini_api_key="fake-key",
        telegram_token="fake-token",
        telegram_chat_id="fake-chat",
        db_path=test_db,
    )
    
    assert result["score"] == 50
    mock_notify.assert_not_called()
    
    chash = canonical_hash(job.title, job.company, job.location)
    rec = get_job(chash, db_path=test_db)
    assert rec["status"] == "scored"
    assert rec["score"] == 50


def _job(n="201"):
    return JobPosting(
        global_id=f"gh:acme:{n}",
        ats="greenhouse",
        company="Acme",
        title=f"Backend Engineer {n}",
        location="Bengaluru, India",
        is_remote=False,
        url=f"https://boards.greenhouse.io/acme/jobs/{n}",
        description_text="Node.js",
    )


@patch("job_hunt.scorer.score_job_with_gemini")
@patch("job_hunt.scorer.send_telegram_notification")
@patch("job_hunt.scorer.time.sleep")
def test_scoring_failure_leaves_job_discovered(mock_sleep, mock_notify, mock_gemini, test_db):
    """A Gemini failure must not be persisted as score=0/'scored' — the job stays
    'discovered' so the next scan re-evaluates it."""
    mock_gemini.side_effect = RuntimeError("429 quota exhausted")
    job = _job()
    save_job(job, status="discovered", db_path=test_db)

    result = score_and_process_job(
        job=job, resume_text="r", gemini_api_key="k",
        telegram_token="t", telegram_chat_id="c", db_path=test_db,
    )

    assert result["status"] == "discovered"
    assert result["score"] is None
    mock_notify.assert_not_called()
    rec = get_job(canonical_hash(job.title, job.company, job.location), db_path=test_db)
    assert rec["status"] == "discovered"
    assert rec["score"] is None


@patch("job_hunt.scorer.score_job_with_gemini")
@patch("job_hunt.scorer.send_telegram_notification")
@patch("job_hunt.scorer.time.sleep")
def test_high_score_with_failed_telegram_stays_scored(mock_sleep, mock_notify, mock_gemini, test_db):
    mock_gemini.return_value = {"score": 90, "reason": "fit"}
    mock_notify.return_value = False  # disabled or HTTP != 200
    job = _job("202")
    save_job(job, status="discovered", db_path=test_db)

    result = score_and_process_job(
        job=job, resume_text="r", gemini_api_key="k", db_path=test_db,
    )

    assert result["status"] == "scored"
    rec = get_job(canonical_hash(job.title, job.company, job.location), db_path=test_db)
    assert rec["status"] == "scored"
    assert rec["score"] == 90


@patch("job_hunt.scorer.score_job_with_gemini")
@patch("job_hunt.scorer.send_telegram_notification")
@patch("job_hunt.scorer.time.sleep")
def test_scorer_uses_configured_model_and_candidate(mock_sleep, mock_notify, mock_gemini, test_db):
    mock_gemini.return_value = {"score": 40, "reason": "meh"}
    job = _job("203")
    save_job(job, status="discovered", db_path=test_db)
    config = {"gemini_model": "gemini-2.5-flash", "candidate": {"name": "Manish Singh"}}

    score_and_process_job(
        job=job, resume_text="r", gemini_api_key="k", db_path=test_db, config=config,
    )

    passed_cfg = mock_gemini.call_args.kwargs["config"]
    assert passed_cfg["gemini_model"] == "gemini-2.5-flash"
    assert passed_cfg["gemini_api_key"] == "k"
    assert passed_cfg["candidate"]["name"] == "Manish Singh"
    assert mock_gemini.call_args.kwargs["raise_on_error"] is True


@patch("job_hunt.scorer.send_telegram")
@pytest.mark.parametrize("token,chat_id", [
    ("", "123"), ("tok", ""), (None, "123"),
    ("YOUR_TELEGRAM_BOT_TOKEN", "123"), ("tok", "YOUR_TELEGRAM_CHAT_ID"),
    ("your_telegram_bot_token_here", "123"),
])
def test_send_telegram_notification_skips_unconfigured(mock_send, token, chat_id):
    from job_hunt.scorer import send_telegram_notification
    assert send_telegram_notification(token, chat_id, job=_job(), score=90, reason="x") is False
    mock_send.assert_not_called()


# ── batch scoring ─────────────────────────────────────────────────────────────

@patch("job_hunt.scorer.score_jobs_batch_with_gemini")
@patch("job_hunt.scorer.send_telegram_notification")
@patch("job_hunt.scorer.time.sleep")
def test_batch_scores_saves_and_leaves_missing_jobs_discovered(mock_sleep, mock_notify, mock_batch, test_db):
    from job_hunt.scorer import score_and_process_batch
    jobs = [_job("301"), _job("302"), _job("303")]
    for j in jobs:
        save_job(j, status="discovered", db_path=test_db)
    # model answered 301 and 302 only; ids are positional
    mock_batch.return_value = {"0": {"score": 91, "reason": "great"}, "1": {"score": 30, "reason": "weak"}}
    mock_notify.return_value = False

    results = score_and_process_batch(
        jobs=jobs, resume_text="r", gemini_api_key="k", db_path=test_db,
        min_notify_score=60, config={"gemini_model": "m"},
    )

    assert [r["score"] for r in results] == [91, 30, None]
    assert [r["status"] for r in results] == ["scored", "scored", "discovered"]
    mock_sleep.assert_called_once_with(4.2)               # one pacing sleep per batch call
    sent_jobs = mock_batch.call_args.args[0]
    assert [j["id"] for j in sent_jobs] == ["0", "1", "2"]
    assert mock_batch.call_args.args[2]["gemini_api_key"] == "k"
    statuses = [get_job(canonical_hash(j.title, j.company, j.location), db_path=test_db)["status"] for j in jobs]
    assert statuses == ["scored", "scored", "discovered"]
    mock_notify.assert_called_once()                       # only the 91 crosses 60


@patch("job_hunt.scorer.score_jobs_batch_with_gemini")
@patch("job_hunt.scorer.time.sleep")
def test_batch_call_failure_leaves_all_discovered(mock_sleep, mock_batch, test_db):
    from job_hunt.scorer import score_and_process_batch
    jobs = [_job("401"), _job("402")]
    for j in jobs:
        save_job(j, status="discovered", db_path=test_db)
    mock_batch.side_effect = RuntimeError("429 quota")

    results = score_and_process_batch(jobs=jobs, resume_text="r", gemini_api_key="k", db_path=test_db)

    assert [r["status"] for r in results] == ["discovered", "discovered"]
    assert all(r["score"] is None for r in results)
