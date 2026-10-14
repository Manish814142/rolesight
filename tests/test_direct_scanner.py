from unittest.mock import patch

import pytest

from job_hunt import scanner
from job_hunt.db import get_job, get_jobs_by_status, init_db, save_job, update_job_status
from job_hunt.models import JobPosting, canonical_hash


@pytest.fixture
def direct_scan_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    resume_file = tmp_path / "resume.md"
    resume_file.write_text("Experienced Node.js and TypeScript Backend Engineer with 3+ years experience.")
    
    db_file = tmp_path / "data" / "jobs.db"
    init_db(str(db_file))
    
    cfg = {
        "gemini_scoring_mode": "batch",  # most tests below exercise the batch path
        "candidate": {
            "name": "Manish Singh",
            "resume_path": "resume.md",
            "min_score": 60,
            "top_n": 5,
        },
        "gemini_api_key": "test-gemini-key",
        "telegram": {"token": "test-token", "chat_id": "test-chat"},
    }
    return cfg, str(db_file)


def _scan_csv():
    """The scan's own output (T34: there is no state/last_scan.json any more): the newest CSV's rows, or [] if none.
    Newest by name (jobs_DATE, jobs_DATE_1, jobs_DATE_2, ...), not by mtime: files written a millisecond apart can tie (T82)."""
    import csv
    from pathlib import Path

    def order(f):
        _, day, *counter = f.stem.split("_")
        return day, int(counter[0]) if counter else 0

    files = sorted(Path("output").glob("jobs_*.csv"), key=order)
    if not files:
        return []
    with files[-1].open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_batch")
def test_direct_scan_and_deduplication(mock_score, mock_fetch, direct_scan_env):
    cfg, db_path = direct_scan_env
    
    # 2 jobs: 1 backend engineer (matches), 1 senior architect (prefilter should skip)
    job_good = JobPosting(
        global_id="gh:stripe:1",
        ats="greenhouse",
        company="Stripe",
        title="Software Engineer, Backend",
        location="Bengaluru, India",
        is_remote=False,
        url="https://boards.greenhouse.io/stripe/1",
        description_text="Node.js and distributed systems",
    )
    job_bad = JobPosting(
        global_id="gh:stripe:2",
        ats="greenhouse",
        company="Stripe",
        title="Senior Director of Sales",
        location="Bengaluru, India",
        is_remote=False,
        url="https://boards.greenhouse.io/stripe/2",
        description_text="Sales leadership",
    )
    mock_fetch.return_value = [job_good, job_bad]
    def _score(**kw):
        out = []
        for j in kw["jobs"]:
            update_job_status(canonical_hash(j.title, j.company, j.location), "scored", 85, "Node.js match")
            out.append({"score": 85, "reason": "Node.js match", "status": "scored"})
        return out

    mock_score.side_effect = _score
    
    companies = [{"name": "Stripe", "ats": "greenhouse", "slug": "stripe"}]
    
    # First scan:
    scanner.run_scan(cfg, companies)
    
    # mock_score called once only for the good job!
    mock_score.assert_called_once()
    assert [j.title for j in mock_score.call_args[1]["jobs"]] == ["Software Engineer, Backend"]
    
    # Skipped jobs recorded in DB
    skipped = get_jobs_by_status("skipped")
    assert len(skipped) == 1
    assert skipped[0]["title"] == "Senior Director of Sales"
    
    # Second scan: same jobs returned
    mock_score.reset_mock()
    scanner.run_scan(cfg, companies)
    
    # Second scan should NOT call mock_score at all because good job was already recorded!
    mock_score.assert_not_called()


def _backend_job(n="9"):
    return JobPosting(
        global_id=f"gh:acme:{n}",
        ats="greenhouse",
        company="Acme",
        title="Backend Engineer (JavaScript)",
        location="Bengaluru, India",
        is_remote=False,
        url=f"https://boards.greenhouse.io/acme/{n}",
        description_text="Node.js",
    )


@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_batch")
def test_failed_scoring_is_retried_next_scan(mock_score, mock_fetch, direct_scan_env):
    """Scorer leaves a failed job as 'discovered'; the next scan must score it again."""
    cfg, _ = direct_scan_env
    mock_fetch.return_value = [_backend_job()]
    mock_score.side_effect = lambda **kw: [{"score": None, "reason": "Scoring failed: 429", "status": "discovered"} for _ in kw['jobs']]
    companies = [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}]

    scanner.run_scan(cfg, companies)
    assert mock_score.call_count == 1
    assert _scan_csv() == []  # failed job not reported as scored (no CSV at all)

    scanner.run_scan(cfg, companies)
    assert mock_score.call_count == 2


@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_batch")
def test_previously_skipped_job_is_reevaluated(mock_score, mock_fetch, direct_scan_env):
    """Rows skipped by an older pre-filter get another pass, so filter fixes take
    effect on jobs already in the DB."""
    cfg, db_path = direct_scan_env
    job = _backend_job("10")
    save_job(job, status="skipped", db_path=db_path)
    mock_fetch.return_value = [job]
    mock_score.side_effect = lambda **kw: [{"score": 80, "reason": "fit", "status": "scored"} for _ in kw['jobs']]

    scanner.run_scan(cfg, [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}])

    mock_score.assert_called_once()
    rec = get_job(canonical_hash(job.title, job.company, job.location), db_path=db_path)
    assert rec["status"] == "discovered"  # promoted; real scorer then sets scored/notified


@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_batch")
def test_scanner_passes_config_to_scorer(mock_score, mock_fetch, direct_scan_env):
    cfg, _ = direct_scan_env
    cfg["gemini_model"] = "gemini-2.5-flash"
    mock_fetch.return_value = [_backend_job("11")]
    mock_score.side_effect = lambda **kw: [{"score": 50, "reason": "meh", "status": "scored"} for _ in kw['jobs']]

    scanner.run_scan(cfg, [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}])

    assert mock_score.call_args.kwargs["config"]["gemini_model"] == "gemini-2.5-flash"


@patch("job_hunt.scanner.send_telegram")
@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_batch")
def test_placeholder_telegram_is_not_sent(mock_score, mock_fetch, mock_send, direct_scan_env):
    cfg, _ = direct_scan_env
    cfg["telegram"] = {"token": "real-looking-token", "chat_id": "YOUR_TELEGRAM_CHAT_ID"}
    mock_fetch.return_value = [_backend_job("12")]
    mock_score.side_effect = lambda **kw: [{"score": 90, "reason": "fit", "status": "scored"} for _ in kw['jobs']]

    scanner.run_scan(cfg, [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}])

    mock_send.assert_not_called()


@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_batch")
def test_scanner_batches_passing_jobs_across_companies(mock_score, mock_fetch, direct_scan_env):
    """Most companies yield 0-3 passing jobs, so batches are filled across companies."""
    cfg, _ = direct_scan_env
    cfg["gemini_batch_size"] = 5
    mock_fetch.side_effect = lambda co: [_backend_job(f"{co['slug']}-{i}") for i in range(4)]
    mock_score.side_effect = lambda **kw: [{"score": 70, "reason": "ok", "status": "scored"} for _ in kw["jobs"]]
    companies = [{"name": f"Co{i}", "ats": "greenhouse", "slug": f"co{i}"} for i in range(3)]

    scanner.run_scan(cfg, companies)

    assert [len(c.kwargs["jobs"]) for c in mock_score.call_args_list] == [5, 5, 2]
    assert len(_scan_csv()) == 12


@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_batch")
@patch("job_hunt.scanner.score_and_process_job")
def test_default_mode_scores_one_job_per_call(mock_single, mock_batch, mock_fetch, direct_scan_env):
    """Batch prompts measurably inflate weak fits (2026-10-04: mean |diff| 15.5 vs
    run-to-run noise 1.0), so single-job scoring stays the default."""
    cfg, _ = direct_scan_env
    cfg.pop("gemini_scoring_mode")
    mock_fetch.return_value = [_backend_job("s1"), _backend_job("s2")]
    mock_single.side_effect = [{"score": 80, "reason": "fit", "status": "scored"},
                               {"score": None, "reason": "Scoring failed: 429", "status": "discovered"}]

    scanner.run_scan(cfg, [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}])

    mock_batch.assert_not_called()
    assert mock_single.call_count == 2
    assert mock_single.call_args.kwargs["config"] is cfg
    assert [r["Score (%)"] for r in _scan_csv()] == ["80"]          # failed job not reported


@patch("job_hunt.scanner.score_and_process_job")
def test_scanner_fetches_companies_in_parallel(mock_single, direct_scan_env):
    """All four fetches must be in flight at once (a Barrier only releases when 4
    threads wait), and processing order still follows companies.json."""
    import threading

    cfg, _ = direct_scan_env
    cfg.pop("gemini_scoring_mode")
    cfg["fetch_workers"] = 4
    barrier = threading.Barrier(4, timeout=5)

    def fake_fetch(company):
        barrier.wait()
        return [_backend_job(company["slug"])]

    mock_single.side_effect = lambda **kw: {"score": 70, "reason": "ok", "status": "scored"}
    companies = [{"name": f"Co{i}", "ats": "greenhouse", "slug": f"co{i}"} for i in range(4)]
    with patch("job_hunt.scanner.fetch_company_jobs", side_effect=fake_fetch):
        scanner.run_scan(cfg, companies)

    assert [c.kwargs["job"].url.rsplit("/", 1)[-1] for c in mock_single.call_args_list] == ["co0", "co1", "co2", "co3"]


@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_job")
def test_posted_within_filter_keeps_fresh_and_undated_jobs(mock_single, mock_fetch, direct_scan_env):
    from datetime import date, timedelta
    cfg, db_path = direct_scan_env
    cfg.pop("gemini_scoring_mode")
    cfg["candidate"]["max_posted_age_days"] = 3
    old, fresh, undated = _backend_job("old"), _backend_job("fresh"), _backend_job("undated")
    old.title, fresh.title, undated.title = "Backend Engineer A", "Backend Engineer B", "Backend Engineer C"
    old.posted_at = (date.today() - timedelta(days=10)).isoformat()
    fresh.posted_at = (date.today() - timedelta(days=1)).isoformat()
    undated.posted_at = ""
    mock_fetch.return_value = [old, fresh, undated]
    mock_single.side_effect = lambda **kw: {"score": 70, "reason": "ok", "status": "scored"}

    scanner.run_scan(cfg, [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}])

    assert sorted(c.kwargs["job"].title for c in mock_single.call_args_list) == ["Backend Engineer B", "Backend Engineer C"]
    rec = get_job(canonical_hash(old.title, old.company, old.location), db_path=db_path)
    assert rec["status"] == "skipped"            # re-evaluated if the window is widened later
    assert {r["Posted"] for r in _scan_csv()} == {fresh.posted_at, ""}


def test_scan_csv_helper_picks_the_highest_numbered_file_even_when_mtimes_tie(tmp_path, monkeypatch):
    """T82: the scanner never overwrites (jobs_DATE.csv, jobs_DATE_1.csv, ...); equal mtimes must not decide which one is read."""
    import os
    from pathlib import Path
    monkeypatch.chdir(tmp_path)
    Path("output").mkdir()
    for name, marker in (("jobs_2026-10-14.csv", "first"), ("jobs_2026-10-14_1.csv", "second"), ("jobs_2026-10-14_2.csv", "third")):
        Path("output", name).write_text(f"Company\n{marker}\n")
        os.utime(Path("output", name), ns=(1_700_000_000_000_000_000,) * 2)
    assert _scan_csv() == [{"Company": "third"}]


@patch("job_hunt.scanner.fetch_company_jobs")
@patch("job_hunt.scanner.score_and_process_job")
def test_the_scan_uses_the_title_filter_of_config_json(mock_single, mock_fetch, direct_scan_env):
    """T103: another person's candidate.titles decide which titles are scored; the defaults would do the opposite here."""
    cfg, db_path = direct_scan_env
    cfg.pop("gemini_scoring_mode")
    cfg["candidate"]["titles"] = {"include": ["java developer"], "exclude": ["intern"]}
    java, backend = _backend_job("java"), _backend_job("backend")
    java.title, backend.title = "Senior Java Developer", "Backend Engineer"
    mock_fetch.return_value = [java, backend]
    mock_single.side_effect = lambda **kw: {"score": 70, "reason": "ok", "status": "scored"}

    scanner.run_scan(cfg, [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}])

    assert [c.kwargs["job"].title for c in mock_single.call_args_list] == ["Senior Java Developer"]
