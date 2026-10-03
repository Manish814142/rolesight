import json
from unittest.mock import patch

import pytest

from job_hunt import scanner
from job_hunt.db import get_job, get_jobs_by_status, init_db, save_job, update_job_status
from job_hunt.models import JobPosting, canonical_hash


@pytest.fixture
def direct_scan_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    resume_file = tmp_path / "resume.md"
    resume_file.write_text("Experienced Node.js and TypeScript Backend Engineer with 3+ years experience.")
    
    db_file = tmp_path / "data" / "jobs.db"
    init_db(str(db_file))
    
    cfg = {
        "candidate": {
            "name": "Manish Singh",
            "resume_path": "resume.md",
            "min_score": 60,
            "top_n": 5,
        },
        "gemini_api_key": "test-gemini-key",
        "telegram": {"token": "test-token", "chat_id": "test-chat"},
    }
    return cfg, str(db_file)

@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_job")
def test_direct_scan_and_deduplication(mock_score, mock_fetch, direct_scan_env):
    cfg, db_path = direct_scan_env
    
    # 2 jobs: 1 backend engineer (matches), 1 senior architect (prefilter should skip)
    job_good = JobPosting(
        global_id="gh:stripe:1",
        ats="greenhouse",
        company="Stripe",
        title="Software Engineer, Backend",
        location="Bengaluru, India",
        is_remote=False,
        url="https://boards.greenhouse.io/stripe/1",
        description_text="Node.js and distributed systems",
    )
    job_bad = JobPosting(
        global_id="gh:stripe:2",
        ats="greenhouse",
        company="Stripe",
        title="Senior Director of Sales",
        location="Bengaluru, India",
        is_remote=False,
        url="https://boards.greenhouse.io/stripe/2",
        description_text="Sales leadership",
    )
    mock_fetch.return_value = [job_good, job_bad]
    def _score(**kw):
        j = kw["job"]
        update_job_status(canonical_hash(j.title, j.company, j.location), "scored", 85, "Node.js match")
        return {"score": 85, "reason": "Node.js match", "status": "scored"}

    mock_score.side_effect = _score
    
    companies = [{"name": "Stripe", "ats": "greenhouse", "slug": "stripe"}]
    
    # First scan:
    scanner.run_scan(cfg, companies)
    
    # mock_score called once only for the good job!
    mock_score.assert_called_once()
    assert mock_score.call_args[1]["job"].title == "Software Engineer, Backend"
    
    # Skipped jobs recorded in DB
    skipped = get_jobs_by_status("skipped")
    assert len(skipped) == 1
    assert skipped[0]["title"] == "Senior Director of Sales"
    
    # Second scan: same jobs returned
    mock_score.reset_mock()
    scanner.run_scan(cfg, companies)
    
    # Second scan should NOT call mock_score at all because good job was already recorded!
    mock_score.assert_not_called()


def _backend_job(n="9"):
    return JobPosting(
        global_id=f"gh:acme:{n}",
        ats="greenhouse",
        company="Acme",
        title="Backend Engineer (JavaScript)",
        location="Bengaluru, India",
        is_remote=False,
        url=f"https://boards.greenhouse.io/acme/{n}",
        description_text="Node.js",
    )


@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_job")
def test_failed_scoring_is_retried_next_scan(mock_score, mock_fetch, direct_scan_env):
    """Scorer leaves a failed job as 'discovered'; the next scan must score it again."""
    cfg, _ = direct_scan_env
    mock_fetch.return_value = [_backend_job()]
    mock_score.return_value = {"score": None, "reason": "Scoring failed: 429", "status": "discovered"}
    companies = [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}]

    scanner.run_scan(cfg, companies)
    assert mock_score.call_count == 1
    assert json.loads(scanner.LAST_SCAN_FILE.read_text()) == []  # failed job not reported as scored

    scanner.run_scan(cfg, companies)
    assert mock_score.call_count == 2


@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_job")
def test_previously_skipped_job_is_reevaluated(mock_score, mock_fetch, direct_scan_env):
    """Rows skipped by an older pre-filter get another pass, so filter fixes take
    effect on jobs already in the DB."""
    cfg, db_path = direct_scan_env
    job = _backend_job("10")
    save_job(job, status="skipped", db_path=db_path)
    mock_fetch.return_value = [job]
    mock_score.return_value = {"score": 80, "reason": "fit", "status": "scored"}

    scanner.run_scan(cfg, [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}])

    mock_score.assert_called_once()
    rec = get_job(canonical_hash(job.title, job.company, job.location), db_path=db_path)
    assert rec["status"] == "discovered"  # promoted; real scorer then sets scored/notified


@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_job")
def test_scanner_passes_config_to_scorer(mock_score, mock_fetch, direct_scan_env):
    cfg, _ = direct_scan_env
    cfg["gemini_model"] = "gemini-2.5-flash"
    mock_fetch.return_value = [_backend_job("11")]
    mock_score.return_value = {"score": 50, "reason": "meh", "status": "scored"}

    scanner.run_scan(cfg, [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}])

    assert mock_score.call_args.kwargs["config"]["gemini_model"] == "gemini-2.5-flash"


@patch("job_hunt.scanner.send_telegram")
@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_job")
def test_placeholder_telegram_is_not_sent(mock_score, mock_fetch, mock_send, direct_scan_env):
    cfg, _ = direct_scan_env
    cfg["telegram"] = {"token": "real-looking-token", "chat_id": "YOUR_TELEGRAM_CHAT_ID"}
    mock_fetch.return_value = [_backend_job("12")]
    mock_score.return_value = {"score": 90, "reason": "fit", "status": "scored"}

    scanner.run_scan(cfg, [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}])

    mock_send.assert_not_called()
