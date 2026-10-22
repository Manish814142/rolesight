# 04 — Companies & scanning

## `companies.json`

The list of job boards to scan. It is committed, it is the core of the project, and it is meant to be grown: every entry
was checked by `autopilot discover` (below) to be live, to belong to the employer it names and to have India jobs (or,
for the 27 entries that carry `"places"`, jobs in those countries: T139).

**Counts (2026-10-22):** 2,510 boards: Greenhouse 733, Workday 481, Ashby 391, SmartRecruiters 264, Lever 206,
Recruitee 195, Oracle HCM 108, Workable 106, Personio 20, Eightfold 4, Amazon 1, Phenom 1. The first 224 were curated by
hand; 1,365 came from the bulk harvest (T111, T112); 921 were checked for other countries instead of India (T139, T142, T144):
58 from the community lists and 862 that passed the visa-evidence rule (below; 900 before its review took out 38). Count yours with
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
3. **Hiring in your places:** at least one job whose location is in India (the scanner's own location rule), or, with
   `--places "United Kingdom, Germany"` (default: `config.json`'s `candidate.countries`), in those countries. An entry
   accepted for other countries records them (`"places": [...]`); the monthly recheck checks it against them, and a scan
   fetches it only when your countries include one of them, so an India scan fetches what it fetched before (T139).
4. **Not abandoned:** the newest posting is at most 180 days old (some SmartRecruiters boards still answer with postings
   from 2015–2020).

`discover` writes a **report** (`--report`, one row per seed: verdict, ATS, board, jobs, jobs in your places (`place_jobs`), pre-filter passes,
newest posting age, identity evidence, sample titles) and a **list of verified entries** (`--out`), and with `--merge FILE`
adds the new ones to the list. Existing entries always win; a new one is dropped when its name, its board or (Oracle HCM)
its host is already there. By default it also re-checks every existing entry (`--no-recheck` skips that). New names are
appended to `scripts/company_seeds.txt` for the record. Without `--report` / `--out` the files land in the current folder
as `discovery_report.csv` and `verified_companies.json`: pass scratch paths.

**Run every command below from the repository folder** (the clone): `discover` reads and writes `scripts/company_seeds.txt`,
`companies.json` and its default report files relative to the folder it is started in, and stops with `FileNotFoundError`
elsewhere. It needs **no API key** (no Gemini call is made; only the job boards' public APIs are read).

**Always:** back up first (`cp companies.json /tmp/companies.backup.json`), read the report, then `git diff companies.json`.

**The report's verdicts:** `verified` (accepted), `no open jobs`, `no India jobs` (with other places: `no jobs in …`), `identity not confirmed`, `stale board (newest
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

### 4. Workday employers, by name (T148)

Workday cannot be guessed like the seven other platforms, and the archive cannot list it: for data centres `wd1`, `wd3` and `wd5`
(about 190 of the first 302 tenants) the Internet Archive and Common Crawl answered HTTP 504 at every size of query, down to one
month (measured 2026-10-22). What works is Workday itself: a tenant's `https://<tenant>.<data centre>.myworkdayjobs.com/robots.txt`
lists every career site it has, and a tenant that is not on that data centre answers 422. So the tenant, its data centre and all its
sites come from the company name alone:

```bash
# paste names, one per line, with the seed suffix
Barclays | workday | auto
Lloyds Banking Group | workday | auto
autopilot discover --seeds names.txt --places "United Kingdom, Germany, ..." --report /tmp/r.csv --out /tmp/v.json --merge companies.json --no-recheck --workers 20
```

- **Which tenant names are tried:** the name run together, without its legal form and without "Group"/"Holdings" ("Lloyds Banking
  Group" -> `lloydsbankinggroup`, `lloydsbanking`), on 16 data centres, wd3 first. **Never a first word alone**: in the prototype
  `standard` was not Standard Chartered's tenant and `lloyds` was Lloyd's of London.
- **Whose it is:** up to three postings' text (those in your places first) must name the company; otherwise the report says
  `identity not confirmed`. A company with no tenant gets the row `no Workday tenant named like it`. This confirms the **name**,
  not which company of that name you meant: the seed `Clark` found the `clark` tenant, Clark Construction (its postings say
  "Clark"), while the community list that supplied the name meant the Berlin insurer (found in review, 2026-10-22). Give a
  one-word name in full ("Clark Construction") or check the report's sample titles.
- **What it found:** of 58 well-known European employers a prototype found 25 (43%); of 1,317 names (every name ever tried plus
  about 350 big European, Gulf, Asian, US, Canadian and Australian employers) 93 had a tenant, 77 companies passed; of the 2,439
  biggest visa sponsors in the registers (US H-1B employers, Irish permit holders, Canadian LMIA employers) 71 had one and 62
  passed (Chevron, Bristol Myers Squibb, Stryker, Kyndryl, Iqvia, Vanguard, Western Union, Zillow, …). Speed: about 11 lookups a
  second at 30 workers; 1,317 names took 47 minutes, 2,439 took 77.
- **Recall is limited by the names you give it.** Tenants whose name differs from the company's ("sc" for Standard Chartered) are
  missed. The websites' own country filter is no alternative: 25 of 60 tenants have none, and the others call it `locationCountry`,
  `Location_Country` or `locationHierarchy1`. The scan's search by country name never found fewer jobs than that filter (0 of 104
  tenant-country pairs, measured), so the per-country search of the scanner is sound.
- **Cost:** a Workday site is checked once per country until one shows a job, so 26 countries cost up to 26 requests per site;
  a site that does not exist (404/422) costs one.

The bulk harvest (section 3) now runs Lever, SmartRecruiters and Workday as small queries (by first letter, by data centre) and
keeps the chunks that answer; a chunk that still fails is asked one date span at a time, halved down to a month.

### Seeds-file formats

One company per line, `#` comments allowed (`scripts/company_seeds.txt` is the record of every name tried):

```
Stripe                                                           # a name: slugs are guessed on 7 ATSs
Jupiter Money | https://jobs.lever.co/jupiter                    # a careers URL on a known ATS: used as it is
Acme | https://jobs.lever.co/acme | exact                        # only this board; the name comes from the board (the harvest writes these)
BlackBerry | workday | bb | wd3 | BlackBerry                     # Workday: tenant | data centre | site
Hilton | https://xxxx.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1 | exact
Barclays | workday | auto                                       # Workday: find the tenant, its data centre and sites from the name (T148)
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

## Visa sponsorship: which companies can sponsor

For someone in India applying abroad, a job counts only if the employer sponsors the visa. **Most postings never say.**
Measured on 2026-10-21 (`scripts/measure_visa_wording.py`): every job on the 989 Greenhouse, Lever, Ashby, Workable, Recruitee
and Personio boards of the list (71,121 jobs; the other ATSs return India only or need a request per job), titles with an
include word:

| Place | Jobs | Visa offered | Refused | No clear answer | Says nothing |
|---|---|---|---|---|---|
| UK | 557 | 20 (3.6%) | 56 (10.1%) | 23 | 458 (82.2%) |
| Germany | 157 | 2 (1.3%) | 2 (1.3%) | 14 | 139 (88.5%) |
| Netherlands | 125 | 7 (5.6%) | 0 | 28 | 90 (72.0%) |
| Ireland | 147 | 5 (3.4%) | 5 (3.4%) | 1 | 136 (92.5%) |
| UAE | 46 | 0 | 0 | 1 | 45 (97.8%) |
| Singapore | 229 | 2 (0.9%) | 11 (4.8%) | 3 | 213 (93.0%) |

(Re-run in review on the same saved fetch with the script as it is now. The first version of this table, 85–100% saying
nothing, came from a run before the "mentions a visa" pattern was widened; Singapore's refusals include T141's
"citizens and PRs only" wording.) These are pattern counts. In a sample of one posting per company, read by hand,
"refused" was right 12 of 12 and "offered" 10 of 12; a refusal written as a bare requirement ("Right to work in Singapore")
lands in "no clear answer". The offers come from few companies: 116 offering postings in all places, 79 of them Anthropic's.

So the employer's public record is used instead: **`job_hunt/data/visa_sponsors.json`**, built by
`scripts/build_visa_sponsors.py` from:

| Source | What being on it means | Size (2026-10-21) | Reuse terms |
|---|---|---|---|
| UK: GOV.UK [register of licensed sponsors: workers](https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers) (2026-10-20) | licensed to sponsor Skilled Worker or Global Business Mobility visas | 123,205 organisations on those routes | Open Government Licence v3.0 |
| Netherlands: IND [public register "Work"](https://ind.nl/en/public-register-recognised-sponsors/public-register-regular-labour-and-highly-skilled-migrants) (2026-10-05) | recognised sponsor, which the highly skilled migrant permit needs | 13,012 | none stated on the page |
| Ireland: DETE [employment permits issued to companies](https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/statistics/), 2025 and Jan–Sep 2026 | permits actually granted, with the count per year | 12,715 employers | Government of Ireland copyright: reuse with the source acknowledged |
| Community lists: [abhi-jha's gist](https://gist.github.com/abhi-jha/5225e0dcc912174dda6b7f01e8a24156), [shubheksha's list](https://github.com/shubheksha/companies-sponsoring-visas) | named as hiring from India with visa and relocation | 130 names | none stated |
| [relocate.me's list](https://github.com/AndrewStetsenko/tech-jobs-with-relocation) (T141) | hand-checked: the company's postings or careers page offer visa or relocation help; each entry with its places | 95 companies (Germany 23, Netherlands 17, UK 9, Singapore 1) | CC0-1.0 |
| USA: USCIS [H-1B Employer Data Hub](https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub), FY2024 (T143) | H-1B petitions approved for the employer that year: new employment and extensions | 51,839 employers with at least one approval | US government work (public domain) |
| Canada: ESDC [positive LMIA employers list](https://open.canada.ca/data/en/dataset/90fed587-1364-4f33-a9ee-208181dc0b97), 2025Q2–2026Q1 (T143) | a positive Labour Market Impact Assessment, the approval most employer work permits need; positions per quarter and how many are software occupations | 31,843 employers | Open Government Licence – Canada |

A community list counts only for the places its entry names (T141): the gist's "Berlin, Germany" says nothing about the
company's jobs in Dubai; an entry for "Remote" or "Global" counts everywhere. The file holds only companies on `companies.json`,
each with the source's own entry (Canva: "CANVA UK OPERATIONS LIMITED" with its two UK routes, and the gist's "London"; an
Irish employer's permit counts per year), never a copy of a register. **2026-10-21: 534 of the 1,589 companies have evidence** (UK 467, Netherlands 185, Ireland 84, lists 18).

**How names are matched, and checked.** An *exact* match agrees once legal suffixes and country words are dropped
("Google (UK) Limited" is Google). A *loose* one agrees only once generic words go too ("Stripe Payments UK Ltd" is Stripe).
A name is not proof: "Stripe Partners", "Amazon Filters Ltd" and "Phoenix Software Limited" are other businesses. So a loose
match counts only when someone has accepted it in **`scripts/visa_sponsor_review.json`**, and any match listed there as
rejected is dropped. All 890 candidate matches of 2026-10-21 were read: 103 rejected, and the 189 loose ones kept were each
accepted there (the other 598 kept are exact). An exact match is not proof either: "TGS UK LTD" on the UK register is
a Bristol coachbuilder (Companies House), while the list's Tgs board is TransPerfect's games testing; it is rejected in the
review file (found in review, 2026-10-21). The rejected
ones are mostly names that are ordinary words (Phoenix, Shift, Mesh, Healthcare, Lighthouse) and other firms with the same
name ("Pico Technology" is not Pico Quantitative Trading). The verdicts went by name, the company's job-board slug and general
knowledge, not by company records; unsure ones were rejected. One independent check: every company whose UK, Dutch or Irish
postings offer sponsorship and that is on that country's record was found (10 of 10). The other 4 are on no record under
their own name.

**What the record does not say:**
- **That a given job is sponsored.** 17 of the 44 companies whose UK postings refuse sponsorship are licensed UK sponsors
  (Graphcore, Addepar, Esri, …). A posting's own "no" outweighs the record.
- **Anything about a company registered under another legal name.** Meta's UK entity, for example, is "Facebook UK Ltd".
- **What happened after the download.** The registers change every month, so rebuild.

**Rebuilding** (from the repository folder; it downloads about 13 MB into the git-ignored `data/visa_sources/`):

```bash
python scripts/build_visa_sponsors.py --report /tmp/visa.csv            # download, match, write the file
python scripts/build_visa_sponsors.py --offline --report /tmp/visa.csv  # same downloads (after a discover --merge)
```

It prints how many loose matches are *unreviewed*; those are not used. Read them in the report (Status `unreviewed`), add each
company's entry to `accepted` or `rejected` in the review file, and run again with `--offline`. `--emit-seeds /tmp/s.txt`
writes the community-list names that are not on the list yet (111 on 2026-10-21), ready for `discover --add-file`.
On 2026-10-21 none of the 111 passed (T135). **34 have a live board but no India job**: Monzo, N26, HelloFresh, Delivery
Hero, SumUp, Plaid, Palantir, Mercari, Ninja Van, Trainline, Miro, Algolia and others, 3,141 jobs in all (Qonto's Lever and
Ashby boards carry the same jobs and were first counted twice). Of the report's other rows (a name can have more than one),
63 have no board on a supported ATS (Apple, Bloomberg, Zalando, …), 8 failed the identity check and 9 boards are stale. So the India gate keeps
out exactly the employers that hire people from India to move abroad. **With T139** (`--places` with the six countries) 27
of them joined the list, each with its `places`: Monzo, N26, HelloFresh, Delivery Hero, SumUp, Plaid, Palantir, Trainline,
Miro, Algolia, Ninja Van, Qonto, Raisin, Tipico and others. Mercari, BlaBlaCar, Back Market, Jam City, Circles.life and
Sunday have no job in those six countries. After that the record covers 561 of 1,616 companies (UK 478, Netherlands 189,
Ireland 86, lists 45); the three new loose matches (Monzo Bank Ltd, Raisin Platforms Limited, SumUp Payments Limited) were
read and accepted. With relocate.me's list (T141, rebuilt 2026-10-21 with the UK register of that day): **563 of 1,616**
(UK 478, Netherlands 189, Ireland 86, lists 49).

**T142** checked the three lists' 167 other names for the 29 countries their entries name (`discover --places`, every country
now has a pack): 34 verified; read by hand, 3 were another company with the name (`ashby/lightspeed` is LightSpeed Build
Technologies in Illinois, not Auckland's Lightspeed; `ashby/clark` and `ashby/sunday` are US start-ups, not Berlin's Clark
and Sunday: "named in N/N job descriptions" proves nothing for a common word), removed and added to `KNOWN_BAD_BOARDS`. The
other 31 joined: Mercari, Wayve, Mollie, Coolblue, Bol.com, Betsson, Flow Traders, Back Market, BlaBlaCar, Smartly.io, Tractable
and more. Record rebuilt: **594 of 1,647** (6 new loose matches read: 4 accepted, 2 rejected).

### Germany, the UAE and Singapore (T141)

These three publish no register of sponsoring employers, and searched for on 2026-10-21, none was found: their rules make one
unnecessary. What a posting that says nothing still tells you, read on the official pages that day:

| Country | The rule | Source | Visa note for a silent posting |
|---|---|---|---|
| UAE | "The employer must apply for the standard work visa"; employers "may not recruit or employ any worker unless a work permit is issued in accordance with MoHRE procedures" | [u.ae, Work visa](https://u.ae/en/information-and-services/visa-and-emirates-id/Types-of-visas/residence-visa-for-working-in-the-uae); [u.ae, Work permits](https://u.ae/en/information-and-services/jobs/Sector-of-employment/employment-in-the-private-sector/work-permits) | `UAE: the employer applies for the work visa` |
| Singapore | "You can apply for an Employment Pass online as an employer or appointed employment agent"; the job must first be advertised on MyCareersFuture (page updated 15 June 2026) | [MOM, Apply for an Employment Pass](https://www.mom.gov.sg/passes-and-permits/employment-pass/apply-for-a-pass) | `Singapore: the employer applies for the Employment Pass` |
| Germany | The EU Blue Card is the professional's own residence permit; no licence for the employer. From €50,700 a year (2026) no approval of the Federal Employment Agency; shortage occupations and career starters from €45,934.20, with its approval | [Federal Employment Agency, EU Blue Card (03/2026)](https://www.arbeitsagentur.de/vor-ort/zav/working-and-living-in-germany/iss-en/issue-03-2026/blue-card) | `Germany: no sponsor licence needed (EU Blue Card)` |

The note follows the posting's own words and any record, e.g. `Not stated; on a relocation list; Germany: no sponsor licence
needed (EU Blue Card)`. A rule is not a promise for one job: a posting that refuses keeps `Posting: no visa sponsorship`, and
nationals-only roles count as refusals ("Emirati National required", "Singaporeans only"). On the 2026-10-21 fetch 4 of 9,884
described postings had such wording, all read: Tamara's "Emirati National required" and Deliveroo's UAE-nationals talent pool
are real; Infoprolearning's 2 ("support Emiratisation objectives through the training of UAE National employees") are a job
duty. So only the explicit forms are used, and Deliveroo's (which says only "Emiratisation") is missed.

Looked at and **not used**, with the reason: Arbeitnow's free job API (`visa_sponsorship=true`, mostly Germany): on 2026-10-21
the filtered page's postings offered sponsorship in 20 of 280 and refused it in 17, against 4 of 300 unfiltered, too weak to call
evidence. Singapore's Tech@SG programme endorses companies' Employment Pass applications but publishes only its list of investment
firms, not the companies. A company's other postings in the same country: on the 2026-10-21 fetch, 0 of 232 silent engineering
postings in these three countries were at a company whose other postings there offer sponsorship (UK: 24 of 301), so it was not
built. No Dubai-specific list was found.

### The USA, Canada, Australia and New Zealand (T143)

**Can someone in India be hired straight into a US job?** Yes, but rarely, and never quickly. Read on the official pages on
2026-10-21:

- **H-1B** is the usual work visa, and the employer applies for it. Each March the employer registers the person, and USCIS
  draws among the registrations ("a weighted selection", by the wage level offered) for 65,000 places plus 20,000 for US
  master's graduates. Only someone selected can be petitioned for; work starts on 1 October at the earliest. The FY2027 cap is
  reached ([USCIS, H-1B electronic registration](https://www.uscis.gov/working-in-the-united-states/temporary-workers/h-1b-specialty-occupations-and-fashion-models/h-1b-electronic-registration-process),
  updated 09/21/2026).
- **The $100,000 payment.** A presidential proclamation of September 2025 added it to new H-1B petitions for people
  *outside* the United States, which is exactly a hire from India. A Massachusetts court vacated USCIS's guidance for it on
  8 June 2026 (California v. Mullin); DHS appealed and says it will still collect the payment if the order is lifted
  ([USCIS, H-1B FAQ](https://www.uscis.gov/newsroom/alerts/h-1b-faq), read through a web search: uscis.gov refuses
  scripts). News reports (CUPA-HR, JURIST) add that a Washington DC court upheld the proclamation in December 2025, appeal
  pending, and that the First Circuit refused DHS a stay in July 2026; neither was read on an official page. A USCIS news
  release also proposes a separate $103,265 fee for all cap petitions, not final. However the courts decide, an employer weighs
  that cost before choosing a candidate abroad over one already in the country.
- **L-1** moves an employee from the company's office abroad to its US office. The person must "generally have been working
  for a qualifying organization abroad for one continuous year" in the three years before
  ([USCIS, L-1A](https://www.uscis.gov/working-in-the-united-states/temporary-workers/l-1a-intracompany-transferee-executive-or-manager),
  updated 08/31/2026; L-1B is the same for specialised knowledge). There is no lottery. For someone in India this is the
  realistic way in: join the company's India office, then transfer. 534 of the 551 companies with a US record below are on
  the list because they have India jobs (the list's own rule), so most have the office for it. Whether a given India entity
  is a "qualifying organization" is the company's legal question, not something the list can tell.

| Country | The rule | Source | Visa note (unless the posting refuses) |
|---|---|---|---|
| USA | as above | USCIS pages above | `USA: from abroad, H-1B is a yearly lottery the employer enters (a $100,000 fee for it is in court); L-1 after a year with the company abroad` |
| Canada | an employer that needs an LMIA hires through the Temporary Foreign Worker Program (its Global Talent Stream aims to decide in 10 business days); some permits need none (an intra-company transfer, for one); a Federal Skilled Worker needs no job offer for permanent residence through Express Entry, which the person applies for (after an invitation) | [ESDC, hire through the Global Talent Stream](https://www.canada.ca/en/employment-social-development/services/foreign-workers/global-talent.html); [IRCC, Federal Skilled Worker Program](https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/who-can-apply/federal-skilled-workers.html) | `Canada: the employer usually needs an LMIA, or you apply for PR yourself (Express Entry)` |
| Australia | "Apply to become an approved sponsor, nominate the role you need to fill, then nominate the person you wish to employ" (Skills in Demand visa, subclass 482, since 7 Dec 2024); no public list of sponsors | [Home Affairs, becoming a sponsor](https://immi.homeaffairs.gov.au/visas/employing-and-sponsoring-someone/sponsoring-workers/becoming-a-sponsor) (quoted through a web search: the page refuses scripts) | `Australia: the employer must be an approved sponsor (Skills in Demand visa)` |
| New Zealand | the employer must be accredited, advertise the job, and pass a job check (declined if a suitable New Zealander was available) before the person applies for the Accredited Employer Work Visa | [INZ, AEWV accreditation and job check](https://www.immigration.govt.nz/work/for-employers/getting-accreditation-or-approval-to-hire/employer-accreditation-for-the-aewv/aewv-employer-accreditation-and-job-check-process/) | `New Zealand: the employer must be accredited and pass a job check (AEWV)` |

Since T143 a country's rule is added unless the posting refuses, so also after "Posting: offers visa sponsorship": a US
posting that sponsors H-1B still means the lottery for someone abroad.

**The two downloads.** *USA:* uscis.gov answers scripts with HTTP 403, so the builder takes
[JohnBroberg/H1B_Hub](https://github.com/JohnBroberg/H1B_Hub)'s copy of the hub's own yearly export (MIT; FY2024 is the newest
there). Checked against the official totals: the copy's FY2024 approvals add up to 141,206 new and 258,195 extended, against
the 141,207 and 258,196 that Pew Research quotes from USCIS; the difference is one row with no employer name, which is left
out. A newer year saved from the hub in a browser goes in with
`python scripts/build_visa_sponsors.py --offline --us-h1b "$HOME/Downloads/Employer Information.csv"`, which replaces only
that file. "New" approvals are new employment: a cap petition, *or* a worker already in the US changing employer, so the count
says the company sponsors, not how many it hires from abroad. *Canada:* the last four quarters, found through the open-data
portal's API. A position is an approved vacancy, not a person who came; the list leaves out employers named after a person.

**Matching** works as for the UK (exact names, loose ones read by hand), with the US file's own ways handled: a trade name
after "D B A" ("RAINTANK INC DBA GRAFANA LABS" is Grafana Labs, "INTERVIEWSTREET INC DBA HACKERRANK" is HackerRank), letters
written apart ("OPENAI L L C", "ADYEN N V") and the suffixes PBC and OPCO ("ANTHROPIC PBC", "OPENAI OPCO LLC"); "Canada" is a
country word like "UK" ("Autodesk Canada Co." is Autodesk). All 749 candidate matches were read on 2026-10-21: USA 584 kept
(497 exact, 87 loose accepted) and 92 rejected (19 of them exact: "PEARL INC" is not the Pearl of JustAnswer, "OBSERVE INC" is
not Observe.AI, "A52 LLC D B A ELASTIC" is a design studio, "S. A. MIRO, INC." is an engineering firm); Canada 61 kept and 12
rejected ("Vyn Inc." with 18 farm positions). Where unsure, the board's own jobs were read (Azul's Prague and Bangalore jobs say
Azul Systems; Ashoka's Arlington, VA jobs say the non-profit), else rejected. The UK, Dutch and Irish matches came out the same
as before. **Record rebuilt: 798 of 1,647 companies** (797 since the review removed Tgs's wrong UK match; UK 486, then 485; Netherlands 199, Ireland 86, lists 80, USA 551, Canada 61).

**Australia and New Zealand have no list to download.** Australia publishes no register of approved sponsors. New Zealand's
accredited-employer lookup is a search for one name, which an employer can opt out of; it was not used.

**How US and Canadian postings word it** (`scripts/measure_visa_wording.py`, 2026-10-21 fetch of the 1,044 boards whose list
API carries the description, titles with an include word):

| Country | Engineering jobs | Offers | Refuses | No clear answer | Says nothing |
|---|---|---|---|---|---|
| USA | 3,786 | 138 (3.6%) | 196 (5.2%) | 270 (7.1%) | 3,182 (84.0%) |
| Canada | 459 | 1 | 8 (1.7%) | 15 (3.3%) | 435 (94.8%) |
| Australia | 122 | 1 | 2 | 3 | 116 (95.1%) |
| New Zealand | 12 | 0 | 0 | 0 | 12 |

Read by hand, 12 random US "offers" and 12 "refuses" were all right. The first reading of 12 "no clear answer" found
refusals the patterns missed because "U.S." has dots in it ("must already have unrestricted U.S. work authorization",
"must be a U.S. citizen" for a security clearance), and one company's investor "Visa Ventures". After the fix 151 postings
became refusals, every distinct sentence read (citizenship for clearance, ITAR and FedRAMP work; work authorization), and 71
"Visa Ventures" ones became silent; the six earlier countries' counts did not move. Still counted as no clear answer:
"Visa transfers, including OPT and H1B transfers, are supported" (it helps someone already in the US, not someone abroad) and
Roblox's "may not be able to ... support future H-1B sponsorship".

### Keeping only companies that sponsor visas (T144)

Manish, 2026-10-22: *keep a company if it sponsors visas, irrespective of a specific job post; otherwise there is no point adding it
(a company that sponsors no role today may sponsor one later).* So a company added **for other countries** (an entry with `places`)
must show evidence; the 1,589 India companies need none. `scripts/filter_by_visa_evidence.py` applies it to what `discover`
verified:

```bash
python scripts/filter_by_visa_evidence.py --candidates /tmp/v1.json /tmp/v2.json --postings /tmp/posting_evidence.json \
    --out /tmp/kept.json --report /tmp/filter.csv      # then: autopilot discover's merge, or merge_companies, into companies.json
```

A company is kept when, for a country it hires in, **one** of these holds: it is on that country's sponsor record (UK register,
Dutch IND register, Irish permits, US H-1B, Canadian LMIA) by an exact match, a *squashed* match (the same name without spaces,
six letters or more: "Cloudimperiumgames" = "Cloud Imperium Games Ltd") or a loose match accepted by hand in
`scripts/visa_sponsor_review.json`, where an exact match on a name of five letters or fewer must be accepted too (T144 review:
"River" matched a hospital's trade name, "UK-Med" a software firm's); it is on a community list for that country; or one of its postings offers visa sponsorship.
A record for a country it does not hire in does not count (a Dutch register entry says nothing about a German job); a Workday
entry records every country checked, so any record counts. **The review file doubles as an alias list**: a name accepted there
counts although no rule proposes it ("SFDC Ireland Limited" for Salesforce, "WAL MART ASSOCIATES INC" for Walmart; this settles
T145). Postings that only offer *relocation* do not count (87 companies; add them if you want).

What it did on 2026-10-22 (the sources that had finished; Workable's 12,585 boards are not in it: that run was stopped after 8.9 h with no output because Workable throttles this machine
(task T160, seeds in 13 batches of 1,000); they go through the same filter when checked):

| Platform | Verified and new | Kept |
|---|---|---|
| Greenhouse | 818 | 204 |
| Ashby | 757 | 186 |
| Recruitee | 1,599 | 145 |
| Personio | 1,385 | 13 |
| SmartRecruiters | 433 | 77 |
| Lever | 228 | 49 |
| Workday | 298 | 188 |
| **Total** | **5,518** | **900** (list 1,647 -> 2,547; 863 after the review below: 2,510) |

By country, new companies kept by the first pass (862): United Kingdom 486, Netherlands 257, Germany 166, France 107, Spain 93, Poland 83, Ireland 78,
Singapore 75, Italy 69, Sweden 68, Portugal 62, Belgium 61, Denmark 54, Switzerland 52, Austria 48, Czechia 44, UAE 44, Norway
41, Luxembourg 41, Finland 37, Estonia 34, Lithuania 34 (Workday entries record every country and are not counted here). Germany,
France, Spain and Poland publish no register, so there the evidence is mostly a posting or a list: 166 of the 2,363 German companies
found were kept.

**The price of the rule, measured.** The 4,190 non-Workday companies dropped had 46,441 jobs in the 22 countries and 1,783 that match
Manish's title filter, at 836 companies; the 674 kept have 10,404 jobs and 703 title matches at 237 companies. Most title-matching
jobs in the new boards are at companies with no sign of sponsoring, and the rule leaves them out on purpose. Companies were also
left out before the filter: 5 job aggregators ("LinkedIn Job Wrapping", "Third-Party Job Posts", "Alumni Network Job Board", AppDirect's
"Recruitment as a Service", an internal logistics board) and 23 recruitment agencies, whose postings hide the employer; none of the
637 agency jobs in Europe shared title and city with a job on another board (measured), so duplicates were not the reason.
The weak name matches (183 companies before the merge, 116 after) were read by hand: 201 register names accepted, 138 rejected
(common words or another company: "Axiom", "Proton", "Open", "Planet"; "Puma Energy" is not PUMA, "Weber Shandwick" is not Weber),
and 64 names accepted as aliases for 28 big Workday employers whose register names differ (Walmart, Gilead, Maersk, Repsol, …).

**A second look at the dropped companies with title-matching jobs (836, 1,783 such jobs).** Manish: add them if sponsorship can be
verified online, so that nobody has to look it up by hand. Three routes were tried on them, measured:

- *Postings of any country and the company's own site* (careers, about, benefits pages found from links in its postings): on 80 random
  ones, a website was found for 10, one posting offered sponsorship and no site said anything: about 1%, so not worth running.
- *Web search* (12 companies, the ones with the most such jobs): usable evidence for 1 (Ebury, through an aggregator quoting the UK
  register); the rest returned job-board noise, third-party tags ("visa sponsorship: not available" for DRW) or relocation text with no
  visa wording (Nord Security, Satispay, Wolt). Not a bulk method.
- *The official registers, by name prefix* (the register's entry begins with the company's name: "Ebury Partners UK Ltd", "DRW
  Investments (UK) Ltd", "DOIT International UK&I Ltd"), restricted to the registers of countries the company hires in: 87 of the
  836 had a candidate, read by hand; 52 register names accepted for 38 companies, 198 rejected (common words: Planet, Slice,
  Marble, "Ashby Capital LLP"). These 38 joined the list.

The other 798 stay out: no evidence from a register, a list, a posting or the web. The same prefix check on the other ~3,800 dropped
companies (no title-matching job) was not run.

**Record rebuilt (2026-10-22): 1,711 of 2,547 companies** (1,712 before the review rejected Tgs's UK match, T133; UK 1,104, Netherlands 494, Ireland 146, lists 93, USA 853, Canada 94).

**The review of T144 (2026-10-22): an exact name is not the same company.** The first pass trusted every exact and squashed match
unread, and several put a company on the list on another business's record (Harmonic on "Harmonic (UK) Ltd." in Farnborough, the
video firm; Ramp on "The Ramp", a Manchester church; Fca, the Financial Conduct Authority's tenant, on Fiat Chrysler's; 7 Eleven,
the Australian licensee's tenant, on the US company's). So every kept record of the entries added for other countries whose name
is five letters or fewer, made only of dictionary words, or a squashed match was read against the board fetched under its own
places (its job locations and how its postings describe it): 430 entries, 572 records, and 89 records of theirs for other
countries; the other 491 entries were checked automatically (register town, US state or Canadian province against the board's
job locations; a non-tech industry or a low-wage stream) and the 141 flagged ones read too. Where a reading left a doubt, the web
was searched (Companies House, SEC subsidiary lists, the press): 27 records, 10 confirmed (UK Bandwidth Limited is in Bandwidth
Inc's SEC subsidiary list; Airspace B.V. is Airspace's European base). **67 records were rejected**, 10 of them loose names the
first pass had accepted by hand (Faculty Services Limited in Edinburgh is not Faculty AI; Duna AI Limited is a Limerick start-up
of 2026). Where unsure, rejected. **38 entries left the list**: 37 with no evidence left and Pulse Healthcare, a staffing agency
the agency check missed. The India list's 184 short-name records were read as well (2 rejected: Neara Ltd, Aleph The Netherlands
Corporation B.V.). Via was then put back by the verifier: the rework had found its UK subsidiary in Via's 10-K, "Via Transportation
UK Ltd.", which is on the UK register (London, Skilled Worker and Global Business Mobility) but which no name rule links to "Via";
it is now accepted as Via's alias, so 37 entries left. **Record rebuilt: 1,668 of 2,510 companies** (UK 1,069, Netherlands 486,
Ireland 145, lists 92, USA 838, Canada 89). What was not read then: exact matches of longer, non-dictionary names outside the 141 flagged, and the India list's
dictionary-word names (230 records). Those 230 (120 companies, American Express to Zeta Global) were read on 2026-10-23 (T154):
229 are the company's own entity; "Fusion Consulting Ltd" (London) is rejected, since the board's Fusion Consulting hires in Barcelona,
Frankfurt, Lisbon and nowhere in the UK. **Record rebuilt: 1,667 of 2,510 companies** (UK 1,068). Still not read: exact matches of
longer names that are not dictionary words, on the India list and outside T144's 141 flagged (T152 asks for a guard for future rebuilds).

**The scan uses it** (T138): with `candidate.countries` set, every job outside your home country gets a **Visa** column in
the CSV: what the posting says, then this record for its country ([docs/05](05-outputs-and-notifications.md)).

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
| Workday | `POST {tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`, `searchText="India"` (per country, see below) | 20/page, ≤2,000, 600 s/tenant | no → enriched | "Posted N Days Ago" text |
| Oracle HCM | `{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions`, India location facet (per country) | 100/page, ≤2,000 | short only → enriched | `PostedDate` |
| Eightfold | `{host}/api/pcsx/search?domain={domain}&location=India` (per country), details from `/api/pcsx/position_details` | 10/page, ≤1,000, 600 s/board; 429 → retry after 3–48 s | no → enriched | `postedTs` (epoch) |
| Phenom | `POST {host}/widgets` (`refineSearch`, country India, or the list of your countries), details from the job page's JSON-LD | 100/page, ≤1,000 | no → enriched | `postedDate` |
| Amazon | `www.amazon.jobs/en/search.json?country=IND` (per country code) | 100/page, ≤4,000 | yes | `posted_date` |
| Workable | `apply.workable.com/api/v1/widget/accounts/{slug}?details=true` | whole board | yes | `published_on` |
| Recruitee | `{slug}.recruitee.com/api/offers` | whole board | yes | `published_at` |
| Personio | `{slug}.jobs.personio.de/xml?language=en` | whole board | yes | `createdAt` |

**Your countries (T137).** Five ATSs answer only for the country they are asked about. With `candidate.countries` set (T136),
each asks for yours instead of India: Workday runs one full-text search per term ("United Kingdom" and "UK"; "United Arab Emirates"
and "Dubai"; the country name for the others, because the spellings find different jobs: at ABB "United Kingdom" found 37 and
"UK" 60, measured 2026-10-21; 74 different jobs in all), all terms sharing one 600 s budget. A job another term already returned
is kept once and the term reads on (until the review fix, "UK"'s first page of such jobs ended it: ABB gave 44 of its 74).
Eightfold one search per country name (the same rule); Phenom one search
with the list; Amazon one per country code (GBR, DEU, NLD, IRL, ARE, SGP); Oracle HCM one read per country facet. An Oracle site
lists only its biggest locations as facets (10 on most), so when one of your countries has none, the site is read once without a
facet, newest first, and the posted-date window stops it. India alone sends exactly the requests above. Measured on 15 boards for
UK + Singapore (7-day window, 324 s): Workday 13–132 UK jobs per tenant, Eightfold Qualcomm 20 + 20, Phenom (BCG) 92 UK, Amazon 759
UK and 134 Singapore, Oracle (the facet-less read) American Express 45 UK. Searching several terms means more requests: Accenture
answered HTTP 429 to some, and its fetch stopped at offset 120 with 384 jobs (counted as incomplete, so nothing is marked closed).

**Rate limits.** An HTTP 429 ("too many requests") is asked again after 2, 5 and 12 s on every adapter (T114); Eightfold keeps
its own longer retry (3–48 s). A Workable board still refused after that is logged by name and its fetch counts as
incomplete, so its stored jobs are not marked closed.

**Workday caveats**
- **India search.** Only jobs that Workday's search matches for "India" (or your countries' terms, above) are fetched.
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
