"""T34: the JSON state files are retired; data/jobs.db is the one source of truth (no network)."""
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from job_hunt import scanner, tools
from job_hunt.db import connect, init_db, save_job, update_job_status
from job_hunt.models import JobPosting, job_key

ROOT = Path(__file__).resolve().parents[1]
RETIRED = re.compile(r"last_scan\.json|job_history\.json|seen_jobs\.json")


def test_no_module_names_the_retired_state_files():
    """The done-when: `grep -rn "last_scan.json\\|job_history.json\\|seen_jobs.json" job_hunt` returns nothing."""
    hits = [f"{p.relative_to(ROOT)}:{n}" for p in (ROOT / "job_hunt").rglob("*.py")
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if RETIRED.search(line)]
    assert hits == []


def _job(i):
    return JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title=f"Backend Engineer {i}",
                      location="Bengaluru, India", is_remote=False, url=f"https://x/{i}", description_text="Node.js")


def test_a_scan_writes_no_json_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js")
    init_db("data/jobs.db")
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [_job(0), _job(1)])

    def fake_score(job, **kw):
        update_job_status(job_key(job), "scored", 70, "r")
        return {"score": 70, "reason": "r", "status": "scored"}

    monkeypatch.setattr(scanner, "score_and_process_job", fake_score)
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k",
                      "telegram": {}}, [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    assert not (tmp_path / "state").exists()
    assert list((tmp_path / "output").glob("jobs_*.csv"))           # the CSV is still written


def test_tool_scan_reports_the_last_scan_from_the_database(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "load_config", lambda: {})
    monkeypatch.setattr(tools, "load_companies", lambda: [])

    def fake_run(cfg, companies):
        from job_hunt.db import finish_scan, start_scan
        init_db("data/jobs.db")
        sid = start_scan()
        for i, score in enumerate((9, 0, 40)):
            save_job(_job(i))
            update_job_status(job_key(_job(i)), "scored", score, "r")
        finish_scan(sid)

    monkeypatch.setattr(tools, "run_scan", fake_run)
    assert "3 jobs found, 2 scored" in tools.tool_scan(config_path=str(tmp_path / "config.json"))


# --- scripts/import_json_history.py: the one-time import of what only the JSON files hold --------------------

SCRIPT = ROOT / "scripts" / "import_json_history.py"


@pytest.fixture
def legacy_dir(tmp_path):
    """A working directory as left by the scanner before T34: data/jobs.db plus the JSON state files."""
    db = tmp_path / "data" / "jobs.db"
    init_db(str(db))
    a, b = _job("a"), _job("b")
    save_job(a, db_path=str(db))
    update_job_status(job_key(a), "scored", 50, "db reason", db_path=str(db))      # scored again after a DB reset
    save_job(b, status="skipped", db_path=str(db))                                 # known, but not scored
    state = tmp_path / "state"
    state.mkdir()

    def entry(u, s):
        return {"company": "X", "title": f"T {u}", "location": "Pune, India", "url": u, "score": s,
                "reason": f"json reason {u}", "posted_at": "2026-10-01", "scan_date": "2026-10-04"}

    (state / "job_history.json").write_text(json.dumps(
        [entry("https://x/a", 80), entry("https://x/b", 70), entry("https://x/c", 90), entry("https://x/d", 30)]))
    # e and f: two openings with the same title, company and location (different URLs) must both be imported
    (state / "last_scan.json").write_text(json.dumps([entry("https://x/c", 90), entry("https://x/e", 75),
                                                      {**entry("https://x/f", 72), "title": "T https://x/e"}]))
    return tmp_path


def _run(d, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--dir", str(d), *args], capture_output=True, text=True,
                          check=True).stdout


def _rows(d):
    with connect(d / "data" / "jobs.db") as con:
        return {u: (st, sc, r, at) for u, st, sc, r, at in
                con.execute("SELECT url, status, score, score_reason, scored_at FROM jobs")}


def test_import_is_a_dry_run_by_default(legacy_dir):
    before = _rows(legacy_dir)
    out = _run(legacy_dir)
    assert "would import 4" in out and "dry run" in out
    assert _rows(legacy_dir) == before


def test_import_adds_only_jobs_the_database_does_not_have(legacy_dir):
    out = _run(legacy_dir, "--apply")
    assert "imported 4" in out
    rows = _rows(legacy_dir)
    assert rows["https://x/a"][:3] == ("scored", 50, "db reason")          # the database's own score wins
    assert rows["https://x/b"][:2] == ("skipped", None)                     # a known row is never touched
    assert rows["https://x/c"] == ("scored", 90, "json reason https://x/c", "2026-10-04T00:00:00+00:00")
    assert rows["https://x/d"][:2] == ("scored", 30) and rows["https://x/e"][:2] == ("scored", 75)
    assert rows["https://x/f"][:2] == ("scored", 72)
    assert "imported 0" in _run(legacy_dir, "--apply")                      # running it again changes nothing
    assert len(_rows(legacy_dir)) == 6


def test_imported_jobs_show_up_in_export_days(legacy_dir, monkeypatch):
    from job_hunt import main as cli
    _run(legacy_dir, "--apply")
    monkeypatch.chdir(legacy_dir)
    con = sqlite3.connect("data/jobs.db")
    con.execute("UPDATE jobs SET scored_at = datetime('now') WHERE score_reason LIKE 'json reason%'")
    con.commit()
    con.close()
    monkeypatch.setattr(sys, "argv", ["autopilot", "export", "--days", "1", "--min", "70"])
    cli.main()
    (csv_path,) = Path("output").glob("*.csv")
    assert "https://x/c" in csv_path.read_text() and "https://x/e" in csv_path.read_text()
