"""T30 review fix: stored Workday ids must equal what the Workday adapter emits.

The first T30 migration rewrote every Workday global_id to 'workday:<display name>:...'
(the adapter uses the tenant: 'workday:amat:...'), so on the first real database all 101
scored Workday rows were unreachable by the new key and would have been re-scored.
Each test checks the stored id against the real `fetch_workday` output.
"""
from unittest.mock import MagicMock, patch

import pytest

from job_hunt import scanner
from job_hunt.adapters.workday import fetch_workday
from job_hunt.db import connect, get_job, init_db
from job_hunt.models import job_key

AMAT_URL = "https://amat.wd1.myworkdayjobs.com/External/job/BangaloreIND/Algorithm-Developer_R2628315"
# Adobe's site name has an underscore: the first T30 backfill split the URL on the wrong one.
ADOBE_URL = "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/Bangalore/Information-Systems-Engineer-4_R169535"

LEGACY_SCHEMA = """
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, canonical_hash TEXT UNIQUE, url_hash TEXT, global_id TEXT,
    title TEXT, company TEXT, ats TEXT, url TEXT, score INTEGER DEFAULT NULL,
    score_reason TEXT DEFAULT NULL, status TEXT DEFAULT 'discovered',
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, scored_at TIMESTAMP DEFAULT NULL)
"""
# The same table without UNIQUE(canonical_hash): what T30's first migration left in production.
MIGRATED_SCHEMA = LEGACY_SCHEMA.replace("canonical_hash TEXT UNIQUE", "canonical_hash TEXT")


def _make_db(path, schema, rows):
    with connect(path) as conn:
        conn.execute(schema)
        for i, (gid, company, url) in enumerate(rows):
            conn.execute(
                "INSERT INTO jobs (canonical_hash, url_hash, global_id, title, company, ats, url, score, status) "
                "VALUES (?, ?, ?, 't', ?, 'workday', ?, 80, 'scored')", (f"h{i}", f"u{i}", gid, company, url))
        conn.commit()


def _adapter_id(url):
    """global_id that fetch_workday really emits for the posting behind `url`."""
    host, _, rest = url.removeprefix("https://").partition("/")
    tenant, dc = host.split(".")[:2]
    site, _, ext = rest.partition("/")
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"jobPostings": [
        {"title": "T", "locationsText": "India", "externalPath": "/" + ext, "bulletFields": ["IGNORED"]}]}
    with patch("requests.post", return_value=resp):
        jobs = fetch_workday(tenant, dc, site)
    assert jobs[0].url == url
    return jobs[0].global_id


def _stored_ids(path):
    with connect(path) as conn:
        return [r[0] for r in conn.execute("SELECT global_id FROM jobs ORDER BY id")]


def test_legacy_db_workday_ids_match_the_adapter(tmp_path):
    db = str(tmp_path / "legacy.db")
    # Pre-T30 adapter ids: tenant + bulletFields[0] (requisition id).
    _make_db(db, LEGACY_SCHEMA, [("workday:amat:R2628315", "Applied Materials", AMAT_URL),
                                 ("workday:adobe:R169535", "Adobe India", ADOBE_URL)])
    init_db(db)
    assert _stored_ids(db) == [_adapter_id(AMAT_URL), _adapter_id(ADOBE_URL)]


def test_already_migrated_db_with_display_name_ids_is_repaired(tmp_path):
    db = str(tmp_path / "prod.db")
    _make_db(db, MIGRATED_SCHEMA, [
        ("workday:Applied Materials:R2628315", "Applied Materials", AMAT_URL),
        ("workday:Adobe India:experienced/job/Bangalore/Information-Systems-Engineer-4_R169535", "Adobe India", ADOBE_URL)])
    init_db(db)
    assert _stored_ids(db) == [_adapter_id(AMAT_URL), _adapter_id(ADOBE_URL)]
    scored = get_job(_adapter_id(AMAT_URL), db_path=db)
    assert scored is not None and scored["status"] == "scored" and scored["score"] == 80


def test_repair_runs_once_and_is_idempotent(tmp_path):
    db = str(tmp_path / "prod.db")
    _make_db(db, MIGRATED_SCHEMA, [("workday:Applied Materials:R2628315", "Applied Materials", AMAT_URL)])
    init_db(db)
    first = _stored_ids(db)
    with connect(db) as conn:
        conn.execute("UPDATE jobs SET global_id = 'hand-edited'")
    init_db(db)  # user_version says the repair already ran: must not touch rows again
    assert first == [_adapter_id(AMAT_URL)]
    assert _stored_ids(db) == ["hand-edited"]


def test_repair_leaves_rows_alone_when_the_new_id_is_taken(tmp_path):
    db = str(tmp_path / "prod.db")
    _make_db(db, MIGRATED_SCHEMA, [(_adapter_id(AMAT_URL), "Applied Materials", AMAT_URL),
                                   ("workday:Applied Materials:R2628315", "Applied Materials", AMAT_URL + "-copy")])
    init_db(db)  # must not raise IntegrityError
    assert len(_stored_ids(db)) == 2


def test_legacy_dedupe_keeps_the_scored_row(tmp_path):
    db = str(tmp_path / "legacy.db")
    with connect(db) as conn:
        conn.execute(LEGACY_SCHEMA)
        for i, status in enumerate(["skipped", "scored"]):  # same requisition stored twice
            conn.execute("INSERT INTO jobs (canonical_hash, global_id, title, company, ats, url, status, score) "
                         "VALUES (?, 'x', 't', 'c', 'workday', ?, ?, ?)",
                         (f"h{i}", AMAT_URL, status, 80 if status == "scored" else None))
        conn.commit()
    init_db(db)
    with connect(db) as conn:
        assert conn.execute("SELECT status FROM jobs").fetchall() == [("scored",)]


@pytest.fixture
def scan_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    return {"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k", "telegram": {}}


def test_scan_does_not_rescore_a_workday_job_scored_before_the_migration(scan_env, tmp_path, monkeypatch):
    """The real consumer: a job already scored in the DB must not reach Gemini again."""
    (tmp_path / "data").mkdir()
    _make_db(str(tmp_path / "data" / "jobs.db"), MIGRATED_SCHEMA,
             [("workday:Applied Materials:R2628315", "Applied Materials", AMAT_URL)])
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"jobPostings": [
        {"title": "Algorithm Developer", "locationsText": "Bengaluru, India", "postedOn": "Posted Today",
         "externalPath": "/job/BangaloreIND/Algorithm-Developer_R2628315", "bulletFields": ["R2628315"]}]}
    scored = []
    monkeypatch.setattr(scanner, "score_and_process_job",
                        lambda job, **kw: scored.append(job.title) or {"score": 50, "reason": "r", "status": "scored"})

    with patch("requests.post", return_value=resp):
        scanner.run_scan(scan_env, [{"name": "Applied Materials", "ats": "workday",
                                     "tenant": "amat", "dc": "wd1", "site": "External"}])

    assert scored == []
    with connect(tmp_path / "data" / "jobs.db") as conn:
        assert conn.execute("SELECT count(*) FROM jobs").fetchone() == (1,)  # no duplicate row
    assert job_key  # imported for readers: the key the scan looked up is job_key(job)
