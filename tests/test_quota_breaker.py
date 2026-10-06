"""T03: stop scoring when the Gemini daily quota runs out (no network: the Gemini client is a stub)."""
import types
from unittest.mock import MagicMock

import pytest

from job_hunt import llm_utils, scanner, scorer
from job_hunt.db import get_jobs_by_status, init_db
from job_hunt.llm_utils import GeminiQuotaExhausted
from job_hunt.models import JobPosting

QUOTA_ERR = "429 RESOURCE_EXHAUSTED. You exceeded your current quota (GenerateRequestsPerDayPerProjectPerModel)"
OK_JSON = '{"score": 66, "reason": "fine"}'


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(llm_utils.time, "sleep", lambda s: None)
    monkeypatch.setattr(scorer.time, "sleep", lambda s: None)


def _client(*outcomes):
    """A stub Gemini client: each call returns/raises the next outcome (the last one repeats)."""
    outcomes = list(outcomes)
    client = MagicMock()

    def generate(model, contents, config):
        o = outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]
        if isinstance(o, Exception):
            raise o
        return types.SimpleNamespace(text=o)

    client.models.generate_content.side_effect = generate
    return client


def _patch_client(monkeypatch, client):
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())))


def _job(i):
    return JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title=f"Backend Engineer {i}",
                      location="Bengaluru, India", is_remote=False, url=f"https://x/{i}", description_text="Node.js")


# --- llm_utils: telling "quota gone" apart from other failures ---------------

def test_all_models_rate_limited_raises_quota_exhausted():
    client = _client(Exception(QUOTA_ERR))
    with pytest.raises(GeminiQuotaExhausted):
        llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"])
    assert client.models.generate_content.call_count == 4      # 2 models x (1 try + 1 retry)


def test_mixed_failures_are_not_reported_as_quota():
    client = _client(Exception(QUOTA_ERR), Exception(QUOTA_ERR), Exception("500 INTERNAL server error"))
    with pytest.raises(Exception) as ei:
        llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"])
    assert not isinstance(ei.value, GeminiQuotaExhausted)


def test_one_model_with_quota_left_still_answers():
    client = _client(Exception(QUOTA_ERR), Exception(QUOTA_ERR), OK_JSON)
    assert llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"]) == OK_JSON


# --- scorer: the flag on the result -------------------------------------------

def test_scoring_result_flags_quota_exhaustion(monkeypatch, tmp_path):
    _patch_client(monkeypatch, _client(Exception(QUOTA_ERR)))
    res = scorer.score_and_process_job(_job(1), "resume", "k", db_path=str(tmp_path / "j.db"), config={})
    assert res["score"] is None and res["status"] == "discovered" and res["quota_exhausted"] is True


def test_other_scoring_failures_are_not_flagged(monkeypatch, tmp_path):
    _patch_client(monkeypatch, _client(Exception("500 INTERNAL")))
    res = scorer.score_and_process_job(_job(1), "resume", "k", db_path=str(tmp_path / "j.db"), config={})
    assert res["score"] is None and not res.get("quota_exhausted")


# --- scanner: the breaker -------------------------------------------------------

@pytest.fixture
def scan_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db(str(tmp_path / "data" / "jobs.db"))
    return {"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k", "telegram": {}}


def _run(monkeypatch, scan_env, client, n_jobs):
    _patch_client(monkeypatch, client)
    jobs = [_job(i) for i in range(n_jobs)]
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: jobs)
    scanner.run_scan(scan_env, [{"name": "X", "ats": "greenhouse", "slug": "x"}])


def test_always_429_stops_after_three_jobs_and_leaves_all_50_discovered(monkeypatch, scan_env):
    """The task's done-when: <= K x (models x 2) calls for 50 jobs, and all 50 stay 'discovered'."""
    client = _client(Exception(QUOTA_ERR))
    _run(monkeypatch, scan_env, client, 50)
    models = len(llm_utils._gemini_models(scan_env))
    assert client.models.generate_content.call_count <= scanner.QUOTA_BREAKER_THRESHOLD * models * 2
    assert len(get_jobs_by_status("discovered")) == 50
    assert get_jobs_by_status("scored") == []


def test_a_success_resets_the_streak(monkeypatch, scan_env):
    """429s on one job, then an answer: the quota is evidently not gone, so scoring continues."""
    q = Exception(QUOTA_ERR)
    # job0: 4 calls fail; job1: 4 calls fail; job2 answers; job3..: all fail until 3 in a row.
    client = _client(*([q] * 8), OK_JSON, *([q] * 100))
    _run(monkeypatch, scan_env, client, 20)
    models = len(llm_utils._gemini_models(scan_env))
    scored = get_jobs_by_status("scored")
    assert len(scored) == 1                                   # job2 was scored after two failures
    # jobs 0 and 1 fail (models x 2 calls each), job 2 answers (1 call), jobs 3-5 fail and trip the breaker
    assert client.models.generate_content.call_count == 2 * models * 2 + 1 + 3 * models * 2
    assert len(get_jobs_by_status("discovered")) == 19


def test_non_quota_failures_never_trip_the_breaker(monkeypatch, scan_env):
    client = _client(Exception("500 INTERNAL"))
    _run(monkeypatch, scan_env, client, 8)
    assert client.models.generate_content.call_count == 8 * len(llm_utils._gemini_models(scan_env))
    assert len(get_jobs_by_status("discovered")) == 8
