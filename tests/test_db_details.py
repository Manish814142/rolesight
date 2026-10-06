"""T29: the jobs table keeps each posting's location, posted date and description (no network)."""
import sqlite3

import pytest

from job_hunt import scanner
from job_hunt.db import get_job, init_db, save_job, update_job_details
from job_hunt.models import JobPosting, job_key

# The table exactly as the production database has it today (13 columns, no details).
OLD_SCHEMA = """
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, canonical_hash TEXT, url_hash TEXT, global_id TEXT,
    title TEXT, company TEXT, ats TEXT, url TEXT, score INTEGER DEFAULT NULL,
    score_reason TEXT DEFAULT NULL, status TEXT DEFAULT 'discovered',
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, scored_at TIMESTAMP DEFAULT NULL)
"""


def _job(i=1, desc="Build Node.js services", posted="2026-10-05", location="Bengaluru, India"):
    return JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title="Backend Engineer",
                      location=location, is_remote=False, url=f"https://x/{i}", description_text=desc, posted_at=posted)


def _columns(path):
    with sqlite3.connect(path) as c:
        return [r[1] for r in c.execute("PRAGMA table_info(jobs)")]


def test_old_database_gains_the_columns_without_losing_a_row(tmp_path):
    db = str(tmp_path / "old.db")
    with sqlite3.connect(db) as c:
        c.execute(OLD_SCHEMA)
        for i, (status, score) in enumerate([("scored", 88), ("skipped", None), ("discovered", None)]):
            c.execute("INSERT INTO jobs (canonical_hash, url_hash, global_id, title, company, ats, url, score, score_reason, status) "
                      "VALUES (?, ?, ?, 't', 'c', 'greenhouse', ?, ?, 'because', ?)",
                      (f"h{i}", f"u{i}", f"greenhouse:x:{i}", f"https://x/{i}", score, status))
        c.commit()
    init_db(db)
    assert {"location", "posted_at", "description"} <= set(_columns(db))
    with sqlite3.connect(db) as c:
        rows = c.execute("SELECT global_id, status, score, score_reason, location FROM jobs ORDER BY id").fetchall()
    assert rows == [("greenhouse:x:0", "scored", 88, "because", None), ("greenhouse:x:1", "skipped", None, "because", None),
                    ("greenhouse:x:2", "discovered", None, "because", None)]


def test_migration_is_idempotent(tmp_path):
    db = str(tmp_path / "old.db")
    with sqlite3.connect(db) as c:
        c.execute(OLD_SCHEMA)
        c.commit()
    init_db(db)
    first = _columns(db)
    init_db(db)
    assert _columns(db) == first and first.count("location") == 1


def test_fresh_database_has_the_columns(tmp_path):
    db = str(tmp_path / "new.db")
    init_db(db)
    assert {"location", "posted_at", "description"} <= set(_columns(db))


def test_new_rows_carry_location_posted_date_and_description(tmp_path):
    db = str(tmp_path / "j.db")
    save_job(_job(), status="discovered", db_path=db)
    row = get_job("greenhouse:x:1", db_path=db)
    assert row["location"] == "Bengaluru, India" and row["posted_at"] == "2026-10-05"
    assert row["description"] == "Build Node.js services"


def test_skipped_rows_keep_location_and_date_but_not_the_description(tmp_path):
    """30,000 skipped postings x ~5 kB of text would bloat the database for nothing."""
    db = str(tmp_path / "j.db")
    save_job(_job(desc="x" * 5000), status="skipped", db_path=db)
    row = get_job("greenhouse:x:1", db_path=db)
    assert row["location"] == "Bengaluru, India" and row["posted_at"] == "2026-10-05" and not row["description"]


def test_update_job_details_fills_an_existing_row(tmp_path):
    db = str(tmp_path / "j.db")
    save_job(_job(desc=""), status="discovered", db_path=db)
    update_job_details("greenhouse:x:1", description="the full text", db_path=db)
    assert get_job("greenhouse:x:1", db_path=db)["description"] == "the full text"


def test_run_scan_stores_the_enriched_description_of_a_scored_job(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js")
    init_db(str(tmp_path / "data" / "jobs.db"))
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [_job(1, desc="")])

    def enrich(job):
        job.description_text = "FULL ENRICHED TEXT"
        return job

    monkeypatch.setattr(scanner, "enrich_job", enrich)
    monkeypatch.setattr(scanner, "score_and_process_job",
                        lambda job, **kw: __import__("job_hunt.db", fromlist=["x"]).update_job_status(job_key(job), "scored", 70, "r")
                        or {"score": 70, "reason": "r", "status": "scored"})
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k", "telegram": {}},
                     [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    row = get_job("greenhouse:x:1")
    assert row["status"] == "scored" and row["description"] == "FULL ENRICHED TEXT"
    assert row["location"] == "Bengaluru, India"
