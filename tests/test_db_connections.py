"""T90: every SQLite connection the code opens is closed.

`with sqlite3.connect(path) as conn:` commits or rolls back at the end of the block but does not close the connection, so it lived until
garbage collection, and `init_db` returned an open one nobody used. Python 3.13 reports each as `ResourceWarning: unclosed database`
(13,859 of them in one CI-style run).
"""
import re
import sqlite3
from pathlib import Path

import pytest

from job_hunt import db
from job_hunt.models import JobPosting

REAL_CONNECT = sqlite3.connect


class _Tracked(sqlite3.Connection):
    opened: list = []

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.was_closed = False
        _Tracked.opened.append(self)

    def close(self):
        self.was_closed = True
        super().close()


@pytest.fixture
def tracked(monkeypatch):
    _Tracked.opened = []
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: REAL_CONNECT(*a, factory=_Tracked, **k))
    return _Tracked


def _job(n=1):
    return JobPosting(f"g{n}", "greenhouse", "Acme", f"Backend Engineer {n}", "Bengaluru, India", False, f"https://x/{n}")


def test_every_public_db_function_closes_what_it_opens(tmp_path, tracked):
    path = str(tmp_path / "data" / "jobs.db")
    job = _job()
    steps = [
        ("init_db", lambda: db.init_db(path)),
        ("save_job", lambda: db.save_job(job, db_path=path)),
        ("has_job", lambda: db.has_job(job.global_id, db_path=path)),
        ("get_job", lambda: db.get_job(job.global_id, db_path=path)),
        ("get_job_by_url", lambda: db.get_job_by_url(job.url, db_path=path)),
        ("update_job_details", lambda: db.update_job_details(job.global_id, location="Pune", db_path=path)),
        ("update_job_status", lambda: db.update_job_status(job.global_id, "scored", 80, "fits", db_path=path)),
        ("start_scan", lambda: db.start_scan(db_path=path)),
        ("finish_scan", lambda: db.finish_scan(1, db_path=path)),
        ("last_scan_jobs", lambda: db.last_scan_jobs(db_path=path)),
        ("open_match_rows", lambda: db.open_match_rows(70, db_path=path)),
        ("record_sightings", lambda: db.record_sightings({("greenhouse", "Acme"): [job]}, db_path=path)),
        ("set_application_status", lambda: db.set_application_status(1, "applied", "2026-10-13", db_path=path)),
        ("scored_jobs_since", lambda: db.scored_jobs_since("2026-01-01", db_path=path)),
        ("get_jobs_by_status", lambda: db.get_jobs_by_status("scored", db_path=path)),
    ]
    for name, call in steps:
        call()
        leaked = [c for c in tracked.opened if not c.was_closed]
        assert not leaked, f"{name} left {len(leaked)} connection(s) open"
    assert len(tracked.opened) >= len(steps), "the tracker saw the connections"


def test_doctors_sqlite_probe_closes_its_connection(tmp_path, tracked):
    from job_hunt.doctor import check_sqlite_write
    ok, _ = check_sqlite_write(str(tmp_path / "data" / "jobs.db"))
    assert ok and tracked.opened and all(c.was_closed for c in tracked.opened)


def test_connect_commits_on_success_and_closes(tmp_path, tracked):
    path = str(tmp_path / "t.db")
    with db.connect(path) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
    assert tracked.opened[-1].was_closed
    check = REAL_CONNECT(path)
    assert check.execute("SELECT x FROM t").fetchall() == [(1,)], "committed"
    check.close()


def test_connect_rolls_back_on_error_and_closes(tmp_path, tracked):
    path = str(tmp_path / "t.db")
    setup = REAL_CONNECT(path)
    setup.execute("CREATE TABLE t (x INTEGER)")
    setup.commit()
    setup.close()
    with pytest.raises(RuntimeError):
        with db.connect(path) as conn:
            conn.execute("INSERT INTO t VALUES (1)")
            raise RuntimeError("boom")
    assert tracked.opened[-1].was_closed
    check = REAL_CONNECT(path)
    assert check.execute("SELECT COUNT(*) FROM t").fetchone() == (0,), "rolled back"
    check.close()


def test_no_source_file_uses_the_with_connect_idiom_that_does_not_close():
    root = Path(__file__).resolve().parent.parent / "job_hunt"
    offenders = [str(f.relative_to(root)) for f in root.rglob("*.py")
                 if re.search(r"^\s*with sqlite3\.connect\(", f.read_text(), re.M)]
    assert not offenders, offenders
