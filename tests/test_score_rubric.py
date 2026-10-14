"""T97: every stored score records which scoring prompt produced it (no network: the client is a stub).

Rubric changes (T58, T73, T74, T79) leave rows scored under older wording in `data/jobs.db`, and nothing said which. A
short id of the prompt text now travels with each score, the way the model does (T71, tests/test_score_model.py).
"""
import csv
import logging
import re
import sqlite3
import types
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from job_hunt import exporter, llm_utils, scanner, scorer
from job_hunt.db import connect, init_db, save_job, update_job_status
from job_hunt.models import JobPosting, job_key

OK_JSON = '{"score": 72, "reason": "fine"}'
BATCH_JSON = '[{"job_id": "0", "score": 66, "reason": "r"}]'
STRUCTURED_JSON = ('{"stack_fit": 80, "role_fit": 80, "seniority_fit": 80, "location_fit": 80, "min_years": 3, '
                   '"accepts_candidate_stack": true, "onsite_outside_india": false, "aimed_at_freshers": false, '
                   '"reason": "ok"}')


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(llm_utils.time, "sleep", lambda s: None)
    monkeypatch.setattr(scorer.time, "sleep", lambda s: None)


def _client(reply):
    """Stub client that answers `reply` and keeps every prompt it was sent."""
    client = MagicMock()
    client.prompts = []

    def generate(model, contents, config):
        client.prompts.append(contents)
        return types.SimpleNamespace(text=reply)

    client.models.generate_content.side_effect = generate
    return client


def _use(monkeypatch, client):
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key=None: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())))
    return client


def _job(i=1):
    return JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title=f"Backend Engineer {i}",
                      location="Bengaluru, India", is_remote=False, url=f"https://x/{i}", description_text="Node.js",
                      posted_at=(date.today() - timedelta(days=1)).isoformat())


def _rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _stored(db, column="score_rubric"):
    with connect(db) as con:
        return con.execute(f"SELECT {column} FROM jobs").fetchone()[0]


def test_rubric_id_is_a_short_hash_of_the_prompt_text(monkeypatch):
    first = llm_utils.rubric_id()
    assert re.fullmatch(r"[0-9a-f]{8}", first)
    assert llm_utils.rubric_id() == first
    assert llm_utils.rubric_id("rule A") != llm_utils.rubric_id("rule B")
    # The id follows the text the process is using, not a value computed when the module was imported.
    monkeypatch.setattr(llm_utils, "SCORING_RUBRIC", llm_utils.SCORING_RUBRIC + " One more rule.")
    assert llm_utils.rubric_id() != first


def test_each_scoring_call_reports_the_id_of_the_text_it_sent(monkeypatch):
    monkeypatch.setattr(llm_utils, "SCORING_RUBRIC", "RUBRIC SENTINEL 123")
    monkeypatch.setattr(llm_utils, "STRUCTURED_INSTRUCTIONS", "STRUCTURED SENTINEL 456")
    cfg = {"gemini_api_key": "k"}

    client = _use(monkeypatch, _client(OK_JSON))
    res = llm_utils.score_job_with_gemini({"title": "t", "content": "d"}, "resume", cfg)
    assert "RUBRIC SENTINEL 123" in client.prompts[-1]
    assert res["rubric"] == llm_utils.rubric_id("RUBRIC SENTINEL 123")

    client = _use(monkeypatch, _client(BATCH_JSON))
    out = llm_utils.score_jobs_batch_with_gemini([{"id": "0", "title": "t"}], "r", cfg)
    assert "RUBRIC SENTINEL 123" in client.prompts[-1]
    assert out["0"]["rubric"] == llm_utils.rubric_id("RUBRIC SENTINEL 123")

    client = _use(monkeypatch, _client(STRUCTURED_JSON))
    res = llm_utils.score_job_structured_with_gemini({"title": "t"}, "r", cfg)
    assert "STRUCTURED SENTINEL 456" in client.prompts[-1] and "RUBRIC SENTINEL 123" not in client.prompts[-1]
    assert res["rubric"] == llm_utils.rubric_id("STRUCTURED SENTINEL 456")


def test_current_ids_are_the_two_prompts_this_checkout_sends():
    assert llm_utils.current_rubric_ids() == {llm_utils.rubric_id(), llm_utils.rubric_id(llm_utils.STRUCTURED_INSTRUCTIONS)}


def test_init_db_adds_the_rubric_column_to_an_existing_database(tmp_path):
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
    init_db(db)                                    # idempotent
    with connect(db) as con:
        assert con.execute("SELECT score, score_rubric FROM jobs WHERE global_id = 'a'").fetchone() == (80, None)


def test_update_job_status_stores_the_rubric_and_a_status_only_update_keeps_it(tmp_path):
    db = str(tmp_path / "jobs.db")
    save_job(_job(), db_path=db)
    update_job_status(job_key(_job()), "scored", 72, "fine", db_path=db, model="m", rubric="abc12345")
    update_job_status(job_key(_job()), "notified", db_path=db)
    with connect(db) as con:
        assert con.execute("SELECT status, score, score_rubric FROM jobs").fetchone() == ("notified", 72, "abc12345")


def test_scoring_one_job_stores_the_rubric_that_scored_it(tmp_path, monkeypatch):
    db = str(tmp_path / "jobs.db")
    save_job(_job(), db_path=db)
    _use(monkeypatch, _client(OK_JSON))
    res = scorer.score_and_process_job(_job(), "resume", "k", db_path=db)
    assert res["rubric"] == llm_utils.rubric_id()
    assert _stored(db) == llm_utils.rubric_id()


def test_batch_scoring_stores_the_rubric(tmp_path, monkeypatch):
    db = str(tmp_path / "jobs.db")
    save_job(_job(), db_path=db)
    _use(monkeypatch, _client(BATCH_JSON))
    (res,) = scorer.score_and_process_batch([_job()], "resume", "k", db_path=db)
    assert res["rubric"] == llm_utils.rubric_id()
    assert _stored(db) == llm_utils.rubric_id()


def test_structured_scoring_stores_the_id_of_its_own_instructions(tmp_path, monkeypatch):
    db = str(tmp_path / "jobs.db")
    save_job(_job(), db_path=db)
    _use(monkeypatch, _client(STRUCTURED_JSON))
    scorer.score_and_process_job(_job(), "resume", "k", db_path=db, config={"scoring_mode": "structured"})
    assert _stored(db) == llm_utils.rubric_id(llm_utils.STRUCTURED_INSTRUCTIONS)
    assert _stored(db) != llm_utils.rubric_id()


def test_a_failed_score_leaves_the_rubric_empty(tmp_path, monkeypatch):
    db = str(tmp_path / "jobs.db")
    save_job(_job(), db_path=db)
    _use(monkeypatch, _client("not json"))
    assert scorer.score_and_process_job(_job(), "resume", "k", db_path=db)["score"] is None
    assert _stored(db) is None


def _scan(tmp_path, monkeypatch, jobs):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db(str(tmp_path / "data" / "jobs.db"))
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: jobs)
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k", "telegram": {}},
                     [{"name": "X", "ats": "greenhouse", "slug": "x"}])


def test_a_scan_stores_logs_and_does_not_flag_the_current_rubric(tmp_path, monkeypatch, caplog):
    """Through the real run_scan, DB, CSV writer and log: the normal day adds no column."""
    _use(monkeypatch, _client(OK_JSON))
    caplog.set_level(logging.INFO, logger="autopilot")
    _scan(tmp_path, monkeypatch, [_job(0), _job(1)])

    with connect("data/jobs.db") as con:
        assert {r[0] for r in con.execute("SELECT score_rubric FROM jobs")} == {llm_utils.rubric_id()}
    assert any(r.getMessage() == f"Scoring rubric: {llm_utils.rubric_id()}" for r in caplog.records)
    (csv_path,) = (tmp_path / "output").glob("jobs_*.csv")
    assert "Rubric" not in _rows(csv_path)[0]


def test_a_structured_scan_logs_the_structured_id(tmp_path, monkeypatch, caplog):
    _use(monkeypatch, _client(STRUCTURED_JSON))
    caplog.set_level(logging.INFO, logger="autopilot")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js")
    init_db(str(tmp_path / "data" / "jobs.db"))
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [_job(0)])
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k",
                      "scoring_mode": "structured", "telegram": {}}, [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    expected = f"Scoring rubric: {llm_utils.rubric_id(llm_utils.STRUCTURED_INSTRUCTIONS)}"
    assert any(r.getMessage() == expected for r in caplog.records)


def test_the_deprecated_providers_log_no_rubric(tmp_path, monkeypatch, caplog):
    """Their prompt is not SCORING_RUBRIC, so naming it would be wrong."""
    caplog.set_level(logging.INFO, logger="autopilot")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "resume.md").write_text("Node.js")
    init_db(str(tmp_path / "data" / "jobs.db"))
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [])
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 60}, "llm_provider": "anthropic",
                      "telegram": {}}, [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    assert not any("Scoring rubric" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("rubrics, shown", [
    (["current", "current"], False),                 # the normal day
    (["current", "0123abcd"], True),                 # one score from an older wording
    (["0123abcd", "0123abcd"], True),                # all of them are
    (["current", None], True),                       # a row scored before the id was recorded (T97)
    ([None, None], False),                           # nothing recorded yet: an always-empty column says nothing (T36)
    (["structured", "structured"], False),           # opted-in structured scoring is current too
])
def test_csv_rubric_column_appears_only_when_a_score_is_not_from_the_current_prompt(tmp_path, rubrics, shown):
    ids = {"current": llm_utils.rubric_id(), "structured": llm_utils.rubric_id(llm_utils.STRUCTURED_INSTRUCTIONS)}
    rubrics = [ids.get(r, r) for r in rubrics]
    jobs = [{"company": "X", "title": f"t{i}", "url": f"u{i}", "score": 70, "rubric": r} for i, r in enumerate(rubrics)]
    path = exporter.export_jobs_to_csv(jobs, out_path=tmp_path / "o.csv")
    rows = _rows(path)
    assert ("Rubric" in rows[0]) is shown
    if shown:
        assert [r["Rubric"] for r in rows] == [r or "" for r in rubrics]


def test_jobs_that_carry_no_rubric_at_all_add_no_column(tmp_path):
    """The deprecated providers' results have no `rubric` key: nothing recorded, so nothing to compare."""
    jobs = [{"company": "X", "title": "t", "url": "u", "score": 70}]
    assert "Rubric" not in _rows(exporter.export_jobs_to_csv(jobs, out_path=tmp_path / "o.csv"))[0]


def test_export_from_the_database_flags_rows_scored_before_the_id_existed(tmp_path):
    """`autopilot export` / open_matches.csv read the column back from data/jobs.db."""
    db = str(tmp_path / "jobs.db")
    for i in (1, 2):
        save_job(_job(i), db_path=db)
    update_job_status(job_key(_job(1)), "scored", 80, "new", db_path=db, rubric=llm_utils.rubric_id())
    update_job_status(job_key(_job(2)), "scored", 75, "old", db_path=db)            # no rubric: scored before T97
    with connect(db) as con:
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute("SELECT * FROM jobs ORDER BY id")]
    jobs = [exporter.job_from_db_row(r, 70) for r in rows]
    assert [j["rubric"] for j in jobs] == [llm_utils.rubric_id(), None]
    out = _rows(exporter.export_jobs_to_csv(jobs, out_path=tmp_path / "o.csv"))
    assert [r["Rubric"] for r in out] == [llm_utils.rubric_id(), ""]
