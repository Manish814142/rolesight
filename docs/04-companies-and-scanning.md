# 04 — Companies & scanning

## `companies.json`

The list of job boards to scan. It is committed, it is the core of the project, and it is meant to be grown: every entry
was checked by `autopilot discover` (below) to be live, to belong to the employer it names and to have India jobs.

**Counts (2026-10-18):** 1,589 boards: Greenhouse 502, Workday 302, Ashby 191, SmartRecruiters 184, Lever 151,
Oracle HCM 108, Workable 103, Recruitee 39, Eightfold 4, Personio 3, Amazon 1, Phenom 1. The first 224 were curated by
hand; the rest came from the bulk harvest (T111, T112). Count yours with
`python -c "import json,collections;print(collections.Counter(c['ats'] for c in json.load(open('companies.json'))))"`.

`job_hunt/data/companies.json` is the copy `autopilot init` gives a new user. **After any change, copy the list there**
(`cp companies.json job_hunt/data/companies.json`); a test fails while the two differ. Every push to GitHub carries both
files (CLAUDE.md), so other job seekers get the grown list.

### Entry shapes

```json
{"name": "Adyen",       "ats": "greenhouse",      "slug": "adyen",           "headcount": "Unknown"}
{"name": "Acceldata",   "ats": "lever",           "slug": "acceldata",       "headcount": "201-500 employees"}
{"name": "Alphonso",    "ats": "ashby",           "slug": "lgads",           "headcount": "Unknown"}
{"name": "Arista Networks", "ats": "smartrecruiters", "slug": "aristanetworks", "headcount": "Unknown"}
{"name": "Leena AI",    "ats": "workable",        "slug": "leena-ai",        "headcount": "Unknown"}
{"name": "Adobe India", "ats": "workday", "tenant": "adobe", "dc": "wd5", "site": "external_experienced", "headcount": "10,001+ employees"}
{"name": "EXL",         "ats": "oracle_hcm", "host": "fa-ewjt-saasfaprod1.fa.ocs.oraclecloud.com", "site": "CX_2", "headcount": "10,001+ employees"}
{"name": "Qualcomm",    "ats": "eightfold", "host": "qualcomm.eightfold.ai", "domain": "qualcomm.com", "headcount": "Unknown"}
{"name": "BCG",         "ats": "phenom", "host": "careers.bcg.com", "locale": "global/en", "headcount": "Unknown"}
{"name": "Amazon",      "ats": "amazon", "headcount": "10,001+ employees"}
```

- **`name`** replaces whatever company name the ATS returns, in every output (CSV, `.xlsx`, LinkedIn column, drafts).
- **`ats`** is one of `greenhouse`, `greenhouse_eu`, `lever`, `ashby`, `smartrecruiters`, `workday`, `oracle_hcm`,
  `eightfold`, `phenom`, `amazon`, `workable`, `recruitee`, `personio`.
- **`headcount`** is display metadata from a stale LinkedIn cache. It never filters anything.
- **No `ats`:** an entry with only a `careers_url` is detected when the URL is a known ATS, otherwise skipped with a
  warning. The list has none.

---

## Growing the list

Three ways in, one gate. Whatever the source, a company goes into `companies.json` only through
`autopilot discover`, which **accepts** a board only when all four hold:

1. **Live:** at least one open job.
2. **Right employer:** the board's own name matches, or the company is named in its job descriptions, or the board came
   from the company's own careers URL or from a harvested board address (`exact`, below). Same-slug boards of other
   companies exist (`ashby/navi` is a San Francisco company).
3. **Hiring in India:** at least one job whose location is in India (the scanner's own location rule).
4. **Not abandoned:** the newest posting is at most 180 days old (some SmartRecruiters boards still answer with postings
   from 2015–2020).

`discover` writes a **report** (`--report`, one row per seed: verdict, ATS, board, jobs, India jobs, pre-filter passes,
newest posting age, identity evidence, sample titles) and a **list of verified entries** (`--out`), and with `--merge FILE`
adds the new ones to the list. Existing entries always win; a new one is dropped when its name, its board or (Oracle HCM)
its host is already there. By default it also re-checks every existing entry (`--no-recheck` skips that). New names are
appended to `scripts/company_seeds.txt` for the record. Without `--report` / `--out` the files land in the current folder
as `discovery_report.csv` and `verified_companies.json`: pass scratch paths.

**Run every command below from the repository folder** (the clone): `discover` reads and writes `scripts/company_seeds.txt`,
`companies.json` and its default report files relative to the folder it is started in, and stops with `FileNotFoundError`
elsewhere. It needs **no API key** (no Gemini call is made; only the job boards' public APIs are read).

**Always:** back up first (`cp companies.json /tmp/companies.backup.json`), read the report, then `git diff companies.json`.

**The report's verdicts:** `verified` (accepted), `no open jobs`, `no India jobs`, `identity not confirmed`, `stale board (newest
posting N days old)`, `known bad board`, `no live board on supported ATSs`, `not rechecked` (an existing entry under `--no-recheck`), and `error: …` (the check raised;
nothing was decided).
With `--merge`, rows starting `[existing]` are the re-check of the entries already in the list.

**The default re-check removes entries.** With `--merge` and without `--no-recheck`, an existing entry that now fails the
four checks is dropped (the run prints `dropping existing <name>`), so the diff can show removals you did not ask for. Pass
`--no-recheck` when you only add, and read the diff either way.

### 1. By name: a pasted list

You have names (a LinkedIn list, a blog post, a salary table, `<a href>` items, legal names such as
`FASHNEAR TECHNOLOGIES PRIVATE LTD (Meesho)`). Paste them into a file in any format:

```bash
autopilot discover --add-file paste.txt --report /tmp/r.csv --out /tmp/v.json --merge companies.json
autopilot discover --add "Plane, BitGo, Groww" --report /tmp/r.csv --out /tmp/v.json --merge companies.json
```

For each name it guesses slugs and probes the public APIs of Greenhouse, Lever, Ashby, SmartRecruiters, Workable,
Recruitee and Personio (40 probes in parallel, `--workers`). With the default re-check of the existing list it took 3 min 21 s
for 2 names against 224 boards; the re-check alone of about 1,500 entries takes about 5½ minutes (both measured), so pass
`--no-recheck` when you only add.

**Workday, Oracle HCM, Eightfold and Phenom cannot be guessed from a name.** Give the board itself, one seed line each
(the seeds-file formats below), taken from the company's careers page URL.

### 2. By careers page: which ATS does a company use?

You have careers-page URLs but do not know the platform behind them:

```bash
autopilot discover --census scripts/careers_urls.txt --report /tmp/census.csv --emit-seeds /tmp/seeds.txt
autopilot discover --add-file /tmp/seeds.txt --report /tmp/r.csv --out /tmp/v.json --merge companies.json
```

The census fingerprints 29 platforms on each page, following up to 3 job links one level deep, and writes seed lines for
the boards it recognises. **If it wrote no seed line, stop there:** `--add-file` with an empty file stops with "holds no company
name" (T132; before that it fell back to checking every line of `scripts/company_seeds.txt`, hours of network). Its first run
(2026-10-04, 458 pages; `scripts/careers_urls.txt` holds 506 now) identified 197:
Workday 17%, Greenhouse 9%, Eightfold and Phenom 7% each, Oracle HCM and Darwinbox 6% each; **52% were JavaScript-only
pages or an unknown platform**. That last group is where most of the missing companies are (see "Where to grow next").

### 3. In bulk: every board the web has seen

You want many companies whose names you would never think to type. `scripts/harvest_board_urls.py` asks the Internet
Archive's URL index for every job-board **root page** it has seen (`jobs.lever.co/<company>`, `boards.greenhouse.io/<company>`,
`<tenant>.wd5.myworkdayjobs.com/<site>`, Oracle HCM candidate sites …), drops junk (template placeholders, file names,
ids, test and development instances) and the boards already in `companies.json`, and writes one seed line per board:

```bash
python scripts/harvest_board_urls.py --out /tmp/seeds.txt                    # every host (slow: the Oracle part reads each site's page)
python scripts/harvest_board_urls.py --out /tmp/lever.txt --hosts lever      # one ATS
python scripts/harvest_board_urls.py --help                                  # the host names: greenhouse, lever, ashby, …, workday, oracle-us2 … oracle-ocs, oracle-fa
```

Then verify the seeds in chunks of one ATS, and read each report:

```bash
autopilot discover --seeds /tmp/lever.txt --report /tmp/r.csv --out /tmp/v.json --merge companies.json --no-recheck --workers 20
autopilot discover --seeds /tmp/workable.txt --report /tmp/r.csv --out /tmp/v.json --merge companies.json --no-recheck --workers 3
cp companies.json job_hunt/data/companies.json
```

What to expect (T111, T112, measured 2026-10-16/17):

- **Most boards are dead.** About 3 in 100 archive boards pass; of 54,113 boards checked, 1,290 were added. Boards seen
  recently pass more often: 2,657 boards from Common Crawl's 2026 crawls (gathered by hand once, not by the script) passed
  at 11%.
- **Speed:** about 1 board per 0.15 s at `--workers 20`. A run of a few thousand boards takes minutes, the whole archive
  hours.
- **Workable and Recruitee refuse bursts** (HTTP 429: Workable refused about half of ~800 requests sent at 20 a second).
  Every request now waits 2, 5 and 12 s and asks again (T114), but run those two with **`--workers 3`**.
- **Oracle HCM hosts are customer codes** (`cbcz.fa.us2.oraclecloud.com`), so the script reads each site's page and takes
  the employer's name from its `<title>` ("Hilton", "Careers \| BXP" → "BXP"); a site whose title names nobody is not a
  seed. A host is one employer: `discover` keeps one entry per host, its busiest site, named by that site's own title
  (T117). 1,892 distinct Oracle sites → 104 employers added.
- **Seed lines look like** `Acme | https://jobs.lever.co/acme | exact`. `exact` makes `discover` check only that board (no
  slug guessing on the other ATSs: 37 fewer requests per board) and take the company name from the board where the ATS
  publishes one. Every site of a Workday tenant is checked and the one with most India jobs is kept.
- A board that makes the check raise is an `error` row in the report, not the end of the run.

### Seeds-file formats

One company per line, `#` comments allowed (`scripts/company_seeds.txt` is the record of every name tried):

```
Stripe                                                           # a name: slugs are guessed on 7 ATSs
Jupiter Money | https://jobs.lever.co/jupiter                    # a careers URL on a known ATS: used as it is
Acme | https://jobs.lever.co/acme | exact                        # only this board; the name comes from the board (the harvest writes these)
BlackBerry | workday | bb | wd3 | BlackBerry                     # Workday: tenant | data centre | site
Hilton | https://xxxx.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1 | exact
Qualcomm | eightfold | qualcomm.eightfold.ai | qualcomm.com       # Eightfold: careers host | employer domain
BCG | phenom | careers.bcg.com | global/en                       # Phenom: careers host | locale path of its URLs
```

### Before you merge: what the report can hide

The four checks are necessary, not sufficient. Each of these got past them once and was caught by reading a report or a
fetch (all fixed or decided since; check for them in yours):

| Trap | Seen | What to do |
|---|---|---|
| A job **aggregator or recruiter** reposting other employers' jobs under its own name | Jobs for Humanity (2,000 reposts), Jobs for Lebanon, Eram Talent (T116) | Drop it unless you want agency postings; the CSV, LinkedIn column and drafts name the agency |
| **"India" that is not India** | 21 boards whose only "India" jobs were `Makati City, NCR, ph`: Metro Manila is also "NCR" (T115, fixed in the filter) | Look at the India locations of boards with 1–3 India jobs |
| **Same slug, other company** | `ashby/navi`, `ashby/bounce`, `personio/edelweiss` (`discovery.KNOWN_BAD_BOARDS`, never accepted) | Add a board you find wrong to that set, with the reason in the commit |
| **Wrong name** on an Oracle host with several brands | "ADI" on Resideo's site, "Lutech" on McDermott's (T117, fixed in the script) | Compare the entry's name with its jobs' descriptions |
| A **one-posting board** that lost its India job a day later | Loopio, Ryansg (T112) | The monthly recheck removes them |

**Removing a wrong entry by hand:** delete its object from `companies.json`, `cp companies.json job_hunt/data/companies.json`,
and, when the board itself is wrong (another employer, a stub), add `(ats, slug)` to `discovery.KNOWN_BAD_BOARDS` with the
reason in the commit, so no later `discover` run adds it back.

### Keeping the list healthy: the monthly recheck

```bash
autopilot discover --recheck --merge companies.json --report /tmp/recheck.csv --out /tmp/recheck.json   # --out: the changed rows
git diff companies.json                                    # read it before committing; then copy the list to job_hunt/data/
scripts/monthly_recheck.sh                                 # the same, report only: it never changes companies.json
scripts/systemd/install.sh --with-recheck                  # run it monthly by systemd (not part of `autopilot schedule on`)
```

Every entry is checked again with the four rules (identity is trusted: these were verified once). A board that fails is
re-discovered by name, which catches a company that moved to another ATS; if that fails too, the entry goes. The report's
`REPLACED <old board> (…) -> <new board>` and `REMOVED <old board>: <reason>` rows are the changes (also in `--out`). Entries are
sent round-robin over the ATSs, an empty answer gets a second look two at a time (a rate limit is not a dead board), a
board whose check raises and a Workday tenant in maintenance are kept and flagged `error`. Measured: 1,515 entries in
5 min 19 s (2026-10-16). Entries the recheck flags but that are not yours to remove (Confluent, Fi Money and Cloudflare in
October 2026) stay until someone decides.

### What a bigger list costs

- **Scan time.** Fetching grows with the boards: 224 boards took 5.3 min to fetch, 1,514 boards 9.5 min, and 16.6 min
  for the whole scan without scoring (T111, measured with Gemini stubbed). Fetching the 104 Oracle sites of T112 alone took 46 s
  (8 at a time, 7-day window).
- **Gemini calls.** More boards, more jobs that pass the filter: the first scan of the 1,589-board list has about 411 to
  score (inferred from the counts of T111 and T112), then each day only the new postings. Each call takes 6–7.5 s; the
  free tier allows 500 a day per model, and the scan moves to the second model when the first has used its day (T118).
- **Nothing breaks with size:** each HTTP call has a 900 s deadline, each Workday tenant 600 s, and one dead board is
  logged and skipped.

### Where to grow next

Ranked by how many companies each could add, for an India job seeker:

1. **Run the harvest again** every few months: the archive keeps growing, and new boards pass more often (11% against
   3%). Adding Common Crawl's URL index to `harvest_board_urls.py` would automate the source that did best.
2. **Adapters for the platforms Indian companies use.** The census found 52% of careers pages on JavaScript-only or
   unknown platforms and 6% on Darwinbox. Darwinbox has no plain-HTTP API (tried, T27: every call needs a browser
   challenge). **Freshteam, Zoho Recruit and Keka have no adapter yet**; how many companies use them was not measured. A new
   platform needs: a file in `job_hunt/adapters/` (`ashby.py`, 58 lines, is the smallest), a branch in
   `adapters.fetch_company_jobs`, its URL pattern in `adapters.detect_ats` (careers URLs and the harvest), a probe in
   `harvester.ATS_PROBES` if a name can be turned into its board address, an `ENRICHERS` entry if its list API has no
   descriptions, a query in `scripts/harvest_board_urls.py`, and tests that make no network call.
3. **Pasted lists** (`--add-file`) for companies you know by name.
4. **Small, known options:** Greenhouse EU boards (`boards.eu.greenhouse.io`; the `greenhouse_eu` adapter exists) were left out of
   the harvest (T111; how many would pass was not measured). Lever EU (`jobs.eu.lever.co`) has no adapter yet: `detect_ats` and
   `lever.py` know only `jobs.lever.co` / `api.lever.co`. KPMG's second Oracle site holds jobs its kept site does not (T120).

### What cannot be reached

- **Custom career portals:** Google, Flipkart, Swiggy's own site, and so on.
- **Platforms with no adapter:** Darwinbox, Freshteam, Zoho Recruit, Keka, iCIMS, Taleo, SuccessFactors.

### Don't use `harvest` / `validate` on the curated list

`autopilot harvest --yaml india.yml` rebuilds a list from that slug file (there is no default; also `ROLESIGHT_HARVEST_YAML`) plus an optional
LinkedIn headcount cache (`--linkedin FILE` or `ROLESIGHT_LINKEDIN_CACHE`); neither file is in the repo. It **refuses to overwrite an existing output file** (default `companies.json`) unless you pass
`--force`, and it skips the boards removed on evidence (`harvester.EXCLUDED_BOARDS`). A rebuilt list lacks everything added
with `discover`. `autopilot validate` rewrites `companies.json` in place and accepts empty boards. Both are older tools;
`discover` replaces them. (`scripts/harvest_board_urls.py`, above, is a different tool: it only writes seed lines.)

---

## What a scan does

`autopilot scan` (`scanner.run_scan`):

1. **Load** `config.json`, `.env`, the resume and `companies.json`. Initialise
   `data/jobs.db`.
2. **Fetch** every company, 8 at a time (`fetch_workers`). Every HTTP response has a hard
   900 s total deadline, and each Workday tenant has a 600 s budget, so a slow board is
   cut off and logged rather than stalling the scan.
3. **For each job,** in company order:
   - Already `scored` or `notified` in the DB → skip.
   - Rejected by the **pre-filter** (title, location) → saved as `skipped`.
   - Posted more than N days ago (N = `candidate.max_posted_age_days`, default 7; `--posted-within`
     overrides it) → saved as `skipped`, so it comes back if you widen the window.
   - Otherwise → saved as `discovered` and queued.
4. **Enrich:** fetch the full description for queued jobs whose ATS list API doesn't
   carry one (Workday, SmartRecruiters, Oracle HCM, Eightfold, Phenom: `adapters.ENRICHERS`). Runs in parallel; a failure
   keeps the text the job already has.
5. **Score** each queued job with Gemini, one call per job, 4.2 s apart. Success →
   `scored` (or `notified` if a Telegram alert went out). Failure → stays `discovered`
   for the next scan.
6. **Write** `output/history/jobs_YYYY-MM-DD.csv` and `.xlsx` (best first; the scores are already in `data/jobs.db`), replace `output/last_scan.*` and `output/open_matches.*`, log the top `top_n`, and send the Telegram
   digest if it's configured.

The pre-filter and scoring rules are spelled out in [07](07-config-and-scoring.md).

### Per-ATS fetching

| ATS | Endpoint (public, no key) | Limits | Description in list? | Posted date |
|---|---|---|---|---|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` (EU: `boards.eu…`) | whole board | yes | `first_published` |
| Lever | `api.lever.co/v0/postings/{slug}?mode=json` | whole board | yes | `createdAt` |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{slug}` | whole board | yes | `publishedAt` |
| SmartRecruiters | `api.smartrecruiters.com/v1/companies/{slug}/postings` | 100/page, ≤2,000 | no → enriched | `releasedDate` |
| Workday | `POST {tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`, `searchText="India"` | 20/page, ≤2,000, 600 s/tenant | no → enriched | "Posted N Days Ago" text |
| Oracle HCM | `{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions`, India location facet | 100/page, ≤2,000 | short only → enriched | `PostedDate` |
| Eightfold | `{host}/api/pcsx/search?domain={domain}&location=India`, details from `/api/pcsx/position_details` | 10/page, ≤1,000, 600 s/board; 429 → retry after 3–48 s | no → enriched | `postedTs` (epoch) |
| Phenom | `POST {host}/widgets` (`refineSearch`, country India), details from the job page's JSON-LD | 100/page, ≤1,000 | no → enriched | `postedDate` |
| Amazon | `www.amazon.jobs/en/search.json?country=IND` | 100/page, ≤4,000 | yes | `posted_date` |
| Workable | `apply.workable.com/api/v1/widget/accounts/{slug}?details=true` | whole board | yes | `published_on` |
| Recruitee | `{slug}.recruitee.com/api/offers` | whole board | yes | `published_at` |
| Personio | `{slug}.jobs.personio.de/xml?language=en` | whole board | yes | `createdAt` |

**Rate limits.** An HTTP 429 ("too many requests") is asked again after 2, 5 and 12 s on every adapter (T114); Eightfold keeps
its own longer retry (3–48 s). A Workable board still refused after that is logged by name and its fetch counts as
incomplete, so its stored jobs are not marked closed.

**Workday caveats**
- **India search.** Only jobs that Workday's search matches for "India" are fetched.
  Postings listed as "N Locations" get one detail call each during the fetch, to read
  their real locations, unless their title already fails the title pre-filter (T23): that job is
  rejected whatever its locations, so it keeps "N Locations" and the scan log's `India` count
  leaves it out. Accenture's "Location Negotiable" placeholder (498 of its 2,000 results)
  is treated the same way (T65).
- **Repeated postings.** Some tenants (Sabre, Warner Bros Discovery, Danaher) keep
  returning earlier postings once the offset passes their total. Paging stops at the
  tenant's `total` and when a page adds nothing new (T47, checked on all 78 tenants:
  no duplicate URLs).

### How long it takes

Measured from the scan logs (`=== Scan complete … (N min)`; the 2026-10-04 line is in the old root `scan.log`, the others in
`data/scan.log`):

| Scan | Boards | Jobs scored | Time |
|---|---|---|---|
| 2026-10-04, first full scan | 215 | 226 | 34.3 min (8.9 fetching) |
| 2026-10-12, first production run (T09) | 224 | 317 | 48.5 min |
| 2026-10-14, repeat | 224 | 156 | 22.5 min |
| 2026-10-15, repeat | 224 | 120 | 20.8 min |

Scoring is most of it: 6.1–7.5 s a job on `gemini-3.5-flash-lite`. For the grown list (1,514 boards, Gemini stubbed, T111)
the fetch took 9.5 min and the scan 16.6 min before scoring; the first real scan of the 1,589-board list has about 411 jobs
to score (inferred), so about an hour (inferred), and the daily ones after it only the new postings.

### Useful flags

| Flag | Effect |
|---|---|
| `--limit N` | Only the first N companies in `companies.json` |
| `--posted-within N` | Score only jobs posted in the last N days for this run (undated jobs always pass); `all` = no window. The default is `candidate.max_posted_age_days`, 7 if unset (T02) |
| `LOG_LEVEL=DEBUG` (env) | Per-job detail on the console. `data/autopilot.log` always has it |

## Next

- [05 — Outputs & notifications](05-outputs-and-notifications.md)
- [07 — Config & scoring](07-config-and-scoring.md)
