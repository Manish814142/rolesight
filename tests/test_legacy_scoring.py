"""T52: the non-Gemini scoring path stores what it scored, so a second scan does not pay for it again.

Only `chat_with_llm` is stubbed; the prompt parsing, run_scan and the SQLite rows are real.
"""
import json

import pytest

from job_hunt import scanner
from job_hunt.db import get_job
from job_hunt.models import JobPosting


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(scanner.time, "sleep", lambda *_: None)


def _posting(n: int) -> JobPosting:
    return JobPosting(global_id=f"greenhouse:acme:{n}", ats="greenhouse", company="Acme", title=f"Backend Engineer {n}",
                      location="Bengaluru, India", is_remote=False, url=f"https://x.co/jobs/{n}", description_text="Node")


@pytest.fixture
def legacy_scan(tmp_path, monkeypatch):
    """Two jobs, llm_provider anthropic (no Gemini key). Returns (run, llm_calls, set_reply)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "resume.md").write_text("Backend engineer, 3 YOE.")
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [_posting(1), _posting(2)])
    monkeypatch.setattr(scanner, "send_telegram", lambda *a: True)
    cfg = {"llm_provider": "anthropic",
           "candidate": {"name": "Ada", "resume_path": "resume.md", "min_score": 55, "top_n": 5}}
    companies = [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}]
    calls, reply = [], {"text": "[]"}

    def fake_llm(config, messages, temperature=0.1, max_tokens=4096):
        calls.append(messages[0]["content"])
        if isinstance(reply["text"], Exception):
            raise reply["text"]
        return reply["text"]

    monkeypatch.setattr(scanner, "chat_with_llm", fake_llm)
    return (lambda: scanner.run_scan(cfg, companies)), calls, (lambda text: reply.update(text=text))


def _both_scored(job_number_1_score=90, job_number_2_score=30):
    return json.dumps([
        {"job_number": 1, "score": job_number_1_score, "title": "Backend Engineer 1", "worth_applying": True,
         "stack": "Node", "location_remote": "Bengaluru", "reason": "fits"},
        {"job_number": 2, "score": job_number_2_score, "title": "Backend Engineer 2", "worth_applying": False,
         "stack": "Java", "location_remote": "Bengaluru", "reason": "stack mismatch"},
    ])


def test_scored_jobs_are_stored_with_score_and_reason(legacy_scan):
    run, _, set_reply = legacy_scan
    set_reply(_both_scored())
    run()
    one, two = get_job("greenhouse:acme:1"), get_job("greenhouse:acme:2")
    assert (one["status"], one["score"], one["score_reason"]) == ("scored", 90, "fits")
    # below the threshold is still a result: stored, so it is not paid for again
    assert (two["status"], two["score"], two["score_reason"]) == ("scored", 30, "stack mismatch")


def test_second_scan_does_not_call_the_llm_again(legacy_scan):
    run, calls, set_reply = legacy_scan
    set_reply(_both_scored())
    run()
    assert len(calls) == 1          # two jobs fit in one batch prompt
    run()
    assert len(calls) == 1


def test_job_the_llm_left_out_stays_discovered_and_is_retried(legacy_scan):
    run, calls, set_reply = legacy_scan
    set_reply(json.dumps([json.loads(_both_scored())[0]]))     # no entry for job 2
    run()
    assert get_job("greenhouse:acme:1")["status"] == "scored"
    assert get_job("greenhouse:acme:2")["status"] == "discovered"
    assert get_job("greenhouse:acme:2")["score"] is None       # never a made-up 0
    run()
    assert len(calls) == 2          # job 2 only; job 1 is final
    assert "Backend Engineer 1" not in calls[1] and "Backend Engineer 2" in calls[1]


@pytest.mark.parametrize("reply", ["sorry, no json here", RuntimeError("llm down")])
def test_failed_call_leaves_every_job_discovered(legacy_scan, reply):
    run, _, set_reply = legacy_scan
    set_reply(reply)
    run()
    for n in (1, 2):
        row = get_job(f"greenhouse:acme:{n}")
        assert row["status"] == "discovered" and row["score"] is None


def test_item_without_a_score_is_not_stored_as_zero(legacy_scan):
    run, _, set_reply = legacy_scan
    set_reply(json.dumps([{"job_number": 1, "title": "x", "worth_applying": False, "reason": "?"}]))
    run()
    assert get_job("greenhouse:acme:1")["status"] == "discovered"


def test_only_worth_applying_jobs_reach_the_csv(legacy_scan):
    """Unchanged behaviour: the legacy path reports the passing jobs only."""
    import csv
    from pathlib import Path
    run, _, set_reply = legacy_scan
    set_reply(_both_scored())
    run()
    (out,) = Path("output").glob("jobs_*.csv")
    assert [r["Application URL"] for r in csv.DictReader(out.open(encoding="utf-8"))] == ["https://x.co/jobs/1"]
