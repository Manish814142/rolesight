"""T84: a scan applies `candidate.cities` (and, without it, accepts every Indian place) and logs which it used."""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from job_hunt import scanner
from job_hunt.db import get_jobs_by_status, init_db, update_job_status
from job_hunt.models import JobPosting, canonical_hash


def _job(n, location):
    return JobPosting(global_id=f"gh:acme:{n}", ats="greenhouse", company="Acme", title="Backend Engineer",
                      location=location, is_remote=False, url=f"https://boards.greenhouse.io/acme/{n}",
                      description_text="Node.js")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js and TypeScript backend engineer, 3 years.")
    init_db(str(tmp_path / "data" / "jobs.db"))
    return {"gemini_api_key": "k", "candidate": {"name": "T", "resume_path": "resume.md", "min_score": 60, "top_n": 5}}


def _scan(cfg, jobs):
    queued = []

    def fake_score(**kw):
        out = []
        for j in kw["jobs"]:
            queued.append(j.location)
            update_job_status(canonical_hash(j.title, j.company, j.location), "scored", 80, "fits")
            out.append({"score": 80, "reason": "fits", "status": "scored"})
        return out

    with patch("job_hunt.scanner.fetch_company_jobs", return_value=jobs), \
            patch("job_hunt.scanner.score_and_process_batch", side_effect=fake_score), \
            patch("job_hunt.scanner.score_and_process_job", side_effect=lambda **kw: queued.append(kw["job"].location) or
                  {"score": 80, "reason": "fits", "status": "scored", "details": {}}):
        scanner.run_scan(cfg, [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}])
    return queued


def test_without_cities_a_scan_queues_every_indian_place(env):
    queued = _scan(env, [_job(1, "Pune, India"), _job(2, "Coimbatore"), _job(3, "London")])
    assert sorted(queued) == ["Coimbatore", "Pune, India"]
    assert [j["location"] for j in get_jobs_by_status("skipped")] == ["London"]


def test_with_cities_a_scan_queues_only_those_and_skips_the_rest(env):
    env["candidate"]["cities"] = ["Pune"]
    queued = _scan(env, [_job(1, "Pune, India"), _job(2, "Coimbatore"), _job(3, "London")])
    assert queued == ["Pune, India"]
    assert sorted(j["location"] for j in get_jobs_by_status("skipped")) == ["Coimbatore", "London"]


def test_a_known_job_is_re_checked_when_the_cities_change(env):
    """'skipped' rows are re-run through the filter on every scan, so widening or narrowing takes effect at once."""
    env["candidate"]["cities"] = ["Pune"]
    _scan(env, [_job(2, "Coimbatore")])
    assert len(get_jobs_by_status("skipped")) == 1
    env["candidate"]["cities"] = []
    assert _scan(env, [_job(2, "Coimbatore")]) == ["Coimbatore"]


def test_check_filter_takes_cities():
    script = Path(__file__).resolve().parent.parent / "scripts" / "check_filter.py"

    def run(*args):
        return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, timeout=60).stdout.strip()
    assert run("Backend Engineer", "Hyderabad, India") == "KEPT"
    assert run("Backend Engineer", "Hyderabad, India", "--cities", "Pune, Mumbai").startswith("REJECTED")
    assert run("Backend Engineer", "Pune", "--cities", "Pune, Mumbai") == "KEPT"
