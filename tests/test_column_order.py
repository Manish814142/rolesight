"""T128: the CSV columns are in reading order, Score first and Worth Applying last of the fixed ones.

Manish (2026-10-17), after opening the sample run: Score is the column he ranks and filters on, but it was the 8th, behind two
long URL columns. "Worth Applying at the end is okay." The order lives in one list, EXPORT_FIELDS; optional columns still follow it.
"""
import csv
from pathlib import Path

from job_hunt.exporter import EXPORT_FIELDS, export_jobs_to_csv

READING_ORDER = ["Score (%)", "Company", "ATS", "Role", "Location", "Posted", "Reason", "Application URL", "LinkedIn people",
                 "Worth Applying", "Scan Date"]


def _header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh))


def test_the_fixed_columns_are_in_reading_order():
    assert EXPORT_FIELDS == READING_ORDER


def test_the_file_has_that_order_and_the_optional_columns_follow(tmp_path):
    job = {"company": "A", "title": "Backend Engineer", "score": 80, "stack": "Node", "application": "applied 2026-10-01"}
    path = export_jobs_to_csv([job], base_name="x", out_dir=tmp_path)
    assert _header(path) == READING_ORDER + ["Stack", "Application"]


def test_the_score_is_the_first_cell_of_every_row(tmp_path):
    path = export_jobs_to_csv([{"company": "A", "title": "T", "score": 91}, {"company": "B", "title": "U", "score": 72}],
                              base_name="x", out_dir=tmp_path)
    with path.open(newline="", encoding="utf-8") as fh:
        assert [row[0] for row in csv.reader(fh)] == ["Score (%)", "91", "72"]
