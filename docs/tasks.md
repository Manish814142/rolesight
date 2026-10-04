# TASKS — JobNotify task board

The one shared board for everyone working on this repo: Manish, Claude Code,
Antigravity, or any other agent.

- **Told to "work from docs/tasks.md"?** Follow the [Working loop](#working-loop).
- **Told to "verify the tasks"?** Follow [Verifying](#verifying).

**Last re-evaluated:** 2026-10-04 against commit `04521db` (355 tests pass, ruff and
mypy clean — measured). File:line references are as of that commit; they drift, so
search for the named function if a line has moved.

---

## Working loop

First read `CLAUDE.md` (project context) and this whole file. Then repeat:

1. **Pick.** First any task with status `changes` (a verifier sent it back). Otherwise
   take the first `todo` from the top (P0 before P1, lower ID first) whose *Needs* are
   all `review` or in the Done log. Skip `decision`, `manish` and `blocked`. Never
   make Manish's decisions for him.
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

## P0 — Before scheduling the daily run

Why this comes first: the expansion work raised volume about 6× (36,228 jobs fetched,
1,271 pre-filter passes, per CHANGELOG). But the production DB `data/jobs.db` has only
ever seen the old 28-board list: 15 `scored` and 816 `skipped` rows, all from 2026-10-03
(measured). A scheduled run today would try to score every pass, with no quota guard.

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T01 | Back up the repo to a private remote | manish | — | XS | — |
| T02 | Turn on the posted-date window by default | decision | — | XS | — |
| T03 | Stop scoring when the Gemini daily quota runs out | todo | — | S | — |
| T04 | Cap the jobs scored per run, newest first | todo | — | S | T03 |
| T05 | Keep one MIN_SCORE, in one place | decision | — | XS | — |
| T06 | Check that Telegram works | manish | — | XS | — |
| T07 | Schedule `run_daily.sh` with a systemd user timer | todo | — | S | T02, T03, T04, T05 |
| T08 | Remove or repoint `setup_cron.sh` | todo | — | XS | T07 |
| T09 | First full production run; record the funnel | todo | — | S | T02–T07 |

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

**T03 · Quota circuit breaker.** The scoring loop in `scanner.run_scan` (L555) calls
Gemini for every pending job and never stops early. Once the daily quota is gone, each
job still costs a retry per model at 5–15 s (`llm_utils._generate_with_fallback`,
L141–165). That wastes roughly 20–30 s per remaining job (inferred). Stop after K
consecutive quota errors (429 / ResourceExhausted on every model), e.g. K = 3, and
leave the rest `discovered` so the next run retries them.
*Done when:* a unit test with a stub client that always raises 429 makes at most about
K × (models × 2) calls for 50 jobs, and all 50 stay `discovered`.

**T04 · Per-run scoring cap, newest first.** Add `max_jobs_to_score_per_run`
(default ≈400). Per CLAUDE.md the free tier allows 500 requests per day per model; the
real quota is unverified. Sort pending jobs by `posted_at`, newest first, so the cap
keeps the freshest.
*Done when:* a unit test with 600 pending jobs scores exactly the 400 newest and leaves
the other 200 `discovered`.

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
| T10 | `draft N` opens the wrong job | todo | — | S | — |
| T11 | Let Adobe "Computer Scientist" titles through | todo | — | XS | — |
| T12 | Exclude CRM/platform "developer" roles | todo | — | S | — |
| T13 | Remove the 2,000-char description cap when scoring | review · claude · ef15c4c | claude | XS | T46 |
| T14 | Send the full resume to `draft` | todo | — | XS | — |
| T15 | Stop tests writing to the real `scan.log` | todo | — | S | — |
| T16 | Put the logs in `data/` with rotation | todo | — | S | T15 |
| T17 | Measure what the python/java/golang exclusions cost now | todo | — | XS | — |
| T18 | Fix the CHANGELOG dates | todo | — | XS | — |
| T46 | Decode HTML-escaped descriptions (Greenhouse) | review · claude · 95b2002 | claude | XS | — |

**T10 · `draft N` numbering.** The digest numbers jobs by score (`top_jobs`,
`scanner.py` L599), but `state/last_scan.json` is written in scan order (L609), and
`drafter.py` L25–31 counts down that file. The earlier review measured digest #4 =
Salesforce (75) while `draft 4` opened Adobe SDE-3 (20). Write `last_scan.json` in the
digest's order. T31 is the lasting fix.
*Done when:* a unit test shows `draft 1` resolves to the highest-scoring job.

**T11 · "Computer Scientist" titles.** On 2026-10-04, 16 of the 19 "Computer
Scientist" / MTS titles in the DB were `skipped` (measured). MTS is now included
(04521db), but `computer scientist` is not in `TITLE_INCLUDE_PATTERN`
(`prefilter.py`). Add it.
*Done when:* unit tests pass "Computer Scientist", "Computer Scientist 2" and
"Computer Scientist II", and still reject "Computer Scientist I (Frontend)".

**T12 · CRM/platform exclusions.** "developer" lets through Salesforce Developer,
MS Dynamics, ServiceNow and Workday Extend roles. The earlier review measured 4 such
passes on the 28-board list, scored 10–20. The 215 boards now include ServiceNow
(706 postings) and Salesforce, so expect more (inferred). Add specific title phrases to
the exclude list. Match on the title only, never the company field.
*Done when:* unit tests pass, and a `scan --limit` dry run has none of these titles
among its passes.

**T13 · Description cap.** `llm_utils.py` L226 and L280 cut job descriptions to
2,000 characters. Remove the cut. It should fit the 250k tokens/min limit at this volume
(assumed).
*Done when:* a unit test shows a 6,000-character description reaching the prompt intact.

**T14 · Full resume in `draft`.** `drafter.py` L114 still uses `resume[:2500]`. The
scorer was fixed in cd5df8e; the resume is about 4,000 characters.
*Done when:* a unit test shows the full resume in the draft prompt.

**T15 · Tests write to the real log.** One `pytest` run grew `./scan.log` by
36,359 bytes (measured), because `job_hunt/log.py` L28 hardcodes `Path("scan.log")`.
Make the path configurable (e.g. a `JOBNOTIFY_LOG` env var) and point it at `tmp_path`
in `conftest.py`.
*Done when:* `stat -c %s scan.log` prints the same number before and after `pytest`.

**T16 · Log location and rotation.** `./scan.log` is 2.2 MB and grows without limit
(plain `FileHandler`). `run_daily.sh` also writes a second log, `data/scan.log`. Move
the Python log into `data/`, give the two files clear names, and use
`RotatingFileHandler` (e.g. 5 MB × 3). Update `.gitignore` and the docs.
*Done when:* nothing grows in the repo root, and a unit test shows rotation at the
size limit.

**T17 · Re-measure the python/java/golang exclusions.** On the 28-board list they
cost 0 jobs; one Adobe "Computer Scientist - Java, Microservices" was blocked. Count
the India jobs on the 215-board list that are blocked *only* by
python/java/golang/react/angular. This is a measurement only: post the numbers in the
Inbox, and Manish decides.
*Done when:* the counts are posted, with the command used.

**T18 · CHANGELOG dates.** Several CHANGELOG entries are dated 2026-10-05, but
`git log` shows the commits were made on 2026-10-04 (measured). Correct the headings
and the in-text dates.
*Done when:* every dated entry matches its commit date in `git log`.

**T46 · Escaped HTML in descriptions.** `bs4` is not installed in `.venv`, so
`adapters/base.py` `strip_html` uses its regex fallback, which never decodes entities.
Greenhouse sends `content` entity-escaped (`&lt;div class=&quot;…`), so all 154
Greenhouse survivors reached Gemini as raw markup, cut at 2,000 chars (measured
2026-10-04). Decode with stdlib `html.unescape`, then strip tags; no new dependency.
Prerequisite for T13: removing the cap first would send up to 79,158 chars of markup.
*Done when:* a unit test turns escaped Greenhouse HTML into plain text, and no
Greenhouse survivor in a live fetch contains `&lt;` or `<div`.

---

## P2 — Better input for the scorer

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T19 | Add an "enrich survivors" step to the scanner | review · claude · 0fd640e | claude | S | — |
| T20 | Workday: fetch descriptions for single-location survivors | review · claude · ded2879 | claude | S | T19 |
| T21 | SmartRecruiters: fetch descriptions for survivors | doing · claude · 2026-10-04 | claude | S | T19 |
| T22 | Oracle HCM: fetch full descriptions for survivors | todo | — | S | T19 |
| T23 | Workday: check titles before the detail call (measure first) | todo | — | S | — |
| T24 | Penalise roles that need onsite work outside India | todo | — | S | — |

**T19 · Enrich step.** In `run_scan`, between the pre-filter and scoring, call an
optional per-adapter `enrich(job)` only for jobs that passed. It does nothing by default.
*Done when:* a unit test shows `enrich` called for survivors only.

**T20 · Workday descriptions.** `workday.py` L82 calls `_fetch_detail` only for
"N Locations" items. Single-location jobs reach Gemini as "No full description
provided." (`scorer.py` L68).
*Done when:* no Workday survivor in a dry run is scored without a description.

**T21 · SmartRecruiters descriptions.** `smartrecruiters.py` L74 sets
`description_text=""`. The Antigravity review suggested the detail endpoint
`GET https://api.smartrecruiters.com/v1/companies/{slug}/postings/{id}`. It is
unverified, so probe it first.
*Done when:* SmartRecruiters survivors have non-empty descriptions in a dry run.

**T22 · Oracle HCM descriptions.** `oracle_hcm.py` L74 stores only
`ShortDescriptionStr`. Find the requisition detail endpoint (unverified).
*Done when:* Oracle HCM survivors carry the full description.

**T23 · Workday title check before detail calls.** "N Locations" detail calls run for
every such job, before the title filter. The earlier review measured about 100 s each
for Nvidia and Salesforce on the old list. Parallel company fetch (ba7d4b7) may have
hidden that cost. Measure first, and only change the code if a tenant still takes
more than 60 s.
*Done when:* the per-tenant time is recorded before and after, with the same survivors.

**T24 · Onsite work outside India.** The earlier review measured a US-onsite role
scoring 75. "India anywhere in the location wins" is correct for multi-location
postings, so the check has to read the description. Add a hard rule to the scoring
prompt: a role that requires onsite presence or work authorisation outside India
scores ≤ 30.
*Done when:* a unit test confirms the rule is in the prompt, and a live re-score of
one such job comes back ≤ 30.

---

## P3 — Coverage

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T25 | Eightfold adapter (probe first) | todo | — | M | — |
| T26 | Phenom adapter (probe first) | todo | — | M | — |
| T27 | Darwinbox adapter (probe first) | todo | — | M | — |
| T28 | Monthly `discover --recheck` that only reports | todo | — | S | T07 |

**T25–T27 · New ATS platforms.** The census (31cb7c0) of 458 careers pages found
Eightfold and Phenom on 7% each and Darwinbox on 6%, while 52% were unidentified (per
CHANGELOG). Step 1: find a public JSON endpoint; if there is none, move the task to
Rejected with the evidence. Step 2: write the adapter, with tests on recorded fixtures
(no network).
*Done when:* `autopilot discover --add-file` accepts at least one company on that
platform, and a scan fetches its jobs.

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
| T29 | Store location, posted_at and description in `jobs` | todo | — | M | — |
| T30 | Dedupe by ATS job ID | todo | — | M | T29 |
| T31 | `draft` reads SQLite | todo | — | S | T29 |
| T32 | `export` reads SQLite | todo | — | S | T29 |
| T33 | first_seen / last_seen and closed-job detection | todo | — | M | T29 |
| T34 | Retire `last_scan.json`, `job_history.json`, `seen_jobs.json` | todo | — | S | T31, T32 |
| T35 | Put the full funnel in the end-of-scan log line | todo | — | XS | — |
| T36 | Fill or drop the always-empty CSV Stack/Region columns | todo | — | XS | — |

**T29 · Richer `jobs` table.** The schema in `db.py` has no location, posted_at or
description (measured), so a decision can't be audited or re-scored. Add the columns
with an idempotent `ALTER TABLE … ADD COLUMN` migration in `init_db`.
*Done when:* a test migrates an old-schema DB file without losing data, and new rows
carry the fields.

**T30 · Dedupe by ATS job ID.** The key is `canonical_hash(title, company, location)`
(`models.py` L26), so separate openings with the same title merge. The earlier review
measured 18 of 565 postings hidden this way (e.g. two Druva req IDs). The `global_id`
column already exists: first check that every adapter fills it with the ATS's own ID,
then key on (ats, global_id), falling back to the hash.
*Done when:* a test stores two req IDs with the same title as two rows, and existing
`scored` rows aren't re-scored after the migration.

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

**T35 · Funnel log line.** The final line (`scanner.py` L635) reports companies,
jobs found, top matches and minutes. Add fetched, India, passed, too old and scoring
failures.
*Done when:* one line in `data/scan.log` shows the whole funnel.

**T36 · Stack/Region columns.** The Gemini path writes `"stack": ""`
(`scanner.py` L580), and Region is empty too. Either add `stack` to the scoring JSON
schema or drop both columns.
*Done when:* no CSV column is always empty.

---

## P5 — Features

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T37 | LinkedIn people-search link column in the CSV | todo | — | XS | — |
| T38 | Application tracker: `autopilot mark <id> applied` | todo | — | M | T29 |
| T39 | One rolling `output/open_matches.csv` | todo | — | S | T32, T38 |
| T40 | Draft from the stored description (drop TinyFish) | todo | — | M | T29 |

**T37 · LinkedIn referral link** (from the Gemini web review). Add a column linking to
`https://www.linkedin.com/search/results/people/?keywords=<company>%20software%20engineer`,
URL-encoded.
*Done when:* a unit test covers the encoding, and the link opens correctly from the CSV.

**T38 · Application tracker.** `autopilot mark <id> applied|interview|rejected|offer`,
stored with the date.
*Done when:* the status is stored in the DB and shown by `export`.

**T39 · Open-matches file.** Each run rewrites `output/open_matches.csv`: every job
scored ≥ MIN_SCORE that isn't applied, isn't closed and is still inside the
posted-date window. The per-scan files stay.
*Done when:* the file is regenerated each run and excludes applied jobs.

**T40 · Draft without TinyFish.** `drafter.py` imports TinyFish (L6) and needs
`TINYFISH_API_KEY` to fetch the job description. Use the description stored by T29.
Keep the drafts-only rule.
*Done when:* `autopilot draft 1` works with `TINYFISH_API_KEY` unset.

---

## P6 — Later / cleanup

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T41 | Structured sub-scores (stack, seniority, location) | todo | — | M | — |
| T42 | Delete the legacy TinyFish careers-page and OpenRouter paths | todo | — | M | T40 |
| T43 | Make `harvest` safe (exclusions file) or deprecate it for `discover` | todo | — | S | — |
| T44 | Keyword gap analysis in `draft` | todo | — | M | T40 |
| T45 | Local dashboard or TUI | todo | — | L | T29 |

T43 context: re-running `harvest` re-adds boards that were removed on evidence (see
CLAUDE.md), and `discover` has become the main way to add companies.

---

## Inbox

New findings go here with the next free ID (next: **T47**), an evidence tag and the
file:line. Manish or the triaging agent moves each one into a priority table.

| ID | Finding | Evidence | Added by |
|---|---|---|---|
| — | — | — | — |

---

## Review queue

The implementer adds a row when a task reaches `review`; the verifier removes it.

| ID | Commit(s) | Implementer | Evidence (command → result) |
|---|---|---|---|
| T46 | 95b2002 | claude | `pytest tests/test_strip_html.py` → 6 passed (4 failed before the fix); `pytest` → 361 passed; ruff, mypy clean. Live: `_prefetch_jobs` on the 74 Greenhouse boards → 154 survivors, 0 containing `&lt;`, `<div` or `&quot;` (was 154/154). |
| T13 | ef15c4c | claude | `pytest tests/test_gemini_provider.py` → 3 new tests failed before the change (6,000-char description cut in single and batch prompts; no bound), pass after; `pytest` → 364 passed, coverage 89.16%; ruff, mypy clean. Deviation: a 20,000-char runaway bound kept (measured clean max 10,180). Live: 16 real Gemini calls with 1,001–7,638-char descriptions all returned valid scores (A/B in CHANGELOG). |
| T19 | 0fd640e | claude | `pytest tests/test_enrich.py` → 4 failed before (no `ENRICHERS` / `scanner.enrich_job`), 4 passed after: survivor enriched; pre-filter reject, too-old and already-scored jobs not; scorer receives the enriched text. `pytest` → 368 passed, coverage 89.24%; ruff, mypy clean. Live run deferred to T20–T22 (registry empty here). conftest stubs `scanner.enrich_job` for every test. |
| T20 | ded2879 | claude | `pytest tests/test_enrich.py` → 4 Workday tests failed before (no `workday.fetch_description`, not registered), pass after; `pytest` → 372 passed; ruff, mypy clean. Live: `scanner._enrich_jobs` (real network) on the 643 Workday survivors saved from a real fetch the same day → empty descriptions 591 → 0, incl. 0 of 153 posted ≤7 days; 109 s. Script: scratchpad `enrich_live.py`. |

---

## Done log

The rows marked "pre-board" were finished before this board existed and have not gone
through [Verifying](#verifying). Their commit mapping comes from the commit messages
and CHANGELOG (inferred), and their numbers from CHANGELOG unless marked measured.

| ID | What | Commit | Evidence | Verified |
|---|---|---|---|---|
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
| Playwright for custom portals; scraping Naukri/LinkedIn; multiple resume profiles | Gemini web, Antigravity | High cost and ban risk. Reopen only with a concrete plan and measured payoff. |
