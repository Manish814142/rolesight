import sqlite3

import pytest

from job_hunt.db import get_job, get_jobs_by_status, has_job, init_db, save_job, update_job_status
from job_hunt.models import JobPosting, canonical_hash


@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "test_jobs.db")
    init_db(db_file)
    return db_file

def test_init_db(temp_db):
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs';")
    assert cursor.fetchone() is not None
    conn.close()

def test_save_and_has_job(temp_db):
    job = JobPosting(
        global_id="lever:spotify:abc-123",
        ats="lever",
        company="Spotify",
        title="Backend Developer",
        location="Remote",
        is_remote=True,
        url="https://jobs.lever.co/spotify/abc-123",
        description_text="Backend services",
        posted_at="2026-03-15",
    )
    chash = canonical_hash(job.title, job.company, job.location)
    assert not has_job(chash, temp_db)
    
    saved = save_job(job, status="discovered", db_path=temp_db)
    assert saved is True
    assert has_job(chash, temp_db)
    
    # Saving duplicate should return False and not fail
    saved_again = save_job(job, status="discovered", db_path=temp_db)
    assert saved_again is False

def test_update_job_status(temp_db):
    job = JobPosting(
        global_id="ashby:ramp:job-999",
        ats="ashby",
        company="Ramp",
        title="Full Stack Engineer",
        location="Bengaluru",
        is_remote=False,
        url="https://jobs.ashbyhq.com/ramp/job-999",
        description_text="TypeScript and Node",
        posted_at="2026-04-01",
    )
    chash = canonical_hash(job.title, job.company, job.location)
    save_job(job, status="discovered", db_path=temp_db)
    
    update_job_status(chash, status="scored", score=85, score_reason="Strong Node fit", db_path=temp_db)
    record = get_job(chash, temp_db)
    assert record is not None
    assert record["status"] == "scored"
    assert record["score"] == 85
    assert record["score_reason"] == "Strong Node fit"
    assert record["scored_at"] is not None

def test_get_jobs_by_status(temp_db):
    job1 = JobPosting("g1", "greenhouse", "C1", "T1", "L1", False, "u1")
    job2 = JobPosting("g2", "lever", "C2", "T2", "L2", True, "u2")
    save_job(job1, status="skipped", db_path=temp_db)
    save_job(job2, status="notified", db_path=temp_db)
    
    skipped = get_jobs_by_status("skipped", temp_db)
    assert len(skipped) == 1
    assert skipped[0]["title"] == "T1"
    
    notified = get_jobs_by_status("notified", temp_db)
    assert len(notified) == 1
    assert notified[0]["title"] == "T2"
