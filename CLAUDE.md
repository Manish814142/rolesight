# autopilot-jobhunt (personal fork — JobNotify)

Personal production job scanner for **Manish Singh** (3 YOE, Node.js / Backend /
Distributed Systems, India or Remote). Forked from `tarunlnmiit/autopilot-jobhunt`
but **never upstreamed** — personal, hardcoded choices (e.g. the pre-filter) are fine.

Canonical pipeline: **Direct ATS APIs → regex pre-filter → Gemini score → SQLite → CSV**.
Telegram is optional. The primary output is the CSV in `output/`.

**Invariant: drafts only — never auto-apply/submit anything.**

**Task board: [`docs/tasks.md`](docs/tasks.md)** — pending work by priority, shared with other
agents. Follow its Working loop (claim → implement → review queue) or its Verifying section.

## Key commands

```bash
autopilot scan              # full scan of companies.json (alias: python -m job_hunt scan)
autopilot scan --limit 5    # only the first 5 companies
autopilot scan --posted-within 7   # only jobs posted in the last 7 days (undated jobs kept)
autopilot discover --recheck --merge companies.json --report /tmp/r.csv   # monthly list health check
autopilot discover --census scripts/careers_urls.txt --report /tmp/c.csv --emit-seeds /tmp/s.txt
                            # which ATS do careers pages use? --emit-seeds -> verify with discover --add-file
./run_daily.sh              # runner: timestamps into data/scan.log; exports MIN_SCORE=70 but .env's MIN_SCORE wins (T05)
autopilot harvest --out /tmp/x.json   # rebuilds a list from india.yml + LinkedIn cache; refuses to overwrite an existing file without --force (T43); prefer discover
autopilot validate          # prunes companies.json in place (accepts empty boards) — prefer discover
autopilot discover --seeds scripts/company_seeds.txt --report /tmp/r.csv --out /tmp/v.json [--merge companies.json]
                            # verify company names against ATS boards; --merge re-checks existing entries too
python scripts/measure_prefilter.py --jobs saved.json   # pre-filter survivors + what each exclusion word costs (--save fetches all, ~9 min)
python scripts/measure_workday_tenants.py   # per-tenant Workday fetch time, detail calls, survivors (~4-9 min, real network)
python scripts/score_golden_set.py         # score the labelled jobs with the rubric off/on (~150 Gemini calls); --from-scores re-analyses
autopilot doctor            # SQLite / Gemini / Telegram / ATS egress checks
autopilot export [--min N] [--days N]   # CSV from state/ (no API keys needed)
autopilot draft 1 | URL [--jd-file F]   # resume + cover letter draft from the stored description
```

Tests / gates: `pytest` (coverage gate 85%), `ruff check job_hunt`, `mypy`.
Tests must make **no network calls** — stub `send_telegram`, adapters, and Gemini.

## Pipeline (`scanner.run_scan`)

1. `companies.json` entries carry `ats` + `slug` (or `tenant`/`dc`/`site` for Workday).
2. `adapters.fetch_company_jobs` → `JobPosting`s from public ATS JSON APIs, fetched in parallel
   (`fetch_workers`, 8) with a 900 s total deadline per HTTP call and 600 s per Workday tenant
   (greenhouse, lever, ashby, smartrecruiters, workday, recruitee, personio, workable, oracle_hcm,
   eightfold, amazon). Oracle HCM entries carry `host` + `site`; Eightfold entries `host` + `domain`
   (PCSX search, 10/page, retried on HTTP 429); Amazon is `{"ats": "amazon"}`.
3. Dedupe by `(ats, global_id)` (the ATS's own job id) in `data/jobs.db`; `canonical_hash` is the
   fallback for rows without an id.
4. `prefilter.should_evaluate_job` — word-bounded title include/exclude + location regex; then
   `prefilter.is_too_old` when `--posted-within N` / `candidate.max_posted_age_days` is set.
5. Enrich: `adapters.enrich_job` fetches the full description for survivors whose ATS list API
   lacks one (`ENRICHERS`: workday, smartrecruiters, oracle_hcm, eightfold), in parallel; failures keep the
   list text.
6. After all companies are fetched, survivors are scored: default one job per Gemini call
   (`scorer.score_and_process_job`, full resume, 4.2 s pacing = 15 RPM). Opt-in
   `"gemini_scoring_mode": "batch"` scores `gemini_batch_size` (10) jobs per call — ~17×
   faster but measured to inflate weak fits by ~15 points (see CHANGELOG 2026-10-04).
   Each stored score names the model that answered (`jobs.score_model`, funnel line, CSV `Model` column when
   a model other than the primary scored; T71).
7. Per-job Telegram alert (if configured) → results sorted best-first → `state/last_scan.json`,
   `state/job_history.json`, incremental CSV `output/jobs_YYYY-MM-DD[_N].csv` (never overwrites),
   digest of the top `top_n`.

A company with no `ats` is detected from its `careers_url` when that names a known ATS; otherwise it is skipped
with a warning (custom careers pages are not scanned).

### Seen-job memory
`data/jobs.db` (SQLite, table `jobs`) is what makes daily runs show only new jobs: key =
`(ats, global_id)`, so two openings with the same title are two rows. `state/last_scan.json` holds only the latest
run (used by `draft N`), `state/job_history.json` the cumulative scored jobs (`export --days`),
`state/seen_jobs.json` is a leftover of the old scanner (T34 retires it).

### DB status lifecycle (`data/jobs.db`, table `jobs`)

| status | meaning | next scan |
|---|---|---|
| `skipped` | rejected by pre-filter | re-run through pre-filter (cheap) — filter fixes apply retroactively |
| `discovered` | passed pre-filter, not yet scored (or **scoring failed**) | re-scored |
| `scored` | Gemini score stored | final |
| `notified` | scored **and** Telegram returned HTTP 200 | final |

A Gemini failure never stores `score=0`; the row stays `discovered`.

## Config

| File | Controls | Git |
|---|---|---|
| `config.json` | candidate profile, `llm_provider`, `gemini_model`, telegram | ignored |
| `.env` | API keys; overrides config.json unless value is a placeholder (`YOUR_…`, `…_here`) | ignored |
| `companies.json` | ATS boards to scan (curated; maintained with `discover`) | committed |
| `resume/YOUR_RESUME.md` | resume text | template committed |

- **LLM:** `llm_provider` defaults to `gemini`; model from `gemini_model` / `GEMINI_MODEL`,
  fallback chain `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` only; a model whose daily quota is gone is skipped until its reset (T64) (free tier: 15 RPM,
  250k TPM, 500 RPD each; `gemini-3.8-flash` has 20 RPD and is never used as a fallback). `anthropic` and `claude_cli` are kept (deprecated) but only stubbed tests exercise them: no real call has been made with either (T63).
  TinyFish and OpenRouter were removed (T42).
- **Telegram:** optional. Empty/placeholder `TELEGRAM_TOKEN` (alias `TELEGRAM_BOT_TOKEN`)
  or `TELEGRAM_CHAT_ID` → skipped with a debug log; the scan still writes the CSV.

## Harvest inputs (not in repo)

`harvester.py` defaults to `/home/user/Downloads/india.yml` (ATS slugs) and
`/home/user/Downloads/linkedin-size-filter-backup-2026-10-03.json` (headcount cache).
Headcount is badge metadata only — **not** a filter (the cache is stale).
A board counts as active only with HTTP 200 **and** ≥1 job; each company appears once.
Matches on a non-declared ATS are tagged `ats_fallback_from`.

After a `discover --merge`, copy `companies.json` to `job_hunt/data/companies.json` (what `autopilot init` ships; a test checks they match).

**Adding companies (the company list is the core of this project — reuse this, never rebuild):**
paste names into a file in any format and run
`autopilot discover --add-file paste.txt --report /tmp/r.csv --out /tmp/v.json --merge companies.json`
(or `--add "A, B, C"`). New names are appended to `scripts/company_seeds.txt`; Workday tenants go
in as `Name | workday | tenant | dc | site` lines and Eightfold sites as `Name | eightfold | host | domain`. Back up `companies.json` and read the report first. Accepted only with live jobs, confirmed identity, ≥1 India job and
a posting ≤180 days old (abandoned SmartRecruiters boards from 2015–2020 exist). Custom portals
(Google, Flipkart, Swiggy careers sites, Darwinbox/Freshteam/Zoho Recruit…) are not reachable.

**`companies.json` is curated — do not blindly overwrite it with `autopilot harvest`.**
Harvest into a scratch file (`--out /tmp/x.json`) and diff. Boards removed on evidence
(wrong employer on a same-slug board, or 0 jobs): Navi (ashby/navi = SF), Bounce
(ashby/bounce = Lisbon/SF), Edelweiss & Josh (personio = DE/UK), Eat Club (0 jobs),
NoBroker/Upstox/Turtlemint/Whatfix SmartRecruiters stubs, Walmart Workday (HTTP 422).

### Workday adapter
`searchText="India"`, 20/page up to 2,000 jobs (Accenture has 2,000, in arbitrary order), 600 s budget per tenant; a blank `locationsText` falls back to the second bullet field (Accenture); "N Locations" and "Location Negotiable" (Accenture; T65) items whose title can pass the pre-filter get one
detail call (`GET …/wday/cxs/{tenant}/{site}{externalPath}`) for real locations + description during
the fetch (a title-rejected job is rejected whatever its locations, so it keeps "N Locations" and is not counted in the funnel's `India`; T23); single-location survivors get their description in the enrich step. Paging stops at the
tenant's `total` or when a page adds nothing new (some tenants repeat postings past it; T47).

## Package map

```
job_hunt/
  adapters/       direct ATS fetchers + detect_ats / fetch_company_jobs / ENRICHERS + enrich_job
  models.py       JobPosting, job_key (global_id, else canonical_hash), url_hash
  db.py           SQLite: init_db, get_job, save_job, update_job_status
  prefilter.py    title/location regexes (personal, hardcoded)
  scorer.py       Gemini scoring + DB status + optional Telegram alert
  scanner.py      run_scan orchestration
  llm_utils.py    provider dispatch (gemini default; anthropic, claude_cli)
  notifier.py     send_telegram, is_telegram_configured, format_job_alert
  exporter.py     incremental CSV writer
  discovery.py    `discover`: verify/add companies (--add-file), --recheck, --census
  harvester.py    old companies.json builder;  validator.py  board pruning
  company_builder.py  headcount matching + blocklist tiers
  doctor.py       diagnostics;  drafter.py  drafts;  tools.py / mcp_server.py  MCP layer
  main.py         CLI + load_config (config.py re-exports it)
```

## Gitignored state

`data/` (jobs.db, autopilot.log, scan.log), `state/*.json`, `output/`, `scan.log` (root: the pre-T16 log), `*.pdf`, `.env`, `config.json`.
