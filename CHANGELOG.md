# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Dates are omitted for pre-1.0 releases that predate this changelog and were
reconstructed from git history.

## [Unreleased]

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
