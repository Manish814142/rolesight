# TASKS — JobNotify task board

The one shared board for everyone working on this repo: Manish, Claude Code,
Antigravity, or any other agent.

- **Told to "work from docs/tasks.md"?** Follow the [Working loop](#working-loop).
- **Told to "verify the tasks"?** Follow [Verifying](#verifying).

**Last re-evaluated:** 2026-10-07 (afternoon, after 3.5's quota reset) against commit `3bc1c13`: all 30 tasks in the review queue verified by a fresh
Claude session at Manish's request (instead of Antigravity); T64–T67, T70, T72, T73 added and implemented; T60 re-checked on 3.5 and verified (604 tests pass,
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

**From 2026-10-07 (Manish):** a separate Claude agent works this board: it implements `todo` tasks and verifies
what is in the Review queue (T64–T67, T70, T60's re-check), **without asking Manish anything**; it writes its
questions into the tasks and the Inbox for the end. After that, the reviewing Claude session reviews the agent's
work and fixes what it finds. The open decisions (T02, T05, T62, T26) are not urgent: Manish answers them last.
Gemini quota: about 500 calls per model per day; a normal day uses 200–300. If `gemini-3.5-flash-lite` is out
for the day, live checks may use `gemini-3.1-flash-lite`, but a task whose verdict depends on 3.5's scores stays
`review` with the remark "3.5 quota reached on <date>; verify on 3.5" instead of being marked done.

**Every task in this list is done and verified (Done log, 2026-10-07).** What moved the score since: T73 (rubric v7,
Manish's apply rule: false positives 2 → 0 at 70 on 82 labelled jobs, `apply` 14/14) and T72 (Amazon "Software Dev
Engineer" titles reach Gemini) — both verified (T72 2026-10-08, T73 2026-10-10). What still would: the decisions T62 (python titles) and T74 (AI / Forward Deployed
Engineer titles), each with measured evidence, and Manish's labels (T59).

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
| T74 | Pre-filter: let "AI Engineer" / "Forward Deployed Engineer" titles through? | decision | — | XS | — |

T48, T57, T58, T60, T61 and T49 were verified 2026-10-07, T72 and T70 on 2026-10-08 (Done log).

**T59 · Confirm the golden-set labels (Manish).** The 82 labels are Claude's, with one line of
reasoning each in `label_reason`. Sort `scripts/golden_set.csv` by `label`, fix any you
disagree with, and set `label_source` to `manish` on rows you checked (about 15 minutes,
assumed). Then run `python scripts/score_golden_set.py` (live: about 164 Gemini calls, ~15
minutes).
*Done when:* the report prints no "NOT CONFIRMED BY MANISH" banner.
**g27 answered by Manish (2026-10-07):** he skips a posting that *requires* a skill or domain he lacks (here
3+ years in the video-games industry), so g27 is now `no` with `label_source` `manish`. His rule for the other
rows: `apply` only when the required stack and experience match his and the day-to-day work does too. With g27
relabelled, the current prompt (3.5, saved T58 scores) finds 14/14 `apply` jobs at MIN_SCORE 60 and 70.
**g1 (from T73's review, 2026-10-08):** Expedia names Kotlin/Java/C# only in the responsibilities ("using languages such as");
its qualifications ask for any language. Kept `apply` (rubric v7 scores it 75–85). If you would skip it, relabel g1 `no`.

**T70 · Which Gemini model scores better?** (Manish's question, 2026-10-07: is 3.1-flash-lite's output the
same as 3.5-flash-lite's, so he can spend quota wisely?) `score_golden_set.py --model M` scores with one model
and no fallback, and `--from-scores a.json b.json …` adds a job-by-job agreement section (mean |difference|,
share within 10 points, pass/fail changes at each MIN_SCORE). Two runs of one model show its run-to-run noise;
the gap between models only counts beyond that. Each run is 82 calls with `--arms current`.
*Done when:* two 3.1 runs and two 3.5 runs of the current prompt on the 82 jobs are compared, and the
recommendation (which model to make primary) is written here.
**Result (2026-10-07, two same-day runs per model, committed rubric, 82 jobs; measured):**
- *Ranking:* AUC 3.5 0.972 / 0.973, 3.1 0.959 / 0.954 (95% CIs of the differences include 0).
- *Noise:* a model's two runs differ by 3.2 points (3.5; 3–4 pass/fail flips, all `maybe`/`no` jobs) and
  0.7 (3.1; none). Yesterday's 3.5 run is within 3.5's own noise of today's (2.5–3.3).
- *Between models:* 8.0–8.4 points; 11–14 jobs change pass/fail. 3.1 scores `no` jobs +7.5 higher,
  `apply` jobs +0.7.
- *At MIN_SCORE 70:* both 14/14 `apply`; false positives 3.5 **2**, 3.1 **10** (precision 92% vs 71%).
  At 80+ the two pass the same jobs.
- *Speed:* both 1.8 s median per call.
**Recommendation:** keep `gemini-3.5-flash-lite` primary; 3.1 is a fallback and fine for functional checks.
The code is model-independent; calibration is not, so re-run `score_golden_set.py --arms current --model M`
twice (164 calls) when the model changes. Mixed-model scans need T71.

**T71 · Record which Gemini model scored each job.** Measured in T70: 3.1-flash-lite scores weak fits ~7 points
higher than 3.5-flash-lite, and a scan silently falls back to 3.1 when 3.5 fails or is out of quota (T64), so one
CSV can mix two calibrations with nothing to show it. Store the answering model with each score (a `jobs`
column, the scorer's result, the CSV when more than one model scored, and the funnel line, e.g.
`scored 6 (gemini-3.5-flash-lite 4, gemini-3.1-flash-lite 2)`). No prompt or score change.
*Done when:* a test with a stub client whose first model fails shows the fallback model stored on that row and
in the CSV; a live scan's funnel line names the model(s).
**Implemented (claude-b, 2026-10-08, bdcd128).** `jobs.score_model` (added by `init_db`; NULL = unknown: rows scored
before T71 and the deprecated providers, whose funnel count is labelled with the provider name), `model` in the scorer
results and the JSON state files, the funnel line, and a CSV **Model** column. **Choice made (Manish's to confirm):** the
column is written when the jobs mix models **or** any job was scored by a model other than the default primary
`gemini-3.5-flash-lite`. The task said "when more than one model scored"; that rule alone would hide a run in which 3.5
was out all day and 3.1 scored everything, which is the calibration T70 warns about. A normal day keeps the 10
columns. **Question for Manish:** keep this, or always show the Model column?

**T74 · Decision for Manish: "AI Engineer" / "Forward Deployed Engineer" titles.** They match no include word,
so the pre-filter drops them before Gemini. Measured 2026-10-07: 68 such India titles ("Gen AI Engineer",
"Applied AI Engineer", "AI Engineer", "Forward Deployed Engineer"…). Scored with the full description: 24 got
≥ 80 on 3.1; re-scored on 3.5 with the T73 rubric, **21 of those 24 score ≥ 70** (13 ≥ 80): EXL Gen AI Engineer
(90, 85, 85), Razorpay FDE (90), OpenAI Applied AI Engineer (88), Adobe Conversation AI Engineer, Target Sr AI
Engineer, Mastercard AI Engineer, HPE Storage AI Engineer (85), Notion FDE India (75). The rest are what Gemini
should reject (HighRadius/Outreach FDE = sales/consulting, 30–35; Deutsche Bank/Databricks 6+ years, 45). Your
profile lists GenAI automation; `seeking` says Backend / Full Stack. Cost: ~68 more scoring calls on a full scan
(+4%), a few a day with `--posted-within 7`. **Implementation if yes:** add
`(gen\s*ai|applied\s+ai|ai|llm)\s+engineer|forward[\s-]deployed\s+engineer` to `TITLE_INCLUDE_PATTERN` with tests
(seniority/lead/staff exclusions still apply).
*Done when:* Manish says yes or no; if yes, the 68 titles pass and no labelled `apply`/`maybe` job is rejected.

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

T03 and T04 were verified 2026-10-07, T64 on 2026-10-08 (Done log).

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

T11, T12, T14, T15, T16, T17 and T18 were verified 2026-10-07, T66 and T67 on 2026-10-08 (Done log); nothing open.

---

## P2 — Better input for the scorer

T23 was verified 2026-10-07 (Done log); nothing open.

---

## P3 — Coverage

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T26 | Phenom adapter (probe first) | decision | — | M | — |
| T28 | Monthly `discover --recheck` that only reports | todo | — | S | T07 |

T65 was verified 2026-10-08 (Done log).

**T25–T27 · New ATS platforms.** (A previous Claude session recorded that Eightfold's PCSX endpoint returns HTTP 403 and Darwinbox needs a tenant session, tried 2026-10-04/05; that note is from memory, not in the repo, so re-check before relying on it.) The census (31cb7c0) of 458 careers pages found
Eightfold and Phenom on 7% each and Darwinbox on 6%, while 52% were unidentified (per
CHANGELOG). Step 1: find a public JSON endpoint; if there is none, move the task to
Rejected with the evidence. Step 2: write the adapter, with tests on recorded fixtures
(no network).
*Done when:* `autopilot discover --add-file` accepts at least one company on that
platform, and a scan fetches its jobs.

**T25–T27 result (claude, 2026-10-06).** *T25 Eightfold:* done, verified 2026-10-07. *T26 Phenom:* the endpoint is public (`POST {host}/widgets`, `selected_fields.country=["India"]`, `size` up to 100 honoured, full description in the job page's JSON-LD), **but Phenom mostly fronts Workday**: on Cisco, DuPont, Fiserv, HPE, Philips and WBD every sampled job's `applyUrl` is a Workday tenant. I added the three missing Workday tenants instead (Cisco, DuPont, Fiserv) through `discover`, no new adapter. The only Phenom-native census board with India jobs is BCG (91 India jobs, **2** pass the pre-filter). **Decision for Manish:** is a native Phenom adapter (~150 lines, a JSON-LD description scrape) worth 2 BCG jobs, or park it until another Phenom-native company turns up? *T27 Darwinbox:* rejected, see the Rejected table.

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
| T31 | `draft` reads SQLite | review · claude-b · 4e337d7 | claude-b | S | T29 |
| T32 | `export` reads SQLite | review · claude-b · ffea468 | claude-b | S | T29 |
| T33 | first_seen / last_seen and closed-job detection | review · claude-b · 239b122 | claude-b | M | T29 |
| T34 | Retire `last_scan.json`, `job_history.json`, `seen_jobs.json` | review · claude-b · fb25e31 | claude-b | S | T31, T32 |

T29, T35 and T36 were verified 2026-10-07 (Done log).

**T31 · `draft` reads SQLite.** Resolve `draft N` / `draft <id>` from the DB rather than
`state/last_scan.json`. This supersedes T10.
*Done when:* unit tests cover both forms; `last_scan.json` is no longer read.
**Implemented (claude-b, 2026-10-08, 4e337d7).** New table `scans` (one row per run, `started_at` / `finished_at`);
`draft N` = job N of the jobs scored during the last *finished* scan, by score then scoring order (the CSV's order),
via `db.last_scan_jobs`; `draft URL` unchanged; `mark N` (T38) follows because it uses the same resolver. **Choice made
(keeps today's meaning):** N still refers to the last scan, not to a DB id. Side effect: until the first scan after
this change, `draft N` says "No scan results found" (`draft URL` works). **Question for Manish:** keep "N of the last
scan", or would a stable job number (e.g. the DB id shown in the CSV) suit you better when working from older CSVs?

**T32 · `export` reads SQLite.** `export` reads `state/job_history.json` /
`last_scan.json` (`main.py` L194–205) and ignores DB status.
*Done when:* `autopilot export --min 70 --days 7` matches the equivalent SQL query.
**Implemented (claude-b, 2026-10-08, ffea468).** `export` = the last finished scan (T31); `--days N` = every
`scored`/`notified` job with `scored_at` on or after that UTC date, best first. **Choices made:** (1) `--days` output
is sorted best-first across scans (the JSON version kept scan order); (2) Worth Applying uses `load_config`'s
`min_score`, read only when `config.json` exists (blank otherwise); (3) structured-mode sub-score columns are no
longer exported (they were never stored in the DB). **Found on a copy of the production data:** the old
`job_history.json` gives 45 jobs for `--min 70 --days 7`, the DB 33; 40 history URLs (15 ≥ 70) are not in the DB at
all and 11 have other scores (from before the DB was cleared on 2026-10-04). T34's import decides about them.

**T33 · Closed jobs.** Record first_seen / last_seen. Mark a job `closed` once its
board stops returning it for N scans in a row.
*Done when:* unit tests cover the transitions.
**Implemented (claude-b, 2026-10-10, 239b122).** Columns `first_seen`, `last_seen`, `missed_scans`, `closed_at`;
`closed_at` is set after `closed_after_missed_scans` (default 3) scans in which the job's board answered without it,
and cleared when it returns. **Choices made (Manish's to confirm):** (1) "closed" is a flag column, not a new
`status`, so scores and the scan lifecycle stay as they are; (2) N = 3; (3) a board counts only when its fetch
succeeded, returned jobs and did not stop early (the reviewer found before the commit that page failures, time
budgets and job caps return subsets; measured: Accenture at its 2,000 cap kept 1,966 of 2,000 URLs over two days,
and 2 of 15 sampled "gone" ones were still live), so a board always at its cap (Accenture, Bosch, EXL, Kotak) never
closes a job. **Question for Manish:** is 3 missed scans right for you (with daily scans: a job closes ~3 days after
its board drops it)?

**T34 · Retire the JSON state files.** Once T31 and T32 are done, remove their writers
and readers. Add a one-time import into SQLite if any history would otherwise be lost.
*Done when:* `grep -rn "last_scan.json\|job_history.json\|seen_jobs.json" job_hunt`
returns nothing.
**Implemented (claude-b, 2026-10-08, fb25e31).** The scanner's three writers/readers and the MCP summary's reader are
gone (`tools.tool_scan` counts from the DB). The one-time import is `scripts/import_json_history.py` (outside
`job_hunt/`, so the done-when grep stays empty), a dry run unless `--apply`; it imports only URLs the DB does not
know. **Not run on the production data** (it writes `data/jobs.db`). Measured on copies: 45 jobs would be imported,
20 of them ≥ 70, scored on 2026-10-04 with that day's (pre-rubric) prompt; `export --min 70 --days 7` 33 → 53.
**Question for Manish:** import them (`python scripts/import_json_history.py --apply`), or leave them out because
their scores predate the rubric (the DB was cleared on purpose on 2026-10-04)? Either way the old `state/*.json`
files can be deleted afterwards; `init` still creates an empty `state/` directory (left alone).

---

## P5 — Features

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T39 | One rolling `output/open_matches.csv` | review · claude-b · 1b206a7 | claude-b | S | T32, T38 |

T37 and T40 were verified 2026-10-07 (Done log).

**T38 · Application tracker.** `autopilot mark <id> applied|interview|rejected|offer`,
stored with the date.
*Done when:* the status is stored in the DB and shown by `export`.
**Implemented (claude-b, 2026-10-08, 5762c6a).** `autopilot mark N | URL applied|interview|rejected|offer` (`none`
clears) → `jobs.application_status` + `application_date` (local date), separate from the scanner's `status`;
`export` shows an **Application** column when some exported job is marked. **Choices made (Manish's to confirm):**
(1) `<id>` is `N`/`#N` = job N of the *last* scan, resolved by `draft`'s own code (so T31 changes both together), or
a job URL; a row of an older CSV needs its URL. (2) Only the latest status is kept: marking `interview` replaces
`applied` and its date. **Questions for Manish:** is `N` of the last scan + URL enough, or do you want a stable id
column in the CSV? Do you want the history (e.g. keep the applied date once it becomes `interview`)?

**T39 · Open-matches file.** Each run rewrites `output/open_matches.csv`: every job
scored ≥ MIN_SCORE that isn't applied, isn't closed and is still inside the
posted-date window. The per-scan files stay.
*Done when:* the file is regenerated each run and excludes applied jobs.
**Implemented (claude-b, 2026-10-08, 1b206a7).** Written at the end of every scan (also when nothing was scored),
atomically. **Choices made (Manish's to confirm):** (1) "applied" = any `autopilot mark` status (applied, interview,
rejected, offer); (2) the window is the *run's* window, so a one-off `scan --posted-within 1` writes a 1-day file
until the next normal run (T02 will set the default); (3) closed jobs are not excluded until T33 records them.
**Question for Manish:** should the file use one fixed window (e.g. 30 days) instead of the run's?

---

## P6 — Later / cleanup

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T44 | Keyword gap analysis in `draft` | review · claude-b · 33ff041 | claude-b | M | T40 |
| T45 | Local dashboard or TUI | todo | — | L | T29 |

T41, T42, T43, T50, T51, T52, T55 and T63 were verified 2026-10-07 (Done log).

**T44 · Keyword gap analysis in `draft`.** (The board had only the title; this definition is claude-b's, 2026-10-10,
for Manish to confirm.) When `draft` writes its files, also list the technologies the posting names that the resume
does not, so Manish sees at a glance what he would be asked for that he lacks (his apply rule: skip postings that
*require* what he does not have). Deterministic, no extra LLM call: a fixed vocabulary of tech terms with aliases.
*Done when:* unit tests cover the matching (aliases, C#/C++/.NET, Java vs JavaScript, word boundaries); `draft`
writes `keyword_gaps.txt` next to the cover letter and prints the missing terms; a real `autopilot draft N` does it.
**Implemented (claude-b, 2026-10-10, 33ff041).** `job_hunt/keywords.py` (72 terms); `draft` writes the file before its
LLM calls. **Questions for Manish:** is a vocabulary list (no LLM, no cost, predictable, but blind to terms it lacks
and to "required vs example") what you want, or should the gap list come from the LLM's "key requirements" instead?
Which terms would you add?

---

## Inbox

New findings go here with the next free ID (next: **T77**), an evidence tag and the
file:line. Manish or the triaging agent moves each one into a priority table.

| ID | Finding | Evidence | Added by |
|---|---|---|---|
| T62 | **Decision for Manish (T17's result):** the language words in the title exclusion block, among India jobs that name a target role and have no other blocker: **python 33** (24 posted in the last 30 days, corrected 2026-10-07 from 21; 21 look like backend/SDE/full-stack, e.g. JPMorgan "Software Engineer III - Python LLM Engineer", Plane "Software Engineer, Backend (Python)"), **java 93** (85, corrected from 75), golang 5, react/angular 6, frontend 8. Seniority words (staff, lead, principal, manager, architect) block about 600 more, as intended. Allow "python" in titles? It would add about 33 scoring calls to a full scan (+3%), and your resume lists Python. Java and golang: say which. Each is a one-word change plus a test. **Scored 2026-10-07** (today's fetch, full descriptions, 3.1, old rubric): of the 32 python-only-blocked India jobs, **9 score ≥ 80** (JPMorgan "Python Backend Developer with AWS and SQL" 95, Plane "Software Engineer, Backend (Python)" 90, Anaplan "Backend Python Engineer" 90, JPMorgan "SE III - Python LLM Engineer" 90…), 17 ≥ 70 (3.1 overstates 70–79) | measured on 34,416 jobs fetched 2026-10-06: `python scripts/measure_prefilter.py --jobs <saved fetch>`; the 30-day column was undercounted (jobs posted that day counted as old) until 55aa663 | claude |
| T75 | **Every per-job lookup scans the whole `jobs` table.** `get_job` / `has_job` / `update_job_status` / `update_job_details` use `WHERE global_id = ?`, which cannot use the partial unique index `idx_jobs_ats_global_id` (its condition `global_id IS NOT NULL AND global_id != ''` is not implied): EXPLAIN QUERY PLAN → `SCAN jobs`. 2.7 ms per `get_job` on a copy of the production DB (30,367 rows); a scan calls it once per fetched job (~40k), so ~110 s per scan (inferred), growing with the table. Fix as in T33's `record_sightings`: add `ats = ?` and the index condition (`SEARCH … USING INDEX`), or a plain index on `global_id` | measured (EXPLAIN, timing); cost per scan inferred | claude-b |
| T76 | **Workday maintenance silently empties a scan's Workday boards.** 2026-10-10 12:19 IST: 77 of 79 Workday tenants answered the jobs POST with HTTP 303 → `community.workday.com/maintenance-page` (Accenture's wd103 answered 200). The adapter follows the redirect, fails to parse the HTML ("Expecting value: line 1 column 1") and logs one warning per tenant; that scan gets no Workday jobs (they are fetched next time, and T33 counts no misses for them). Possible: detect the redirect and log one clear line, or retry later in the run | measured (curl, full fetch) | claude-b |
| T69 | Low-priority notes from the 2026-10-07 review, no action proposed: (a) structured scoring (T41) hard-codes temperature 0.1 and ignores `gemini_temperature` (T60) — `llm_utils.score_job_structured_with_gemini`; (b) the deprecated non-Gemini scorer still cuts the resume at 2,500 and each JD at 1,500 characters — `scanner.score_batch`; (c) the T61 word `embedded` would also reject "Backend Engineer – Embedded Finance" (0 such titles in 34,416); (d) one full scan writes ~5.3 MB of DEBUG log, so T16's 5 MB × 3 rotation keeps about the last 3 scans; (f) structured scoring (T41, opt-in) still caps a stack mismatch at 60 in code (`combine_subscores`), while the T73 rubric uses 50; (g) generic "Senior Engineer" / "Engineer II/III" titles (~250 India jobs on 2026-10-06; Micron, Microchip, Thermo Fisher, Target India, NI, Anaplan, CrowdStrike, MongoDB) match no include word — mostly hardware, but Target/Anaplan/MongoDB use them for software; not measured further; (e) the production `data/jobs.db` still has the pre-T29 schema and `user_version` 0: its next scan runs T29's columns and T30's one-time Workday repair (checked on a copy: 30,367 rows kept, 0.19 s) | measured (a, b by reading the code; c, d, e by running it) | claude |

---

## Review queue

The implementer adds a row when a task reaches `review`; the verifier removes it.

| ID | Commit(s) | Implementer | Evidence (command → result) |
|---|---|---|---|
| T44 | 33ff041 | claude-b | `pytest tests/test_keywords.py` → collection error before (no module), 18 passed after (aliases, C#/.NET/C++, Java vs JavaScript, English words that are not technologies, gap order, `draft` writes the file and logs the missing terms). Mutants: Go matched case-insensitively → 1 failed; Java matched inside JavaScript → 2 failed; draft writes no file → 1 failed. Precision on real text: the 82 golden-set postings, contexts of every ambiguous term (Go, Spring, SQL, REST, React, Rust, SAP, RAG, ML, C#, .NET, C++…) read: all the technology; one recall miss seen (lowercase "springboot"). Real CLI (scratch dir, 3.1 wrapper, 6 calls): `autopilot draft 1` (Amazon 10571791, a posting that names no vocabulary term — checked: JD terms [] , resume 26) → "nothing from the vocabulary"; `autopilot draft <Mastercard R-292799>` → "In the posting, not in your resume (7): Spring / Spring Boot, SQS, AWS Lambda, Kubernetes, Terraform, GitHub Actions, Machine learning", in both 13; both end "Review, edit, then submit manually". Gates: 685 passed, coverage 92.58%, no-network 685 passed, ruff and mypy clean |
| T33 | 239b122 | claude-b | `pytest tests/test_closed_jobs.py` → before the code 7 failed (transition tests), after the review fix 16 passed (adds: Workday page failure after page 1, Workday cap, Workday budget, a complete paged fetch, the cap of Amazon/SmartRecruiters/Oracle HCM/Eightfold, and a partial board through `run_scan` that counts no misses). Mutants: incomplete boards still counted → 1 failed; seen jobs also missed (`<=`) → 7 failed; Workday cap not flagged → 1 failed. Real `_prefetch_jobs` on all 223 boards (2026-10-10 12:19 IST, 30,631 jobs, 304 s): flagged 4 at cap (Accenture, Bosch, EXL, Kotak 2,000 each) + 77 Workday tenants whose first page failed (Workday maintenance redirect; empty, so no misses either). Reviewer, live: Accenture 10-08 vs 10-10 share 1,966 of 2,000 / 1,996 URLs; 2 of 15 sampled missing ones still live. `record_sightings` on a copy of the production DB with the 39,873-job fetch of 2026-10-08: 1.9–2.0 s per scan (a first version, before an index fix, ran > 5 min: `SCAN jobs`); 3 such scans would close 3,759 of the 2026-10-04 rows (23 scored; measured before the partial-fetch rule, so Accenture's would now stay open). Real CLI, scratch dir, `closed_after_missed_scans: 1` (before the partial-fetch fix): "2 job(s) marked closed", both Amazon, both URLs HTTP 404 on amazon.jobs. Gates: 667 passed, coverage 92.54%, no-network 667 passed, ruff and mypy clean |
| T39 | 1b206a7 | claude-b | `pytest tests/test_open_matches.py` → 5 failed before, 5 passed after. Mutants: applied jobs not excluded → 4 failed; Workday relative age not advanced → 2 failed; file written only when something was scored → 3 failed. Real CLI in the scratch scan directory (3.1 wrapper, cap 1, `--posted-within 1`): log `Open matches (score >= 60, not applied, posted within 1 day(s)): 4 → output/open_matches.csv`; the file's 4 rows = the DB's unmarked rows ≥ 60 (marked `interview`/`applied` rows absent; checked row by row); `autopilot mark <top row> applied`, scan again → 4 rows, the marked URL absent (that the 4th is the job this scan scored is inferred, not checked); per-scan `jobs_*.csv` still written. Gates: 651 passed, coverage 92.09%, no-network 651 passed, ruff and mypy clean |
| T34 | fb25e31 | claude-b | `pytest tests/test_retire_json_state.py` → 6 failed before the code (grep test listed scanner/tools lines; a scan wrote `state/`; no script), 6 passed after. Mutants (scratch worktree): imported rows without their own key → 1 failed; importing onto known unscored rows → 2 failed. Tests that read `last_scan.json` (`test_direct_scanner` ×4, `test_scanner`, `test_legacy_scoring`, `test_tools_and_mcp`) now read the scan's CSV or the DB; `test_state_roundtrip` removed with `load_state`/`save_state`. **Done-when:** `grep -rn "last_scan.json\|job_history.json\|seen_jobs.json" job_hunt` → no output, exit 1. Real CLI, scratch dir with `state/` deleted: scan (3.1 wrapper, cap 1) → `scored 1 (gemini-3.1-flash-lite 1)`, no `state/` afterwards; `autopilot export` → "Exported 1 jobs (last scan)" from the DB. Import on copies of the production DB + `state/*.json`: dry run → "203 scored job(s) … 158 already in data/jobs.db, would import 45", DB hash unchanged; `--apply` → imported 45; again → imported 0; integrity ok; export `--min 70 --days 7` 33 → 53. A first version skipped 13 of the 45 (same title/company/location as another opening, unique key of id-less rows) — fixed before the commit. Real `data/jobs.db` SHA-256 unchanged. Gates: 646 passed, coverage 92.04%, no-network 646 passed, ruff and mypy clean |
| T32 | ffea468 | claude-b | `pytest tests/test_export_from_db.py` → 4 failed before (export listed the planted bogus JSON job), 5 passed after; old JSON-based export tests (`test_main_cli`, `test_export_smoke`, T38's no-DB test) now build the DB. Mutants: no date window → 1 failed; fixed threshold 55 → 1 failed; scan order instead of best-first → 1 failed. **Done-when, real CLI under `unshare -rn`:** `autopilot export --min 70 --days 7` → CSV URLs identical (same order) to `SELECT url FROM jobs WHERE status IN ('scored','notified') AND score >= 70 AND substr(scored_at,1,10) >= date('now','-7 days') ORDER BY score DESC, scored_at, id`: scratch scan DB 3 = 3; copy of production `data/jobs.db` (+ a `config.json` holding only `min_score`) 33 = 33. Production `job_history.json` would give 45 (see the task). Gates: 641 passed, coverage 92.06%, no-network 641 passed, ruff and mypy clean |
| T31 | 4e337d7 | claude-b | `pytest tests/test_draft_from_db.py tests/test_drafter.py tests/test_draft_numbering.py` → before the code: 4 failed + the tracker fixture could not import `start_scan`; after: 19 passed. Mutants (scratch worktree): ties in another order → 1 failed; `finish_scan` never called → 6 failed; ignoring the scan's time window → 3 failed. Tests that built `last_scan.json` by hand (3 in `test_drafter.py`, T10's numbering test, T38's fixture) now build the DB; T10's fake scorer now stores its score like the real one. Real CLI in the scratch scan directory: scan through the 3.1-only wrapper (cap 2) → `output/jobs_2026-10-08_2.csv`, `scans` row 1 started 16:14:41Z finished 16:16:38Z; `state/last_scan.json` deleted; `autopilot mark 1 none` → row 1 (Mastercard R-290601); `autopilot draft 2` (3 calls, 3.1) → `application_info.txt` "Source URL: …/10571613/sde-ii-amazon-india-ads" = CSV row 2, ends "Review, edit, then submit manually". Gates: 636 passed, coverage 92.04%, no-network 636 passed, ruff and mypy clean |

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
| T58 | Fresher cap (rubric rule 7); rule 2 judges the work | 9dd63f5 | Saved v2/v4 scores re-analysed: Hevo 90 → 50, FP at 70 5 → 2, precision 83% → 92%, AUC 0.946 vs 0.948, `apply` 15/15 → 14/15. **Done-when partly unmet, as its evidence said:** g27 (Amazon "SP Support") is missed, and under the current prompt not bimodal but always capped ([45, 45, 40, 45, 45] in T60's runs, which may include 3.1 answers; 40 and 40 live on 3.1, reason: the posting's 3+ years of video-games experience) — a labelling question: Manish relabelled g27 `no` (T59), after which the current prompt finds 14/14 `apply` at 60 and 70. Not in its evidence: `apply+maybe` recall at 70 fell 89% → 82% (Nike g20 75 → 50) | verified · claude · 2026-10-07 |
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
| T60 | Score variance measured; temperature unchanged | da2ed06 (+ tooling 9445456) | Sent back in the morning: ~9 of its 200 calls were answered by 3.1 after 3.5's quota ran out (real quota errors 19:52–19:54 on 2026-10-06 in `./scan.log`). Re-checked on 3.5 only (`measure_score_variance.py --ids ab5,g20,g27,h10 --runs 5 --model gemini-3.5-flash-lite --temperature 0` and `0.1`): temp 0 → 2/4 spread > 20, mean 22.5, flips 3/3; temp 0.1 → 3/4, 30.0, flips 3/4. "Temperature 0 is worse" does not hold; neither removes the bimodal flips; default 0.1 kept (CHANGELOG and README corrected). Saved numbers otherwise reproduce | verified · claude · 2026-10-07 (on 3.5) |
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
| T64 | Skip a Gemini model whose daily quota is gone (+ midnight-Pacific cap) | 2dede5d + 2fcfcc0 | `pytest tests/test_daily_quota.py tests/test_quota_breaker.py` → 16 passed. Mutants (scratch worktree): never remembering the model → 6 failed; no midnight-Pacific cap → 1 failed; a per-minute 429 treated as per-day → 6 failed. Through the real google-genai SDK (2.28.0) pointed at a local HTTP server that replays the real per-day 429 body from `./scan.log` (2026-10-06): 3 jobs → 1 request to 3.5, 3 to 3.1, skip until 01:00 UTC (retryDelay, earlier than midnight Pacific); a per-minute 429 → 6 requests to 3.5 (retried), nothing remembered. `data/autopilot.log` shows "retry in 23h21m" at 06:08 IST (00:38 UTC) 2026-10-07, as the CHANGELOG says. Not run: a model really out of its daily quota | verified · claude-b · 2026-10-08 |
| T65 | Workday "Location Negotiable" gets the detail call | 0fcb546 | Test passes. Live `fetch_workday("accenture", "wd103", "AccentureCareers")` on 2026-10-08 with `item_location` / `_fetch_detail` recorded: 2,000 jobs (2,000 unique), 502 "Location Negotiable", 7 detail calls, all on them; 5 → US offices (still rejected), 2 "Custom Software Engineer" → Hyderabad / Bengaluru (now pass); pre-filter passes 463 without the change (the same jobs with the placeholder) → 465 with it; 277 s | verified · claude-b · 2026-10-08 |
| T66 | PyYAML declared | 83a573d | Fresh Python 3.11 venv from `requirements.txt` (PyYAML 6.0.3, google-genai 2.29.0), run in a worktree of HEAD: `python -m job_hunt discover --add "Stripe" --report r.csv --out v.json --no-recheck` → exit 0, Stripe verified (728 jobs, 44 India). Deleting the pyyaml line from `requirements.txt` or `pyproject.toml` fails `test_every_third_party_import_is_a_declared_dependency` ("… lacks pyyaml") | verified · claude-b · 2026-10-08 |
| T67 | `discover --help` prints usage; unknown flags exit 1 | 4ac4c68 | Real CLI in an empty directory: `autopilot discover --help` → usage, exit 0; `--add-flie x.txt`, `--add` and `--report` without a value → "unknown or incomplete argument", exit 1; the directory stayed empty. Every flag used with `discover` in docs and code (merge, add-file, report, recheck, census, add, out, help, emit-seeds, seeds, no-recheck) is in the accepted set; `--add/--report/--out/--no-recheck` ran to exit 0 in the T66 check | verified · claude-b · 2026-10-08 |
| T72 | Pre-filter accepts Amazon's "Software Dev Engineer" titles | 560a6e8 | Fresh fetch of all 223 boards on 2026-10-08 through the scanner's own `_prefetch_jobs` (39,873 jobs, 0 errors, 335 s), then `should_evaluate_job` from a worktree at 2fcfcc0 (before) and from HEAD, each in its own process: survivors 1,692 → 1,745, **+53, every one an Amazon "Software Dev Engineer …" title** (I/II/III, Sr.), 0 removed. Labelled `apply`/`maybe` jobs rejected by HEAD's filter: none. Reverting the regex fails 4 tests. Not re-run: the evidence's live scoring of the added jobs (33 of 56 ≥ 80 on 3.1) | verified · claude-b · 2026-10-08 |
| T71 | Record which Gemini model scored each job | bdcd128 | Reviewer re-ran in a clean worktree at bdcd128: `pytest tests/test_score_model.py` 12 passed, full suite 616 passed. Mutants: storing `model=None` in the scorer → 2 failed; dropping the CSV value → 1 failed. Read the implementer's live evidence (scratch `init` dir, `scan --posted-within 1`: `scored 6 (gemini-3.5-flash-lite 6)`; a scan with a failing primary → `scored 2 (gemini-3.1-flash-lite 2)`, rows and CSV `Model` = 3.1) and checked it against the diff. Note: the deprecated non-Gemini path counts its provider in the funnel but stores `score_model` NULL (by design: "unknown") | verified · claude · 2026-10-08 |
| T38 | `autopilot mark #N\|URL applied\|interview\|rejected\|offer` | 5762c6a | Reviewer, real CLI under `unshare -rn` on a copy of the implementer's scratch scan (production DB untouched): `mark <amazon url> offer` → exit 0, row read back `status` scored / score 45 / `application_status` offer / 2026-10-08; `mark <url> none` → cleared (NULL, NULL); `mark <url> hired` → exit 1 with the allowed values; `export --days 2` → header ends `Application, Model`, the two earlier marks shown. 13 tests pass. `mark #N` was not re-run by me (the copy no longer had `state/last_scan.json`; the implementer ran it) | verified · claude · 2026-10-08 |
| T70 | Which Gemini model scores better (3.5 vs 3.1); keep 3.5 primary | 9445456, 3bc1c13 (numbers) | The implementer's four score files were no longer on disk, so re-measured the same day (2026-10-08) on the pre-T73 rubric it used: `score_golden_set.py --arms current --model gemini-3.1-flash-lite` from a worktree at 560a6e8 (rubric hash checked; 82/82 answered) + the reviewer's same-day 3.5 run of that rubric (`…/scratchpad/r/full_v4_a.scores.json`) → `--from-scores`: at 70 `apply` 14/14 for both; false positives 3.5 **2**, 3.1 **11** (claimed 10); precision 92% vs 69% (claimed 71%); AUC 0.959 vs 0.956, CI [-0.025, +0.022]; between models mean |diff| 8.3, 12 pass/fail changes at 60 and at 70 (claimed 8.0–8.4, 11–14); 3.1 minus 3.5: `no` +6.9, `maybe` +5.0, `apply` +1.7 (claimed +7.5 / +0.7). Independent 3.5 spot-check (mine): the 11 jobs 3.1 passes wrongly at 70, scored once each on 3.5 with that rubric → 2 of the 10 answered ≥ 70 (g16, g17: 75), 1 failed (503). Recommendation holds on precision. Also seen (not part of T70): on the T73 v6 rubric, one run each, 3.1 ranked *better* (AUC 0.990 vs 0.956, CI [+0.003, +0.079]) and found g1, but with 3 false positives at 70 vs 0; not re-run on v7. Not reproduced: 3.5's run-to-run noise (needs a second 3.5 run) and the 1.8 s median (3.1 answered in 15–28 s this evening) | verified · claude-b · 2026-10-08 |
| T73 | Rubric v7: skip postings that require a stack or domain Manish lacks | 3bc1c13 + fix b6f4775 | First sent back (2026-10-08, claude-b): v6 scored `apply` job g1 (Expedia) 50 in 10 of 11 runs on 3.5 (v4: 75–85), reading a responsibilities "languages such as Kotlin, Java or C#" as a mandate. Re-verified 2026-10-10 on v7: the diff is rule 4 only (+ its tests, docs, CHANGELOG); the committed `SCORING_RUBRIC` equals v6 at cfadad7 with the measured rule 4 swapped in (rebuilt from the measurement script via `ast`, 4,023 chars) and HEAD's. The reviewer's saved runs (`…/scratchpad/r/full_v7_a/b.scores.json`, `full_v4_a.scores.json`) through `score_golden_set.py --from-scores` reproduce every CHANGELOG number: `apply` 14/14 ×3; FP at 60 5 → 0/0, at 70 2 → 0/0; AUC 0.959 → 0.971/0.973 (CIs include 0); v7 runs 3.1 points apart, 0/1 flips; held-out identical. **My own live check on 3.5 (24 calls, model pinned, HEAD rubric):** g1 ×5 → 85, 75, 85, 75, 85 (+ 85 in the apply pass); v4's 5 false positives at 60 (g16, g17, g27, ab6, ab22) → 50, 45, 45, 50, 50, each reason naming the real requirement (Java+Spring mandatory, Golang required, video-games industry, JVM language, C#/.NET); all 14 `apply` → 75–90 (14/14 ≥ 70). Gates at HEAD (89274ce): 685 passed, coverage 92.58%, no-network 685 passed, ruff and mypy clean | verified · claude-b · 2026-10-10 |
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
| Pre-filter Accenture's generic "Custom Software Engineer" titles by the "Must have skills" line (T68) | claude, 2026-10-07 | Manish, 2026-10-07: a title or skills-line rule would also drop real fits; Gemini reads the whole description and decides, which is the safe side. Cost accepted: some scoring calls on low-fit Accenture roles (6 of 6 scored 30–40 in one scan). |
| Playwright for custom portals; scraping Naukri/LinkedIn; multiple resume profiles | Gemini web, Antigravity | High cost and ban risk. Reopen only with a concrete plan and measured payoff. |
