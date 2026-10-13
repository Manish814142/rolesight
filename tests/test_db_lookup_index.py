"""T75: a lookup by global_id used to scan the whole jobs table (2.2 ms per call on 43,466 rows, a scan makes ~35,000 of them).

The partial unique index is on (ats, global_id) with a WHERE clause the plain `global_id = ?` does not imply, so SQLite
could not use it. The test runs the SQL the program really sends and asks SQLite for its plan.
"""
import sqlite3

import pytest

from job_hunt import db
from job_hunt.models import JobPosting, job_key


def _job(i):
    return JobPosting(global_id=f"greenhouse:acme:{i}", ats="greenhouse", company="Acme", title=f"Backend Engineer {i}",
                      location="Pune, India", is_remote=False, url=f"https://acme/{i}", posted_at="2026-10-10",
                      description_text="Node.js")


@pytest.fixture
def traced(tmp_path, monkeypatch):
    """A database of 300 jobs and a list that collects every statement sqlite3 runs (parameters filled in)."""
    path = str(tmp_path / "jobs.db")
    db.init_db(path)
    for i in range(300):
        db.save_job(_job(i), status="discovered", db_path=path)
    statements: list[str] = []
    real_connect = sqlite3.connect

    def connect(*args, **kwargs):
        con = real_connect(*args, **kwargs)
        con.set_trace_callback(statements.append)
        return con

    monkeypatch.setattr(db.sqlite3, "connect", connect)
    return path, statements


def _plans(path, statements):
    con = sqlite3.connect(path)
    plans = []
    for sql in statements:
        if "global_id" in sql and sql.lstrip().upper().startswith(("SELECT", "UPDATE")) and "jobs" in sql:
            plans.append((sql, " | ".join(row[3] for row in con.execute("EXPLAIN QUERY PLAN " + sql))))
    con.close()
    return plans


@pytest.mark.parametrize("call", [
    lambda path: db.get_job(job_key(_job(7)), db_path=path),
    lambda path: db.has_job(job_key(_job(7)), db_path=path),
    lambda path: db.update_job_status(job_key(_job(7)), "scored", 80, "r", db_path=path),
    lambda path: db.update_job_details(job_key(_job(7)), location="Pune", db_path=path),
], ids=["get_job", "has_job", "update_job_status", "update_job_details"])
def test_a_lookup_by_global_id_uses_an_index(traced, call):
    path, statements = traced
    statements.clear()
    call(path)
    plans = [(sql, plan) for sql, plan in _plans(path, statements) if "global_id = 'greenhouse:acme:7'" in sql]
    assert plans, f"no statement filtered on the global_id was seen: {statements}"
    for sql, plan in plans:
        assert "SCAN" not in plan and "INDEX" in plan, f"{sql[:80]!r} -> {plan}"


def test_the_lookups_still_return_the_same_rows(tmp_path):
    path = str(tmp_path / "jobs.db")
    db.init_db(path)
    for i in range(50):
        db.save_job(_job(i), status="discovered", db_path=path)
    assert db.get_job(job_key(_job(7)), db_path=path)["title"] == "Backend Engineer 7"
    assert db.has_job(job_key(_job(7)), db_path=path) and not db.has_job("greenhouse:acme:999", db_path=path)
    db.update_job_status(job_key(_job(7)), "scored", 80, "r", db_path=path)
    assert db.get_job(job_key(_job(7)), db_path=path)["score"] == 80
