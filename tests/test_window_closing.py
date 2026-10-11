"""T78: a board whose fetch stopped at the posted-date window still lets T33 close the jobs that are inside the window.

stop_at_window (T02) marks such a fetch incomplete, and record_sightings counts no misses on an incomplete board, so the
Oracle HCM / Eightfold / SmartRecruiters boards could never close a job. What the stop leaves unread is only OLD jobs;
a stored job that is inside the window would have been on the pages that were read, so not seeing it is a real miss.
Jobs outside the window, and jobs with no date, stay unknown. One day of margin covers lists that are only roughly
ordered by date.
"""
import logging
import sqlite3
from datetime import date, timedelta

import pytest

from job_hunt import db, scanner
from job_hunt.adapters import base
from job_hunt.db import init_db, record_sightings, save_job
from job_hunt.models import JobPosting

WINDOW = 7


def _ago(days):
    return (date.today() - timedelta(days=days)).isoformat()


def _job(name, posted_at, company="Qualcomm", ats="eightfold"):
    # "Staff …" titles never pass the pre-filter, so nothing is scored: only the sightings matter here.
    return JobPosting(global_id=f"{ats}:{company}:{name}", ats=ats, company=company, title=f"Staff Engineer {name}",
                      location="Bengaluru, India", is_remote=False, url=f"https://{company}/{name}", posted_at=posted_at)


def _row(job):
    con = sqlite3.connect("data/jobs.db")
    con.row_factory = sqlite3.Row
    r = con.execute("SELECT * FROM jobs WHERE global_id = ?", (job.global_id,)).fetchone()
    con.close()
    return dict(r)


@pytest.fixture
def scan(tmp_path, monkeypatch):
    """run(returned, reason): one real run_scan of a board that returns `returned` and says it stopped for `reason`."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js")
    init_db("data/jobs.db")

    def run(returned, reason=base.WINDOW_STOP_REASON, closed_after=1):
        def fetch(company):
            if reason:
                base.mark_incomplete(reason)
            return returned
        monkeypatch.setattr(scanner, "fetch_company_jobs", fetch)
        cfg = {"candidate": {"resume_path": "resume.md", "min_score": 60, "max_posted_age_days": WINDOW},
               "gemini_api_key": "k", "telegram": {}, "closed_after_missed_scans": closed_after}
        scanner.run_scan(cfg, [{"name": "Qualcomm", "ats": "eightfold", "host": "h", "domain": "d"}])
    return run


def _stored(*jobs):
    for j in jobs:
        save_job(j, status="skipped")


def test_the_reason_the_adapters_use_is_a_named_constant():
    assert base.WINDOW_STOP_REASON == "posted-date window"
    base.begin_fetch(7)
    assert base.stop_at_window([_ago(30)]) is True
    assert base.fetch_incomplete() == base.WINDOW_STOP_REASON


def test_a_stored_job_inside_the_window_that_the_stopped_fetch_did_not_return_is_closed(scan):
    gone, still = _job("gone", _ago(2)), _job("still", _ago(1))
    _stored(gone, still)
    scan([still])
    assert _row(gone)["closed_at"] and _row(gone)["missed_scans"] == 1
    assert _row(still)["closed_at"] is None and _row(still)["missed_scans"] == 0


def test_a_stored_job_outside_the_window_is_left_alone(scan):
    old, new = _job("old", _ago(40)), _job("new", _ago(1))
    _stored(old, new)
    scan([new])
    assert (_row(old)["missed_scans"], _row(old)["closed_at"]) == (0, None)


def test_a_stored_job_with_no_posted_date_is_left_alone(scan):
    undated, new = _job("undated", ""), _job("new", _ago(1))
    _stored(undated, new)
    scan([new])
    assert (_row(undated)["missed_scans"], _row(undated)["closed_at"]) == (0, None)


def test_the_last_day_of_the_window_gets_a_margin(scan):
    edge, inside, new = _job("edge", _ago(WINDOW)), _job("inside", _ago(WINDOW - 1)), _job("new", _ago(0))
    _stored(edge, inside, new)
    scan([new])
    assert _row(edge)["missed_scans"] == 0, "age == window is where a roughly ordered list may not reach: unknown"
    assert _row(inside)["missed_scans"] == 1


def test_any_other_early_stop_still_counts_no_misses(scan):
    gone, new = _job("gone", _ago(2)), _job("new", _ago(1))
    _stored(gone, new)
    scan([new], reason="page failed at offset 20")
    assert (_row(gone)["missed_scans"], _row(gone)["closed_at"]) == (0, None)


def test_a_job_that_is_really_gone_is_closed_after_the_usual_three_scans(scan):
    gone, new = _job("gone", _ago(2)), _job("new", _ago(1))
    _stored(gone, new)
    for n in (1, 2):
        scan([new], closed_after=3)
        assert (_row(gone)["missed_scans"], _row(gone)["closed_at"]) == (n, None)
    scan([new], closed_after=3)
    assert _row(gone)["closed_at"]
    scan([gone, new], closed_after=3)                       # it comes back: open again
    assert (_row(gone)["missed_scans"], _row(gone)["closed_at"]) == (0, None)


def test_the_scan_log_says_what_a_window_stop_counts(scan, caplog):
    _stored(_job("gone", _ago(2)))
    caplog.set_level(logging.INFO, logger="autopilot")
    scan([_job("new", _ago(1))])
    line = next(r.getMessage() for r in caplog.records if "Fetch stopped" in r.getMessage())
    assert "posted-date window" in line and "inside the window" in line


def test_record_sightings_windowed_boards_directly(tmp_path):
    path = str(tmp_path / "jobs.db")
    init_db(path)
    gone, old, undated, kept = _job("g", _ago(2)), _job("o", _ago(30)), _job("u", ""), _job("k", _ago(1))
    for j in (gone, old, undated, kept):
        save_job(j, db_path=path)
    closed = record_sightings({("eightfold", "Qualcomm"): [kept]}, closed_after=1, db_path=path,
                              windowed={("eightfold", "Qualcomm"): WINDOW})
    assert closed == 1
    rows = {r[0]: r[1:] for r in sqlite3.connect(path).execute("SELECT global_id, missed_scans, closed_at FROM jobs")}
    assert rows[gone.global_id][0] == 1 and rows[gone.global_id][1]
    assert rows[old.global_id] == (0, None) and rows[undated.global_id] == (0, None) and rows[kept.global_id] == (0, None)


def test_a_board_in_both_sets_counts_no_misses(tmp_path):
    """`incomplete` (a failed page, a cap) wins over `windowed`: the window stop is only trusted when it is the reason."""
    path = str(tmp_path / "jobs.db")
    init_db(path)
    gone, kept = _job("g", _ago(2)), _job("k", _ago(1))
    for j in (gone, kept):
        save_job(j, db_path=path)
    board = ("eightfold", "Qualcomm")
    record_sightings({board: [kept]}, closed_after=1, db_path=path, incomplete={board}, windowed={board: WINDOW})
    assert db.get_job(gone.global_id, db_path=path)["closed_at"] is None
