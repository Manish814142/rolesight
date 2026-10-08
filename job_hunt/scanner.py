import json
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from job_hunt.adapters import enrich_job, fetch_company_jobs
from job_hunt.db import get_job, init_db, save_job, update_job_details, update_job_status
from job_hunt.llm_utils import chat_with_llm
from job_hunt.log import get_logger
from job_hunt.models import job_key
from job_hunt.notifier import is_telegram_configured, send_telegram
from job_hunt.prefilter import is_too_old, location_is_india, posted_age_days, should_evaluate_job
from job_hunt.scorer import score_and_process_batch, score_and_process_job

logger = get_logger()

STATE_FILE = Path("state/seen_jobs.json")
LAST_SCAN_FILE = Path("state/last_scan.json")
JOB_HISTORY_FILE = Path("state/job_history.json")

SCORE_PROMPT = """You are evaluating job postings for a candidate. Output ONLY a JSON array, no other text.

CANDIDATE:
{candidate_profile}

RESUME SUMMARY:
{resume_summary}

JOBS TO SCORE:
{jobs_text}

For each job output:
{{
  "job_number": 1,
  "score": 0-100,
  "title": "extracted job title",
  "stack": "key tech from JD (comma-separated, max 6 items)",
  "location_remote": "location + remote policy",
  "reason": "one sentence why this fits or doesn't fit the candidate",
  "worth_applying": true/false
}}

Scoring: 80-100 near-perfect; 60-79 good fit; 40-59 partial; <40 poor.
Set worth_applying=true only if score >= {min_score}.
Include ALL jobs. Output ONLY the JSON array."""

from job_hunt.exporter import export_jobs_to_csv  # noqa: E402


def _build_candidate_profile(config: dict) -> str:
    cand = config.get("candidate", {})
    name = cand.get("name", "the candidate")
    profile = cand.get("profile", "")
    seeking = cand.get("seeking", "")
    not_suitable = cand.get("not_suitable", "")

    lines = [f"- {name}"]
    if profile:
        lines.append(f"- {profile}")
    if seeking:
        lines.append(f"- Seeking: {seeking}")
    if not_suitable:
        lines.append(f"- NOT suitable: {not_suitable}")
    return "\n".join(lines)


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"seen_urls": []}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# Opt-in batch scoring (config "gemini_scoring_mode": "batch"): jobs per Gemini call.
# ~10 jobs x 2k-char descriptions + resume ≈ 7k tokens, well inside the 250k TPM free tier.
# Not the default: measured 2026-10-04 on 10 live jobs, batch scores differed from
# single-job scores by 15.5 points on average (run-to-run noise: 1.0), inflating weak fits.
DEFAULT_GEMINI_BATCH_SIZE = 10

# Stop scoring after this many consecutive jobs (or batches) failed with a quota error on every Gemini
# model: the daily quota is gone, and each further job would burn ~20-30 s of retries for nothing (T03).
# The rest stay 'discovered' and are scored on the next scan.
QUOTA_BREAKER_THRESHOLD = 3

# At most this many jobs are scored per run, newest first (config "max_jobs_to_score_per_run"; 0 = no cap, T04).
# The free tier allows about 500 calls per model per day, and the rest simply stay 'discovered' for the next
# scan. Jobs with no known posted date count as newest, so they are never starved.
DEFAULT_MAX_JOBS_TO_SCORE = 400

# Companies fetched concurrently (config "fetch_workers"). Fetching is network-bound;
# DB writes and scoring stay sequential. Each HTTP call has a hard total deadline
# (adapters/base.py) and Workday tenants a per-board budget, so no board can stall a scan.
DEFAULT_FETCH_WORKERS = 8


def _prefetch_jobs(companies: list[dict], workers: int) -> list[tuple[list, str | None]]:
    """Fetch every company's ATS jobs concurrently; returns (jobs, error) in input order."""
    def one(company: dict) -> tuple[list, str | None]:
        try:
            return fetch_company_jobs(company), None
        except Exception as e:
            return [], str(e)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        return list(ex.map(one, companies))


def _enrich_jobs(jobs: list, workers: int) -> int:
    """Fetch full descriptions for pre-filter survivors concurrently (in place).

    Returns how many jobs' descriptions changed.
    """
    before = [j.description_text for j in jobs]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        list(ex.map(enrich_job, jobs))
    return sum(j.description_text != b for j, b in zip(jobs, before))


def score_job(job: dict, resume: str, config: dict) -> dict:
    from job_hunt.llm_utils import score_job_with_gemini
    return score_job_with_gemini(job, resume, config)


def score_jobs(jobs: list[dict], resume: str, config: dict) -> list[dict]:
    if not jobs:
        return []

    if config.get("llm_provider") == "gemini":
        min_score = config.get("candidate", {}).get("min_score", 55)
        results = []
        for idx, job in enumerate(jobs):
            res = score_job(job, resume, config)
            score = res.get("score", 0)
            reason = res.get("reason", "")
            logger.debug(f"    [{score:3d}] {job.get('title', '?')} — {reason[:80]}")
            if score >= min_score:
                j = job.copy()
                j.update(
                    {
                        "score": score,
                        "extracted_title": job.get("title", "?"),
                        "stack": "",
                        "location_remote": job.get("location", ""),
                        "reason": reason,
                        "worth_applying": True,
                    }
                )
                results.append(j)
            if idx < len(jobs) - 1:
                # Pacing sleep to strictly stay under Gemini free-tier 15 RPM cap (60s / 15 = 4.0s)
                time.sleep(4.2)
        return sorted(results, key=lambda x: x["score"], reverse=True)


    scored = score_batch(jobs, resume, config) or []
    return sorted((j for j in scored if j["worth_applying"]), key=lambda x: x["score"], reverse=True)


def _as_score(value) -> Optional[int]:
    """The model's score as an int, or None when it is missing or not a number (never a made-up 0)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(value)


def score_batch(jobs: list[dict], resume: str, config: dict) -> Optional[list[dict]]:
    """Score `jobs` in one prompt (deprecated non-Gemini providers).

    Returns one dict per job the model scored, passing or not, each with `score`, `reason` and
    `worth_applying`. A job the model left out or gave no score is absent, so the caller leaves it
    for the next scan. Returns None when the call or its JSON failed.
    """
    jobs_text = "\n\n".join(
        f"JOB {i + 1}:\nCompany: {j['company']} | Location: {j['location']}\n"
        f"Title: {j['title']}\nURL: {j['url']}\n"
        f"Content:\n{j.get('content', j.get('snippet', ''))[:1500]}"
        for i, j in enumerate(jobs)
    )

    min_score = config.get("candidate", {}).get("min_score", 55)
    candidate_profile = _build_candidate_profile(config)

    prompt = SCORE_PROMPT.format(
        candidate_profile=candidate_profile,
        resume_summary=resume[:2500],
        jobs_text=jobs_text,
        min_score=min_score,
    )

    logger.debug(f"  Scoring {len(jobs)} job(s) via LLM (min_score={min_score})...")
    t0 = time.time()
    try:
        raw = chat_with_llm(
            config,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        elapsed = time.time() - t0
        start, end = raw.find("["), raw.rfind("]") + 1
        if start == -1:
            logger.error("  LLM returned no JSON array")
            return None
        scored = json.loads(raw[start:end])
        logger.debug(f"  LLM scoring complete in {elapsed:.1f}s — {len(scored)} results parsed")
    except Exception as e:
        logger.error(f"  Scoring error: {e}")
        return None

    results: dict[int, dict] = {}
    for item in scored:
        score = _as_score(item.get("score"))
        idx = item.get("job_number", 0) - 1
        if score is None or not 0 <= idx < len(jobs) or idx in results:
            continue
        title = item.get("title", "?")
        reason = item.get("reason", "")
        logger.debug(f"    [{score:3d}] {title} — {reason[:80]}")
        job = jobs[idx].copy()
        job.update(
            {
                "score": score,
                "extracted_title": title,
                "stack": item.get("stack", ""),
                "location_remote": item.get("location_remote", job["location"]),
                "reason": reason,
                "worth_applying": bool(item.get("worth_applying", False)),
            }
        )
        results[idx] = job

    logger.debug(f"  {sum(j['worth_applying'] for j in results.values())}/{len(scored)} jobs passed min_score threshold")
    return list(results.values())


def format_telegram_message(top_jobs: list[dict], date_str: str) -> str:
    lines = [f"<b>Job Hunt — {date_str}</b>", f"<i>{len(top_jobs)} matches found</i>\n"]
    for i, job in enumerate(top_jobs, 1):
        lines.append(
            f"<b>#{i}</b> | {job['company']} | {job.get('extracted_title', job['title'])}\n"
            f"📍 {job.get('location_remote', job['location'])}\n"
            f"🔧 {job.get('stack', 'N/A')}\n"
            f"✅ {job.get('reason', '')}\n"
            f"<a href=\"{job['url']}\">Apply</a>\n"
        )
    lines.append('Reply "apply to #N" to draft application.')
    return "\n".join(lines)


def _export_to_csv(jobs: list[dict], label: str) -> Path:
    out_path = export_jobs_to_csv(jobs, out_dir="output")
    logger.info(f"Results exported to CSV ({label}): {out_path}")
    return out_path


def _by_model(scored_by: Counter) -> str:
    """' (gemini-3.5-flash-lite 4, gemini-3.1-flash-lite 2)' for the funnel line; '' when nothing was scored."""
    return " (" + ", ".join(f"{m} {n}" for m, n in scored_by.most_common()) + ")" if scored_by else ""


def run_scan(config: dict, companies: list[dict]) -> None:
    scan_start = time.time()
    total = len(companies)
    logger.info(f"=== Scan started — {total} companies to check ===")
    logger.info(f"Candidate: {config.get('candidate', {}).get('name', 'unknown')}")
    logger.info(f"Min score: {config.get('candidate', {}).get('min_score', 55)} | Top N: {config.get('candidate', {}).get('top_n', 5)}")
    provider = config.get("llm_provider") or "gemini"
    model_by_provider = {
        "gemini": config.get("gemini_model") or "gemini-3.5-flash-lite",
        "anthropic": config.get("anthropic_model", "default"),
        "claude_cli": config.get("claude_cli_model") or "claude default",
    }
    logger.info(f"LLM provider: {provider} | Model: {model_by_provider.get(provider, 'default')}")

    resume_path = Path(config.get("candidate", {}).get("resume_path", "resume/YOUR_RESUME.md"))
    resume = resume_path.read_text()
    logger.debug(f"Resume loaded: {resume_path} ({len(resume)} chars)")

    min_score = config.get("candidate", {}).get("min_score", 55)
    top_n = config.get("candidate", {}).get("top_n", 5)

    init_db()
    gemini_key = config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
    tg_token = config.get("telegram", {}).get("token")
    tg_chat_id = config.get("telegram", {}).get("chat_id")

    state = load_state()
    seen_urls: set = set(state.get("seen_urls", []))
    logger.info(f"State loaded — {len(seen_urls)} previously seen URLs")

    all_scored_jobs: list[dict] = []
    errors: list[str] = []
    companies_scanned = 0
    scoring_failures = 0
    fetched_total = india_total = already_scored = prefilter_rejected = scored_ok = 0
    scored_by: Counter = Counter()   # model -> jobs it scored this run (T71; the fallback may answer some)
    # Pre-filter survivors from every company; scored together after fetching so
    # Gemini batches fill up (most companies contribute only 0-3 jobs).
    pending_direct: list = []

    max_age = config.get("candidate", {}).get("max_posted_age_days")
    if max_age is not None:
        logger.info(f"Posted-date filter: last {max_age} day(s) only (jobs without a posted date are kept)")
    too_old = 0

    workers = int(config.get("fetch_workers", DEFAULT_FETCH_WORKERS))
    logger.info(f"Fetching {total} companies with {workers} parallel workers...")
    fetch_start = time.time()
    prefetched = _prefetch_jobs(companies, workers)
    logger.info(f"Fetch complete in {(time.time() - fetch_start) / 60:.1f} min")

    for idx, company in enumerate(companies, 1):
        logger.info(f"[{idx}/{total}] Scanning {company['name']}...")
        try:
            # 1. Native direct ATS adapter results (fetched above)
            direct_jobs, fetch_error = prefetched[idx - 1]
            if fetch_error:
                raise RuntimeError(fetch_error)
            if company.get("ats") or direct_jobs:
                if direct_jobs:
                    logger.info(f"  Fetched {len(direct_jobs)} job(s) directly via ATS adapter")
                    queued = 0
                    fetched_total += len(direct_jobs)
                    for job in direct_jobs:
                        seen_urls.add(job.url)
                        india_total += location_is_india(job.location)
                        j_key = job_key(job)
                        # Only scored/notified rows are final. 'skipped' rows are re-run
                        # through the (cheap, local) pre-filter so filter fixes apply to
                        # known jobs; 'discovered' rows are ones whose scoring failed.
                        existing = get_job(j_key)
                        prior_status = existing["status"] if existing else None
                        if prior_status in ("scored", "notified"):
                            logger.debug(f"  Skipping previously scored job: {job.title}")
                            already_scored += 1
                            continue

                        passed, reason = should_evaluate_job(job)
                        if not passed:
                            logger.debug(f"  Pre-filter skipped: {job.title} ({reason})")
                            prefilter_rejected += 1
                            if prior_status is None:
                                save_job(job, status="skipped")
                            continue

                        if is_too_old(job.posted_at, max_age):
                            logger.debug(f"  Older than {max_age} day(s): {job.title} (posted {job.posted_at})")
                            too_old += 1
                            if prior_status is None:
                                save_job(job, status="skipped")  # re-evaluated if the window widens
                            continue

                        if prior_status is None:
                            save_job(job, status="discovered")
                        elif prior_status != "discovered":
                            update_job_status(j_key, "discovered")
                        pending_direct.append(job)
                        queued += 1

                    if queued:
                        logger.info(f"  {queued} job(s) passed the pre-filter — queued for scoring")
                else:
                    logger.info(f"  No open jobs found via {company.get('ats')} adapter")

                companies_scanned += 1
                continue

            # No adapter could fetch this company (custom careers pages are not scanned).
            logger.warning(f"  Skipping {company['name']}: no supported ATS (custom careers pages are not scanned)")
            companies_scanned += 1

        except Exception as company_err:
            msg = f"❌ {company['name']}: {company_err}"
            errors.append(msg)
            logger.error(f"  Company scan failed: {company_err}")
            continue

    queued_total = len(pending_direct)
    cap = int(config.get("max_jobs_to_score_per_run", DEFAULT_MAX_JOBS_TO_SCORE))
    if 0 < cap < len(pending_direct):
        pending_direct.sort(key=lambda j: posted_age_days(j.posted_at) or 0)   # stable: ties keep fetch order
        logger.warning(f"{len(pending_direct)} job(s) are pending but at most {cap} are scored per run: the newest "
                       f"{cap} go first, {len(pending_direct) - cap} stay 'discovered' for the next scan")
        del pending_direct[cap:]
    elif pending_direct:
        pending_direct.sort(key=lambda j: posted_age_days(j.posted_at) or 0)

    if pending_direct:
        # Workday/SmartRecruiters/Oracle list APIs carry little or no description;
        # fetch it for survivors only (see adapters.ENRICHERS).
        enrich_start = time.time()
        enriched = _enrich_jobs(pending_direct, workers)
        logger.info(f"Full descriptions fetched for {enriched} of {len(pending_direct)} survivor(s) "
                    f"in {time.time() - enrich_start:.0f} s")
        for job in pending_direct:  # keep what the scorer sees, so a score can be audited and redone (T29)
            update_job_details(job_key(job), location=job.location, posted_at=job.posted_at,
                               description=job.description_text)
        if gemini_key:
            scored_pairs: list = []
            quota_streak = 0
            if config.get("scoring_mode") == "structured" and config.get("gemini_scoring_mode") == "batch":
                logger.warning("scoring_mode 'structured' scores one job per call; gemini_scoring_mode 'batch' is ignored")
            if config.get("gemini_scoring_mode", "single") == "batch" and config.get("scoring_mode") != "structured":
                batch_size = max(1, int(config.get("gemini_batch_size", DEFAULT_GEMINI_BATCH_SIZE)))
                n_batches = -(-len(pending_direct) // batch_size)
                logger.info(f"Scoring {len(pending_direct)} job(s) in {n_batches} Gemini batch(es) of up to {batch_size}...")
                for i in range(0, len(pending_direct), batch_size):
                    if quota_streak >= QUOTA_BREAKER_THRESHOLD:
                        break
                    chunk = pending_direct[i: i + batch_size]
                    results = score_and_process_batch(
                        jobs=chunk,
                        resume_text=resume,
                        gemini_api_key=gemini_key,
                        telegram_token=tg_token,
                        telegram_chat_id=tg_chat_id,
                        min_notify_score=min_score,
                        config=config,
                    )
                    scored_pairs.extend(zip(chunk, results))
                    quota_streak = quota_streak + 1 if all(r.get("quota_exhausted") for r in results) else 0
            else:
                logger.info(f"Scoring {len(pending_direct)} job(s) one per Gemini call (~4.2 s each)...")
                for job in pending_direct:
                    res = score_and_process_job(
                        job=job,
                        resume_text=resume,
                        gemini_api_key=gemini_key,
                        telegram_token=tg_token,
                        telegram_chat_id=tg_chat_id,
                        min_notify_score=min_score,
                        config=config,
                    )
                    scored_pairs.append((job, res))
                    quota_streak = quota_streak + 1 if res.get("quota_exhausted") else 0
                    if quota_streak >= QUOTA_BREAKER_THRESHOLD:
                        break
            if quota_streak >= QUOTA_BREAKER_THRESHOLD:
                succeeded = sum(1 for _, r in scored_pairs if r["score"] is not None)
                logger.warning(
                    f"Gemini quota exhausted ({quota_streak} in a row failed on every model): scoring stopped after "
                    f"{succeeded} scored; {len(pending_direct) - succeeded} job(s) are left as 'discovered' for the next scan"
                )
            for job, res in scored_pairs:
                if res["score"] is None:
                    scoring_failures += 1
                    continue
                scored_ok += 1
                scored_by[res.get("model") or "unknown model"] += 1
                logger.debug(f"    [{res['score']:3d}] {job.title} @ {job.company} — {res['reason'][:80]}")
                all_scored_jobs.append({
                    "company": job.company,
                    "title": job.title,
                    "extracted_title": job.title,
                    "location": job.location,
                    "location_remote": job.location,
                    "url": job.url,
                    "score": res["score"],
                    "reason": res["reason"],
                    "stack": "",
                    "worth_applying": res["score"] >= min_score,
                    "posted_at": job.posted_at,
                    "model": res.get("model"),
                    **(res.get("details") or {}),
                })
        else:
            # Deprecated non-Gemini providers: score_batch puts 10 jobs in one prompt. Every job the model
            # scored is stored (so the next scan does not pay for it again); the rest stay 'discovered'.
            legacy = [
                {"company": j.company, "title": j.title, "location": j.location,
                 "url": j.url, "content": j.description_text, "job_key": job_key(j)}
                for j in pending_direct
            ]
            try:
                for i in range(0, len(legacy), 10):
                    chunk = legacy[i: i + 10]
                    scored = score_batch(chunk, resume, config)
                    if scored is None:
                        scoring_failures += len(chunk)
                        continue
                    scoring_failures += len(chunk) - len(scored)
                    for item in scored:
                        update_job_status(item["job_key"], "scored", item["score"], item["reason"])
                        scored_ok += 1
                        scored_by[provider] += 1
                        if item["worth_applying"]:
                            all_scored_jobs.append(item)
            except Exception as score_err:
                logger.error(f"Scoring failed with provider '{provider}': {score_err} — jobs left as 'discovered'")
                errors.append(f"⚠️ Scoring failed: {score_err}")

    state["seen_urls"] = list(seen_urls)
    state["last_scan"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    logger.debug("State saved")

    # Best first. The digest, state/last_scan.json (read by `draft N`) and the CSV all
    # use this order, so digest #N = `draft N` = CSV row N.
    all_scored_jobs.sort(key=lambda x: x.get("score") or 0, reverse=True)
    top_jobs = [j for j in all_scored_jobs if (j.get("score") or 0) >= min_score][:top_n]

    scan_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for item in all_scored_jobs:
        item["scan_date"] = scan_date

    LAST_SCAN_FILE.parent.mkdir(exist_ok=True)
    LAST_SCAN_FILE.write_text(json.dumps(all_scored_jobs, indent=2))
    logger.debug(f"Last scan saved: {len(all_scored_jobs)} total jobs → {LAST_SCAN_FILE}")

    history: list[dict] = []
    if JOB_HISTORY_FILE.exists():
        try:
            history = json.loads(JOB_HISTORY_FILE.read_text())
        except Exception:
            history = []
    existing_urls = {j["url"] for j in history}
    new_entries = [j for j in all_scored_jobs if j["url"] not in existing_urls]
    history.extend(new_entries)
    JOB_HISTORY_FILE.write_text(json.dumps(history, indent=2))
    logger.debug(f"Job history updated: +{len(new_entries)} new entries ({len(history)} total)")

    if too_old:
        logger.info(f"{too_old} job(s) skipped as posted more than {max_age} day(s) ago")

    if scoring_failures:
        logger.warning(
            f"{scoring_failures} job(s) could not be scored (LLM error/quota) — "
            "left as 'discovered' and will be retried next scan"
        )

    elapsed = time.time() - scan_start
    logger.info(
        f"Funnel: fetched {fetched_total} | India {india_total} | already scored {already_scored} | "
        f"pre-filter rejected {prefilter_rejected} | too old {too_old} | queued {queued_total} | "
        f"scored {scored_ok}{_by_model(scored_by)} | failed {scoring_failures} | left for next scan {queued_total - scored_ok}"
    )
    logger.info(
        f"=== Scan complete — {companies_scanned}/{total} companies, "
        f"{len(all_scored_jobs)} jobs found, {len(top_jobs)} top matches "
        f"({elapsed / 60:.1f} min) ==="
    )

    if top_jobs:
        logger.info("Top matches:")
        for j in top_jobs:
            logger.info(f"  [{j.get('score', '?'):3}] {j.get('extracted_title') or j.get('title')} @ {j['company']} — {j.get('reason', '')[:80]}")

    date_str = datetime.now().strftime("%d %b %Y")
    tg = config.get("telegram", {})
    telegram_configured = is_telegram_configured(tg.get("token"), tg.get("chat_id"))

    # Always persist results to CSV when there are scored jobs — this is the
    # durable record regardless of whether Telegram is configured.
    csv_path = _export_to_csv(all_scored_jobs, "scan results") if all_scored_jobs else None

    if errors and telegram_configured:
        error_msg = f"<b>Job Hunt Errors — {date_str}</b>\n" + "\n".join(errors)
        send_telegram(tg["token"], tg["chat_id"], error_msg)

    if not top_jobs:
        logger.info("No matching jobs found today.")
        if telegram_configured:
            msg = f"<b>Job Hunt — {date_str}</b>\nNo new matches today."
            send_telegram(tg["token"], tg["chat_id"], msg)
        return

    msg = format_telegram_message(top_jobs, date_str)
    logger.info("\n" + msg)

    # Telegram is an optional notification on top of the CSV. When it's not
    # configured we simply skip it — no error, the CSV already holds the results.
    if telegram_configured:
        sent = send_telegram(tg["token"], tg["chat_id"], msg)
        if sent:
            logger.info(f"Telegram notification sent. Results also saved to CSV: {csv_path}")
        else:
            logger.warning(f"Telegram send failed — results saved to CSV: {csv_path}")
    else:
        logger.debug("Telegram not configured — skipping notification")
        logger.info(f"Results saved to CSV: {csv_path}")
