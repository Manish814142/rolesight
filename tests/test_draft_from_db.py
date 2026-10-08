"""T31: `draft N` resolves job N of the last completed scan from data/jobs.db, not state/last_scan.json (no network)."""
import json
import sqlite3

import pytest

from job_hunt import db, drafter, scanner
from job_hunt.db import init_db, update_job_status
from job_hunt.models import JobPosting, job_key


def _job(t):
    return JobPosting(global_id=f"gh:x:{t}", ats="greenhouse", company="Acme Co", title=f"Backend Engineer {t}",
                      location="Bengaluru, India", is_remote=False, url=f"https://x/{t}", description_text="Node.js")


@pytest.fixture
def scan(tmp_path, monkeypatch):
    """Run the real run_scan on `jobs` with fixed scores; the fake scorer stores the score like the real one does."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db(str(tmp_path / "data" / "jobs.db"))

    def run(scores):
        jobs = [_job(t) for t in scores]
        monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: jobs)

        def fake_score(job, **kw):
            s = scores[job.title.split()[-1]]
            update_job_status(job_key(job), "scored", s, "r")
            return {"score": s, "reason": "r", "status": "scored"}

        monkeypatch.setattr(scanner, "score_and_process_job", fake_score)
        scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 40, "top_n": 5},
                          "gemini_api_key": "k", "telegram": {}}, [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    return run


def test_draft_numbers_come_from_the_database_not_last_scan_json(scan, tmp_path):
    scan({"A": 20, "B": 75, "C": 50})
    # last_scan.json is not read any more: delete it, or fill it with other jobs, and N still means the same job
    (tmp_path / "state" / "last_scan.json").write_text(json.dumps([{"url": "https://wrong/1", "company": "W"}] * 3))
    assert [drafter._resolve_job(n)[0] for n in ("1", "#2", "3")] == ["https://x/B", "https://x/C", "https://x/A"]
    (tmp_path / "state" / "last_scan.json").unlink()
    assert drafter._resolve_job("#1") == ("https://x/B", "acme_co")
    assert not hasattr(drafter, "LAST_SCAN_FILE")


def test_draft_n_is_job_n_of_the_latest_completed_scan(scan):
    scan({"A": 20, "B": 75})
    scan({"A": 20, "B": 75, "D": 60, "E": 85})          # A and B are already scored: only D and E are new
    assert drafter._resolve_job("1")[0] == "https://x/E" and drafter._resolve_job("2")[0] == "https://x/D"
    with pytest.raises(ValueError, match=r"not in last scan \(found 2 jobs\)"):
        drafter._resolve_job("3")


def test_a_scan_that_scored_nothing_leaves_nothing_to_draft(scan):
    scan({"A": 20})
    scan({"A": 20})                                      # nothing new: the last scan scored 0 jobs, as last_scan.json said
    with pytest.raises(ValueError, match=r"found 0 jobs"):
        drafter._resolve_job("1")


def test_equal_scores_keep_the_scoring_order_like_the_csv(scan):
    scan({"A": 70, "B": 70, "C": 90})
    assert [drafter._resolve_job(n)[0] for n in "123"] == ["https://x/C", "https://x/A", "https://x/B"]


def test_a_scan_that_did_not_finish_does_not_replace_the_last_completed_one(scan):
    scan({"A": 20, "B": 75})
    sid = db.start_scan()                                 # e.g. killed half-way: started, never finished
    save = _job("Z")
    db.save_job(save, status="discovered")
    update_job_status(job_key(save), "scored", 99, "r")
    assert sqlite3.connect("data/jobs.db").execute("SELECT finished_at FROM scans WHERE id = ?", (sid,)).fetchone() == (None,)
    assert drafter._resolve_job("1")[0] == "https://x/B"


def test_no_completed_scan_means_no_scan_results(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="Run: autopilot scan"):
        drafter._resolve_job("#1")                        # no database at all: none is created
    assert not (tmp_path / "data" / "jobs.db").exists()
    init_db("data/jobs.db")
    with pytest.raises(FileNotFoundError, match="Run: autopilot scan"):
        drafter._resolve_job("#1")                        # a database without any completed scan (e.g. before T31)


def test_a_url_is_used_as_given(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert drafter._resolve_job("https://acme.co/jobs/1") == ("https://acme.co/jobs/1", "company")
