"""T122: every CSV names the ATS a job is posted on, so a spreadsheet filter can pick the platform to apply on.

Manish (2026-10-17): "add the source of the ATS in the excel, so a person can filter by the ATS they want to apply on."
The value is the ATS id as companies.json and the database spell it (greenhouse, lever, workday, oracle_hcm, ...).
No network: adapters and scoring are stubbed, the CSV writers, `run_scan` and the SQLite rows are real.
"""
import csv
import sys
from pathlib import Path

import pytest

from job_hunt import main as cli
from job_hunt import scanner
from job_hunt.db import init_db, save_job, update_job_status
from job_hunt.exporter import EXPORT_FIELDS, export_jobs_to_csv, job_from_db_row, job_to_export_row
from job_hunt.models import JobPosting, job_key


def _read(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_a_row_carries_the_ats_as_stored():
    assert job_to_export_row({"company": "A", "ats": "oracle_hcm"})["ATS"] == "oracle_hcm"
    assert job_to_export_row({"company": "A"})["ATS"] == ""


def test_the_column_sits_next_to_the_company_in_every_csv(tmp_path):
    assert EXPORT_FIELDS[1:3] == ["Company", "ATS"]                      # Score comes first since T128
    path = export_jobs_to_csv([{"company": "A", "ats": "lever", "title": "Backend Engineer"}], base_name="x", out_dir=tmp_path)
    assert list(_read(path)[0])[1:3] == ["Company", "ATS"]


def test_a_database_row_keeps_its_ats_and_a_missing_one_is_blank():
    assert job_from_db_row({"company": "A", "ats": "workday", "score": 80}, 70)["ats"] == "workday"
    assert job_from_db_row({"company": "A", "ats": None, "score": 80}, 70)["ats"] == ""
    assert job_to_export_row(job_from_db_row({"company": "A", "ats": None, "score": 80}, 70))["ATS"] == ""


# --- the real scan -----------------------------------------------------------------------

def _posting(ats: str, n: int) -> JobPosting:
    return JobPosting(global_id=f"{ats}:x:{n}", ats=ats, company=f"{ats.title()} Co", title=f"Backend Engineer {n}",
                      location="Bengaluru, India", is_remote=False, url=f"https://{ats}.example/{n}", description_text="Node.js")


@pytest.fixture
def scan(tmp_path, monkeypatch):
    """A scan of three boards on three ATSs; every job scores 80. Returns the list of CSVs the scan wrote."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db("data/jobs.db")
    by_board = {"G": [_posting("greenhouse", 1), _posting("greenhouse", 2)], "L": [_posting("lever", 1)], "W": [_posting("workday", 1)]}
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: by_board[c["name"]])

    def fake_score(job, **kw):
        update_job_status(job_key(job), "scored", 80, "fits")
        return {"score": 80, "reason": "fits", "status": "scored"}

    monkeypatch.setattr(scanner, "score_and_process_job", fake_score)
    companies = [{"name": "G", "ats": "greenhouse", "slug": "g"}, {"name": "L", "ats": "lever", "slug": "l"},
                 {"name": "W", "ats": "workday", "tenant": "w", "dc": "wd1", "site": "s"}]
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k", "telegram": {}}, companies)
    return tmp_path


def test_the_scans_csv_names_each_jobs_ats_and_a_filter_on_it_finds_that_platform_only(scan):
    (out,) = Path("output/history").glob("jobs_*.csv")
    rows = _read(out)
    assert len(rows) == 4 and all(r["ATS"] for r in rows)                   # no blank cell
    assert {r["Application URL"] for r in rows if r["ATS"] == "greenhouse"} == {"https://greenhouse.example/1", "https://greenhouse.example/2"}
    assert [r["Application URL"] for r in rows if r["ATS"] == "lever"] == ["https://lever.example/1"]
    assert [r["Company"] for r in rows if r["ATS"] == "workday"] == ["Workday Co"]


def test_the_rolling_open_matches_file_has_it_too(scan):
    rows = _read(Path("output/open_matches.csv"))
    assert sorted((r["ATS"], r["Application URL"]) for r in rows) == [
        ("greenhouse", "https://greenhouse.example/1"), ("greenhouse", "https://greenhouse.example/2"),
        ("lever", "https://lever.example/1"), ("workday", "https://workday.example/1")]


def test_autopilot_export_has_it_too(scan, monkeypatch):
    before = set(Path("output/history").glob("*.csv"))
    monkeypatch.setattr(sys, "argv", ["autopilot", "export"])
    cli.main()
    (written,) = set(Path("output/history").glob("*.csv")) - before
    assert sorted(r["ATS"] for r in _read(written)) == ["greenhouse", "greenhouse", "lever", "workday"]


def test_a_row_stored_without_an_ats_exports_with_a_blank_cell_not_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("data/jobs.db")
    job = _posting("lever", 9)
    save_job(job, status="discovered")
    update_job_status(job_key(job), "scored", 75, "fits")
    import sqlite3
    con = sqlite3.connect("data/jobs.db")
    con.execute("UPDATE jobs SET ats = NULL")
    con.commit()
    con.close()
    from job_hunt.db import scored_jobs_since
    rows = scored_jobs_since("2000-01-01") or []
    (out,) = [export_jobs_to_csv([job_from_db_row(r, 70) for r in rows], base_name="blank", out_dir=tmp_path)]
    assert [r["ATS"] for r in _read(out)] == [""]


def test_the_deprecated_scorers_csv_has_it_too(tmp_path, monkeypatch):
    """The non-Gemini path (llm_provider anthropic or claude_cli) builds its job dicts apart from the Gemini path."""
    import json
    monkeypatch.chdir(tmp_path)
    (tmp_path / "resume.md").write_text("Backend engineer, 3 YOE.")
    monkeypatch.setattr(scanner.time, "sleep", lambda *_: None)
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [_posting("ashby", 1)])
    monkeypatch.setattr(scanner, "send_telegram", lambda *a: True)
    reply = json.dumps([{"job_number": 1, "score": 90, "title": "Backend Engineer", "worth_applying": True, "stack": "Node",
                         "location_remote": "Bengaluru", "reason": "fits"}])
    monkeypatch.setattr(scanner, "chat_with_llm", lambda config, messages, temperature=0.1, max_tokens=4096: reply)
    cfg = {"llm_provider": "anthropic", "candidate": {"name": "Ada", "resume_path": "resume.md", "min_score": 55, "top_n": 5}}
    scanner.run_scan(cfg, [{"name": "Ashby Co", "ats": "ashby", "slug": "ashby"}])
    (out,) = Path("output/history").glob("jobs_*.csv")
    assert [r["ATS"] for r in _read(out)] == ["ashby"]
