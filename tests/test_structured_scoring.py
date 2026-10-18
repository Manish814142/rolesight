"""T41: the model extracts facts and sub-scores; deterministic code applies the caps and computes the score."""
import json
import types
from unittest.mock import MagicMock

import pytest

from job_hunt import llm_utils
from job_hunt.llm_utils import SUBSCORE_WEIGHTS, combine_subscores, score_job_structured_with_gemini


def facts(**kw):
    base = {"stack_fit": 100, "role_fit": 100, "seniority_fit": 100, "location_fit": 100, "min_years": 3,
            "accepts_candidate_stack": True, "onsite_outside_india": False, "aimed_at_freshers": False,
            "reason": "fits"}
    base.update(kw)
    return base


def test_weights_sum_to_one():
    assert abs(sum(SUBSCORE_WEIGHTS.values()) - 1.0) < 1e-9


def test_perfect_fit_scores_100_and_partial_fits_are_weighted():
    assert combine_subscores(facts())["score"] == 100
    s = combine_subscores(facts(stack_fit=60, role_fit=80, seniority_fit=70, location_fit=100))["score"]
    expected = round(0.35 * 60 + 0.25 * 80 + 0.25 * 70 + 0.15 * 100)
    assert s == expected


def test_different_sub_scores_break_what_used_to_be_a_tie():
    a = combine_subscores(facts(stack_fit=95, seniority_fit=90))["score"]
    b = combine_subscores(facts(stack_fit=85, seniority_fit=100))["score"]
    assert a != b


@pytest.mark.parametrize("override, cap", [
    ({"onsite_outside_india": True}, 30),
    ({"role_fit": 20}, 40),
    ({"min_years": 7}, 50),
    ({"aimed_at_freshers": True}, 50),
    ({"accepts_candidate_stack": False}, 50),
])
def test_caps_are_applied_in_code(override, cap):
    out = combine_subscores(facts(**override))
    assert out["score"] <= cap
    assert out["capped_by"]


def test_a_stack_mismatch_caps_at_50_like_the_rubric():
    """T69(f): rule 4 of the rubric caps at 50 (T73); the structured mode's code said 60."""
    out = combine_subscores(facts(accepts_candidate_stack=False))
    assert out["score"] == 50 and "stack" in out["capped_by"]


def test_the_lowest_cap_wins_and_it_is_reported():
    out = combine_subscores(facts(onsite_outside_india=True, min_years=8, accepts_candidate_stack=False))
    assert out["score"] <= 30 and "onsite" in out["capped_by"]


def test_no_cap_means_none_reported():
    assert combine_subscores(facts())["capped_by"] == ""


def test_five_years_is_not_capped_but_six_is():
    assert combine_subscores(facts(min_years=5))["score"] == 100
    assert combine_subscores(facts(min_years=6))["score"] <= 50
    assert combine_subscores(facts(min_years=None))["score"] == 100


# --- the Gemini call (stubbed) ------------------------------------------------------------

def _stub(monkeypatch, payload):
    client = MagicMock()
    client.models.generate_content.return_value = types.SimpleNamespace(text=payload if isinstance(payload, str) else json.dumps(payload))
    cfg_cls = MagicMock()
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=cfg_cls)))
    return client, cfg_cls


JOB = {"company": "C", "title": "Backend Engineer", "location": "Bengaluru", "content": "Node.js, 3+ years"}


def test_structured_call_returns_the_computed_score_and_the_facts(monkeypatch):
    client, cfg_cls = _stub(monkeypatch, facts(stack_fit=90, seniority_fit=80))
    out = score_job_structured_with_gemini(JOB, "RESUME TEXT", {"gemini_api_key": "k"})
    assert out["score"] == combine_subscores(facts(stack_fit=90, seniority_fit=80))["score"]
    assert out["stack_fit"] == 90 and out["min_years"] == 3 and out["reason"] == "fits"
    prompt = client.models.generate_content.call_args.kwargs["contents"]
    assert "RESUME TEXT" in prompt and "Node.js, 3+ years" in prompt
    assert "do not compute" in prompt.lower()                    # the model must not produce the final score
    assert cfg_cls.call_args.kwargs["response_json_schema"]["type"] == "object"


def test_out_of_range_sub_scores_are_clamped(monkeypatch):
    _stub(monkeypatch, facts(stack_fit=250, role_fit=-5))
    out = score_job_structured_with_gemini(JOB, "r", {"gemini_api_key": "k"})
    assert out["stack_fit"] == 100 and out["role_fit"] == 0


def test_missing_fields_raise_so_the_job_is_retried_not_scored_zero(monkeypatch):
    _stub(monkeypatch, {"stack_fit": 80, "reason": "partial"})
    with pytest.raises(ValueError):
        score_job_structured_with_gemini(JOB, "r", {"gemini_api_key": "k"})


def test_not_json_raises(monkeypatch):
    _stub(monkeypatch, "sorry, I cannot")
    with pytest.raises(Exception):
        score_job_structured_with_gemini(JOB, "r", {"gemini_api_key": "k"})


# --- plumbing: scoring_mode "structured" is opt-in; the default stays holistic ----------------------------

from job_hunt import scanner, scorer  # noqa: E402
from job_hunt.db import get_job, init_db, save_job  # noqa: E402
from job_hunt.models import JobPosting  # noqa: E402


def _job(i=1):
    return JobPosting(global_id=f"greenhouse:x:{i}", ats="greenhouse", company="X", title="Backend Engineer",
                      location="Bengaluru, India", is_remote=False, url=f"https://x/{i}", description_text="Node.js")


def test_scorer_default_mode_is_the_holistic_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr(scorer.time, "sleep", lambda s: None)
    monkeypatch.setattr(scorer, "score_job_with_gemini", lambda **kw: {"score": 71, "reason": "holistic"})
    monkeypatch.setattr(scorer, "score_job_structured_with_gemini", lambda *a, **k: pytest.fail("must not be called"))
    init_db(str(tmp_path / "j.db"))
    res = scorer.score_and_process_job(_job(), "resume", "k", db_path=str(tmp_path / "j.db"), config={})
    assert res["score"] == 71 and res["details"] == {}


def test_scorer_structured_mode_returns_details_and_stores_the_cap_in_the_reason(monkeypatch, tmp_path):
    monkeypatch.setattr(scorer.time, "sleep", lambda s: None)
    out = {**combine_subscores(facts(min_years=8)), **facts(min_years=8)}
    monkeypatch.setattr(scorer, "score_job_structured_with_gemini", lambda *a, **k: out)
    db = str(tmp_path / "j.db")
    init_db(db)
    save_job(_job(), db_path=db)
    res = scorer.score_and_process_job(_job(), "resume", "k", db_path=db, config={"scoring_mode": "structured"})
    assert res["score"] <= 50 and res["details"]["capped_by"] == "asks for 6+ years"
    assert res["details"]["stack_fit"] == 100 and res["details"]["min_years"] == 8
    row = get_job("greenhouse:x:1", db_path=db)
    assert row["status"] == "scored" and "asks for 6+ years" in row["score_reason"]


def test_run_scan_puts_sub_scores_in_the_results_only_in_structured_mode(monkeypatch, tmp_path):
    import csv
    from pathlib import Path
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    monkeypatch.setattr(scorer.time, "sleep", lambda s: None)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db(str(tmp_path / "data" / "jobs.db"))
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [_job(1)])
    full = {**combine_subscores(facts(stack_fit=70)), **facts(stack_fit=70)}
    monkeypatch.setattr(scorer, "score_job_structured_with_gemini", lambda *a, **k: full)
    cfg = {"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k", "telegram": {},
           "scoring_mode": "structured"}
    scanner.run_scan(cfg, [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    row = list(csv.DictReader(next(Path("output/history").glob("jobs_*.csv")).open()))[0]
    assert row["Stack fit"] == "70" and row["Seniority fit"] == "100" and row["Min years"] == "3"


def test_structured_mode_ignores_batch_mode_and_scores_one_job_per_call(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    monkeypatch.setattr(scorer.time, "sleep", lambda s: None)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db(str(tmp_path / "data" / "jobs.db"))
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [_job(1), _job(2)])
    monkeypatch.setattr(scanner, "score_and_process_batch", lambda **k: pytest.fail("batch must not run"))
    calls = []
    monkeypatch.setattr(scorer, "score_job_structured_with_gemini",
                        lambda *a, **k: calls.append(1) or {**combine_subscores(facts()), **facts()})
    cfg = {"candidate": {"resume_path": "resume.md", "min_score": 60}, "gemini_api_key": "k", "telegram": {},
           "scoring_mode": "structured", "gemini_scoring_mode": "batch"}
    scanner.run_scan(cfg, [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    assert len(calls) == 2
