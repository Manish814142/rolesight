"""Scanner pipeline (non-Gemini scoring path) — fetch + LLM mocked, filesystem in tmp_path."""
import json
import types

import pytest

from job_hunt import scanner
from job_hunt.models import JobPosting


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(scanner.time, "sleep", lambda *_: None)


# --- pure helpers --------------------------------------------------------------











def test_build_candidate_profile():
    cfg = {"candidate": {"name": "Ada", "profile": "ML eng", "seeking": "remote",
                         "not_suitable": "junior"}}
    out = scanner._build_candidate_profile(cfg)
    assert "- Ada" in out and "Seeking: remote" in out and "NOT suitable: junior" in out


def test_format_telegram_message():
    jobs = [{"company": "Acme", "title": "T", "extracted_title": "ML Eng", "location": "NY",
             "location_remote": "Remote", "stack": "Python", "reason": "fits", "url": "u"}]
    msg = scanner.format_telegram_message(jobs, "01 Jan 2026")
    assert "ML Eng" in msg and "Apply" in msg and "1 matches" in msg


# --- state ---------------------------------------------------------------------

def test_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert scanner.load_state() == {"seen_urls": []}
    scanner.save_state({"seen_urls": ["a", "b"]})
    assert scanner.load_state()["seen_urls"] == ["a", "b"]


# --- score_jobs ----------------------------------------------------------------

def test_score_jobs_empty():
    assert scanner.score_jobs([], "resume", {}) == []


def test_score_jobs_parses_and_filters(monkeypatch):
    jobs = [{"company": "Acme", "location": "Remote", "title": "MLE", "url": "u1"},
            {"company": "Beta", "location": "NY", "title": "SWE", "url": "u2"}]
    raw = json.dumps([
        {"job_number": 1, "score": 90, "title": "ML Engineer", "worth_applying": True,
         "stack": "Python", "reason": "great"},
        {"job_number": 2, "score": 20, "title": "Frontend", "worth_applying": False},
    ])
    monkeypatch.setattr(scanner, "chat_with_llm", lambda *a, **k: "noise " + raw + " tail")
    out = scanner.score_jobs(jobs, "resume", {"candidate": {"min_score": 55}})
    assert len(out) == 1 and out[0]["score"] == 90 and out[0]["extracted_title"] == "ML Engineer"


def test_score_jobs_no_json(monkeypatch):
    monkeypatch.setattr(scanner, "chat_with_llm", lambda *a, **k: "sorry no json")
    assert scanner.score_jobs([{"company": "A", "location": "L", "title": "T", "url": "u"}], "r", {}) == []


def test_score_jobs_llm_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(scanner, "chat_with_llm", boom)
    assert scanner.score_jobs([{"company": "A", "location": "L", "title": "T", "url": "u"}], "r", {}) == []


# --- export --------------------------------------------------------------------

def test_export_to_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jobs = [{"company": "Acme", "extracted_title": "MLE", "url": "u", "score": 88,
             "worth_applying": True, "scan_date": "2026-01-01"}]
    path = scanner._export_to_csv(jobs, "test")
    text = path.read_text()
    assert "Acme" in text and "MLE" in text and "Yes" in text


# --- run_scan integration ------------------------------------------------------

@pytest.fixture
def scan_setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "resume.md").write_text("Backend engineer, 3 YOE.")
    job = JobPosting(global_id="greenhouse:acme:1", ats="greenhouse", company="Acme", title="Backend Engineer",
                     location="Bengaluru, India", is_remote=False, url="https://x.co/jobs/1", description_text="Node")
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [job])
    monkeypatch.setattr(scanner, "score_jobs", lambda jobs, resume, cfg: [
        {**jobs[0], "score": 90, "extracted_title": "Backend Engineer", "reason": "fit", "stack": ""}])
    # llm_provider "anthropic" and no Gemini key: the non-Gemini scoring path
    cfg = {"llm_provider": "anthropic", "candidate": {"name": "Ada", "resume_path": "resume.md",
                                                      "min_score": 55, "top_n": 5}}
    companies = [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}]
    return cfg, companies


def test_run_scan_no_telegram_writes_csv(scan_setup, monkeypatch):
    sent = []
    monkeypatch.setattr(scanner, "send_telegram", lambda *a: sent.append(a))
    cfg, companies = scan_setup
    scanner.run_scan(cfg, companies)
    assert not sent  # no telegram configured
    assert json.loads(scanner.LAST_SCAN_FILE.read_text())[0]["score"] == 90
    from pathlib import Path
    assert list(Path("output").glob("jobs_*.csv"))


def test_run_scan_with_telegram(scan_setup, monkeypatch):
    sent = []
    monkeypatch.setattr(scanner, "send_telegram", lambda tok, chat, msg: sent.append(msg) or True)
    cfg, companies = scan_setup
    cfg["telegram"] = {"token": "t", "chat_id": "c"}
    scanner.run_scan(cfg, companies)
    assert sent and "matches" in sent[0]


def test_run_scan_scoring_failure_does_not_abort_the_scan(scan_setup, monkeypatch):
    """A scoring exception (non-Gemini provider) is logged; the scan finishes and the job stays 'discovered'."""
    def boom(*a, **k):
        raise RuntimeError("score boom")

    monkeypatch.setattr(scanner, "score_jobs", boom)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a: True)
    cfg, companies = scan_setup
    scanner.run_scan(cfg, companies)           # must not raise
    from job_hunt.db import get_jobs_by_status
    assert [j["title"] for j in get_jobs_by_status("discovered")] == ["Backend Engineer"]


def test_company_with_only_a_careers_url_is_scanned_when_its_ats_is_detected(scan_setup, monkeypatch):
    """fetch_company_jobs detects the ATS from a careers_url; run_scan must use those jobs (T42)."""
    monkeypatch.setattr(scanner, "send_telegram", lambda *a: True)
    cfg, _ = scan_setup
    scanner.run_scan(cfg, [{"name": "Acme", "careers_url": "https://boards.greenhouse.io/acme"}])
    from job_hunt.db import get_jobs_by_status
    assert len(get_jobs_by_status("discovered")) == 1


def test_company_with_no_supported_ats_is_skipped_not_fatal(scan_setup, monkeypatch):
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [])
    monkeypatch.setattr(scanner, "send_telegram", lambda *a: True)
    cfg, _ = scan_setup
    scanner.run_scan(cfg, [{"name": "Custom Portal Inc", "careers_url": "https://custom.example/careers"}])
