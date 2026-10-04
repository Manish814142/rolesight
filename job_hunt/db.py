"""SQLite storage and deduplication module for JobNotify."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from job_hunt.models import JobPosting, canonical_hash, url_hash

DEFAULT_DB_PATH = "data/jobs.db"

# PRAGMA user_version of a database whose Workday ids were re-derived (see _rekey_workday).
SCHEMA_VERSION = 1


def _rekey_workday(conn: sqlite3.Connection) -> None:
    """Make every stored Workday global_id equal what the adapter emits for that job.

    The first T30 migration rewrote them to 'workday:<company display name>:...' while the
    adapter uses the tenant ('workday:amat:...'), so already-scored jobs were never found
    again and would have been re-scored. A row whose new id is already taken is left alone.
    """
    # Imported here, not at module level: the adapters package imports models.
    from job_hunt.adapters.workday import workday_global_id_from_url

    rows = conn.execute("SELECT id, global_id, url FROM jobs WHERE ats = 'workday'").fetchall()
    for row_id, global_id, url in rows:
        new_id = workday_global_id_from_url(url)
        if new_id and new_id != global_id:
            try:
                conn.execute("UPDATE jobs SET global_id = ? WHERE id = ?", (new_id, row_id))
            except sqlite3.IntegrityError:
                pass


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Migrate legacy database schema where canonical_hash was UNIQUE.

    Changes canonical_hash from UNIQUE to indexed, adds unique index on
    (ats, global_id) for jobs with an ATS requisition ID, and retains a fallback
    unique index on canonical_hash for jobs lacking a global_id.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs';")
    row = cursor.fetchone()
    if not row or not row[0]:
        return
    table_sql = row[0]
    if (
        "canonical_hash  TEXT UNIQUE" in table_sql
        or "canonical_hash TEXT UNIQUE" in table_sql
        or "UNIQUE(canonical_hash)" in table_sql
        or "UNIQUE (canonical_hash)" in table_sql
    ):
        # 1. Re-derive Workday ids from the stored URLs, exactly as the adapter builds them
        _rekey_workday(conn)
        # 2. Collapse rows that now share (ats, global_id) -- the same requisition stored twice --
        #    keeping a scored one if there is one
        conn.execute("""
            DELETE FROM jobs
            WHERE global_id IS NOT NULL AND global_id != ''
              AND id NOT IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY ats, global_id
                        ORDER BY (status IN ('scored', 'notified')) DESC, id
                    ) AS rn
                    FROM jobs
                    WHERE global_id IS NOT NULL AND global_id != ''
                ) WHERE rn = 1
              );
        """)
        # 3. Recreate table without UNIQUE on canonical_hash
        conn.execute("PRAGMA foreign_keys=OFF;")
        conn.execute("""
            CREATE TABLE jobs_new (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_hash  TEXT,
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
        """)
        conn.execute("INSERT INTO jobs_new SELECT * FROM jobs;")
        conn.execute("DROP TABLE jobs;")
        conn.execute("ALTER TABLE jobs_new RENAME TO jobs;")
        conn.commit()


def init_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Initialize SQLite database, run migrations, and create indexes."""
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_hash  TEXT,
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
    _migrate_db(conn)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_canonical ON jobs(canonical_hash);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_ats_global_id ON jobs(ats, global_id) "
        "WHERE global_id IS NOT NULL AND global_id != '';"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_canonical_fallback ON jobs(canonical_hash) "
        "WHERE global_id IS NULL OR global_id = '';"
    )
    if conn.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
        _rekey_workday(conn)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    return conn


def has_job(
    key: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
    c_hash: Optional[str] = None,
) -> bool:
    """Check if a job exists by global_id or canonical_hash."""
    init_db(db_path)
    lookup_key = key or c_hash or ""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM jobs WHERE global_id = ? LIMIT 1;", (lookup_key,))
        if cursor.fetchone() is not None:
            return True
        cursor.execute("SELECT 1 FROM jobs WHERE canonical_hash = ? LIMIT 1;", (lookup_key,))
        return cursor.fetchone() is not None


def save_job(
    job: JobPosting,
    status: str = "discovered",
    db_path: str = DEFAULT_DB_PATH,
) -> bool:
    """Save a JobPosting to the database if it doesn't already exist.

    Dedupes by (ats, global_id) if global_id is present, falling back to canonical_hash.
    Returns True if inserted, False if it already exists.
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
    key: Optional[str] = None,
    status: str = "discovered",
    score: Optional[int] = None,
    score_reason: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
    c_hash: Optional[str] = None,
) -> None:
    """Update status, score, score_reason and scored_at for a job by global_id or canonical_hash."""
    init_db(db_path)
    lookup_key = key or c_hash or ""
    now_iso = datetime.now(timezone.utc).isoformat() if score is not None else None

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        if score is not None:
            cursor.execute(
                """
                UPDATE jobs
                SET status = ?, score = ?, score_reason = ?, scored_at = ?
                WHERE global_id = ?;
                """,
                (status, score, score_reason, now_iso, lookup_key),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    UPDATE jobs
                    SET status = ?, score = ?, score_reason = ?, scored_at = ?
                    WHERE canonical_hash = ?;
                    """,
                    (status, score, score_reason, now_iso, lookup_key),
                )
        else:
            cursor.execute(
                "UPDATE jobs SET status = ? WHERE global_id = ?;",
                (status, lookup_key),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "UPDATE jobs SET status = ? WHERE canonical_hash = ?;",
                    (status, lookup_key),
                )
        conn.commit()


def get_job(
    key: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
    c_hash: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve a job by global_id (primary) or canonical_hash (fallback)."""
    init_db(db_path)
    lookup_key = key or c_hash or ""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE global_id = ? LIMIT 1;", (lookup_key,))
        row = cursor.fetchone()
        if row is not None:
            return dict(row)
        cursor.execute("SELECT * FROM jobs WHERE canonical_hash = ? LIMIT 1;", (lookup_key,))
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
