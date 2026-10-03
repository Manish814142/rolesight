"""SQLite storage and deduplication module for JobNotify."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from job_hunt.models import JobPosting, canonical_hash, url_hash

DEFAULT_DB_PATH = "data/jobs.db"


def init_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Initialize SQLite database and create jobs table if not exists."""
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_canonical ON jobs(canonical_hash);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
    conn.commit()
    return conn


def has_job(c_hash: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Check if a job with the canonical hash already exists in database."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM jobs WHERE canonical_hash = ? LIMIT 1;", (c_hash,))
        return cursor.fetchone() is not None


def save_job(
    job: JobPosting,
    status: str = "discovered",
    db_path: str = DEFAULT_DB_PATH,
) -> bool:
    """Save a JobPosting to the database if it doesn't already exist.

    Returns True if inserted, False if canonical_hash already exists.
    """
    init_db(db_path)
    c_hash = canonical_hash(job.title, job.company, job.location)
    u_hash = url_hash(job.url)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO jobs (
                    canonical_hash, url_hash, global_id, title,
                    company, ats, url, status, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    c_hash,
                    u_hash,
                    job.global_id,
                    job.title,
                    job.company,
                    job.ats,
                    job.url,
                    status,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def update_job_status(
    c_hash: str,
    status: str,
    score: Optional[int] = None,
    score_reason: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Update status, score, score_reason and scored_at for a job."""
    init_db(db_path)
    now_iso = datetime.now(timezone.utc).isoformat() if score is not None else None

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        if score is not None:
            cursor.execute(
                """
                UPDATE jobs
                SET status = ?, score = ?, score_reason = ?, scored_at = ?
                WHERE canonical_hash = ?;
                """,
                (status, score, score_reason, now_iso, c_hash),
            )
        else:
            cursor.execute(
                """
                UPDATE jobs
                SET status = ?
                WHERE canonical_hash = ?;
                """,
                (status, c_hash),
            )
        conn.commit()


def get_job(c_hash: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieve a job by its canonical hash."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE canonical_hash = ? LIMIT 1;", (c_hash,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_jobs_by_status(
    status: str, db_path: str = DEFAULT_DB_PATH
) -> List[Dict[str, Any]]:
    """Retrieve all jobs with a specific status."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE status = ? ORDER BY id DESC;", (status,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
