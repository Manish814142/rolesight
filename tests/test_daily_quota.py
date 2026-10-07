"""T64: a model whose DAILY quota is gone is skipped for the rest of the run (no network: the client is a stub).

Measured 2026-10-07: with gemini-3.5-flash-lite at its 500/day limit, every job still sent it two requests and
slept 5 s (Google's "retry in 23h20m6s" does not match the per-minute "retry in Ns" pattern) before the
fallback model answered: ~6.5 s per job, ~43 min on a 400-job run (inferred).
"""
import time
import types
from unittest.mock import MagicMock

import pytest

from job_hunt import llm_utils, scanner, scorer
from job_hunt.db import get_jobs_by_status, init_db
from job_hunt.llm_utils import GeminiQuotaExhausted
from job_hunt.models import JobPosting

# Shaped like the real error of 2026-10-07 (abridged): per-day quotaId and a retryDelay of ~23 h.
DAILY_ERR = ("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota. "
             "Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, "
             "limit: 500, model: gemini-3.5-flash-lite\\nPlease retry in 23h20m6.475468307s.', 'status': "
             "'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure', "
             "'violations': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}, "
             "{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '84006s'}]}}")
MINUTE_ERR = ("429 RESOURCE_EXHAUSTED. Quota exceeded, quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier. "
              "Please retry in 12.5s.")
OK_JSON = '{"score": 72, "reason": "fine"}'


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(llm_utils.time, "sleep", lambda s: slept.append(s))
    return slept


def _client(by_model):
    """Stub client: by_model maps a model name to the outcome it always gives (an Exception or text)."""
    client = MagicMock()
    client.calls = []

    def generate(model, contents, config):
        client.calls.append(model)
        o = by_model[model]
        if isinstance(o, Exception):
            raise o
        return types.SimpleNamespace(text=o)

    client.models.generate_content.side_effect = generate
    return client


def test_a_daily_exhausted_model_is_not_retried_and_is_skipped_on_the_next_job(no_sleep):
    client = _client({"m1": Exception(DAILY_ERR), "m2": OK_JSON})
    assert llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"]) == OK_JSON
    assert llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"]) == OK_JSON
    assert client.calls == ["m1", "m2", "m2"]          # was m1, m1, m2, m1, m1, m2
    assert no_sleep == []                              # no 5 s wait on a quota that resets tomorrow


def test_the_skip_lasts_until_the_reset_given_by_retry_delay():
    client = _client({"m1": Exception(DAILY_ERR), "m2": OK_JSON})
    before = time.time()
    llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"])
    until = llm_utils._DAILY_QUOTA_EXHAUSTED["m1"]
    assert before < until <= time.time() + 84006          # never past retryDelay (and capped at midnight Pacific)
    llm_utils._DAILY_QUOTA_EXHAUSTED["m1"] = time.time() - 1      # the quota has reset
    client.calls.clear()
    llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"])
    assert client.calls == ["m1", "m2"]                # tried again


def test_every_model_out_for_the_day_raises_without_any_request():
    client = _client({"m1": Exception(DAILY_ERR), "m2": Exception(DAILY_ERR)})
    with pytest.raises(GeminiQuotaExhausted):
        llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"])
    assert client.calls == ["m1", "m2"]
    with pytest.raises(GeminiQuotaExhausted):
        llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"])
    assert client.calls == ["m1", "m2"]                # no request at all the second time


def test_a_per_minute_limit_is_still_retried_and_not_remembered(no_sleep):
    client = _client({"m1": Exception(MINUTE_ERR), "m2": OK_JSON})
    llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"])
    assert client.calls == ["m1", "m1", "m2"] and no_sleep == [13.5]
    assert "m1" not in llm_utils._DAILY_QUOTA_EXHAUSTED


def test_a_scan_with_the_primary_model_out_for_the_day_asks_it_once(tmp_path, monkeypatch):
    """The 2026-10-07 situation through the real run_scan: every job is scored by the fallback model, and the
    exhausted primary is asked once for the whole run instead of twice per job."""
    monkeypatch.setattr(scorer.time, "sleep", lambda s: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db(str(tmp_path / "data" / "jobs.db"))
    primary, fallback = llm_utils._gemini_models({})[:2]
    client = _client({primary: Exception(DAILY_ERR), fallback: OK_JSON})
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())))
    jobs = [JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title=f"Backend Engineer {i}",
                       location="Bengaluru, India", is_remote=False, url=f"https://x/{i}", description_text="Node.js")
            for i in range(10)]
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: jobs)
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k",
                      "telegram": {}}, [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    assert client.calls.count(primary) == 1 and client.calls.count(fallback) == 10
    assert len(get_jobs_by_status("scored")) == 10


def test_the_skip_never_outlasts_the_next_midnight_pacific(monkeypatch):
    """Google's docs: per-day quotas reset at midnight Pacific. Measured 2026-10-07: at 00:40 UTC the 429 said
    'retry in 23h20m' (retryDelay 84006 s), yet gemini-3.5-flash-lite answered again at 08:05 UTC. So a long-lived
    process must not trust retryDelay past the next Pacific midnight (07:00 UTC in October, PDT)."""
    from datetime import datetime, timezone

    now = datetime(2026, 10, 7, 0, 40, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(llm_utils.time, "time", lambda: now)
    client = _client({"m1": Exception(DAILY_ERR), "m2": OK_JSON})
    llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"])
    assert llm_utils._DAILY_QUOTA_EXHAUSTED["m1"] == datetime(2026, 10, 7, 7, 0, tzinfo=timezone.utc).timestamp()


def test_a_short_retry_delay_is_kept_when_it_ends_before_midnight_pacific(monkeypatch):
    from datetime import datetime, timezone

    now = datetime(2026, 10, 7, 6, 0, tzinfo=timezone.utc).timestamp()      # 23:00 PDT
    monkeypatch.setattr(llm_utils.time, "time", lambda: now)
    client = _client({"m1": Exception(DAILY_ERR.replace("84006s", "600s")), "m2": OK_JSON})
    llm_utils._generate_with_fallback(client, "p", MagicMock(), ["m1", "m2"])
    assert llm_utils._DAILY_QUOTA_EXHAUSTED["m1"] == now + 600
