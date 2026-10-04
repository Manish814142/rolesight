# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Dates are omitted for pre-1.0 releases that predate this changelog and were
reconstructed from git history.

## [Unreleased]

### Docs (2026-10-04)
- Documentation rewritten to the current direct-ATS + Gemini pipeline (it still described upstream's TinyFish + OpenRouter careers-page scanner).
  - **README:** overview, features, how it works (with the first real scan's measured funnel), current status and known gaps, commands, config, outputs, the company list, layout.
  - **`docs/01`–`09`:** rewritten. `05-integrations.md` was renamed `05-outputs-and-notifications.md`, and now covers the CSV, DB statuses, state files, logs, export, drafts and Telegram.
  - **Other pages:** ARCHITECTURE.md brought up to date (enrich step, limits, known limitations with task IDs). SETUP.md is now a pointer to `docs/01`. CONTRIBUTING, SECURITY and PRIVACY were rewritten for the fork, and PRIVACY lists every outbound host in the code. The MCP skill was updated, and CLAUDE.md got factual corrections only.
- Documented commands were run as written: `autopilot --help`, `export --min 101`, the `fetch_company_jobs` one-liner, and an MCP stdio client listing the three tools. Six findings went to the `docs/tasks.md` Inbox (T51–T56).

### Fixed (2026-10-04)
- T30: deduplicate by ATS job ID (`global_id`) rather than title+company+location hash. Separate openings with the same title at the same company and location are now stored as independent rows in SQLite and evaluated by Gemini. Migrates `jobs` table schema to index on `(ats, global_id)` with fallback to `canonical_hash`. Existing scored rows are preserved.
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

### Added (2026-10-05, coverage)
- Amazon adapter (`amazon.jobs` search JSON, country=IND; 2,329 India roles on 2026-10-05) and Oracle HCM adapter (public `recruitingCEJobRequisitions` REST API, India location facet looked up per tenant) — covers JPMorgan, Kotak, Cerner/Oracle Health, EXL, NI, DP World, ...
- `discover --census ... --emit-seeds FILE`: census hits on supported platforms become seed lines (board URL evidence), verified via `discover --add-file`. Seeds with Workday / Oracle HCM URLs are converted automatically.

- `companies.json` 187 → 215: 27 boards found by the census on supported platforms (Visa, Expedia, Palo Alto, Nike, Hotstar/JioStar, Genpact, Sprinklr, Bosch, JPMorgan, Kotak, EXL, ...) plus Amazon.
- Measured end-to-end (real scanner path, 2026-10-05): jobs fetched 17,485 → 36,228; pre-filter passes 204 → 1,271; posted ≤7 days 34 → 226; ≤3 days 21 → 99. Fetch time 3.9 → 8.9 min (larger Workday cap).

### Changed (2026-10-05, coverage)
- Pre-filter lets "Senior"/"Sr." titles through (Gemini judges them against the resume): 227 India jobs, 38 in 7 days, were blocked by that word alone. Staff/Principal/Lead/Manager stay excluded.
- Pre-filter accepts "Software Development Engineer" (all 202 Amazon India SDE titles were rejected) and "Member of Technical Staff"/MTS.
- SmartRecruiters adapter paginates past 100 (Swiggy 168, ServiceNow 706 postings); Workday India search cap raised 100 → 500 (Target 302, Nvidia 276).
- `detect_ats` handles Workday locale paths (`/en-US/search`), Greenhouse embed URLs, Oracle HCM candidate-site URLs.

### Added (2026-10-05)
- `autopilot discover --census FILE`: fingerprints the ATS behind each careers page (29 platforms + job boards), following up to 3 job links one level deep. `scripts/careers_urls.txt` holds 504 careers URLs from Manish's lists. First run: 197/458 companies identified (52% JS-only/unknown); Workday 17%, Greenhouse 9%, Eightfold/Phenom 7% each, Oracle HCM/Darwinbox 6% each.
- `autopilot scan --posted-within N` (or `candidate.max_posted_age_days`): only score jobs posted in the last N days. Jobs without a known posted date are always kept. Too-old jobs are saved as `skipped`, so widening the window later re-evaluates them. Measured on 2,627 live jobs (16 companies, 6 ATSs): 100% had parseable dates; of 40 pre-filter passes, 9 were ≤7 days old, 5 ≤3 days, 0 ≤1 day.
- `autopilot discover --recheck --merge companies.json`: periodic health check — re-verifies every entry, re-discovers failing companies by name (ATS migration) or removes them; review with `git diff companies.json`. Measured: 187 entries in 32 s with no changes.
- CSV export has a `Posted` column.

### Fixed (2026-10-05)
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
