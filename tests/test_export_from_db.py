"""T32: `autopilot export` reads data/jobs.db, not state/last_scan.json / job_history.json (no network)."""
import csv
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from job_hunt import main as cli
from job_hunt.db import finish_scan, init_db, save_job, start_scan, update_job_status
from job_hunt.models import JobPosting, job_key

# EQUIVALENT_SQL is the done-when's reference: what `export --min 70 --days 7` must list, in this order.
EQUIVALENT_SQL = ("SELECT url FROM jobs WHERE status IN ('scored', 'notified') AND score >= 70 "
                  "AND substr(scored_at, 1, 10) >= date('now', '-7 days') ORDER BY score DESC, scored_at, id")


def _job(i, **kw):
    return JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company=f"C{i}", title=f"Backend Engineer {i}",
                      location=kw.get("location", "Bengaluru, India"), is_remote=False, url=f"https://x.example/{i}",
                      description_text="Node.js", posted_at=kw.get("posted_at", "2026-10-07"))


def _ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


@pytest.fixture
def history(tmp_path, monkeypatch):
    """Jobs scored over two weeks with every status; scored_at is set directly so the dates are known."""
    monkeypatch.chdir(tmp_path)
    init_db("data/jobs.db")
    rows = [  # i, status, score, days ago
        (0, "scored", 90, 0), (1, "notified", 85, 2), (2, "scored", 70, 6), (3, "scored", 69, 1),
        (4, "scored", 95, 9), (5, "skipped", None, 0), (6, "discovered", None, 1), (7, "scored", 75, 3),
    ]
    for i, status, score, ago in rows:
        save_job(_job(i), status="discovered")
        if score is not None:
            update_job_status(job_key(_job(i)), status, score, f"reason {i}", model="gemini-3.5-flash-lite")
    con = sqlite3.connect("data/jobs.db")
    for i, status, score, ago in rows:
        if score is not None:
            con.execute("UPDATE jobs SET scored_at = ? WHERE global_id = ?", (_ago(ago), f"greenhouse:x:{i}"))
        else:
            con.execute("UPDATE jobs SET status = ? WHERE global_id = ?", (status, f"greenhouse:x:{i}"))
    con.commit()
    con.close()
    # The old JSON state disagrees with the database on purpose: export must not read it.
    (tmp_path / "state").mkdir()
    bogus = [{"company": "Wrong", "title": "Wrong", "url": "https://wrong/1", "score": 99, "scan_date": "2099-01-01"}]
    (tmp_path / "state" / "last_scan.json").write_text(json.dumps(bogus))
    (tmp_path / "state" / "job_history.json").write_text(json.dumps(bogus))
    return tmp_path


def _export(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["autopilot", "export", *args])
    cli.main()
    newest = max(Path("output").glob("*.csv"), key=lambda p: p.stat().st_mtime_ns)
    return list(csv.DictReader(newest.open(encoding="utf-8")))


def test_export_min_70_days_7_matches_the_equivalent_sql_query(history, monkeypatch):
    """The done-when."""
    expected = [r[0] for r in sqlite3.connect("data/jobs.db").execute(EQUIVALENT_SQL)]
    assert expected == ["https://x.example/0", "https://x.example/1", "https://x.example/7", "https://x.example/2"]
    rows = _export(monkeypatch, "--min", "70", "--days", "7")
    assert [r["Application URL"] for r in rows] == expected
    first = rows[0]
    assert (first["Company"], first["Role"], first["Location"], first["Posted"], first["Score (%)"], first["Reason"]) == \
        ("C0", "Backend Engineer 0", "Bengaluru, India", "2026-10-07", "90", "reason 0")
    assert first["Scan Date"] == _ago(0)[:10]


def test_export_without_days_lists_the_last_finished_scan(history, monkeypatch):
    sid = start_scan()
    for i, score in ((10, 60), (11, 80)):
        save_job(_job(i))
        update_job_status(job_key(_job(i)), "scored", score, "r")
    finish_scan(sid)
    rows = _export(monkeypatch)
    assert [r["Application URL"] for r in rows] == ["https://x.example/11", "https://x.example/10"]


def test_worth_applying_uses_the_scans_min_score_when_there_is_a_config(history, monkeypatch):
    rows = {r["Application URL"]: r["Worth Applying"] for r in _export(monkeypatch, "--days", "7")}
    assert set(rows.values()) == {""}                    # no config.json: the threshold is unknown, left blank
    Path("config.json").write_text(json.dumps({"candidate": {"min_score": 70}}))
    monkeypatch.delenv("MIN_SCORE", raising=False)
    rows = {r["Application URL"]: r["Worth Applying"] for r in _export(monkeypatch, "--days", "7")}
    assert rows["https://x.example/2"] == "Yes" and rows["https://x.example/3"] == "No"


def test_export_without_a_database_says_so_and_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for args, message in (([], "No scan found"), (["--days", "7"], "No history yet")):
        monkeypatch.setattr(sys, "argv", ["autopilot", "export", *args])
        with pytest.raises(SystemExit) as ei:
            cli.main()
        assert message in str(ei.value)
    assert not (tmp_path / "data").exists()


def test_the_model_and_application_columns_come_from_the_database(history, monkeypatch):
    con = sqlite3.connect("data/jobs.db")
    con.execute("UPDATE jobs SET score_model = 'gemini-3.1-flash-lite', application_status = 'applied', "
                "application_date = '2026-10-08' WHERE global_id = 'greenhouse:x:1'")
    con.commit()
    con.close()
    rows = {r["Application URL"]: r for r in _export(monkeypatch, "--days", "7")}
    assert rows["https://x.example/1"]["Model"] == "gemini-3.1-flash-lite"
    assert rows["https://x.example/1"]["Application"] == "applied 2026-10-08"
    assert rows["https://x.example/0"]["Model"] == "gemini-3.5-flash-lite" and rows["https://x.example/0"]["Application"] == ""
