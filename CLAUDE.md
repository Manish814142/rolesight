# RoleSight

Job radar and scanner, published as an open-source project; the default configuration is **Manish Singh's** (3 YOE,
Node.js / Backend / Distributed Systems, India or Remote). Started from `tarunlnmiit/autopilot-jobhunt` (MIT) and not
kept in step with it — personal, hardcoded choices (e.g. the pre-filter) are fine.

Canonical pipeline: **Direct ATS APIs → regex pre-filter → Gemini score → SQLite → CSV**.
Telegram is optional. The primary output is the CSV in `output/`.

**Invariant: drafts only — never auto-apply/submit anything.**

**Task board: [`docs/tasks.md`](docs/tasks.md)** — pending work by priority, shared with other
agents. Follow its Working loop (claim → implement → review queue) or its Verifying section.

## Key commands

```bash
autopilot init [--resume CV.pdf] [--yes] [--countries "UK, Germany"]   # templates; --resume drafts candidate.*, candidate.titles and rubric.md from a resume (T103); --countries writes candidate.countries (T140)
autopilot check-filter "Java Developer" "Pune, India"   # KEPT/REJECTED with config.json's title filter and cities (T80, T103)
autopilot scan              # full scan of companies.json (alias: python -m job_hunt scan)
autopilot scan --limit 5    # only the first 5 companies
autopilot scan --posted-within 3   # window for this run (default: candidate.max_posted_age_days, 7; `all` = none; undated jobs kept)
autopilot discover --recheck --merge companies.json --report /tmp/r.csv --out /tmp/recheck.json   # monthly list health check (from the repo folder)
autopilot discover --census scripts/careers_urls.txt --report /tmp/c.csv --emit-seeds /tmp/s.txt
                            # which ATS do careers pages use? --emit-seeds -> verify with discover --add-file
autopilot schedule on [--at HH:MM] | off | status   # the daily scan by itself: systemd user timer, else cron; OFF by default (T121)
./run_daily.sh              # runner: timestamps into data/scan.log; min_score comes from config.json (default 70, T05)
autopilot harvest --out /tmp/x.json   # rebuilds a list from india.yml + LinkedIn cache; refuses to overwrite an existing file without --force (T43); prefer discover
autopilot validate          # prunes companies.json in place (accepts empty boards) — prefer discover
autopilot discover --seeds scripts/company_seeds.txt --report /tmp/r.csv --out /tmp/v.json [--merge companies.json] [--places "UK, Germany"]
                            # verify company names against ATS boards; --merge re-checks existing entries too
python scripts/check_filter.py "Java Developer" "Pune, India" [--remote]   # KEPT or REJECTED + the reason, for one job (T80)
python scripts/measure_prefilter.py --jobs saved.json   # pre-filter survivors + what each exclusion word costs (--save fetches all, ~9 min)
python scripts/measure_generic_titles.py --jobs saved.json   # India jobs dropped only for a generic title ("Senior Engineer"), by kind and company (T69 g)
python scripts/rubric_ids.py [--db data/jobs.db]   # which rubric text each stored score's id means, and how many scored rows carry each id (T97; read-only)
python scripts/measure_workday_tenants.py   # per-tenant Workday fetch time, detail calls, survivors (~4-9 min, real network)
python scripts/measure_visa_wording.py --jobs saved.json   # how postings in UK/DE/NL/IE/UAE/SG word visa sponsorship (--save fetches, ~3.5 min; T133)
python scripts/build_visa_sponsors.py [--offline] --report /tmp/visa.csv   # job_hunt/data/visa_sponsors.json from the UK/NL/IE sponsor records (T133)
python scripts/filter_by_visa_evidence.py --candidates v1.json v2.json --out kept.json --report f.csv   # keep only companies with visa-sponsor evidence (T144)
# discover seed "Name | workday | auto": finds a Workday tenant, its data centre and sites from the company name (robots.txt; T148)
python scripts/score_golden_set.py         # score the labelled jobs with the rubric off/on (~150 Gemini calls); --from-scores re-analyses
autopilot doctor            # SQLite / Gemini / Telegram / ATS egress checks
autopilot export [--min N] [--days N]   # CSV (+ .xlsx) in output/history/ from data/jobs.db: last finished scan, or N days (no API keys needed; T32)
autopilot draft 1 | URL [--jd-file F]   # resume + cover letter draft from the stored description, + keyword_gaps.txt (T44)
autopilot mark 1 | URL applied          # application status (applied|interview|rejected|offer|none) in data/jobs.db; export shows it (T38)
```

Tests / gates: `pytest` (coverage gate 85%), `ruff check job_hunt/ tests/ conftest.py` (what CI runs), `mypy`.
Tests must make **no network calls** — stub `send_telegram`, adapters, and Gemini.

## Pipeline (`scanner.run_scan`)

1. `companies.json` entries carry `ats` + `slug` (or `tenant`/`dc`/`site` for Workday).
2. `adapters.fetch_company_jobs` → `JobPosting`s from public ATS JSON APIs, fetched in parallel
   (`fetch_workers`, 8) with a 900 s total deadline per HTTP call and 600 s per Workday tenant
   (greenhouse, lever, ashby, smartrecruiters, workday, recruitee, personio, workable, oracle_hcm,
   eightfold, amazon). Workday, Eightfold, Phenom, Oracle HCM and Amazon ask the board for the person's countries (`places.Places`
   `workday_terms` / `search_names` / `amazon_codes`; India alone = the old "India" / `IND` requests, T137). Oracle HCM entries carry `host` + `site`; Eightfold entries `host` + `domain`
   (PCSX search, 10/page, retried on HTTP 429); Amazon is `{"ats": "amazon"}`.
3. Dedupe by `(ats, global_id)` (the ATS's own job id) in `data/jobs.db`; `canonical_hash` is the
   fallback for rows without an id.
4. `prefilter.should_evaluate_job` — title include/exclude word lists (`config.json` `candidate.titles`, else `prefilter.DEFAULT_TITLE_*`;
   `prefilter.configure_titles` at scan start, T103) + the location rule: India's regexes when `candidate.countries` is absent or India alone
   (unchanged, 0 of 111,106 saved jobs decided differently), else `job_hunt/places.py`'s country packs (`configure_places` at scan start, T136); then
   `prefilter.is_too_old` (`candidate.max_posted_age_days`, default 7 — T02; `--posted-within N|all` overrides). The window also
   reaches the adapters: no Workday detail call for an older job, and newest-first lists (Oracle HCM, Eightfold, SmartRecruiters) stop paging.
5. Enrich: `adapters.enrich_job` fetches the full description for survivors whose ATS list API
   lacks one (`ENRICHERS`: workday, smartrecruiters, oracle_hcm, eightfold), in parallel; failures keep the
   list text.
6. After all companies are fetched, survivors are scored: default one job per Gemini call
   (`scorer.score_and_process_job`, full resume, 4.2 s pacing = 15 RPM). Opt-in
   `"gemini_scoring_mode": "batch"` scores `gemini_batch_size` (10) jobs per call — ~17×
   faster but measured to inflate weak fits by ~15 points (see CHANGELOG 2026-10-04).
   With `candidate.countries` other than India alone, `llm_utils.configure_rubric` rewrites rule 1 and rule 5's location line for
   those countries and the visa rule (`rubric_for_places`; India alone keeps the text and id `82e017b4`, T138).
   Each stored score names the model that answered (`jobs.score_model`, funnel line, CSV `Model` column when
   a model other than the primary scored; T71) and the id of the rubric text (`jobs.score_rubric`, scan log `Scoring rubric:`, CSV `Rubric`
   column when a score is not from the current one; `python scripts/rubric_ids.py [--db data/jobs.db]` decodes the ids; T97).
7. Per-job Telegram alert (if configured) → results sorted best-first → incremental CSV
   `output/history/jobs_YYYY-MM-DD[_N].csv` (never overwrites; each CSV also gets a formatted `.xlsx` beside it, T128), `output/last_scan.csv` (everything *this* scan scored, rewritten every run, T130)
   and `output/open_matches.csv` (rewritten every run: the jobs *this* scan
   scored ≥ min_score, not marked applied, inside the posted window; T124. `open_matches_scope: "all_open"` brings back the rolling list
   of every unmarked match, T39); the scan's row in table `scans` is finished,
   digest of the top `top_n`.

A company with no `ats` is detected from its `careers_url` when that names a known ATS; otherwise it is skipped
with a warning (custom careers pages are not scanned).

### Seen-job memory
`data/jobs.db` (SQLite, table `jobs`) is what makes daily runs show only new jobs: key =
`(ats, global_id)`, so two openings with the same title are two rows. Table `scans` (T31) records each run;
`draft N` / `mark N` / `export` read `scans` + `jobs`. The `state/*.json` files are retired (T34): nothing writes or
reads them; `scripts/import_json_history.py` imports scores only they hold (dry run unless `--apply`).

### DB status lifecycle (`data/jobs.db`, table `jobs`)

| status | meaning | next scan |
|---|---|---|
| `skipped` | rejected by pre-filter | re-run through pre-filter (cheap) — filter fixes apply retroactively |
| `discovered` | passed pre-filter, not yet scored (or **scoring failed**) | re-scored |
| `scored` | Gemini score stored | final |
| `notified` | scored **and** Telegram returned HTTP 200 | final |

A Gemini failure never stores `score=0`; the row stays `discovered`.
Separately (T33), `closed_at` is set once a job's board answers `closed_after_missed_scans` (3) scans in a row
without it (`missed_scans`; `first_seen`/`last_seen`); a failed, empty or early-stopped fetch (page failure, time
budget, job cap: `adapters.base.mark_incomplete`) is no miss; a returning job reopens. The one exception (T78): a fetch that
stopped at the posted-date window counts a miss for the board's stored jobs that are inside the window (one day of margin),
since those would have been on the pages read, and for no older or undated job.

## Config

| File | Controls | Git |
|---|---|---|
| `config.json` | candidate profile, title filter (`candidate.titles`), `countries` / `home_country` (T136; absent = India), `rubric_file`, `llm_provider`, `gemini_model`, telegram | ignored |
| `rubric.md` | the person's scoring rubric when `candidate.rubric_file` names it (else `llm_utils.DEFAULT_SCORING_RUBRIC`, Manish's) | ignored |
| `.env` | API keys; overrides config.json unless value is a placeholder (`YOUR_…`, `…_here`) | ignored |
| `companies.json` | ATS boards to scan (curated; maintained with `discover`) | committed |
| `resume/YOUR_RESUME.md` | resume text | template committed |

- **Manish's own config.json carries his title filter written out** (`candidate.titles`, since 2026-10-14, equal to
  `prefilter.DEFAULT_TITLE_*`, the regexes they replaced: 0 of 39,985 jobs decided differently). **A change to his filter goes into
  his config.json** (and into the defaults + both example configs when it should ship); changing only the defaults no longer
  reaches him. He has **no `rubric_file`**: his rubric is the built-in one (`llm_utils.DEFAULT_SCORING_RUBRIC`, id `82e017b4`), so
  measured rubric changes in code reach him. His `.env` overrides (`CANDIDATE_NAME`, `RESUME_PATH`, `TOP_N`) are commented out:
  config.json decides. `.env` values that are placeholders or empty never override the shell (`settings.load_env_file`, T103).
- **LLM:** `llm_provider` defaults to `gemini`; model from `gemini_model` / `GEMINI_MODEL`,
  fallback chain `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` only; a model whose daily quota is gone is skipped until its reset (T64) (free tier: 15 RPM,
  250k TPM, 500 RPD each; `gemini-3.8-flash` has 20 RPD and is never used as a fallback). `anthropic` and `claude_cli` are kept (deprecated) but only stubbed tests exercise them: no real call has been made with either (T63).
  TinyFish and OpenRouter were removed (T42).
- **Telegram:** optional. Empty/placeholder `TELEGRAM_TOKEN` (alias `TELEGRAM_BOT_TOKEN`)
  or `TELEGRAM_CHAT_ID` → skipped with a debug log; the scan still writes the CSV.

## Harvest inputs (not in repo)

`harvest` has no default input file (T94): pass `--yaml FILE` (ATS slugs; Manish keeps `india.yml` in `~/Downloads`) or set `ROLESIGHT_HARVEST_YAML`.
The optional headcount cache (his is `linkedin-size-filter-backup-2026-10-03.json`, also in `~/Downloads`) comes from `--linkedin FILE` or
`ROLESIGHT_LINKEDIN_CACHE`; `discover` reads it only from that variable and shows headcount "Unknown" without it.
Headcount is badge metadata only — **not** a filter (the cache is stale).
A board counts as active only with HTTP 200 **and** ≥1 job; each company appears once.
Matches on a non-declared ATS are tagged `ats_fallback_from`.

After a `discover --merge`, copy `companies.json` to `job_hunt/data/companies.json` (what `autopilot init` ships; a test checks they match).

**Every push to GitHub carries `companies.json` and its copy `job_hunt/data/companies.json`** (Manish, 2026-10-17: so other job seekers get the list). Both are tracked, so a push of `main` includes them;
a partial push (another branch, a cherry-pick) or an uncommitted list would not. Before: `git diff --stat origin/main main -- :/companies.json :/job_hunt/data/companies.json` shows what goes.
After: `git fetch && { git diff --quiet origin/main -- :/companies.json :/job_hunt/data/companies.json && echo "GitHub has the current list" || echo "GitHub does NOT have the current list yet"; }`. Whether and when to push is his call; nothing is pushed without his say.

**Adding companies (the company list is the core of this project — reuse this, never rebuild):**
paste names into a file in any format and run
`autopilot discover --add-file paste.txt --report /tmp/r.csv --out /tmp/v.json --merge companies.json`
(or `--add "A, B, C"`). New names are appended to `scripts/company_seeds.txt`; Workday tenants go
in as `Name | workday | tenant | dc | site` lines and Eightfold sites as `Name | eightfold | host | domain`. Back up `companies.json` and read the report first. Accepted only with live jobs, confirmed identity, ≥1 India job (with `--places` / `candidate.countries`: ≥1 job there; the entry then
carries `"places"`, the recheck checks it against them and a scan fetches it only for those countries, T139) and
a posting ≤180 days old (abandoned SmartRecruiters boards from 2015–2020 exist). Custom portals
(Google, Flipkart, Swiggy careers sites, Darwinbox/Freshteam/Zoho Recruit…) are not reachable.

**Growing the list in bulk (T111):** `python scripts/harvest_board_urls.py --out /tmp/seeds.txt [--hosts lever,workday]` lists the job-board
root pages the Internet Archive has seen (every Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, Personio board and Workday
site), drops junk and boards already in `companies.json`, and writes `Name | board URL | exact` seed lines. `exact` makes `discover`
check only that board (no slug guessing on the other ATSs) and name the company from the board where the ATS publishes a name; it also
keeps every site of a Workday tenant and lets the one with most India jobs win. Run it on chunks of one ATS:
`autopilot discover --seeds /tmp/seeds.txt --report /tmp/r.csv --out /tmp/v.json --merge companies.json --no-recheck --workers 20`.
About 3 boards in 100 pass (live, ≥1 India job, a posting ≤180 days old); one board that makes the fetch raise is an `error` row, not the
end of the run. **Workable refuses about half the requests of a sustained burst with HTTP 429** (measured 2026-10-16: about 800 requests at 20 a second; Recruitee's were seen in a bulk run's log). Every request now waits and asks again after a 429 (T114),
but a bulk run of Workable or Recruitee boards should still use `--workers 3` (at 20 workers, before the retry existed, 13 of 100 sampled Workable "no live board" verdicts, and 19 of 100 Recruitee, were alive when probed one at a time). Oracle HCM sites are harvested too (T112): the
host is a customer code (`cbcz.fa.us2…`), so the script names each site from its page `<title>`; `discover` keeps one entry per
host, its busiest site, named by that site's own title (T117). The full guide for people: `docs/04-companies-and-scanning.md`, "Growing the list".

**A company added for other countries must show visa-sponsor evidence (T144, Manish 2026-10-22):** an entry with `places` is kept only
if it is on a sponsor record or community list for a country it hires in, or a posting offers visa sponsorship
(`scripts/filter_by_visa_evidence.py`; the review file `scripts/visa_sponsor_review.json` also holds hand-accepted aliases). The India
companies need none. Workday employers are found by name (`Name | workday | auto`, T148): the archive cannot list wd1/wd3/wd5.

**Visa-sponsor evidence (T133):** `job_hunt/data/visa_sponsors.json` lists the companies on the list that appear on the UK register of licensed
sponsors, the Dutch IND register, Ireland's permits-issued-to-companies files, the USCIS H-1B approvals (FY2024 via the JohnBroberg/H1B_Hub copy,
uscis.gov refuses scripts; `--us-h1b FILE` for a newer export) and Canada's positive LMIA employers (T143), or three community lists (incl.
relocate.me's CC0 one, T141; a list entry counts only for its places), each with the source's own entry; the UAE, Singapore, Germany, the
USA, Canada, Australia and New Zealand also get their official rule in the note unless the posting refuses (`visa.COUNTRY_RULE`). Built by
`scripts/build_visa_sponsors.py` (downloads into `data/visa_sources/`; `--offline` reuses them). A loose name match (generic words dropped)
counts only when accepted in `scripts/visa_sponsor_review.json`, which also holds the rejections: after a rebuild, read the report's
`unreviewed` rows. Why: 85–100% of engineering postings outside India never state a visa policy (measured 2026-10-21,
`scripts/measure_visa_wording.py`); and 17 of the 44 UK companies whose postings refuse sponsorship are licensed, so a posting's own refusal wins.
The scan writes it per job abroad as the CSV's Visa column (`job_hunt/visa.py`, T138). Guide: `docs/04-companies-and-scanning.md`, "Visa sponsorship".

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
  prefilter.py    title rules (TitleRules: config.json candidate.titles or the defaults), India location regexes (+ _in_your_places)
  places.py       candidate.countries / home_country -> Places: a pack for every country (9 hand-made + GeoNames: data/countries.json,
                  scripts/build_countries.py), explicit_countries, configure/active/using, listed_for (T136-T142)
  visa.py         the Visa column: wording (posting), record (visa_sponsors.json), note (T138)
  onboarding.py   `init` (+ --resume drafting with Gemini) and `check-filter`
  scorer.py       Gemini scoring + DB status + optional Telegram alert
  scanner.py      run_scan orchestration
  llm_utils.py    provider dispatch (gemini default; anthropic, claude_cli)
  notifier.py     send_telegram, is_telegram_configured, format_job_alert
  exporter.py     incremental CSV writer (columns in reading order, Score first, T128)
  xlsx_report.py  the formatted .xlsx written beside each CSV, built from it; never stops a scan (T128)
  discovery.py    `discover`: verify/add companies (--add-file), --recheck, --census
  harvester.py    old companies.json builder;  validator.py  board pruning
  company_builder.py  headcount matching + blocklist tiers
  doctor.py       diagnostics;  drafter.py  drafts;  tools.py / mcp_server.py  MCP layer
  scheduler.py    `schedule on|off|status`: the daily scan as a systemd user timer or a cron line, off by default (T121)
  main.py         CLI + load_config (config.py re-exports it)
```

## Gitignored state

`data/` (jobs.db, autopilot.log, scan.log), `state/*.json` (retired, T34), `output/`, `scan.log` (root: the pre-T16 log), `*.pdf`, `.env`, `config.json`.
