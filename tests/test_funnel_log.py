"""T35: one log line shows the whole funnel of a scan (no network)."""
import logging
from datetime import date, timedelta

from job_hunt import scanner
from job_hunt.db import init_db, save_job, update_job_status
from job_hunt.models import JobPosting, job_key


def _job(i, title="Backend Engineer", location="Bengaluru, India", posted=None):
    posted = posted if posted is not None else date.today().isoformat()
    return JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title=f"{title} {i}",
                      location=location, is_remote=False, url=f"https://x/{i}", description_text="Node.js", posted_at=posted)


def test_funnel_line_counts_every_stage(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js")
    init_db(str(tmp_path / "data" / "jobs.db"))
    old = _job(0)                                            # already scored on an earlier scan
    save_job(old, status="discovered")
    update_job_status(job_key(old), "scored", 80, "r")
    jobs = [
        old,
        _job(1), _job(2),                                    # pass; one scores, one fails
        _job(3, location="Austin, TX"),                      # not India
        _job(4, title="Staff Engineer", location="Pune, India"),   # India, rejected by the title
        _job(5, posted=(date.today() - timedelta(days=60)).isoformat()),   # India, passes, too old
        _job(6, location="Mumbai, India"),                   # passes the pre-filter too
    ]
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: jobs)
    results = {"Backend Engineer 1": {"score": 70, "reason": "r", "status": "scored"},
               "Backend Engineer 2": {"score": None, "reason": "failed", "status": "discovered"}}

    def fake_score(job, **kw):
        res = results.get(job.title, {"score": 65, "reason": "r", "status": "scored"})
        if res["score"] is not None:
            update_job_status(job_key(job), "scored", res["score"], "r")
        return res

    monkeypatch.setattr(scanner, "score_and_process_job", fake_score)
    caplog.set_level(logging.INFO, logger="autopilot")
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 60, "max_posted_age_days": 30},
                      "gemini_api_key": "k", "telegram": {}}, [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    line = next(r.getMessage() for r in caplog.records if "Funnel" in r.getMessage())
    # 7 fetched; 6 in India (not Austin); 1 already scored; 1 rejected by title; 1 too old; 3 queued (1, 2, 6); 2 scored; 1 failed
    for part in ("fetched 7", "India 6", "already scored 1", "pre-filter rejected 2", "too old 1",
                 "queued 3", "scored 2", "failed 1", "left for next scan 1"):
        assert part in line, (part, line)


def test_funnel_line_is_one_line(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js")
    init_db(str(tmp_path / "data" / "jobs.db"))
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [])
    caplog.set_level(logging.INFO, logger="autopilot")
    scanner.run_scan({"candidate": {"resume_path": "resume.md"}, "gemini_api_key": "k", "telegram": {}},
                     [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    lines = [r.getMessage() for r in caplog.records if "Funnel" in r.getMessage()]
    assert len(lines) == 1 and "\n" not in lines[0] and "fetched 0" in lines[0]
