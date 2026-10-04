"""Enrich step (T19): survivors get their full description before scoring.

Per-ATS description fetchers: Workday (T20), SmartRecruiters (T21), Oracle HCM (T22).
"""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from job_hunt import adapters, scanner
from job_hunt.adapters import smartrecruiters, workday
from job_hunt.db import init_db, save_job, update_job_status
from job_hunt.models import JobPosting, canonical_hash


def _resp(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


# --- Workday (T20) ---------------------------------------------------------

WD_URL = "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/Noida/Software-Development-Engineer-2_R162019"


@patch("requests.get")
def test_workday_description_fetched_for_single_location_job(mock_get):
    mock_get.return_value = _resp({"jobPostingInfo": {
        "location": "Noida", "jobDescription": "<p>Build <b>Node.js</b> services</p>"}})
    job = JobPosting(global_id="workday:adobe:R162019", ats="workday", company="Adobe",
                     title="Software Development Engineer 2", location="Noida, India",
                     is_remote=False, url=WD_URL)

    desc = workday.fetch_description(job)

    assert mock_get.call_args.args[0] == (
        "https://adobe.wd5.myworkdayjobs.com/wday/cxs/adobe/external_experienced"
        "/job/Noida/Software-Development-Engineer-2_R162019")
    assert desc == "Build Node.js services"


@patch("requests.get")
def test_workday_job_that_already_has_a_description_is_not_refetched(mock_get):
    # "N Locations" items were resolved via the same detail call during the fetch.
    job = JobPosting(global_id="g", ats="workday", company="X", title="t", location="India",
                     is_remote=False, url=WD_URL, description_text="already here")
    assert workday.fetch_description(job) == ""
    mock_get.assert_not_called()


@patch("requests.get")
def test_workday_url_without_job_path_is_skipped(mock_get):
    job = JobPosting(global_id="g", ats="workday", company="X", title="t", location="India",
                     is_remote=False, url="https://adobe.wd5.myworkdayjobs.com/external")
    assert workday.fetch_description(job) == ""
    mock_get.assert_not_called()


def test_workday_enricher_is_registered():
    assert adapters.ENRICHERS["workday"] is workday.fetch_description


# --- SmartRecruiters (T21) -------------------------------------------------

def _sr_job():
    return JobPosting(global_id="smartrecruiters:BoschGroup:744000083912345", ats="smartrecruiters",
                      company="Bosch", title="Software Developer", location="Bengaluru, KA, in",
                      is_remote=False, url="https://jobs.smartrecruiters.com/BoschGroup/744000083912345")


@patch("requests.get")
def test_smartrecruiters_description_from_posting_detail(mock_get):
    # Shape of GET /v1/companies/{slug}/postings/{id}, probed live 2026-10-04.
    mock_get.return_value = _resp({"jobAd": {"sections": {
        "companyDescription": {"title": "Company Description", "text": "<p>Bosch is big.</p>"},
        "jobDescription": {"title": "Job Description", "text": "<ul><li>Build SAP ABAP reports</li></ul>"},
        "qualifications": {"title": "Qualifications", "text": "<p>5+ years SAP &amp; ABAP</p>"},
        "additionalInformation": {"title": "Additional Information", "text": ""},
    }}})

    desc = smartrecruiters.fetch_description(_sr_job())

    assert mock_get.call_args.args[0] == (
        "https://api.smartrecruiters.com/v1/companies/BoschGroup/postings/744000083912345")
    assert "Build SAP ABAP reports" in desc and "5+ years SAP & ABAP" in desc
    assert "<" not in desc
    # The role comes before the company blurb.
    assert desc.index("Build SAP ABAP") < desc.index("Bosch is big")


@patch("requests.get")
def test_smartrecruiters_detail_error_gives_empty(mock_get):
    mock_get.return_value = _resp({}, status=404)
    assert smartrecruiters.fetch_description(_sr_job()) == ""


def test_smartrecruiters_enricher_is_registered():
    assert adapters.ENRICHERS["smartrecruiters"] is smartrecruiters.fetch_description


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
