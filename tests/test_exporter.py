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
