"""T110, added in review: the paths test_local_dates.py leaves open. None of these needs a time zone, so none is skipped.

Found by putting the old lines back (mutants): `discovery.newest_age_days(jobs)` is called with no `now` by both of its callers,
and only the `now=` form was tested; and a row with no usable timestamp must still count as seen today, as it did before T110.
"""
from datetime import date, datetime, timedelta, timezone

from job_hunt import db, discovery, scanner
from job_hunt.models import JobPosting


def test_discover_reads_todays_date_in_local_days_when_it_is_given_no_clock(monkeypatch):
    """The path `discover` takes. The local date is set a day after UTC's, as it is between 00:00 and 05:30 in India, so a
    UTC "today" fails this at any hour (the clock-driven form of the same bug was T109)."""
    local_today = datetime.now(timezone.utc).date() + timedelta(days=1)

    class LocalDate(date):
        @classmethod
        def today(cls):
            return local_today
    monkeypatch.setattr(discovery, "date", LocalDate)
    posted = (local_today - timedelta(days=7)).isoformat()
    jobs = [JobPosting(global_id="x", ats="a", company="c", title="t", location="l", is_remote=False, url="u", posted_at=posted)]
    assert discovery.newest_age_days(jobs) == 7


def test_the_window_miss_rule_counts_a_row_with_no_usable_first_seen_as_seen_today(tmp_path):
    path = str(tmp_path / "jobs.db")
    db.init_db(path)
    with db.connect(path) as conn:
        for n, first_seen in enumerate(["", "not a time"]):
            conn.execute("INSERT INTO jobs (global_id, ats, company, title, status, posted_at, first_seen, last_seen) "
                         "VALUES (?, 'workday', 'Acme', 'Backend Engineer', 'skipped', 'Posted 6 Days Ago', ?, '2000-01-01T00:00:00+00:00')",
                         (f"w:{n}", first_seen))
        ids = db._unseen_inside_window(conn, "workday", "Acme", "2999-01-01T00:00:00+00:00", window_days=7)
    assert len(ids) == 2                                   # 6 days old, inside the window less its day of margin


def test_open_matches_keeps_a_scored_row_with_no_usable_timestamp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db.init_db("data/jobs.db")
    with db.connect("data/jobs.db") as conn:
        conn.execute("INSERT INTO jobs (global_id, ats, company, title, url, status, score, score_reason, posted_at, scored_at, "
                     "discovered_at, first_seen) VALUES ('w:3', 'workday', 'Acme', 'Backend Engineer', 'https://acme/3', 'scored', 80, "
                     "'fits', 'Posted 2 Days Ago', 'garbage', '', '')")
    assert scanner._write_open_matches(70, 7, "all_open") == 1
