"""T118: no cap on jobs scored per run; the two models' daily limits are the limit.

Manish (2026-10-17): "there should be no cap, on my account I have 500 per model limit so total 1000 I can run: first 500 on the
3.5 flash lite model, the rest on 3.1 flash lite, so it should switch automatically when it hits the limit." The switch itself exists
(T64: a model whose daily quota is gone is skipped until it resets); what stopped a 700-job run was the default cap of 400.
The real run_scan with a stub client (no network): the first model gives 500 answers and then Google's per-day 429, the second gives 500.
"""
import types
from unittest.mock import MagicMock

import pytest

from job_hunt import llm_utils, scanner, scorer
from job_hunt.db import connect, init_db
from job_hunt.models import JobPosting

DAILY_ERR = ("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, limit: 500. "
             "Please retry in 23h20m6s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'violations': [{'quotaId': "
             "'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}, {'retryDelay': '84006s'}]}}")
OK_JSON = '{"score": 72, "reason": "fine"}'
DAILY_ALLOWANCE = 500


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """The pacing pauses (4.2 s per job in a real run) are recorded, not slept."""
    pauses = []
    monkeypatch.setattr(llm_utils.time, "sleep", lambda s: None)
    monkeypatch.setattr(scorer.time, "sleep", lambda s: pauses.append(s))
    return pauses


def _client(allowance):
    """Stub Gemini: each model answers `allowance[model]` times, then gives the per-day 429 on every call."""
    client = MagicMock()
    client.calls, client.answered = [], {m: 0 for m in allowance}

    def generate(model, contents, config):
        client.calls.append(model)
        if client.answered[model] >= allowance[model]:
            raise Exception(DAILY_ERR)
        client.answered[model] += 1
        return types.SimpleNamespace(text=OK_JSON)

    client.models.generate_content.side_effect = generate
    return client


def _run(tmp_path, monkeypatch, n_jobs, allowance, config_extra=None):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db(str(tmp_path / "data" / "jobs.db"))
    primary, fallback = llm_utils._gemini_models({})[:2]
    client = _client({primary: allowance, fallback: allowance})
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key=None: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())))
    jobs = [JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title=f"Backend Engineer {i}",
                       location="Bengaluru, India", is_remote=False, url=f"https://x/{i}", description_text="Node.js")
            for i in range(n_jobs)]
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: jobs)
    cfg = {"candidate": {"resume_path": "resume.md", "min_score": 60, **(config_extra or {})}, "gemini_api_key": "k", "telegram": {}}
    scanner.run_scan(cfg, [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    with connect(str(tmp_path / "data" / "jobs.db")) as con:
        by_model = dict(con.execute("SELECT score_model, count(*) FROM jobs WHERE status IN ('scored', 'notified') GROUP BY 1").fetchall())
        left = con.execute("SELECT count(*) FROM jobs WHERE status = 'discovered'").fetchone()[0]
    return primary, fallback, client, by_model, left


def test_the_default_is_no_cap():
    assert scanner.DEFAULT_MAX_JOBS_TO_SCORE == 0


def test_700_jobs_the_first_500_go_to_the_first_model_and_the_other_200_to_the_second_without_any_setting(tmp_path, monkeypatch):
    primary, fallback, client, by_model, left = _run(tmp_path, monkeypatch, 700, DAILY_ALLOWANCE)
    assert by_model == {primary: 500, fallback: 200} and left == 0
    assert client.calls.count(primary) == 501                     # 500 answers, then the per-day 429 once: never asked again
    assert client.calls.count(fallback) == 200


def test_when_both_models_have_used_their_day_the_scan_stops_and_leaves_the_rest_for_the_next_one(tmp_path, monkeypatch, no_sleep):
    primary, fallback, client, by_model, left = _run(tmp_path, monkeypatch, 1100, DAILY_ALLOWANCE)
    assert by_model == {primary: 500, fallback: 500} and left == 100
    assert client.calls.count(primary) == 501 and client.calls.count(fallback) <= 503     # a handful of calls after the last answer, then it stops
    # Without the stop the 100 jobs left would still each wait their 4.2 s pacing pause (about 7 minutes) for nothing.
    assert len(no_sleep) <= 1000 + 5, f"{len(no_sleep)} pacing pauses for 1,000 answers: the scan did not stop"


def test_a_cap_can_still_be_asked_for(tmp_path, monkeypatch):
    primary, fallback, client, by_model, left = _run(tmp_path, monkeypatch, 30, DAILY_ALLOWANCE, {})
    assert sum(by_model.values()) == 30                           # baseline without a cap
    scored_capped = _run_capped(tmp_path / "capped", monkeypatch, 30, 12)
    assert scored_capped == (12, 18)


def _run_capped(path, monkeypatch, n_jobs, cap):
    path.mkdir()
    monkeypatch.chdir(path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (path / "resume.md").write_text("Node.js backend engineer")
    init_db(str(path / "data" / "jobs.db"))
    primary = llm_utils._gemini_models({})[0]
    client = _client({primary: DAILY_ALLOWANCE})
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key=None: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())))
    jobs = [JobPosting(global_id=f"greenhouse:y:{i}", ats="greenhouse", company="Y", title=f"Backend Engineer {i}",
                       location="Bengaluru, India", is_remote=False, url=f"https://y/{i}", description_text="Node.js")
            for i in range(n_jobs)]
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: jobs)
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 60}, "max_jobs_to_score_per_run": cap,
                      "gemini_api_key": "k", "telegram": {}}, [{"name": "Y", "ats": "greenhouse", "slug": "y"}])
    with connect(str(path / "data" / "jobs.db")) as con:
        return (con.execute("SELECT count(*) FROM jobs WHERE status IN ('scored', 'notified')").fetchone()[0],
                con.execute("SELECT count(*) FROM jobs WHERE status = 'discovered'").fetchone()[0])
