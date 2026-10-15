"""SQLite storage and deduplication module for RoleSight."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from job_hunt.models import JobPosting, canonical_hash, url_hash
from job_hunt.prefilter import current_age_days, local_date_of

DEFAULT_DB_PATH = "data/jobs.db"

# PRAGMA user_version of a database whose Workday ids were re-derived (see _rekey_workday).
SCHEMA_VERSION = 1


@contextmanager
def connect(db_path: str = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    """A connection that commits when the block ends well, rolls back when it raises, and is then closed (T90).

    `with sqlite3.connect(path) as conn:` does the first two but never closes: the connection lived until garbage collection,
    and Python 3.13 reports each one as `ResourceWarning: unclosed database`."""
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


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


# What a posting looked like when it was scored (T29): the decision can be audited and re-scored later.
DETAIL_COLUMNS = ("location", "posted_at", "description")
# The Gemini model that produced `score` (T71): models score differently (T70), and a scan falls back to another
# model when the primary fails. NULL = unknown (rows scored before T71, or by the deprecated providers).
SCORE_MODEL_COLUMN = "score_model"
# Which scoring prompt wrote `score` (T97): a short id of the rubric text (llm_utils.rubric_id). The rubric changes
# (T58, T73, T74, T79) and a scored row is final, so this is how rows from older wording are found. NULL = unknown
# (rows scored before T97, or by the deprecated providers, whose prompt is a different one).
SCORE_RUBRIC_COLUMN = "score_rubric"
# Where Manish's application stands (T38, `autopilot mark`): applied / interview / rejected / offer and the local date
# it was marked. Separate from `status`, which is the scanner's own lifecycle (skipped/discovered/scored/notified).
APPLICATION_COLUMNS = ("application_status", "application_date")


# Is the posting still up? (T33) first_seen / last_seen: the first and the latest scan that fetched it;
# missed_scans: scans in a row in which its board answered with jobs but not this one; closed_at: set once
# missed_scans reaches `closed_after_missed_scans`, cleared if the job comes back. A flag, not a `status`, so the
# scanner's own lifecycle (skipped/discovered/scored/notified) is untouched.
SIGHTING_COLUMNS = {"first_seen": "TEXT", "last_seen": "TEXT", "missed_scans": "INTEGER NOT NULL DEFAULT 0",
                    "closed_at": "TEXT"}
DEFAULT_CLOSED_AFTER_MISSED_SCANS = 3


def _ensure_detail_columns(conn: sqlite3.Connection) -> None:
    """Add the detail, score-model, score-rubric, application and sighting columns to a database that predates them (idempotent).
    first_seen is backfilled from discovered_at, the time the row was first saved."""
    have = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    for col in (*DETAIL_COLUMNS, SCORE_MODEL_COLUMN, SCORE_RUBRIC_COLUMN, *APPLICATION_COLUMNS):
        if col not in have:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT")
    for col, decl in SIGHTING_COLUMNS.items():
        if col not in have:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {decl}")
            if col == "first_seen":
                conn.execute("UPDATE jobs SET first_seen = discovered_at WHERE first_seen IS NULL;")


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize SQLite database, run migrations, and create indexes."""
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    with connect(db_path) as conn:
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
        # One row per scan run (T31): `draft N` / `mark N` mean job N of the last *completed* scan, best score first.
        conn.execute(
            "CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, "
            "finished_at TEXT DEFAULT NULL);"
        )
        _migrate_db(conn)
        _ensure_detail_columns(conn)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_canonical ON jobs(canonical_hash);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
        # get_job / has_job / update_job_* look a job up by its bare global_id; the partial unique index below is on
        # (ats, global_id) with a WHERE clause that `global_id = ?` does not imply, so SQLite scanned the table (T75).
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_global_id ON jobs(global_id);")
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


def has_job(
    key: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
    c_hash: Optional[str] = None,
) -> bool:
    """Check if a job exists by global_id or canonical_hash."""
    init_db(db_path)
    lookup_key = key or c_hash or ""
    with connect(db_path) as conn:
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
    now = datetime.now(timezone.utc).isoformat()

    with connect(db_path) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO jobs (
                    canonical_hash, url_hash, global_id, title,
                    company, ats, url, status, discovered_at,
                    location, posted_at, description, first_seen, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
                    now,
                    job.location,
                    job.posted_at,
                    # Skipped postings (30,000+) would add ~5 kB each for nothing.
                    "" if status == "skipped" else job.description_text,
                    now,
                    now,
                ),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def update_job_details(
    key: str,
    location: Optional[str] = None,
    posted_at: Optional[str] = None,
    description: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Fill the detail columns of an existing row (by global_id, else canonical_hash); None leaves a column alone."""
    init_db(db_path)
    fields = {"location": location, "posted_at": posted_at, "description": description}
    sets = {k: v for k, v in fields.items() if v is not None}
    if not sets:
        return
    assignments = ", ".join(f"{k} = ?" for k in sets)
    with connect(db_path) as conn:
        cur = conn.execute(f"UPDATE jobs SET {assignments} WHERE global_id = ?;", (*sets.values(), key))
        if cur.rowcount == 0:
            conn.execute(f"UPDATE jobs SET {assignments} WHERE canonical_hash = ?;", (*sets.values(), key))
        conn.commit()


def fill_missing_details(
    key: str,
    location: Optional[str] = None,
    posted_at: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Store a location and a posted date on an existing row (by global_id, else canonical_hash) only where it has none
    (T99): rows scored before T29 never got them. Never overwrites, and never touches the description (that column is
    what the scorer saw) or any score column."""
    init_db(db_path)
    fields = {"location": location, "posted_at": posted_at}
    sets = {k: v for k, v in fields.items() if v}
    if not sets:
        return
    assignments = ", ".join(f"{k} = COALESCE(NULLIF({k}, ''), ?)" for k in sets)
    with connect(db_path) as conn:
        cur = conn.execute(f"UPDATE jobs SET {assignments} WHERE global_id = ?;", (*sets.values(), key))
        if cur.rowcount == 0:
            conn.execute(f"UPDATE jobs SET {assignments} WHERE canonical_hash = ?;", (*sets.values(), key))
        conn.commit()


def update_job_status(
    key: Optional[str] = None,
    status: str = "discovered",
    score: Optional[int] = None,
    score_reason: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
    c_hash: Optional[str] = None,
    model: Optional[str] = None,
    rubric: Optional[str] = None,
) -> None:
    """Update status, score, score_reason, scored_at, score_model and score_rubric for a job by global_id or canonical_hash.

    `model` and `rubric` are stored with a score (None = unknown); a status-only update leaves score, model and rubric alone.
    """
    init_db(db_path)
    lookup_key = key or c_hash or ""
    now_iso = datetime.now(timezone.utc).isoformat() if score is not None else None

    with connect(db_path) as conn:
        cursor = conn.cursor()
        if score is not None:
            cursor.execute(
                """
                UPDATE jobs
                SET status = ?, score = ?, score_reason = ?, scored_at = ?, score_model = ?, score_rubric = ?
                WHERE global_id = ?;
                """,
                (status, score, score_reason, now_iso, model, rubric, lookup_key),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    UPDATE jobs
                    SET status = ?, score = ?, score_reason = ?, scored_at = ?, score_model = ?, score_rubric = ?
                    WHERE canonical_hash = ?;
                    """,
                    (status, score, score_reason, now_iso, model, rubric, lookup_key),
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
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE global_id = ? LIMIT 1;", (lookup_key,))
        row = cursor.fetchone()
        if row is not None:
            return dict(row)
        cursor.execute("SELECT * FROM jobs WHERE canonical_hash = ? LIMIT 1;", (lookup_key,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_job_by_url(url: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """The stored row for a job URL (matched on url_hash), or None."""
    init_db(db_path)
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM jobs WHERE url_hash = ? LIMIT 1;", (url_hash(url),)).fetchone()
        return dict(row) if row else None


def start_scan(db_path: str = DEFAULT_DB_PATH) -> int:
    """Record that a scan run started; returns its id (T31)."""
    init_db(db_path)
    with connect(db_path) as conn:
        cur = conn.execute("INSERT INTO scans (started_at) VALUES (?);", (datetime.now(timezone.utc).isoformat(),))
        conn.commit()
        return int(cur.lastrowid or 0)


def finish_scan(scan_id: int, db_path: str = DEFAULT_DB_PATH) -> None:
    """Record that scan `scan_id` finished: from now on it is the "last scan" of `draft N`."""
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute("UPDATE scans SET finished_at = ? WHERE id = ?;", (datetime.now(timezone.utc).isoformat(), scan_id))
        conn.commit()


def last_scan_jobs(db_path: str = DEFAULT_DB_PATH) -> Optional[List[Dict[str, Any]]]:
    """The jobs scored during the last completed scan, best score first and, among equal scores, in scoring order:
    the order of that scan's CSV and digest, so job N here is CSV row N (T10, T31). None when no scan has completed
    (no database, or one from before T31); a missing database is not created."""
    if not os.path.exists(db_path):
        return None
    init_db(db_path)
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        scan = conn.execute("SELECT started_at, finished_at FROM scans WHERE finished_at IS NOT NULL "
                            "ORDER BY id DESC LIMIT 1;").fetchone()
        if scan is None:
            return None
        rows = conn.execute(
            "SELECT * FROM jobs WHERE score IS NOT NULL AND scored_at >= ? AND scored_at <= ? "
            "ORDER BY score DESC, scored_at ASC, id ASC;", (scan["started_at"], scan["finished_at"])).fetchall()
        return [dict(r) for r in rows]


def open_match_rows(min_score: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Scored jobs at or above `min_score` that Manish has not applied to (no application status at all) and that are
    not closed (T33), best first (T39, output/open_matches.csv). The posted-date window is applied by the caller."""
    init_db(db_path)
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status IN ('scored', 'notified') AND score >= ? AND application_status IS NULL "
            "AND closed_at IS NULL ORDER BY score DESC, scored_at, id;", (min_score,)).fetchall()
        return [dict(r) for r in rows]


# A fetch that stopped at the posted-date window (T02) read every page down to the first all-old one, so a stored job
# that is inside the window and was not returned is really absent. One day of margin: the lists are sorted by date,
# but a board whose order is only roughly by date could leave a job at the edge on a page that was not read.
WINDOW_STOP_MARGIN_DAYS = 1


def _unseen_inside_window(conn: sqlite3.Connection, ats: str, company: str, now: str, window_days: int) -> List[int]:
    """Row ids of the board's open jobs not seen in this scan whose posted date puts them inside the window."""
    # The local date, as the fetch's window (prefilter.is_too_old) uses: UTC's is a day behind India's from 00:00 to 05:30 IST,
    # which made a job at the window's edge look a day newer and count a miss (found 2026-10-15 at 05:16 IST).
    today = date.today()
    ids = []
    rows = conn.execute("SELECT id, posted_at, first_seen FROM jobs WHERE ats = ? AND company = ? AND closed_at IS NULL "
                        "AND (last_seen IS NULL OR last_seen < ?);", (ats, company, now))
    for row_id, posted_at, first_seen in rows.fetchall():
        seen_on = local_date_of(first_seen or "") or today          # the local day it was seen (T110)
        age = current_age_days(posted_at or "", seen_on, today)
        if age is not None and age <= window_days - WINDOW_STOP_MARGIN_DAYS:
            ids.append(row_id)
    return ids


def record_sightings(boards: Dict[tuple, List[JobPosting]], closed_after: int = DEFAULT_CLOSED_AFTER_MISSED_SCANS,
                     db_path: str = DEFAULT_DB_PATH, incomplete: Optional[set] = None,
                     windowed: Optional[Dict[tuple, int]] = None) -> int:
    """After a scan (T33): `boards` maps (ats, company) to the jobs that board returned. Pass only boards whose fetch
    succeeded with at least one job: a failed or empty fetch says nothing about whether a posting is still up.
    Returned jobs get last_seen = now, missed_scans = 0 and are reopened if closed; the board's other rows get one
    more missed scan and are closed when they reach `closed_after` -- except on boards in `incomplete` (the fetch
    stopped early: page failure, time budget or job cap), whose other rows are left as they are.
    `windowed` maps a board whose fetch stopped at the posted-date window to that window in days (T78): its other
    rows count a miss only when their posted date puts them inside the window (with a day of margin); older and
    undated rows are left as they are, because the pages that would hold them were not read.
    Returns how many jobs were closed now."""
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    closed = 0
    with connect(db_path) as conn:
        for (ats, company), jobs in boards.items():
            with_id = [(now, j.ats, j.global_id) for j in jobs if j.global_id]
            without = [(now, canonical_hash(j.title, j.company, j.location)) for j in jobs if not j.global_id]
            # The extra global_id conditions repeat the partial unique index's WHERE clause, so SQLite can use it:
            # without them every update scanned the whole table (EXPLAIN QUERY PLAN: SCAN jobs; >5 min on 39k jobs).
            conn.executemany("UPDATE jobs SET last_seen = ?, missed_scans = 0, closed_at = NULL "
                             "WHERE ats = ? AND global_id = ? AND global_id IS NOT NULL AND global_id != '';", with_id)
            conn.executemany("UPDATE jobs SET last_seen = ?, missed_scans = 0, closed_at = NULL "
                             "WHERE canonical_hash = ? AND (global_id IS NULL OR global_id = '');", without)
            board = (ats, company)
            if board in (incomplete or set()):
                continue
            if board in (windowed or {}):
                missed = _unseen_inside_window(conn, ats, company, now, (windowed or {})[board])
                conn.executemany("UPDATE jobs SET missed_scans = missed_scans + 1 WHERE id = ?;", [(i,) for i in missed])
            else:
                conn.execute("UPDATE jobs SET missed_scans = missed_scans + 1 WHERE ats = ? AND company = ? "
                             "AND closed_at IS NULL AND (last_seen IS NULL OR last_seen < ?);", (ats, company, now))
            closed += conn.execute("UPDATE jobs SET closed_at = ? WHERE ats = ? AND company = ? AND closed_at IS NULL "
                                   "AND missed_scans >= ?;", (now, ats, company, closed_after)).rowcount
        conn.commit()
    return closed


def set_application_status(row_id: int, status: Optional[str], day: Optional[str],
                           db_path: str = DEFAULT_DB_PATH) -> None:
    """Record (or with None, clear) the application status and its date on one row (T38)."""
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute("UPDATE jobs SET application_status = ?, application_date = ? WHERE id = ?;",
                     (status, day, row_id))
        conn.commit()


def scored_jobs_since(cutoff_date: str, db_path: str = DEFAULT_DB_PATH) -> Optional[List[Dict[str, Any]]]:
    """Every job scored on or after `cutoff_date` (UTC, YYYY-MM-DD), best first (`export --days N`, T32). None when
    there is no database; a missing database is not created."""
    if not os.path.exists(db_path):
        return None
    init_db(db_path)
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status IN ('scored', 'notified') AND score IS NOT NULL "
            "AND substr(scored_at, 1, 10) >= ? ORDER BY score DESC, scored_at, id;", (cutoff_date,)).fetchall()
        return [dict(r) for r in rows]


def get_jobs_by_status(
    status: str, db_path: str = DEFAULT_DB_PATH
) -> List[Dict[str, Any]]:
    """Retrieve all jobs with a specific status."""
    init_db(db_path)
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE status = ? ORDER BY id DESC;", (status,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
