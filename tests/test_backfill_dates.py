"""T99: a scored row with no posted date gets one from the scan that fetches the job again (no Gemini call).

Rows scored before T29 (the 145 of 2026-10-04) have no `posted_at`, and open_matches.csv keeps undated rows, so it listed
them whatever the posting's real age. Only the date and the location are filled in; never the score, the status, the
reason, the model, the rubric or the description (that column means "what the scorer saw").
"""
import csv
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from job_hunt import llm_utils, scanner
from job_hunt.db import connect, fill_missing_details, get_job, init_db, save_job, update_job_status
from job_hunt.models import JobPosting, job_key
from job_hunt.prefilter import posted_date_iso

TODAY = date.today()


def _iso(days_ago):
    return (TODAY - timedelta(days=days_ago)).isoformat()


def _job(posted_at="", location="", description="", i=1):
    return JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title=f"Backend Engineer {i}",
                      location=location, is_remote=False, url=f"https://x/{i}", description_text=description,
                      posted_at=posted_at)


def _scored(db, posted_at="", location="", rubric=None):
    """A row as the 2026-10-04 scan left it: scored, final, with no date and no location."""
    save_job(_job(posted_at, location), db_path=db)
    update_job_status(job_key(_job()), "scored", 82, "old reason", db_path=db, model="m-old", rubric=rubric)


def _scan(tmp_path, monkeypatch, fetched):
    """The real run_scan over one board; any Gemini call would hit the MagicMock, which the tests then check."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    client = MagicMock()
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [fetched])
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types", lambda api_key=None: (client, MagicMock()))
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 70}, "gemini_api_key": "k", "telegram": {},
                      "open_matches_scope": "all_open"},     # T124: these tests are about the rolling list of T39
                     [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    return client


def _open_matches_roles(tmp_path):
    with open(tmp_path / "output" / "open_matches.csv", newline="", encoding="utf-8") as fh:
        return [r["Role"] for r in csv.DictReader(fh)]


def test_a_scored_row_gets_its_date_and_location_and_nothing_else(tmp_path, monkeypatch):
    db = str(tmp_path / "data" / "jobs.db")
    init_db(db)
    _scored(db)
    client = _scan(tmp_path, monkeypatch, _job(_iso(2), "Pune, India", "A long description"))
    row = get_job(job_key(_job()), db_path=db)
    assert (row["posted_at"], row["location"]) == (_iso(2), "Pune, India")
    assert (row["status"], row["score"], row["score_reason"], row["score_model"]) == ("scored", 82, "old reason", "m-old")
    assert row["score_rubric"] is None and not row["description"]             # what the scorer saw stays unknown
    assert client.models.generate_content.call_count == 0                     # no Gemini call
    assert _open_matches_roles(tmp_path) == ["Backend Engineer 1"]            # inside the window: still listed


def test_a_row_whose_posting_is_older_than_the_window_leaves_open_matches(tmp_path, monkeypatch):
    """The point of T99: before, the undated row stayed in the file whatever the posting's real age."""
    db = str(tmp_path / "data" / "jobs.db")
    init_db(db)
    _scored(db)
    _scan(tmp_path, monkeypatch, _job(_iso(20), "Pune, India"))
    assert get_job(job_key(_job()), db_path=db)["posted_at"] == _iso(20)
    assert _open_matches_roles(tmp_path) == []
    assert get_job(job_key(_job()), db_path=db)["status"] == "scored"         # still final: only the list changed


@pytest.mark.parametrize("posted, days", [("Posted 3 Days Ago", 3), ("Posted 30+ Days Ago", 30), ("Posted Today", 0),
                                          ("Posted Yesterday", 1)])
def test_workdays_relative_dates_are_stored_as_the_date_they_mean(tmp_path, monkeypatch, posted, days):
    """`current_age_days` adds the days since the row was *scored* to a relative text, so storing "Posted 3 Days Ago" for a
    row scored ten days ago would age it by thirteen."""
    db = str(tmp_path / "data" / "jobs.db")
    init_db(db)
    _scored(db)
    _scan(tmp_path, monkeypatch, _job(posted, "Pune, India"))
    assert get_job(job_key(_job()), db_path=db)["posted_at"] == _iso(days)


def test_a_date_the_row_already_has_is_not_overwritten(tmp_path, monkeypatch):
    db = str(tmp_path / "data" / "jobs.db")
    init_db(db)
    _scored(db, posted_at=_iso(5), location="Mumbai, India")
    _scan(tmp_path, monkeypatch, _job(_iso(1), "Pune, India"))
    row = get_job(job_key(_job()), db_path=db)
    assert (row["posted_at"], row["location"]) == (_iso(5), "Mumbai, India")


def test_a_row_scored_long_ago_whose_posting_is_recent_stays_in_open_matches(tmp_path, monkeypatch):
    """The 2026-10-04 rows were scored ten days ago; a date read today can be later than that (an ATS that bumps
    `updated_at`). Its age is today minus that date, not the days since the row was scored."""
    db = str(tmp_path / "data" / "jobs.db")
    init_db(db)
    _scored(db)
    with connect(db) as con:
        con.execute("UPDATE jobs SET scored_at = ?", ((TODAY - timedelta(days=10)).isoformat() + "T08:00:00+00:00",))
        con.commit()
    _scan(tmp_path, monkeypatch, _job(_iso(2), "Pune, India"))
    assert _open_matches_roles(tmp_path) == ["Backend Engineer 1"]


def test_a_real_date_ages_from_itself_whenever_it_was_read():
    from job_hunt.prefilter import current_age_days
    scored, today = date(2026, 10, 4), date(2026, 10, 14)
    assert current_age_days("2026-10-12", scored, today) == 2                  # later than the scored date
    assert current_age_days("2026-10-01", scored, today) == 13                 # the usual case, unchanged
    assert current_age_days("Posted 5 Days Ago", scored, today) == 15          # relative text is relative to the day it was read
    assert current_age_days("", scored, today) is None


def test_an_undated_posting_adds_no_date_but_still_fills_the_location(tmp_path, monkeypatch):
    db = str(tmp_path / "data" / "jobs.db")
    init_db(db)
    _scored(db)
    _scan(tmp_path, monkeypatch, _job("", "Pune, India"))
    row = get_job(job_key(_job()), db_path=db)
    assert not row["posted_at"] and row["location"] == "Pune, India"
    assert _open_matches_roles(tmp_path) == ["Backend Engineer 1"]            # undated jobs are kept, as before


def test_fill_missing_details_only_fills_empty_columns(tmp_path):
    db = str(tmp_path / "jobs.db")
    init_db(db)
    save_job(_job(location="Pune, India"), db_path=db)
    fill_missing_details(job_key(_job()), location="Mumbai", posted_at="2026-10-01", db_path=db)
    with connect(db) as con:
        assert con.execute("SELECT location, posted_at FROM jobs").fetchone() == ("Pune, India", "2026-10-01")
    fill_missing_details(job_key(_job()), posted_at="2026-09-01", db_path=db)  # already dated
    fill_missing_details(job_key(_job()), db_path=db)                          # nothing to fill
    with connect(db) as con:
        assert con.execute("SELECT location, posted_at FROM jobs").fetchone() == ("Pune, India", "2026-10-01")


@pytest.mark.parametrize("posted, expected", [
    ("2026-10-01", "2026-10-01"),
    ("2026-10-01T09:30:00.000Z", "2026-10-01"),
    ("Posted Today", TODAY.isoformat()),
    ("Posted Yesterday", _iso(1)),
    ("Posted 5 Days Ago", _iso(5)),
    ("Posted 30+ Days Ago", _iso(30)),
    ("1760000000", "2025-10-09"),                 # epoch seconds
    ("1760000000000", "2025-10-09"),              # epoch milliseconds
    ("", None),
    ("sometime soon", None),
])
def test_posted_date_iso_turns_every_adapters_value_into_a_date(posted, expected):
    assert posted_date_iso(posted) == expected
