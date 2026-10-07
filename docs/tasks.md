# TASKS — JobNotify task board

The one shared board for everyone working on this repo: Manish, Claude Code,
Antigravity, or any other agent.

- **Told to "work from docs/tasks.md"?** Follow the [Working loop](#working-loop).
- **Told to "verify the tasks"?** Follow [Verifying](#verifying).

**Last re-evaluated:** 2026-10-07 against commit `4ac4c68`: all 30 tasks in the review queue verified by a fresh
Claude session at Manish's request (instead of Antigravity); T64–T67 added and implemented (587 tests pass,
coverage 91.9%, ruff and mypy clean — measured). File:line references drift; search for the named function if
a line has moved.

---

## Working loop

First read `CLAUDE.md` (project context) and this whole file. Then repeat:

1. **Pick.** First any task with status `changes` (a verifier sent it back). Otherwise
   take the first `todo` in the [Accuracy-first order](#accuracy-first-order) whose
   *Needs* are all `review` or in the Done log; when that list is exhausted, take the
   first `todo` from the top of the tables below (P0 before P1, lower ID first). Skip
   `decision`, `manish` and `blocked`. Never make Manish's decisions for him.
2. **Claim.** Set Status to `doing · <you> · <date>`, where you are `claude`,
   `antigravity`, `manish`, and so on. Commit only that line: `tasks: claim T03`. A
   task already `doing` belongs to someone else; if it has had no commits for 3 days,
   ask Manish before taking it.
3. **Implement** that task only, with tests. Unrelated problems you notice go in the
   [Inbox](#inbox), not into this change.
4. **Check.** Run the task's *Done when* through the real program (not a proxy), then
   `pytest`, `ruff check job_hunt` and `mypy`. If a check fails, or you couldn't run it,
   say so. Don't hand it over as done.
5. **Commit** the work, with a message that starts with the ID
   (`T03: stop scoring when Gemini quota is exhausted`). Add a CHANGELOG line under
   `[Unreleased]`. Stage only the files you changed (`git add <paths>`, never
   `git add -A`), because another agent may be working in the same tree.
6. **Hand over for review.** Set Status to `review · <you> · <short hash>`. Add a row
   to the [Review queue](#review-queue) with the exact commands you ran and their
   output. Commit: `tasks: T03 ready for review`.
7. **Next.** Go back to step 1. Stop when nothing is pickable, when Manish told you
   to stop, or when you're blocked. Then report what you finished and what is waiting
   on him.

One task at a time: never claim a second task while one of yours is `doing`.

**Found something new?** Add it to the [Inbox](#inbox) with the next free ID. Never
renumber IDs. Don't reopen anything in [Rejected](#rejected--parked) without new
evidence.

**Manish answers a `decision`** by writing his choice into the task and setting it to `todo`.

## Verifying

For each row in the [Review queue](#review-queue), oldest first:

1. **Read** the task and `git show <commit>`. The diff should contain that task and
   nothing else.
2. **Re-run** the *Done when* check and the gates yourself. Don't trust the evidence
   column; checking it is the point.
3. **Check** that the CHANGELOG line exists and that what it claims is true.
4. **Pass:** remove the row from the queue and from its priority table. Add the task to
   the [Done log](#done-log) with your command, its result and
   `verified · <you> · <date>`. Commit: `tasks: verify T03`.
   **Fail:** set Status to `changes · <you>`. Under the task, add a
   **Review notes (<date>, <you>):** line saying what failed and how you checked.
   Remove the queue row. Commit: `tasks: T03 changes requested`.

Prefer a verifier other than the implementer, or at least a fresh session.

### Ground rules for every agent

- **Drafts only** — never auto-apply or submit an application.
- **Tests make no network calls.** Stub adapters, Gemini and Telegram.
- **`companies.json` is curated.** Change it through `autopilot discover` and review
  with `git diff`. Never overwrite it with `autopilot harvest`.
- **Tag claims** as *measured* (you ran it; give the number), *inferred* (follows from
  a measurement) or *assumed* (not checked). Never write "verified" for a check you didn't run.
- **Secrets** stay in `.env` / `config.json` (both gitignored). Never copy them into
  this file, commits or logs.

**Status:** `todo` · `doing · who · date` · `review · who · commit` ·
`changes · verifier` (sent back; see the task's review notes) · `blocked` ·
`decision` (Manish chooses) · `manish` (needs his accounts or devices).
Verified tasks leave their table and move to the Done log.
**Size** (estimates): XS < 30 min · S ≈ 1 h · M ≈ half a day · L ≈ 1+ day

---

## Accuracy-first order

**Manish's rule (2026-10-04):** the product is a job notifier driven by the LLM score, so
any task that changes what Gemini sees, how it scores, or which jobs reach it comes
before everything else. **Division of work:** Antigravity implements; Claude reviews
(see [Verifying](#verifying)). Claude's own tasks in the Review queue should be verified
by Antigravity. (2026-10-07: Manish asked Claude to verify the 30 queued tasks instead; a fresh session did.)

**Every task in this list is done and verified (Done log, 2026-10-07).** It is kept as the record of the order.
What still moves the score: Manish's labels (T59, and whether g27 is `apply`), T68 (Accenture's generic titles,
a decision) and the decisions below.

| # | Task | Why it changes the score or the accuracy | Evidence |
|---|---|---|---|
| 1 | **T60** Scores flip by ~50 points between runs on ambiguous postings | One run per job misplaces ambiguous jobs across MIN_SCORE | measured |
| 2 | **T12** CRM / platform "developer" titles | Wastes scoring calls on Salesforce / Dynamics / ServiceNow roles | measured on the old list, inferred for 215 boards |
| 3 | **T61** C++ / embedded / kernel / GPU / Rust / Ruby / PHP titles | 4.7% of survivors are scored for nothing | measured |
| 4 | **T11** "Computer Scientist" titles | 16 of 19 were skipped by the pre-filter | measured |
| 5 | **T17** Cost of the python/java/golang title exclusions (measure only) | Manish's resume has Python, yet a "Python" title word is excluded | measured: exclusion list in `prefilter.py` |
| 6 | **T49** Big employers that report "no India jobs" | Possible missed jobs at Accenture, Sony, Western Digital | assumed, not investigated |
| 7 | **T03**, **T04** Quota breaker, newest-first cap | Decide which jobs get scored when the daily quota runs out | inferred |
| 8 | **T41** Structured sub-scores | Breaks ties by stack / seniority / location. Prompt wording can't (T48: two versions moved calibration, not ranking) | measured (T48) |
| 9 | **T29**, **T35** Store the job text; funnel log line | Needed to audit and re-score; not accuracy by themselves | inferred |

Decisions that change what Manish sees: **T05** (MIN_SCORE 60 or 70) and **T02** (posted-date
window). On the first real scan (203 distinct jobs, 2026-10-04) 74 scored ≥ 60, 67 ≥ 70
and 38 ≥ 80 (measured).

After this list: **T40, T50, T42** (Manish will not use TinyFish; all three verified 2026-10-07), then the rest.

### New accuracy tasks

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T59 | Confirm the golden-set labels | manish | — | S | T48 |

T48, T57, T58, T60, T61 and T49 were verified 2026-10-07 (Done log).

**T59 · Confirm the golden-set labels (Manish).** The 82 labels are Claude's, with one line of
reasoning each in `label_reason`. Sort `scripts/golden_set.csv` by `label`, fix any you
disagree with, and set `label_source` to `manish` on rows you checked (about 15 minutes,
assumed). Then run `python scripts/score_golden_set.py` (live: about 164 Gemini calls, ~15
minutes).
*Done when:* the report prints no "NOT CONFIRMED BY MANISH" banner.
**Question from the T58 review (2026-10-07):** g27, Amazon SDE II "SP Support", is labelled `apply`, but its
posting lists "3+ years of Video Games Industry … experience" as a *basic* qualification. Gemini caps it every
time under the current prompt (40–45 on 3.5-flash-lite ×5, 40 and 40 on 3.1-flash-lite, reason: "lacks the
mandatory 3+ years of experience in the Video Games Industry"). If you would not apply, relabel it `no` or
`maybe`: it is the one `apply` job the current prompt misses.

---

## P0 — Before scheduling the daily run

Why this comes first: the expansion work raised volume about 6× (36,228 jobs fetched,
1,271 pre-filter passes, per CHANGELOG). The production DB `data/jobs.db` holds one scan of
2026-10-04: 30,367 rows, 145 `scored`, 23 `discovered` (the Amazon re-score, T57), 30,199 `skipped`
(measured 2026-10-07, read-only). T03 and T04 now stop scoring when the quota is gone and cap a run
at 400 jobs; T02 and T05 are still Manish's decisions.

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T01 | Back up the repo to a private remote | manish | — | XS | — |
| T02 | Turn on the posted-date window by default | decision | — | XS | — |
| T05 | Keep one MIN_SCORE, in one place | decision | — | XS | — |
| T06 | Check that Telegram works | manish | — | XS | — |
| T07 | Schedule `run_daily.sh` with a systemd user timer | todo | — | S | T02, T03, T04, T05 |
| T08 | Remove or repoint `setup_cron.sh` | todo | — | XS | T07 |
| T09 | First full production run; record the funnel | todo | — | S | T02–T07 |
| T64 | Skip a Gemini model whose daily quota is gone | review · claude · 2dede5d | claude | S | — |

T03 and T04 were verified 2026-10-07 (Done log).

**T64 · Skip a Gemini model whose daily quota is gone** (found verifying T48/T03, 2026-10-07). With
`gemini-3.5-flash-lite` at its 500/day limit, every job still sent it two requests and slept 5 s (Google's
"retry in 23h20m6s" does not match the per-minute pattern) before the fallback answered: ~6.5 s per job,
~43 min on a 400-job run (inferred). A per-day 429 now marks the model until Google's `retryDelay`; all
models out → `GeminiQuotaExhausted` with no request, so T03's breaker stops at once.
*Done when:* with one model out for the day, a run asks it once (not twice per job), and per-minute 429s are
still retried.

**T01 · Private backup remote.** `origin` points at upstream
(`tarunlnmiit/autopilot-jobhunt`). The 8 commits since `3b59877` exist only on this
disk (measured). Create a private GitHub repo, run `git remote add backup <url>`, and push `main`.
Never push to `origin`.
*Done when:* `git ls-remote backup main` prints the same hash as `git rev-parse HEAD`.

**T02 · Posted-date window on by default.** `--posted-within N` /
`candidate.max_posted_age_days` exists (b700235). But `config.json` doesn't set it and
`run_daily.sh` doesn't pass it (measured), so every run scores all 1,271 passes.
Measured by the expansion work: 226 passes posted ≤7 days ago, 99 ≤3 days.
**Manish: choose N** (suggested 7). Set it in `config.json`. Also document
`max_posted_age_days`, `fetch_workers` and `gemini_scoring_mode` in
`config.example.json`; none of them are there today.
*Done when:* `./run_daily.sh --limit 5` logs "skipped as posted more than N day(s) ago".

**T05 · One MIN_SCORE.** `.env` has `MIN_SCORE=60`, and `load_dotenv(override=True)`
(`main.py` L52) makes it beat the `70` that `run_daily.sh` exports (measured).
`run_daily.sh` then prints 70 in its banner while the scan uses 60.
**Manish: choose 60 or 70.** Keep the value in one place and remove the misleading
banner value.
*Done when:* the scan's own `Min score:` log line (`scanner.py` L383) shows the chosen
value, whichever way the run is started.

**T06 · Telegram.** The last sends logged in `data/scan.log` failed with HTTP 404
(2026-10-03 13:55Z, measured). `.env` was edited afterwards, so the current state is
unknown. Run `autopilot doctor`; if Telegram fails, fix the token or chat ID in `.env`.
*Done when:* the doctor's Telegram check passes and a test message arrives on the phone.

**T07 · Schedule the daily scan.** There is no crontab entry and no scan timer
(measured). Follow the existing `~/.config/systemd/user/job-hunt-wallpaper.timer`:
`OnCalendar=` plus `Persistent=true`, which should catch up a run missed while the
laptop was off (inferred from systemd docs, not tested). The service runs
`<repo>/run_daily.sh` with `WorkingDirectory=<repo>`. Commit the unit files under
`scripts/systemd/` with install steps.
*Done when:* `systemctl --user list-timers` lists the timer, and
`systemctl --user start <service>` appends a complete run to `data/scan.log`.

**T08 · `setup_cron.sh`.** It installs `python -m job_hunt.main scan >> ./scan.log`,
which bypasses `run_daily.sh` (measured). It is still referenced in `SETUP.md` L523,
`docs/04-companies-and-scanning.md` L50 and `docs/08-troubleshooting.md` L13. Delete
it and point the docs at T07's timer, or make it install `run_daily.sh`.
*Done when:* `grep -rn setup_cron .` returns only the references you intended.

**T09 · First production run.** After T02–T05 (T06 optional), run `./run_daily.sh`
once. Record in CHANGELOG: jobs fetched, India, pre-filter passes, too old, scored,
≥ MIN_SCORE, scoring failures, and minutes taken.
*Done when:* `data/jobs.db` has rows scored today, a new `output/jobs_*.csv` exists, and
`data/scan.log` ends with "Scan finished with exit code 0".

---

## P1 — Small correctness fixes

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T66 | Declare PyYAML (discover failed on a fresh install) | review · claude · 83a573d | claude | XS | — |
| T67 | `discover --help` / a mistyped flag ran a full discovery | review · claude · 4ac4c68 | claude | XS | — |

T11, T12, T14, T15, T16, T17 and T18 were verified 2026-10-07 (Done log).

**T66 · PyYAML is not a declared dependency** (found verifying T51). `discovery`, `harvester` and
`company_builder` import `yaml`; neither `pyproject.toml` nor `requirements.txt` listed it, so on a fresh
`pip install -r requirements.txt` `autopilot discover` died with `ModuleNotFoundError` (measured).
*Done when:* a fresh virtualenv from `requirements.txt` runs `discover`; a test fails if a third-party import
in `job_hunt/` is missing from either file.

**T67 · `discover` ignored unknown arguments** (found verifying T66). `discover --help` or a typo
(`--add-flie`) ran a full discovery of every seed (~1,100 names, 40 workers) and wrote two files in the
current directory.
*Done when:* `--help` prints usage; an unknown or value-less argument exits non-zero; every documented flag
still works.

---

## P2 — Better input for the scorer

T23 was verified 2026-10-07 (Done log); nothing open.

---

## P3 — Coverage

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T26 | Phenom adapter (probe first) | decision | — | M | — |
| T65 | Workday "Location Negotiable" items were never resolved | review · claude · 0fcb546 | claude | XS | — |
| T28 | Monthly `discover --recheck` that only reports | todo | — | S | T07 |

**T25–T27 · New ATS platforms.** (A previous Claude session recorded that Eightfold's PCSX endpoint returns HTTP 403 and Darwinbox needs a tenant session, tried 2026-10-04/05; that note is from memory, not in the repo, so re-check before relying on it.) The census (31cb7c0) of 458 careers pages found
Eightfold and Phenom on 7% each and Darwinbox on 6%, while 52% were unidentified (per
CHANGELOG). Step 1: find a public JSON endpoint; if there is none, move the task to
Rejected with the evidence. Step 2: write the adapter, with tests on recorded fixtures
(no network).
*Done when:* `autopilot discover --add-file` accepts at least one company on that
platform, and a scan fetches its jobs.

**T25–T27 result (claude, 2026-10-06).** *T25 Eightfold:* done, verified 2026-10-07. *T26 Phenom:* the endpoint is public (`POST {host}/widgets`, `selected_fields.country=["India"]`, `size` up to 100 honoured, full description in the job page's JSON-LD), **but Phenom mostly fronts Workday**: on Cisco, DuPont, Fiserv, HPE, Philips and WBD every sampled job's `applyUrl` is a Workday tenant. I added the three missing Workday tenants instead (Cisco, DuPont, Fiserv) through `discover`, no new adapter. The only Phenom-native census board with India jobs is BCG (91 India jobs, **2** pass the pre-filter). **Decision for Manish:** is a native Phenom adapter (~150 lines, a JSON-LD description scrape) worth 2 BCG jobs, or park it until another Phenom-native company turns up? *T27 Darwinbox:* rejected, see the Rejected table.

**T65 · Workday "Location Negotiable"** (found verifying T49). 498 of Accenture's 2,000 India-search
results show this placeholder instead of a city; 8 of 12 sampled were in India by the detail endpoint, but the
pre-filter rejected all of them as not India. They now get the detail call that "N Locations" items get
(only when the title can pass).
*Done when:* a live Accenture fetch resolves them; measured: 7 detail calls, 2 India jobs recovered (471 → 473).

**T28 · Scheduled recheck.** `discover --recheck --merge companies.json` (b700235)
catches ATS migrations and dead boards, but only runs when started by hand. Run it
monthly against a scratch copy of `companies.json` and save the diff for Manish to
review. Never write the real file unattended.
*Done when:* the timer is listed, and a run produces a diff file while
`companies.json` is unchanged.

---

## P4 — One source of truth (SQLite)

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T31 | `draft` reads SQLite | todo | — | S | T29 |
| T32 | `export` reads SQLite | todo | — | S | T29 |
| T33 | first_seen / last_seen and closed-job detection | todo | — | M | T29 |
| T34 | Retire `last_scan.json`, `job_history.json`, `seen_jobs.json` | todo | — | S | T31, T32 |

T29, T35 and T36 were verified 2026-10-07 (Done log).

**T31 · `draft` reads SQLite.** Resolve `draft N` / `draft <id>` from the DB rather than
`state/last_scan.json`. This supersedes T10.
*Done when:* unit tests cover both forms; `last_scan.json` is no longer read.

**T32 · `export` reads SQLite.** `export` reads `state/job_history.json` /
`last_scan.json` (`main.py` L194–205) and ignores DB status.
*Done when:* `autopilot export --min 70 --days 7` matches the equivalent SQL query.

**T33 · Closed jobs.** Record first_seen / last_seen. Mark a job `closed` once its
board stops returning it for N scans in a row.
*Done when:* unit tests cover the transitions.

**T34 · Retire the JSON state files.** Once T31 and T32 are done, remove their writers
and readers. Add a one-time import into SQLite if any history would otherwise be lost.
*Done when:* `grep -rn "last_scan.json\|job_history.json\|seen_jobs.json" job_hunt`
returns nothing.

---

## P5 — Features

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T38 | Application tracker: `autopilot mark <id> applied` | todo | — | M | T29 |
| T39 | One rolling `output/open_matches.csv` | todo | — | S | T32, T38 |

T37 and T40 were verified 2026-10-07 (Done log).

**T38 · Application tracker.** `autopilot mark <id> applied|interview|rejected|offer`,
stored with the date.
*Done when:* the status is stored in the DB and shown by `export`.

**T39 · Open-matches file.** Each run rewrites `output/open_matches.csv`: every job
scored ≥ MIN_SCORE that isn't applied, isn't closed and is still inside the
posted-date window. The per-scan files stay.
*Done when:* the file is regenerated each run and excludes applied jobs.

---

## P6 — Later / cleanup

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T44 | Keyword gap analysis in `draft` | todo | — | M | T40 |
| T45 | Local dashboard or TUI | todo | — | L | T29 |

T41, T42, T43, T50, T51, T52, T55 and T63 were verified 2026-10-07 (Done log).

---

## Inbox

New findings go here with the next free ID (next: **T70**), an evidence tag and the
file:line. Manish or the triaging agent moves each one into a priority table.

| ID | Finding | Evidence | Added by |
|---|---|---|---|
| T62 | **Decision for Manish (T17's result):** the language words in the title exclusion block, among India jobs that name a target role and have no other blocker: **python 33** (24 posted in the last 30 days, corrected 2026-10-07 from 21; 21 look like backend/SDE/full-stack, e.g. JPMorgan "Software Engineer III - Python LLM Engineer", Plane "Software Engineer, Backend (Python)"), **java 93** (85, corrected from 75), golang 5, react/angular 6, frontend 8. Seniority words (staff, lead, principal, manager, architect) block about 600 more, as intended. Allow "python" in titles? It would add about 33 scoring calls to a full scan (+3%), and your resume lists Python. Java and golang: say which. Each is a one-word change plus a test | measured on 34,416 jobs fetched 2026-10-06: `python scripts/measure_prefilter.py --jobs <saved fetch>`; the 30-day column was undercounted (jobs posted that day counted as old) until 55aa663 | claude |
| T68 | **Decision for Manish:** Accenture's generic "Custom Software Engineer" title (418 of its ~470 pre-filter survivors) hides platform and senior roles that T12's title words would have rejected. In the live scan of 2026-10-07 all 6 jobs the newest-first cap picked were Accenture's ("Posted Today"), and all scored 30–40 for SAP BRIM, Varicent administration, automotive HIL testing or 7.5+ years. Option: read Accenture's "Must have skills : …" description line in the pre-filter (needs the description, i.e. a detail call per survivor). Cost of doing nothing: up to ~36 scoring calls a week on mostly low scores (inferred from 36–37 posted per 7 days) | measured: 6 of 6 scored jobs (scratch-dir scan, 2026-10-07); inferred: the weekly cost | claude |
| T69 | Low-priority notes from the 2026-10-07 review, no action proposed: (a) structured scoring (T41) hard-codes temperature 0.1 and ignores `gemini_temperature` (T60) — `llm_utils.score_job_structured_with_gemini`; (b) the deprecated non-Gemini scorer still cuts the resume at 2,500 and each JD at 1,500 characters — `scanner.score_batch`; (c) the T61 word `embedded` would also reject "Backend Engineer – Embedded Finance" (0 such titles in 34,416); (d) one full scan writes ~5.3 MB of DEBUG log, so T16's 5 MB × 3 rotation keeps about the last 3 scans; (e) the production `data/jobs.db` still has the pre-T29 schema and `user_version` 0: its next scan runs T29's columns and T30's one-time Workday repair (checked on a copy: 30,367 rows kept, 0.19 s) | measured (a, b by reading the code; c, d, e by running it) | claude |

---

## Review queue

The implementer adds a row when a task reaches `review`; the verifier removes it.

| ID | Commit(s) | Implementer | Evidence (command → result) |
|---|---|---|---|
| T67 | 4ac4c68 | claude | `pytest tests/test_discovery.py -k never_starts` → 3 failed before ("a full discovery was started", once the test had a seeds file), pass after. Real CLI: `python -m job_hunt discover --help` → usage, exit 0; `discover --add-flie x.txt` → "unknown or incomplete argument '--add-flie'", exit 1. Every flag used in the docs (grep of CLAUDE.md, README, docs/, code) is in the accepted set. Gates green. |
| T66 | 83a573d | claude | Fresh venv (`python3 -m venv`, `pip install -r requirements.txt`): importing every module → `discovery`, `harvester`, `company_builder` fail `No module named 'yaml'`. New `test_every_third_party_import_is_a_declared_dependency` failed ("pyproject.toml lacks pyyaml"), passes after. After: fresh Python 3.11 venv from `requirements.txt` → `python -m job_hunt discover --add "Stripe" --report r.csv --out v.json --no-recheck` (scratch cwd with a copy of the seeds file) → exit 0, Stripe verified (731 jobs, 44 India). Not run: `docker build` (no Docker; it installs from pyproject). |
| T65 | 0fcb546 | claude | New adapter test failed before (0 detail calls), passes after. Live `fetch_workday("accenture", "wd103", "AccentureCareers")` with `_fetch_detail` counted: 2,000 jobs, 7 detail calls (the candidate titles among 498 "Location Negotiable"), 5 resolved to US offices (still rejected), 2 to Bengaluru/Hyderabad (now pass): pre-filter passes 471 → 473; 245 s. Gates green. |
| T64 | 2dede5d | claude | `pytest tests/test_daily_quota.py` → 5 failed before, pass after (incl. one through `run_scan`: 10 jobs, the exhausted primary asked once, 10 scored). T03's tests switched to a per-minute 429 and still pass (14 with T64's). Live, primary really out for the day: 2 golden-set jobs with the default config → 1 request to 3.5 ("daily quota exhausted; skipped for the next 22.8 h"), 2 to 3.1; second job 1.8 s. `autopilot draft 1` logged the skip once. Gates green; suite also passes under `unshare -rn`. Not measured: a full 400-job run. |

---

## Done log

The rows marked "pre-board" were finished before this board existed and have not gone
through [Verifying](#verifying). Their commit mapping comes from the commit messages
and CHANGELOG (inferred), and their numbers from CHANGELOG unless marked measured.

| ID | What | Commit | Evidence | Verified |
|---|---|---|---|---|
| T46 | Decode HTML-escaped descriptions (Greenhouse) | 95b2002 | `pytest tests/test_strip_html.py` → 6 passed; `pytest` → 380 passed, coverage 89.39%; ruff, mypy clean | verified · antigravity · 2026-10-04 |
| T13 | Remove the 2,000-char description cap when scoring | ef15c4c | `pytest tests/test_gemini_provider.py` → 17 passed; `pytest` → 380 passed, coverage 89.39%; ruff, mypy clean | verified · antigravity · 2026-10-04 |
| T19 | Add an "enrich survivors" step to the scanner | 0fd640e | `pytest tests/test_enrich.py` → 15 passed; `pytest` → 380 passed, coverage 89.39%; ruff, mypy clean | verified · antigravity · 2026-10-04 |
| T20 | Workday: fetch descriptions for single-location survivors | ded2879 | `pytest tests/test_enrich.py` → 15 passed; `pytest` → 380 passed, coverage 89.39%; ruff, mypy clean | verified · antigravity · 2026-10-04 |
| T21 | SmartRecruiters: fetch descriptions for survivors | b7ba18e | `pytest tests/test_enrich.py` → 15 passed; `pytest` → 380 passed, coverage 89.39%; ruff, mypy clean | verified · antigravity · 2026-10-04 |
| T22 | Oracle HCM: fetch full descriptions for survivors | 61c6874 | `pytest tests/test_enrich.py` → 15 passed; `pytest` → 380 passed, coverage 89.39%; ruff, mypy clean | verified · antigravity · 2026-10-04 |
| T10 | `draft N` opens digest job #N (number last_scan.json and CSV by score) | e126b79 | `pytest tests/test_draft_numbering.py` → 1 passed; `pytest` → 380 passed, coverage 89.39%; ruff, mypy clean | verified · antigravity · 2026-10-04 |
| T47 | Workday paging repeats postings | d160271 | `pytest` → 398 passed. Live, all 78 Workday tenants (447 s): 8,769 rows, 0 duplicate URLs; of 559 distinct survivors seen before the fix 1 is missing (NCR), and NCR's raw list paged with no stop rule has 24 distinct postings without it, so that one simply closed | verified · claude · 2026-10-04 |
| T30 | Dedupe by ATS job ID | 289d062 + fix 8ba9771 | First version failed review: its migration rewrote all Workday ids to `workday:<display name>:…`, so 0 of 16 live already-scored jobs matched (101 of 168 scored rows are Workday) and the next scan would have re-scored and duplicated them. Fixed by claude (one id function for adapter and migration, once-per-DB repair, dedupe keeps the scored row). After the fix: real scan of 215 companies on a copy of the production DB, Gemini stubbed → 50 queued, 0 already scored, 0 URLs twice, 34,308 rows = 34,308 distinct URLs; `pytest` → 398 passed | verified · claude · 2026-10-04 (after fix) |
| T24 | Penalise onsite work outside India | 847e3c2 (inside T48's rubric) | Rule 1 of `SCORING_RUBRIC` is in both prompts (unit test). Live, 1 job (the US-only Salesforce role): 45 without the rubric, 25 and 25 with it. Only the one job tested; the current pre-filter now rejects this job's all-US location before scoring | verified · claude · 2026-10-04 |
| T48 | Scoring rubric and a golden set | 0448ea6, 4ca2e17 (+ test fix 5602d1d) | `pytest tests/test_scoring_rubric.py` → 17 passed. Live `score_golden_set.py --limit 3` → 6 calls, report with the unconfirmed-labels banner (3.5-flash-lite was out of daily quota; 3.1 answered). `--from-scores` on the saved 75-job scores reproduces every number: FP at 70 7 → 4, precision 77% → 85%, `apply` 13/13, AUC 0.955 vs 0.956, CI [-0.028, +0.029], biggest top tie 11 → 10. 5 random `label_reason`s read against their descriptions: 5/5 match. The only full duplicate description is two ServiceNow requisitions (documented). Fixed: a rule-2 test assertion (`a and b or c`) that passed with the cap removed | verified · claude · 2026-10-07 |
| T57 | Amazon full description, not the 202-char stub | 0ed9567 | Adapter tests pass. Live `fetch_amazon()`: 2,304 India jobs, median description 3,923 chars (≥ 2,500), 0 under 500, 0 raw HTML. `data/jobs.db` (read-only): 23 Amazon rows `discovered`, score and reason NULL; `state/job_history.json` has 0 Amazon entries | verified · claude · 2026-10-07 |
| T58 | Fresher cap (rubric rule 7); rule 2 judges the work | 9dd63f5 | Saved v2/v4 scores re-analysed: Hevo 90 → 50, FP at 70 5 → 2, precision 83% → 92%, AUC 0.946 vs 0.948, `apply` 15/15 → 14/15. **Done-when partly unmet, as its evidence said:** g27 (Amazon "SP Support") is missed, and under the current prompt not bimodal but always capped ([45, 45, 40, 45, 45] in T60's runs; 40 and 40 live on 3.1, reason: the posting's 3+ years of video-games experience) — a labelling question, now in T59. Not in its evidence: `apply+maybe` recall at 70 fell 89% → 82% (Nike g20 75 → 50) | verified · claude · 2026-10-07 |
| T12 | Reject CRM/ERP/BI platform titles | 0660d1d | Saved 34,416-job fetch (2026-10-06) through each commit's real `should_evaluate_job`: survivors 1,191 → 1,109 (−82, 0 added). All 82 removed titles read: platform roles only (Salesforce, SAP/ABAP, ServiceNow, Power BI/Platform, Informatica, Oracle EBS/CPQ, Workday, D365…). Labelled `apply`/`maybe` jobs: 0 rejected. Controls pass (Node.js backend, "Dynamic Pricing") | verified · claude · 2026-10-07 |
| T61 | Reject C++/embedded/kernel/GPU/Rust/Ruby/PHP titles | b69171a | Same method: 1,109 → 1,053 (−56, 0 added); all 56 titles read (Arista, Nvidia, HPE, NXP, Applied Materials…; nearest calls Zscaler "Backend Dev - C/C++", GitLab "Backend Engineer (Ruby)"). Labelled `apply`/`maybe`: 0 rejected. Limit: "Embedded Finance" would be rejected (0 such titles; T69) | verified · claude · 2026-10-07 |
| T11 | Accept "Computer Scientist" titles | 56abafb | Same method: 1,053 → 1,060 (+7, all Adobe: Computer Scientist / 2 / II / Senior … Agentic AI); "Computer Scientist I (Frontend)" still rejected | verified · claude · 2026-10-07 |
| T17 | Measure the language-word exclusions (T62) | faa8bb0 (+ fix 55aa663) | `measure_prefilter.py --jobs <same fetch>` reproduces the blocked counts (python 33, java 93, golang 5, react 3 + reactjs 2 + angular 1, frontend 8). Bug found and fixed: `(age or 9999)` counted age 0 as unknown, so the 30-day column was low; as of the fetch date python 24 (not 21) and java 85 (not 75). T62 corrected; the new test failed before the fix | verified · claude · 2026-10-07 |
| T49 | Accenture added; Sony and Western Digital recorded | 5d3a26e | Live `fetch_workday("accenture", …)`: 2,000 jobs, 2,000 unique, 1,395 India, 471 pass (claimed 470), 37 posted ≤ 7 days (claimed 36), 0 "Not specified", 219 s. Sony Workday location facet: 67 entries, none India; its "India" search returns US/EU cities. Western Digital SmartRecruiters: 332 postings, 1 in India (an HR analyst). Found: "Location Negotiable" → T65 | verified · claude · 2026-10-07 |
| T03 | Stop scoring when the Gemini quota runs out | a186a99 (+ test 421b6e7) | 8 tests pass; removing the single-mode `break` fails the 50-job done-when test and the reset test. Removing the batch-mode check failed no test: added one (fails on that mutant). Live: with 3.5 out for the day and 3.1 answering, the breaker correctly did not trip, but each job wasted 2 requests + 5 s → T64 | verified · claude · 2026-10-07 |
| T04 | At most 400 jobs scored per run, newest first | 2694d8a | 6 tests pass; an oldest-first mutant fails 2. Live scan (scratch copy, cap 6): "110 job(s) are pending but at most 6 are scored per run … 104 stay 'discovered'"; funnel `queued 110 \| scored 6 \| left for next scan 104` | verified · claude · 2026-10-07 |
| T41 | Structured scoring, opt-in | ea14a3f | 19 tests pass. Saved facts of 82 jobs through the current `combine_subscores`: 82/82 equal the stored scores; vs the current prompt AUC 0.950 vs 0.948, precision at 60 61% vs 86%, `apply` at 70 13/15 vs 14/15, top scores 8 vs 3 distinct values. Default unchanged (`config.json` sets no `scoring_mode`). Note: ignores `gemini_temperature` (T69) | verified · claude · 2026-10-07 |
| T29 | Location, posted date and description in `jobs` | ad47c73 | 7 tests pass (its evidence said 8; the commit had 7). `init_db` on a copy of `data/jobs.db`: 30,367 rows before and after, statuses and score sum (5,692) equal, `integrity_check` ok, 0.19 s; later calls 0.2 ms. Live scan: the 6 scored rows carry location, date and 3,171–5,119-char descriptions; 39,118 skipped rows have a location and no description. The production DB is still unmigrated (T69 e) | verified · claude · 2026-10-07 |
| T35 | One funnel line at the end of every scan | f35f3b1 (+ 26f5493) | Live `./run_daily.sh --posted-within 1` from a scratch copy (`init` + `.env` with only the Gemini key, all 223 companies, cap 6): one line in `data/scan.log`: `Funnel: fetched 39235 \| India 19995 \| already scored 0 \| pre-filter rejected 37576 \| too old 1549 \| queued 110 \| scored 6 \| failed 0 \| left for next scan 104` (37,576 + 1,549 + 110 = 39,235); log ends "Scan finished with exit code 0"; 10.0 min | verified · claude · 2026-10-07 |
| T60 | Score variance measured; temperature 0 rejected | da2ed06 | `measure_score_variance.py --from-runs` on the saved runs (13 maybe + 7 apply, 5 runs each): temp 0.1 → 2/20 spread > 20, mean 6.0, flips 2 / 3 at 60 / 70; temp 0 → 4/20, mean 8.2, 4 / 4. Not re-derived: the resampled median-of-3 figures (not adopted) | verified · claude · 2026-10-07 |
| T14 | Whole resume in the draft prompt | 9d3f0f9 | The test passes; reverting to `resume[:2500]` makes it fail. The deprecated non-Gemini scorer still cuts the resume (T69) | verified · claude · 2026-10-07 |
| T40 | Draft from the stored description, no TinyFish | f43906f + 2e1b2c9 | Drafter and CLI tests pass. Real CLI in the scratch scan directory: `env -u TINYFISH_API_KEY python -m job_hunt draft 1` → exit 0; resume, cover letter and application_info written; ends "Review, edit, then submit manually"; the letter uses terms found only in the JD | verified · claude · 2026-10-07 |
| T42 | TinyFish careers-page path, OpenRouter, WhatsApp deleted; tests isolated | bce3983 | All 34 `job_hunt` modules import with `tinyfish`/`openai` blocked. The whole suite passes with no network (`unshare -rn`): 587 passed. The live scan and draft above ran with TINYFISH/OPENROUTER unset | verified · claude · 2026-10-07 |
| T50 | `init` ships the curated company list | e7a72f9 | `python -m job_hunt init` in an empty directory with TinyFish/OpenRouter unset: `companies.json` byte-identical to the repo's (223, 0 without `ats`); no tinyfish/openrouter key in `config.json`; the scan from there exited 0 with rows for 222 of 223 boards (NXP timed out at offset 0) | verified · claude · 2026-10-07 |
| T51 | google-genai is a core dependency | ea77ab5 (+ docs 91e5c1f) | Fresh venv from `requirements.txt` → google-genai 2.28.0; the Gemini client builds; `scanner` and `main` import. Found: `discovery`/`harvester` need `yaml` → T66; `docs/01-install.md` still said google-genai was optional → fixed | verified · claude · 2026-10-07 |
| T55 | Packaging metadata describes this fork | 4f10709 | `grep -rniE "tinyfish\|openrouter" pyproject.toml requirements.txt Dockerfile smithery.yaml` → nothing; pyproject, server.json, glama.json and smithery.yaml parse; upstream identity only in server.json/glama.json (intended). Not run: `docker build` (no Docker here) | verified · claude · 2026-10-07 |
| T52 | The non-Gemini scoring path stores its scores | 4061a76 | 7 tests pass; removing the `update_job_status` call fails 3. Not run: a real anthropic/claude_cli call | verified · claude · 2026-10-07 |
| T63 | anthropic provider `TypeError` on temperature | 6fbb1ab | 3 tests pass. `chat_with_llm({"llm_provider": "anthropic", …})` against 127.0.0.1:9 → `APIConnectionError`, not `TypeError` (anthropic SDK 1.11.0) | verified · claude · 2026-10-07 |
| T15 | The test suite no longer writes `scan.log` | 735568b | `stat -c %s scan.log` = 14,574,498 before and after every full pytest + ruff + mypy run this session | verified · claude · 2026-10-07 |
| T16 | Log to `data/autopilot.log` with rotation | 2350bdc | Log-path tests pass. Live scan directory: `data/autopilot.log` plus `autopilot.log.1` (4,999,889 bytes: it rotated during one scan), no `./scan.log`; the 2 adapter warnings appear on the console and in the file. One scan writes ~5.3 MB (T69 d) | verified · claude · 2026-10-07 |
| T18 | CHANGELOG dates match the commits | 3a51699 | `git blame --ignore-rev 3a51699` on every dated heading (38 now): 0 mismatches with the introducing commit's date; `git log` has no commit dated 2026-10-05 | verified · claude · 2026-10-07 |
| T36 | Drop the always-empty Stack/Region columns | 8edc8d9 | Exporter tests pass. Live `output/jobs_2026-10-07.csv`: 10 columns, none always empty | verified · claude · 2026-10-07 |
| T37 | LinkedIn people-search column | 3425abb | Live CSV link: `https://www.linkedin.com/search/results/people/?keywords=Accenture%20software%20engineer` (display name: `fetch_company_jobs` replaces the Workday tenant). Not verified: that LinkedIn shows people for it (needs Manish's login) | verified · claude · 2026-10-07 |
| T23 | No Workday detail call for title-rejected jobs | c112f6a | Saved per-tenant runs re-derived: detail calls 1,039 → 48 (991 → 0 on title-rejected jobs), tenants over 60 s 12 → 4, survivors 1,003 → 1,008 (only Danaher differs: HTTP 502 in the before run). Tests pass | verified · claude · 2026-10-07 |
| T43 | `harvest` refuses to overwrite; boards removed on evidence stay out | a7c2252 | Real `python -m job_hunt harvest` and `harvest --out companies.json` in a scratch directory holding `companies.json` → refusal, exit 2, SHA-256 unchanged. `EXCLUDED_BOARDS` = the 8 boards of CLAUDE.md's removal list, each slug present in `india.yml`, compared in lower case. 26 tests pass | verified · claude · 2026-10-07 |
| T25 | Eightfold adapter; UKG, Lam Research, Qualcomm, Morgan Stanley | 3d78991 | 69 tests pass (eightfold + discovery). Live scan: UKG 88, Lam Research 109, Morgan Stanley 115, Qualcomm 595 jobs; every posted date a valid ISO date (2025-04-07 … 2026-10-07), so `postedTs` is seconds as assumed | verified · claude · 2026-10-07 |
| — | Commit the working tree; tree clean | cd5df8e … 04521db | 355 tests pass, ruff and mypy clean (measured 2026-10-04) | pre-board |
| — | Location filter: Delhi / NCR / Kolkata and case-sensitive `, in` | cd5df8e | "Indianapolis, IN" still rejected (unit test) | pre-board |
| — | Full resume in the scoring prompts | cd5df8e | previously first 2,500 of ~4,000 chars | pre-board |
| — | Opt-in batch scoring (not the default) | cd5df8e | batch shifted scores 15.5 pts vs 1.0 pt run-to-run noise | pre-board |
| — | `companies.json` 28 → 215 boards, incl. Okta, Databricks, Stripe, SpotDraft, Plane, Twilio, BitGo | cd5df8e, 67c952d, 04521db | 215 entries, all 7 present (measured) | pre-board |
| — | Parallel company fetch with hard download deadlines | ba7d4b7 | 139 companies in 6.4 min vs ~45 min sequential | pre-board |
| — | Posted-within filter, Greenhouse `first_published`, CSV `Posted` column | b700235 | 100% parseable dates on 2,627 jobs | pre-board |
| — | `discover --recheck` health check | b700235 | 187 entries rechecked in 32 s | pre-board |
| — | ATS census (`discover --census`) | 31cb7c0 | 197 of 458 careers pages identified | pre-board |
| — | "Senior" / SDE / MTS titles allowed; Amazon and Oracle HCM adapters; SmartRecruiters pagination; Workday cap 100 → 500 | 04521db | pre-filter passes 204 → 1,271 | pre-board |

---

## Rejected / parked

Don't reopen without new evidence.

| Suggestion | Source | Why |
|---|---|---|
| Batch scoring as the default | Antigravity | Measured to shift scores by 15.5 pts vs 1.0 pt noise, inflating weak fits (CHANGELOG). It stays opt-in. |
| Config-driven pre-filter | Antigravity | CLAUDE.md: a hardcoded personal filter is fine for this fork. |
| HeadcountFilter resolver / cache sync | Antigravity | Headcount is display-only, not a filter, so it doesn't change results. |
| "Direct ATS jump" button in HeadcountFilter | Antigravity | Belongs in the HeadcountFilter repo, not here. |
| Thread pool for Workday detail calls | Gemini web | Superseded by parallel company fetch (ba7d4b7). T23 re-measures first. |
| Darwinbox adapter (T27) | claude, probe 2026-10-06 | No plain-HTTP JSON endpoint found. On valid tenants (magicpin, netmeds) every `/ms/candidateapi/*` path (`companyinfo`, `job?page=1`, `job/count`, `job/filters`, even `getturnstilecaptchasitekey`), GET and POST, with and without Origin/Referer/cookie, answers 500 "Error while getting tenant info"; mpl and demo are walled by Cloudflare 403; an invalid subdomain answers "Invalid subdomain" (so the tenant is recognised and the failure is in tenant resolution for non-browser requests). The app loads a Cloudflare Turnstile challenge. Five different attempts failed; reopen only with a browser-free way to obtain the tenant context, or a decision to use Playwright. |
| Playwright for custom portals; scraping Naukri/LinkedIn; multiple resume profiles | Gemini web, Antigravity | High cost and ban risk. Reopen only with a concrete plan and measured payoff. |
