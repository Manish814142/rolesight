"""T38: `autopilot mark <#N|URL> applied|interview|rejected|offer` records where an application stands (no network)."""
import csv
import json
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

from job_hunt import main as cli
from job_hunt import tracker
from job_hunt.db import init_db, save_job, update_job_status
from job_hunt.models import JobPosting, job_key

DAY = date(2026, 10, 8)


def _job(i):
    return JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title=f"Backend Engineer {i}",
                      location="Bengaluru, India", is_remote=False, url=f"https://x.example/{i}",
                      description_text="Node.js", posted_at="2026-10-08")


@pytest.fixture
def scanned(tmp_path, monkeypatch):
    """A working directory after one scan: 3 scored jobs in data/jobs.db and state/last_scan.json, best first."""
    monkeypatch.chdir(tmp_path)
    init_db("data/jobs.db")
    jobs = [_job(i) for i in range(3)]
    for j, score in zip(jobs, (90, 80, 70)):
        save_job(j)
        update_job_status(job_key(j), "scored", score, "fine")
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "last_scan.json").write_text(json.dumps(
        [{"company": j.company, "title": j.title, "url": j.url, "score": s, "reason": "fine", "scan_date": "2026-10-08"}
         for j, s in zip(jobs, (90, 80, 70))]))
    (tmp_path / "state" / "job_history.json").write_text((tmp_path / "state" / "last_scan.json").read_text())
    return jobs


def _row(url):
    con = sqlite3.connect("data/jobs.db")
    con.row_factory = sqlite3.Row
    return dict(con.execute("SELECT * FROM jobs WHERE url = ?", (url,)).fetchone())


def test_mark_by_number_uses_the_same_job_as_draft(scanned):
    row = tracker.mark_job("#2", "applied", today=DAY)
    assert row["url"] == scanned[1].url
    stored = _row(scanned[1].url)
    assert (stored["application_status"], stored["application_date"]) == ("applied", "2026-10-08")
    assert (stored["status"], stored["score"]) == ("scored", 80)          # the scoring lifecycle is untouched
    assert _row(scanned[0].url)["application_status"] is None


def test_mark_by_url_and_a_later_status_replaces_the_earlier_one(scanned):
    tracker.mark_job(scanned[0].url, "applied", today=date(2026, 10, 8))
    tracker.mark_job(scanned[0].url, "interview", today=date(2026, 10, 15))
    stored = _row(scanned[0].url)
    assert (stored["application_status"], stored["application_date"]) == ("interview", "2026-10-15")


def test_none_clears_a_mistaken_mark(scanned):
    tracker.mark_job("1", "applied", today=DAY)
    tracker.mark_job("1", "none", today=DAY)
    stored = _row(scanned[0].url)
    assert stored["application_status"] is None and stored["application_date"] is None


@pytest.mark.parametrize("ref, status, message", [
    ("1", "aplied", "status must be one of"),
    ("https://not-scanned.example/9", "applied", "not in the database"),
    ("#7", "applied", "not in last scan"),
])
def test_bad_input_changes_nothing(scanned, ref, status, message):
    before = sqlite3.connect("data/jobs.db").execute("SELECT * FROM jobs ORDER BY id").fetchall()
    with pytest.raises((ValueError, LookupError)) as ei:
        tracker.mark_job(ref, status, today=DAY)
    assert message in str(ei.value)
    assert sqlite3.connect("data/jobs.db").execute("SELECT * FROM jobs ORDER BY id").fetchall() == before


def test_init_db_adds_the_application_columns_to_an_existing_database(tmp_path):
    db = str(tmp_path / "jobs.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, canonical_hash TEXT, url_hash TEXT, "
                "global_id TEXT, title TEXT, company TEXT, ats TEXT, url TEXT, score INTEGER DEFAULT NULL, "
                "score_reason TEXT DEFAULT NULL, status TEXT DEFAULT 'discovered', "
                "discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, scored_at TIMESTAMP DEFAULT NULL)")
    con.execute("INSERT INTO jobs (global_id, status, score) VALUES ('a', 'scored', 80)")
    con.commit()
    con.close()
    init_db(db)
    assert sqlite3.connect(db).execute(
        "SELECT score, application_status, application_date FROM jobs").fetchone() == (80, None, None)


def _cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["autopilot", *args])
    cli.main()


def test_cli_mark_then_export_shows_the_status(scanned, monkeypatch, capsys):
    """The done-when through the real CLI: the status is stored in the DB and shown by `export`. No config.json and
    no API keys are needed, like export."""
    monkeypatch.setattr(tracker, "_today", lambda: DAY)
    _cli(monkeypatch, "mark", "#1", "applied")
    assert "applied" in capsys.readouterr().out
    assert _row(scanned[0].url)["application_status"] == "applied"
    _cli(monkeypatch, "export", "--days", "7")
    (out,) = Path("output").glob("*.csv")
    rows = {r["Application URL"]: r for r in csv.DictReader(out.open(encoding="utf-8"))}
    assert rows[scanned[0].url]["Application"] == "applied 2026-10-08"
    assert rows[scanned[1].url]["Application"] == ""


def test_export_without_any_mark_keeps_its_columns(scanned, monkeypatch):
    _cli(monkeypatch, "export")
    (out,) = Path("output").glob("*.csv")
    assert "Application" not in next(csv.reader(out.open(encoding="utf-8")))


def test_export_without_a_database_still_works(scanned, monkeypatch):
    os.remove("data/jobs.db")
    _cli(monkeypatch, "export")
    assert list(Path("output").glob("*.csv"))
    assert not os.path.exists("data/jobs.db")       # export never creates the database


@pytest.mark.parametrize("args", [["mark"], ["mark", "1"], ["mark", "1", "hired"]])
def test_cli_mark_usage_errors_exit_non_zero(scanned, monkeypatch, args):
    with pytest.raises(SystemExit) as ei:
        _cli(monkeypatch, *args)
    assert ei.value.code not in (0, None)
