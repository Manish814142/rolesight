# 04 — Companies & scanning

## `companies.json`

The list of job boards to scan. It is committed, **curated** and the core of the project:
each board was checked to be live, to belong to the right employer and to have India jobs.

**Counts (2026-10-06):** 216 boards: Workday 79, Greenhouse 74, Lever 23, Ashby 20,
SmartRecruiters 13, Oracle HCM 4, Workable 2, Amazon 1.

### Entry shapes

```json
{"name": "Adyen",       "ats": "greenhouse",      "slug": "adyen",           "headcount": "Unknown"}
{"name": "Acceldata",   "ats": "lever",           "slug": "acceldata",       "headcount": "201-500 employees"}
{"name": "Alphonso",    "ats": "ashby",           "slug": "lgads",           "headcount": "Unknown"}
{"name": "Arista Networks", "ats": "smartrecruiters", "slug": "aristanetworks", "headcount": "Unknown"}
{"name": "Leena AI",    "ats": "workable",        "slug": "leena-ai",        "headcount": "Unknown"}
{"name": "Adobe India", "ats": "workday", "tenant": "adobe", "dc": "wd5", "site": "external_experienced", "headcount": "10,001+ employees"}
{"name": "EXL",         "ats": "oracle_hcm", "host": "fa-ewjt-saasfaprod1.fa.ocs.oraclecloud.com", "site": "CX_2", "headcount": "10,001+ employees"}
{"name": "Amazon",      "ats": "amazon", "headcount": "10,001+ employees"}
```

- **`name`** replaces whatever company name the ATS returns, in every output.
- **`ats`** is one of: `greenhouse`, `greenhouse_eu`, `lever`, `ashby`,
  `smartrecruiters`, `workday`, `oracle_hcm`, `amazon`, `workable`, `recruitee`,
  `personio`.
- **`headcount`** is display metadata only, from a stale LinkedIn cache. It never filters
  anything.
- **Entries without an `ats`.** One with a `careers_url` is auto-detected when the URL is a
  known ATS; otherwise it is skipped with a warning. The curated list has no such entries.

### Adding companies: `autopilot discover`

Paste names into a file in any format (plain lines, `Name = url`, numbered lists, salary
tables, `<a href>` items, legal names such as
`FASHNEAR TECHNOLOGIES PRIVATE LTD (Meesho)`), then run:

```bash
cp companies.json /tmp/companies.backup.json
autopilot discover --add-file paste.txt --report /tmp/r.csv --out /tmp/v.json --merge companies.json
# or inline:  autopilot discover --add "Plane, BitGo, Groww" --report /tmp/r.csv --out /tmp/v.json --merge companies.json
```

For each name, `discover` guesses slugs and probes 7 ATS APIs plus a curated list of
Workday tenants. It **accepts** a board only when all four of these hold:

1. **Live:** at least one open job.
2. **Right employer:** the board name matches, the company is named in its job
   descriptions, or the slug came from the company's own careers URL. Same-slug boards of
   other companies exist (for example, `ashby/navi` is a San Francisco company).
3. **Hiring in India:** at least one India-located job.
4. **Not abandoned:** the newest posting is at most 180 days old. Some SmartRecruiters
   boards still answer with postings from 2015–2020.

What happens to your files:

- **The report.** Read `--report` (one row per seed: verdict, ATS, board, jobs, India
  jobs, pre-filter passes, newest posting age, identity evidence, sample titles) before
  trusting the merge.
- **The seeds file.** New names are appended to `scripts/company_seeds.txt` for the
  record.
- **Existing entries are re-checked** with the same rules by default. `--no-recheck`
  skips that.
- **Default output paths.** Without `--report` / `--out`, the files are
  `discovery_report.csv` and `verified_companies.json` in the current directory. Pass
  scratch paths.
- **Speed.** It runs 40 probes in parallel (`--workers`).

**Workday tenants** can't be guessed reliably. Add them as seed lines:

```
BlackBerry | workday | bb | wd3 | BlackBerry
Jupiter Money | https://jobs.lever.co/jupiter
```

**Boards rejected on evidence** (hardcoded in `discovery.KNOWN_BAD_BOARDS`, never accepted):
Navi and Bounce on Ashby (other companies), Edelweiss and Josh on Personio (DE/UK
companies), Eat Club on Workable (0 jobs), Porter on Lever, and the NoBroker / Upstox /
Turtlemint / Whatfix stubs on SmartRecruiters. Walmart's Workday returns HTTP 422 and
isn't in the list.

### Health check: `--recheck`

```bash
autopilot discover --recheck --merge companies.json --report /tmp/recheck.csv
git diff companies.json
```

This re-verifies every entry. A board that fails is re-discovered by name, which catches
a company that moved to another ATS; if that fails too, the board is removed. Measured:
187 entries checked in 32 s with no changes. Run it monthly and review the diff before
committing. It isn't scheduled yet (T28).

### Which ATS does a company use? `--census`

```bash
autopilot discover --census scripts/careers_urls.txt --report /tmp/census.csv --emit-seeds /tmp/seeds.txt
autopilot discover --add-file /tmp/seeds.txt --report /tmp/r.csv --out /tmp/v.json --merge companies.json
```

This fingerprints the platform behind each careers page (29 platforms plus job boards),
following up to 3 job links one level deep. The first run identified 197 of 458
companies. 52% were JavaScript-only or unknown. Workday was 17%, Greenhouse 9%,
Eightfold and Phenom 7% each, Oracle HCM and Darwinbox 6% each.

### What can't be reached

- **Custom career portals:** Google, Flipkart, Swiggy's own site, and so on.
- **Platforms with no adapter:** Darwinbox, Eightfold, Phenom, Freshteam, Zoho Recruit,
  Keka. Adapters for Eightfold, Phenom and Darwinbox are tasks T25–T27, which start by
  checking whether a public API exists.

### Don't use `harvest` / `validate` on the curated list

`autopilot harvest` rebuilds a list from `india.yml` plus a LinkedIn cache (by default in
`~/Downloads`, not in the repo). It **writes to `companies.json` by default**, replacing
the curated list, and it **re-adds boards that were removed on evidence**.
`autopilot validate` rewrites `companies.json` too, and accepts empty boards. If you use
them at all, write to a scratch file (`harvest --out /tmp/x.json`) and diff. `discover`
replaces both.

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
   - Posted more than N days ago, when `--posted-within N` is set → saved as `skipped`,
     so it comes back if you widen the window.
   - Otherwise → saved as `discovered` and queued.
4. **Enrich:** fetch the full description for queued jobs whose ATS list API doesn't
   carry one (Workday, SmartRecruiters, Oracle HCM). Runs in parallel; a failure keeps
   the text the job already has.
5. **Score** each queued job with Gemini, one call per job, 4.2 s apart. Success →
   `scored` (or `notified` if a Telegram alert went out). Failure → stays `discovered`
   for the next scan.
6. **Write** `state/last_scan.json`, append to `state/job_history.json`, write
   `output/jobs_YYYY-MM-DD.csv` (best first), log the top `top_n`, and send the Telegram
   digest if it's configured.

The pre-filter and scoring rules are spelled out in [07](07-config-and-scoring.md).

### Per-ATS fetching

| ATS | Endpoint (public, no key) | Limits | Description in list? | Posted date |
|---|---|---|---|---|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` (EU: `boards.eu…`) | whole board | yes | `first_published` |
| Lever | `api.lever.co/v0/postings/{slug}?mode=json` | whole board | yes | `createdAt` |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{slug}` | whole board | yes | `publishedAt` |
| SmartRecruiters | `api.smartrecruiters.com/v1/companies/{slug}/postings` | 100/page, ≤2,000 | no → enriched | `releasedDate` |
| Workday | `POST {tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`, `searchText="India"` | 20/page, ≤500, 600 s/tenant | no → enriched | "Posted N Days Ago" text |
| Oracle HCM | `{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions`, India location facet | 100/page, ≤2,000 | short only → enriched | `PostedDate` |
| Amazon | `www.amazon.jobs/en/search.json?country=IND` | 100/page, ≤4,000 | yes | `posted_date` |
| Workable | `apply.workable.com/api/v1/widget/accounts/{slug}?details=true` | whole board | yes | `published_on` |
| Recruitee | `{slug}.recruitee.com/api/offers` | whole board | yes | `published_at` |
| Personio | `{slug}.jobs.personio.de/xml?language=en` | whole board | yes | `createdAt` |

**Workday caveats**
- **India search.** Only jobs that Workday's search matches for "India" are fetched.
  Postings listed as "N Locations" get one detail call each during the fetch, to read
  their real locations, unless their title already fails the title pre-filter (T23): that job is
  rejected whatever its locations, so it keeps "N Locations" and the scan log's `India` count
  leaves it out.
- **Repeated postings.** Some tenants (Sabre, Warner Bros Discovery, Danaher) keep
  returning earlier postings once the offset passes their total. Paging stops at the
  tenant's `total` and when a page adds nothing new (T47, checked on all 78 tenants:
  no duplicate URLs).

### How long it takes

The first full scan (2026-10-04, 215 companies, `--posted-within 7`) took **34.3 min**:
8.9 min fetching, 32 s fetching descriptions (170 of 226 survivors), and about 24 min
scoring 226 jobs. Scoring time grows with the number of new jobs: about 6.3 s each.

Workday was most of that fetch time. Skipping the detail call for title-rejected jobs (T23) cut a Workday-only fetch of all
79 tenants from 534 s to 255 s (measured 2026-10-06, 8 workers, `python scripts/measure_workday_tenants.py`); a full
scan's total was not re-measured.

Later daily scans only score jobs not already `scored`, so they should be much shorter
(*inferred*; not yet measured on a repeat run).

### Useful flags

| Flag | Effect |
|---|---|
| `--limit N` | Only the first N companies in `companies.json` |
| `--posted-within N` | Score only jobs posted in the last N days (undated jobs always pass). Same as `candidate.max_posted_age_days` |
| `LOG_LEVEL=DEBUG` (env) | Per-job detail on the console. `data/autopilot.log` always has it |

## Next

- [05 — Outputs & notifications](05-outputs-and-notifications.md)
- [07 — Config & scoring](07-config-and-scoring.md)
