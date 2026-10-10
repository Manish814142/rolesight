# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Dates are omitted for pre-1.0 releases that predate this changelog and were
reconstructed from git history.

## [Unreleased]

### Added (2026-10-10, T74 — AI Engineer / Forward Deployed Engineer titles, with a rubric clause for heavy AI)
- Manish: allow these titles, but only when the posting accepts his stack (MEAN, backend; GenAI used in workflows), not when it requires heavy AI such as LangGraph, LangChain, vector databases or "advanced things". **Pre-filter:** `AI / Gen AI / Generative AI / Agentic AI / Applied AI / LLM Engineer` and `Forward Deployed Engineer` titles now match the include list (seniority, intern, test, frontend and platform exclusions still apply; "AI/ML Engineer", "Machine Learning Engineer" and "Data Scientist" are not added). Measured on the saved fetch of 2026-10-08: survivors 1,792 → 1,900 (+108, 0 removed; 80 of the 108 name an Indian place, 18 posted within 7 days, 60 within 30). 28 of the 108 are OpenAI offices outside India (Paris, Tokyo, Singapore…) that the "remote" flag lets through; the rubric caps them (T77).
- **Rubric (rule 8):** a REQUIRED qualification that demands hands-on AI/ML engineering he has not done caps the score at 50: agents or LLM pipelines with an orchestration framework, RAG/semantic search over a vector database, training / fine-tuning / evaluating models, PyTorch / TensorFlow / Hugging Face, MLOps / LLMOps, NLP specialisation, or years of ML experience. Not triggered by "bonus" / "preferred" items, by mere familiarity with LLMs, RAG or function calling, or by using LLM APIs inside backend work. Without it the new titles would flood the CSV: **measured (gemini-3.5-flash-lite pinned, one run, 75 India AI/FDE postings fetched 2026-10-10 with full descriptions, labelled by Claude against his rule in the new `scripts/golden_set_ai.csv`)**: the old rubric passed 23 at 70, 19 of them labelled `no` (precision 17%).
- **Three wordings were measured; the shipped one is the third (v8c).** v8 (first): 3 pass, 2 false positives, but it capped postings that only ask for *familiarity* (DevRev FDE 75, 75, 75 → 45, 45, 45; Notion once 30 for an unrelated location reading). v8b ("hands-on", "familiarity" exception): 5 pass, 3 false positives, allowed found 2 of 9; three runs each: Notion 75, 75, 75; MongoDB 72, 75, 75; Razorpay 90, 45, 45; DevRev 50, 45, 50. v8c (v8b + "bonus"/"preferred" sections never count): on the 43 AI postings scored before the daily quota ended, **16 passes → 2** (the old wording on the same 43 jobs); the two left are Genpact's "AI Engineer 4A" (a Databricks data-engineering role, 85, the same under the old rubric) and HackerRank's FDE (a customer-configuration role, 75).
- **Cost, measured on the original 82 labelled jobs** (v8b, one run; v7's two runs on the same day for comparison): `apply` found 12 of 14 (v7: 14 of 14 in both runs), false positives 0 at 60 and 70, AUC 0.945 vs 0.971 / 0.973 (the CI of the difference includes 0), 3–4 jobs change pass/fail against 0–1 between two v7 runs. The 25 labelled jobs that mention AI items, scored twice under v8c: Thermo Fisher j7 (`apply`, 90 under v7) → 45, 45; MongoDB g8 (`apply`, 90) → 90, 45; Philips g12 (`maybe`, 85) → 75, 45; all others within noise and no `no` job rose to 70. **j7's requirements are RAG, agentic workflows and pgvector/Qdrant vector search: exactly what Manish said to reject, so its old `apply` label (from 2026-10-04, before his rule) probably no longer holds; I did not change it (T59 is his to confirm).**
- **Not measured / caveats.** The final wording's full 75-job run stopped at job 43 when the 500-call daily quota of `gemini-3.5-flash-lite` ran out (19:28 IST; the API said "retry in 10 h"); a full re-run is owed. All 75 labels are one rater's (mine); only 9 postings are labelled allowed, all borderline, so the "allowed found" figures rest on a handful of jobs and the model flips ±30 on them between runs (Razorpay 90, 45, 45). Expect real AI/FDE postings that fit him to be capped some of the time; the cost of the clause is those misses. No held-out AI postings exist yet: the next scans' AI titles are the held-out test. Not run: a real scan with these titles.

### Added (2026-10-10, T26 — Phenom adapter; BCG)
- New `job_hunt/adapters/phenom.py`: Phenom People careers sites that hold their own jobs (most only front a Workday tenant and are scanned through the Workday adapter, see T26's result on the board). Search is `POST {host}/widgets` scoped to `selected_fields.country = ["India"]`, 100 per page; entries carry `host` and `locale` (the site's path prefix, `global/en`); the full description comes from the JSON-LD `JobPosting` of the public job page (`ENRICHERS["phenom"]`). Seed format for `discover`: `BCG | phenom | careers.bcg.com | global/en`.
- Added through the real `autopilot discover --add-file … --merge companies.json`: **BCG** (101 jobs, 96 India, newest posted 1 day ago, 3 pass the pre-filter); `companies.json` is now 224 boards. Run through the real adapter, pre-filter and enrich: 101 unique ids, 3 survivors, descriptions of 8.4–8.6 k characters. Measured 2026-10-10 on the live site; fixtures in `tests/test_phenom.py` follow its real response.
- Not verified: scoring of those three jobs by Gemini. Phenom's list is not newest first (BCG's first page: 2026-10-06, 08-21, 08-20, 08-18, 08-25 …), so the posted-date window never cuts a Phenom fetch short.

### Added (2026-10-10, T02 — posted-date window on by default; the adapters save requests)
- `candidate.max_posted_age_days` now defaults to **7** (`job_hunt/settings.py`; JSON `null` switches it off, `autopilot scan --posted-within N|all` overrides it for one run); the example configs document it with `fetch_workers` and `gemini_scoring_mode`. Measured on the saved fetch of 2026-10-08 (all boards, current pre-filter): 302 of 1,900 survivors are posted within 7 days (205 within 3, 495 within 14), none undated, so a first scan fits the 400-job cap.
- The window now reaches the adapters (Manish: a job outside the window should cost no API call): Workday makes no per-job detail call for an older "N Locations" / "Location Negotiable" job, and Oracle HCM (`sortBy=POSTING_DATES_DESC`), Eightfold (`sort_by=timestamp`) and SmartRecruiters stop paging at the first page that holds only older jobs. A board stopped that way is marked incomplete (T33 closes nothing on it). **Amazon is deliberately not cut:** its `sort=recent` is only roughly by date (measured: 980 places where a later job was newer than the previous one, by up to 192 days; 3 jobs of a 14-day window sat after the first all-older page).
- Measured on the live boards, requests with no window → 7-day window (same in-window survivors in every row but Qualcomm's first run): Qualcomm 58 → 10 (126 s → 20 s), EXL 21 → 5, Bosch 20 → 7, NielsenIQ 5 → 3, Citi (Workday) 62 → 48, JPMorgan 4 → 4, Genpact 83 → 83. Qualcomm's first comparison showed 3 vs 2 in-window survivors; a re-run minutes later gave 3 vs 3 with every in-window job inside the first 40 of 577 (inferred: a posting changed between the two fetches, which ran minutes apart; not proven). Newest-first order checked over whole boards before relying on it: Oracle HCM (4 boards), SmartRecruiters (13) and Eightfold (4) had 0 order violations.

### Added (2026-10-10, T07/T28 — systemd user timers, ready but not installed)
- `scripts/systemd/install.sh` writes `job-hunt-scan.service/.timer` (daily 09:00, `--at HH:MM`, `Persistent=true`) into `~/.config/systemd/user` and enables the timer; `--with-recheck` adds the monthly `job-hunt-recheck` pair (1st of the month, report only); `--uninstall` removes them; `--no-systemctl` only writes the files. **Nothing has been installed**: the tests render into a temp directory and `systemd-analyze --user verify` accepts the rendered units (the real parser; passes). Installing is Manish's call.
- `scripts/monthly_recheck.sh` (T28): copies `companies.json` to `data/recheck/`, runs `discover --recheck --merge` on the copy, and leaves `diff.<date>.txt` and `report.<date>.csv`; the real list is never written (the test hashes it before and after). **Real run (2026-10-10, about 2 minutes by file times, all 224 boards, network only):** `Recheck: 224 -> 224 companies (0 changed)`, empty diff, `companies.json` and its packaged copy byte-identical before and after (SHA-256). The first real run left a stray `verified_companies.json` (discover's default `--out`) in the repository root; the script now passes `--out data/recheck/verified.<date>.json` and the test catches it.

### Removed (2026-10-10, T08)
- `setup_cron.sh` (it installed a cron line that bypassed `run_daily.sh` and wrote to `./scan.log`); the docs point at `scripts/systemd/install.sh`.

### Changed (2026-10-10, T62 — "python" is allowed in job titles)
- Manish: allow "python" for now and decide again on the results. `python` is removed from the title exclusion words (`java` and `golang` stay; he named only python). The seniority, intern, test, frontend and platform exclusions and the include-word requirement still apply: "Staff Python Engineer", "Python Data Scientist" (no include word) and "Java Python Developer" are still rejected (tests).
- Measured on the saved fetch of 2026-10-08 (39,873 jobs, 223 boards) through the real `should_evaluate_job`, before and after: survivors 1,745 → 1,792 (+47, 0 removed); 39 of the 47 were posted within 30 days and 11 within 7. Citi 16, Cisco 7, JPMorgan 4, Motorola Solutions 3, others 1–2. Inferred: about 47 more scoring calls on a first full scan, and a handful a day with a posted-date window. Not measured: what Gemini scores them (an earlier run with the old rubric gave 9 of 32 python-only titles 80+, on 3.1).
- `scripts/measure_prefilter.py` no longer watches "python" (it can no longer block).

### Changed (2026-10-10, T05 — one MIN_SCORE, 70)
- Manish chose `min_score` 70 (measured on the 82 labelled jobs: precision 92% at 70 against 86% at 60; the CSV still lists every score). It now lives in one place: `config.json`'s `candidate.min_score`. The code default is 70 for every reader (`job_hunt/settings.py`; scanner and export used 55 before), the example configs say 70, the `.env` template has no active `MIN_SCORE` line, and `run_daily.sh` no longer exports a value that `.env` overrode (its banner printed 70 while the scan used 60). Manish's own `config.json` is set to 70 and his `.env` line is commented out.
- Checked through the real runner: `./run_daily.sh --limit 1` in a scratch directory (`.env` with the comment, no `MIN_SCORE` in the shell) logs `Min score: 70 | Top N: 5` first; that scan then stopped at loading a resume the scratch directory did not have, which the check did not need. Not run: a Telegram alert at 70.

### Added (2026-10-10, T44 — keyword gaps in `draft`)
- `autopilot draft` also writes `keyword_gaps.txt` in the draft folder and prints its first line: the technologies the posting names that the resume does not ("In the posting, not in your resume (7): Spring / Spring Boot, SQS, AWS Lambda, …") and those in both. No LLM call: `job_hunt/keywords.py` holds a fixed vocabulary of 72 terms with their spellings (C#/.NET/C++ by symbol, Java not inside JavaScript, ambiguous English words such as Go, Spring, React, REST matched case-sensitively; "Express" only as Express.js or next to Node). It is written before the LLM calls, so it exists even if they fail. It does not tell requirements from examples or pluses (that is the scorer's job, T73).
- Checked: on the 82 golden-set postings every sampled hit of the ambiguous terms is the technology (one miss seen: lowercase "springboot"). Real `autopilot draft` in a scratch directory (3.1 wrapper): a language-agnostic Amazon posting → nothing missing, 0 in both (its text names no vocabulary term; the resume has 26); Mastercard "Senior Software Engineer" → 7 missing, 13 in both.

### Added (2026-10-08, T33 — first/last seen and closed jobs)
- `jobs` gains `first_seen`, `last_seen`, `missed_scans` and `closed_at` (added by `init_db`; `first_seen` backfilled from `discovered_at`). After fetching, each scan records what every board returned: returned jobs get `last_seen` and are reopened if closed; the board's other rows get one more missed scan, and `closed_at` is set at `closed_after_missed_scans` (config, default 3). Only boards whose fetch succeeded with at least one job count, so an outage or an empty answer closes nothing. Closed is a flag, not a `status`: scores and the scan lifecycle are untouched; closed jobs leave `output/open_matches.csv` (T39). One log line reports how many were closed.
- **Partial fetches never count as misses** (found in review before the commit): the paged adapters (Workday, Eightfold, Amazon, SmartRecruiters, Oracle HCM) keep earlier pages when a later page fails, stop when their time budget is spent, and stop at a job cap; each such stop now flags the fetch (`adapters.base.mark_incomplete`, per thread, read by `scanner._prefetch_jobs`, which now returns `(jobs, error, incomplete)`). A flagged board's returned jobs count as seen; its other jobs get no miss. So a board always at its cap (Accenture) never closes a job. Measured on all 223 boards (2026-10-10, 30,631 jobs, 304 s): 4 at their cap (Accenture, Bosch, EXL, Kotak Mahindra Bank, 2,000 each) and 77 Workday tenants whose first page failed (Workday was answering HTTP 303 to `community.workday.com/maintenance-page`; such boards return no jobs, so they count for nothing anyway). Why caps matter (reviewer, live): Accenture's 2,000 of 2026-10-08 vs 1,996 today share 1,966; of the 34 gone, 2 of 15 sampled are still live.
- Measured: 1.9–2.0 s per scan on a copy of the production database (30,367 rows) fed the 39,873 jobs fetched 2026-10-08; three such scans would close 3,759 of the 2026-10-04 rows (23 scored). A first version ran > 5 min there: `WHERE ats = ? AND global_id = ?` cannot use the partial unique index (EXPLAIN QUERY PLAN: `SCAN jobs`); repeating the index's condition makes it `SEARCH … USING INDEX`. Churn of capped boards over ~1.5 h: Accenture 3 of 2,000 missing, Amazon 2 of 2,334. Real CLI, scratch directory, `closed_after_missed_scans: 1`: "2 job(s) marked closed" (both Amazon; both URLs answer HTTP 404 on amazon.jobs).

### Added (2026-10-08, T39 — one rolling file of open matches)
- Every scan rewrites `output/open_matches.csv` (atomically, also when it scored nothing): every job in `data/jobs.db` scored ≥ `min_score`, with no `autopilot mark` status (applied, interview, rejected or offer all count as applied), inside that run's posted-date window (undated jobs kept, no window = all), best score first. A Workday "Posted N Days Ago" is aged from the day it was fetched (`prefilter.current_age_days`). The per-scan CSVs are unchanged. Closed jobs cannot be excluded until T33 records them.
- Checked through the real CLI in a scratch directory (3.1 wrapper, cap 1, `--posted-within 1`): the log says `Open matches (score >= 60, not applied, posted within 1 day(s)): 4 → output/open_matches.csv`; the file lists exactly the 4 unmarked rows ≥ 60 of the database (the two marked ones are absent); after `autopilot mark <top row> applied` the next scan's file no longer lists it.

### Removed (2026-10-08, T34 — the JSON state files)
- Scans no longer write `state/last_scan.json`, `state/job_history.json` or `state/seen_jobs.json`, and no module reads them (`grep -rn "last_scan.json\|job_history.json\|seen_jobs.json" job_hunt` → nothing; a test keeps it so). `data/jobs.db` is the one record: `draft N`, `mark N` and `export` read it (T31, T32), and so does the MCP scan summary ("N jobs found, M scored"). The unused "seen URLs" set is gone with `seen_jobs.json`.
- New `scripts/import_json_history.py`: a one-time import of scored jobs that only the old files hold (dry run by default, `--apply` to write; only URLs the database does not know, so the database's own scores win; idempotent). **Not run on the production data** (it writes `data/jobs.db`; Manish decides). Measured on copies of the production files: 203 scored URLs in the JSON files, 158 already in the database, 45 would be imported (20 of them ≥ 70; scored 2026-10-04 with that day's prompt, before the database was cleared); `export --min 70 --days 7` 33 → 53 rows after `--apply`; a second `--apply` imports 0. A first version lost 13 of the 45 (same title, company and location as another opening) to the unique key of id-less rows; imported rows now get their own key (`ats` `import`).
- Checked through the real CLI in a scratch directory with `state/` deleted: a scan (3.1 wrapper, cap 1) left no `state/` directory, and `autopilot export` exported that scan from the database.

### Fixed (2026-10-08, T73 review — rubric v7)
- The T73 rubric (v6) lost an `apply` job the next day: claude-b's review found golden-set g1 (Expedia SDE II) at 50 in 10 of 11 runs on `gemini-3.5-flash-lite` (the pre-T73 rubric: 75–85, same model, same day). Its qualifications ask for any language; Kotlin/Java/C# appear only in "you will build … using languages such as", and v6 read that as a mandate. The T73 entry's "`apply` 14/14 in every run" held for its two runs of 2026-10-07 only. **v7:** rule 4 counts only the posting's requirements or qualifications; languages named only in the responsibilities, or only as examples, are a stack stretch (rule 6, 65–84), not a cap. Everything else is unchanged from v6.
- **Measured 2026-10-08, `gemini-3.5-flash-lite`, 82 labelled jobs, same day:** g1 under v7 75, 85, 85, 85, 85; two full v7 runs vs one pre-T73 run: `apply` 14/14 in all three; false positives at `min_score` 60 **5 → 0, 0**, at 70 **2 → 0, 0** (precision 83% / 92% → 100%); `apply+maybe` recall at 70 89% → 85% / 81%; AUC 0.959 → 0.971 / 0.973 (95% CI of the difference includes 0); the two v7 runs differ by 3.1 points with 0 / 1 pass/fail changes at 60 / 70. Held-out (16 jobs): identical to the pre-T73 rubric. The committed text is byte-identical to the measured one.

### Changed (2026-10-08, T32 — `export` reads SQLite)
- `autopilot export` reads `data/jobs.db` instead of `state/last_scan.json` / `state/job_history.json`. Without `--days`: the jobs scored during the last finished scan (T31's `scans` table), in that scan's CSV order. With `--days N`: every `scored`/`notified` job whose `scored_at` UTC date is on or after N days ago, best score first across scans (the JSON version kept scan order). Location, Posted, Reason, Model (T71) and Application (T38) come from the row. **Worth Applying** uses the `min_score` a scan here would use (`load_config`, only when `config.json` exists; blank otherwise, so export still needs no config or API keys). Not exported any more: structured-scoring sub-score columns (opt-in `scoring_mode: structured`; they were only in the JSON files).
- **Done-when measured:** `export --min 70 --days 7` lists exactly the rows, in the order, of `SELECT url FROM jobs WHERE status IN ('scored','notified') AND score >= 70 AND substr(scored_at,1,10) >= date('now','-7 days') ORDER BY score DESC, scored_at, id` — on the scratch scan database (3 rows) and on a copy of the production database (33 rows).
- **What changes for the existing production data:** the same command from the old `job_history.json` would list 45 jobs. 40 of its 176 URLs (15 of them ≥ 70) are not in `data/jobs.db` at all (scored before the database was cleared on 2026-10-04) and 11 have a different score there. Whether to import them is T34's one-time import.

### Changed (2026-10-08, T31 — `draft N` reads SQLite)
- `draft N` / `#N` (and `mark N`, which uses the same resolver) find job N in `data/jobs.db` instead of `state/last_scan.json`: a new table `scans` gets a row when a scan starts and its finish time when the scan writes its results, and job N is the N-th of the jobs scored during the last finished scan, by score, then scoring order — the order of that scan's CSV and digest, so CSV row N is still `draft N`. A scan that stops half-way does not replace the last finished one. `draft URL` is unchanged. **Until the first scan after this change** there is no finished scan in the database, so `draft N` answers "No scan results found. Run: autopilot scan" (`draft URL` works). With the deprecated non-Gemini providers, `last_scan.json` held only jobs ≥ `min_score`, so N could differ there.
- Checked through the real CLI in a scratch directory: a scan (fallback narrowed to 3.1 by a wrapper, cap 2) wrote `output/jobs_2026-10-08_2.csv`; with `state/last_scan.json` deleted, `autopilot mark 1 none` resolved row 1 (Mastercard R-290601) and `autopilot draft 2` drafted row 2 (Amazon 10571613, "Source URL" in `application_info.txt`), ending "Review, edit, then submit manually".

### Added (2026-10-08, T38 — application tracker)
- `autopilot mark N | URL applied|interview|rejected|offer` records where an application stands, with today's local date, in `data/jobs.db` (new `application_status` / `application_date` columns, added to an existing database by `init_db`; the scanner's own `status` is untouched). `N` / `#N` is job N of the last scan, resolved by the same code as `draft N`; a URL is looked up directly. A later mark replaces the earlier one; `none` clears it. Unknown status, a job not in the database or N past the last scan → message and exit 1, nothing written. No API keys needed, and nothing is sent anywhere.
- `autopilot export` gains an **Application** column (e.g. `applied 2026-10-08`), read from the database read-only and written only when some exported job has been marked; without a database, export works as before and does not create one.
- Checked through the real CLI (no network namespace) in a scratch directory: `mark 1 applied` and `mark <url> interview` → exit 0, both rows carry the status and date while `status`/`score` stay `scored`/60 and 90; `mark 1 hired`, `mark` and an unknown URL → exit 1; `export --days 1` → Application column with the two marks, 6 rows empty. `init_db` on a copy of the production database: 30,367 rows, statuses and score sum unchanged, integrity ok, 0.19 s.

### Added (2026-10-08, T71 — which model scored each job)
- Every stored score names the Gemini model that answered: new `jobs.score_model` column (added to an existing `data/jobs.db` by `init_db`; NULL for rows scored before this and for the deprecated providers), a `model` key in the scorer's results, `state/last_scan.json` and `state/job_history.json`, and the funnel line, e.g. `scored 6 (gemini-3.5-flash-lite 4, gemini-3.1-flash-lite 2)`. The CSV gets a **Model** column only when some job in it was scored by a model other than the default primary (`gemini-3.5-flash-lite`), so a normal scan keeps its 10 columns. Why: T70 measured `gemini-3.1-flash-lite` scoring weak fits ~7 points higher, and a scan falls back to it when the primary fails or is out of quota (T64), so one CSV could mix two calibrations with nothing to show it. No prompt or score change.
- Checked through the real CLI in a scratch directory (`init` copy, three boards, `--posted-within 1`): default config, cap 6 → funnel `scored 6 (gemini-3.5-flash-lite 6)`, 6 rows with `score_model` 3.5, CSV unchanged (10 columns). Primary set to a nonexistent model, fallback chain narrowed to `gemini-3.1-flash-lite` in a wrapper around `job_hunt.main.main` (so no call could reach 3.5 while it was in use elsewhere), cap 2 → two 404s, then `scored 2 (gemini-3.1-flash-lite 2)`, both rows store 3.1 (the model that answered, not the configured one), and the CSV has a Model column. `autopilot export --days 1` on that history → Model column, 6 × 3.5 and 2 × 3.1.

### Changed (2026-10-07, T73 — scoring rubric v6)
- Rubric rule 4 (stack mismatch) caps at **50** instead of 60 — 60 equalled `min_score` 60, so a capped job still passed (Nike's "Java + Spring Boot mandatory" role scored exactly 60) — and fires when the posting *requires* a backend language outside the candidate's stack and accepts none of his for that work. Lists given as examples ("languages such as Kotlin, Java or C#") are not requirements; TypeScript used only for a frontend part does not count as accepting his stack. New rule 8 caps at 50 a posting that *requires* an industry, platform or tool he lacks (video-games industry, embedded, SAP…); preferred items never trigger it. Both encode Manish's rule of 2026-10-07: skip a posting that requires what he doesn't have.
- **Measured on `gemini-3.5-flash-lite`, 82 labelled jobs, two runs each, same day:** false positives at `min_score` 60 3 → **0**, at 70 2 → **0** (precision 88–92% → 100%); `apply` found 14/14 in every run; between two runs 0 pass/fail changes (the old rubric: 3–4); `apply+maybe` recall at 70 81–85% → 81% (the `maybe` jobs that drop require Java or Go); AUC 0.97 → 0.95 (the 95% CI of the difference includes 0). On the 16 held-out jobs it equals the old rubric at 70. An intermediate version (v5) lost 2 `apply` jobs (it read "such as" lists as requirements) and was not kept. The committed text is byte-identical to the measured one.

### Measured (2026-10-07, T70 completed and T60 re-checked on 3.5)
- T70, now with two same-day runs per model: `gemini-3.5-flash-lite` vs `gemini-3.1-flash-lite` on the 82 jobs, committed rubric: a model's two runs differ by 3.2 points (3.5) and 0.7 (3.1); the models differ by 8.0–8.4 points with 11–14 pass/fail changes; at `min_score` 70 both find 14/14 `apply`, with 2 false positives on 3.5 and 10 on 3.1; AUC 0.972/0.973 vs 0.959/0.954. 3.5 stays the primary model. Also measured: 3.5 answers in 1.8 s median, like 3.1.
- T60 re-checked on 3.5 only (the 4 hardest jobs × 5 runs at each temperature): temperature 0 — 2 of 4 jobs spread over 20 points, mean spread 22.5; 0.1 — 3 of 4, 30.0. The earlier "temperature 0 is worse" mixed in ~9 calls answered by 3.1 and does not hold; neither temperature removes the bimodal flips. Default stays 0.1.

### Fixed (2026-10-07, T72)
- The pre-filter accepts Amazon's "Software **Dev** Engineer" spelling (`software\s+dev(elopment)?\s+engineer`). The 2026-10-04 fix only matched "Software Development Engineer", so every "Software Dev Engineer I/II/III" and "Sr. Software Dev Engineer" title — Amazon's most common SDE spelling after it — was rejected before Gemini. Measured on the 34,416 jobs fetched 2026-10-06: survivors 1,060 → 1,115, all 55 added are Amazon SDE roles (several on the same team as golden-set `apply` job g3), 0 removed; no labelled `apply`/`maybe` job is rejected; "Software Dev Engineer, Frontend", "Principal Software Dev Engineer" and "Software Dev Manager" stay rejected.

### Added (2026-10-07, T70 — which Gemini model)
- `scripts/score_golden_set.py --model M` scores with one model and no fallback (a failed call is `None`, never the other model's answer), `--arms current` scores only the chosen prompt(s) (82 calls a run), and `--from-scores` takes several files and prints a job-by-job agreement section (mean |difference|, share within 10 points, pass/fail changes at each MIN_SCORE). `scripts/measure_score_variance.py` takes `--model` and `--ids`.
- **Measured** (current prompt, 82 labelled jobs; 3.5-flash-lite from T58's saved run of 2026-10-06, which the old `./scan.log` shows ran before 3.5's quota errors began at 19:52; 3.1-flash-lite twice on 2026-10-07, 164/164 answered): ranking is the same (AUC 0.961 vs 0.959 / 0.954); 3.1 is steadier (its two runs differ by 0.7 points, no pass/fail change) but scores weak fits higher (+7.5 on `no` jobs, +5.8 on `maybe`, +0.7 on `apply`); between the models 10–11 jobs change pass/fail. At MIN_SCORE 70 both find 14/14 `apply` jobs, with 2 false positives on 3.5 and 10 on 3.1; at 80 and above the two are identical. 3.5 has only one run so far (its quota was reached on 2026-10-07): the comparison is completed on 3.5 later.
- Golden set: Manish relabelled g27 (Amazon "SP Support", which requires 3+ years in the video-games industry) from `apply` to `no` (`label_source` `manish`): he skips postings that require a skill or domain he lacks. With it, the current prompt finds 14/14 `apply` jobs at MIN_SCORE 60 and 70 (T58's saved scores).
- Found while answering this: the T60 variance runs of 2026-10-06 were partly answered by 3.1 (about 9 of 200 calls, after 3.5's daily quota ran out at 19:52), so T60 is back in review for a 3.5-only re-check.

### Fixed (2026-10-07, T67)
- `autopilot discover --help` prints its usage. Before, `discover` ignored any argument it did not know, so `--help` or a mistyped flag (`--add-flie paste.txt`) silently ran a full discovery of every seed in `scripts/company_seeds.txt` (~1,100 names, 40 workers, minutes of network) and wrote `discovery_report.csv` / `verified_companies.json` in the current directory. Now an unknown or value-less argument exits 1 with a message. Real CLI: `discover --help` → usage, exit 0; `discover --add-flie x.txt` → "unknown or incomplete argument '--add-flie'", exit 1. Every flag used in the docs (`--add`, `--add-file`, `--census`, `--emit-seeds`, `--merge`, `--no-recheck`, `--out`, `--recheck`, `--report`, `--seeds`, `--workers`) is still accepted.

### Fixed (2026-10-07, T66)
- `pyyaml` is a declared dependency (`pyproject.toml` and `requirements.txt`). `discovery`, `harvester` and `company_builder` import `yaml`, but nothing declared it, so on a fresh `pip install -r requirements.txt` `autopilot discover` (the company-list tool) died with `ModuleNotFoundError: No module named 'yaml'` (measured in a fresh virtualenv while verifying T51; the dev `.venv` had PyYAML only because it was installed by hand). After: a fresh Python 3.11 virtualenv from `requirements.txt` runs `python -m job_hunt discover --add "Stripe"` to exit 0 (verified, 731 jobs, 44 India). `tests/test_packaging.py` now fails if any third-party import in `job_hunt/` (other than the optional anthropic / MCP ones) is missing from either file. Also corrected `docs/01-install.md`, which still said `google-genai` was optional.

### Fixed (2026-10-07, T65)
- Workday: a list item whose location is the placeholder "Location Negotiable" now gets the same detail call as "N Locations" when its title can pass the pre-filter, so its real cities decide the location test (it was always rejected as not India). Found while verifying T49: 498 of Accenture's 2,000 India-search results carry it; 8 of 12 sampled were in India by the detail endpoint; 7 of the 498 have a candidate title. Live Accenture fetch through the adapter after the change: 7 detail calls, 5 resolved to US offices (still rejected), **2 resolved to Bengaluru/Hyderabad and now pass** (pre-filter passes 471 → 473); 245 s (219 s before; network noise). `tests/test_adapters_extra.py` has a test for it. Also: ARCHITECTURE.md still said the Workday cap was 500 (T49 raised it to 2,000).

### Fixed (2026-10-07, T64)
- A Gemini model whose **daily** quota is gone is skipped until its reset instead of being retried on every job. Measured 2026-10-07 with `gemini-3.5-flash-lite` at its 500/day limit: each job still sent it two requests and slept 5 s (Google's "retry in 23h20m6s" does not match the per-minute "retry in N s" pattern) before `gemini-3.1-flash-lite` answered, about 6.5 s per job, ~43 min on a 400-job run (inferred). Now a 429 whose quota id names a per-day limit marks the model until the `retryDelay` Google sends; when every model is out, scoring raises `GeminiQuotaExhausted` without a request, so the T03 breaker stops at once. Per-minute 429s are retried as before. Live, same day, two golden-set jobs with the default config: 1 request to 3.5 (logged "skipped for the next 22.8 h"), 2 to 3.1, the second job in 1.8 s; `autopilot draft` logged the skip once too. `tests/test_daily_quota.py` (5 tests, including one through `run_scan`); T03's tests now use a per-minute 429.
- T64 follow-up (2026-10-07): the skip ends at the next midnight Pacific at the latest. Google's docs say per-day quotas reset then; its own `retryDelay` did not: at 00:40 UTC the 429 said ~23 h 20 min, yet `gemini-3.5-flash-lite` answered again at 08:05 UTC (measured), so a process running across the reset would have skipped the primary for ~16 extra hours.

### Fixed (2026-10-07, review of T03 / T17 / T58)
- `scripts/measure_prefilter.py` counted a job posted on the day of the fetch as old: age 0 is falsy, so `(age or 9999) <= 30` was false (407 of the 34,416 jobs fetched 2026-10-06 were posted that day). Recomputed as of 2026-10-06 on the same fetch: python-only blocks 33, of which **24** (not 21) were posted in 30 days; java 93, **85** (not 75). The blocked counts themselves were right.
- Tests only: T58's rule-2 assertion passed even with the cap removed (`a and b or c`); batch-mode scoring now has a test for T03's quota breaker (removing the batch breaker failed no test before).

### Added (2026-10-06, T26/T27 probes)
- `companies.json` 220 → 223 (also `job_hunt/data/companies.json`): **Cisco** (`cisco.wd5/Cisco_Careers`: 320 jobs, 254 in India, 51 pass the pre-filter), **Fiserv** (`fiserv.wd5/EXT`: 37 / 30 / 1) and **DuPont** (`dupont.wd5/Jobs`: 4 / 1 / 0, a marginal board that meets the acceptance rules). Found by the Phenom probe (T26): the Phenom careers sites of Cisco, DuPont, Fiserv, HPE, Philips and WBD return a Workday `applyUrl` for every sampled job, so the Workday adapter that already exists reads them (added with `discover --add-file --merge`; full fetch of the three through the scanner's `_prefetch_jobs` took 46 s, no warnings). The Phenom `widgets` endpoint itself is public, but the only Phenom-native census board with India jobs is BCG (91 India jobs, 2 pass the pre-filter): no adapter written, **decision for Manish** (T26).
- **Darwinbox (T27) rejected**: no plain-HTTP job endpoint. On valid tenants every `/ms/candidateapi/*` path answers 500 "Error while getting tenant info" (five attempts: paths, GET/POST, Origin/Referer/cookies, even the Turnstile site-key call); other tenants are behind Cloudflare 403. Evidence is in the board's Rejected table.
- **Side effect worth knowing:** `discover --merge` re-checks every existing entry, and this run's re-check flagged **Gojek** (`lever/GoToGroup`) as "no open jobs". Fetched directly afterwards the board has 42 jobs, **all in Jakarta, none in India** (the first call had timed out), so the entry no longer meets the "≥ 1 India job" rule. I restored it (this change is additions only); whether to remove it is Manish's call or the monthly recheck's (T28).

### Added (2026-10-06, T25)
- **Eightfold adapter** (`adapters/eightfold.py`): the careers-site API the Eightfold pages call themselves, `GET {host}/api/pcsx/search?domain={domain}&location=India&sort_by=timestamp` (10 per page; title, locations, epoch `postedTs`) and `/api/pcsx/position_details` (full HTML description, filled by the enricher for survivors). Entries carry `host` and `domain`; `discover --add-file` takes `Name | eightfold | host | domain` lines and verifies them through the real adapter. The earlier "Eightfold is 403" note was half right: `/api/apply/v2/jobs` answers 403 ("Not authorized for PCSX"), `/api/pcsx/search` answers 200. Of the 8 census sites I tried, 3 exposed it (Micron, UKG, Twilio, PayPal responded; BNY Mellon, HP, Citi, Capital One did not); guessed tenants added Qualcomm, Morgan Stanley and Lam Research.
- **Found by running it for real, not by the fixtures:** (1) Eightfold answers HTTP 429 to a few quick requests (3rd page in a back-to-back run); the adapter pauses and retries 3/6/12/24/48 s and spaces pages by 1 s. (2) `sort_by=relevance` paging is unstable: a full Qualcomm traversal returned 583 of the 594 ids it reports (pages 400, 520 and 530 repeated ids; 61 requests), while `sort_by=timestamp` returned 594 of 594; the adapter now sorts by time. Real adapter, final: Qualcomm 594 jobs / 594 unique in 154 s, no warnings. That is one traversal per sort order, not a stability proof.
- `companies.json` 216 → 220 (also copied to `job_hunt/data/companies.json`): **UKG** (89 India jobs, 11 pass the pre-filter), **Lam Research** (110, 2), **Qualcomm** (594, 15), **Morgan Stanley** (115, 2), all via `discover --add-file --merge` (216 existing entries still valid, nothing removed). Not added: Micron, Nvidia, PayPal and Twilio also answer on Eightfold but are already in the list (Workday / Greenhouse), so adding them would score the same jobs twice. Scan path checked without Gemini: the scanner's own `_prefetch_jobs`, pre-filter and `_enrich_jobs` on UKG, Lam Research and Morgan Stanley → 30 s, 15 survivors, descriptions filled 15/15 (3,352 to 6,754 characters). **Not run:** a full `autopilot scan` with scoring on these boards.

### Changed (2026-10-06, T43)
- `autopilot harvest` refuses to overwrite an existing output file unless `--force` is given (its default output is the curated `companies.json`; exit code 2, nothing written), and it no longer re-adds the boards removed on evidence: `harvester.EXCLUDED_BOARDS` lists ashby/navi, ashby/bounce, personio/edelweiss, personio/josh and the SmartRecruiters stubs of NoBroker, Upstox, Turtlemint and Whatfix (matched on the verified board's ats and slug, derived from the CLAUDE.md removal list and the real `india.yml` names). Eat Club (0 jobs) and Walmart (Workday HTTP 422) are not listed: harvest already drops a board without jobs or one that does not answer. `validate` is unchanged and still rewrites `companies.json` in place. Checked with the real command in a scratch directory holding a `companies.json`: exit 2, the file's SHA-256 unchanged; and `run_harvest` with stubbed HTTP drops ashby/navi while keeping a control company. Not run: a real `harvest` against the network.

### Changed (2026-10-06, T23)
- Workday: the "N Locations" detail call (one HTTP request per job) is no longer made for a job whose title the pre-filter rejects (`prefilter.title_is_candidate`, the same title test `should_evaluate_job` runs first, so such a job is rejected whatever its locations). Measured with the new `scripts/measure_workday_tenants.py` (all 79 Workday tenants, 8 workers, real network, before the change then after): detail calls **1,039 → 48** (991 of the 1,039 had gone to title-rejected jobs); wall clock **534 s → 255 s**; tenants over 60 s **12 → 4** (Accenture 252 → 255 s, Genpact 139 → 135 s, Citi 268 → 113 s, Amgen 121 → 106 s: all paging-bound, not detail-bound); Salesforce 271 → 23 s, Nvidia 145 → 55 s. Survivors are identical for 78 of 79 tenants (1,003 → 1,008 in total); the one difference is Danaher, which returned HTTP 502 on its first page in the "before" run (0 jobs) and 187 jobs / 5 survivors in the "after" run. Side effect: a skipped job keeps "N Locations" as its location, so the funnel's `India` figure no longer counts those jobs (inferred: up to ~990 fewer on a full scan; the survivors are unaffected). The two runs were ~30 minutes apart on a live network, so single-tenant timings carry noise.

### Added (2026-10-06, T37)
- CSV column **LinkedIn people**: a link to a LinkedIn people search for `<company> software engineer` (`https://www.linkedin.com/search/results/people/?keywords=…`, percent-encoded by `exporter.linkedin_people_search_url`), for finding someone to ask for a referral. Checked: `tests/test_exporter.py`, and a CSV written by the real `autopilot export` for five companies (including `Ben & Jerry's, Inc. #1?` and `Société Générale`) parsed with `urllib.parse` gives back exactly `<company> software engineer` as the only query parameter. **Not verified:** that LinkedIn opens and shows people for this URL (it needs a logged-in session; no browser here). Column positions shift again; read the CSV by header name.

### Changed (2026-10-06, T36)
- The CSV no longer has the always-empty **Stack** and **Region** columns. Region was never set by any scorer (only old test fixtures had it); Stack is now written only when some job has one (the deprecated non-Gemini scorer returns it; the Gemini path does not), like the structured-scoring sub-score columns. Dropped rather than filled: adding `stack` to the Gemini scoring schema changes the scoring prompt and would need re-measuring against the golden set. A default Gemini scan's CSV has 9 columns. Checked through the real `autopilot export` on a `last_scan.json` shaped like a Gemini scan: the header is Company, Role, Location, Posted, Application URL, Score (%), Reason, Worth Applying, Scan Date, and no column is empty. Column positions changed: anything reading the CSV by position (not by header name) breaks.

### Fixed (2026-10-06, T18)
- Four entries were headed 2026-10-05; the commits that added them (04521db, 5f1be31) are dated 2026-10-04, and `git log` has no commit on 2026-10-05 at all. The headings, the two measurement dates inside the entries (Amazon's 2,329 India roles; the end-to-end funnel) and the same dates in five source/test comments now say 2026-10-04. The only evidence is the git author dates (+0530); if the machine clock was off when the commits were made, these dates are off with it. Every dated heading now equals the date of the commit that introduced it (checked with `git blame` on each heading line); the release headings match their tags.

### Changed (2026-10-06, T16)
- The DEBUG log moved from `./scan.log` to `data/autopilot.log` (`JOBNOTIFY_LOG` still overrides) and rotates at 5 MB, keeping 3 older files (it was a plain, ever-growing file; 14.5 MB in the repo root after a day of testing). `data/` is created if missing. The adapters, scorer and other `job_hunt.*` loggers now share the handlers: their warnings (e.g. `greenhouse fetch failed for <slug>`) reach the log file, which they never did, and still print once on the console (checked in a scratch directory through the real `import job_hunt.scanner`: warning 1× on the console and 1× in `data/autopilot.log`, debug line in the file only, nothing on stderr). `run_daily.sh` still writes its own `data/scan.log` (console output of scheduled runs). An old `./scan.log` is left in place, no longer written; `setup_cron.sh` still redirects to `./scan.log` (T08).

### Fixed (2026-10-06, T15)
- The test suite no longer writes to the repo's `scan.log`. The log path comes from `JOBNOTIFY_LOG` (default `./scan.log`, unchanged for real runs) and `conftest.py` points it at a temporary directory, removed when pytest ends, before `job_hunt` is imported. Measured: `stat -c %s scan.log` → 14,574,498 bytes before and after a full `pytest` + ruff + mypy run (the file had grown from 2.2 MB to 14.5 MB today from repeated runs). `tests/test_log_path.py` checks the env var and that the live logger's file is outside the repo.

### Fixed (2026-10-06, T63)
- The `anthropic` provider no longer raises `TypeError` on every call: `Messages.create` in the installed SDK (1.11.0) has no `temperature` parameter, and `_chat_with_anthropic` always passed one. It now sends `temperature` only when the SDK's `create` accepts it (older SDKs, which `pyproject.toml` still allows, keep the scorer's 0.1). Measured: before, `chat_with_llm({"llm_provider": "anthropic"}, …)` pointed at a dead local port → `TypeError`; after → `APIConnectionError` (the request is built and sent). `tests/test_anthropic_provider.py` binds the call to the installed SDK's real signature. **Not verified:** a real Anthropic API response (no key here), and `claude_cli` was not run; CLAUDE.md no longer says these providers "still work".

### Fixed (2026-10-06, T52)
- The non-Gemini scoring path (`llm_provider: anthropic` / `claude_cli`, deprecated) stores what it scores: each job the model scored becomes `scored` with its score and reason in `data/jobs.db`, so the next scan does not pay for it again (before, every row stayed `discovered` and the whole list was re-scored each day). Jobs scored below the threshold are stored too; a job the model left out, gave no score, or whose call failed stays `discovered` and is retried (never a made-up 0). The funnel line now counts these jobs (it printed `scored 0` on this path). `scanner.score_batch` returns every parsed result (`None` when the call failed) and `score_jobs` filters it, so its output is unchanged; the CSV and `last_scan.json` still hold only the jobs the model marked worth applying to. Checked with `tests/test_legacy_scoring.py`, which stubs only `chat_with_llm` and runs the real parse, `run_scan` and SQLite twice; no real provider was called.

### Changed (2026-10-06, T55)
- Packaging describes this fork: `pyproject.toml` (description, keywords without `openrouter`, the upstream `[project.urls]` removed), the `Dockerfile` (no TinyFish/OpenRouter variables, `GEMINI_API_KEY`, no upstream source label), `smithery.yaml` (Gemini key and provider instead of TinyFish/OpenRouter) and the `server.json` description. `server.json` / `glama.json` keep the upstream registry identity fields. `tests/test_packaging.py` fails if any of these names TinyFish or OpenRouter again. `docker build` was not run (no Docker here).

### Fixed (2026-10-06, T51)
- `google-genai` (the default Gemini provider) is a core dependency in `pyproject.toml` and `requirements.txt`; before, `pip install -r requirements.txt` gave a scanner whose every scoring call failed ("google-genai is not installed"). `openpyxl` (imported nowhere) is dropped from `requirements.txt`; the `gemini` extra is kept as an empty alias. The minimum is 2.28.0, the version tested; older ones are untested. Checked in a fresh virtualenv: `pip install -r requirements.txt` → google-genai 2.28.0, and `llm_utils._get_genai_client_and_types` builds a client from the repo code.

### Fixed (2026-10-06, T50)
- `autopilot init` ships the curated 216-company list (it copied 140 careers-URL-only upstream entries that could only be scanned through TinyFish, so a new user's first scan fetched nothing) and a config and `.env` template without TinyFish, OpenRouter or the legacy `search_*` fields; the docs say TinyFish and OpenRouter were removed. `tests/test_packaged_defaults.py` fails if the packaged list drifts from `companies.json`: after `discover --merge`, copy `companies.json` to `job_hunt/data/companies.json`. Checked with the real CLI in an empty directory: `init` → 216 companies, all with an ATS, no TinyFish/OpenRouter keys in `config.json`; `scan --limit 3 --posted-within 1` with those keys unset → exit 0, `fetched 2321 … scored 11 | failed 0`.

### Removed (2026-10-06, T42)
- The legacy TinyFish careers-page scanner (`discover_job_urls`, `fetch_job_details`, the URL regexes, the `tinyfish` client in `run_scan`), the OpenRouter provider (`chat_with_fallback`, `llm_provider: openrouter`, `OPENROUTER_*` settings; a config that still names it now fails with a clear message) and the dead `notifier.send_whatsapp` (T54) are deleted, and `tinyfish` and `openai` are no longer dependencies. `anthropic` and `claude_cli` providers and `score_jobs` (their scorer) stay. A company with no supported ATS is skipped with a warning; a company that only has a `careers_url` is now scanned when its ATS can be detected from it (it was silently routed to the TinyFish path). A scoring exception in the non-Gemini path is logged and no longer aborts the scan.
- **Test isolation (found while doing this):** a full run reached the *real* Gemini API (genuine 429s in the log), because `load_dotenv(override=True)` in one test put the real key into the process environment for every later test. `conftest.py` now restores the environment after each test and blocks the real Gemini client unless a test stubs it; `tests/test_isolation.py` pins both.

### Changed (2026-10-06, T40)
- `autopilot draft` no longer uses TinyFish. The job description comes from the database (T29 stores it for queued jobs); `--jd-file FILE` takes a pasted description for a job the database doesn't have, and the error says so. The prompts get the whole description (up to 20,000 characters; it was cut at 4,000, where requirements often start). A URL ref names the output folder after the stored company. `db.get_job_by_url` looks a job up by URL. Real CLI run (`python -m job_hunt draft 1`, TINYFISH_API_KEY unset, real Gemini, scratch directory from a real scan): exit 0, resume, cover letter and application info written, the letter citing details only present in that posting.

### Fixed (2026-10-06, T14)
- `autopilot draft` sends the whole resume to the cover-letter prompt (it was cut at 2,500 characters, dropping Projects and Education; the scorer got the full resume since cd5df8e).

### Added (2026-10-06, T60)
- `scripts/measure_score_variance.py` runs the labelled jobs N times and reports spreads and decision flips; `gemini_temperature` (default 0.1, unchanged) is a config key so it can be tried. **Measured (real Gemini, 20 hardest labelled jobs × 5 runs, 200 calls):** at 0.1, 2 of 20 jobs spread over 20 points (mean spread 6.0) and 2 / 3 crossed MIN_SCORE 60 / 70 between runs; at temperature 0, 4 of 20 (mean 8.2) and 4 / 4. So temperature 0 is worse and stays unused. Re-scoring the 45-80 band twice and taking the median would cut a single run's disagreement with the job's majority decision from about 3-4% to 2-3% (resampled from the 5 runs), for roughly two extra calls on each borderline job: not adopted. The ~50-point flips seen earlier (Amazon "SP Support" [30, 30, 30, 85, 88]) belonged to older prompt versions: under the current prompt it scores [45, 45, 40, 45, 45]. **No scoring behaviour changed.**

### Added (2026-10-06, T35)
- The end-of-scan log gets one funnel line: `Funnel: fetched N | India I | already scored A | pre-filter rejected R | too old T | queued Q | scored S | failed F | left for next scan L`. Real CLI run on 3 companies with `--posted-within 2` (real Gemini, scratch directory): `fetched 2325 | India 2156 | already scored 0 | pre-filter rejected 2078 | too old 235 | queued 12 | scored 12 | failed 0 | left for next scan 0` (2,325 = 2,078 + 235 + 12). `prefilter.location_is_india` is now the one India-location test.

### Added (2026-10-06, T29)
- The `jobs` table keeps each posting's `location`, `posted_at` and `description` (idempotent `ALTER TABLE` in `init_db`; existing rows are untouched, new columns start empty). Queued jobs get the description the scorer saw, after the enrich step, so a score can be audited and redone; `skipped` rows keep location and date only (30,000+ descriptions would add ~150 MB for nothing). `db.update_job_details` fills an existing row. Checked on a copy of the production database: 30,367 rows → 30,367, statuses and the score sum unchanged, `integrity_check` ok, 0.18 s.

### Added (2026-10-06, T41)
- Structured scoring, opt-in (`"scoring_mode": "structured"`; the default stays the single-score prompt). The model reports facts and sub-scores (stack, role, seniority and location fit, minimum years asked, accepts-candidate-stack, onsite-outside-India, aimed-at-freshers); code computes the score as a weighted mean (35/25/25/15) and applies the caps (30 onsite abroad, 40 unsuitable role, 50 for 6+ years or freshers, 60 stack outside the candidate's) deterministically. Sub-scores and the cap that bit go to the CSV (columns appear only when a run produced them) and into the reason; the database is unchanged. One job per call: `gemini_scoring_mode: batch` is ignored in this mode. `scripts/score_golden_set.py --structured` adds it as an arm.
  **Measured on the 82 labelled jobs, one run each (real Gemini):** ranking is unchanged (AUC 0.950 vs 0.948 for the current prompt); ties at the top split better (scores ≥ 85 take 8 distinct values instead of 3; biggest tie 7 instead of 10); `min_years` matches a regex on the posting in 65 of 66 comparable jobs. **But calibration is worse:** precision at MIN_SCORE 60 is 61% (18 false positives) against 86% (4), and at 70 it misses 2 of 15 `apply` jobs (13/15 against 14/15). The stack flag is as uneven as the old rubric rule: Expedia ("languages such as Kotlin, Java or C#") and Toast ("…or another OO language") are flagged as a stack mismatch, while Tower's required Rust is not. So it is not the default; after three prompt-level iterations that moved calibration but not ranking, the weights were not tuned further. Single run per job (T60).

### Fixed (2026-10-06)
- T04: at most `max_jobs_to_score_per_run` jobs (default 400; 0 = no cap) are scored per run, newest first by posted date (undated jobs count as newest, so they are never starved); the rest stay `discovered` and are scored on the next scan. The cap is applied before the description-enrich step, so detail calls are only paid for jobs that will be scored. 400 is a guess against the ~500 calls/model/day free tier. Tested through the real `run_scan`: 600 pending → the 400 newest scored, 200 `discovered`.
- T03: scoring stops when the Gemini quota is gone. `llm_utils` raises `GeminiQuotaExhausted` when every model in the fallback chain fails with a 429/quota error (mixed failures, e.g. one 500, are not reported as quota); the scorer flags it on the result; the scanner (single and batch mode) stops after `QUOTA_BREAKER_THRESHOLD` = 3 consecutive such jobs and logs how many are left as `discovered`. A job that scores resets the streak. Before: each remaining job burned ~20-30 s of retries (inferred from the retry waits). Tested with a stub that always returns 429 for 50 jobs: 12 calls (3 jobs × 2 models × 2 attempts), all 50 stay `discovered`. Not tested live: the quota was not exhausted.
- T49: Accenture added (216 companies). Its Workday list API leaves `locationsText` empty and puts the city in the second bullet field, so every Accenture job reached the pre-filter as "Not specified" and `discover` rejected the tenant as "no India jobs"; the adapter and `discover` now share one `item_location` (blank text → bullet field; never guessed from the URL, whose slug is the job title at some tenants). The Workday cap rose 500 → 2,000: Accenture's 2,000 India results come in arbitrary order and 341 of them were posted in the last 7 days, only 41 of those within the first 500. Measured: Accenture 2,000 jobs in 264 s, 470 pass the pre-filter (418 are titled just "Custom Software Engineer"), 36 posted in the last 7 days. Sony's and Western Digital's "no India jobs" were checked and are correct (Sony's Workday has no India location; Western Digital's SmartRecruiters board has 1 India posting of 331; its Workday site was not found).
- T17 (measurement): `scripts/measure_prefilter.py` counts what the pre-filter lets through and which language words block India jobs on their own (measured 2026-10-06, 34,416 jobs: python 33, java 93, golang 5, react/angular 6, frontend 8; seniority words ~600). It changes no behaviour; the decision on python/java is T62.
- T11: the pre-filter accepts "Computer Scientist" titles (Adobe's engineering ladder), still subject to the exclusions (Architect, Java, C++, Frontend, Staff/Principal/Lead). Measured: Adobe's 14 India postings, 1 → 8 pass; survivors 1,053 → 1,060.
- T61: the pre-filter rejects titles naming C++, embedded, firmware, kernel, GPU/CUDA, FPGA/Verilog, Rust, Ruby or PHP. Measured on 34,416 jobs: survivors 1,109 → 1,053 (56 fewer scoring calls per full scan), 0 such titles remain, no labelled apply/maybe job is rejected.
- T12: the pre-filter rejects CRM / ERP / BI / RPA platform roles by title (Salesforce, ServiceNow, SAP/ABAP, Workday, Dynamics/D365, Oracle EBS/HCM/CPQ, Power BI/Platform/Apps, Tableau, Informatica, RPA, mainframe, Zuora, Boomi…). Matched on the title only, never the company; "CRM" alone is left to the scorer. Measured on the 34,416 jobs fetched 2026-10-06: survivors 1,191 → 1,109 (82 fewer scoring calls per full scan), 0 platform titles remain, and none of the labelled apply/maybe jobs is rejected.
- T58: rubric rule 7 caps roles aimed at freshers / new graduates / 0-1 years at 50, judged by the experience the posting asks for and not by the title (Amgen's "Associate Software Engineer" asks 2-6 years, "Sr Associate" 4-9; Thermo's "Software Engineer I" asks 3+). Measured (real Gemini, 82 labelled jobs): the two Hevo fresher roles 90 → 45-50; Graviton new-grad, Thermo and HPE junior roles stay ≤ 45; the three controls (Amgen Sr Associate full stack 90, Thermo "Engineer I" 3+ yrs 90, Amgen 2-4 yrs 72-75) are untouched. Adding the rule exposed a second misfire, fixed in the same change: rule 2 capped ServiceNow's own software engineers as "ServiceNow platform administration" (2 of 5 runs at 35-40); it now says to judge the work, not the employer's name (0 of 5). Seven junior-role cases were added to `scripts/golden_set.csv` (82 rows).
  **Measured limit:** one posting (Amazon SDE II "SP Support", with a stray "3+ years of Video Games Industry" requirement) scores [30, 30, 30, 85, 88] across five runs of the *same* prompt, and 30-45 under the new one. So run-to-run noise on ambiguous postings is up to ~55 points (the earlier 3.3 was for clear ones), and differences of one or two jobs on this set mean nothing.
- T57: the Amazon adapter uses the API's full `description` (HTML stripped, then the qualification bullets) instead of `description_short`, which Amazon cuts mid-sentence at 202 characters. Live: median description 1,244 → 3,871 characters over 2,295 India postings; falls back to the stub when `description` is empty. The 23 already-scored Amazon rows in `data/jobs.db` were reset to `discovered` (and their entries dropped from `state/job_history.json`) so the next scan scores them on the full text.

### Docs (2026-10-04)
- Documentation rewritten to the current direct-ATS + Gemini pipeline (it still described upstream's TinyFish + OpenRouter careers-page scanner).
  - **README:** overview, features, how it works (with the first real scan's measured funnel), current status and known gaps, commands, config, outputs, the company list, layout.
  - **`docs/01`–`09`:** rewritten. `05-integrations.md` was renamed `05-outputs-and-notifications.md`, and now covers the CSV, DB statuses, state files, logs, export, drafts and Telegram.
  - **Other pages:** ARCHITECTURE.md brought up to date (enrich step, limits, known limitations with task IDs). SETUP.md is now a pointer to `docs/01`. CONTRIBUTING, SECURITY and PRIVACY were rewritten for the fork, and PRIVACY lists every outbound host in the code. The MCP skill was updated, and CLAUDE.md got factual corrections only.
- Documented commands were run as written: `autopilot --help`, `export --min 101`, the `fetch_company_jobs` one-liner, and an MCP stdio client listing the three tools. Six findings went to the `docs/tasks.md` Inbox (T51–T56).

### Fixed (2026-10-04)
- T48 (review fix, finished by Claude): the scoring prompt carries `SCORING_RUBRIC` anchors (cap ≤ 30 onsite/work authorisation outside India; ≤ 40 unsuitable roles; ≤ 50 for 6+ YOE; ≤ 60 for a mandatory non-Node stack; 85+ only when stack, seniority and location all fit). The first version's evidence was circular (labels set by the build script from old scores; `--dry-run` scores from a rule-based simulator) and is withdrawn. **Replaced the instrument:** `scripts/golden_set.csv` is now 75 real postings (59 `dev`, 16 `held-out`) with Claude's labels, each with a `label_source` and a one-line reason — **single rater, not confirmed by Manish; the report says so until every row says `manish`** — and `scripts/score_golden_set.py` scores every job with the rubric off and on and prints precision, recall, AUC, ties and a bootstrap CI. The old builder fetched the wrong Amazon page and stored one unrelated description on 6 jobs; it is deleted and a test guards against shared descriptions. **Measured on 75 jobs (real Gemini, same text, rubric off vs current):** at MIN_SCORE 70 false positives 7 → 4 (precision 77% → 85%), every `apply` job still passes (13/13), `apply+maybe` recall 92% → 88%; ranking quality is unchanged (AUC 0.955 vs 0.956, 95% CI of the difference [-0.028, +0.029]); the biggest tie among scores ≥ 85 is 11 → 10. So the rubric moves calibration; it does not rank better, and ties need sub-scores (T41). **Rule 4 was wrong in the committed version:** it capped postings that accept a language on the resume (Hotstar "Java, Golang, or Python", Toast "Kotlin, Java, or another OO language" fell to 58, so 2 of 11 `apply` jobs were lost). Its wording now says when it does not apply (revised text: recall back to 11/11 on the dev set, false positives 5 → 3 at 70). The "avoid clustering at 90" text was removed: it measurably did nothing. Both changes were evaluated on the same dev set that exposed them; on the 16 held-out jobs (only 4 positives) the revised prompt is not distinguishable from no rubric. Known gaps, not fixed here: fresher-level roles (Hevo "Associate SDE") score 88–90 under every prompt (T58); Amazon descriptions are cut to a 202-character stub (T57).
- T30: deduplicate by ATS job ID (`global_id`) rather than title+company+location hash. Separate openings with the same title at the same company and location are now stored as independent rows in SQLite and evaluated by Gemini. Migrates `jobs` table schema to index on `(ats, global_id)` with fallback to `canonical_hash`. Existing scored rows are preserved. Review fix: the first migration rewrote every Workday `global_id` to `workday:<company display name>:…` while the adapter emits `workday:<tenant>:<requisition>`, so none of the 101 scored Workday rows in the production DB (0 of 16 live jobs checked) would have been found again — they would have been re-scored and duplicated. Workday ids are now derived from one function (`workday_global_id`) used by both the adapter and the migration, repaired once per database (`PRAGMA user_version`), and the legacy dedupe keeps the scored row.
- T47: fix Workday paging repeats. The CXS adapter now reads `total` from the first response and stops when `offset >= total`, stops immediately if a page yields no new `externalPath` entries, and deduplicates postings by `externalPath`. Unit tests verify a looping page stops within 2 requests and at `total`. Live check: Sabre 40 distinct jobs (was 500 rows with 40 distinct URLs), Warner Bros Discovery 39 jobs, Danaher 200 jobs, each returning rows == distinct URLs.
- T10: `draft N` opens digest job #N. Scan results are sorted by score (best first) before `state/last_scan.json` and the CSV are written, so digest #N = `draft N` = CSV row N; before, `last_scan.json` and the CSV were in scan order. The existing `last_scan.json` is reordered on the next scan.

### Fixed (2026-10-04, scoring input)
- T46: `strip_html` decodes entity-escaped HTML. `bs4` was never installed, so the regex fallback ran and Greenhouse's escaped `content` reached Gemini as raw markup (all 154 Greenhouse survivors, measured). Now stdlib-only; a live fetch of 74 Greenhouse boards has 0 survivors with markup (clean median 5,622 chars, max 10,180).
- T13: the scoring prompts (single and batch) send the whole job description instead of the first 2,000 chars; a 20,000-char bound only guards against runaway pages. Live A/B before the fix (16 jobs, real Gemini): with full descriptions every score was equal or lower — Greenhouse mean |Δ| 15 (MongoDB "Software Engineer 3" 90 → 65), SmartRecruiters 26, Workday 6.7, vs 3.3 run-to-run noise; at MIN_SCORE 70, 6 of 16 passed before vs 3 after.

### Added (2026-10-04, scoring input)
- T19: enrich step — after the pre-filter and posted-date window, `run_scan` calls `adapters.enrich_job` (in parallel, `fetch_workers`) for the jobs about to be scored, so per-job detail calls are paid only for survivors. Adapters register a description fetcher in `adapters.ENRICHERS`; failures keep the list-API text. Logs "Full descriptions fetched for K of N survivor(s)".
- T20: Workday enricher — single-location survivors get `jobDescription` from the CXS detail endpoint (multi-location ones already had it). Live on 643 Workday survivors: empty descriptions 591 → 0 in 109 s (8 workers); median 4,754 chars, max 11,730.
- T21: SmartRecruiters enricher — `GET /v1/companies/{slug}/postings/{id}` sections (job description, qualifications, additional information, then company description). Live fetch of the 13 boards: 74 survivors, empty descriptions 74 → 0 in 14 s; median 4,745 chars.
- T22: Oracle HCM enricher — `recruitingCEJobRequisitionDetails` (finder `ById`): description, responsibilities, qualifications, then organisation/company text (EXL and Kotak keep most of the role in responsibilities/qualifications). Live fetch of the 4 tenants: 77 survivors, under 300 chars 42 → 1, median 181 → 2,721 chars in 13 s. The 3 still short (2 Kotak, 1 EXL) have no description on Oracle at all, even with `expand=all`.

### Added (2026-10-04, coverage)
- Amazon adapter (`amazon.jobs` search JSON, country=IND; 2,329 India roles on 2026-10-04) and Oracle HCM adapter (public `recruitingCEJobRequisitions` REST API, India location facet looked up per tenant) — covers JPMorgan, Kotak, Cerner/Oracle Health, EXL, NI, DP World, ...
- `discover --census ... --emit-seeds FILE`: census hits on supported platforms become seed lines (board URL evidence), verified via `discover --add-file`. Seeds with Workday / Oracle HCM URLs are converted automatically.

- `companies.json` 187 → 215: 27 boards found by the census on supported platforms (Visa, Expedia, Palo Alto, Nike, Hotstar/JioStar, Genpact, Sprinklr, Bosch, JPMorgan, Kotak, EXL, ...) plus Amazon.
- Measured end-to-end (real scanner path, 2026-10-04): jobs fetched 17,485 → 36,228; pre-filter passes 204 → 1,271; posted ≤7 days 34 → 226; ≤3 days 21 → 99. Fetch time 3.9 → 8.9 min (larger Workday cap).

### Changed (2026-10-04, coverage)
- Pre-filter lets "Senior"/"Sr." titles through (Gemini judges them against the resume): 227 India jobs, 38 in 7 days, were blocked by that word alone. Staff/Principal/Lead/Manager stay excluded.
- Pre-filter accepts "Software Development Engineer" (all 202 Amazon India SDE titles were rejected) and "Member of Technical Staff"/MTS.
- SmartRecruiters adapter paginates past 100 (Swiggy 168, ServiceNow 706 postings); Workday India search cap raised 100 → 500 (Target 302, Nvidia 276).
- `detect_ats` handles Workday locale paths (`/en-US/search`), Greenhouse embed URLs, Oracle HCM candidate-site URLs.

### Added (2026-10-04)
- `autopilot discover --census FILE`: fingerprints the ATS behind each careers page (29 platforms + job boards), following up to 3 job links one level deep. `scripts/careers_urls.txt` holds 504 careers URLs from Manish's lists. First run: 197/458 companies identified (52% JS-only/unknown); Workday 17%, Greenhouse 9%, Eightfold/Phenom 7% each, Oracle HCM/Darwinbox 6% each.
- `autopilot scan --posted-within N` (or `candidate.max_posted_age_days`): only score jobs posted in the last N days. Jobs without a known posted date are always kept. Too-old jobs are saved as `skipped`, so widening the window later re-evaluates them. Measured on 2,627 live jobs (16 companies, 6 ATSs): 100% had parseable dates; of 40 pre-filter passes, 9 were ≤7 days old, 5 ≤3 days, 0 ≤1 day.
- `autopilot discover --recheck --merge companies.json`: periodic health check — re-verifies every entry, re-discovers failing companies by name (ATS migration) or removes them; review with `git diff companies.json`. Measured: 187 entries in 32 s with no changes.
- CSV export has a `Posted` column.

### Fixed (2026-10-04)
- Greenhouse `posted_at` now uses `first_published`; `updated_at` changes on every edit (differed on 182/200 Stripe jobs).

### Added (2026-10-04, later)
- `companies.json` 139 → 187 verified boards from Manish's second list + additions (872 names, 50 Workday tenant guesses). All 139 existing entries re-verified. The 48 new boards return 2,944 jobs (1,641 India), 65 passing the pre-filter.
- Parallel company fetch in `run_scan` (`fetch_workers`, default 8); DB writes and scoring stay sequential. Measured: 139 companies fetched in 6.4 min vs ~45 min summed sequential time.
- Hard total download deadline for every ATS HTTP call (`adapters/base.http_get/http_post`, 900 s) — `requests` timeouts are per read, so a trickling response could stall a scan forever. Workday tenants also get a 600 s per-board budget. (300 s was tried first and dropped Paytm and Extreme Networks, whose Lever downloads took ~300–436 s.)
- `autopilot discover --add-file PASTE` / `--add "A, B"`: verifies only the pasted companies and appends new names to `scripts/company_seeds.txt`. Parses plain lines, "Name = url", numbered lists, campus-calendar lines, salary tables (tab-separated), `<a href>` items and legal names with the brand in parentheses ("FASHNEAR TECHNOLOGIES PRIVATE LTD (Meesho)" → Meesho). `--no-recheck` skips re-verifying existing entries.

### Added (2026-10-04)
- `autopilot discover` (`job_hunt/discovery.py`): verifies company names from `scripts/company_seeds.txt` against 7 ATS APIs + curated Workday tenants. A board is accepted only with live jobs, confirmed identity (board name, company named in JDs, or slug from the company's own careers URL), ≥1 India job, and a posting within 180 days. `--merge` re-checks existing `companies.json` entries with the same rules.
- Opt-in batch scoring (`"gemini_scoring_mode": "batch"`, `gemini_batch_size`, default 10) using a JSON response schema. Not the default: on 10 live jobs batch scores differed from single-job scores by 15.5 points on average vs 1.0 run-to-run noise, inflating weak fits (no good fit fell below 60).

### Changed (2026-10-04)
- Location filter accepts Delhi / NCR / Kolkata and SmartRecruiters' lowercase `, in` country code (case-sensitive, so "Indianapolis, IN" is still rejected).
- Gemini scoring prompts include the full resume (previously first 2,500 of ~4,000 chars — Projects/Education were cut).
- Gemini fallback chain limited to `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` (500 RPD each); `gemini-3.8-flash` (20 RPD) and `gemini-flash-latest` removed.
- Scanner collects pre-filter survivors across all companies and scores them after fetching.
- `companies.json` expanded from 28 to 139 verified boards via `autopilot discover` (800 seeds). Dropped abandoned SmartRecruiters boards Cars24, Lendingkart, Unacademy (newest postings 6–11 years old). Live funnel 2026-10-04: 14,541 jobs fetched, 3,716 in India, 139 pass the pre-filter, 126 new.

### Fixed
- Pre-filter regexes are word-bounded: `java` no longer rejects "JavaScript", `test` no longer rejects "Latest"/"Contest", `intern` no longer rejects "Internal", `india` no longer accepts "Indianapolis". Also handles `Back-end`, `Full-Stack`, `NodeJS`, `SDE2`, `Sr.`, `Internship`, `.NET`, `C#`.
- Gemini scoring failures are no longer stored as `score=0`/`scored`; the job stays `discovered` and is retried next scan.
- Jobs are marked `notified` only when Telegram returns HTTP 200; otherwise `scored`.
- Scorer now uses `gemini_model` from config/env and passes the candidate profile into the scoring prompt (previously hardcoded model, no profile).
- Placeholder Telegram values (`YOUR_…`, `…_here`) are treated as unconfigured — no more HTTP 404 sends.
- Direct-scanner tests no longer make real HTTP calls to api.telegram.org.

### Changed
- Dedupe treats only `scored`/`notified` as final: `skipped` rows are re-run through the pre-filter and `discovered` rows are re-scored.
- `TINYFISH_API_KEY` is optional (`draft` raises a clear error without it). `llm_provider` defaults to `gemini`; OpenRouter is deprecated and logs a warning.
- `TELEGRAM_BOT_TOKEN` accepted as an alias for `TELEGRAM_TOKEN`.
- Harvester probes the ATS declared in `india.yml` first, applies `validator.KNOWN_CORRECTIONS`, and tags other-ATS matches with `ats_fallback_from`.
- Pre-filter title include list adds `Product/Platform/Infrastructure/Systems Engineer`.
- Location filter: remote roles tied to another region (US/UK/EU/LATAM, US cities, `, CA`-style state codes) are rejected unless India is also listed; `worldwide/anywhere/global` and geography-free remote pass; Mumbai and Chennai added. `.gitignore` adds `scratchpad/`; ARCHITECTURE.md rewritten for the direct-ATS pipeline.
- Workday adapter searches `searchText="India"`, paginates up to 100 jobs (20/page), keeps earlier pages if a later page fails, and resolves "N Locations" items (plus description) via the job detail endpoint.
- Harvester no longer drops companies on LinkedIn headcount (cache is stale, e.g. Sigmoid tagged 11-50); headcount is badge metadata only.
- `companies.json` curated to 28 boards, each verified to have live jobs from the right employer.
- `.gitignore` adds `data/` and `*.pdf`; CLAUDE.md rewritten for the direct-ATS + Gemini pipeline.

### Added
- Comprehensive architecture and future roadmap guide ([`ARCHITECTURE.md`](file:///home/user/codes/random_projects/JobNotify/ARCHITECTURE.md)) detailing high-level design, data flow, component breakdown, testing invariants, and multi-milestone expansion plan (multi-channel alerts, direct ATS scrapers, granular scoring, web dashboard, interview prep).
- Local runtime and toolchain bootstrap: Python 3.12 virtual environment, `uv` dependency management, full dev/mcp/claude dependencies installed.
- Added dedicated Google Gemini LLM provider using `google-genai` SDK:
  - Settings parser and [`job_hunt/config.py`](file:///home/user/codes/random_projects/JobNotify/job_hunt/config.py) accept `GEMINI_API_KEY` and `GEMINI_MODEL` (defaulting to `gemini-3.5-flash-lite`).
  - Provider dispatch in [`job_hunt/llm_utils.py`](file:///home/user/codes/random_projects/JobNotify/job_hunt/llm_utils.py) and scoring in [`job_hunt/scanner.py`](file:///home/user/codes/random_projects/JobNotify/job_hunt/scanner.py).
  - Strict JSON output formatting (`{"score": <0-100>, "reason": "<one sentence explanation>"}`) via `response_mime_type="application/json"`.
  - Graceful fallback returning `{"score": 0, "reason": "Scoring failed"}` on API or parsing failures to guarantee the scan loop never crashes.
- **Module 1 (Native Direct ATS Adapters)**:
  - Added zero-browser HTTP fetching adapters under [`job_hunt/adapters/`](file:///home/user/codes/random_projects/JobNotify/job_hunt/adapters/):
    - Greenhouse (`boards-api.greenhouse.io` and `boards.eu.greenhouse.io`)
    - Lever (`api.lever.co/v0/postings`)
    - Ashby HQ (`api.ashbyhq.com/posting-api/job-board`)
    - SmartRecruiters (`api.smartrecruiters.com/v1/companies/{slug}/postings`)
    - Workday Client CXS API (`{tenant}.{dc}.myworkdayjobs.com/wday/cxs/...`)
    - Recruitee (`{slug}.recruitee.com/api/offers`)
    - Personio (`{slug}.jobs.personio.de/xml?language=en`)
  - Intelligent ATS auto-detection from company URLs (`detect_ats`).
- **Module 2 (SQLite Deduplication & Local Regex Pre-Filter)**:
  - Unified canonical schema [`JobPosting`](file:///home/user/codes/random_projects/JobNotify/job_hunt/models.py) with deterministic MD5 canonical hashing and URL hashing.
  - Persistent SQLite database at `data/jobs.db` ([`job_hunt/db.py`](file:///home/user/codes/random_projects/JobNotify/job_hunt/db.py)) tracking `discovered`, `skipped`, `scored`, and `notified` status.
  - Local regex pre-filter ([`job_hunt/prefilter.py`](file:///home/user/codes/random_projects/JobNotify/job_hunt/prefilter.py)) to drop non-matching titles, excluded seniorities, and unsupported locations before sending to LLM.
- **Gemini Scoring & Rate Throttling**:
  - Unified scoring pipeline ([`job_hunt/scorer.py`](file:///home/user/codes/random_projects/JobNotify/job_hunt/scorer.py)) with 4.2-second sleep pacing to strictly respect 15 RPM cap.
  - Automatic Telegram alert triggers for jobs matching score threshold (>= 70).
- **Task 1: Ingest Local Data & Build `companies.json`**:
  - Implemented [`job_hunt/company_builder.py`](file:///home/user/codes/random_projects/JobNotify/job_hunt/company_builder.py) extracting Indian tech companies from `india.yml`.
  - Matched company names against `companyCache` in `linkedin-size-filter-backup-2026-10-03.json`.
  - Applied Safety Blocklist: safely discarded only companies explicitly tagged as `1-10 employees` or `11-50 employees`, while retaining all larger tiers (`51-200`, `201-500`, `501-1,000`, `1,001-5,000`, `5,001-10,000`, `10,001+ employees`) and unlisted/unknown entries.
  - Generated deduplicated `companies.json` with 249 companies across Ashby, Greenhouse, Lever (with Workday support).
- **Task 2: Notification Badges (`job_hunt/notifier.py`)**:
  - Added `format_job_alert` to [`job_hunt/notifier.py`](file:///home/user/codes/random_projects/JobNotify/job_hunt/notifier.py) embedding company headcount badge:
    `🏢 <b>Company:</b> {company} 🏷️ <i>[{headcount}]</i>`.
  - Integrated badge with [`JobPosting`](file:///home/user/codes/random_projects/JobNotify/job_hunt/models.py) model and [`job_hunt/scorer.py`](file:///home/user/codes/random_projects/JobNotify/job_hunt/scorer.py).
- **Task 3: Lightweight Diagnostics (`autopilot doctor`)**:
  - Implemented single-file diagnostics module in [`job_hunt/doctor.py`](file:///home/user/codes/random_projects/JobNotify/job_hunt/doctor.py) runnable via `autopilot doctor` or `python -m job_hunt doctor`.
  - Verifies SQLite write permissions on `data/jobs.db`.
  - Confirms Gemini quota health with 1-token test prompt (`gemini-3.5-flash-lite`).
  - Verifies Telegram bot credentials via `getMe`.
  - Pings sample network egress endpoints for Greenhouse, Lever, Ashby, and Workday.
  - Outputs a clean pass/fail checklist to terminal.
- **Task 4: Daily Runner Script (`run_daily.sh`)**:
  - Created executable [`run_daily.sh`](file:///home/user/codes/random_projects/JobNotify/run_daily.sh) for automated execution.
  - Appends timestamped logs to `data/scan.log`.
  - Sets default alert threshold to score >= 70.
  - Forwards CLI parameters (e.g. `--limit 5`).
- **Slug Validation & Active Board Pruning (`job_hunt/validator.py`)**:
  - Implemented concurrent ATS endpoint validator ([`job_hunt/validator.py`](file:///home/user/codes/random_projects/JobNotify/job_hunt/validator.py)) with CLI command `autopilot validate` / `python -m job_hunt validator`.
  - Applied known corrections for Razorpay (`greenhouse`, `razorpaysoftwareprivatelimited`), Freshworks (`smartrecruiters`, `freshworks`), BrowserStack (`workday`, `browserstack`), and Slice.
  - Pruned all inactive/404/403 endpoints, leaving `companies.json` with 10 verified active company boards.
- **ATS Adapter Resiliency**:
  - Updated all direct ATS adapters to intercept HTTP 404 responses and log at `DEBUG` level instead of printing warning stack traces, keeping scans clean and readable.

## [0.4.4] — 2026-07-09

### Added
- Job discovery search query is now config-driven: `candidate.search_seniority`
  / `candidate.search_keywords` in `config.json` shape the `site:<domain>`
  query sent to TinyFish per company. Empty/absent falls back to the previous
  hardcoded senior/staff ML/DS terms, so existing configs behave identically.
  Closes #24.

### Fixed
- `job_hunt/__init__.py` `__version__` re-synced with `pyproject.toml` (had
  drifted to a stale `0.4.1` across the last two releases).

## [0.4.3] — 2026-07-05

### Added
- MCP tools now ship full metadata: per-tool `ToolAnnotations` (title, readOnly/
  destructive/idempotent/openWorld hints), per-parameter descriptions via
  `Annotated[..., Field(...)]`, and structured output schemas (FastMCP auto).
  Improves registry quality scoring and host UX.

### Changed
- `mcp` extra now requires `mcp>=1.9` (ToolAnnotations support).

## [0.4.2] — 2026-07-05

> Note: 0.4.1 was recorded here but never uploaded to PyPI (latest there was 0.4.0);
> 0.4.2 supersedes it everywhere (PyPI, MCP registries).

### Added
- PEP 561 `py.typed` marker + `Typing :: Typed` and explicit Python 3.11/3.12/3.13
  classifiers on PyPI.
- `.github/PULL_REQUEST_TEMPLATE.md` — checklist including the drafts-only invariant.
- README: `mcp-name` ownership marker (Official MCP Registry) and registry-status line.

## [0.4.1] — 2026-07-03

### Added
- CI hardening: Python 3.13 in the test matrix, pip caching, and a `gitleaks`
  secret-scan job.
- Formal test scaffold: `pytest.ini` and a shared `conftest.py` (`fake_llm`,
  `clean_env`, `sample_config`, `sample_job` fixtures).
- Coverage gate (`--cov=job_hunt`, `fail_under = 85`) plus a mocked test suite
  raising coverage from ~36% to ~90%.
- `mypy` type checking with `job_hunt/` fully annotated; enforced in CI.
- GitHub issue templates (bug report, feature request).
- `skills/autopilot-jobhunt/SKILL.md` — a Claude Code usage skill that drives the hunt
  via the MCP tools.
- MCP registry manifests: `server.json` (official MCP Registry) and `smithery.yaml`.
- `autopilot mcp` subcommand to launch the stdio MCP server from the installed console
  script.
- `autopilot-jobhunt` console-script alias (== the PyPI distribution name) so
  MCP-registry runners that derive the command from the package name resolve
  correctly.
- `docs/` guide set: install, providers, API keys, scanning, integrations, MCP,
  config/scoring, troubleshooting, and a testing checklist.
- `SECURITY.md`, `PRIVACY.md`, and this `CHANGELOG.md`.

### Fixed
- `job_hunt/__init__.py` `__version__` corrected from a stale `0.1.0` to track the
  packaged version.

## [0.4.0]

### Added
- `glama.json` for Glama MCP ownership/indexing and a Glama quality badge.
- `Dockerfile` and OCI image labels for the Glama MCP listing and ghcr package linking.
- Demo GIF and star CTA in the README.
- `LOG_LEVEL` env honored for console verbosity.

### Changed
- Scanner always saves results to CSV and logs a provider-aware startup line.

## [0.3.1]

### Fixed
- Compose `config.json` and `.env` correctly (placeholder guard so the default `.env`
  template no longer clobbers real config values).
- `export` works without API keys (reads local scan state only).
- Added per-request timeouts to OpenRouter and Anthropic calls.
- Handle both dict and list JSON shapes from the Claude CLI output.

## [0.3.0]

### Added
- `claude_cli` LLM provider (score/draft via the local `claude` CLI, no API key).

## [0.2.0]

### Added
- pip-install workflow with `autopilot init` scaffolding.
- Structured logging and CSV fallback when Telegram send fails.
- Anthropic/Claude as an optional LLM provider.
- `SETUP.md` and `CLAUDE.md`.

### Changed
- Renamed the package and repository to `autopilot-jobhunt`.

## [0.1.0]

### Added
- Initial open-source release: nightly careers-page scan, LLM resume scoring,
  Telegram alerts, and on-demand resume + cover-letter drafting.
