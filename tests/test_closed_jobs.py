"""T33: first_seen / last_seen, and a job is marked closed once its board stops returning it for N scans in a row."""
import csv
import sqlite3
from pathlib import Path

import pytest

from job_hunt import db, scanner
from job_hunt.db import connect, init_db, save_job, update_job_status
from job_hunt.models import JobPosting, job_key


def _job(name, company="X", ats="greenhouse"):
    return JobPosting(global_id=f"{ats}:{company}:{name}", ats=ats, company=company, title=f"Staff Engineer {name}",
                      location="Bengaluru, India", is_remote=False, url=f"https://{company}/{name}")


def _row(job):
    with connect("data/jobs.db") as con:
        con.row_factory = sqlite3.Row
        r = con.execute("SELECT * FROM jobs WHERE global_id = ?", (job.global_id,)).fetchone()
        return dict(r) if r else None


@pytest.fixture
def scan(tmp_path, monkeypatch):
    """run(boards): one real run_scan where board name -> the jobs it returns (an Exception = the fetch failed).
    Titles are 'Staff …', so the pre-filter skips them and nothing is scored: only the sightings matter here."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js")
    init_db("data/jobs.db")

    def run(boards, closed_after=None):
        def fetch(company):
            out = boards[company["name"]]
            if isinstance(out, Exception):
                raise out
            return out() if callable(out) else out
        monkeypatch.setattr(scanner, "fetch_company_jobs", fetch)
        cfg = {"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k", "telegram": {},
               "open_matches_scope": "all_open"}      # T124: this file is about the rolling list of T39
        if closed_after is not None:
            cfg["closed_after_missed_scans"] = closed_after
        scanner.run_scan(cfg, [{"name": n, "ats": "greenhouse", "slug": n.lower()} for n in boards])
    return run


def test_first_and_last_seen(scan):
    a = _job("a")
    scan({"X": [a]})
    first = _row(a)
    assert first["first_seen"] and first["first_seen"] <= first["last_seen"] and first["missed_scans"] == 0
    assert first["first_seen"][:10] == first["last_seen"][:10]
    scan({"X": [a, _job("b")]})
    again = _row(a)
    assert again["first_seen"] == first["first_seen"] and again["last_seen"] > first["last_seen"]


def test_a_job_its_board_stops_returning_is_closed_after_n_scans_and_reopens_if_it_returns(scan):
    a, b = _job("a"), _job("b")
    scan({"X": [a, b]})
    for n in (1, 2):
        scan({"X": [b]})
        assert (_row(a)["missed_scans"], _row(a)["closed_at"]) == (n, None)
    scan({"X": [b]})
    assert _row(a)["missed_scans"] == 3 and _row(a)["closed_at"]          # default N = 3
    assert _row(b)["closed_at"] is None and _row(b)["missed_scans"] == 0
    scan({"X": [a, b]})                                                     # back on the board: open again
    assert (_row(a)["missed_scans"], _row(a)["closed_at"]) == (0, None)


def test_a_failed_or_empty_fetch_is_not_a_miss(scan):
    a = _job("a")
    scan({"X": [a]})
    for boards in ({"X": RuntimeError("timeout")}, {"X": []}, {"X": []}, {"X": []}):
        scan(boards)
    assert (_row(a)["missed_scans"], _row(a)["closed_at"]) == (0, None)


def test_only_the_jobs_own_board_counts(scan):
    a, other = _job("a", company="X"), _job("o", company="Y")
    scan({"X": [a], "Y": [other]}, closed_after=1)
    scan({"X": RuntimeError("down"), "Y": [_job("p", company="Y")]}, closed_after=1)
    assert _row(a)["closed_at"] is None                                    # X was not fetched: unknown, not gone
    assert _row(other)["closed_at"]                                        # Y answered without it


def test_the_scoring_status_is_untouched_and_closed_jobs_leave_open_matches(scan):
    a, b = _job("a"), _job("b")
    for j, s in ((a, 80), (b, 75)):
        save_job(j)
        update_job_status(job_key(j), "scored", s, "r")
    scan({"X": [a, b]}, closed_after=1)
    scan({"X": [b]}, closed_after=1)
    assert _row(a)["status"] == "scored" and _row(a)["score"] == 80 and _row(a)["closed_at"]
    urls = [r["Application URL"] for r in csv.DictReader(Path("output/open_matches.csv").open(encoding="utf-8"))]
    assert urls == [b.url]                                                 # T39: closed jobs are not open matches


def test_init_db_adds_the_columns_and_backfills_first_seen(tmp_path):
    path = str(tmp_path / "jobs.db")
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, canonical_hash TEXT, url_hash TEXT, "
                "global_id TEXT, title TEXT, company TEXT, ats TEXT, url TEXT, score INTEGER DEFAULT NULL, "
                "score_reason TEXT DEFAULT NULL, status TEXT DEFAULT 'discovered', "
                "discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, scored_at TIMESTAMP DEFAULT NULL)")
    con.execute("INSERT INTO jobs (global_id, discovered_at) VALUES ('a', '2026-10-04T06:00:00+00:00')")
    con.commit()
    con.close()
    init_db(path)
    with connect(path) as con:
        row = con.execute("SELECT first_seen, last_seen, missed_scans, closed_at FROM jobs").fetchone()
    assert row == ("2026-10-04T06:00:00+00:00", None, 0, None)


def test_record_sightings_counts_what_it_closed(tmp_path):
    path = str(tmp_path / "jobs.db")
    init_db(path)
    a, b = _job("a"), _job("b")
    for j in (a, b):
        save_job(j, db_path=path)
    assert db.record_sightings({("greenhouse", "X"): [b]}, closed_after=1, db_path=path) == 1
    assert db.record_sightings({("greenhouse", "X"): [b]}, closed_after=1, db_path=path) == 0   # already closed


# --- Partial fetches (review of T33): a board that stopped early says nothing about the jobs it did not return ------

def _wd_page(n, offset, total):
    return {"total": total, "jobPostings": [
        {"title": f"Engineer {offset + i}", "locationsText": "Pune, India", "externalPath": f"/job/P/J_{offset + i}",
         "bulletFields": [f"R{offset + i}"], "postedOn": "Posted Today"} for i in range(n)]}


def _resp(payload):
    from unittest.mock import MagicMock
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


def test_workday_says_when_a_later_page_failed(monkeypatch):
    """Novartis, 2026-10-07: 'Workday fetch failed … at offset 20' — 20 jobs kept, the rest unknown."""
    from job_hunt.adapters import base, workday

    def post(url, json=None, **kw):
        if json["offset"] == 0:
            return _resp(_wd_page(20, 0, 60))
        raise RuntimeError("HTTP 500")
    monkeypatch.setattr(workday, "http_post", post)
    base.begin_fetch()
    assert len(workday.fetch_workday("novartis", "wd3", "Novartis_Careers")) == 20
    assert "page failed" in base.fetch_incomplete()


def test_workday_says_when_it_stopped_at_its_cap(monkeypatch):
    """Accenture returns 2,000 India results in arbitrary order (T49): at the cap the set may differ every scan."""
    from job_hunt.adapters import base, workday
    monkeypatch.setattr(workday, "MAX_JOBS", 40)
    monkeypatch.setattr(workday, "http_post", lambda url, json=None, **kw: _resp(_wd_page(20, json["offset"], 500)))
    base.begin_fetch()
    assert len(workday.fetch_workday("accenture", "wd103", "AccentureCareers")) == 40
    assert "cap" in base.fetch_incomplete()


def test_workday_says_when_the_time_budget_ran_out(monkeypatch):
    from job_hunt.adapters import base, workday
    monkeypatch.setattr(workday, "http_post", lambda url, json=None, **kw: _resp(_wd_page(20, json["offset"], 100)))
    base.begin_fetch()
    workday.fetch_workday("t", "wd1", "S", budget=-1)
    assert "budget" in base.fetch_incomplete()


def test_a_complete_paged_fetch_is_not_flagged(monkeypatch):
    from job_hunt.adapters import base, workday
    monkeypatch.setattr(workday, "http_post", lambda url, json=None, **kw: _resp(_wd_page(
        max(0, min(20, 30 - json["offset"])), json["offset"], 30)))
    base.begin_fetch()
    assert len(workday.fetch_workday("t", "wd1", "S")) == 30
    assert base.fetch_incomplete() is None


@pytest.mark.parametrize("adapter", ["amazon", "smartrecruiters", "oracle_hcm", "eightfold"])
def test_every_paged_adapter_flags_its_cap(monkeypatch, adapter):
    """Caps: Amazon 4,000, SmartRecruiters / Oracle HCM 2,000, Eightfold 1,000 (made small here)."""
    import importlib

    from job_hunt.adapters import base
    mod = importlib.import_module(f"job_hunt.adapters.{adapter}")
    page = getattr(mod, "PAGE_SIZE")
    monkeypatch.setattr(mod, "MAX_JOBS", page)            # one page = the cap; the board has far more
    payloads = {
        "amazon": {"hits": 10 * page, "jobs": [{"id_icims": str(i), "title": "SDE", "job_path": f"/{i}"} for i in range(page)]},
        "smartrecruiters": {"totalFound": 10 * page, "content": [{"id": f"j{i}", "name": "SDE"} for i in range(page)]},
        "oracle_hcm": {"items": [{"TotalJobsCount": 10 * page, "requisitionList": [{"Id": str(i), "Title": "SDE"} for i in range(page)]}]},
        "eightfold": {"data": {"count": 10 * page, "positions": [{"id": i, "name": "SDE"} for i in range(page)]}},
    }
    fake = lambda *a, **k: _resp(payloads[adapter])     # noqa: E731
    for name in ("http_get", "_get"):
        if hasattr(mod, name):
            monkeypatch.setattr(mod, name, fake)
    monkeypatch.setattr("time.sleep", lambda s: None)
    if adapter == "oracle_hcm":
        monkeypatch.setattr(mod, "_india_facet_id", lambda host, site: 300000000)
    base.begin_fetch()
    if adapter == "amazon":
        mod.fetch_amazon()
    elif adapter == "smartrecruiters":
        mod._fetch_all_postings("https://x", "slug")
    elif adapter == "oracle_hcm":
        mod.fetch_oracle_hcm("h.example", "CX")
    else:
        mod.fetch_eightfold("h.example", "d.com", company="D")
    assert "cap" in (base.fetch_incomplete() or "")


def test_a_board_that_stopped_early_counts_no_misses(scan):
    """Through run_scan: the fetch returns only part of the board and says so; nothing is counted as missed, and what
    it did return still counts as seen."""
    from job_hunt.adapters import base
    a, b = _job("a"), _job("b")
    scan({"X": [a, b]}, closed_after=1)

    def partial_board():
        base.mark_incomplete("page failed at offset 20")
        return [b]
    scan({"X": partial_board}, closed_after=1)
    assert (_row(a)["missed_scans"], _row(a)["closed_at"]) == (0, None)
    assert _row(b)["last_seen"] > _row(a)["last_seen"]
    scan({"X": [b]}, closed_after=1)                                       # a complete answer without it: closed
    assert _row(a)["closed_at"]
