# TASKS — JobNotify task board

The one shared board for everyone working on this repo: Manish, Claude Code,
Antigravity, or any other agent.

- **Told to "work from docs/tasks.md"?** Follow the [Working loop](#working-loop).
- **Told to "verify the tasks"?** Follow [Verifying](#verifying).

**Last re-evaluated:** 2026-10-04 against commit `04521db` (accuracy-first order added after the first real scan) (355 tests pass, ruff and
mypy clean — measured). File:line references are as of that commit; they drift, so
search for the named function if a line has moved.

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
by Antigravity.

Pick from this list top to bottom (T47, T30 and T24 are done: see the Done log; T48, T57 and T58 are in review). Status lives in the task's own row (below, or in its
P-table); this list only sets the order.

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

After this list: **T40, T50, T42** (Manish will not use TinyFish), then the rest.

### New accuracy tasks

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T48 | Scoring rubric and a golden set | review · claude · 4ca2e17 | claude | M | — |
| T57 | Amazon descriptions are a 202-character stub | review · claude · 0ed9567 | claude | XS | — |
| T58 | Fresher-level roles score 88–90 | review · claude · 9dd63f5 | claude | S | — |
| T59 | Confirm the golden-set labels | manish | — | S | T48 |
| T60 | Scores flip by ~50 points between runs on ambiguous postings | todo | — | S | — |
| T61 | Pre-filter: C++ / embedded / kernel / GPU / Rust / Ruby / PHP titles | review · claude · b69171a | claude | XS | — |
| T49 | Check big employers that report "no India jobs" | review · claude · 5d3a26e | claude | S | — |

**T48 · Scoring rubric and a golden set.** The prompt (`llm_utils.score_job_with_gemini`)
asks for "score 0-100" with no scale. First real scan, measured: 21 of 203 jobs tie at
exactly 90 and 38 are ≥ 80; a Nike role whose reason says it "specifically requires
C#/.NET Core, outside his primary Node.js" scored 75; same-title Hotstar, Mastercard and
Nike jobs differ by up to 75 points, but their reasons cite different job descriptions,
so that spread is content, not noise. Run-to-run noise was 3.3 points on 3 jobs (small
sample). Nobody has ever measured the score's precision. Do: (a) add anchors to the
prompt (for example primary-stack mismatch caps at 60; required years above the
candidate's by 3+ caps at 50; 90+ only when stack, seniority and location all fit);
(b) write `scripts/golden_set.csv` from the scan output (about 40 jobs: top, middle,
bottom) for Manish to label apply / maybe / no; (c) a script that scores the set and
prints agreement and the precision at MIN_SCORE. Manish's labelling takes about 20 minutes
(assumed); mark the task `blocked` until then.
*Done when:* the script prints agreement for the old and the new prompt on the same
labelled jobs. Keep the new prompt only if precision at MIN_SCORE doesn't drop and the
tie at the top shrinks.

**Result (2026-10-04, claude; commits 0448ea6, 4ca2e17).** Antigravity's version was sent back:
its labels came from the build script (old score ≥ 85 → `apply`) and its `--dry-run` scores
from a rule-based simulator, so "precision 59.1% → 86.7%" was circular; its builder also stored
one wrong Amazon description on 6 jobs. Claude replaced the instrument and fixed rubric rule 4:
- `scripts/golden_set.csv`: 75 real postings (59 `dev`, 16 `held-out`), Claude's labels with
  `label_source` and `label_reason` per row. **Single rater, not confirmed by Manish (T59);**
  the report prints a banner until every row says `manish`. Labels were read from the job text
  against the resume, but not strictly blind: Claude had seen first-scan scores earlier.
- `scripts/score_golden_set.py`: live mode scores each job with the rubric off and on; failed
  calls are `None`, never 0; prints precision, recall, AUC, ties and a bootstrap CI;
  `--from-scores` re-analyses saved scores.
- Rule 4 capped postings that accept a language on the resume (Hotstar "Java, Golang, or
  Python"; Toast "…or another OO language": 2 of 11 `apply` jobs lost). It now states its
  exceptions. The "avoid clustering at 90" text did nothing measurable and is gone.
Measured on all 75 (real Gemini, same text, rubric off → current): at MIN_SCORE 70 false
positives 7 → 4 and precision 77% → 85%; `apply` recall 13/13 both; `apply+maybe` recall
92% → 88%; **AUC 0.955 vs 0.956 (95% CI of the difference [-0.028, +0.029]), so ranking is
unchanged**; biggest tie among scores ≥ 85: 11 → 10. On the 16 held-out jobs (4 positives)
the revised prompt is not distinguishable from none. Conclusion: the rubric is a calibration
shift, not an accuracy gain. Two prompt versions (v1 by Antigravity, v2 by Claude) traded
recall against false positives without moving ranking, so further wording tweaks are the wrong
lever: ties and calibration need structured sub-scores (T41), a threshold choice (T05), and
the gaps in T57 and T58.
**For the verifier:** run `pytest tests/test_scoring_rubric.py`; run
`python scripts/score_golden_set.py --limit 3` (needs the Gemini key; 6 calls); then read the
CSV: do 5 `label_reason` lines match their descriptions?

**T57 · Amazon descriptions are a 202-character stub.** `adapters/amazon.py` builds the
description from `description_short`, which Amazon cuts mid-sentence at 202 characters, plus
the qualification bullets. The search API's `description` field holds the full text (2,796
characters on the first record; measured 2026-10-04). Amazon is the biggest source (245 of
1,271 pre-filter passes; 22 of the 74 jobs scoring ≥ 60 in the first scan), so its jobs were
scored without what the team builds or which stack it uses. Put `description` (through
`strip_html`) before the qualifications. After the fix, set the already `scored` Amazon rows
in `data/jobs.db` back to `discovered` so they are scored on the full text.
*Done when:* a unit test shows the full `description` in `JobPosting.description_text`; a live
`fetch_amazon` has median description length ≥ 2,500 characters (it was 1,244).

**T58 · Fresher-level roles score 88–90.** A held-out job, Hevo "Associate Software
Development Engineer" ("Freshers with experience in software development, ideally with
internships"), scored 90 with no rubric, 88 with the committed rubric and 90 with the
revised one (measured, one job). The rubric only caps roles that are too senior. Add a rule
for roles aimed at fewer than 2 years of experience, or a pre-filter pattern for
Associate / Graduate / Trainee / Fresher titles. Check on more than one example before
choosing the rule.
*Done when:* that job scores ≤ 50 and `score_golden_set.py` shows no new missed `apply` jobs
among the other 74.

**T59 · Confirm the golden-set labels (Manish).** The 75 labels are Claude's, with one line of
reasoning each in `label_reason`. Sort `scripts/golden_set.csv` by `label`, fix any you
disagree with, and set `label_source` to `manish` on rows you checked (about 15 minutes,
assumed). Then run `python scripts/score_golden_set.py` (live: about 150 Gemini calls, 14
minutes).
*Done when:* the report prints no "NOT CONFIRMED BY MANISH" banner.

**T60 · Scores flip by ~50 points between runs on ambiguous postings.** Measured 2026-10-06,
five runs of the same prompt on the same text: Amazon SDE II "SP Support" (a stray "3+ years
of Video Games Industry" requirement) scored [30, 30, 30, 85, 88] under the committed
rubric; ServiceNow's Armis integration role scored [90, 90, 35, 40, 90] under an earlier
rubric wording. Temperature is 0.1. The earlier "3.3 points of noise" holds only for clear
postings. So one run per job misplaces ambiguous jobs on either side of MIN_SCORE, and
comparisons of one or two jobs on the golden set mean nothing. Measure first: 5 runs on 20
jobs, report the spread per job. Then try, cheapest first: temperature 0; re-scoring only
results between 45 and 80 two more times and keeping the median (costs about 2 extra calls
for the minority of jobs in that band; count how many).
*Done when:* the harness (or a small script) shows the share of jobs whose 5-run spread
exceeds 20 points, before and after the change.

**T61 · Pre-filter: C++ / embedded / kernel / GPU / Rust / Ruby / PHP titles.** 56 of the
1,191 pre-filter survivors (4.7%) name one of these in the title (measured on the 34,416
jobs fetched 2026-10-06: C++ 17, embedded 15, GPU 8, kernel 4, firmware 4, Rust 3, Ruby 2,
FPGA/PHP/CUDA 1 each). Each costs a scoring call, and all the labelled examples
(HPE C++, Nvidia embedded, Graviton C++, Quadric LLVM) are `no`. Add them to the title
exclusions with unit tests; keep a negative control ("Software Engineer, Backend (Node.js)").
Same policy family as T17, which only measures.
*Done when:* those 56 titles no longer pass, and the labelled `apply`/`maybe` jobs in
`scripts/golden_set.csv` all still pass the pre-filter.

**T49 · Big employers that report "no India jobs".** `discover` rejected Accenture, Sony
and Western Digital because the first page of their Workday India search had no India
jobs; all three employ large India teams (assumed). Either the tenant or site is wrong, or
`searchText="India"` misses their location format. Check each by hand against the
company's real careers page, then fix the entry or the search.
*Done when:* each of the three is added with at least one India job, or this task records
why it can't be.

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
| T03 | Stop scoring when the Gemini daily quota runs out | doing · claude · 2026-10-06 | claude | S | — |
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
| T11 | Let Adobe "Computer Scientist" titles through | review · claude · 56abafb | claude | XS | — |
| T12 | Exclude CRM/platform "developer" roles | review · claude · 0660d1d | claude | S | — |
| T14 | Send the full resume to `draft` | todo | — | XS | — |
| T15 | Stop tests writing to the real `scan.log` | todo | — | S | — |
| T16 | Put the logs in `data/` with rotation | todo | — | S | T15 |
| T17 | Measure what the python/java/golang exclusions cost now | review · claude · faa8bb0 | claude | XS | — |
| T18 | Fix the CHANGELOG dates | todo | — | XS | — |

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

---

## P2 — Better input for the scorer

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T23 | Workday: check titles before the detail call (measure first) | todo | — | S | — |

**T23 · Workday title check before detail calls.** "N Locations" detail calls run for
every such job, before the title filter. The earlier review measured about 100 s each
for Nvidia and Salesforce on the old list. Parallel company fetch (ba7d4b7) may have
hidden that cost. Measure first, and only change the code if a tenant still takes
more than 60 s.
*Done when:* the per-tenant time is recorded before and after, with the same survivors.

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
| T50 | Remove TinyFish from the docs, `init` and `config.example.json` | todo | — | S | T40 |

**T50 · Remove TinyFish from the docs and setup.** Manish will not use TinyFish. SETUP.md
L27 still says "TinyFish (required)"; PRIVACY.md L27 and SECURITY.md L27 say page
fetching always uses it; `config.example.json` has `tinyfish_api_key`. Worse, the 140
companies that `autopilot init` copies (`job_hunt/data/companies.json`) are
careers-URL-only entries with no `ats` field (measured: 140 of 140), so a fresh `init`
has no company the scanner can fetch without TinyFish. Ship the curated list instead (it
is India-tilted; say so in SETUP.md).
*Done when:* in an empty directory `autopilot init` then `autopilot scan --limit 3`
fetches jobs with `TINYFISH_API_KEY` unset; `grep -rni tinyfish SETUP.md PRIVACY.md
SECURITY.md config.example.json docs/` returns only notes saying it was removed.

**T50 update (docs rewrite, 2026-10-04):** the docs half is done. README, SETUP.md, PRIVACY.md,
SECURITY.md and `docs/` now describe TinyFish as unused, needed only by `draft` until T40.
Still open: `autopilot init`'s company list, `config.example.json`, and the `grep` check
(which will keep finding the T40 notes until T40/T42 remove the code).

T43 context: re-running `harvest` re-adds boards that were removed on evidence (see
CLAUDE.md), and `discover` has become the main way to add companies.

---

## Inbox

New findings go here with the next free ID (next: **T63**), an evidence tag and the
file:line. Manish or the triaging agent moves each one into a priority table.

| ID | Finding | Evidence | Added by |
|---|---|---|---|
| T51 | `requirements.txt` has `google-genai` commented out, so an install from it scores nothing (every call fails "google-genai is not installed"). Add it, or delete `requirements.txt` in favour of the `gemini` extra | measured: `requirements.txt` L8–9; error text in `llm_utils._get_genai_client_and_types` | claude (docs rewrite) |
| T52 | Without a Gemini key, the legacy `score_jobs` path scores survivors but never writes the score to the DB, so the same jobs stay `discovered` and are re-scored every scan | inferred from `scanner.run_scan` (legacy `else` branch after the Gemini block, no `update_job_status`); not run | claude (docs rewrite) |
| T53 | Warnings from module loggers (`job_hunt.adapters.*`, `job_hunt.scorer`, …) never reach `scan.log`. Only the `autopilot` logger has the file handler (`log.py`), so e.g. "Greenhouse fetch failed for …" appears on the console only. Fold into T16 | inferred from `log.py`; `grep -c "fetch failed for" scan.log` → 0 (measured) | claude (docs rewrite) |
| T54 | `notifier.send_whatsapp` (TextMeBot) is dead code: only `tests/test_notifier.py` calls it. Remove it with the T42 cleanup | measured: `grep -rn send_whatsapp job_hunt tests` | claude (docs rewrite) |
| T55 | Packaging metadata is still upstream's: `pyproject.toml` URLs, description and `openrouter` keyword; `tinyfish` and `openai` are core dependencies; the `Dockerfile` sets `TINYFISH_API_KEY` / `OPENROUTER_API_KEY` and installs `.[mcp]` without `gemini`. `server.json`, `smithery.yaml` and `glama.json` describe the upstream registry listing | measured: read the files | claude (docs rewrite) |
| T56 | Before T25/T27: a previous Claude session recorded that Eightfold (PCSX endpoint → HTTP 403) and Darwinbox (needs a tenant session) have no easy public API (tried 2026-10-04/05). Check that record before re-probing | assumed: Claude memory, not re-checked, not in the repo | claude (docs rewrite) |
| T62 | **Decision for Manish (T17's result):** the language words in the title exclusion block, among India jobs that name a target role and have no other blocker: **python 33** (21 posted in the last 30 days; 21 look like backend/SDE/full-stack, e.g. JPMorgan "Software Engineer III - Python LLM Engineer", Plane "Software Engineer, Backend (Python)"), **java 93** (75), golang 5, react/angular 6, frontend 8. Seniority words (staff, lead, principal, manager, architect) block about 600 more, as intended. Allow "python" in titles? It would add about 33 scoring calls to a full scan (+3%), and your resume lists Python. Java and golang: say which. Each is a one-word change plus a test | measured on 34,416 jobs fetched 2026-10-06: `python scripts/measure_prefilter.py --jobs <saved fetch>` | claude |

---

## Review queue

The implementer adds a row when a task reaches `review`; the verifier removes it.

| ID | Commit(s) | Implementer | Evidence (command → result) |
|---|---|---|---|
| T49 | 5d3a26e | claude | Probed all three boards directly. **Accenture:** false negative, fixed and added (216 companies): list API has empty `locationsText`, city in `bulletFields[1]`; 2,000 India results in arbitrary order (341 posted in 7 days, only 41 in the first 500) so the Workday cap rose 500 → 2,000. `discover --add-file … --merge companies.json --no-recheck` → verified, 20/20 India on the first page; `git diff companies.json` = one new entry. Through the real adapter: 2,000 jobs in 264 s, 470 pass the pre-filter, 36 posted ≤ 7 days. **Sony:** correct rejection (Workday facets list 11 countries, none India; 94 India-text hits, 0 with an India location). **Western Digital:** SmartRecruiters board 331 postings, 1 in India; Workday site not found (guessed 63 tenant/dc/site combinations); left out. New tests failed before (location, cap, discovery); `pytest` all pass, ruff and mypy clean. Not done: scoring Accenturè's jobs; 418 of the 470 survivors are titled just "Custom Software Engineer", so the scorer must judge them from the description. |
| T17 | faa8bb0 | claude | Measurement only, no behaviour change. `python scripts/measure_prefilter.py --jobs <saved fetch of 34,416 jobs, 2026-10-06>` → 1,060 pass the pre-filter; India jobs blocked only by one word: python 33 (21 in 30 days), java 93 (75), golang 5, react 3 + reactjs 2 + angular 1, frontend 8. Numbers and the question for Manish posted as Inbox T62. `pytest` all pass; the script has a unit test on synthetic rows. |
| T11 | 56abafb | claude | `pytest tests/test_prefilter.py` → 5 new tests failed before, all pass after (accepts Computer Scientist / 2 / II / - II / Senior … Agentic AI; still rejects Frontend, Architect, C++, Java, Principal, Staff); `pytest` all pass, ruff and mypy clean. Real filter on the 34,416 jobs fetched 2026-10-06: Adobe Computer Scientist in India 1 → 8 of 14 pass. Not done: scoring those 7 newly passing jobs (needs a scan). |
| T61 | b69171a | claude | `pytest tests/test_prefilter.py` → 13 new tests failed before the words were added, all pass after; `pytest` all pass, ruff and mypy clean. Real filter on the 34,416 jobs fetched 2026-10-06: survivors 1,109 → 1,053, 0 titles with the new words left, no labelled apply/maybe job rejected. Whole-word controls ("Rustic", "Cpp-free") pass. Not done: a live scan. |
| T12 | 0660d1d | claude | `pytest tests/test_prefilter.py` → the 22 platform-title tests failed before the pattern, all pass after; `pytest` all pass, ruff and mypy clean. Real filter on the 34,416 jobs fetched 2026-10-06: survivors 1,191 → 1,109, 0 platform-word titles among them; all labelled apply/maybe jobs in `scripts/golden_set.csv` still pass. Negative controls (Node.js backend, ServiceNow own "Cybersecurity Integrations", "Sapient", "Dynamic Pricing", "Biometrics", company Salesforce/ServiceNow/SAP/Workday with a plain title) pass. Not done: a live scan. |
| T58 | 9dd63f5 | claude | `pytest tests/test_scoring_rubric.py` → the rule-7 and rule-2 tests failed before, pass after; `pytest` all pass, ruff and mypy clean. Live Gemini, 82 labelled jobs, rubric v2 (committed) vs v4 (this change), 0 failures: Hevo "Associate SDE" 90 → 50 and Hevo "SDE I" 90 → 50 (target ≤ 50 met, but only just); Graviton/Thermo/HPE junior roles ≤ 40; the 3 controls untouched (90, 90, 72). ServiceNow Armis role: 5 runs under the old rule 2 = [90, 90, 35, 40, 90], under the new = [90 ×5]. All 82: at MIN_SCORE 70 false positives 5 → 2, precision 83% → 92%, AUC 0.946 vs 0.948. **Done-when not fully met:** `apply` recall 15/15 → 14/15, because Amazon "SP Support" (g27) scored 30–45 under v4. It is bimodal under every prompt (the committed one gives [30, 30, 30, 85, 88]), so this is not shown to come from the change; see T60. Labels are single-rater (T59). |
| T57 | 0ed9567 | claude | `pytest tests/test_adapters_extra.py` → the new full-description test failed before the change, 9 passed after; `pytest` → all pass, ruff and mypy clean. Live `fetch_amazon` (2,295 India jobs, 246 pass the pre-filter): median description 1,244 → 3,871 chars, 0 raw `<br>`. DB: 23 scored Amazon rows reset to `discovered` and their 27 entries dropped from `state/job_history.json` (backup in the session scratchpad). **Not run:** a scan that re-scores them (needs Gemini quota; happens on the next scan). |
| T48 | 0448ea6, 4ca2e17 | claude (fixing antigravity's 847e3c2) | `pytest` → 404 passed, coverage 89.99%, ruff and mypy clean; 3 mutations of the new code/data (AUC ties, failed call = 0, one description copied onto 6 rows) each make a test fail, then restored. Live Gemini, 75 labelled jobs × rubric off / committed / revised, 0 failures, `score_golden_set.py --from-scores` → at MIN_SCORE 70 false positives 7 → 4, `apply` recall 13/13, AUC 0.955 vs 0.956 (CI includes 0). Script's own live mode run on 3 jobs (6 calls). **Not done:** labels are Claude's, not Manish's (T59); held-out set has 4 positives. |

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
