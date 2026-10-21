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


def test_a_uk_scan_writes_a_visa_column_and_an_india_scan_does_not(env, tmp_path):
    import csv
    env["candidate"]["countries"] = ["United Kingdom"]
    _scan(env, [_job(1, "London, UK")])
    rows = list(csv.DictReader(open(tmp_path / "output" / "last_scan.csv", encoding="utf-8")))
    assert rows[0]["Location"] == "London, UK" and rows[0]["Visa"] == "Not stated"     # Acme: no record; "Node.js" says nothing
    del env["candidate"]["countries"]
    places.configure_places(places.INDIA)
    _scan(env, [_job(2, "Pune, India")])
    assert "Visa" not in open(tmp_path / "output" / "last_scan.csv", encoding="utf-8").readline()


def test_init_countries_writes_the_built_in_names_and_keeps_the_rest(tmp_path, monkeypatch, capsys):
    import json

    from job_hunt.main import init_project
    from job_hunt.onboarding import parse_init_args
    assert parse_init_args(["--countries", "UK, Dubai"]) == {"countries": "UK, Dubai"}
    monkeypatch.chdir(tmp_path)
    init_project(**parse_init_args(["--countries", "uk, Dubai, Canada"]))
    cfg = json.loads((tmp_path / "config.json").read_text())
    assert cfg["candidate"]["countries"] == ["United Kingdom", "United Arab Emirates", "Canada"]
    assert cfg["candidate"]["home_country"] == "India" and cfg["llm_provider"] == "gemini"
    assert (tmp_path / "config.json").stat().st_mode & 0o777 == 0o600
    out = capsys.readouterr().out
    assert "looking in United Kingdom, United Arab Emirates, Canada" in out and "'Canada' has no built-in place list" in out
    assert cfg["candidate"]["seeking"] == ("Backend or platform roles in United Kingdom, United Arab Emirates or Canada. I live in "
                                           "India; for a role outside India I need the employer to sponsor my work visa and relocation")
    assert "Bengaluru" not in json.dumps(cfg["candidate"]["seeking"])


def test_init_countries_keeps_a_seeking_you_wrote(tmp_path, monkeypatch):
    import json

    from job_hunt.onboarding import set_countries
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"candidate": {"seeking": "Staff roles in Berlin"}}))
    set_countries(tmp_path, "Germany")
    cand = json.loads((tmp_path / "config.json").read_text())["candidate"]
    assert cand == {"seeking": "Staff roles in Berlin", "countries": ["Germany"]}


def test_the_example_configs_name_india_and_mean_what_no_setting_means():
    import json

    from job_hunt.places import places_from_config
    for f in ("config.example.json", "job_hunt/data/config.example.json"):
        cand = json.loads((Path(__file__).resolve().parent.parent / f).read_text())["candidate"]
        assert cand["countries"] == ["India"] and cand["home_country"] == "India"
        assert places_from_config({"candidate": cand}) == places_from_config({})


def test_init_resume_drafts_seeking_for_your_countries(tmp_path, monkeypatch):
    """T140: the draft prompt asks for a `seeking` in your countries, with the visa; India's prompt is unchanged."""
    import json

    from job_hunt import onboarding

    class Stop(Exception):
        pass
    prompts = []

    def fake_generate(key, models, parts, schema=None):
        prompts.append(parts[-1])
        raise Stop
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    (tmp_path / "cv.md").write_text("Backend engineer in Pune. " * 20)
    (tmp_path / "config.json").write_text(json.dumps({"candidate": {"countries": ["Singapore"]}}))
    with pytest.raises(Stop):
        onboarding.personalize(tmp_path, tmp_path / "cv.md", True, True, generate=fake_generate)
    assert "in Singapore (where they want to work" in prompts[0] and "need the employer to sponsor a work visa" in prompts[0]
    assert "anywhere in India or remote" not in prompts[0]
    assert onboarding._INDIA_SEEKING in onboarding._draft_prompt("cv", "2026-10-21")
