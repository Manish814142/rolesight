# TASKS — JobNotify task board

The one shared board for everyone working on this repo: Manish, Claude Code,
Antigravity, or any other agent.

- **Told to "work from docs/tasks.md"?** Follow the [Working loop](#working-loop).
- **Told to "verify the tasks"?** Follow [Verifying](#verifying).

**Last re-evaluated:** 2026-10-10 (evening) against commit `0c3ba2b`: Manish answered the open decisions (below) and the agent implemented every
task that needed nothing more from him; they are in the [Review queue](#review-queue). Measured at that commit: 797 tests pass (also
under `unshare -rn`, no network), coverage 92.68%, ruff and mypy clean. File:line references drift; search for the named function if a line has moved.

**Reviewed 2026-10-10/11 (claude, against `2225284`):** T02, T05, T26 and T62 verified 2026-10-10, T08 on 2026-10-11 (Done log). T07 and T28: their
scripts pass, but the review found the timers' network wait did nothing and fixed it (`scripts/systemd/wait-online.sh`, see T07); installing them
stays Manish's call. T74 waited for `gemini-3.5-flash-lite`'s quota (out at 19:28 IST on 2026-10-10) and was verified on 2026-10-11 on 3.5 (Done log); it raised
two label questions (j7, g8: T59) and one new task (T79).
**Second review round (2026-10-11 night, claude):** T80, T81, T78 verified; T77 verified after a reviewer fix (non-place words and `IND` no longer
reject a remote job); **T79's rubric change reverted** (it fixed one posting but lowered ranking on the 82 labelled jobs: AUC 0.944 / 0.931 vs
0.971–0.976) and sent back as `changes`; T85 added. Review queue empty.

### Manish's answers (2026-10-10) and what became of them

| Task | His answer | Result |
|---|---|---|
| T02 | Asked what the question was ("how many days back"); added: a job older than the window should not be scraped at all | **7 days** is now the default (Claude's choice, one number: `candidate.max_posted_age_days` in `config.json`, `null` = off, `--posted-within N\|all`). The adapters no longer spend a request on older jobs where the list order allows it. **Tell me if you want 3.** |
| T05 | 70 | Done: `min_score` 70, in `config.json` only. |
| T62 | Allow "python" for now; decide again on the results | Done (`java`, `golang` stay excluded: he named only python). |
| T74 | Allow AI Engineer / Forward Deployed Engineer only when the posting accepts his MEAN / backend stack with GenAI used in workflows; not when it needs LangGraph, LangChain, vector DBs or other advanced AI | Done in the pre-filter and rubric rule 8, measured; **see T74's caveats (some borderline AI roles are now capped)**. |
| T26 | Build the Phenom adapter | Done (BCG added). |
| T45 | A web page, not a terminal; configure everything A–Z; Gemini suggests / checks the configuration; "clarify if I understood wrong" | Architectural, so a **design proposal with questions** is written (`docs/superpowers/specs/2026-10-10-web-ui-design.md`); no code until he approves it. |
| T34 | "You decide, in my best interest" | Decided: **do not import** the 45 old scores (they come from the pre-rubric prompt of 2026-10-04; any job still open is re-scored by the next scan — *correction 2026-10-12: true only for jobs the retired JSON files alone knew; the 145 `scored` rows already in the database are final, see T86*). `scripts/import_json_history.py` stays for whoever disagrees. `state/*.json` are left on disk. |
| T31, T33, T38, T39, T44, T71, g1 | Not answered | The defaults the implementer chose stay in force; they are still **waiting for his confirmation**. |

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
Engineer" titles reach Gemini) — both verified (T72 2026-10-08, T73 2026-10-10). Since then T62 (python titles) and T74 (AI / Forward Deployed Engineer titles with a
heavy-AI cap) were decided, built and verified (2026-10-10/11). What still would move it: Manish's labels (T59, incl. j7 and g8) and T79.

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

T48, T57, T58, T60, T61 and T49 were verified 2026-10-07, T72 and T70 on 2026-10-08, T62 on 2026-10-10, T74 on 2026-10-11 (Done log).

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
**g8 (from T74's review, 2026-10-11):** MongoDB "Software Engineer 3 - Enterprise Architecture" (Gurugram) is labelled `apply` (2026-10-04), but it is
an AI-experimentation team and its required list asks for "hands-on experience prototyping with LLMs or agentic systems (evals, fine-tuning, RAG,
tool use, orchestration frameworks)". Under the T74 clause it passes 3 of 8 runs. Keep `apply` (then the clause is too strict for you) or relabel `no`?
**j7 (from T74, 2026-10-10):** Thermo Fisher "Software Engineer I, AI Solutions & Platforms" is labelled `apply` (2026-10-04), but its duties are RAG and agentic
workflows with pgvector / Qdrant vector search, which is the "heavy AI" he said to reject on 2026-10-10. The new rubric clause scores it 45. Relabel it `no` if you
agree; I did not change a label to fit a result. The new file `scripts/golden_set_ai.csv` (75 AI / FDE postings) needs the same confirmation.
**g1 (from T73's review, 2026-10-08):** Expedia names Kotlin/Java/C# only in the responsibilities ("using languages such as");
its qualifications ask for any language. Kept `apply` (rubric v7 scores it 75–85). If you would skip it, relabel g1 `no`.

**T62 · Allow "python" in job titles.** *Decision (Manish, 2026-10-10):* yes for now; decide again on the results. `java` and `golang` stay excluded.
**Implemented (claude, 2026-10-10, 4b2ef97).** One word removed from the title exclusion pattern; tests for 7 titles that now pass and 9 that must still be
rejected (Staff, Lead, Architect, Intern, Data Scientist, Java, Golang, Test, Frontend). Measured on the saved 2026-10-08 fetch (39,873 jobs): survivors
1,745 → 1,792 (+47, 0 removed; 11 posted within 7 days, 39 within 30). *Done when:* the 47 titles pass, nothing else changes — met on the saved fetch.
Not measured: what Gemini scores them under the current rubric (the 2026-10-07 numbers were 3.1 and the old rubric: 9 of 32 ≥ 80).

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
**Decision (Manish, 2026-10-10):** yes, *but only* when the posting accepts his MEAN / backend stack with GenAI used in workflows; not when it
requires heavy AI (LangGraph, LangChain, vector DBs, "advanced things").
**Implemented (claude, 2026-10-10, 0c3ba2b).** (1) Pre-filter: AI / Gen AI / Generative AI / Agentic AI / Applied AI / LLM Engineer and Forward
Deployed Engineer titles pass (survivors 1,792 → 1,900 on the saved 2026-10-08 fetch, 0 removed; 80 of the 108 are in India). (2) Rubric rule 8
gains an AI/ML clause. (3) New `scripts/golden_set_ai.csv`: 75 India AI/FDE postings fetched 2026-10-10 with full descriptions, labelled by Claude
against his rule (66 `no`, 1 `apply`, 8 `maybe`; none confirmed by him). Measured on `gemini-3.5-flash-lite` (pinned): the old rubric passes 23 at
70, 19 of them `no` (precision 17%); the shipped wording passes 2 of the first 43 where the old one passed 16 (false positives 15 → 2). **Costs and
caveats:** on the original 82 labelled jobs one run of the second wording found 12 of 14 `apply` (v7: 14 of 14, twice); j7 (Thermo Fisher "AI
Solutions & Platforms": RAG, agentic workflows, pgvector/Qdrant) 90 → 45 and g8 (MongoDB SE 3) 90 → 45/90, which is the clause working on j7
(its `apply` label predates his rule — **please relabel `no` if you agree, T59**) and a misfire on g8. Borderline AI-light FDE roles (Razorpay
90/45/45, DevRev 45–50) are capped most of the time. **Not done: the final wording's full 75-job run (3.5's 500-call daily quota ran out at job 43,
19:28 IST) — re-run `python scripts/score_golden_set.py --csv scripts/golden_set_ai.csv --arms current --model gemini-3.5-flash-lite` after the reset
(the API said "retry in 10 h" at 19:28 IST; the reset was observed at 12:30 IST on 2026-10-07, so after 12:30 IST on 2026-10-11 is safe) and `--from-scores` it against the saved scores before marking this verified.** Questions for Manish: are the 9 labels I called
allowed right (T59 for the new file)? Do you want "AI/ML Engineer" and "Machine Learning Engineer" titles too (not added)?
**Review notes (2026-10-10, claude) — was on hold for 3.5's quota; finished 2026-10-11 (below).** Checked
without Gemini: the diff is T74 only; the pre-filter change reproduces on the saved fetch in separate worktrees (1,792 → 1,900, +108, 0 removed); the
43-job partial run reproduces from the saved scores (old rubric 16 pass at 70, 15 of them `no`; shipped wording 2, both `no`). A probe call at 20:17 IST
still got HTTP 429 (`retryDelay` 33,187 s). **Gaps the 3.5 run must close:** (a) the AI set's only `apply` job and 2 of its 8 `maybe` jobs are among
the 32 unanswered; (b) the shipped wording was never run on all 82 original jobs, only on the 25 that mention AI, twice
(`data/golden_runs/gold_ai25_t74_shipped_x2_2026-10-10.txt`): `apply` g8 (MongoDB) **90 / 45** and `maybe` g12 75 / 45, although g8's vector-DB and
LangGraph items sit under "Bonus Round", which the clause says never counts, so g8 is a misfire in 1 of 2 runs [*corrected 2026-10-11:* its required
list also asks for hands-on LLM / agentic prototyping, so g8 is borderline, not a misfire]; j7 45 / 45 (label question above).
(c) The clause states facts about Manish ("used GenAI/LLM APIs inside backend services … has not built ML or agent systems"); they match his resume
today (GenAI automation, token cost; no agents or RAG), but **the rubric must be edited if his resume changes**. **To finish (about 162 calls on 3.5):**
`python scripts/score_golden_set.py --csv scripts/golden_set_ai.csv --arms current --model gemini-3.5-flash-lite` (75) and
`python scripts/score_golden_set.py --arms current --model gemini-3.5-flash-lite` (82), each then `--from-scores` against the baselines copied to the
gitignored `data/golden_runs/` (the scratchpad copies vanish on reboot): `ai_old_rubric_3.5_2026-10-10.json`, `ai_t74_partial43_3.5_2026-10-10.json`,
`gold_v7_a_3.5_2026-10-08.json`, `gold_v7_b_3.5_2026-10-08.json`; plus `python scripts/measure_score_variance.py --ids g8 --model gemini-3.5-flash-lite`
(5 runs). Pass if the AI set keeps few false positives at 70 and the original `apply` jobs other than j7 stay ≥ 70; if g8 keeps failing, the
"bonus" wording needs another fix.
**Review result (2026-10-11, claude, on 3.5): verified** (Done log). AI set, all 75 answered: 6 pass at 70 (old 23), 3 `no` (old 19), the `apply`
found. Original 82: 0 false positives, `apply` 13/14 — the miss is j7, by design. g8 over 8 runs passes 3 (borderline; see T59). The 3 AI-set false
positives are steady or noisy without the clause (ai33 85/90/85, old 85; ai41 70–75, old 70; ai44 85/85/45, old 40). Not a T74 issue but found
here: ai65 (`apply`) 30/75/30 from rule 1 on a Hyderabad role — T79.

---

## P0 — Before scheduling the daily run

Why this comes first: the expansion work raised volume about 6× (36,228 jobs fetched,
1,271 pre-filter passes, per CHANGELOG). The production DB `data/jobs.db` holds one scan of
2026-10-04: 30,367 rows, 145 `scored`, 23 `discovered` (the Amazon re-score, T57), 30,199 `skipped`
(measured 2026-10-07, read-only). T03 and T04 now stop scoring when the quota is gone and cap a run
at 400 jobs; T02 (7 days) and T05 (70) are decided and verified.

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T01 | Back up the repo to a private remote | manish | — | XS | — |
| T06 | Check that Telegram works | manish | — | XS | — |
| T07 | Schedule `run_daily.sh` with a systemd user timer | manish | — | S | T02, T03, T04, T05 |
| T09 | First full production run; record the funnel | review · claude · 4f3d83a | claude | S | T02–T05 (T06, T07 are Manish's and not needed for a manual run) |

T03 and T04 were verified 2026-10-07, T64 on 2026-10-08, T02 and T05 on 2026-10-10, T08 on 2026-10-11 (Done log).

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
**Decision (Manish, 2026-10-10):** he asked what the question was and added that a job older than the window should not be scraped at all (no API call for it).
**Implemented (claude, 2026-10-10, 5001dcd).** Default **7** (my choice: he named no number; 3 was his example; 7 survives a skipped day), in
`job_hunt/settings.py`; `null` in `config.json` = no window; `autopilot scan --posted-within N|all` overrides it; the example configs document it with
`fetch_workers` and `gemini_scoring_mode`. The window reaches the adapters: no Workday detail call for an older job; Oracle HCM, Eightfold and SmartRecruiters
stop paging at the first all-older page (their lists are newest first: 0 order violations over whole boards, measured); Amazon is not cut (980 order
violations). Real boards, requests with no window → 7 days: Qualcomm 58 → 10, EXL 21 → 5, Bosch 20 → 7, NielsenIQ 5 → 3, Citi 62 → 48; in-window survivors
equal except Qualcomm's first run (3 vs 2; a re-run gave 3 vs 3, so probably a posting that changed between the runs — inferred). The scan's own log line is
`Posted-date filter: last 7 day(s) …` (the "skipped as posted more than N days ago" wording of this done-when does not exist; the funnel's `too old` is the
count). Side effect: 4 older tests that assumed no window now say `max_posted_age_days: null`.
**Review notes (2026-10-10, claude):** verified (Done log). *Correction:* the done-when's line does exist — `scanner.py` logs
`N job(s) skipped as posted more than 7 day(s) ago` whenever `too old` > 0 (there since b700235); the reviewer's real `./run_daily.sh --limit 5`
printed `254 job(s) skipped as posted more than 7 day(s) ago`. Also corrected: the docs called 7 "Manish's" number; it is Claude's choice until he
confirms it. Known trade-off (documented in docs/07): a board stopped at the window counts as partly fetched, so T33 closes nothing on it — T78 (fixed 2026-10-11: jobs inside the window are counted).

**T05 · One MIN_SCORE.** `.env` has `MIN_SCORE=60`, and `load_dotenv(override=True)`
(`main.py` L52) makes it beat the `70` that `run_daily.sh` exports (measured).
`run_daily.sh` then prints 70 in its banner while the scan uses 60.
**Manish: choose 60 or 70.** Keep the value in one place and remove the misleading
banner value.
*Done when:* the scan's own `Min score:` log line (`scanner.py` L383) shows the chosen
value, whichever way the run is started.
**Decision (Manish, 2026-10-10): 70.** **Implemented (claude, 2026-10-10, bda04eb).** `candidate.min_score` in `config.json` is the one place (set to 70 in his file;
his `.env` line is commented out); the code default for every reader is 70 (`job_hunt/settings.py`; scanner and export used 55); example configs say 70; the `.env`
template has no active line; `run_daily.sh` exports nothing. Real `./run_daily.sh --limit 1` in a scratch directory logs `Min score: 70 | Top N: 5` first.
Not run: a Telegram alert at 70.
**Review notes (2026-10-10, claude):** verified (Done log). *Correction:* the reason given in `settings.py`, docs/07 and the CHANGELOG ("precision 92% at
70 against 86% at 60") was the pre-T73 rubric's; with rubric v7 neither threshold passes a `no` job (2 runs). Reworded; the choice of 70 is unchanged.

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
**Prepared, not installed (claude, 2026-10-10, 50d9135).** `scripts/systemd/install.sh` writes the two unit files (daily 09:00, `--at HH:MM`, `Persistent=true`)
into `~/.config/systemd/user` and enables the timer; `--uninstall` removes them. `systemd-analyze --user verify` accepts the rendered files (real parser; test).
**Needs Manish's go-ahead (installing a timer is his call):** `scripts/systemd/install.sh`. Also his choice: the time of day, and that the first scheduled
scan uses `gemini-3.5-flash-lite`'s quota (about 300 calls with the 7-day window, measured on the saved fetch: 302 survivors).
**Review notes (2026-10-10, claude):** the unit files passed `systemd-analyze` but their `Wants=` / `After=network-online.target` did nothing: the
user manager has no such unit (`systemctl --user show network-online.target` → `LoadState=not-found`, measured here). With `Persistent=true` a
missed run starts as soon as the user manager starts (login, wake), often before Wi-Fi, and that scan would fetch nothing. **Fixed by the reviewer
(committed 2026-10-11):** both services run `scripts/systemd/wait-online.sh` as `ExecStartPre` — it waits up to 5 min
for a TCP connection to `generativelanguage.googleapis.com:443`, else exits 1 with a line in `data/scan.log`. Measured: online exit 0 (≈5.2 s per try
here); under `unshare -rn` exit 1 at the limit with the log line; 7 new tests (probe stubbed, no network) red when the units lack the line or the
script exits 0 on failure. Still `manish`: installing is his call (`scripts/systemd/install.sh`, add `--with-recheck` for T28). Since the fix is the
reviewer's own, a fresh session should re-read it.

**T08 · `setup_cron.sh`.** It installs `python -m job_hunt.main scan >> ./scan.log`,
which bypasses `run_daily.sh` (measured). It is still referenced in `SETUP.md` L523,
`docs/04-companies-and-scanning.md` L50 and `docs/08-troubleshooting.md` L13. Delete
it and point the docs at T07's timer, or make it install `run_daily.sh`.
*Done when:* `grep -rn setup_cron .` returns only the references you intended.
**Implemented (claude, 2026-10-10, 50d9135).** `setup_cron.sh` deleted; `docs/01-install.md`, README and ARCHITECTURE point at `scripts/systemd/install.sh`.
`grep -rn setup_cron .` now finds only history (CHANGELOG, this board) and one sentence in `docs/01-install.md` saying it is gone.
**Review (2026-10-11, claude):** verified (Done log).

**T09 · First production run.** After T02–T05 (T06 optional), run `./run_daily.sh`
once. Record in CHANGELOG: jobs fetched, India, pre-filter passes, too old, scored,
≥ MIN_SCORE, scoring failures, and minutes taken.
*Done when:* `data/jobs.db` has rows scored today, a new `output/jobs_*.csv` exists, and
`data/scan.log` ends with "Scan finished with exit code 0".

---

## P1 — Small correctness fixes

T11, T12, T14, T15, T16, T17 and T18 were verified 2026-10-07, T66 and T67 on 2026-10-08, T77, T78 and T81 on 2026-10-11 (Done log).

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T79 | Rule 1 (the outside-India cap) is sometimes applied to an Indian city | changes · claude (fix reverted 2026-10-11; see review notes) | — | M | — |
| T75 | Every per-job lookup scans the whole `jobs` table | review · claude · a465be9 | claude | S | — |
| T87 | Two scan tests had a literal posted date that aged out of the 7-day window | review · claude · 05fb89f | claude | XS | — |
| T76 | Workday maintenance silently empties a scan's Workday boards | review · claude · 09f3617 | claude | S | — |
| T83 | `autopilot init` and `run_daily.sh` still create an empty `state/` directory | review · claude · ea80c07 | claude | XS | — |
| T85 | The example config describes the wrong person | review · claude · 9a49634 | claude | XS | — |

**T85 · The example config describes the wrong person. `config.example.json` and `job_hunt/data/config.example.json` (what `autopilot init` writes) still carry upstream's persona: `profile` "10+ YOE, Senior/Staff ML/AI Engineer … MLOps", `seeking` "Remote-friendly or relocation to EU / NA / APAC", `not_suitable` "… pure SWE with no ML …". This fork's pre-filter rejects Staff titles and non-India places and its rubric is written for a 3-year backend engineer, so a new user who forgets to edit them gets scores that contradict the filter. The guide (T80) says to edit them first. Possible fix: neutral placeholders, or the guide's own examples ("3 YOE backend engineer …")** *Done when:* both example files carry the guide's own example sentences (a test ties the three to `docs/00-user-guide.md`), nothing mentions the upstream persona, and `autopilot init` still writes a valid config.

**T83 · `autopilot init` still creates an empty `state/` directory. `main.init_project` ends with `(cwd / "state").mkdir(exist_ok=True)`, but the `state/*.json` files are retired (T34): nothing reads or writes them. Harmless; a new user sees a folder with no purpose. Possible fix: drop the line (and the matching `Dockerfile`/doc mentions if any)** *Done when:* `autopilot init` in an empty directory and `run_daily.sh` create no `state/`; nothing else breaks.

**T76 · Workday maintenance silently empties a scan's Workday boards. 2026-10-10 12:19 IST: 77 of 79 Workday tenants answered the jobs POST with HTTP 303 → `community.workday.com/maintenance-page` (Accenture's wd103 answered 200). The adapter follows the redirect, fails to parse the HTML ("Expecting value: line 1 column 1") and logs one warning per tenant; that scan gets no Workday jobs (they are fetched next time, and T33 counts no misses for them). Possible: detect the redirect and log one clear line, or retry later in the run** *Done when:* a Workday answer that ended on another host (the maintenance page) is reported as one clear line per scan, the board is marked incomplete (T33 counts no miss), and no JSON-parse warning is logged for it; a normal answer is unchanged.

**T87 · Two scan tests had a literal posted date.** `tests/test_db_details.py` (`2026-10-05`) failed on 2026-10-13 and `tests/test_score_model.py` (`2026-10-08`) would have from 2026-10-16: a real `run_scan` drops jobs older than the window. *Done when:* both use yesterday and the suite passes with and without network.

**T75 · Every per-job lookup scans the whole `jobs` table. `get_job` / `has_job` / `update_job_status` / `update_job_details` use `WHERE global_id = ?`, which cannot use the partial unique index `idx_jobs_ats_global_id` (its condition `global_id IS NOT NULL AND global_id != ''` is not implied): EXPLAIN QUERY PLAN → `SCAN jobs`. 2.7 ms per `get_job` on a copy of the production DB (30,367 rows); a scan calls it once per fetched job (~40k), so ~110 s per scan (inferred), growing with the table. Fix as in T33's `record_sightings`: add `ats = ?` and the index condition (`SEARCH … USING INDEX`), or a plain index on `global_id`** *Done when:* `EXPLAIN QUERY PLAN` of each lookup the program really runs says `SEARCH … USING INDEX`, none says `SCAN jobs`, and the same ids still return the same rows.

**T79 · Rule 1 (the outside-India cap, ≤ 30) is sometimes applied to an Indian city. Notion's "Forward Deployed Engineer, India" (ai65, labelled `apply`), Hyderabad, 3 office days, `#LI-Onsite`: 3.5 scored it 30, 75, 30 on 2026-10-11 (75 in the full run), reasons "requires on-site presence in Hyderabad … conflicts with the candidate's … Bengaluru preference". Rule 1 already says India-based and India-hybrid roles are eligible; `candidate.seeking` reads "Remote / Hybrid / Bengaluru / India". Rare so far: the other non-Bengaluru `apply`/`maybe` jobs in the labelled set (Hyderabad, Gurugram, Karnataka) score 75–90, and none of the 145 scored jobs of the 2026-10-04 scan has a ≤ 50 score whose reason names another Indian city. **Question for Manish:** do you take on-site or hybrid roles in any Indian city? If yes, possible fix: rule 1 says a role in any Indian city is never capped for location, measured on ai65 ×5 and the 82 labelled jobs (~90 calls on 3.5)** Manish's order of 2026-10-11 ("T79 and T09 when the quota is confirmed") covers doing it; his rule in CLAUDE.md is "India or remote", so the wording below only states what rule 1 already says. *Done when:* on `gemini-3.5-flash-lite` (pinned), ai65 (Notion FDE, Hyderabad, labelled `apply`) scores ≥ 70 in at least 4 of 5 runs where it scored 30, 75, 30; on the 82 labelled jobs there is no new false positive at 70 and `apply` stays at 13 of 14 or better.
**Review notes (2026-10-11, claude): changes — the fix (10df19d) is reverted.** It did fix ai65 (15 runs: mean 67.3 → 81.0, 13/15 → 15/15 pass), but the two checks it owed, run by the reviewer on 3.5 the same evening, show a cost on everything else: on the 82 labelled jobs AUC 0.944 and **0.931** (two runs) against 0.971 / 0.973 / 0.976 without the sentence (one of them T74's run that evening, same model); `apply` jobs −6 points on average (several 85 → 75), `no` jobs +2.6, recall of `apply`+`maybe` at 70 74–78% vs 81–85%, one more `apply` lost in one run. The 63 other AI-set `no` jobs: 0 false positives either way. The misfire it targets is rare (ai65: 2 of 15 runs; 0 of the 145 real scored jobs of 2026-10-04 show it). **Options, Manish's call:** (a) accept the rare misfire (the reviewer's recommendation for now); (b) make `candidate.seeking` in his `config.json` say what he accepts, e.g. "Remote, or hybrid / on-site anywhere in India (Bengaluru preferred)" — his file, so his wording — then measure ai65 ×15 and the 82 ×2 (about 180 calls on 3.5); (c) a different rubric wording, measured the same way. Whatever is tried must be judged on the 82, not on ai65 alone.

**T77 · The pre-filter lets remote-flagged jobs in named non-India places through.** `should_evaluate_job` passes a job when the ATS says "remote" and the location does not match the small exclude list (US, UK, Canada, Germany, Europe, London…): OpenAI's Ashby board flags Paris, Tokyo, Singapore, Seoul, Madrid, Sydney and Washington DC offices as remote, so 25 OpenAI jobs and 65 of 1,900 survivors (3.4%) on the saved 2026-10-08 fetch name no Indian place. The rubric caps them (rule 1), so the cost is the scoring calls (about 5 s each), not wrong results. Possible fix: reject a remote-flagged job whose location names a city and country with no India term** *Done when:* measured on a fresh full fetch: the jobs the change removes are listed and every one names a non-India place with no India term; no job whose location is India, `Remote`, worldwide/anywhere or an Indian state/city survives less; survivors drop by about the 3.4% measured.
**Review notes (2026-10-11, claude): verified after a fix by the reviewer.** The rule treated every word left after its filler list as a place, so non-place words and India's own code rejected a remote job: with a passing title, `IND - Remote`, `IN - Remote - IND`, `Remote (Full Time - Remote)` and `Remote or Office (Depending on Region)` (all on the 2026-10-11 fetch; their jobs had failed the title filter, so the survivor count did not show them), and in probes `Remote - IST`, `Remote, UTC+5:30`, `Remote (Contract)`, `Remote (Permanent)`, `Telecommute`, `Home Office`. Boards do put such words in the location (1,180 jobs on that fetch). A wrongly kept job costs one call that rule 1 caps; a wrongly rejected one is never shown, so the fix errs that way: job-type, timezone, office and short connecting words are filler, and `IND` counts as Indian. Measured on the same 39,713 jobs: survivors still 1,817 (1,878 before T77), 0 real decisions changed; of 842 distinct remote locations with a passing title, exactly those 4 flip to kept and every foreign place stays rejected. 14 new tests (red before the fix) + 5 guards (`Singapore (Permanent)`, `Paris, France (Full-Time)`, … still rejected).

**T78 · With the posted-date window on, closed-job detection (T33) is off for newest-first boards. `adapters.base.stop_at_window` marks a fetch that stopped at the window as incomplete, and `db.record_sightings` counts no misses on an incomplete board, so the 21 Oracle HCM / SmartRecruiters / Eightfold boards never close a job while they stop early (Qualcomm did: `incomplete=posted-date window`, measured). Small today: `open_matches.csv` already drops jobs older than the window, so a closed job lingers there at most ~7 days. Possible refinement: on a window stop, count a miss only for that board's rows whose current age is inside the window (they would have been on the pages read)** *Done when:* a board that stopped at the window counts a miss for stored jobs that are inside the window and were not returned, and for no other job; three such scans close a job that is really gone; a job outside the window or undated is never closed by a window stop.
**Review notes (2026-10-11, claude): verified** (Done log). The window-stop reason, the per-row age check and the scanner wiring read correctly; SmartRecruiters stores the same `releasedDate` it stops on, and `mark_incomplete` keeps the first reason (a page failure before the window stop still blocks closing).

**T81 · The `.env` template overrode `config.json`.** Found by running T80's steps in a fresh clone: `init` wrote `CANDIDATE_NAME="Your Name"`, `RESUME_PATH="resume/YOUR_RESUME.md"` and `TOP_N=5` as live lines, `main.load_config` lets those beat `config.json` with no placeholder check, so a new user's edited name and resume path were ignored and the scan scored against the template resume. *Done when:* after `autopilot init` in an empty directory, the name, resume path, `top_n` and `min_score` edited in `config.json` are what `load_config` returns. Existing `.env` files are not touched (Manish's has real values in those lines).
**Review notes (2026-10-11, claude): verified** (Done log). Manish's own `.env` still has live `CANDIDATE_NAME`, `RESUME_PATH` and `TOP_N` lines from the old template; today they equal `config.json` (resume `resume/manish_singh.md`), so nothing is wrong yet, but a later change of the resume path in `config.json` would be ignored: comment those three lines out (the guide, section 3).

---

## P2 — Better input for the scorer

T23 was verified 2026-10-07 (Done log); nothing open.

---

## P3 — Coverage

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|
| T28 | Monthly `discover --recheck` that only reports | manish (script verified; the timer is installed with T07) | claude | S | T07 |

T65 was verified 2026-10-08, T26 on 2026-10-10 (Done log).

**T25–T27 · New ATS platforms.** (A previous Claude session recorded that Eightfold's PCSX endpoint returns HTTP 403 and Darwinbox needs a tenant session, tried 2026-10-04/05; that note is from memory, not in the repo, so re-check before relying on it.) The census (31cb7c0) of 458 careers pages found
Eightfold and Phenom on 7% each and Darwinbox on 6%, while 52% were unidentified (per
CHANGELOG). Step 1: find a public JSON endpoint; if there is none, move the task to
Rejected with the evidence. Step 2: write the adapter, with tests on recorded fixtures
(no network).
*Done when:* `autopilot discover --add-file` accepts at least one company on that
platform, and a scan fetches its jobs.

**T25–T27 result (claude, 2026-10-06).** *T25 Eightfold:* done, verified 2026-10-07. *T26 Phenom:* the endpoint is public (`POST {host}/widgets`, `selected_fields.country=["India"]`, `size` up to 100 honoured, full description in the job page's JSON-LD), **but Phenom mostly fronts Workday**: on Cisco, DuPont, Fiserv, HPE, Philips and WBD every sampled job's `applyUrl` is a Workday tenant. I added the three missing Workday tenants instead (Cisco, DuPont, Fiserv) through `discover`, no new adapter. The only Phenom-native census board with India jobs is BCG (91 India jobs, **2** pass the pre-filter). **Decision for Manish:** is a native Phenom adapter (~150 lines, a JSON-LD description scrape) worth 2 BCG jobs, or park it until another Phenom-native company turns up? *T27 Darwinbox:* rejected, see the Rejected table.

**T26 · Phenom adapter.** *Decision (Manish, 2026-10-10): build it.* **Implemented (claude, 2026-10-10, a18c25a).** `job_hunt/adapters/phenom.py`
(`POST {host}/widgets`, India scope, 100 per page, description from the job page's JSON-LD), wired into dispatch, `ENRICHERS` and `discover` (seed
`BCG | phenom | careers.bcg.com | global/en`). Added through the real `autopilot discover --add-file … --merge`: BCG, 101 jobs, 96 India, 3 pass the
pre-filter, descriptions 8.4–8.6 k characters; `companies.json` is 224 boards. Not run: Gemini on those 3 jobs; a scan with BCG in the full list.
Phenom's list is not newest first, so the posted-date window never cuts it.
**Review notes (2026-10-10, claude):** verified (Done log). Real `fetch_company_jobs` on BCG: 101 jobs, 101 unique ids, 96 India, 6.5 s, complete; 40 of
100 neighbouring pairs out of date order (so not cutting it at the window is right); the 3 survivors' JSON-LD descriptions are job-specific (8,461–8,623
characters, three different hashes, RAG/FastAPI text for the two AI roles, marketing-platform text for the third), not a shared page template.

**T28 · Scheduled recheck.** `discover --recheck --merge companies.json` (b700235)
catches ATS migrations and dead boards, but only runs when started by hand. Run it
monthly against a scratch copy of `companies.json` and save the diff for Manish to
review. Never write the real file unattended.
*Done when:* the timer is listed, and a run produces a diff file while
`companies.json` is unchanged.
**Implemented (claude, 2026-10-10, 50d9135 + aac9a99).** `scripts/monthly_recheck.sh` works on a copy in `data/recheck/` and leaves `diff.<date>.txt`,
`report.<date>.csv`, `verified.<date>.json`; `scripts/systemd/install.sh --with-recheck` adds the monthly timer (1st, 10:00). Real run on all 224 boards
(about 2 minutes): `224 -> 224 companies (0 changed)`, empty diff, `companies.json` and its packaged copy byte-identical (SHA-256 before and after).
The first real run left `verified_companies.json` in the repo root; fixed in aac9a99. **Timer not installed (Manish's go-ahead, see T07).**
**Review notes (2026-10-10, claude):** the script half of the done-when passes. Reviewer's real `scripts/monthly_recheck.sh` in a clean worktree at
`2225284`: `224 -> 224 companies (0 changed)`, exit 0 in 132 s; SHA-256 of `companies.json`, `job_hunt/data/companies.json` and
`scripts/company_seeds.txt` identical before and after; `git status --untracked-files=all` empty afterwards (everything it writes is under the
gitignored `data/recheck/`). The other half ("the timer is listed") needs the install, so T28 waits with T07 (status `manish`). The recheck unit got
the same network wait as the scan (T07's review notes).

---

## P4 — One source of truth (SQLite)

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|

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
**Decision (Manish, 2026-10-10: "you decide, in my best interest"; claude):** **do not import.** The scores come from the pre-rubric prompt of 2026-10-04
(the DB was cleared on purpose that day), 20 of the 45 are ≥ 70 and would become final, and any job still open is re-scored by the next scan. Anyone who disagrees
can run `python scripts/import_json_history.py --apply`. The old `state/*.json` files stay on disk (his data; safe to delete).

---

## P5 — Features

| ID | Task | Status | Owner | Size | Needs |
|---|---|---|---|---|---|

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

T41, T42, T43, T50, T51, T52, T55 and T63 were verified 2026-10-07, T80 on 2026-10-11 (Done log).

**T80 · User guide.** (Manish, 2026-10-11: no web UI, a guide instead; replaces T45.) One `docs/00-user-guide.md` that tells a new person, in order: install, where the resume
goes, which `config.json` field changes what (`profile`, `seeking`, `not_suitable`, `min_score`, `max_posted_age_days`, `top_n`), which words to edit in `job_hunt/prefilter.py`
for titles and locations, how to add companies (`discover`), how to read the CSV, run it daily, what to do when something fails.
*Done when:* every setting the guide names exists in the code (a test checks), and each step was run once in an empty directory.
**Implemented (claude, 2026-10-11, 0d0f9b0).** `docs/00-user-guide.md`, `scripts/check_filter.py` (try the pre-filter on one job after editing the word lists), `tests/test_user_guide.py` (14 tests) and `tests/test_check_filter.py` (5). The guide's settings, `.env` variables, pattern names, commands, flags, paths, links and example jobs are all checked against the program; the run in an empty directory was a fresh `git clone` (details in the Review queue). It found two real bugs, fixed on the way: T81 and a wrong placement in `docs/07`. **For Manish:** sections 3 (the `.env` trap) and 5 (the word lists) are the ones to read first; the guide assumes a reader who edits files but does not read Python.
**Review notes (2026-10-11, claude): verified** (Done log), with one wording fix (section 3 said "Three variables … (and `MIN_SCORE`)" and then "those four lines") and one line in section 5 for the T77 fix. New Inbox item T85: the example config's persona contradicts this fork.

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

New findings go here with the next free ID (next: **T88**), an evidence tag and the
file:line. Manish or the triaging agent moves each one into a priority table.

| ID | Finding | Evidence | Added by |
|---|---|---|---|
| T86 | **33 of the 93 rows of `open_matches.csv` carry scores from the old prompt.** After the first full run (T09, 2026-10-12) the file lists 60 jobs scored that day and 33 scored on 2026-10-04, before rubric v7/v8 (old: mean 79.0, six at 90; new: mean 81.1, fifteen at 90). A `scored` row is final, so the 105 old-prompt jobs still on their boards were "already scored" and kept their score; the earlier note that open jobs are re-scored by the next scan (T34) holds only for jobs the retired JSON files alone knew. Possible fix: set the 2026-10-04 rows (145, or just the 33 listed) back to `discovered` so the next scan re-scores them (33–105 calls on 3.5; the old scores stay in `data/jobs.db.bak-2026-10-12`), or leave them and accept that the file mixes two prompts. It rewrites stored scores in his database, so Manish's call | measured (SQL on `data/jobs.db`, `output/open_matches.csv`) | claude |
| T84 | **Jobs in Indian cities the pre-filter's city list lacks are rejected for location.** `LOCATION_INDIA_PATTERN` knows 11 cities and the word `india`; a job whose location is only e.g. `Coimbatore`, `Indore`, `Nagpur`, `Bhubaneswar` or `Lucknow` (no `India`, no state code) is rejected "does not match target locations". On the fetch of 2026-10-11 (39,713 jobs) 362 jobs sit in such Indian places, 26 of them with a title that passes (24 Accenture "Custom Software Engineer"/"Application Developer" roles in Coimbatore, Indore, Nagpur and Bhubaneswar; 2 InMobi in Lucknow), 2 of those posted within 7 days. T77 added `LOCATION_INDIA_MORE_PATTERN` (states, UTs, 40-odd cities) for its own purpose; reusing it in `location_is_india` would let these through. Question: does Manish want India jobs outside the 11 cities scored (he wrote "India or remote")? Not changed: it widens what reaches Gemini | measured (`location_is_india`, saved fetch) | claude |
| T82 | **One unexplained failure of an existing test in one full run.** 2026-10-11, once in six full runs of the suite (the other five, three of them back to back, passed): `tests/test_export_from_db.py::test_worth_applying_uses_the_scans_min_score_when_there_is_a_config` failed; the file alone passes, and I did not capture the failure message. The test builds its own database and `config.json` in a temp directory, so a shared-state or timing cause is suspected, not shown. If it recurs, run the full suite with `-x` and keep the output. **2026-10-13:** 10 more consecutive full runs (923 tests each, no coverage), 0 failures; not explained, not reproduced | measured (1 failure in 6 runs; not reproduced); cause unknown | claude |
| T69 | Low-priority notes from the 2026-10-07 review, no action proposed: (a) structured scoring (T41) hard-codes temperature 0.1 and ignores `gemini_temperature` (T60) — `llm_utils.score_job_structured_with_gemini`; (b) the deprecated non-Gemini scorer still cuts the resume at 2,500 and each JD at 1,500 characters — `scanner.score_batch`; (c) the T61 word `embedded` would also reject "Backend Engineer – Embedded Finance" (0 such titles in 34,416); (d) one full scan writes ~5.3 MB of DEBUG log, so T16's 5 MB × 3 rotation keeps about the last 3 scans; (f) structured scoring (T41, opt-in) still caps a stack mismatch at 60 in code (`combine_subscores`), while the T73 rubric uses 50; (g) generic "Senior Engineer" / "Engineer II/III" titles (~250 India jobs on 2026-10-06; Micron, Microchip, Thermo Fisher, Target India, NI, Anaplan, CrowdStrike, MongoDB) match no include word — mostly hardware, but Target/Anaplan/MongoDB use them for software; not measured further; (e) the production `data/jobs.db` still has the pre-T29 schema and `user_version` 0: its next scan runs T29's columns and T30's one-time Workday repair (checked on a copy: 30,367 rows kept, 0.19 s) | measured (a, b by reading the code; c, d, e by running it) | claude |

---

## Review queue

The implementer adds a row when a task reaches `review`; the verifier removes it.

| ID | Commit(s) | Implementer | Evidence (command → result) |
|---|---|---|---|
| T85 | 9a49634 | claude | **Red first:** `pytest tests/test_example_config_persona.py` → 4 failed (the persona phrases in both files; the three sentences differ from the guide's). Real command: `autopilot init` in an empty directory → `config.json` holds the guide's three sentences and `load_config()` accepts it (`min_score` 70). Gates: 923 passed (also under `unshare -rn`), coverage 92.74%, ruff/mypy clean. **Design choice to check:** the guide's examples (a 3-year backend engineer, Bengaluru) are the template, so a user who does not edit them is scored as that profile, consistent with the fork's filter and rubric; the alternative was `<years> YOE <role>` placeholders, which would be sent to Gemini verbatim. Existing `config.json` files are untouched | |
| T83 | ea80c07 | claude | Real command in an empty directory: `autopilot init; ls -A` → `.env companies.json config.json data output resume` (no `state`; `data` comes from the logger). `tests/test_init_dirs.py` (2, red first) + `test_init_project_scaffolds` updated (it asserted `state/` exists). `bash -n run_daily.sh` parses; the script itself was not run (it starts a real scan). Gates: 915 passed (also under `unshare -rn`), coverage 92.74%, ruff/mypy clean. An existing `state/` folder is untouched | |
| T76 | 09f3617 | claude | **Red first:** `pytest tests/test_workday_maintenance.py` → 2 failed, the log showing the three cryptic `Workday fetch failed for a/site at offset 0: Expecting value…` warnings (one per tenant). **Against the real library:** two local servers (tenant answers `POST` with 303 to another host's `/maintenance-page`) and the adapter's own `http_post`: the real `requests` response has `history [303]`, `url http://localhost:<port>/maintenance-page`; `workday._redirected_away` returns it, and `""` when the final host is the tenant's. After: one WARNING per scan naming the URL and saying the boards are fetched next time; the board is incomplete with reason `Workday maintenance: redirected to <url>` (T33 counts no miss, as before); a normal answer and an on-host redirect are unchanged (2 guard tests). Gates: 913 passed (also under `unshare -rn`), coverage 92.74%, ruff/mypy clean. **Not done / not verified:** no retry later in the run; Workday's real maintenance page is gone, so the real target is known from the 2026-10-10 measurement only. **Check yourself:** `pytest tests/test_workday_maintenance.py -q` | |
| T75 | a465be9 | claude | **On a copy of the production database (43,466 rows, 2026-10-13):** `EXPLAIN QUERY PLAN` of `SELECT * FROM jobs WHERE global_id = ? LIMIT 1` `SCAN jobs` → `SEARCH jobs USING INDEX idx_jobs_global_id (global_id=?)`; bare lookup **2.18 ms → 0.024 ms**, `get_job` 2.84 → 0.45 ms (it still runs `init_db` per call); `init_db` on the copy builds the index in 0.04 s; 300 random ids return the same rows with and without it; `PRAGMA integrity_check` ok. `tests/test_db_lookup_index.py` (5): the SQL each of `get_job`, `has_job`, `update_job_status`, `update_job_details` really sends is captured with sqlite3's trace hook and run through `EXPLAIN QUERY PLAN`; the 4 plan tests were red before the index. Gates: 909 passed (also under `unshare -rn`), coverage 92.69%, ruff/mypy clean. **Saving per scan is inferred** (about 35,000 lookups × 2.4 ms ≈ 80 s of a 48.5-minute scan), not timed in a scan. **Check yourself:** `python3 -c "import sqlite3; c=sqlite3.connect('data/jobs.db'); print(c.execute('EXPLAIN QUERY PLAN SELECT * FROM jobs WHERE global_id=?',('x',)).fetchall())"` → `SEARCH … idx_jobs_global_id` (your database gets the index at the next `init_db`, i.e. the next scan or `doctor`) | |
| T87 | 05fb89f | claude | `pytest tests/test_db_details.py` failed on 2026-10-13 (`Funnel: … too old 1 | queued 0`) with and without T75's index; fixed by posting "yesterday". Found the second one by running the suite with the code's clock +20 days (a throw-away plugin, not committed): the remaining failures were tests that read the real clock, i.e. artifacts of the simulation. 909 passed, also under `unshare -rn` | |
| T09 | 4f3d83a | claude | `./run_daily.sh` (real `data/jobs.db`, `config.json`, 224 boards, `min_score` 70, 7-day window), 19:20–20:08 IST on 2026-10-12, **48.5 min**, `data/scan.log` last line `Scan finished with exit code 0`. Funnel line: `fetched 33652 | India 17104 | already scored 105 | pre-filter rejected 31920 | too old 1310 | queued 317 | scored 317 (gemini-3.5-flash-lite 316, gemini-3.1-flash-lite 1) | failed 0 | left for next scan 0`; fetch 5.0 min, descriptions 70 s, scoring 39.3 min. **Done-when read from the artifacts:** SQL `select count(*) from jobs where substr(scored_at,1,10)='2026-10-12'` → 317 (status `scored` 462 = 145 + 317); `output/jobs_2026-10-12.csv` has 317 rows and a `Model` column; table `scans` holds the run with a finish time. 60 of 317 scored ≥ 70, 29 ≥ 85; `open_matches.csv` 93 rows. T77 live: 55 jobs rejected as `names a non-India place`; T78 live: 14 boards stopped at the window, 0 jobs closed (first run with sighting memory), 3,206 rows at `missed_scans` 1. **Caveats:** (1) one job (Amazon SDE 2, AFT Inventory, 85) was scored by `gemini-3.1-flash-lite` after a `Connection reset by peer` on 3.5, shown in the Model column; (2) `autopilot doctor` had migrated the production DB in place before I took the backup, so `data/jobs.db.bak-2026-10-12` is the migrated file (30,367 rows before and after; the pre-migration file is gone); (3) 33 of the 93 open matches are old-prompt scores, T86. T06 (Telegram) and T07 (timer) are Manish's and were not needed for a manual run. **Check yourself:** `tail -3 data/scan.log`; `python3 -c "import sqlite3; print(sqlite3.connect('data/jobs.db').execute(\"select score_model,count(*) from jobs where substr(scored_at,1,10)='2026-10-12' group by 1\").fetchall())"` → `[('gemini-3.1-flash-lite', 1), ('gemini-3.5-flash-lite', 316)]` | |

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
| T70 | Which Gemini model scores better (3.5 vs 3.1); keep 3.5 primary | 9445456, 3bc1c13 (numbers) | The implementer's four score files were no longer on disk, so re-measured the same day (2026-10-08) on the pre-T73 rubric it used: `score_golden_set.py --arms current --model gemini-3.1-flash-lite` from a worktree at 560a6e8 (rubric hash checked; 82/82 answered) + the reviewer's same-day 3.5 run of that rubric (`…/scratchpad/r/full_v4_a.scores.json`) → `--from-scores`: at 70 `apply` 14/14 for both; false positives 3.5 **2**, 3.1 **11** (claimed 10); precision 92% vs 69% (claimed 71%); AUC 0.959 vs 0.956, CI [-0.025, +0.022]; between models mean \|diff\| 8.3, 12 pass/fail changes at 60 and at 70 (claimed 8.0–8.4, 11–14); 3.1 minus 3.5: `no` +6.9, `maybe` +5.0, `apply` +1.7 (claimed +7.5 / +0.7). Independent 3.5 spot-check (mine): the 11 jobs 3.1 passes wrongly at 70, scored once each on 3.5 with that rubric → 2 of the 10 answered ≥ 70 (g16, g17: 75), 1 failed (503). Recommendation holds on precision. Also seen (not part of T70): on the T73 v6 rubric, one run each, 3.1 ranked *better* (AUC 0.990 vs 0.956, CI [+0.003, +0.079]) and found g1, but with 3 false positives at 70 vs 0; not re-run on v7. Not reproduced: 3.5's run-to-run noise (needs a second 3.5 run) and the 1.8 s median (3.1 answered in 15–28 s this evening) | verified · claude-b · 2026-10-08 |
| T73 | Rubric v7: skip postings that require a stack or domain Manish lacks | 3bc1c13 + fix b6f4775 | First sent back (2026-10-08, claude-b): v6 scored `apply` job g1 (Expedia) 50 in 10 of 11 runs on 3.5 (v4: 75–85), reading a responsibilities "languages such as Kotlin, Java or C#" as a mandate. Re-verified 2026-10-10 on v7: the diff is rule 4 only (+ its tests, docs, CHANGELOG); the committed `SCORING_RUBRIC` equals v6 at cfadad7 with the measured rule 4 swapped in (rebuilt from the measurement script via `ast`, 4,023 chars) and HEAD's. The reviewer's saved runs (`…/scratchpad/r/full_v7_a/b.scores.json`, `full_v4_a.scores.json`) through `score_golden_set.py --from-scores` reproduce every CHANGELOG number: `apply` 14/14 ×3; FP at 60 5 → 0/0, at 70 2 → 0/0; AUC 0.959 → 0.971/0.973 (CIs include 0); v7 runs 3.1 points apart, 0/1 flips; held-out identical. **My own live check on 3.5 (24 calls, model pinned, HEAD rubric):** g1 ×5 → 85, 75, 85, 75, 85 (+ 85 in the apply pass); v4's 5 false positives at 60 (g16, g17, g27, ab6, ab22) → 50, 45, 45, 50, 50, each reason naming the real requirement (Java+Spring mandatory, Golang required, video-games industry, JVM language, C#/.NET); all 14 `apply` → 75–90 (14/14 ≥ 70). Gates at HEAD (89274ce): 685 passed, coverage 92.58%, no-network 685 passed, ruff and mypy clean | verified · claude-b · 2026-10-10 |
| T31 | `draft N` / `mark N` read the last completed scan from SQLite | 4e337d7 | Reviewer, on a copy of the implementer's scratch scan, clean worktree at HEAD, `unshare -rn`: `autopilot export` (last scan) lists the jobs in exactly the order `db.last_scan_jobs` returns (2 = 2); `mark 2 applied` marked CSV row 2's URL. The rule keeps T10's meaning (N = CSV row N of the last scan). Note: on the deprecated non-Gemini path the CSV lists only worth-applying jobs while N counts every scored job | verified · claude · 2026-10-10 |
| T32 | `export` reads data/jobs.db | ffea468 | Reviewer, copy of the production DB + a `config.json` with only `min_score` 60, `unshare -rn`: `autopilot export --min 60 --days 30` → 38 rows, URLs identical and in the same order as `SELECT url FROM jobs WHERE status IN ('scored','notified') AND score >= 60 AND substr(scored_at,1,10) >= date('now','-30 days') ORDER BY score DESC, scored_at, id` (38); Worth Applying from `min_score`. `load_config` only exits without `config.json`, which export checks first. Production DB SHA-256 unchanged | verified · claude · 2026-10-10 |
| T33 | first_seen / last_seen; closed jobs; partial fetches never count as misses | 239b122 | Reviewer caught before the commit that a partial fetch (Workday page failure after page 1 — novartis at offset 20 in the 2026-10-07 scan log — time budget, job cap) was counted as complete. Measured: Accenture (at its 2,000 cap) shared 1,966 URLs between 2026-10-08 and 2026-10-10; of 15 sampled missing ones, 2 were still live. The fix flags early stops per board; reviewer re-ran `tests/test_closed_jobs.py` at 239b122 → 16 passed, and disabling the partial-board skip → 1 failed (`test_a_board_that_stopped_early_counts_no_misses`). Not run by the reviewer: a 3-scan live sequence (the implementer's live closures were 2 Amazon jobs, both HTTP 404) | verified · claude · 2026-10-10 |
| T34 | Retire the JSON state files; data/jobs.db is the one record | fb25e31 | Done-when `grep -rn "last_scan.json\|job_history.json\|seen_jobs.json" job_hunt` → nothing (exit 1). Reviewer's real scan on T34's code in a fresh `init` dir (1 board, 1 job scored on 3.5): no `state/` created; `scans` row finished; `export` and `draft 1`'s lookup read the DB; funnel `scored 1 (gemini-3.5-flash-lite 1)`. `scripts/import_json_history.py` dry run on copies: 45 would be imported (40 from `job_history.json` alone, 15 ≥ 70), DB hash unchanged. Reviewer's recommendation: do not import (pre-rubric scores of 2026-10-04 would become final; open jobs are re-scored by the next scan) — question under T34 | verified · claude · 2026-10-10 |
| T39 | Every scan rewrites output/open_matches.csv | 1b206a7 | Reviewer, `scanner._write_open_matches` on a copy of the production DB: 33 rows = the SQL rule, same order; after marking row 1 `applied` → 32 rows, that job gone, the rest unchanged; no `.tmp` left. Rows scored before T29 have no stored posted date, so a posted-date window keeps them (undated kept by design) until T33 closes them | verified · claude · 2026-10-10 |
| T44 | `draft` writes keyword_gaps.txt (posting terms the resume lacks) | 33ff041 | Reviewer: `tests/test_keywords.py` 18 passed; on real golden-set postings against the real resume: Nike g16 → missing Spring / Spring Boot (its mandatory stack), Sureify g17 → missing Go (required); probes "go-getter", "Go above and beyond", NoSQL, HTML/XML → no match; "Spring 2026 batch" → Spring (a season word: cosmetic, hint list only) | verified · claude · 2026-10-10 |
| T05 | One `min_score` (70), set in `config.json` only | bda04eb | Reviewer: every `min_score` reader goes through `settings.min_score_of` (grep); the real `load_config` in the repo directory (his `.env`, whose `MIN_SCORE` line is now a comment, + `config.json`) → 70; real `./run_daily.sh --limit 5` in a clean worktree at `2225284` (secret-free config, no API key, dummy resume) → first line `Min score: 70 \| Top N: 5`, exit 0. The stated reason (92% vs 86% precision) was the pre-T73 rubric's: reworded (T05's notes). Not run: a Telegram alert at 70 | verified · claude · 2026-10-10 |
| T62 | "python" allowed in job titles | 4b2ef97 | Reviewer: `should_evaluate_job` from worktrees at `4b2ef97^` and `4b2ef97`, each in its own process, over the saved 2026-10-08 fetch (39,873 jobs) → survivors 1,745 → 1,792, **+47, 0 removed, every added title contains "python"** (Citi 16, Cisco 7, JPMorgan 4, Motorola 3). Not measured: Gemini scores of the 47 (not part of the done-when; real scans will show them, 11 posted within 7 days) | verified · claude · 2026-10-10 |
| T26 | Phenom adapter; BCG added through `discover` | a18c25a | Reviewer, real network: `fetch_company_jobs` on BCG → 101 jobs, 101 unique ids, 96 India, complete; 3 pre-filter survivors, `enrich_job` → job-specific JSON-LD descriptions of 8,461–8,623 chars (three hashes); list order not by date (40 of 100 pairs), so no window stop. `companies.json` and the packaged copy identical (SHA-256) | verified · claude · 2026-10-10 |
| T02 | Posted-date window on by default (7 days); adapters skip older jobs | 5001dcd | Reviewer: real `./run_daily.sh --limit 5` in a clean worktree (no key) → `Posted-date filter: last 7 day(s)` and the done-when line **`254 job(s) skipped as posted more than 7 day(s) ago`** (the implementer said that wording did not exist), funnel fetched 2,377 / too old 254 / queued 43, exit 0. Eightfold order over whole boards, measured by the reviewer: Lam 108, Morgan Stanley 109, Qualcomm 580, UKG 88 jobs → **0** violations (the implementer's saved output had no Eightfold rows). Qualcomm A/B: no window 3 in-window survivors, 7-day window 3, same ids, 10 requests. Oracle HCM / SmartRecruiters order and the other boards' request counts read from the implementer's saved output, not re-run. Trade-off logged as T78 | verified · claude · 2026-10-10 |
| T08 | `setup_cron.sh` removed; docs point at the systemd timer | 50d9135 | Reviewer: `grep -rn setup_cron .` (excluding `.venv`, `.git`, `data`, `output`) → CHANGELOG (history), this board, and one sentence in `docs/01-install.md` saying it is gone; `SETUP.md`, docs/04 and docs/08 no longer name it; the file does not exist | verified · claude · 2026-10-11 |
| T74 | AI Engineer / Forward Deployed Engineer titles; rubric rule 8 caps heavy-AI requirements | 0c3ba2b | Reviewer, 2026-10-11, `gemini-3.5-flash-lite` pinned, rubric unchanged since 0c3ba2b (0 diff lines): `score_golden_set.py --csv scripts/golden_set_ai.csv --arms current --model gemini-3.5-flash-lite` → 75/75 answered, **6 pass at 70 vs the old rubric's 23, `no` among them 3 vs 19 (precision 17% → 50%)**, the one `apply` found; `score_golden_set.py --arms current --model …` on the original 82 → 0 false positives at 60 and 70, `apply` 13/14 (j7 90/90 → 45, the heavy-AI posting the clause targets), AUC 0.976 vs v7 0.971/0.973, 1–2 pass/fail changes vs v7 (v7 vs v7: 0–1); `measure_score_variance.py --ids g8` ×5 → 45, 50, 90, 45, 40 (borderline, its required list asks for hands-on LLM/agentic prototyping; label question in T59). Pre-filter: survivors 1,792 → 1,900, 0 removed (worktrees, 2026-10-10). The 3 AI-set false positives are steady or flip without the clause (ai33, ai41, ai44 ×3). Found on the way: rule 1 caps a Hyderabad role (T79). Score files: `data/golden_runs/*_2026-10-11*` | verified · claude · 2026-10-11 |
| T80 | User guide (`docs/00-user-guide.md`), `scripts/check_filter.py`, tests that check the guide against the code | 0d0f9b0 | Reviewer: read the whole guide against the code (score cap 400 / `0` = none in `scanner.py`, CSV columns in `exporter.py`, rubric facts, example configs identical); `tests/test_user_guide.py` + `test_check_filter.py` pass; **5 deliberate errors planted in the guide** (a default, an example row, an unknown flag, a misspelt key, the cap) → each turned a test red; `scripts/check_filter.py` on 5 jobs gave the expected KEPT/REJECTED with the filter's reasons. Fixed: the "three/four variables" wording | verified · claude · 2026-10-11 |
| T81 | `.env` template leaves name, resume path, top_n to `config.json` | 17c83e3 | Reviewer: real `autopilot init` in an empty directory → the four candidate lines are comments; with `config.json` set to `Test Person` / `resume/me.md` / top_n 3, `load_config()` returns exactly those (min_score 70). Manish's own `.env` still has the old live lines (same values today): see T81's notes | verified · claude · 2026-10-11 |
| T78 | A board cut at the posted-date window counts misses for stored jobs inside the window | 54f74cc | Reviewer's own run through the real scanner: scratch `init` directory, only Qualcomm (Eightfold), `closed_after_missed_scans` 1, two stored jobs the live board does not return (posted 2 and 60 days ago), no Gemini key → `Fetch stopped at the posted-date window …`, `1 job(s) marked closed`; the 2-day job `missed_scans` 1 and closed, the 60-day job 0 and open. Mutation (treat a windowed board like a full one) → 4 tests red | verified · claude · 2026-10-11 |
| T77 | A remote flag no longer carries a job whose location names a non-India place | 52f1a60 + review fix | Reviewer found false rejections (`IND - Remote`, `Remote (Full Time - Remote)`, `Remote - IST`, …) and fixed them (T77's notes). On the 2026-10-11 fetch (39,713 jobs): survivors 1,878 → 1,817 with T77 and with the fix; 0 real decisions changed by the fix; 842 distinct remote locations swept with a passing title → only the 4 non-place strings flip to kept. 19 new tests (14 red before the fix) | verified · claude · 2026-10-11 |
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
| Web UI for configuration (T45) | Manish, 2026-10-11 | Too much work for the benefit; the user guide (T80) covers it. Design kept at `docs/superpowers/specs/2026-10-10-web-ui-design.md`. Reopen only if he asks. |
| Playwright for custom portals; scraping Naukri/LinkedIn; multiple resume profiles | Gemini web, Antigravity | High cost and ban risk. Reopen only with a concrete plan and measured payoff. |
