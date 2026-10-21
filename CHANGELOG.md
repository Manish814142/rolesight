# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Dates are omitted for pre-1.0 releases that predate this changelog and were
reconstructed from git history.

## [Unreleased]

### Fixed (2026-10-21, T140 follow-up: what an audit of the international path found)
- `rolesight init --resume CV --countries "…"`: the resume draft's `seeking` was asked for "your city, or anywhere in India or
  remote" whatever the countries, which brings back the location mark-down the end-to-end run found. With countries other than
  India the prompt now asks for the roles in those countries and the visa sponsorship and relocation needed; India's prompt is
  byte-identical to before (compared with the committed one).
- The Telegram alert of a job outside your home country carries its Visa note (`🛂 Visa: …`); India's alert is unchanged.
- `autopilot` help lists `init --countries`, `check-filter --countries` and `discover --places`.
- Docs brought in line with the international path: ARCHITECTURE (pipeline, `places.py` and `visa.py`, discover's gate, rule 1,
  the Visa column and alert, the limitation), README (location rules, the Visa column, the layout, the pre-filter row), the user
  guide (what you can change, `cities`, `init --countries --resume`, rule 1 and your countries, the funnel's `In your places`,
  `discover`, the filter table), `docs/07` (the place rules for other countries), `docs/08` (five symptoms), `docs/01`, the docs
  index and CLAUDE.md (the package map, `config.json`).

### Added (2026-10-21, T140: T108 part 5, init --countries, the guide, the end-to-end run)
- `rolesight init --countries "United Kingdom, Germany"` writes `candidate.countries` (as the built-in names) into `config.json` and
  keeps the rest; while `candidate.seeking` is still the example's text (it names Bengaluru) it is replaced with one naming your
  countries and the visa you need. Both example configs carry `"countries": ["India"]` and `"home_country": "India"` (the same as
  leaving them out). The user guide's new section **Looking for jobs outside India**; `docs/07`, `docs/10`, the README.
- **The end-to-end run (T108's Done when).** A fresh folder, `init --yes --countries Singapore`, six boards (Thoughtworks, Databricks,
  Airwallex, Nvidia, Qualcomm, Salesforce), a real `scan` with Gemini: 1,618 jobs fetched, 249 in Singapore; Workday (Salesforce: 32
  Singapore jobs) and Eightfold (Qualcomm, Lam Research) searched for Singapore; 18 jobs scored by Gemini over three runs, incl.
  Salesforce's (Workday) and Qualcomm's (Eightfold) with `--posted-within 30`; the CSV's Visa column filled.
- Two fixes from that run. (1) The Visa column said "Not stated" for Thoughtworks Singapore postings that "require the successful
  candidate to be a Singapore Citizen or PR", which Gemini capped: citizenship and residence requirements are now refusals (on T133's
  fetch, 23 of 9,884 described postings change class, all read: real requirements, e.g. GitLab "Must be a Singapore Citizen"; one
  false hit, Deliveroo's broken word "pr ocess", fixed by reading "PR" in upper case only). (2) The example's `seeking` ("Remote, or
  hybrid in Bengaluru") made Gemini mark an Airwallex Singapore office job down to 25 "for the Bengaluru preference"; with the
  replaced text the same job scored 45 on its real gap (a JVM language).

### Added (2026-10-21, T139: T108 part 4, discover checks your places; 27 employers that hire abroad)
- `autopilot discover --places "United Kingdom, Germany"` (default: `config.json`'s `candidate.countries`, else India): a board needs
  a job there instead of in India. An entry accepted for other countries records them (`"places": [...]` in `companies.json`); the
  monthly recheck checks every entry against its own places (each in its own worker thread, `places.using`), and a scan fetches an
  entry with `places` only when your countries include one of them, so **an India scan fetches exactly the 1,589 it fetched before**.
  The Workday light check runs one first page per search term until one shows a job there. The report's `india_jobs` column is now
  `place_jobs`; the India verdict is still `no India jobs`.
- **27 employers joined the list**: T135's 111 community-list names checked for the UK, Germany, the Netherlands, Ireland, the UAE
  and Singapore: Monzo, N26, HelloFresh, Delivery Hero, SumUp, Plaid, Palantir, Trainline, Miro, Algolia, Ninja Van, Qonto, Raisin,
  Tipico, Trivago, GoCardless and others (1,589 → 1,616; every accepted row read; the 1,589 entries unchanged). The visa record was
  rebuilt for them: 561 of 1,616 companies (3 new loose matches read and accepted).

### Added (2026-10-21, T138: T108 part 3, scoring and a Visa column for your countries)
- **The rubric follows your countries.** With `candidate.countries` other than India alone, rule 1 ("cap 30 for on-site work outside
  India…") becomes: cap 30 for on-site or hybrid work outside your countries, and for a posting that cannot sponsor a visa or asks
  for citizenship, permanent residence or an existing right to work there (you live in `home_country` and need sponsorship); a
  posting silent on visas is not capped. Rule 5's "Location fits (India or Remote)" names your countries. Only these two built-in lines
  change, also in a `rubric.md` drafted by `init --resume` (whose rule 1 stays the built-in one); a rule 1 you rewrote is used as
  written, with a warning. Structured scoring's location lines and its cap label follow too. **India alone: the same text and id
  (`82e017b4`).**
- **A Visa column** in every CSV and Excel file, for a job outside your home country: what the posting says ("Posting: no visa
  sponsorship" / "offers visa sponsorship" / "unclear" / "Not stated"), then the company's public record for that country from
  T133 ("UK licensed sponsor", "Dutch recognised sponsor", "N Irish work permits", "on a relocation list"), e.g. `Not stated; UK
  licensed sponsor`. `autopilot export` writes it from the stored descriptions. India alone: no Visa column, the CSV is unchanged.
  New `job_hunt/visa.py` holds T133's wording patterns (moved from `scripts/measure_visa_wording.py`, which imports them).

### Added (2026-10-21, T137: T108 part 2, the connectors search your countries)
- Workday, Eightfold, Phenom, Oracle HCM and Amazon answer only for the country they are asked about; with `candidate.countries`
  they now ask for yours. Workday: one full-text search per term (UK: "United Kingdom" and "UK", UAE: "United Arab Emirates" and
  "Dubai", measured: the spellings find different jobs), sharing the seen-job set and the 600 s budget; a failed term keeps what the
  others returned. Eightfold: one search per country. Phenom: the list of countries. Amazon: one search per country code. Oracle HCM:
  one read per country facet; when a country has no facet on the site (sites list only their biggest locations), one read without a
  facet, newest first, stopped by the posted-date window. **India alone sends the same requests as before** (the existing adapter
  tests, unchanged, still pass). Measured for UK + Singapore on 15 real boards: every connector returned jobs there (Amazon 759 UK
  and 134 Singapore; Phenom 92 UK; Workday up to 132 UK at Accenture, whose fetch was cut by HTTP 429 at offset 120).

### Added (2026-10-21, T136: T108 part 1, your countries in the pre-filter)
- **`candidate.countries`** (default India) and **`candidate.home_country`** (default India, where you live) in `config.json`. New
  `job_hunt/places.py` holds a pack per country: United Kingdom, Germany, Netherlands, Ireland, United Arab Emirates, Singapore and
  India (its names, cities, the codes boards write: Amazon's "Dubai, ARE" and "SGP", SmartRecruiters' "Berlin, de", and the regions
  that include it). "UK", "UAE", "Holland", "Deutschland" and the like resolve; another country is matched by its name, with a
  warning in the scan log. A city that also exists in North America ("London, Ontario", "Dublin, OH", "US-CA-Dublin") does not count.
- The pre-filter: **India alone keeps its rules unchanged** (your config through the old and the new filter, both saved fetches:
  0 of 111,106 decisions or reasons differ). For other countries: a location naming one of them passes, a region of one of them passes
  when it names no other place ("Remote - EMEA", not "EMEA - UK"), worldwide and remote-with-no-place pass, the rest is rejected
  ("not in your places"). Measured on the 2026-10-21 fetch with the six countries and Manish's title filter: 1,027 jobs pass
  (UK 366, Singapore 107, Germany 93, Ireland 73, Netherlands 66, UAE 27, a region 15, remote with no place 278); for a UAE config
  no job with a passing title and a Dubai/UAE location was rejected.
- `rolesight check-filter … --countries "UK, Germany"` (default: config.json's). The scan log names the countries, and the funnel
  says "In your places N" instead of "India N" when they are not India alone.
- The connectors still ask Workday, Eightfold, Phenom, Oracle HCM and Amazon for India jobs (T137 next).

### Added (2026-10-21, T133: visa-sponsor evidence per company, groundwork for T108)
- Manish: the people he has in mind are in India and will relocate, so "company should provide visa as well"; most postings
  will not say, so use public datasets of which companies sponsor.
- **`scripts/measure_visa_wording.py`** counts how postings in the UK, Germany, the Netherlands, Ireland, the UAE, Singapore and
  "Europe/EMEA" word visa sponsorship (offered, refused, unclear, nothing), relocation help and "must live here" wording. Measured
  on 2026-10-21 on the 989 boards whose list API carries descriptions (71,121 jobs, fetched in 3 min 26 s): engineering-titled
  postings say nothing about a visa in 84.9% (UK, 557 jobs), 93.6% (DE), 88.8% (NL), 92.5% (IE), 100% (UAE, 46), 97.8% (SG); when
  they do, a refusal is more common (UK: 56 refused, 20 offered). Pattern counts, checked by reading samples by hand (second
  sample, one posting per company: refused 12 of 12 right, offered 10 of 12); two misses of the first sample were fixed.
- **`job_hunt/data/visa_sponsors.json`**, built by **`scripts/build_visa_sponsors.py`**: the companies on `companies.json` that
  appear on the GOV.UK register of licensed sponsors (2026-10-20, Open Government Licence), the IND public register of recognised
  sponsors (2026-10-05), DETE's employment permits issued to companies (2025 and 2026), or two community lists of companies hiring
  from India with visa and relocation, each with the source's own entry. **534 of 1,589 companies** (UK 467, NL 185, IE 84,
  lists 18). Names are matched exactly or loosely (generic words dropped); a loose match counts only when accepted in
  `scripts/visa_sponsor_review.json`. All 890 candidate matches were read: 103 rejected (ordinary-word names such as Phoenix,
  Shift, Mesh; other firms of the same name). Check: every company whose UK, Dutch or Irish postings offer sponsorship and that is
  on that record was found (10 of 10). 17 of the 44 UK companies whose postings refuse sponsorship are licensed: the record says a
  company can sponsor, not that a job is sponsored. `--offline` rebuilds from the downloads; `--emit-seeds` writes the community-list
  names not on the list (111). The scan does not read the file yet (T108). Guide: `docs/04`, "Visa sponsorship".
- **T135:** those 111 names through `discover --add-file … --no-recheck`: **none passed**, so `companies.json` is unchanged. 35 have a
  live board for the right employer with no India job (Monzo, N26, HelloFresh, Delivery Hero, SumUp, Plaid, Palantir, Mercari, …;
  3,184 jobs), 63 no board on a supported ATS, 8 identity not confirmed, 9 stale. The names are recorded in `scripts/company_seeds.txt`
  for when `discover`'s gate follows the person's places (T108).

### Fixed (2026-10-21, T134)
- **T134:** a normal install (`pip install .`, or a wheel) now ships `job_hunt/data/`, so `autopilot init` works without `-e`.
  `.gitignore`'s `data/`, meant for the root `data/` folder, also matched `job_hunt/data/`, and the wheel builder (hatchling) leaves
  out what `.gitignore` matches: the 0.4.4 wheel built from the tree held none of `companies.json`, `config.example.json`,
  `env_example`, `resume_template.md` or `__init__.py`, and `autopilot init --yes` stopped with `No module named 'job_hunt.data'`
  (measured in a fresh venv). The rule is now `/data/`: the wheel holds all five, and `init` from it writes `companies.json` (1,589
  companies), `config.json`, `.env`, `rubric.md` and the resume template. The guide
  and CI use `pip install -e .`, which reads this folder, so neither showed it. A test asks git whether anything in `job_hunt/data/`
  is ignored.

### Fixed (2026-10-18, T132 and two review follow-ups)
- **T132:** `discover --add-file FILE` or `--add TEXT` with no company name in it (an empty file, blank lines, comments, `--add ","`,
  or an explicitly empty value such as `--add "$NAMES"` with an unset variable) now stops ("holds no company name", exit 1). Before,
  that read like no `--add` at all and `discover` checked every line of `scripts/company_seeds.txt` (1,491 names, hours of network);
  the census writes such an empty file when it recognises no board. `.gitignore` now covers `discover`'s default `discovery_report.csv`
  and `verified_companies.json`, and the README's examples pass scratch paths.
- **T123:** the before/after push checks name the files from the repository root (`:/companies.json`): run from `scripts/`, the
  after-check had said "GitHub has the current list" while the lists differed, and the before-check had printed nothing.
- **T117:** the tie-break test puts the main-title site between the others by name, so a tie broken by name in either direction fails
  it (a descending one passed before).

### Docs (2026-10-18, T131: a guide to growing the company list)
- Manish: "if someone wants to increase the company list … they get the ground to work on top of that instead of doing from scratch."
  `docs/04-companies-and-scanning.md` had the 223-board counts of 2026-10-06, said Eightfold and Phenom had no adapter and did not
  mention the bulk harvest. Its new **Growing the list** section: the one gate (`discover`'s four checks), the three ways in (a pasted
  list, the careers-page census, the bulk harvest of `scripts/harvest_board_urls.py` incl. Oracle HCM names from page titles), every
  seed-line format, the traps a report can hide (aggregators, Metro Manila "NCR", same-slug boards, Oracle names, one-posting boards),
  the monthly recheck, what a bigger list costs (fetch and Gemini, measured) and where to grow next (rerun the harvest; adapters for
  Freshteam, Zoho Recruit, Keka, and what an adapter needs). The scan section: Eightfold and Phenom in the enrich step, the Phenom row,
  Workday's cap of 2,000, the 429 retry, and the measured scan times of 2026-10-12/14/15. CLAUDE.md no longer says Oracle sites are not
  harvested; `discover --help` shows the `exact` seed line and its options; README, the docs index and the user guide link the guide.
- After jobnotify-70's review of T131: the guide says to run `discover` from the repository folder and that it needs no API key, lists
  the report's verdicts, warns that the default re-check removes failing entries, stops step 2 when the census wrote no seed line,
  adds `--out` to every recheck example (it left `verified_companies.json` in the current folder), says how to remove an entry by
  hand, and corrects Lever EU (no adapter), the source of the 2026-10-04 timing (the root `scan.log`) and the census file's 506 URLs.
  `docs/08` links the renamed recheck section.

### Changed (2026-10-18, T130: a clean `output/`, a fixed `last_scan.*`, dated files in `history/`, drafts in `drafts/`, and the link-click note)
- Manish (screenshot of `output/`): "I want the output path clean so a user is not confused by so many files; the newest file should not be at the bottom of 100 files." Chosen with him: the lighter variant (the CSV twins of the two fixed files stay at the top),
  "no monthly subfolders, leave my existing files alone, no auto-delete". Now: **`open_matches.xlsx/.csv`** (the jobs this scan found to apply to) and the new **`last_scan.xlsx/.csv`** (everything this scan scored, whatever the score, the same table and row order as
  the dated file, so row N is still job N for `draft N` and `mark N`) keep their names and are replaced by every scan; **`history/`** holds the dated pair of every scan (`jobs_DATE[_N].csv` and `.xlsx`, never overwritten) and what
  `autopilot export` writes; **`drafts/`** holds `autopilot draft` output (`output/drafts/<company>-<date>/`, before `output/<company>-<date>/`). A scan that scores nothing adds nothing to `history/` and leaves both fixed files with the header only. RoleSight deletes
  no dated file and has no clean-up setting (Manish: users keep the delete control); files written before T130 are not moved. `export_jobs()` now returns the CSV's path, `draft_application()` the folder, and the MCP tools say where the file is (the
  skill reads `last_scan.csv`/`open_matches.csv` or the file the export reply names).
- A fixed file that cannot be replaced (open in a spreadsheet on Windows, where a rename over an open file fails) is now a **warning**, not an exception: before, `os.replace` raised at the end of the scan, after the scan row was finished but before the Telegram digest.
  The same helper writes `open_matches` and `last_scan` (beside its name, then moved over it, and its Excel copy).
- Docs: README, user guide, `docs/01`, `04`, `05`, `06`, `09`, ARCHITECTURE, CLAUDE.md, PRIVACY.md and the skill describe the layout; `docs/00` and `docs/05` say how a link opens in each program (Excel: one click; LibreOffice: Ctrl+click unless "Ctrl-click required to open
  hyperlinks" is unticked in Tools → Options → LibreOffice → Security → Options; Google Sheets: hover card), so a user on another system does not think the links are broken; a test checks the guides name no removed path and carry that note.
- Measured, real network and real Gemini, in an empty scratch folder that already held old-style files: scan 1 (6 companies, 12 jobs scored, 1 at 70 or more) wrote exactly `history/jobs_DATE.{csv,xlsx}`, `last_scan.*` (12 rows, byte-identical to the dated CSV) and `open_matches.*` (1 row);
  `draft 1` and `mark 1 applied` acted on row 1 of `last_scan.csv`; `export` and `export --days 7 --min 70` wrote `_1` and `_last7d` pairs into `history/`; scan 2 (nothing new) left `history/` as it was and both fixed files with 0 rows (csv and xlsx);
  the three old files kept their checksums; no `.tmp` left. LibreOffice 7.3 opened both fixed workbooks. **Not tested:** a really locked file (Windows; simulated by a test that makes the replace raise), anything on Windows or macOS, Excel.
  `scripts/verify_ats_and_score.py` (a one-off) still writes its report at the top of `output/`.
- 22 new tests (`tests/test_output_layout.py`: fresh folder, second scan, empty scan, weak-only scan, old files, export, drafts, both MCP tools, locked file, the guides); 17 mutants each fail a test (three survived the first run: a test checked "history" against all of a test's
  log records, including an earlier INFO line, and the exporter's own default folder was never used; both fixed). 30 existing tests now look in `history/` and `drafts/`.

### Changed + Added (2026-10-17, T128: columns in reading order, and a formatted Excel report beside every CSV)
- Manish, after opening the sample run: Score was the 8th column, behind two long links. "Worth Applying at the end is okay"; "csv or excel, any format works, you decide"; "what else can we do: formatting, text size, colouring?"
  The CSV columns are now **Score (%), Company, ATS, Role, Location, Posted, Reason, Application URL, LinkedIn people, Worth Applying, Scan Date** (optional columns, Model and Rubric still follow). `Worth Applying` stays in `open_matches.csv`
  (always `Yes` there): dropping it would have been a special case across the writer, the tests and the docs for one narrow column. Files written earlier keep the old order; readers that use the header names are not affected.
- New `job_hunt/xlsx_report.py`: beside **every** CSV (the scan's `jobs_*.csv`, `open_matches.csv`, `autopilot export`) a workbook of the same rows under the same name (`.xlsx`), built from the CSV just written. Header row dark blue, bold and
  frozen together with Score and Company; a filter on every column; Score a number, **green** from 85 (unless Worth Applying says No) and **amber** when Worth Applying is Yes below that; Role, Location and Reason wrapped with rows sized to
  their text; Application URL and LinkedIn people are "Open" and "Search" cells that carry the links; widths set; Calibri 11 named on every font; landscape, one page wide, header repeated. Text from a job board is always stored as
  text (a title starting with `=`, `+`, `-` or `@` is not a formula), control characters are dropped from the report, an address beyond 2,000 characters stays plain text. The report is secondary: a failure (a file open in Excel on Windows,
  a missing library) logs `Excel report … not written`, removes an older report of that name and the scan goes on; it is written beside its name and moved over it. `openpyxl>=3.1` is now a core dependency (`pyproject.toml`,
  `requirements.txt`; `test_packaging.py` had asserted it was unused).
- Seen in a LibreOffice 7.3 render of the first version and fixed: wrapped rows kept one line's height (text drawn over itself), and the header, links and scores came out in a serif font because the fonts had no name.
  Measured: the final 49-row report and a 735-row one (`autopilot export --days 30` on a copy of the real database, 0.5 s, 22 printed pages, header repeated on page 2) open in LibreOffice and read back with openpyxl. **Not tested:** Excel.
  This also answers T126 for anyone who opens the `.xlsx`: no import dialog, the letters are right (the CSV is unchanged, UTF-8 without a byte-order mark).
- 29 new tests (`test_column_order.py`, `test_xlsx_report.py`: unit, real scan, `autopilot export`, a failing save, and LibreOffice converting the `.xlsx` back to CSV when it is installed); 19 mutants each fail a test (an earlier run of the
  mutation harness reused stale bytecode for four of them and reported them killed by the wrong test; fixed and rerun).

### Docs (2026-10-17, after the T121–T125 review: testing checklist, test counts, a real 11-company run)
- `docs/09-testing-checklist.md` still recorded 398 tests (2026-10-04). Now 1,749 passed, coverage 93.34%, ruff and mypy clean (measured on the tree after the reviewer's fixes). Added: `autopilot schedule status` as a keyless smoke test
  (and why `schedule on` is not a test to run on a working machine), the ATS column and the T124 `open_matches.csv` meaning in the "real, small scan" steps, and that `--limit N` takes the first N companies (Amazon alone queued 44
  jobs on 2026-10-17, measured by fetching and pre-filtering), with a recipe for a trial in an empty folder that keeps the real `data/jobs.db` and `output/` untouched. The T121/T124 test counts above now include the reviewer's tests.
- A real scan of 11 companies (Cisco, Hewlett Packard Enterprise, Renesas Electronics, NielsenIQ, Bosch, ServiceNow, UKG, JPMorgan Chase, Rubrik, Kong, Proximity Labs; 7 job systems) was run from an empty folder with a fresh
  database and no Telegram: 11/11 companies, 49 jobs queued, 49 scored, 0 failed, 6.0 min. `jobs_*.csv` has 49 rows × 11 columns, ATS second and filled on every row; `open_matches.csv` has the 13 jobs of that run with a score of 70
  or more, best first, all of them also in the jobs file. Both open in LibreOffice (converted to .xlsx and read back with openpyxl: 49 and 13 rows, same header). The files are UTF-8 without a byte-order mark; LibreOffice 7.3
  started headless guessed a legacy encoding and garbled 5 cells ("Karnātaka", a non-breaking space), and with UTF-8 chosen at import none (a copy with a BOM did not help in that LibreOffice; Excel not tested). Noted in the user guide.

### Fixed (2026-10-17, T125: what happens to a scheduled run when the computer is off, and numbers that were still 224)
- Manish asked what happens when someone schedules the scan for 06:00 on Ubuntu and the laptop is off then. `schedule on` and the docs said a missed run is "made up when it is back on". More exactly (systemd.timer(5) on this
  machine: `Persistent=true` triggers the service when the timer is activated if it would have run while the timer was inactive): the **user** timer is activated when the user manager starts, which is **at login**
  (`Linger=no` here, measured with `loginctl show-user`; `loginctl enable-linger` makes it start at boot). With cron the run is skipped. The command's output and the guides now say so, and that nothing is lost for good (7-day
  window, jobs already seen are not scored twice). Not tested: a real power-off and login, and a suspended laptop (expected to run on wake; inferred).
- The README intro and `docs/10` still said 224 boards, and the README's ATS table still showed the first 224 (82 Workday, 74 Greenhouse, …): now 1,589 and the counts of `companies.json` (checked against the file).

### Changed (2026-10-17, T124: `open_matches.csv` shows what the last scan found, not every job still unmarked)
- Manish (pasted note): "I don't think anyone marks jobs applied by hand… until the web UI is built, show only the current run's jobs on `open_matches.csv`, not the old ones." The T39 list kept every job ≥ `min_score`
  until `autopilot mark` said otherwise, so with nobody marking it only grew. Now `output/open_matches.csv` holds the jobs **the scan that just ran scored** at or above `min_score`, not marked applied, inside
  the posted-date window (best first, same columns); a scan with nothing new leaves the header and no rows. Nothing is lost: every scored job is in that day's `jobs_*.csv` and in `autopilot export --days N`.
  `"open_matches_scope": "all_open"` in `config.json` brings the T39 rolling list back; any other value stops the scan before it fetches anything. The 10 tests that pinned the rolling list now set `all_open`;
  17 new tests (14 + the reviewer's: interview, rejected and offer marks also keep a job off the list); 7 mutants (scope ignored, `min_score` or applied filter dropped, default flipped, scope not validated, config not passed on, empty run falling back to the rolling list) each fail a test.

### Added (2026-10-17, T121: `autopilot schedule on | off | status`, the daily scan as an opt-in switch)
- Manish: "if someone wants to schedule it on a daily basis it runs automatically, but don't start it on my laptop; give users the option to turn it on and off, by default it's off." New
  `job_hunt/scheduler.py` and the command `autopilot schedule on [--at HH:MM] [--method auto|systemd|cron]`, `schedule off`, `schedule status`. **Off by default**: no other command or module touches
  the scheduler (a test checks both the calls and the imports). `on` uses the systemd user timer of T07 where `systemctl --user` works, else one crontab line ending in `# rolesight-scan` (also what macOS gets);
  every other crontab line is kept as it was, an unreadable crontab is never overwritten, turning one method on removes the other (one run a day), `off` removes only `job-hunt-scan.*` and the marked line (not the
  monthly recheck units, not `job-hunt-wallpaper.*`), and `status` only reads. Windows: `on` explains the Task Scheduler steps and changes nothing. Tested with stand-in `systemctl` and `crontab` programs at the front of PATH
  (the real `install.sh` and real subprocess calls run against them; the fixture checks first that PATH resolves both names to the stand-ins): 39 tests (38 + the reviewer's); a cron line is run through `/bin/sh` in cron's bare environment
  against a copy of the real `run_daily.sh`; 20 mutants, 1 survived and got its test. Measured on this machine, read-only: `schedule status` → OFF, and the real `systemctl --user` and `crontab -l` agree (no
  `job-hunt-scan` unit, no crontab). **Not run:** the real `systemctl enable` and a real cron daemon (turning either on here was not allowed), anything on macOS or Windows.

### Fixed (2026-10-17, T121 review: a clone in a folder whose name has a space or %)
- The units `install.sh` writes put the clone's path unquoted into `ExecStart=`/`ExecStartPre=`. systemd splits a command line at spaces
  unless the word is quoted and reads `%` as a specifier (systemd.service(5), systemd.syntax(7)), so for a clone in `~/my repo` the
  timer was ON and every run would have started `bash ~/my`: shown with systemd's own parser (`systemd-analyze verify` on a probe
  unit: `Command …/my is not executable`). The path is now double-quoted with `%` → `%%`, `$` → `$$`, `\` and `"` escaped, and `%`
  doubled in `WorkingDirectory=`; the same probe now passes for `my repo` and `100% done` (a `$` in the path is handled per the manual,
  not provable with `verify`). Both the scan and the recheck units. Also a test that a failed switch from cron to systemd keeps the
  cron line (a mutant that removed cron first survived).

### Fixed (2026-10-17, T119: the scan unit's timeout)
- `scripts/systemd/job-hunt-scan.service.in`: `TimeoutStartSec` 3 h → 4 h. With no cap on the jobs scored (T118) a day can score 1,000 jobs (500 per model): measured 6.1–7.5 s a job, so ~125 min of scoring plus ~17 min to fetch
  the 1,589 boards, ~2.4 h in the worst case; 3 h left little room for retries. The comment in the unit no longer says "30-40 minutes".

### Added (2026-10-17, T122: an ATS column in the CSV)
- Manish: "add the source of the ATS in the excel, so a person can filter by the ATS they want to apply on." Every CSV (the scan's `jobs_*.csv`, the rolling `open_matches.csv`, `autopilot export`) has a column **ATS**
  right after Company, holding the id the board is listed under in `companies.json` and in `data/jobs.db` (`greenhouse`, `lever`, `workday`, `oracle_hcm`, …). It is always written, like Company. Measured on a copy of the real
  database: `autopilot export --days 30` wrote 735 rows, no blank ATS cell (workday 476, amazon 80, smartrecruiters 53, oracle_hcm 44, greenhouse 33, eightfold 32, ashby 9, lever 4, workable 3, phenom 1).
  Files written before this change have no such column; the next scan rewrites `open_matches.csv` with it.

### Fixed (2026-10-17, T117: an Oracle HCM entry is named after the site that is scanned)
- Found by the review of T112 (jobnotify-fa): the harvest named every site of a host with the title most of the host's sites carry, while `discover` keeps the host's busiest site, which can
  be another employer's: 3 of the 104 entries were named after the wrong employer (ADI for Resideo's site, Lutech for McDermott's, Tumi for Samsonite's) and 3 after another site's region
  (First Solar (US), Intertek UK, Novotech China); the six were renamed by hand. Now each site is named by **its own** page title (a site whose title names nobody takes the host's main title),
  a host's sites are written together with the main-titled ones first (so a tie in India jobs goes to the host's main brand), and `merge_companies` keeps **one Oracle entry per host**, the
  first given, which is the busiest site: two employers on one host are one entry (Manish: "do needful for the t117"; measured on the 104 hosts: 8 have sites with different titles, and
  keeping them all would add small-subsidiary entries such as eight SVKM colleges).
- Tested end to end on 2026-10-17: the list without its 104 Oracle additions, the archive's 2,092 Oracle URLs, new seeds, `discover` (147 sites verified), merge. The Oracle part of the list comes out as the same 108
  employers (1,589 entries as now); 104 are identical in name and scanned site to the current list, including Resideo, McDermott and Samsonite, which the rule now gets right by itself; the other four
  carry their site's own title (First Solar India, Intertek Global, Novotech Global, SVKM enterprize for the host named NMIMS). The names already in `companies.json` are not changed (the merge keeps
  existing entries).

### Changed (2026-10-17, T118: no cap on the jobs scored per run)
- Manish: "there should be no cap, on my account I have 500 per model limit so total 1000 I can run; first 500 on the 3.5 flash lite model, the rest on 3.1 flash lite, so it should
  switch automatically when it hits the limit." `max_jobs_to_score_per_run` now defaults to **0 (no cap)**; it was 400 (T04). The switch to the second model already existed (T64: a
  model whose daily quota is gone is skipped until the reset, the next in the chain answers) and the quota breaker (T03) still ends the run when both are out. New
  `tests/test_two_model_day.py` runs those numbers through the real `run_scan` with a stub client: 700 jobs -> 500 scored by the first model and 200 by the second, with the first
  asked once after its limit; 1,100 jobs -> 500 + 500 scored, 100 left `discovered` and no more pacing pauses than answers (the stop works). The old test of the default cap now
  asks for a cap explicitly. Newest first still holds, so if both models run out mid-run the oldest postings are the ones left over.
- Not measured: a real run against Gemini's quota. The two daily limits and the reset (midnight Pacific, 12:30 IST) are as Google documents and as T64 measured on 2026-10-07; each
  stored score still names the model that gave it (the CSV's `Model` column shows when it was not the first one), and scores of the two models differ (T70).

### Added (2026-10-17, T112: 104 Oracle HCM employers, found by the page title)
- Manish ("if these are open issues then fix them"). Oracle HCM candidate sites are written `cbcz.fa.us2.oraclecloud.com`: the host is a customer code, so T111 left the
  archive's 2,092 Oracle site URLs (1,892 distinct sites) out. The employer's name is in the title of the site's own page (`<title>Hilton</title>`; the REST fields
  `LegalEmployer`, `BusinessUnit` and `Organization` were empty on all 34 sites sampled). `scripts/harvest_board_urls.py` now has a query per Oracle data centre
  (`oracle-us2` … `oracle-ocs`, `oracle-fa`; the whole `oraclecloud.com` domain times out), reads each site's page, and cleans the title (`clean_site_title`: "Hoya Global Career
  Site" → "Hoya", "Careers | BXP" → "BXP", "Career Site(Servify)" → "Servify", JSON escapes and entities decoded; error pages, "Candidate Experience site", bare industry words such as
  "Aerospace" and a few non-English phrases give no name, and a site with no name is not a seed). On Oracle the host is the employer: every site of a host gets the host's most
  common title, a host already in `companies.json` is skipped, test and development instances (`…-dev12`, `…-test-saasfaprod1`) are skipped, and `discover` keeps the host's
  busiest site. About 1,630 of the 2,092 URLs (78 %) gave a name by their own page title (measured on the last two runs: 1,634 and the final one); 1,585 seeds on 902 hosts; **148 sites on 104
  employers passed** (live, at least one India job, a recent posting): Quess, Tata Capital, Fortis, Adani, Havells, KPMG Global Services, Essar, eClerx, Honeywell, Zensar, Nokia,
  IHG, Citco, DP World, Aster DM Healthcare, American Express, Akamai, Hilton, Icertis, Daimler Truck, DTCC … **1,488 → 1,592 boards** (Oracle HCM entries 4 → 108). The recheck run on the
  result flagged three of T111's additions that had lost their one India posting by then (Loopio: Toronto only; International SOS Government Medical Services: US and Iraq; Ryansg: three
  postings, none in India); they were dropped: **1,589 boards**. The other three it flags are the existing Confluent, Fi Money and Cloudflare, left for Manish as before.
- Review fix: one name per host was the host's most common title, but `discover` keeps the host's busiest site, which can belong to another
  employer. The review read each kept site's own title: 96 of 104 matched; renamed in both copies: ADI → **Resideo** (the site is Resideo's, its
  descriptions say "Join Resideo's…"), Lutech → **McDermott** (McDermott's site, Chennai engineering roles), Tumi → **Samsonite**, First Solar (US) → First Solar,
  Intertek UK → Intertek, Novotech China → Novotech. Legrand and NMIMS (SVKM's site) were kept. Jobs are stored by host and requisition id, so a name
  changes only the Company shown in the CSV, the LinkedIn column and drafts.
- The harvest tool carries on when the Internet Archive does not answer for one query (it did for `oracle-us2` after 4 tries): the others are kept, the failed one is named on
  stderr, the exit code is 3.
- Not done: of the 1,892 distinct Oracle sites 1,585 became seeds; the rest have a page title that names nobody and no named sibling on their host (or are test instances or on a host already listed). They would need another source of the name.

### Fixed (2026-10-16, T114: an HTTP 429 is asked again, not read as an empty board)
- **Measured cause.** Workable (behind Cloudflare) refuses about half the requests of a sustained burst: 457 of 1,500, 713 of 1,200 and 374 of 700 in three bursts at 20
  parallel (it started after about 800 requests), with an HTML body and `Retry-After: 0`, and recovers in about ten seconds (a single probe was refused at 4 s and 8 s, accepted at 12 s).
  No 429 at up to 20 parallel for the 103 Workable and 39 Recruitee boards of the list (one request each), so a scan's 8 workers rarely hit it; a bulk `discover` run does. Recruitee's 429s
  were seen in that run's log. The Workable adapter returned an empty list on a 429 at debug level, so a scan lost the board's jobs without a word, and `discover`'s probe counted
  such boards dead (13 of 100 sampled "no live board" verdicts were alive).
- `adapters.base`: every request (`http_get`, `http_post`) that is answered with 429 is asked again after 2, 5 and 12 s; the server's `Retry-After` is only a floor for the pause (its
  `0` would ask again at once), capped at 30 s; the last 429 is returned as it is. `retry_429=False` opts out (Eightfold keeps its own, longer retry). `harvester._probe` does the same.
  Workable, still refused after that, now warns by name and marks the fetch incomplete (`HTTP 429 from Workable`); a 404 stays quiet.
- Real A/B on 60 Workable boards that all have jobs, fetched at 20 parallel right after a burst had put Workable into 429: **old behaviour 43 of 60 returned jobs (17 lost), new 60 of 60** (29 s).

### Fixed (2026-10-16, T113: the Workday light check, found by the review of T111)
- `discover`'s Workday check (used for new Workday seeds and by the monthly `--recheck`) read the first 20 results of the `India` search and counted the ones whose
  location text names India. Workday writes "2 Locations" for a posting with several, and the real adapter resolves those with a detail call (T23); the light check did not.
  Northern Trust's search has 99 hits, but its first 20 read "2 Locations" ×3, "Chicago, IL", "Luxembourg"…, so the recheck called it "no India jobs" and would have
  removed it. When the first page shows no India job, the check now resolves up to 8 such postings with the adapter's own detail call and stops at the first India one
  (`adapters.workday.is_multi_location`, `fetch_detail_locations`, `WORKDAY_DETAIL_CALLS`). Northern Trust now passes (1 India job found).
- **Workday maintenance no longer looks like dead boards.** While a data centre is in maintenance Workday redirects every request to `community.workday.com/maintenance-page`.
  The adapter knows (T76); the light check read the HTML as "no open jobs", and a monthly recheck run in such a window would have removed every Workday tenant on that
  data centre (seen live on 2026-10-16: `wd102` was in maintenance, Hotstar, Minor, Piramal and Vena answered with the page). It is now an `error` row: a new seed is not accepted
  on it, an existing entry is kept and flagged.

### Changed (2026-10-16, T116: three job aggregators leave `companies.json`)
- Manish ("drop the 3 aggregators"): Jobs for Humanity (SmartRecruiters, 2,000 postings on every fetch, 12 pass the title and location filter, several "only for women" or
  "only for persons with disability"), Jobs for Lebanon (1,401, none pass) and Eram Talent (Workable, 1,272, none pass) repost other employers' jobs under their own name,
  so the CSV's Company column and the LinkedIn link name the agency. Measured again before removing: 2,000 / 12, 1,401 / 0, 1,272 / 0. **1,491 → 1,488 boards.** The smaller
  recruiters stay (GenZS Recruitment solutions, Ezrecruiting, InstaTalent Recruit LLP). All three were T111 additions; the 224 originals are untouched.

### Fixed (2026-10-16, T115: "NCR" in a Philippine location is Metro Manila, not Delhi)
- Found by the review of T111. `NCR` was in the list of Indian cities, so `Makati City, NCR, ph` (SmartRecruiters writes the country as a lower-case code)
  counted as India: Philippine jobs passed the location filter, and `discover` admitted boards whose only "India" jobs were in Metro Manila. `NCR` is now no
  evidence of Delhi when the same location names the Philippines (`ph`, Philippines, Manila and its cities, `prefilter.without_philippine_ncr`); any other
  Indian term in the location still counts ("Makati, NCR, ph; Pune, India" stays India). `discover` has its own location check and uses the same rule.
- Measured: on the saved fetch of 2026-10-13 (39,985 jobs) 3 locations change, all Philippine, and 0 pre-filter decisions; on a fresh fetch of all 1,514 boards (164,053 jobs)
  396 locations change, all Philippine NCR ones and none Indian, and 10 jobs that passed the title and location filter (and would have reached Gemini) no longer do.
- Review fix: someone who chooses Delhi NCR (or NCR) in `candidate.cities` still got Metro Manila jobs, because the chosen-city check runs before the India
  check; `city_matches` now applies the same rule. On a fresh fetch of the 1,514 boards (167,608 jobs) with `cities: ["Delhi NCR"]`: 10 Manila jobs passed
  before this fix, 0 after; with no cities chosen (the default) no decision changes.
- Removed from `companies.json` (Manish, 2026-10-16: "fix the filter and drop the 21"): the 21 boards admitted only on Metro Manila jobs (AireSpring, Arch Global Services
  (Philippines), Canyon GBS, Dashlabs.ai, Deep Blue Company, Delivery Hero, Fredley Group of Companies, Growthdesk, Ikano-Retail, Keywords Studios, Lendi Group, Much Prosperity
  Trading International, Okos Smart Homes, PETA Asia, Pilmico Foods, Pronto Marketing, Santen, Simplesat, Talent, Wrist, Questronix) and two more of T111's additions that the
  recheck found without a job in India or without any job (Appfire, Herewith Caregivers). **1,514 → 1,491 boards.** The 224 originals are untouched; the four existing
  entries the recheck also flags (Confluent, Fi Money, Cloudflare, Northern Trust) stay, as before, until Manish decides.

### Added (2026-10-16, T111: `companies.json` grows from 224 to 1,514 boards)
- **Manish asked for as many companies as possible** ("more options to apply to different types of company"). `scripts/harvest_board_urls.py` lists the
  job-board root pages the Internet Archive has seen (Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, Personio boards and Workday
  sites; 51,456 boards) and Common Crawl's 2026 crawls added 2,657 more that the archive lacked, written as `Name | board URL | exact` seed lines.
  `discover` checked all 54,113 (live, at least one India job, a posting no older than 180 days): **1,290 passed and were added** (greenhouse 504,
  workday 303 (221 new), smartrecruiters 207, ashby 192, lever 151, workable 105, recruitee 39, personio 3; the 224 originals are unchanged).
  511 of the new companies (40 %) have a role passing the title and location filter today, and their boards hold 14,285 India jobs (measured
  with `discover`'s report; Workday counts the first page only). Recent Common Crawl boards passed at 11 % against 3 % for the archive's old ones.
- `discover`: an `exact` seed probes only its own board (no slug guessing on every other ATS: 37 requests per board saved) and takes the company
  name from the board where the ATS publishes one (spaces and invisible marks tidied); every site of a Workday tenant is checked and the one with most
  India jobs kept; one board that makes the fetch raise is an `error` row, not the end of a 30-minute run; `--workers` now also bounds the
  verification phase (Workable and Recruitee answer HTTP 429 to many parallel requests and the adapters read that as an empty board: at 20 workers 13 of 100
  sampled Workable "no live board" verdicts and 19 of 100 Recruitee were alive when probed one at a time; a second pass at 3 workers found 17 and 28 more).
- Not added, by choice: Oracle HCM sites (about 2,090 in the archive; the host is a customer code such as `cbcz.fa.us2.oraclecloud.com`, so there is no
  company name to show), Greenhouse EU and Lever EU boards.
- Measured cost of the bigger list (the scanner's own `run_scan` on a copy of the database, Gemini stubbed, 7-day window, 2026-10-16): 224 boards: 34,325 jobs
  fetched, 18,084 in India, 63 to score, fetch 5.3 min, scan 6.1 min. **1,514 boards: 133,412 fetched, 32,621 in India, 320 to score (about 22 min of Gemini
  calls at 4.2 s), fetch 9.5 min, scan 16.6 min without scoring.** The 320 are the 7-day backlog of the first scan; a day later only the new postings are scored.

### Fixed (2026-10-16, T111: found by growing the list sevenfold)
- **The monthly recheck (`discover --recheck`, T28) read rate limits as dead boards.** `companies.json` is sorted by ATS, so 12 workers sent Workable 12 requests
  at once; 34 of the 86 Workable boards were reported "no open jobs" and would have been removed. The likely cause is HTTP 429, which the adapter reads as an
  empty board (not seen in that run; 8 of 8 sampled boards returned jobs when fetched alone, and after the change no Workable board is flagged). Entries now go out round-robin over the ATSs, a "no open jobs" answer is asked again two at a time before an entry is dropped, and a board whose
  check raises is kept and flagged (`error`) instead of ending the check. On the 1,515-entry list: 42 changes before, 5 after. The five left: Confluent and Fi Money (empty on their
  boards since 2026-10-14), Cloudflare (436 jobs, none in India) and Northern Trust (a false alarm: its Workday search has 99 hits but the light check reads
  20 and cannot resolve "2 Locations" postings, Inbox T113) are existing entries and Manish's call, so they stay; ABBYY (5 jobs, none in India) was new and was dropped.
- The Greenhouse adapter raised on a board whose job has `"location": {"name": null}` (or a null title): `discover` died 8 minutes into a run. It reads null as empty.

### Fixed (2026-10-15, T110: every age is counted in local days)
- Found by jobnotify-7f's review of T109: the same UTC date in two more places. `discovery.newest_age_days` took "today" from UTC (measured
  by the reviewer: a posting 181 days old counted 180 and its board was accepted), and the day a job was first seen or scored was the UTC
  date of its stored timestamp (`first_seen[:10]`, `scored_at[:10]`). That day matters for Workday's relative "Posted N Days Ago": a job read
  at 05:16 IST was dated from the day before, so `open_matches.csv` dropped it a day early. `prefilter.local_date_of` gives the local day of
  a stored timestamp; `db._unseen_inside_window`, `scanner._write_open_matches` and `discovery.newest_age_days` use it or `date.today()`.
  Tests pin `TZ=Asia/Kolkata` and 2026-10-14 23:46 UTC (05:16 IST the next day): 4 red before, green after; putting back each old line fails
  them. Left as they are, on purpose: the export cutoff (UTC against UTC timestamps), the CSV's `Scan Date` column (a label, UTC's date; the file name's date is the local one), and posting
  timestamps turned into a UTC date by the adapters (the board's own ±1 day; every age is computed from it the same way).

### Fixed (2026-10-15, T109: the window-miss rule used UTC's date)
- `db._unseen_inside_window` (T78: a board whose fetch stopped at the posted-date window counts a miss only for jobs inside the window, with a
  day of margin) took today's date in UTC, while the window itself (`prefilter.is_too_old`) and every other age use the local date. From 00:00
  to 05:30 IST UTC is a day behind, so a job at the window's edge looked a day newer and counted a miss, eating the margin; three such scans
  could close a job that was still open. Found when `tests/test_window_closing.py::test_the_last_day_of_the_window_gets_a_margin` failed at
  05:16 IST on 2026-10-15 (passing the day before). It now uses the local date; a new test sets the local date a day after UTC's, so it fails on
  the old code at any hour.

### Added (2026-10-14, docs/10: limitations and future work)
- `docs/10-limitations-and-future-work.md`: what is still fixed to one setup and where in the code (India in six places, among them four
  adapters that ask the board for India jobs only; the reachable job boards; Gemini's free tier, score noise, a rubric measured for one
  person, AI-made test labels; scheduling, Telegram, no web UI), and the ideas not started (other countries, scoring a job found anywhere,
  a short daily list, learning from the person's decisions, referrals, follow-ups, interview prep, region company lists). Linked from the
  README, `docs/README.md`, `ARCHITECTURE.md` and `CONTRIBUTING.md` (Manish: no development now; publish what is left so others can extend it).
- Found while writing it and checked with `rolesight check-filter`: `"cities": ["Dubai"]` already lets "Dubai, United Arab Emirates" through
  the filter (a chosen city counts even when the India lists do not know it), but remote jobs open to India still pass and the adapters
  still fetch India only, so it is not a working setup for Dubai (T108).
- Stale text corrected: the README's known gaps no longer list the rule-1 problem fixed by T79 and now lead with "India only";
  `ARCHITECTURE.md` no longer says generic "Senior Engineer" titles are not scanned (scored since T96).

### Changed (2026-10-14, backups of the key files are ignored)
- `.gitignore` ignores `config.json.bak*` and `.env.bak*`: a dated backup of Manish's `config.json` (`config.json.bak-2026-10-14`, holding his key)
  showed up as untracked, so a careless `git add` could have committed it. Backups now go to `data/backups/` (ignored, folder 700, files 600).

### Fixed (2026-10-14, T105: key files readable by their owner only)
- `init` wrote `.env` and `config.json` with the umask: 664 here (group-writable, world-readable), and since T103 `init --resume` can save the
  Gemini key into `.env`. Both are now created with mode 600 from the first byte (`onboarding.write_private`), and saving a typed key
  tightens an existing `.env` to 600. `rolesight doctor` warns when `.env` or `config.json` holds a real key (not a placeholder) and others
  can read it: `[WARN] Key file: .env holds a key and other users can read it (mode 664): run chmod 600 .env`. Measured: a real `init` with
  umask 002 gives `.env` 600, `config.json` 600, `companies.json` 664; the check on this checkout's own files (664, real keys) reports both.

### Changed (2026-10-14, T104: a titles block that leaves a list out says so)
- A `candidate.titles` block is still taken as written, but without `exclude` (no title rejected for a word) or `generic_engineer_titles`
  (bare "Senior Engineer" titles not scored) the scan log and `check-filter` (on stderr) now say what that means and how to change it.
  `"exclude": []` written out does not warn. The note is not part of the rules (`TitleRules` equality unchanged).

### Fixed (2026-10-14, T106: every "current rubric" follows rubric_file; SDE6-SDE9)
- The MCP `export_jobs` tool compared stored scores with the built-in rubric, not the person's `rubric_file`, so their own scores showed
  in a `Rubric` column as older. Through a real MCP client: with the fix no column, with `tools.py` reverted the column is back.
  `scripts/rubric_ids.py` had the same blind spot; it now prints `Your rubric (rubric.md): <id>` and marks that id `(current)`.
- The default include list has `sde6`-`sde9` again (the old `sde\d*` took any number; T103 listed `sde1`-`sde5`). Re-measured: 0 of
  39,985 jobs and 0 of 34,624 titles decided differently; still different: SDE10 and above written without a space (0 in that data).

### Fixed (2026-10-14, CI's secret scan: two fake test keys)
- The first push of T103 failed CI's gitleaks job: `generic-api-key` on a fake key written out in `tests/test_onboarding.py`. Run locally over the whole
  history (gitleaks 8.24.3, CI's version, checksum verified), it also found an older one, `tests/test_doctor.py` (T92); neither is a real key (my
  pre-push scan checks real key formats). The tests now build their fake keys at run time, as `tests/test_public_release.py` already asked, and
  `.gitleaks.toml` allows exactly those two strings, which history keeps: full history 383 commits → no leaks; the change itself → no leaks.

### Added (2026-10-14, T103: everything personal is configurable; `init --resume` drafts it from a resume)
- **The title filter is word lists in `config.json`** (`candidate.titles`: `include`, `exclude`, `exceptions`, `generic_engineer_titles`),
  no longer regexes in `job_hunt/prefilter.py`. An entry matches as whole words in any case; spaces and hyphens inside it are optional
  ("back end" also matches "Back-End" and "backend"); `.net`, `c#`, `c++` work as written; `exceptions` lift an excluded word inside a
  phrase ("technical staff", "embedded finance"). Without a `titles` block the defaults apply: Manish's, written as lists that make
  **the same decision as the old regexes on all 34,624 distinct titles** of the 2026-10-13 fetch and the production database and on all
  39,985 jobs of the fetch (2,193 kept before and after; one reason text differs: "Oracle-ERP Tester" is now rejected for `Oracle-ERP`,
  before for `Tester`). A frozen copy of the old regexes is the reference in `tests/test_title_rules.py`. A broken block (unknown key,
  empty include, odd characters) stops the scan before the fetch with a message; an include entry an exclude word always blocks is
  logged. `discover` and `check-filter` use the same filter.
- **The scoring rubric can be a file** (`candidate.rubric_file`, e.g. `rubric.md`). Without it the built-in rubric is used, so Manish's
  rubric id is unchanged (`82e017b4`). `rolesight init` writes the built-in text to `rubric.md` (same id) and the example config names it.
  The scan logs `Rubric text: rubric.md | built-in` next to `Scoring rubric: <id>`; `export` compares with the configured rubric.
- **`rolesight init --resume FILE` (.pdf, .md, .txt) drafts a person's settings**: for a PDF, Gemini first turns it into
  `resume/<name>.md`; one call drafts name, profile, seeking, not_suitable, the title lists (starting from the defaults) and the jobs with
  their dates; the **years of experience are counted in code** from those dates (overlaps once, internships at their length,
  "present" = this month); a second call rewrites the rubric's facts for those years and that stack, and the eight rule headings and
  caps must come back word for word, else the built-in rubric is kept with a note. It asks for the Gemini key on a terminal (saved to
  `.env`), never prints it, asks before replacing personal settings (`--yes`; `.bak` copies), and prints what it wrote, the years and the
  jobs they came from. `rolesight check-filter TITLE [LOCATION]` replaces `python scripts/check_filter.py` (which still works).
- **Measured with real Gemini on Manish's resumes (2026-10-14):** found by those runs and fixed before the commit: the model guessed the
  experience wrong without today's date (1.5 and 5 years for a 3.3-year resume), so the date is in the prompt and the years are now
  counted in code (3.3 from his resume's dates); a rubric returned inside JSON lost its line breaks, so it is a separate plain-text call;
  a bare `engineer` include word is dropped (it would pass nearly every title). Drafted from his current resume, the title lists keep all
  2,193 jobs his keep plus 199 (roles in languages his resume lists but his own lists exclude); on his 82 labelled jobs the drafted settings rank a
  little below his hand-tuned ones (AUC 0.931 vs 0.955 / 0.953 the same day, `apply` at 70 12/14 both, one more false positive). A real
  `rolesight scan --limit 3` in a fresh directory with those settings: 2,384 fetched, 48 scored, `Title filter: config.json` and
  `Rubric text: rubric.md` in the log.

### Fixed (2026-10-14, found by T103's real run: a key exported in the shell)
- `.env` was loaded with `load_dotenv(override=True)`, so the template's `GEMINI_API_KEY="your_gemini_api_key_here"` replaced a real key
  exported in the shell: `init --resume` said "No Gemini API key" and a scan would have sent the placeholder. `settings.load_env_file` now
  puts the `.env` values into the environment over the shell's, except a placeholder or an empty value (`main.load_config`, `doctor`,
  `init`). Tests: the shell key reaches `load_config` and `init` next to a template `.env`; a real `.env` value still wins.

### Fixed (2026-10-14, T102: the last TinyFish and OpenRouter traces in the templates)
- Manish: "if TinyFish is not used in our project and not important, you can remove it." Nothing in `job_hunt/`, the packaging files, the scripts or the CI uses it (`grep -ri tinyfish` finds one comment in `main.py` saying it
  was removed in T42). What was left: the **root `.env.example`** (the file a visitor to the repository copies) still offered a `TINYFISH_API_KEY` and `OPENROUTER_*` block that nothing reads, and had drifted from the template
  `autopilot init` writes: it also carried live `CANDIDATE_NAME`, `RESUME_PATH`, `MIN_SCORE=60` and `TOP_N` lines, the trap T81 had removed from the packaged copy (an active line there silently beats `config.json`). It is now
  byte-identical to `job_hunt/data/env_example`, and a test keeps it so.
- Kept on purpose: the migration notes in the README, SETUP, `docs/01-install.md`, ARCHITECTURE and CLAUDE.md ("TinyFish and OpenRouter were removed"), the tests that prove their variables no longer reach the config, and the test
  fixtures that load an old `config.json` with a `tinyfish_api_key` (an upgrader's file must still load).
- His local, git-ignored `config.json` lost its dead `tinyfish_api_key` entry (parsed before and after: every other key identical; `load_config()` still works); his `.env` has had no TinyFish line since 2026-10-13. The key itself can
  only be revoked in his TinyFish account, which this project cannot reach; it was never in git (history holds only upstream's `sk-tinyfish-your-…` placeholders).

### Changed (2026-10-14, T86 follow-up: the last old-prompt rows of `open_matches.csv`; data only, no code)
- After T86's scan, 18 rows of `open_matches.csv` still carried 2026-10-04 scores. None had a stored description, so they could not be re-scored from the
  database, and no scan had seen them since. Each was checked at its own ATS endpoint (read-only GETs): 17 are gone (Greenhouse and Workday 404, SmartRecruiters
  `active: false`, Oracle no requisition, and Workday 403 on 10 jobs while a live job of the same tenant answered 200 to the same request) and now have
  `closed_at` (a job that is seen again reopens, T33); 1 is live (Kotak, posted 2026-09-28), but its Oracle requisition has no description text in any field, so
  it was not scored blind: its posted date is stored, and at 16 days it is outside the 7-day window. `open_matches.csv`: 87 → 69 rows, none from 2026-10-04.
  Checked against the backup `data/jobs.db.bak-2026-10-14-before-T86b`: 18 rows changed (17 `closed_at`, 1 `posted_at`), no score. 0 Gemini calls.

### Added (2026-10-14, T101: a test for the commit headers; T01 closed)
- `tests/test_public_release.py` already refused any e-mail address in a published file; it now also refuses a commit whose author or committer address is outside a short list (the
  owner's personal mail, the original author's university, GitHub's web-UI and noreply addresses, the assistant's trailer). Reason: git takes `user.email` from the global config when a clone,
  a CI runner or a new tool has no local one, and this machine's global identity is a work address; the repository's own config overrides it, so today every commit is clean (measured on `main`:
  616 commits under the personal address, 118 by the original author, 18 by GitHub; the work domain 0 times in author, committer or message). The global config is left alone on purpose: changing
  it would put the personal address on commits in other repositories. The work address is not written in the test (the file is public): anything outside the list fails.
- T01 (private backup) is closed: the code is on GitHub (`origin/main` = `main` = `42fa036`, measured with `git ls-remote`). Not in any git remote, by design: `.env`, `config.json`, the resume and
  `data/jobs.db` (git-ignored; copies only in `data/*.bak-*` on the same disk).

### Changed (2026-10-14, T100: Developer Advocate roles are rejected by title)
- Manish's rule, as for "AI / ML Engineer": keep a role only if his skills match it, and he left the reading of his resume to Claude. Developer advocacy / developer relations is a different job
  (talks, articles, community, demos); his resume shows backend engineering and none of that. `advocate`, `advocacy`, `evangelist`, `devrel` and `developer relations` join the title exclude
  list (`prefilter.TITLE_EXCLUDE_PATTERN`). Autodesk's "Senior Developer Advocate (APIs)" had scored 82 on the first scan with the T79 rubric (its own reason: "rather than pure backend engineering");
  Gemini had scored the same kind of role 10, 25 and 35 elsewhere, and the labelled set calls it `no`. Rather than rely on a score that swings, the title is decided before Gemini.
- Measured on the saved fetch of 2026-10-13 (39,985 jobs): survivors 2,196 → 2,193, exactly the three Developer Advocate titles (Amazon, Autodesk, Salesforce) removed, none added.
  "Developer Experience Engineer", "Software Engineer, Developer Tools" and "Backend Engineer, Developer Platform" still pass. Rows already scored stay as they are: Autodesk's 82 stays in
  the database and in `open_matches.csv` until the posting leaves the 7-day window or the job closes.

### Fixed (2026-10-14, review of T96, T97 and T86)
- **`quality` joins `qa` and `test…` in the title exclude list.** T96's "software … engineer" rule let quality-engineering titles through, and the first scan
  scored KLA's "Software Quality Engineer" 75 (its own reason: "quality engineering and test automation"). On the fetch of 2026-10-13 the word removes 13
  passing titles (4 in the 7-day window), all QA, test automation or construction quality ("Software Quality Automation Engineer – Python & Playwright",
  "Sr. Engineer, Construction Quality- CSA"), and adds none; "Senior Software Engineer" still passes. The KLA row already scored stays in the database.
- **`docs/07` no longer tells you to reset every row with an older rubric id.** A scan re-scores only a job it fetches again, that passes today's pre-filter
  and is inside the posted window; any other row set back to `discovered` is never scored again and drops out of `open_matches.csv` and `export` (T86: 3 of
  145 qualified). The bulk `UPDATE` it printed would have reset 459 rows of today's database.

### Fixed (2026-10-14, T98: the MCP server runs on `mcp` 1.x and 2.x, and a tool that cannot run now answers)
- `mcp` 2.x renamed `FastMCP` to `MCPServer` (`mcp.server.mcpserver`) and made `ToolAnnotations` snake_case; Dependabot's PR #1 (closed) failed mypy on it. `job_hunt/mcp_server.py`
  now loads whichever class the installed SDK has and builds the hints from the camelCase names, which both generations accept. `pyproject.toml` allows `mcp>=1.9,<3`
  (the extra and `dev`). The existing test only called the tool functions; the new `tests/test_mcp_real_client.py` starts `python -m job_hunt.mcp_server` and talks to it with the
  SDK's own stdio client: the server's name, the three tools and their hints, a successful `export_jobs` against a database, and the three tools failing.
- That test found a bug that predates the port: a tool that ended in `sys.exit("reason")` (no `config.json`, no `companies.json`, no scan history: the CLI helpers all do) made the server
  neither answer nor fail, so the client waited for ever (reproduced on `mcp` 1.30: the call hit the test's 60 s timeout). `tools.py` now turns the exit into a `ToolError` carrying the
  reason, and the MCP layer re-raises it as the SDK's own `ToolError`, the only exception whose message 2.x shows a client; the call returns `isError` with "config.json not found." etc.
- Measured: the same new and existing tests pass under `mcp` 1.30.0 (the project's venv; 1157 tests, ruff, mypy clean) and under `mcp` 2.3.0 in a scratch venv (1156 passed, 1 skipped: `anthropic`
  not installed there; ruff and mypy clean). Four deliberate breakages were each caught under 2.3.0 (a fifth, snake_case hint keys, is equivalent there and caught under 1.30).
  Not run: a real MCP host such as Claude Code connecting to it. After this is on GitHub, `@dependabot unignore mcp` would let the `<3` bound be proposed again.

### Changed (2026-10-14, T69: the low-priority review notes, a, b, c and f; d and e left, see the board)
- (a) Structured and batch scoring read `gemini_temperature` like the single-job path (they hard-coded 0.1; the default is unchanged).
- (b) The deprecated non-Gemini scorer (`scanner.score_batch`) sends the whole resume and each description up to `MAX_DESCRIPTION_CHARS` (20,000), as the Gemini path has since
  T13; it cut them at 2,500 and 1,500 characters. No real call has been made with these providers (T63): the test checks the prompt that reaches the (stubbed) model.
- (c) The title word `embedded` no longer rejects "Embedded Finance / Payments / Banking / Insurance / Lending" (fintech products, not firmware). Measured on the saved
  fetch of 2026-10-13 (39,985 jobs): 151 titles contain the word, none of this kind for an engineer, and the survivors are the same 2,209 before and after.
- (f) Structured scoring caps a stack mismatch at 50 in code, as rubric rule 4 does since T73 (the code said 60). Opt-in mode only.
- Decided, no code: "AI / ML Engineer" (with a slash), "ML Engineer" and the like stay rejected (Manish, 2026-10-14: ML engineering is not his area; his resume shows GenAI used through APIs inside
  Node.js services and no model-building work). The tests that pin the rejection now list the slash form too.

### Fixed (2026-10-14, T82: the unexplained test failure explained)
- `tests/test_export_from_db.py::test_worth_applying_uses_the_scans_min_score_when_there_is_a_config` failed once in six full runs (2026-10-11). Cause, now shown:
  the test helper `_export` read "the newest CSV" by `st_mtime_ns`, the test runs two exports into one directory a few milliseconds apart, and file
  timestamps here have 1 ms resolution (measured: 4,764 of 4,999 back-to-back writes tie). On a tie `max()` returns the first file the directory lists, which
  can be the first export's (every Worth Applying blank), so the second assertion failed. Measured: the two CSVs are 1 to 3 ms apart (150 runs, 0 ties
  observed, so the real rate is low); forcing a tie with `os.utime` reproduces the failure on demand. The helper now reads the file the call itself wrote
  (set difference), and `tests/test_direct_scanner.py::_scan_csv` (same pattern) picks the highest-numbered `jobs_DATE[_N].csv` by name. Two regression tests force a tie.
  Product code is unchanged.

### Done (2026-10-14, T86: the old-prompt scores)
- Manish said "yes you can re-score" for the 145 rows scored on 2026-10-04 (older prompt). A scan can re-score only a job it fetches, that passes today's pre-filter and
  is inside the 7-day window, so resetting all 145 would have re-scored 3 and left 142 as `discovered` for good; only those 3 were reset (Autodesk, State Street,
  Wolters Kluwer), after a backup (`data/jobs.db.bak-2026-10-14-before-T86`) and a copy of the 145 old scores (`data/old_prompt_scores_2026-10-04.json`).
- Real `./run_daily.sh`, 12:31 to 12:53 IST (22.5 min): `Funnel: fetched 34268 | India 18070 | already scored 369 | pre-filter rejected 32210 | too old 1533 | queued 156 |
  scored 156 (gemini-3.5-flash-lite 156) | failed 0 | left for next scan 0`. Every new row carries rubric `82e017b4` (T97) and model `gemini-3.5-flash-lite`.
- The 3 rows: Autodesk "Senior Developer Advocate" 50 → 82, State Street "Emerging Technology and Transformation Developer - AVP" 75 → 45 (LLM and agent workflows as the
  main duty: rule 8), Wolters Kluwer "Associate Enterprise Software Engineer - DevSecOps" 45 → 75. Three rows say nothing about the rubric on average; T60 measured swings
  of this size between runs of the same prompt on ambiguous postings.
- Of the new scores 29 of 156 are 70 or more; of the 51 generic-engineer titles T96 lets through 1 reached 70 (KLA "Software Quality Engineer", 75), of the 3 places T84 adds
  none did. `open_matches.csv`: 87 rows (18 of 2026-10-04, 40 of 2026-10-12, 29 of 2026-10-14); its `Rubric` column is blank for the 58 rows scored before T97.

### Fixed (2026-10-14, T99: scored rows with no posted date no longer sit in `open_matches.csv` at any age)
- Rows scored before T29 (all 145 of 2026-10-04) have no `posted_at`, and a scan skipped them at "Skipping previously scored job", so they never got one;
  `open_matches.csv` keeps undated jobs, so it listed them whatever the posting's real age. When a scan fetches a job whose stored row is `scored`/`notified`
  and lacks them, it now stores `location` and `posted_at` (`db.fill_missing_details`: only where empty; never the description, the score, status, reason,
  model or rubric; no Gemini call). `posted_at` is stored as an ISO date (`prefilter.posted_date_iso`): Workday's "Posted 3 Days Ago" is relative to the day it is read.
- `current_age_days` now ages a real date from itself (today minus the date). It used to clamp to the day the row was scored and add the days since, which
  would have aged a date later than the scored date (an ATS that bumps `updated_at`) by too much; relative Workday text is unchanged.
- Measured on a copy of the production database, the real `run_scan` over the saved fetch of 2026-10-13: 101 of the 145 old-prompt rows (those still on their
  boards) get a date and location, every scored row is otherwise byte-identical, 0 Gemini calls; the scan's own `open_matches` writer goes 73 → 59 rows (14
  rows posted more than 7 days ago leave; 19 old-prompt rows stay: 18 are off their boards and undated until T33 closes them, 1 is in the window).

### Added (2026-10-14, T97: every stored score records which rubric produced it)
- `jobs.score_rubric` holds `llm_utils.rubric_id()`, 8 hex digits of the SHA-256 of the scoring prompt text (`SCORING_RUBRIC` for single and batch scoring;
  the opt-in structured mode has its own instructions and its own id). Each of the three scoring functions returns the id of the text it sent, the scorer
  stores it with the score and `init_db` adds the column to an existing database (a copy of the production file: 43,466 rows and the 462 scored ones kept, 0.02 s). Rows
  scored before this change, and by the deprecated providers, stay empty ("unknown"); nothing is guessed for them.
- The scan logs `Scoring rubric: <id>` after its provider line (Gemini only). `export` and `open_matches.csv` get a `Rubric` column when some score is not from the
  current rubric and at least one carries an id (so an all-unknown file is unchanged, as before). It exists because the rubric changed in T58, T73, T74 and T79
  while a scored row is final: T86 found 33 old-prompt rows in `open_matches.csv` only from commit dates.
- `python scripts/rubric_ids.py [--db data/jobs.db]` prints every distinct rubric in the git history with the commit that first had it, and the database's scored rows
  by id (read-only). Measured on 2026-10-14: `82e017b4` (current) is `f5daced`'s rule 1; `12a5ae0c` (5,563 characters, `7bc5b61`) is the one that scored the 317 rows of
  2026-10-12.
- The id covers the rubric text only, not the code around the prompt, the candidate profile or the resume. Four older tests that compared a whole scoring result now
  expect the extra `rubric` key.

### Changed (2026-10-14, CI: Dependabot's two pull requests)
- CI uses `actions/checkout@v7`, `actions/setup-python@v7` and `gitleaks/gitleaks-action@v3` (Dependabot #2; its CI run passed on all three Pythons and
  gitleaks v3 scanned: "1 commits scanned … no leaks found").
- The Codecov upload step is removed: it never uploaded. On every run, v5 and v7 alike, the Codecov CLI logged `Upload queued for processing failed: {"message":"Token
  required - not valid tokenless upload"}` (the repository has no `CODECOV_TOKEN`), and `fail_ci_if_error: false` kept the step green. The 85% coverage gate
  is pytest's own (`fail_under` in `pyproject.toml`) and still runs on every Python. Adding it back needs a Codecov account and the token as a repository secret.
- Not taken: `mcp` 2.x (Dependabot #1, closed). With `mcp` 2.3.0 mypy fails on all three Pythons: `mcp.server.fastmcp` no longer exports `FastMCP`, and
  `ToolAnnotations` takes `read_only_hint` instead of `readOnlyHint`. `mcp>=1.9,<2` stays; porting the MCP server is T98.

### Changed (2026-10-14, T79: rule 1 never caps a role in an Indian city)
- Rule 1 of the scoring rubric (the ≤ 30 cap for on-site work outside India) sometimes capped an on-site role in an Indian city other than Bengaluru:
  Notion's Forward Deployed Engineer in Hyderabad (`ai65`, labelled `apply`) scored ≤ 30 in 5 of 20 runs, the reasons citing the candidate's Bengaluru
  preference. The rule's bracket now reads "(Roles in any Indian city, whether on-site, hybrid or remote, and remote roles open to India are eligible for higher
  scores)" instead of "(India-based roles, India hybrid, or remote roles …)"; the cap itself is unchanged. Measured on `gemini-3.5-flash-lite` (pinned), all
  runs on 2026-10-14 against a same-day control, criteria fixed beforehand: ai65 capped **0 of 20** (control 5 of 20); the 82 labelled jobs, two runs: AUC
  **0.955 / 0.953** vs 0.921, `apply` +1.5 points on average, 0 false positives at 70 in every run, highest `no` 50; `apply` at 70 is 12 of 14 in every run,
  control included (the same two jobs, g8 and j7, whose labels are open questions in T59). The first attempt (an added sentence, 2026-10-11) was reverted for
  lowering the ranking; this one changes only the existing bracket. **Noise worth knowing:** the unchanged rubric's AUC on the 82 was 0.976 on 2026-10-11,
  0.949 on 2026-10-13 (66 answered) and 0.921 today, so a rubric change is only comparable to a control scored the same day. Score files in
  `data/golden_runs/t79c_*` (git-ignored).

### Changed (2026-10-14, T84 and T96: more of what reaches Gemini, on Manish's answers)
- **T84, the location check is on the country.** Manish applies to all of India, so `location_is_india` now also accepts any Indian state or union territory and some 150
  more cities (Coimbatore, Indore, Nagpur, Bhubaneswar, Lucknow, Kochi, ... `LOCATION_INDIA_MORE_PATTERN`), not only 11 cities and the word "india"; upper-case `IND`
  counts too. Left out on purpose: names that are also places elsewhere (Salem, Bilaspur, Punjab). **New, optional: `candidate.cities`** (a list such as `["Pune", "Hyderabad"]`, or
  `"Delhi NCR"` for Delhi, Noida, Gurugram, Ghaziabad, Faridabad): with it, a job in an Indian city or state that is not one of them is rejected, unless it is remote or
  names no city; Bangalore = Bengaluru and the like match. Empty or absent = all of India (the default, and Manish's). The scan logs which it uses; `check_filter.py --cities`
  shows it for one job.
- **T96 (T69 g), generic engineer titles reach Gemini.** A title that is only "Engineer" with a seniority or level ("Senior Engineer", "Engineer II", "Associate Engineer") or has
  "software" and "engineer" in any order ("Engineer III, Software", "Sr Software Application Engineer") continues to Gemini, which judges the description; companies name roles
  differently. Exclude words still win ("Lead Engineer"); "Data Engineer", "Mechanical Engineer" and the like still need an include word.
- **Measured** with the old filter (from git) and the new one on the fetch of 2026-10-13 (39,985 jobs): jobs passing 1,847 → 2,209 (+362: 335 from titles, 27 from places, 1 from both); none stopped
  passing; **52 of the 362 are posted within 7 days or undated**, i.e. about 52 more scoring calls a week. `scripts/measure_generic_titles.py` now reports what the title rule still drops.

### Fixed (2026-10-14, review of T92 and T95: a secret cut in half)
- `doctor`'s Telegram check and `send_telegram` cut a failed response's text to 100 / 200 characters and then masked the token; the REST fallback of `doctor`'s
  Gemini check did the same with the key (120 characters). A secret that straddled the cut no longer matched, so its first part was printed. Each now masks the
  whole text, then cuts it (`tests/test_redact.py`: three tests, red before the fix). Neither Telegram nor Google is known to echo the secret in a response body;
  this closes the case where one does.

### Added (2026-10-13, T69 g: how many generic engineer titles does the filter drop?)
- `scripts/measure_generic_titles.py` (with `tests/test_measure_generic_titles.py`) counts, from a saved `measure_prefilter.py --save` fetch, the India jobs the title rule drops
  only for lacking an include word, by kind (bare "Senior Engineer" / "Engineer II", qualified, other), with the 7-day window and the companies. Measured on 2026-10-13: 26 bare-title jobs
  (3 in the window) and 25 "Engineer II, Software"-style (1 in the window), about 4 a week; no filter change (details in the board's T69 row). The classifier test was checked by three
  deliberate breakages, each of which failed it.

### Fixed (2026-10-13, T90: SQLite connections are closed)
- `with sqlite3.connect(path) as conn:` commits or rolls back but does not close, so every database call left a connection to be garbage-collected (and each public
  `db` function opened two, because it first called `init_db`, which returned an open connection nobody used). Python 3.13 reports each one: on 3.13.16, `pytest --cov=job_hunt`
  gave 13,859 `ResourceWarning: unclosed database` (0 on 3.11 and 3.12). `db.connect` is now a context manager that commits, rolls back on error and closes, used at all 16
  sites (`db.py`, `doctor.py`); `init_db` closes its connection and returns nothing (no caller used the value). Behaviour is otherwise unchanged.
  The tests that opened their own connections (14 places) and `scripts/import_json_history.py` close theirs too. Result on 3.13.16: `pytest --cov=job_hunt` 967 passed, **0 warnings** (was 13,859);
  none of the remaining `-W error::ResourceWarning` findings is SQLite (29 are `unclosed file` in tests that read CSVs: not touched).

### Fixed (2026-10-13, T95: the Telegram bot token in error messages)
- Telegram's API puts the bot token in the URL path (`/bot<token>/sendMessage`), and `requests` names the URL in its connection errors. Measured with the real library and
  no network: `str(e)` contains the token. `notifier.send_telegram` printed that text (into `data/scan.log` through `run_daily.sh`), and `doctor`'s Telegram check
  returned it (printed, and logged with `RUN_PREFLIGHT_DOCTOR=1`). Both now replace the token with `***` (`/bot***/sendMessage`), also in the text of a failed response.
  The helper is `job_hunt.log.redact`, which T92's Gemini fix now shares. Telegram is off today, so no token was printed.

### Changed (2026-10-13, T94: no personal default paths)
- `harvest` and `discover` no longer default to files in one person's Downloads folder. `harvest` without `--yaml` (or `ROLESIGHT_HARVEST_YAML`) now stops with
  exit 1 and says so, before any request (before, on another machine it died with `FileNotFoundError: YAML not found: /home/user/Downloads/india.yml`). The LinkedIn
  headcount cache is read only when given (`--linkedin`, or `ROLESIGHT_LINKEDIN_CACHE`), and `discover` without it no longer logs a warning naming that path;
  headcount shows "Unknown", as it did when the file was missing. Manish's old behaviour is one variable each. `grep -rn '/home/user' job_hunt` is empty.
  Three existing CLI tests now pass `--yaml`, because the command requires it.

### Fixed (2026-10-13, T93: old product names a user could trip over)
- The two "install this" hints named a package that does not exist (`autopilot-jobs[mcp]`, `autopilot-jobs[claude]`; the distribution is `rolesight`
  and is not on PyPI). They now give the command that works in a clone: `pip install -e '.[mcp]'` and `pip install -e '.[claude]'`.
- The MCP server reports itself as `rolesight` (it was `autopilot-jobs`, the name a client shows); its docstring, `job_hunt/__init__.py`, `conftest.py` and
  `doctor`'s banner (`ROLESIGHT DOCTOR DIAGNOSTICS`) follow. The `autopilot` command and the `job_hunt` package keep their names.
- Checked in a clean virtual environment with no extras: both messages print as written, and `pip install -e '.[mcp]'` makes `job_hunt.mcp_server` import.
  (The `[claude]` command was not run; the extra exists in `pyproject.toml`.)

### Fixed (2026-10-13, T92: `doctor`'s Gemini check)
- `doctor` pinged `gemini-3.5-flash-lite` whatever `gemini_model` / `GEMINI_MODEL` said, so a user on another model had the wrong one checked. It now
  pings the model a scan would try first (`GEMINI_MODEL` from `.env`, else `config.json`'s `gemini_model`, else the default) and every message names it, failures
  included (a 503 or 429 says which model). It still runs without a `config.json`.
- The REST fallback (reached only without `google-genai`) put the API key in the URL (`…:generateContent?key=…`), so an error that names the URL would print
  the key, and `RUN_PREFLIGHT_DOCTOR=1` writes doctor's output to `data/scan.log`. The key now goes in the `x-goog-api-key` header, and any error text has the key
  replaced by `***` on both paths. `grep -rn '?key=' job_hunt` is empty and a test keeps it so.

### Changed (2026-10-13, T91 — one recruiter's personal address removed from the golden sets)
- The labelled job postings in `scripts/golden_set.csv` and `scripts/golden_set_ai.csv` are copied verbatim from public boards. Of the 15 distinct e-mail addresses in them, one is an individual recruiter's (LogicMonitor, once in each file); it is now `[address removed]`. The others are role mailboxes (careers, accommodations, a diversity-and-inclusion team) and stay. Scoring is unaffected: the address carries no requirement. The published history still holds the old text.

### Fixed (2026-10-13, found while measuring T79)
- `scripts/measure_score_variance.py`: one failed Gemini call (a 503 "model is currently experiencing high demand") raised out of the loop, ended the whole measurement and saved nothing (it happened on a 20-run ai65 measurement). A failed call is now printed and skipped, never stored as a score; the other runs are kept and saved. Test red first.

### Changed (2026-10-13, T88: renamed JobNotify → RoleSight, prepared for a public MIT release)
- **Name.** The project, the distribution (`pyproject.toml` `name = "rolesight"`), the Claude skill (`skills/rolesight`) and every
  doc now say RoleSight. A `rolesight` command is added next to `autopilot` (in an existing checkout run `pip uninstall -y autopilot-jobhunt && pip install -e .`: a plain re-install leaves the old distribution installed next to the new one, measured in a scratch venv); the
  `autopilot-jobhunt` command alias, which existed for the upstream package's registry listing, is gone. The log override
  variable `JOBNOTIFY_LOG` is now `ROLESIGHT_LOG`. Older entries below keep the name they were written under.
- **CI would have been red on the first push.** It lints `job_hunt/ tests/ conftest.py`; the local gate only linted `job_hunt/`.
  Measured on a fresh clone: 8 ruff errors in 5 test files (2 unused imports, 3 import orders, 3 chained statements); fixed, and
  every gate listing now names the CI paths.
- **Secret scan.** CI's gitleaks job scans the whole history. Run locally (gitleaks 8.30.1, 303 commits): 1 finding, a false
  positive in `scripts/golden_set.csv` (the posting phrase "APIs, middleware/integration"); `.gitleaks.toml` allowlists the two
  golden-set CSVs by path, and the rerun reports no leaks. After the rewrite, six more findings were the same phrase quoted in our own
  notes (CHANGELOG, the board, a test docstring); `.gitleaks.toml` now also allowlists that one string, and the whole history is clean.
- **Licence and credit.** `LICENSE` keeps Tarun Gupta's 2025 notice and adds Manish Singh's 2026 line; the README credits
  autopilot-jobhunt and says what was added since. `tests/test_public_release.py` guards the name, the notice, the credit,
  and that no e-mail address sits in a published file.
- **Removed** what belonged to the upstream listing, not to this project: `server.json`, `glama.json`, `demo/` (the upstream
  demo GIF and fixtures, referenced by nothing) and `assets/`. The code of conduct no longer sends reports to the
  upstream author's address; `SECURITY.md` points at GitHub's private reporting.
- README status refreshed from the stale 2026-10-04 figures (the Amazon description stub it listed was fixed in T57).
- **No PyPI.** The upstream `publish` job (PyPI upload on a `v*` tag) and the tag trigger are removed from `ci.yml`: Manish has no PyPI
  account and does not want one, and the job would have failed on every tag. Install is from a clone.
- **Golden sets stay** (`scripts/golden_set.csv`, `golden_set_ai.csv`: verbatim public postings with Claude's labels), with a notice in the
  README saying whose text it is and that it is removed on request.
- **Links.** `[project.urls]` and the README badges point at `github.com/Manish814142/rolesight`; `.gitignore` covers office lock files.
- **History (T89).** The 251 commits after the fork point were rewritten so that none carries Manish's work address (author and committer are his personal address);
  the original author's 68 commits, tags and refs keep their exact ids, and the old objects are pruned. All commit ids written in the board and this file were remapped.

### Fixed (2026-10-13, review of T76 and T87)
- **T76:** a redirect to another host is a dead end only when its answer is not JSON. Before T76 a cross-host redirect that ended in JSON (a tenant moved to another Workday data centre) was followed and its jobs read; T76 had turned every such redirect into an empty board. And the "maintenance" warning is once per scan, not once per process (`workday.reset_redirect_report()` at the start of each scan's fetch), so the long-running MCP server warns on every scan. Checked through the real `requests` with two local servers: 303 to an HTML maintenance page → one warning, empty incomplete board; 308 to another host answering JSON → its job, not incomplete. 2 tests, red first.
- **T87:** three `tests/test_discovery.py` tests posted on a literal `2026-09-30` / `2026-10-01` and would have failed from about April 2027 against discover's 180-day rule; they now post ten days before today. Found by running the whole suite with the clock moved +30 / +200 / +400 days (`time-machine` in a throw-away venv, started before any test module is imported); the only other failures at those dates come from SQLite's own `date('now')`, which the tool does not move (not a real failure: the product code never reads SQLite's clock).

### Changed (2026-10-13, T85 — the example config describes the person this fork is built for)
- `config.example.json` and `job_hunt/data/config.example.json` (what `autopilot init` writes) carried upstream's persona ("10+ YOE, Senior/Staff ML/AI Engineer … MLOps", "relocation to EU / NA / APAC", "pure SWE with no ML"). A user who forgot to edit the three sentences got scores that contradicted this fork's filter (it rejects Staff titles and non-India places) and rubric (written for a 3-year backend engineer). They now hold the user guide's own examples: `3 YOE backend engineer. Stack: Node.js, TypeScript, MongoDB, AWS` / `Remote, or hybrid in Bengaluru. Backend or platform roles` / `Pure frontend, QA, support, management, internships`. `tests/test_example_config_persona.py` (8 cases, 4 red first) ties both files to the guide's lines and bans the old phrases. Measured with the real command: `autopilot init` in an empty directory writes those sentences and `load_config` accepts the file. Not changed: an existing `config.json`.

### Removed (2026-10-13, T83 — no empty `state/` folder any more)
- `autopilot init` and `run_daily.sh` created a `state/` directory although nothing has read or written it since T34. Both stopped (`main.init_project`, the `mkdir -p` line of `run_daily.sh`). Measured with the real command in an empty directory: `autopilot init` now leaves `.env companies.json config.json data output resume` (`data` is made by the logger, as before). `tests/test_init_dirs.py` (2 tests, red first) and the updated `test_init_project_scaffolds` pin it; `bash -n run_daily.sh` parses (the script itself was not run: it starts a real scan). An existing `state/` folder is left alone.

### Fixed (2026-10-13, T76 — Workday's maintenance page is reported once, clearly)
- On 2026-10-10 77 of 79 Workday tenants answered the jobs POST with a 303 to `community.workday.com/maintenance-page`; `requests` followed it, the HTML was not JSON, and each tenant logged "Expecting value: line 1 column 1". The adapter now checks whether the answer ended on another host than the tenant's (`workday._redirected_away`): if so it stops that board, marks it incomplete with the reason `Workday maintenance: redirected to <url>` (T33 counts no miss, as before), and logs **one** warning per scan that says what happened and that the boards are fetched next time; later tenants log the same at debug. A normal answer, and a redirect that stays on the tenant's own host, are unchanged. Not done: a retry later in the run (the board's jobs come back on the next scan; nothing is closed in between).
- **Verified against the real library, not only a fake:** two local servers (a "tenant" answering `POST` with 303 to a "maintenance" server on another host) and `http_post`: the real `requests` response has `history [303]` and `url http://localhost:<port>/maintenance-page`, and `_redirected_away` returns that URL (and `""` when the final host is the tenant's). `tests/test_workday_maintenance.py` (4 tests; the 2 that exercise the new behaviour were red first, showing the three cryptic per-tenant warnings). **Not tested against Workday itself:** the maintenance window of 2026-10-10 is over, so the real redirect target is known only from the earlier measurement.

### Fixed (2026-10-13, T87 — two scan tests had a literal posted date that aged out of the 7-day window)
- `tests/test_db_details.py` posted its job on `2026-10-05` and `tests/test_score_model.py` on `2026-10-08`; both run a real `run_scan`, whose window (T02) drops a job older than 7 days. The first started failing on 2026-10-13 (`Funnel: … too old 1 | queued 0`, measured: it failed with and without the T75 change), the second would have failed from 2026-10-16. Both now post "yesterday". **Found by running the suite with the code's clock moved 20 days ahead (a throw-away pytest plugin, not committed):** the failures that remained were tests that compute their dates from the real clock (they only fail because the simulation moves one side), so no other literal-date test goes through a scan. `test_discovery.py`'s `2026-10-01` is checked against a 180-day rule (good until April 2027).

### Fixed (2026-10-13, T75 — a lookup by job id no longer scans the whole `jobs` table)
- `get_job`, `has_job`, `update_job_status` and `update_job_details` filter on the bare `global_id`, which the partial unique index on `(ats, global_id)` cannot serve (its `WHERE` clause is not implied), so each lookup was `SCAN jobs`. `init_db` now also creates `idx_jobs_global_id ON jobs(global_id)`. **Measured on a copy of the production database (43,466 rows):** plan `SCAN jobs` → `SEARCH jobs USING INDEX idx_jobs_global_id (global_id=?)`; a bare `SELECT … WHERE global_id = ?` **2.18 ms → 0.024 ms**, `get_job` (which still runs `init_db` on every call) 2.84 → 0.45 ms; creating the index on that copy took 0.04 s; the same 300 random ids return the same rows and `PRAGMA integrity_check` is `ok`. A full scan makes about 35,000 such lookups (33,652 jobs were fetched in the T09 run), so about 80 s of the 48.5 minutes (inferred, not timed in a scan).
- `tests/test_db_lookup_index.py` (5 tests): the SQL each of the four functions really sends is captured through `sqlite3`'s trace hook and run through `EXPLAIN QUERY PLAN`; no plan may say `SCAN`. The 4 plan tests were red before the index; the fifth pins that the lookups return the same rows.

### Run (2026-10-12, T09 — first full production run)
- `./run_daily.sh` on the real `data/jobs.db` and `config.json` (224 boards, `min_score` 70, 7-day window, `gemini-3.5-flash-lite` primary), started 19:20 IST, ended 20:08 IST: **48.5 minutes**. Funnel (the scan's own line): **fetched 33,652 | India 17,104 | already scored 105 | pre-filter rejected 31,920 | too old 1,310 | queued 317 | scored 317 (gemini-3.5-flash-lite 316, gemini-3.1-flash-lite 1) | failed 0 | left for next scan 0**. Fetch 5.0 min (fewer jobs than the 39,713 of the unwindowed fetch of 2026-10-11 because 14 newest-first boards stopped at the window), descriptions of 237 of the 317 survivors 70 s, scoring 39.3 min (7.4 s per job, 4.2 s of it pacing). **60 of the 317 scored ≥ 70 (`min_score`), 29 ≥ 85**; `open_matches.csv` lists 93 (≥ 70, not applied, inside the window).
- Done-when, read from the artifacts: `data/jobs.db` has 317 rows with `scored_at` of 2026-10-12 (status `scored` 462 in all: 145 of 2026-10-04 + 317); `output/jobs_2026-10-12.csv` (317 rows, with the `Model` column) exists; `data/scan.log` ends `Scan finished with exit code 0`; table `scans` has the run with a finish time.
- **One job was scored by the fallback model**: Amazon "Software Dev Engineer 2, AFT Inventory", 85 on `gemini-3.1-flash-lite`, after a `Connection reset by peer` on 3.5 (a network error, not the quota); the CSV's Model column shows it, and 3.1 scores weak fits about 7 points higher (T70). The only other warning was one 503 UNAVAILABLE retry.
- **T77 and T78 on live data.** T77: 55 jobs were rejected with `is remote but names a non-India place` (debug log), reasons such as `'Boston, Massachusetts'`, `'CA Remote Ontario'`. T78: 14 boards stopped at the posted-date window and one at its cap (2000); nothing was closed, as expected on the first run with sighting memory (3 missed scans are needed), and 3,206 older rows now have `missed_scans` 1: jobs of the 2026-10-03/04 fetch that their boards no longer list.
- **The production database was migrated in place before this run, by `autopilot doctor`** (it opens `data/jobs.db`; columns `location … closed_at` added, `user_version` 1): 30,367 rows before and after (23 discovered, 145 scored, 30,199 skipped), so nothing was lost, but my backup (`data/jobs.db.bak-2026-10-12`, taken right after) is of the migrated file; the pre-migration file no longer exists.
- **Found: 33 of the 93 `open_matches.csv` rows still carry scores of 2026-10-04**, from the prompt before rubric v7/v8 (mean 79.0, six at 90; the 60 new ones average 81.1, fifteen at 90). A `scored` row is final, so the 105 old-prompt jobs still on their boards were "already scored" and not re-scored. The T34 note "any job still open is re-scored by the next scan" was wrong for rows already in the database (it holds for jobs that only the retired JSON files knew). Not changed: re-scoring them rewrites his stored scores (T86).

### Reverted (2026-10-11, review of T79 — the rule 1 sentence about Indian cities)
- The reviewer ran the two checks T79 owed, on `gemini-3.5-flash-lite` pinned, same evening. **The 63 other `no` jobs of the AI set:** 0 reach 60 or 70 under the new wording (as under T74's), mean shift +0.8. **A second full run of the 82 labelled jobs:** AUC **0.931** (first T79 run 0.944) against 0.971, 0.973 and 0.976 for the three runs without the sentence (two v7 runs of 2026-10-08 and T74's run of 2026-10-11, the latter on the same evening and model, so not a drift of the day); recall of `apply`+`maybe` at 70 74–78% against 81–85%; `apply` 13/14 and 12/14. Job by job (mean of the two T79 runs against the mean of the three): `apply` jobs **−6.0** points (Expedia g1, Sigmoid h12, Okta h2, Amazon ab2: 85 → 75), `maybe` −2.2 (Coinbase h10, Amgen j5 fell to 50 once each), `no` **+2.6** (Turvo h16 30 → 45, Elastic h13 25 → 40). False positives stayed 0. The sentence squeezed scores toward the middle on the whole set to fix one posting (ai65) that was capped in 2 of 15 runs.
- Reverted: `SCORING_RUBRIC` is again byte-identical to T74's measured rubric (7bc5b61, checked via `ast`), its wording test and the docs/07 parenthesis are removed. Kept: `scripts/measure_score_variance.py --csv` and its test. Score files: `data/golden_runs/named_t79run1.json`, `named_t79run2.json`, `ai_rest63_v9_review_2026-10-11.json`. T79 is back on the board with the options.

### Fixed (2026-10-11, review of T77 — words that are not places no longer reject a remote job)
- T77 treated every word left after its filler list as a place, so a remote-flagged job was rejected for `IND - Remote` and `IN - Remote - IND` (India's own code), `Remote (Full Time - Remote)` and `Remote or Office (Depending on Region)` (all on the 2026-10-11 fetch, with a passing title), and in probes for `Remote - IST`, `Remote, UTC+5:30`, `Remote (Contract)`, `Remote (Permanent)`, `Telecommute`, `Home Office`. Boards do put job-type, timezone and office words in the location field (1,180 jobs on that fetch). Job-type, timezone, office and short connecting words are now filler, and `IND` counts as an Indian place. A wrongly kept job costs one scoring call that rule 1 caps; a wrongly rejected one is never shown.
- Measured on the same 39,713 jobs: survivors 1,817 with T77 and with the fix (1,878 before T77), 0 real decisions changed; of 842 distinct remote locations run with a passing title, exactly those 4 flip to kept and every foreign place stays rejected. 19 new tests in `tests/test_remote_named_place.py` (14 red before the fix, 5 guards such as `Singapore (Permanent)` still rejected).

### Changed (2026-10-11, T79 — rubric rule 1 no longer lets a preferred city cap an Indian role)
- Rule 1 (the outside-India cap) gains one sentence: a role in any Indian city, on-site, hybrid or remote, meets the rule; a preference for one city in the candidate's profile (Bengaluru, in `candidate.seeking`) is not a location cap and does not lower the score; only a role outside India is capped. Why: Notion's Forward Deployed Engineer (ai65, Hyderabad hybrid, labelled `apply`) had scored 30, 75, 30; the reasons said "…conflicts with the candidate's Bengaluru preference". His rule in CLAUDE.md is "India or remote".
- **Measured, `gemini-3.5-flash-lite` pinned (no fallback), 2026-10-11, `scripts/measure_score_variance.py --csv … --ids ai65` and a scratch script that keeps the reasons.** ai65 ×15 with the old wording: **25, 30, 70 ×4, 75 ×9 (mean 67.3; 13 of 15 pass at 70; all 15 reasons mention the location)**; with the new wording: **75 ×6, 85 ×9 (mean 81.0; 15 of 15 pass; 8 of 15 reasons still mention the location)**; permutation test on the mean difference p ≈ 4e-5. The pass count alone (13/15 vs 15/15) is not significant; the shift of the whole distribution is the evidence. An earlier 5-run baseline (25, 75, 75, 70, 85) already passed 4 of 5, which is why the board's "4 of 5" done-when could not tell a fix from noise and 15 runs were used.
- **Regression checks.** The 82 labelled jobs, one run: **0 false positives at 60 and at 70, `apply` 13/14 (as in the 2026-10-11 run of the previous wording)**; AUC **0.944** against 0.976 for that run (paired bootstrap on the difference: −0.030, 95% CI [−0.070, −0.006]; against the v7 run a of 2026-10-08, CI [−0.076, +0.011] includes 0). Two `maybe` jobs fell from 75 to 50 in that run (h10 Coinbase "Remote - India", j5 Amgen Hyderabad), which lowered recall of apply+maybe from 81% to 74%. **Re-scored ×5 under the new wording they score 75, 75, 75, 82, 82 and 70, 70, 70, 72, 75**: noise on borderline-stack jobs, the same size as between two runs of one rubric (v7 run a vs run b: 3 jobs moved 15+ points and j5 crossed 70 there too), not the clause. Five `no` jobs rose 15–20 points (25 → 40 …) and all stay below 70. The AI/FDE set's decisive jobs, one run each: ai65 `apply` 75 → 85; the 8 `maybe` unchanged in pass/fail; known false positives ai33 85 → 75, ai41 70 → 75 (still pass, as before), ai44 85 → 45 (it flips between runs: 85, 85, 45).
- **Not measured, owed:** the 63 other `no` jobs of the AI set under the new wording (not re-run: the free-tier 3.5 quota for 2026-10-11 was nearly spent; 63 calls) and a second full 82-job run, which would settle the AUC difference. Labels are one rater's (Claude's) and unconfirmed by Manish (T59). If the extra Indian-city leniency lets weak jobs through, the CSV's Reason column shows it; revert = remove the sentence from `SCORING_RUBRIC` rule 1.
- `scripts/measure_score_variance.py` gains `--csv` (default `scripts/golden_set.csv`) so the AI set's jobs can be re-scored; test red first.

### Changed (2026-10-11, T77 — a "remote" flag no longer carries a job in a named non-India place)
- `prefilter.should_evaluate_job`: a job that passes the location stage only because the ATS flagged it remote (or its location says "remote") is now rejected when its location names a place: `named_place()` removes filler words (remote, hybrid, work from home, APAC, and Workday's placeholders "3 Locations" / "Location Negotiable" / "Remote Work, More…") and whatever words remain are a place; an Indian state or city the main list lacks (`LOCATION_INDIA_MORE_PATTERN`: Karnataka, Kochi, Coimbatore, …) is never one. Reason logged: `Location 'Paris' is remote but names a non-India place: 'Paris'`.
- **Measured on a fresh full fetch of all 224 boards (2026-10-11, 39,713 jobs; `scripts/measure_prefilter.py --save`, then `--jobs` with the old and the new filter):** survivors **1,878 → 1,817** (the repo's own script prints both). 63 survivors had passed on the flag alone (3.4%); 61 are now rejected, **all 61 True → False, none with an India term or a worldwide word**, 39 distinct location strings that I read one by one (US states and cities, Poland, France, Spain, Japan, Singapore, Korea, UAE, Malaysia, Italy, Australia, Switzerland, Brazil, Philippines, Ireland, Slovenia, Mexico, Vietnam, the Netherlands); 5 of the 61 were posted within 7 days. By company: OpenAI 24, Arista Networks 7, Confluent 4, Databricks 4, 16 others 1–2 each. The 2 left are plain "Remote". The saving is the scoring calls for those jobs (about 5 s each, inferred), not wrong scores: rubric rule 1 capped them.
- **Found while checking my first version (and fixed before the commit):** Workday's placeholder locations ("3 Locations", "Location Negotiable", "Remote Work, More…") are not places; the first version would have dropped a remote-flagged job carrying one, which today gets the benefit of the doubt. `tests/test_remote_named_place.py` (49 cases; the 7 placeholder cases were red against the first version) now pins them, plus Indian places missing from the main list, a place inside a placeholder ("Illinois Remote Work, More…" is still rejected), and that non-remote jobs are judged as before.
- **Not changed, and a separate gap (T84):** 26 jobs whose title passes sit in Indian cities the main city list does not know (24 Accenture "Custom Software Engineer" roles in Coimbatore, Indore, Nagpur and Bhubaneswar, 2 InMobi in Lucknow; 2 posted within 7 days) and are rejected for location today. None of the 362 jobs located in such places is remote-flagged, so this change neither causes nor fixes it. **Residual risk:** a remote-flagged job in an Indian place outside both lists would now be rejected (0 seen in 39,713 jobs).

### Fixed (2026-10-11, T78 — closed-job detection works again on boards cut at the posted-date window)
- Since T02, a fetch that stopped at the window (Oracle HCM, Eightfold, SmartRecruiters: 21 boards) was marked incomplete, and `record_sightings` counts no misses on an incomplete board, so those boards could never close a job. What the stop leaves unread is only older jobs, so now (`record_sightings(…, windowed=…)`, `adapters.base.WINDOW_STOP_REASON`) a stored job of such a board counts a miss when its posted date is inside the window **minus one day** and the board did not return it; older and undated jobs stay unknown, and any other early stop (failed page, time budget, cap) still counts none. The day of margin covers a list that is only roughly ordered by date (the three adapters measured 0 order violations on 2026-10-10, but only on the boards sampled).
- **Measured through the real adapter** (live Qualcomm Eightfold board, scratch database, no Gemini key, `closed_after_missed_scans` 1, window 7): a stored job posted 2 days ago that the board does not return, and a stored one posted 60 days ago. Before (the pre-T78 clone): both `missed_scans` 0, none closed, log `no job of this board counts as missed`. After: the 2-day-old one `missed_scans` 1 and closed (`1 job(s) marked closed`), the 60-day-old one untouched. `tests/test_window_closing.py` (10 tests; 7 were red before the change, including the named reason constant and `incomplete` winning over `windowed`; the other 3 already passed and pin what must not change: old jobs, undated jobs, other early stops); three deliberate breakages of `db.py` (no margin, undated counted, old counted) each turn a test red.
- Residual risk, stated: if a board's order were not by date, an open job inside the window could be missed on three scans in a row and closed (it would reopen the first time a scan returns it, but a stop at the window never returns it again once it is older than the window). Nothing measured shows this on these three adapters.

### Added (2026-10-11, T80 — user guide; Manish put the web UI (T45) on hold)
- New `docs/00-user-guide.md`: for someone who edits files rather than code. One table says "I want to… → change this → where"; then install, `autopilot init`, the resume and key, every `config.json` and `.env` setting with its default, how to edit the title and location word lists in `job_hunt/prefilter.py` and check the edit, adding companies with `discover`, reading the CSV (`export`, `mark`, `draft`), running daily, and a troubleshooting table. Linked from the README and `docs/README.md`. Replaces the web UI proposed in T45 (design kept in `docs/superpowers/specs/2026-10-10-web-ui-design.md`).
- New `scripts/check_filter.py`: `python scripts/check_filter.py "Java Developer" "Bengaluru, India" [--remote]` prints `KEPT` or `REJECTED — <the filter's reason>` for one job, so an edit to the word lists can be checked in a second, without a scan. 5 tests, all red before it existed.
- **Checked against the code, not only read.** `tests/test_user_guide.py` (14 tests) takes every setting the guide names and checks it against the program: each `config.json` key must be read by the code **at the place the guide says** (an `ast` pass over `job_hunt/`: top level, `candidate` or `telegram`); every key of `config.example.json` must be in the guide; the numeric defaults must equal the code's (`min_score_of({})`, `max_posted_age_of({})`, `DEFAULT_FETCH_WORKERS`, `DEFAULT_MAX_JOBS_TO_SCORE`); each `.env` variable must be read by the code; each pre-filter pattern name must be a compiled regex in `prefilter`; every `autopilot` command and `--flag` in a command line (inline or fenced) must exist; every repo path and in-page link must resolve; and the guide's table of example jobs is run through the real `should_evaluate_job`. Each kind of check was shown to fail on a deliberate breakage of the guide (14 breakages tried; the one that slipped through, a wrong script path inside a fenced command, led to checking every word of every command line).
- **Run once from a fresh `git clone` in an empty directory (scratch copy, `python3.11` venv; real network and key):** `pip install -e .` 32 s; `autopilot init`; edit `config.json`; `doctor` (one Lever host timed out once; the rest PASS); `autopilot scan --limit 3 --posted-within 3` (2,354 fetched, 17 sent to Gemini, 17 scored, 3 min 15 s; `Candidate: Test Person` shows the edited settings are in force); `export --min 85`; `mark 1 applied` (the next `export` gains an Application column); `draft 2` (3 Gemini calls, 16 s, four files); `discover --add "Figma, Zerodha" --merge companies.json` (3 min 21 s: Figma already listed, Zerodha has no supported board); `./run_daily.sh --limit 1 --posted-within 1` (exit 0, `data/scan.log` written, `already scored 16`); removing `|java` from `TITLE_EXCLUDE_PATTERN` flipped `Java Developer` to KEPT and adding `|data\s*engineer` kept `Data Engineer` (so the editable install reads the edited file). **Not run:** `scripts/systemd/install.sh` (installing the timer is Manish's go-ahead, T07) and the `anthropic` / `claude_cli` providers.
- **Two things the run found.** (1) The `.env` template overrode `config.json` (fixed as T81, above). (2) `docs/07` listed `scoring_mode` and `max_jobs_to_score_per_run` in the `candidate` table, but the code reads them at the top level (`scanner.py`, `scorer.py`), so a value put under `candidate` was ignored without a message; the rows moved to the top-level table.

### Fixed (2026-10-11, T81 — the `.env` that `autopilot init` writes no longer beats `config.json`)
- Found while following the new user guide (T80) in a fresh `git clone`: `autopilot init` wrote a `.env` with `CANDIDATE_NAME="Your Name"`, `RESUME_PATH="resume/YOUR_RESUME.md"` and `TOP_N=5` as live lines, and `main.load_config` lets any of those three beat `config.json` without a placeholder check. **Measured:** after `init`, setting `candidate.name` to "Test Person" and `candidate.resume_path` to `resume/me.md` in `config.json` still gave `name 'Your Name'`, `resume_path 'resume/YOUR_RESUME.md'`: a new user would have scanned against the template resume, with no message. The four lines (`MIN_SCORE` was already commented since T05) are now comments in `job_hunt/data/env_example`. An `.env` made earlier keeps its lines: delete or comment `CANDIDATE_NAME`, `RESUME_PATH` and `TOP_N` there if `config.json` should decide (Manish's own `.env` has real values in them, so nothing changes for him). `tests/test_env_template.py` (3 tests, all red before): no live override line in the template; the lines stay as commented examples; the real consumer, `init` in an empty directory then `load_config` after editing `config.json`, returns `config.json`'s name, resume path, `top_n` and `min_score`.

### Fixed (2026-10-10, review of T07 / T28 — the timers wait for the network)
- The unit files asked for `Wants=` / `After=network-online.target`, a unit the systemd **user** manager does not have (`systemctl --user show network-online.target` → `LoadState=not-found`, measured): the lines did nothing, and a run made up at login (`Persistent=true`) could start before Wi-Fi is connected and fetch nothing. Both services now run `scripts/systemd/wait-online.sh` first: it waits up to 5 minutes for a TCP connection to `generativelanguage.googleapis.com:443`, then gives up with a line in `data/scan.log` (the unit fails, so no scan runs offline). Measured: online it returns 0 (about 5 s per try on this machine); under `unshare -rn` (no network) it exits 1 at its limit and writes the line. The tests stub the probe (no network). Still not installed: that is Manish's go-ahead (T07).

### Added (2026-10-10, T74 — AI Engineer / Forward Deployed Engineer titles, with a rubric clause for heavy AI)
- Manish: allow these titles, but only when the posting accepts his stack (MEAN, backend; GenAI used in workflows), not when it requires heavy AI such as LangGraph, LangChain, vector databases or "advanced things". **Pre-filter:** `AI / Gen AI / Generative AI / Agentic AI / Applied AI / LLM Engineer` and `Forward Deployed Engineer` titles now match the include list (seniority, intern, test, frontend and platform exclusions still apply; "AI/ML Engineer", "Machine Learning Engineer" and "Data Scientist" are not added). Measured on the saved fetch of 2026-10-08: survivors 1,792 → 1,900 (+108, 0 removed; 80 of the 108 name an Indian place, 18 posted within 7 days, 60 within 30). 28 of the 108 are OpenAI offices outside India (Paris, Tokyo, Singapore…) that the "remote" flag lets through; the rubric caps them (T77).
- **Rubric (rule 8):** a REQUIRED qualification that demands hands-on AI/ML engineering he has not done caps the score at 50: agents or LLM pipelines with an orchestration framework, RAG/semantic search over a vector database, training / fine-tuning / evaluating models, PyTorch / TensorFlow / Hugging Face, MLOps / LLMOps, NLP specialisation, or years of ML experience. Not triggered by "bonus" / "preferred" items, by mere familiarity with LLMs, RAG or function calling, or by using LLM APIs inside backend work. Without it the new titles would flood the CSV: **measured (gemini-3.5-flash-lite pinned, one run, 75 India AI/FDE postings fetched 2026-10-10 with full descriptions, labelled by Claude against his rule in the new `scripts/golden_set_ai.csv`)**: the old rubric passed 23 at 70, 19 of them labelled `no` (precision 17%).
- **Three wordings were measured; the shipped one is the third (v8c).** v8 (first): 3 pass, 2 false positives, but it capped postings that only ask for *familiarity* (DevRev FDE 75, 75, 75 → 45, 45, 45; Notion once 30 for an unrelated location reading). v8b ("hands-on", "familiarity" exception): 5 pass, 3 false positives, allowed found 2 of 9; three runs each: Notion 75, 75, 75; MongoDB 72, 75, 75; Razorpay 90, 45, 45; DevRev 50, 45, 50. v8c (v8b + "bonus"/"preferred" sections never count): on the 43 AI postings scored before the daily quota ended, **16 passes → 2** (the old wording on the same 43 jobs); the two left are Genpact's "AI Engineer 4A" (a Databricks data-engineering role, 85, the same under the old rubric) and HackerRank's FDE (a customer-configuration role, 75).
- **Cost, measured on the original 82 labelled jobs** (v8b, one run; v7's two runs on the same day for comparison): `apply` found 12 of 14 (v7: 14 of 14 in both runs), false positives 0 at 60 and 70, AUC 0.945 vs 0.971 / 0.973 (the CI of the difference includes 0), 3–4 jobs change pass/fail against 0–1 between two v7 runs. The 25 labelled jobs that mention AI items, scored twice under v8c: Thermo Fisher j7 (`apply`, 90 under v7) → 45, 45; MongoDB g8 (`apply`, 90) → 90, 45; Philips g12 (`maybe`, 85) → 75, 45; all others within noise and no `no` job rose to 70. **j7's requirements are RAG, agentic workflows and pgvector/Qdrant vector search: exactly what Manish said to reject, so its old `apply` label (from 2026-10-04, before his rule) probably no longer holds; I did not change it (T59 is his to confirm).**
- **Not measured / caveats.** The final wording's full 75-job run stopped at job 43 when the 500-call daily quota of `gemini-3.5-flash-lite` ran out (19:28 IST; the API said "retry in 10 h"); a full re-run is owed. All 75 labels are one rater's (mine); only 9 postings are labelled allowed, all borderline, so the "allowed found" figures rest on a handful of jobs and the model flips ±30 on them between runs (Razorpay 90, 45, 45). Expect real AI/FDE postings that fit him to be capped some of the time; the cost of the clause is those misses. No held-out AI postings exist yet: the next scans' AI titles are the held-out test. Not run: a real scan with these titles.
- **Review, 2026-10-11 (gemini-3.5-flash-lite pinned, rubric unchanged since 7bc5b61; score files in the gitignored `data/golden_runs/`).** The owed full run of the 75 AI postings: **6 pass at 70 (old rubric: 23), 3 of them `no` (old: 19): precision 17% → 50%**; the one `apply` (Notion FDE, ai65, 75) and 2 of 8 `maybe` pass; the first 43 jobs agree with the 2026-10-10 partial run (mean |difference| 2.6, no pass/fail change). The 3 false positives are not the clause's: Genpact ai33 85 / 90 / 85 (85 under the old rubric too), HackerRank ai41 70–75 (old 70), HPE ai44 85 / 85 / 45 (old 40: it flips). The original 82 jobs: false positives 0 at 60 and 70, `apply` 13 of 14, AUC 0.976 (v7: 0.971 / 0.973); the only pass/fail change against both v7 runs is j7 (90 / 90 → 45), the heavy-AI posting the clause targets. MongoDB g8 (`apply`) under this wording, 8 runs: 90, 45, 90, 45, 50, 90, 45, 40 — its required list does ask for "hands-on experience prototyping with LLMs or agentic systems (evals, fine-tuning, RAG, tool use, orchestration frameworks)", so it is borderline under Manish's rule, not a misfire; its label is his to confirm (T59). Separately, Notion ai65 scored 30, 75, 30 in three more runs: rule 1 (the outside-India cap) applied to a Hyderabad hybrid role (T79).

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
- Manish chose `min_score` 70 (the CSV still lists every score). *Corrected in review:* the 92%-vs-86% precision figures were the pre-T73 rubric's (one saved same-day 3.5 run of that rubric, re-analysed: 92% vs 83%); with rubric v7 (T73, before T74's AI clause) neither 60 nor 70 passes a `no` job on the 82 labelled jobs (2 runs, 14/14 `apply` at both). It now lives in one place: `config.json`'s `candidate.min_score`. The code default is 70 for every reader (`job_hunt/settings.py`; scanner and export used 55 before), the example configs say 70, the `.env` template has no active `MIN_SCORE` line, and `run_daily.sh` no longer exports a value that `.env` overrode (its banner printed 70 while the scan used 60). Manish's own `config.json` is set to 70 and his `.env` line is commented out.
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
- Four entries were headed 2026-10-05; the commits that added them (bfe74de, 4462b99) are dated 2026-10-04, and `git log` has no commit on 2026-10-05 at all. The headings, the two measurement dates inside the entries (Amazon's 2,329 India roles; the end-to-end funnel) and the same dates in five source/test comments now say 2026-10-04. The only evidence is the git author dates (+0530); if the machine clock was off when the commits were made, these dates are off with it. Every dated heading now equals the date of the commit that introduced it (checked with `git blame` on each heading line); the release headings match their tags.

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
- `autopilot draft` sends the whole resume to the cover-letter prompt (it was cut at 2,500 characters, dropping Projects and Education; the scorer got the full resume since d773438).

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
- Comprehensive architecture and future roadmap guide ([`ARCHITECTURE.md`](ARCHITECTURE.md)) detailing high-level design, data flow, component breakdown, testing invariants, and multi-milestone expansion plan (multi-channel alerts, direct ATS scrapers, granular scoring, web dashboard, interview prep).
- Local runtime and toolchain bootstrap: Python 3.12 virtual environment, `uv` dependency management, full dev/mcp/claude dependencies installed.
- Added dedicated Google Gemini LLM provider using `google-genai` SDK:
  - Settings parser and [`job_hunt/config.py`](job_hunt/config.py) accept `GEMINI_API_KEY` and `GEMINI_MODEL` (defaulting to `gemini-3.5-flash-lite`).
  - Provider dispatch in [`job_hunt/llm_utils.py`](job_hunt/llm_utils.py) and scoring in [`job_hunt/scanner.py`](job_hunt/scanner.py).
  - Strict JSON output formatting (`{"score": <0-100>, "reason": "<one sentence explanation>"}`) via `response_mime_type="application/json"`.
  - Graceful fallback returning `{"score": 0, "reason": "Scoring failed"}` on API or parsing failures to guarantee the scan loop never crashes.
- **Module 1 (Native Direct ATS Adapters)**:
  - Added zero-browser HTTP fetching adapters under [`job_hunt/adapters/`](job_hunt/adapters/):
    - Greenhouse (`boards-api.greenhouse.io` and `boards.eu.greenhouse.io`)
    - Lever (`api.lever.co/v0/postings`)
    - Ashby HQ (`api.ashbyhq.com/posting-api/job-board`)
    - SmartRecruiters (`api.smartrecruiters.com/v1/companies/{slug}/postings`)
    - Workday Client CXS API (`{tenant}.{dc}.myworkdayjobs.com/wday/cxs/...`)
    - Recruitee (`{slug}.recruitee.com/api/offers`)
    - Personio (`{slug}.jobs.personio.de/xml?language=en`)
  - Intelligent ATS auto-detection from company URLs (`detect_ats`).
- **Module 2 (SQLite Deduplication & Local Regex Pre-Filter)**:
  - Unified canonical schema [`JobPosting`](job_hunt/models.py) with deterministic MD5 canonical hashing and URL hashing.
  - Persistent SQLite database at `data/jobs.db` ([`job_hunt/db.py`](job_hunt/db.py)) tracking `discovered`, `skipped`, `scored`, and `notified` status.
  - Local regex pre-filter ([`job_hunt/prefilter.py`](job_hunt/prefilter.py)) to drop non-matching titles, excluded seniorities, and unsupported locations before sending to LLM.
- **Gemini Scoring & Rate Throttling**:
  - Unified scoring pipeline ([`job_hunt/scorer.py`](job_hunt/scorer.py)) with 4.2-second sleep pacing to strictly respect 15 RPM cap.
  - Automatic Telegram alert triggers for jobs matching score threshold (>= 70).
- **Task 1: Ingest Local Data & Build `companies.json`**:
  - Implemented [`job_hunt/company_builder.py`](job_hunt/company_builder.py) extracting Indian tech companies from `india.yml`.
  - Matched company names against `companyCache` in `linkedin-size-filter-backup-2026-10-03.json`.
  - Applied Safety Blocklist: safely discarded only companies explicitly tagged as `1-10 employees` or `11-50 employees`, while retaining all larger tiers (`51-200`, `201-500`, `501-1,000`, `1,001-5,000`, `5,001-10,000`, `10,001+ employees`) and unlisted/unknown entries.
  - Generated deduplicated `companies.json` with 249 companies across Ashby, Greenhouse, Lever (with Workday support).
- **Task 2: Notification Badges (`job_hunt/notifier.py`)**:
  - Added `format_job_alert` to [`job_hunt/notifier.py`](job_hunt/notifier.py) embedding company headcount badge:
    `🏢 <b>Company:</b> {company} 🏷️ <i>[{headcount}]</i>`.
  - Integrated badge with [`JobPosting`](job_hunt/models.py) model and [`job_hunt/scorer.py`](job_hunt/scorer.py).
- **Task 3: Lightweight Diagnostics (`autopilot doctor`)**:
  - Implemented single-file diagnostics module in [`job_hunt/doctor.py`](job_hunt/doctor.py) runnable via `autopilot doctor` or `python -m job_hunt doctor`.
  - Verifies SQLite write permissions on `data/jobs.db`.
  - Confirms Gemini quota health with 1-token test prompt (`gemini-3.5-flash-lite`).
  - Verifies Telegram bot credentials via `getMe`.
  - Pings sample network egress endpoints for Greenhouse, Lever, Ashby, and Workday.
  - Outputs a clean pass/fail checklist to terminal.
- **Task 4: Daily Runner Script (`run_daily.sh`)**:
  - Created executable [`run_daily.sh`](run_daily.sh) for automated execution.
  - Appends timestamped logs to `data/scan.log`.
  - Sets default alert threshold to score >= 70.
  - Forwards CLI parameters (e.g. `--limit 5`).
- **Slug Validation & Active Board Pruning (`job_hunt/validator.py`)**:
  - Implemented concurrent ATS endpoint validator ([`job_hunt/validator.py`](job_hunt/validator.py)) with CLI command `autopilot validate` / `python -m job_hunt validator`.
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
