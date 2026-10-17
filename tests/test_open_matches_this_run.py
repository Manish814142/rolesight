"""T124: output/open_matches.csv lists the jobs the LAST SCAN scored, not every job still unmarked.

Manish (2026-10-17): nobody marks a job applied by hand, so the rolling list of T39 only grew with old jobs and showed the
same ones again every day. Until the web UI exists, the file shows what this run found and what to apply to now; the
per-scan jobs_*.csv keeps every scored job, and `open_matches_scope: "all_open"` in config.json brings the rolling list back.
No network: adapters and scoring are stubbed; run_scan, the CSV writers and the SQLite rows are real.
"""
import csv
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from job_hunt import scanner, tracker
from job_hunt.db import init_db, save_job, update_job_status
from job_hunt.models import JobPosting, job_key

TODAY = date.today().isoformat()


def _job(name: str, posted: str = TODAY, ats: str = "greenhouse") -> JobPosting:
    return JobPosting(global_id=f"{ats}:x:{name}", ats=ats, company="X", title=f"Backend Engineer {name}", location="Bengaluru, India",
                      is_remote=False, url=f"https://x/{name}", description_text="Node.js", posted_at=posted)


def _scored_earlier(job: JobPosting, score: int, days_ago: int = 1) -> None:
    save_job(job)
    update_job_status(job_key(job), "scored", score, "r")
    con = sqlite3.connect("data/jobs.db")
    con.execute("UPDATE jobs SET scored_at = ? WHERE global_id = ?",
                ((datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(), job.global_id))
    con.commit()
    con.close()


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Three jobs scored by earlier scans (80, 90, 75: all above min_score 70, none marked) and a `run` that scans again."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js")
    init_db("data/jobs.db")
    earlier = [_job("O1"), _job("O2"), _job("O3")]
    for job, score in zip(earlier, (80, 90, 75)):
        _scored_earlier(job, score)
    fetched = {"jobs": []}

    def run(new=(), scores=None, **config):
        """One scan whose boards return the earlier jobs again plus `new`; `scores` maps a role suffix to its score."""
        fetched["jobs"] = [*earlier, *new]
        monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: list(fetched["jobs"]))

        def fake_score(job, **kw):
            score = (scores or {}).get(job.title.rsplit(" ", 1)[1], 70)
            update_job_status(job_key(job), "scored", score, "r")
            return {"score": score, "reason": "r", "status": "scored"}

        monkeypatch.setattr(scanner, "score_and_process_job", fake_score)
        scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 70}, "gemini_api_key": "k", "telegram": {}, **config},
                         [{"name": "X", "ats": "greenhouse", "slug": "x"}])
        with Path("output/open_matches.csv").open(encoding="utf-8") as fh:
            return [r["Application URL"].rsplit("/", 1)[1] for r in csv.DictReader(fh)]
    return run


def test_only_the_jobs_this_scan_scored_and_that_pass_min_score_are_listed_best_first(env):
    listed = env(new=[_job("N1"), _job("N2"), _job("N3"), _job("N4")], scores={"N1": 85, "N2": 65, "N3": 95, "N4": 70})
    assert listed == ["N3", "N1", "N4"]                      # N2 (65) is below 70; O1-O3 (80, 90, 75) are old news


def test_a_scan_that_finds_nothing_new_leaves_the_file_empty_not_full_of_old_jobs(env):
    assert env(new=[_job("N1")], scores={"N1": 90}) == ["N1"]
    assert env() == []                                       # same boards, nothing new: yesterday's job is not shown again
    assert Path("output/open_matches.csv").read_text(encoding="utf-8").startswith("Company,")


def test_the_next_scan_replaces_the_list_with_its_own_jobs(env):
    assert env(new=[_job("N1")], scores={"N1": 90}) == ["N1"]
    assert env(new=[_job("N1"), _job("N2")], scores={"N2": 88}) == ["N2"]


def test_a_job_already_marked_applied_is_not_listed_even_when_this_scan_scored_it(env):
    already = _job("M")
    save_job(already)
    tracker.mark_job(already.url, "applied")
    assert env(new=[already, _job("N1")], scores={"M": 99, "N1": 90}) == ["N1"]


@pytest.mark.parametrize("mark", ["interview", "rejected", "offer"])
def test_any_mark_keeps_a_job_off_the_list_not_only_applied(env, mark):
    """T124 review: as in the rolling list (`application_status IS NULL`), a job marked interview, rejected or offer is not
    something to apply to now; a version that hid only "applied" passed every other test."""
    marked = _job("M")
    save_job(marked)
    tracker.mark_job(marked.url, mark)
    assert env(new=[marked, _job("N1")], scores={"M": 99, "N1": 90}) == ["N1"]


def test_an_undated_job_is_kept_like_in_the_scan_itself(env):
    assert env(new=[_job("U", posted="")], scores={"U": 90}) == ["U"]


def test_the_per_scan_csv_still_has_every_job_scored_so_the_old_ones_are_not_lost(env):
    env(new=[_job("N1"), _job("N2")], scores={"N1": 90, "N2": 40})
    (per_scan,) = Path("output").glob("jobs_*.csv")
    with per_scan.open(encoding="utf-8") as fh:
        assert sorted(r["Application URL"].rsplit("/", 1)[1] for r in csv.DictReader(fh)) == ["N1", "N2"]


def test_the_ats_column_is_there(env):
    env(new=[_job("N1", ats="lever")], scores={"N1": 90})
    with Path("output/open_matches.csv").open(encoding="utf-8") as fh:
        assert [(r["ATS"], r["Company"]) for r in csv.DictReader(fh)] == [("lever", "X")]


def test_the_rolling_list_is_still_there_when_asked_for(env):
    listed = env(new=[_job("N1")], scores={"N1": 85}, open_matches_scope="all_open")
    assert listed == ["O2", "N1", "O1", "O3"]                 # every unmarked job >= min_score, best first (T39)


def test_this_run_is_the_default_scope_by_name(env):
    assert env(new=[_job("N1")], scores={"N1": 85}, open_matches_scope="this_run") == ["N1"]


@pytest.mark.parametrize("bad", ["everything", "all", "run", 7])
def test_an_unknown_scope_stops_the_scan_before_anything_is_fetched(env, monkeypatch, bad):
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: pytest.fail("fetched before the config was checked"))
    with pytest.raises(SystemExit, match="open_matches_scope"):
        scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 70}, "gemini_api_key": "k", "telegram": {},
                          "open_matches_scope": bad}, [{"name": "X", "ats": "greenhouse", "slug": "x"}])


def test_the_log_line_says_what_the_file_holds(env, caplog):
    import logging
    with caplog.at_level(logging.INFO):
        env(new=[_job("N1")], scores={"N1": 90})
    line = next(r.getMessage() for r in caplog.records if "open_matches.csv" in r.getMessage())
    assert "this run" in line and ": 1 →" in line
