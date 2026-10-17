"""Unit tests for job_hunt/exporter.py incremental CSV generation."""
from __future__ import annotations

import csv
from pathlib import Path

from job_hunt.exporter import (
    EXPORT_FIELDS,
    export_jobs_to_csv,
    get_incremental_csv_path,
    job_to_export_row,
)


def test_job_to_export_row() -> None:
    job = {
        "company": "Acme Corp",
        "title": "Backend Engineer",
        "location": "Bengaluru, India",
        "url": "https://example.com/jobs/1",
        "score": 85,
        "stack": "Python, FastAPI",
        "region": "India",
        "reason": "Strong Python skills match",
        "worth_applying": True,
        "scan_date": "2026-10-03",
    }
    row = job_to_export_row(job)
    assert row["Company"] == "Acme Corp"
    assert row["Role"] == "Backend Engineer"
    assert row["Location"] == "Bengaluru, India"
    assert row["Application URL"] == "https://example.com/jobs/1"
    assert row["Score (%)"] == 85
    assert row["Stack"] == "Python, FastAPI"
    assert row["Worth Applying"] == "Yes"
    assert row["Scan Date"] == "2026-10-03"


def test_incremental_csv_path_naming(tmp_path: Path) -> None:
    base = "jobs_2026-10-03"

    p0 = get_incremental_csv_path(base, out_dir=tmp_path)
    assert p0 == tmp_path / f"{base}.csv"
    p0.touch()

    p1 = get_incremental_csv_path(base, out_dir=tmp_path)
    assert p1 == tmp_path / f"{base}_1.csv"
    p1.touch()

    p2 = get_incremental_csv_path(base, out_dir=tmp_path)
    assert p2 == tmp_path / f"{base}_2.csv"


def test_export_jobs_to_csv_no_overwrite(tmp_path: Path) -> None:
    jobs1 = [{"company": "Alpha", "title": "Dev 1", "url": "https://a.com", "score": 90}]
    jobs2 = [{"company": "Beta", "title": "Dev 2", "url": "https://b.com", "score": 80}]

    path1 = export_jobs_to_csv(jobs1, base_name="jobs_test", out_dir=tmp_path)
    assert path1.name == "jobs_test.csv"
    assert path1.exists()

    path2 = export_jobs_to_csv(jobs2, base_name="jobs_test", out_dir=tmp_path)
    assert path2.name == "jobs_test_1.csv"
    assert path2.exists()
    assert path1 != path2

    # Verify contents of path1 are intact
    with path1.open("r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 1
        assert reader[0]["Company"] == "Alpha"

    # Verify contents of path2
    with path2.open("r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 1
        assert reader[0]["Company"] == "Beta"
        assert list(reader[0].keys()) == EXPORT_FIELDS


def test_export_row_includes_posted_date():
    from job_hunt.exporter import job_to_export_row
    assert job_to_export_row({"posted_at": "2026-09-03T13:30:34-04:00"})["Posted"] == "2026-09-03"
    assert job_to_export_row({"posted_at": "Posted 5 Days Ago"})["Posted"] == "Posted 5 Days Ago"
    assert job_to_export_row({})["Posted"] == ""


# --- T36: no column is always empty ---------------------------------------------------

def _gemini_path_job(n: int) -> dict:
    """The dict run_scan builds for a Gemini-scored job: `stack` is "" and nothing sets `region`."""
    return {"company": f"Acme {n}", "ats": "greenhouse", "title": "Backend Engineer", "extracted_title": "Backend Engineer",
            "location": "Bengaluru, India", "location_remote": "Bengaluru, India", "url": f"https://x.co/{n}",
            "score": 80 + n, "reason": "fits", "stack": "", "worth_applying": True,
            "posted_at": "2026-10-06", "scan_date": "2026-10-06"}


def test_a_gemini_scan_csv_has_no_always_empty_column(tmp_path: Path) -> None:
    path = export_jobs_to_csv([_gemini_path_job(1), _gemini_path_job(2)], base_name="gemini", out_dir=tmp_path)
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    empty = [col for col in rows[0] if not any(r[col] != "" for r in rows)]
    assert empty == []
    assert "Stack" not in rows[0] and "Region" not in rows[0]


def test_stack_column_appears_when_a_scorer_provides_it(tmp_path: Path) -> None:
    """The non-Gemini scorer returns a stack per job; the column is written then (and only then)."""
    jobs = [{**_gemini_path_job(1), "stack": "Node.js, Postgres"}, _gemini_path_job(2)]
    path = export_jobs_to_csv(jobs, base_name="legacy", out_dir=tmp_path)
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["Stack"] for r in rows] == ["Node.js, Postgres", ""]


# --- T37: LinkedIn people-search link ---------------------------------------------------

def test_linkedin_people_search_url_is_percent_encoded() -> None:
    from job_hunt.exporter import linkedin_people_search_url

    assert linkedin_people_search_url("Acme") == (
        "https://www.linkedin.com/search/results/people/?keywords=Acme%20software%20engineer")
    # characters that would end or split the query string must not survive unencoded
    url = linkedin_people_search_url("Ben & Jerry's, Inc. #1?")
    query = url.split("keywords=", 1)[1]
    assert query == "Ben%20%26%20Jerry%27s%2C%20Inc.%20%231%3F%20software%20engineer"
    assert linkedin_people_search_url("") == "" and linkedin_people_search_url("   ") == ""


def test_csv_has_a_linkedin_link_column(tmp_path: Path) -> None:
    path = export_jobs_to_csv([_gemini_path_job(1)], base_name="li", out_dir=tmp_path)
    with path.open(encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    assert row["LinkedIn people"] == "https://www.linkedin.com/search/results/people/?keywords=Acme%201%20software%20engineer"
