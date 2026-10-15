"""T110: every age is counted in local days. A stored timestamp is UTC; between 00:00 and 05:30 IST its UTC date is the day before
India's, so a job first seen then, or a board checked then, was judged a day off (found by reviewing T109, 2026-10-15)."""
import time
from datetime import date, datetime, timezone

import pytest

from job_hunt import db, discovery, prefilter
from job_hunt.models import JobPosting

pytestmark = pytest.mark.skipif(not hasattr(time, "tzset"), reason="needs POSIX time.tzset")
MORNING_UTC = "2026-10-14T23:46:00+00:00"          # 05:16 IST on 2026-10-15, when T109 was found


@pytest.fixture
def india(monkeypatch):
    # The POSIX form needs no tz database: with "Asia/Kolkata" a slim container (none installed) silently falls back to UTC.
    monkeypatch.setenv("TZ", "IST-5:30")
    time.tzset()
    assert time.localtime(0).tm_gmtoff == 19800            # a wrong zone must not fail the tests below for the wrong reason
    yield
    monkeypatch.undo()
    time.tzset()


def test_a_utc_timestamp_is_read_as_the_local_day(india):
    assert prefilter.local_date_of(MORNING_UTC) == date(2026, 10, 15)
    assert prefilter.local_date_of("2026-10-14T12:00:00+00:00") == date(2026, 10, 14)
    assert prefilter.local_date_of("2026-10-14") == date(2026, 10, 14)          # a bare date is already a day
    assert prefilter.local_date_of("") is None and prefilter.local_date_of("Posted Today") is None


def test_discover_counts_a_boards_newest_posting_in_local_days(india):
    jobs = [JobPosting(global_id="x", ats="a", company="c", title="t", location="l", is_remote=False, url="u", posted_at="2026-10-08")]
    assert discovery.newest_age_days(jobs, now=datetime(2026, 10, 14, 23, 46, tzinfo=timezone.utc)) == 7


def test_the_window_miss_rule_dates_a_workday_relative_age_from_the_local_day_it_was_seen(india, tmp_path, monkeypatch):
    """"Posted 6 Days Ago" read at 05:16 IST is 6 days old that day, not 7: with UTC's day it looked older and lost its miss."""
    class LocalDate(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 15)
    monkeypatch.setattr(db, "date", LocalDate)
    path = str(tmp_path / "jobs.db")
    db.init_db(path)
    with db.connect(path) as conn:
        conn.execute("INSERT INTO jobs (global_id, ats, company, title, status, posted_at, first_seen, last_seen) "
                     "VALUES ('w:1', 'workday', 'Acme', 'Backend Engineer', 'skipped', 'Posted 6 Days Ago', ?, ?)",
                     (MORNING_UTC, MORNING_UTC))
        ids = db._unseen_inside_window(conn, "workday", "Acme", "2026-10-16T00:00:00+00:00", window_days=7)
    assert len(ids) == 1


def test_open_matches_keeps_a_workday_job_scored_after_midnight_for_its_whole_window(india, tmp_path, monkeypatch):
    """The path that happens: Workday says "Posted 1 Day Ago" at 05:16 IST on 10-15, the job is scored then (its scored_at is
    UTC's 10-14). On 10-21 it is 7 days old, inside the 7-day window; counted from UTC's day it was 8 and left the file early."""
    from job_hunt import scanner
    from job_hunt.db import connect, init_db

    class LocalDate(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 21)
    monkeypatch.setattr(scanner, "date", LocalDate)
    monkeypatch.chdir(tmp_path)
    init_db("data/jobs.db")
    with connect("data/jobs.db") as conn:
        conn.execute("INSERT INTO jobs (global_id, ats, company, title, url, status, score, score_reason, posted_at, scored_at, "
                     "first_seen) VALUES ('w:2', 'workday', 'Acme', 'Backend Engineer', 'https://acme/2', 'scored', 80, 'fits', "
                     "'Posted 1 Day Ago', ?, ?)", (MORNING_UTC, MORNING_UTC))
    assert scanner._write_open_matches(70, 7) == 1
