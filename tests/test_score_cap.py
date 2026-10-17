"""T04: cap the jobs scored per run, newest first (no network: scoring is a stub that records the DB status)."""
from datetime import date, timedelta

import pytest

from job_hunt import scanner
from job_hunt.db import get_jobs_by_status, init_db, update_job_status
from job_hunt.models import JobPosting, job_key


def _job(i, posted=None):
    return JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title=f"Backend Engineer {i}",
                      location="Bengaluru, India", is_remote=False, url=f"https://x/{i}", description_text="Node.js",
                      posted_at=posted if posted is not None else (date.today() - timedelta(days=i)).isoformat())


@pytest.fixture
def scan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db(str(tmp_path / "data" / "jobs.db"))
    scored_titles = []

    def fake_score(job, **kw):
        scored_titles.append(job.title)
        update_job_status(job_key(job), "scored", 50, "r")
        return {"score": 50, "reason": "r", "status": "scored"}

    monkeypatch.setattr(scanner, "score_and_process_job", fake_score)

    def run(jobs, **cfg):
        monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: jobs)
        config = {"candidate": {"resume_path": "resume.md", "min_score": 60, "max_posted_age_days": None},   # the cap, not the window
                  "gemini_api_key": "k", "telegram": {}, **cfg}
        scanner.run_scan(config, [{"name": "X", "ats": "greenhouse", "slug": "x"}])
        return scored_titles
    return run


def test_there_is_no_cap_by_default_all_600_are_scored(scan):
    """T118 (Manish 2026-10-17): the default of 400 is gone; the models' daily limits are the limit (tests/test_two_model_day.py)."""
    titles = scan([_job(i) for i in range(600)])          # job i was posted i days ago
    assert len(titles) == 600
    assert len(get_jobs_by_status("scored")) == 600 and len(get_jobs_by_status("discovered")) == 0


def test_a_cap_asked_for_still_scores_the_newest_of_600_and_leaves_the_rest_discovered(scan):
    titles = scan([_job(i) for i in range(600)], max_jobs_to_score_per_run=400)
    assert len(titles) == 400
    assert set(titles) == {f"Backend Engineer {i}" for i in range(400)}
    assert len(get_jobs_by_status("scored")) == 400 and len(get_jobs_by_status("discovered")) == 200


def test_scoring_order_is_newest_first(scan):
    jobs = [_job(30), _job(2), _job(90), _job(0)]
    titles = scan(jobs)
    assert titles == ["Backend Engineer 0", "Backend Engineer 2", "Backend Engineer 30", "Backend Engineer 90"]


def test_configured_cap_and_zero_means_no_cap(scan):
    assert len(scan([_job(i) for i in range(10)], max_jobs_to_score_per_run=3)) == 3


def test_zero_disables_the_cap(scan):
    assert len(scan([_job(i) for i in range(450)], max_jobs_to_score_per_run=0)) == 450


def test_undated_jobs_are_not_starved_by_the_cap(scan):
    jobs = [_job(1), _job(5), _job(9, posted=""), _job(200)]
    titles = scan(jobs, max_jobs_to_score_per_run=3)
    assert "Backend Engineer 9" in titles and "Backend Engineer 200" not in titles
    assert len(titles) == 3


def test_jobs_left_by_the_cap_are_scored_on_the_next_scan(scan):
    jobs = [_job(i) for i in range(6)]
    first = list(scan(jobs, max_jobs_to_score_per_run=4))      # `scan` returns one shared, growing list
    assert len(first) == 4
    second = scan(jobs, max_jobs_to_score_per_run=4)           # same jobs: only the 2 left over are pending
    assert len(second) - len(first) == 2 and len(get_jobs_by_status("scored")) == 6
