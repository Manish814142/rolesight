"""T71: every stored score records which Gemini model produced it (no network: the client is a stub).

Measured in T70: gemini-3.1-flash-lite scores weak fits ~7 points higher than gemini-3.5-flash-lite, and a scan falls
back to 3.1 when 3.5 fails or is out of quota (T64), so one CSV could mix two calibrations with nothing to show it.
"""
import csv
import logging
import sqlite3
import types
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from job_hunt import exporter, llm_utils, scanner, scorer
from job_hunt.db import init_db, save_job, update_job_status
from job_hunt.models import JobPosting, job_key

PRIMARY, FALLBACK = llm_utils.GEMINI_FALLBACK_MODELS[:2]
OK_JSON = '{"score": 72, "reason": "fine"}'


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(llm_utils.time, "sleep", lambda s: None)
    monkeypatch.setattr(scorer.time, "sleep", lambda s: None)


def _client(outcomes):
    """Stub client; outcomes(model, call_no) -> an Exception to raise or the response text."""
    client = MagicMock()
    client.calls = []

    def generate(model, contents, config):
        client.calls.append(model)
        o = outcomes(model, len(client.calls))
        if isinstance(o, Exception):
            raise o
        return types.SimpleNamespace(text=o)

    client.models.generate_content.side_effect = generate
    return client


def _use(monkeypatch, client):
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key=None: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())))


def _job(i):
    return JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title=f"Backend Engineer {i}",
                      location="Bengaluru, India", is_remote=False, url=f"https://x/{i}", description_text="Node.js",
                      posted_at=(date.today() - timedelta(days=1)).isoformat())   # not a literal: the scan's 7-day window


def test_generate_reports_which_model_answered():
    client = _client(lambda m, n: Exception("500 INTERNAL") if m == "m1" else OK_JSON)
    assert llm_utils._generate_with_model(client, "p", MagicMock(), ["m1", "m2"]) == (OK_JSON, "m2")
    assert llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"]) == OK_JSON   # unchanged API


def test_score_job_with_gemini_returns_the_model(monkeypatch):
    _use(monkeypatch, _client(lambda m, n: OK_JSON))
    res = llm_utils.score_job_with_gemini({"title": "t", "content": "d"}, "resume", {"gemini_api_key": "k"})
    assert res == {"score": 72, "reason": "fine", "model": PRIMARY}


def test_structured_and_batch_scoring_return_the_model(monkeypatch):
    structured = ('{"stack_fit": 80, "role_fit": 80, "seniority_fit": 80, "location_fit": 80, "min_years": 3, '
                  '"accepts_candidate_stack": true, "onsite_outside_india": false, "aimed_at_freshers": false, '
                  '"reason": "ok"}')
    _use(monkeypatch, _client(lambda m, n: Exception("500 INTERNAL") if m == PRIMARY else structured))
    assert llm_utils.score_job_structured_with_gemini({"title": "t"}, "r", {"gemini_api_key": "k"})["model"] == FALLBACK
    _use(monkeypatch, _client(lambda m, n: '[{"job_id": "0", "score": 70, "reason": "a"}]'))
    out = llm_utils.score_jobs_batch_with_gemini([{"id": "0", "title": "t"}], "r", {"gemini_api_key": "k"})
    assert out == {"0": {"score": 70, "reason": "a", "model": PRIMARY}}


def test_init_db_adds_the_model_column_to_an_existing_database(tmp_path):
    db = str(tmp_path / "jobs.db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, canonical_hash TEXT, url_hash TEXT, "
                 "global_id TEXT, title TEXT, company TEXT, ats TEXT, url TEXT, score INTEGER DEFAULT NULL, "
                 "score_reason TEXT DEFAULT NULL, status TEXT DEFAULT 'discovered', "
                 "discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, scored_at TIMESTAMP DEFAULT NULL)")
    conn.execute("INSERT INTO jobs (global_id, status, score) VALUES ('a', 'scored', 80)")
    conn.commit()
    conn.close()
    init_db(db)
    row = sqlite3.connect(db).execute("SELECT score, score_model FROM jobs WHERE global_id = 'a'").fetchone()
    assert row == (80, None)                       # old rows: model unknown, score kept


def test_update_job_status_stores_the_model(tmp_path):
    db = str(tmp_path / "jobs.db")
    save_job(_job(1), db_path=db)
    update_job_status(job_key(_job(1)), "scored", 72, "fine", db_path=db, model=FALLBACK)
    row = sqlite3.connect(db).execute("SELECT status, score, score_model FROM jobs").fetchone()
    assert row == ("scored", 72, FALLBACK)


def test_a_scan_whose_primary_fails_on_one_job_records_the_fallback_on_that_row_and_in_the_csv(
        tmp_path, monkeypatch, caplog):
    """The done-when: the first model fails for job 0 only (a 500, not a quota error), so job 0 is scored by the
    fallback model and job 1 by the primary. Through the real run_scan, DB, CSV writer and funnel line."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db(str(tmp_path / "data" / "jobs.db"))
    client = _client(lambda m, n: Exception("500 INTERNAL") if (m == PRIMARY and n == 1) else OK_JSON)
    _use(monkeypatch, client)
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [_job(0), _job(1)])
    caplog.set_level(logging.INFO, logger="autopilot")
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k",
                      "telegram": {}}, [{"name": "X", "ats": "greenhouse", "slug": "x"}])

    assert client.calls == [PRIMARY, FALLBACK, PRIMARY]
    rows = dict(sqlite3.connect("data/jobs.db").execute("SELECT global_id, score_model FROM jobs").fetchall())
    assert rows == {"greenhouse:x:0": FALLBACK, "greenhouse:x:1": PRIMARY}
    (csv_path,) = (tmp_path / "output").glob("jobs_*.csv")
    by_role = {r["Role"]: r for r in csv.DictReader(csv_path.open(encoding="utf-8"))}
    assert by_role["Backend Engineer 0"]["Model"] == FALLBACK and by_role["Backend Engineer 1"]["Model"] == PRIMARY
    line = next(r.getMessage() for r in caplog.records if "Funnel" in r.getMessage())
    assert f"scored 2 ({PRIMARY} 1, {FALLBACK} 1)" in line or f"scored 2 ({FALLBACK} 1, {PRIMARY} 1)" in line, line


def test_the_funnel_line_names_the_model_when_only_one_scored(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js")
    init_db(str(tmp_path / "data" / "jobs.db"))
    _use(monkeypatch, _client(lambda m, n: OK_JSON))
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [_job(0), _job(1), _job(2)])
    caplog.set_level(logging.INFO, logger="autopilot")
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k",
                      "telegram": {}}, [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    line = next(r.getMessage() for r in caplog.records if "Funnel" in r.getMessage())
    assert f"scored 3 ({PRIMARY} 3)" in line, line
    (csv_path,) = (tmp_path / "output").glob("jobs_*.csv")
    assert "Model" not in next(csv.reader(csv_path.open(encoding="utf-8")))    # the normal case: no new column


def test_batch_scoring_stores_the_model(tmp_path):
    db = str(tmp_path / "jobs.db")
    save_job(_job(1), db_path=db)
    import job_hunt.scorer as s
    orig = s.score_jobs_batch_with_gemini
    s.score_jobs_batch_with_gemini = lambda payload, resume, cfg: {"0": {"score": 66, "reason": "r", "model": FALLBACK}}
    try:
        (res,) = s.score_and_process_batch([_job(1)], "resume", "k", db_path=db)
    finally:
        s.score_jobs_batch_with_gemini = orig
    assert res["model"] == FALLBACK
    assert sqlite3.connect(db).execute("SELECT score_model FROM jobs").fetchone() == (FALLBACK,)


@pytest.mark.parametrize("models, shown", [
    ([PRIMARY, PRIMARY], False),           # the normal day: no extra column
    ([PRIMARY, FALLBACK], True),           # mixed calibrations in one file
    ([FALLBACK, FALLBACK], True),          # the primary was out all run: every score is the fallback's
    ([None, None], False),                 # rows written before T71 (or by the deprecated providers)
])
def test_csv_model_column_appears_only_when_a_job_was_not_scored_by_the_primary(tmp_path, models, shown):
    jobs = [{"company": "X", "title": f"t{i}", "url": f"u{i}", "score": 70, "model": m} for i, m in enumerate(models)]
    path = exporter.export_jobs_to_csv(jobs, out_path=tmp_path / "o.csv")
    header = next(csv.reader(path.open(encoding="utf-8")))
    assert ("Model" in header) is shown
