"""Tests for T30: deduplicating by ATS job ID rather than title+company+location hash."""
from unittest.mock import patch

import pytest

from job_hunt.db import connect, get_job, has_job, init_db, save_job, update_job_status
from job_hunt.models import JobPosting, canonical_hash, url_hash


@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "test_jobs.db")
    init_db(db_file)
    return db_file


def test_two_req_ids_same_title_stored_as_two_rows(temp_db):
    """Two job openings at the same company with the same title and location
    but different ATS requisition IDs must be saved as two distinct rows."""
    j1 = JobPosting(
        global_id="greenhouse:druva:11111",
        ats="greenhouse",
        company="Druva",
        title="Senior Software Engineer",
        location="Pune, India",
        is_remote=False,
        url="https://boards.greenhouse.io/druva/jobs/11111",
    )
    j2 = JobPosting(
        global_id="greenhouse:druva:22222",
        ats="greenhouse",
        company="Druva",
        title="Senior Software Engineer",
        location="Pune, India",
        is_remote=False,
        url="https://boards.greenhouse.io/druva/jobs/22222",
    )

    # First job saves successfully
    assert save_job(j1, status="discovered", db_path=temp_db) is True
    # Second job with same title+company+location must ALSO save successfully
    assert save_job(j2, status="discovered", db_path=temp_db) is True

    # Duplicate insert of the same job returns False
    assert save_job(j1, status="discovered", db_path=temp_db) is False

    # Both jobs exist independently in the DB
    assert has_job("greenhouse:druva:11111", db_path=temp_db) is True
    assert has_job("greenhouse:druva:22222", db_path=temp_db) is True

    with connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM jobs WHERE title = 'Senior Software Engineer'")
        assert cursor.fetchone()[0] == 2

    # Scoring j1 updates only j1, not j2
    update_job_status("greenhouse:druva:11111", "scored", score=85, score_reason="Strong fit", db_path=temp_db)
    rec1 = get_job("greenhouse:druva:11111", db_path=temp_db)
    rec2 = get_job("greenhouse:druva:22222", db_path=temp_db)
    assert rec1 is not None and rec1["status"] == "scored" and rec1["score"] == 85
    assert rec2 is not None and rec2["status"] == "discovered" and rec2["score"] is None


def test_legacy_database_migration_allows_new_req_and_keeps_scored(tmp_path):
    """An old database with UNIQUE(canonical_hash) must migrate cleanly:
    1. Existing scored rows stay scored.
    2. A new requisition with the same title can now be saved without error."""
    db_file = str(tmp_path / "legacy.db")
    # Create old schema with canonical_hash TEXT UNIQUE
    with connect(db_file) as conn:
        conn.execute(
            """
            CREATE TABLE jobs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_hash  TEXT UNIQUE,
                url_hash        TEXT,
                global_id       TEXT,
                title           TEXT,
                company         TEXT,
                ats             TEXT,
                url             TEXT,
                score           INTEGER DEFAULT NULL,
                score_reason    TEXT DEFAULT NULL,
                status          TEXT DEFAULT 'discovered',
                discovered_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scored_at       TIMESTAMP DEFAULT NULL
            );
            """
        )
        c_hash = canonical_hash("Staff Engineer", "Druva", "Pune, India")
        conn.execute(
            """
            INSERT INTO jobs (canonical_hash, url_hash, global_id, title, company, ats, url, score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (c_hash, url_hash("http://1"), "greenhouse:druva:10001", "Staff Engineer", "Druva", "greenhouse", "http://1", 90, "scored")
        )
        conn.commit()

    # Calling init_db migrates the schema
    init_db(db_file)

    # 1. Existing scored row is still scored
    existing = get_job("greenhouse:druva:10001", db_path=db_file)
    assert existing is not None
    assert existing["status"] == "scored"
    assert existing["score"] == 90

    # 2. A new job with the same title+company+location can now be saved
    j_new = JobPosting(
        global_id="greenhouse:druva:10002",
        ats="greenhouse",
        company="Druva",
        title="Staff Engineer",
        location="Pune, India",
        is_remote=False,
        url="http://2",
    )
    assert save_job(j_new, status="discovered", db_path=db_file) is True

    # Both exist
    with connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT global_id, status FROM jobs WHERE title = 'Staff Engineer' ORDER BY id")
        rows = cursor.fetchall()
        assert rows == [("greenhouse:druva:10001", "scored"), ("greenhouse:druva:10002", "discovered")]


@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_job")
def test_scanner_evaluates_new_opening_with_same_title_as_scored(mock_score, mock_fetch, tmp_path, monkeypatch):
    """When a job with title T is already 'scored' in SQLite, a second opening
    with the same title T but a new global_id must NOT be skipped as previously scored."""
    from job_hunt import scanner

    monkeypatch.chdir(tmp_path)
    resume = tmp_path / "resume.md"
    resume.write_text("Backend engineer Node.js")
    db_file = str(tmp_path / "data" / "jobs.db")
    init_db(db_file)
    cfg = {
        "candidate": {"name": "Test", "resume_path": "resume.md", "min_score": 60, "top_n": 5},
        "gemini_api_key": "test-key",
    }
    j1 = JobPosting(
        global_id="gh:stripe:1",
        ats="greenhouse",
        company="Stripe",
        title="Software Engineer, Backend",
        location="Bengaluru, India",
        is_remote=False,
        url="https://boards.greenhouse.io/stripe/1",
        description_text="Node.js engineer",
    )
    save_job(j1, status="scored", db_path=db_file)
    update_job_status(j1.global_id, status="scored", score=85, score_reason="Good fit", db_path=db_file)

    j2 = JobPosting(
        global_id="gh:stripe:2",
        ats="greenhouse",
        company="Stripe",
        title="Software Engineer, Backend",
        location="Bengaluru, India",
        is_remote=False,
        url="https://boards.greenhouse.io/stripe/2",
        description_text="Node.js engineer second opening",
    )
    mock_fetch.return_value = [j2]
    mock_score.return_value = {"score": 88, "reason": "Good fit", "status": "scored"}

    companies = [{"name": "Stripe", "ats": "greenhouse", "slug": "stripe"}]
    scanner.run_scan(cfg, companies)

    # j2 must NOT be skipped as previously scored; mock_score should have been called for j2!
    assert mock_score.call_count == 1
    rec2 = get_job("gh:stripe:2", db_path=db_file)
    assert rec2 is not None

