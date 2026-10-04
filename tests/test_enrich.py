"""Enrich step (T19): survivors get their full description before scoring."""
from datetime import date

import pytest

from job_hunt import adapters, scanner
from job_hunt.db import init_db, save_job, update_job_status
from job_hunt.models import JobPosting, canonical_hash


def _job(title, ats="workday", location="Bengaluru, India", posted_at="", desc=""):
    return JobPosting(global_id=f"{ats}:x:{title}", ats=ats, company="X", title=title,
                      location=location, is_remote=False, url=f"https://x/{title}",
                      description_text=desc, posted_at=posted_at)


def test_enrich_job_without_enricher_is_noop(monkeypatch):
    monkeypatch.setattr(adapters, "ENRICHERS", {})
    assert adapters.enrich_job(_job("A", desc="orig")).description_text == "orig"


def test_enrich_job_replaces_description(monkeypatch):
    monkeypatch.setattr(adapters, "ENRICHERS", {"workday": lambda job: "FULL JD"})
    assert adapters.enrich_job(_job("A", desc="")).description_text == "FULL JD"


def test_enrich_job_failure_or_empty_result_keeps_job(monkeypatch):
    def boom(job):
        raise RuntimeError("HTTP 500")
    monkeypatch.setattr(adapters, "ENRICHERS", {"workday": boom, "oracle_hcm": lambda job: ""})
    assert adapters.enrich_job(_job("A", desc="short")).description_text == "short"
    assert adapters.enrich_job(_job("B", ats="oracle_hcm", desc="short")).description_text == "short"


@pytest.fixture
def scan_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db(str(tmp_path / "data" / "jobs.db"))
    return {"candidate": {"resume_path": "resume.md", "min_score": 60, "max_posted_age_days": 7},
            "gemini_api_key": "k", "telegram": {}}


def test_run_scan_enriches_survivors_only_and_scores_enriched_text(scan_env, monkeypatch):
    today = date.today().isoformat()
    survivor = _job("Backend Engineer", posted_at=today)
    rejected = _job("Engineering Manager", posted_at=today)
    too_old = _job("Backend Developer", posted_at="2020-01-01")
    already = _job("Software Engineer", posted_at=today)
    save_job(already, status="discovered")
    update_job_status(canonical_hash(already.title, already.company, already.location), "scored", 80, "r")
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [survivor, rejected, too_old, already])

    enriched = []

    def fake_enrich(job):
        enriched.append(job.title)
        job.description_text = "FULL JD"
        return job

    monkeypatch.setattr(scanner, "enrich_job", fake_enrich)
    scored = []

    def fake_score(job, **kw):
        scored.append((job.title, job.description_text))
        return {"score": 50, "reason": "r", "status": "scored"}

    monkeypatch.setattr(scanner, "score_and_process_job", fake_score)

    scanner.run_scan(scan_env, [{"name": "X", "ats": "workday", "tenant": "x", "dc": "wd1", "site": "s"}])

    assert enriched == ["Backend Engineer"]
    assert scored == [("Backend Engineer", "FULL JD")]
