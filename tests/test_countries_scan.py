"""T136: a scan with `candidate.countries` keeps the jobs in those countries, says so in the log, and `check-filter` takes them."""
import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from job_hunt import places, scanner
from job_hunt.db import get_jobs_by_status, init_db, update_job_status
from job_hunt.models import JobPosting, canonical_hash


def _job(n, location):
    return JobPosting(global_id=f"gh:acme:{n}", ats="greenhouse", company="Acme", title="Backend Engineer",
                      location=location, is_remote=False, url=f"https://boards.greenhouse.io/acme/{n}", description_text="Node.js")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js and TypeScript backend engineer, 3 years.")
    init_db(str(tmp_path / "data" / "jobs.db"))
    yield {"gemini_api_key": "k", "candidate": {"name": "T", "resume_path": "resume.md", "min_score": 60, "top_n": 5}}
    places.configure_places(places.INDIA)


def _scan(cfg, jobs):
    queued = []

    def fake_score(**kw):
        queued.append(kw["job"].location)
        update_job_status(canonical_hash(kw["job"].title, kw["job"].company, kw["job"].location), "scored", 80, "fits")
        return {"score": 80, "reason": "fits", "status": "scored", "details": {}}

    with patch("job_hunt.scanner.fetch_company_jobs", return_value=jobs), \
            patch("job_hunt.scanner.score_and_process_job", side_effect=fake_score):
        scanner.run_scan(cfg, [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}])
    return queued


def test_a_scan_for_singapore_queues_singapore_jobs_and_skips_india(env, caplog):
    env["candidate"]["countries"] = ["Singapore"]
    with caplog.at_level(logging.INFO, logger="job_hunt.scanner"):
        queued = _scan(env, [_job(1, "Singapore"), _job(2, "Pune, India"), _job(3, "Remote - APAC")])
    assert sorted(queued) == ["Remote - APAC", "Singapore"]
    assert [j["location"] for j in get_jobs_by_status("skipped")] == ["Pune, India"]
    log = caplog.text
    assert "Location filter: Singapore, the regions that include them" in log and "you live in India" in log
    assert "| In your places 2 |" in log


def test_an_india_scan_logs_and_counts_as_before(env, caplog):
    with caplog.at_level(logging.INFO, logger="job_hunt.scanner"):
        _scan(env, [_job(1, "Pune, India"), _job(2, "Singapore")])
    assert "Location filter: all of India, and remote jobs from India" in caplog.text
    assert "| India 1 |" in caplog.text and "In your places" not in caplog.text


def test_a_country_without_a_pack_is_warned_about_and_matched_by_name(env, caplog):
    env["candidate"]["countries"] = "Canada"
    with caplog.at_level(logging.INFO, logger="job_hunt.scanner"):
        queued = _scan(env, [_job(1, "Toronto, Canada"), _job(2, "Toronto")])
    assert queued == ["Toronto, Canada"]
    assert "'Canada' has no built-in place list" in caplog.text


def test_check_filter_takes_countries(tmp_path):
    script = Path(__file__).resolve().parent.parent / "scripts" / "check_filter.py"

    def run(*args):
        return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, timeout=60,
                              cwd=tmp_path).stdout.strip()
    assert run("Backend Engineer", "Dubai, United Arab Emirates", "--countries", "UAE, Singapore") == "KEPT"
    assert run("Backend Engineer", "Bengaluru, India", "--countries", "UAE").startswith(
        "REJECTED — Location 'Bengaluru, India' is not in your places (United Arab Emirates)")
    assert run("Backend Engineer", "Bengaluru, India") == "KEPT"                # no config.json here: India
    (tmp_path / "config.json").write_text('{"candidate": {"countries": ["Germany"]}}')
    assert run("Backend Engineer", "Berlin, Germany") == "KEPT"                 # config.json's countries
    assert run("Backend Engineer", "Berlin, Germany", "--countries", "India").startswith("REJECTED")
