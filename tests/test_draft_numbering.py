"""T10: `draft N` must open the job numbered N in the digest (sorted by score)."""
import csv
from pathlib import Path

from job_hunt import drafter, scanner
from job_hunt.db import init_db, update_job_status
from job_hunt.models import JobPosting, job_key

SCORES = {"Backend Engineer A": 20, "Backend Engineer B": 75, "Backend Engineer C": 50}


def test_draft_numbers_follow_score_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db(str(tmp_path / "data" / "jobs.db"))
    jobs = [JobPosting(global_id=f"gh:x:{t}", ats="greenhouse", company="X", title=t,
                       location="Bengaluru, India", is_remote=False, url=f"https://x/{t[-1]}",
                       description_text="Node.js")
            for t in SCORES]  # scan order: A (20), B (75), C (50)
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: jobs)
    def fake_score(job, **kw):   # stores the score like the real scorer: `draft N` reads the database (T31)
        update_job_status(job_key(job), "scored", SCORES[job.title], "r")
        return {"score": SCORES[job.title], "reason": "r", "status": "scored"}

    monkeypatch.setattr(scanner, "score_and_process_job", fake_score)
    cfg = {"candidate": {"resume_path": "resume.md", "min_score": 40, "top_n": 5},
           "gemini_api_key": "k", "telegram": {}}

    scanner.run_scan(cfg, [{"name": "X", "ats": "greenhouse", "slug": "x"}])

    assert drafter._resolve_job("1")[0] == "https://x/B"  # highest score
    assert drafter._resolve_job("2")[0] == "https://x/C"
    assert drafter._resolve_job("3")[0] == "https://x/A"
    # The CSV (the primary interface) lists jobs in the same order, so row N = draft N.
    rows = list(csv.DictReader(next(Path("output/history").glob("jobs_*.csv")).open()))
    assert [r["Application URL"] for r in rows] == ["https://x/B", "https://x/C", "https://x/A"]
