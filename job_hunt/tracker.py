"""Application tracker (T38): `autopilot mark <#N|URL> applied|interview|rejected|offer`.

Records where Manish's application for a job stands, with the local date it was marked, in `data/jobs.db`
(`application_status`, `application_date`). The job is found the same way `draft` finds it: `#N` / `N` is job N of
the last scan (CSV row N of that scan), a URL is looked up directly. `none` clears a mistaken mark. Nothing is ever
submitted anywhere: this only records what Manish did himself.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from typing import Any, Dict, List, Optional

from job_hunt.db import (
    DEFAULT_DB_PATH,
    get_application_statuses,
    get_job_by_url,
    set_application_status,
)
from job_hunt.drafter import _resolve_job

APPLICATION_STATUSES = ("applied", "interview", "rejected", "offer")
CLEAR = "none"
USAGE = "Usage: autopilot mark #N | URL applied|interview|rejected|offer   (none clears it)"


def _today() -> date:
    return date.today()


def mark_job(ref: str, status: str, db_path: str = DEFAULT_DB_PATH, today: Optional[date] = None) -> Dict[str, Any]:
    """Store `status` for the job `ref` names; returns the updated row. Raises ValueError / LookupError /
    FileNotFoundError (nothing written) when the status is unknown or the job cannot be found."""
    status = status.strip().lower()
    if status not in (*APPLICATION_STATUSES, CLEAR):
        raise ValueError(f"status must be one of {', '.join(APPLICATION_STATUSES)} (or {CLEAR} to clear), "
                         f"not {status!r}")
    url, _ = _resolve_job(ref)                      # the same #N / URL rule as `draft`
    if not os.path.exists(db_path):
        raise LookupError(f"No database at {db_path}: run a scan first")
    row = get_job_by_url(url, db_path)
    if row is None:
        raise LookupError(f"This job is not in the database: {url}")
    day = (today or _today()).isoformat()
    new_status, new_day = (None, None) if status == CLEAR else (status, day)
    set_application_status(row["id"], new_status, new_day, db_path)
    return {**row, "application_status": new_status, "application_date": new_day}


def application_labels(urls: List[str], db_path: str = DEFAULT_DB_PATH) -> Dict[str, str]:
    """{url: "applied 2026-10-08"} for the URLs that have an application status (read-only; for `export`)."""
    return {u: f"{a['status']} {a['date']}".strip() for u, a in get_application_statuses(urls, db_path).items()}


def main(argv: List[str]) -> None:
    if len(argv) != 2:
        sys.exit(USAGE)
    ref, status = argv
    try:
        row = mark_job(ref, status)
    except (ValueError, LookupError, FileNotFoundError) as e:
        sys.exit(f"mark: {e}")
    what = f"'{row.get('title')}' @ {row.get('company')}"
    if row["application_status"] is None:
        print(f"Cleared the application status of {what} ({row.get('url')})")
    else:
        print(f"Marked {what} as {row['application_status']} on {row['application_date']} ({row.get('url')})")
