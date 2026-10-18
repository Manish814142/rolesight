# 00 — User guide: what to change, and where

For someone who wants to **use** RoleSight and change how it behaves, without reading the code. Every
section says the file, the setting and what happens when you change it. The other guides
([README](README.md)) explain *why*; this one explains *where*.

RoleSight fetches open jobs from company career boards, throws away the ones that obviously don't fit
(free, local), has Google Gemini score the rest against your resume, and writes the matches to a
spreadsheet (CSV), best first. It **never applies** to anything; you do that yourself.

## 1. What you can change

| I want to… | Change this | Where |
|---|---|---|
| Set everything up from my resume in one step | `rolesight init --resume my_cv.pdf` | [3](#3-set-up-your-files) |
| Use my own resume | the resume file and `candidate.resume_path` | [3](#3-set-up-your-files) |
| Say who I am, what I want and what I never want | `candidate.profile`, `candidate.seeking`, `candidate.not_suitable` | [4](#4-the-settings-file-configjson) |
| See fewer or more matches | `candidate.min_score` | [4](#4-the-settings-file-configjson) |
| Look only at newer jobs | `candidate.max_posted_age_days` | [4](#4-the-settings-file-configjson) |
| Allow or block job titles (Java, Data Engineer, …) | `candidate.titles` in `config.json` | [5](#5-which-jobs-reach-gemini-the-word-lists) |
| Change how a job is scored against me (years, stack) | `rubric.md` (`candidate.rubric_file`) | [5](#the-scoring-rubric-rubricmd) |
| Allow or block places | the location words in `job_hunt/prefilter.py` | [5](#5-which-jobs-reach-gemini-the-word-lists) |
| Scan more companies | `autopilot discover --add` | [6](#6-add-companies) |
| Get alerts on Telegram | `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | [4](#4-the-settings-file-configjson) |
| Run it every day by itself (off until you switch it on) | `autopilot schedule on` | [8](#8-run-it-every-day) |

If you only do one thing: add your Gemini key and run `rolesight init --resume` with your resume. It writes
everything that is personal for you to read and change. Everything else has a working default.

## 2. Install

You need **Python 3.11 or newer** and a free **Gemini API key** from
[aistudio.google.com/apikey](https://aistudio.google.com/apikey).

```bash
python3 --version        # must print 3.11 or higher
git clone <the-repo-url> RoleSight
cd RoleSight
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
autopilot --help         # prints the list of commands
```

- **Use `pip install -e .` (with `-e`).** The `-e` makes the installed program read the code in this folder, so an
  edit to the place rules in `job_hunt/prefilter.py` (section 5) takes effect. Your settings in `config.json` and
  `rubric.md` work either way.
- If `python3 --version` prints 3.10 or lower, pip stops with `requires a different Python: 3.10.12 not in '>=3.11'`.
  Use a newer interpreter for the `venv` line, e.g. `python3.11 -m venv .venv`.
- `pip install -e .` takes about half a minute (measured: 32 s).
- Every later session: `cd RoleSight && source .venv/bin/activate` first.

## 3. Set up your files

```bash
rolesight init                                   # the files, with defaults
rolesight init --resume ~/Downloads/my_cv.pdf    # your settings, drafted from your resume
```

(`rolesight` and `autopilot` are the same program.) `rolesight init` creates whatever is missing and skips what
already exists: `config.json` (your settings), `.env` (your key), `rubric.md` (how a job is scored against you),
`resume/YOUR_RESUME.md` (a template) and the company list `companies.json`. All of them stay on your computer;
`config.json`, `.env`, `rubric.md` and your resume are kept out of git. `.env` and `config.json` are created readable by you
only (mode 600), as they hold your key; `rolesight doctor` warns about an older one others can read (`chmod 600 .env config.json`).

1. **Your key.** Get a free Gemini key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Run
   `rolesight init --resume …` in a terminal and it asks for the key and saves it to `.env`; or open `.env` and
   replace `your_gemini_api_key_here` yourself: `GEMINI_API_KEY="…"`.
2. **Your resume and your settings: `rolesight init --resume FILE`.** `FILE` is your resume as `.pdf`, `.md` or
   `.txt` (from Word: *File → Save as → PDF*). One Gemini call reads it and writes:
   - into `config.json`: your name, the three profile sentences (section 4), the title words (section 5), the
     resume path, and `rubric_file`;
   - `rubric.md`: the scoring rubric rewritten with your years, stack and skills;
   - for a PDF, `resume/<name>.md`: the text of your resume (the scan sends this text with every job, so check it).

   It prints what it wrote. **It is a draft:** read the candidate part of `config.json` and `rubric.md`, and change
   anything that is not you. Run it again later with `--yes` to replace the candidate settings (the old ones are
   kept as `config.json.bak` and `rubric.md.bak`).
   Without `--resume`, set the resume yourself: copy `resume/YOUR_RESUME.md` to `resume/my_resume.md`, replace its
   text, and set `candidate.resume_path` to it. The **whole file** is sent to Gemini with every job (see
   [PRIVACY.md](../PRIVACY.md)).
3. **Check it:** `rolesight doctor`. Each line starts with `PASS`, `WARN` or `FAIL`. A `WARN` for Telegram is
   fine. A `FAIL` on one job-board host can be a one-off timeout (it happened once on Lever in the test run
   for this guide): run `doctor` again before worrying.

### A `.env` line beats `config.json`

Four variables in `.env` override the matching setting in `config.json` whenever they are not commented out:
`CANDIDATE_NAME`, `RESUME_PATH`, `MIN_SCORE` and `TOP_N`. A `.env` made by `autopilot init` today has them
commented out (`# RESUME_PATH=…`), so `config.json` decides. A `.env` made **before 2026-10-11** has three of them live,
with the template values, and silently beats whatever you wrote in `config.json`: your scan would then score
against the template resume. If you changed the resume path and the scan seems to ignore it, open `.env` and put
`#` in front of those four lines. The first lines of every scan show what is in force
(`Candidate: …`, `Min score: … | Top N: …`).

## 4. The settings file: `config.json`

Open `config.json` in any text editor. It is JSON: keep the quotes and commas, and save as plain text.
`config.example.json` is the same file with the defaults, if you want to start over. A setting you leave out
uses the default. A name that is not in the tables below is ignored without any message, so check spelling.

### config.json settings

| Setting | Default | What it changes |
|---|---|---|
| `candidate.name` | — | Your name, used in the prompt and in cover-letter drafts |
| `candidate.resume_path` | `resume/YOUR_RESUME.md` | Which resume file is sent to Gemini |
| `candidate.profile` | — | One line about you: years of experience, role, main skills. Gemini reads it with every job |
| `candidate.seeking` | — | What you want: role types, cities, remote or on-site. Gemini reads it with every job |
| `candidate.not_suitable` | — | What to score low: roles you never want to see. Gemini reads it with every job |
| `candidate.relocation_note` | — | A sentence added to cover-letter drafts |
| `candidate.min_score` | 70 | The score (0–100) that counts as a match: "Worth Applying = Yes", Telegram alerts and the end-of-scan list. It does not change what gets scored |
| `candidate.top_n` | 5 | How many matches the end-of-scan list in the log shows |
| `candidate.max_posted_age_days` | 7 | Only jobs posted in the last N days are scored. `null` switches the window off. Jobs with no posted date are always kept |
| `candidate.titles` | the default word lists | Which job titles are scored at all: `include`, `exclude`, `exceptions`, `generic_engineer_titles`. Section 5 |
| `candidate.rubric_file` | built-in rubric | The file with your scoring rubric, e.g. `"rubric.md"`. Without this line the built-in rubric is used. See [the scoring rubric](#the-scoring-rubric-rubricmd) |
| `candidate.cities` | `[]` | Leave empty to look at **all of India** (and remote jobs from India). To look only at some cities, list them: `["Pune", "Hyderabad", "Delhi NCR"]`. Usual alternative names match (Bangalore = Bengaluru, Gurgaon = Gurugram); remote jobs and jobs that name no city (just "India") are always kept |
| `llm_provider` | `gemini` | Leave as `gemini` |
| `gemini_api_key` | — | Your key; usually put in `.env` instead (`GEMINI_API_KEY`) |
| `gemini_model` | `gemini-3.5-flash-lite` | Which Gemini model scores. Don't change without a reason: scores differ between models |
| `gemini_scoring_mode` | `single` | `single` scores one job per call (accurate). `batch` is faster but was measured to inflate scores. Leave as `single` |
| `fetch_workers` | 8 | How many companies are fetched at once. Lower it if your connection struggles |
| `max_jobs_to_score_per_run` | 0 | Most jobs scored in one run, newest first; the rest wait for the next scan. `0` = no limit (the default since T118): Gemini's own daily limit is the limit, about 500 calls per model per day, and the scan goes on with the second model when the first has used its day |
| `telegram.token` | — | Telegram alerts, optional. Usually put in `.env` (`TELEGRAM_TOKEN`) |
| `telegram.chat_id` | — | Telegram alerts, optional. Usually put in `.env` (`TELEGRAM_CHAT_ID`) |
| `anthropic_api_key` | — | Only if `llm_provider` is `anthropic` (deprecated; never used in real runs). Leave as it is |
| `anthropic_model` | — | Same: leave as it is |
| `claude_cli_model` | — | Same: leave as it is |

**How to write the three profile sentences.** Gemini reads them next to your resume for every job, so be
specific and concrete:

- `candidate.profile`: `"3 YOE backend engineer. Stack: Node.js, TypeScript, MongoDB, AWS"`
- `candidate.seeking`: `"Remote, or hybrid in Bengaluru. Backend or platform roles"`
- `candidate.not_suitable`: `"Pure frontend, QA, support, management, internships"`

To see the effect of a change, run a small scan (section 7) and read the **Reason** column.

### .env variables

`.env` holds your keys. Each line is `NAME="value"`; a line starting with `#` is ignored.

| Variable | Overrides | Notes |
|---|---|---|
| `GEMINI_API_KEY` | `gemini_api_key` | Required. The one thing you must fill in |
| `GEMINI_MODEL` | `gemini_model` | Optional |
| `LLM_PROVIDER` | `llm_provider` | Optional; leave `gemini` |
| `TELEGRAM_TOKEN` | `telegram.token` | Optional. `TELEGRAM_BOT_TOKEN` also works |
| `TELEGRAM_CHAT_ID` | `telegram.chat_id` | Optional |
| `CANDIDATE_NAME` | `candidate.name` | Leave commented out, so that `config.json` decides |
| `RESUME_PATH` | `candidate.resume_path` | Leave commented out (see section 3) |
| `MIN_SCORE` | `candidate.min_score` | Leave commented out |
| `TOP_N` | `candidate.top_n` | Leave commented out |

A value in `.env` beats the same setting in `config.json`, except text like `your_…_here` or `YOUR_…`, which
counts as "not filled in".

## 5. Which jobs reach Gemini: the word lists

Before any job is scored, a free local filter drops what obviously doesn't fit. It saves Gemini calls (each costs
time and a share of the free daily quota). A job the filter rejects is never scored, so a wrong word here hides
jobs from you. Read the lists once, whoever drafted them.

### Job titles: `candidate.titles` in `config.json`

```json
"titles": {
  "include": ["back end", "software engineer", "developer", "node", "nodejs", "node.js"],
  "exclude": ["lead", "principal", "manager", "java", "qa", "intern"],
  "exceptions": ["technical staff"],
  "generic_engineer_titles": true
}
```

| Key | What it decides |
|---|---|
| `include` | A title must contain **at least one** of these to be scored |
| `exclude` | A title with **any** of these is rejected, checked first: seniority levels you don't want, roles you don't do, languages you don't use |
| `exceptions` | Phrases that don't count as excluded although they contain an excluded word: `"technical staff"` keeps "Member of Technical Staff" although `staff` is excluded |
| `generic_engineer_titles` | `true` also scores titles that say nothing about the job: only "Engineer" with a seniority or level ("Senior Engineer", "Engineer II"), or "software" and "engineer" in any order. Gemini judges them by the description |

How an entry matches: as **whole words, in any case** (`java` matches "Senior JAVA Developer" but not
"JavaScript"). **Spaces and hyphens inside an entry are optional**: `back end` also matches "Back-End" and
"backend". List variants separately (`node`, `nodejs`, `node.js`). Use words and `. + # / & -` only; `.net`,
`c#` and `c++` work as written. Without a `titles` block the defaults are used: the example config has them in
full (`config.example.json`), 35 include and 91 exclude entries written for a 3-year backend engineer. A `titles`
block is taken as written: a list you leave out is empty, and the scan and `check-filter` say so (`candidate.titles has
no "exclude" list…`); write `"exclude": []` if you really mean none. If an include entry contains an excluded word, so that
it can never pass, the scan says so at its start (`Title filter: include entry … can never pass`).

### Places: `job_hunt/prefilter.py`

The location rules are for jobs **in India** (the company list is built for India) and live in the code. To look
only at some cities, use `candidate.cities` (section 4) instead of editing them.

### Pre-filter patterns

| Name | What it decides | Edit it to… |
|---|---|---|
| `LOCATION_INDIA_PATTERN` | The word `india` and the main cities: a job in one of them passes the location check, even if other countries are listed too | add a city |
| `LOCATION_INDIA_MORE_PATTERN` | The rest of India: states, union territories and some 150 more cities, so "Coimbatore" or "Telangana" alone is enough | add a place you see rejected |
| `LOCATION_EXCLUDE_PATTERN` | Regions that count as "not workable from India", e.g. a remote job tied to the US | add a country or city to reject |

The order: the exclude words are checked first, then the include words, then the location. A job that the board
flags as "remote" passes the location check only if its location names no place: "Remote" passes, "Singapore" or
"Remote - Poland" is rejected (some boards flag their foreign offices as remote). Words that are not places ("Full
time", "Contract", "IST", "Office") and India's code `IND` keep the job. "Senior" is not excluded by default on
purpose (in India it often means 3–6 years).

### What the filter does with these

| Title | Location | Result |
|---|---|---|
| Senior Backend Engineer | Bengaluru, India | kept |
| Software Engineer | Remote - India | kept |
| Java Developer | Bengaluru, India | rejected |
| Engineering Manager | Pune, India | rejected |
| Data Engineer | Pune, India | rejected |
| Backend Engineer | Berlin, Germany | rejected |
| Account Executive | Mumbai, India | rejected |
| Backend Engineer | Coimbatore | kept |
| Senior Engineer | Pune, India | kept |
| Mechanical Engineer | Pune, India | rejected |

(`Data Engineer` and `Mechanical Engineer` are rejected because no include word matches them. `Java Developer` is rejected by the exclude
list. `Backend Engineer` in `Coimbatore` is kept because any Indian city or state counts as India, not only the main cities (T84). `Senior Engineer` is kept because a title that is only "Engineer" with a seniority or level ("Engineer II"), or "software" and "engineer" in any order, goes to Gemini to be judged by the description (T96).) These rows are checked against the real filter by a test, so they cannot drift from the code.

### Change a word, then check it

1. Open `config.json` and change one entry of `candidate.titles` (keep the quotes and commas). A copy of the file
   is your way back.
2. Ask the filter about a job, without running a scan:

```bash
rolesight check-filter "Java Developer" "Bengaluru, India"
```

It prints `KEPT` (the job would be scored) or `REJECTED — <the filter's reason>`, using your `config.json`
(titles and cities). Add `--remote` if the board flags the job as remote. (`python scripts/check_filter.py …` is
the same.)

Worked example (run in a fresh directory for this guide, with the default lists): `Java Developer` /
`Bengaluru, India` printed `REJECTED — Title matched exclude pattern: 'Java'`. After deleting `"java"` from
`exclude`, it printed `KEPT`. After adding `"data engineer"` to `include`, `Data Engineer` / `Pune, India` also
printed `KEPT`. Putting the two entries back restored `REJECTED`.

A changed filter applies to jobs seen before as well: a job the old filter rejected is checked again by the
next scan. A job already scored keeps its score.

### The scoring rubric: `rubric.md`

Whatever passes the filter, Gemini scores with a rubric: eight rules with score caps (for example "the role needs
far more years than you have: at most 50"). The built-in rubric was written and measured for one person (about
3.3 years of experience, Node.js, TypeScript and Python, India). `rolesight init` writes it to `rubric.md`, and
`rolesight init --resume` rewrites its facts for you: your years and the seniority bands that follow, your stack
and the languages outside it, the domains you have or lack. The eight rule headings and their caps stay as they
are; if Gemini changed them, `init` keeps the built-in text and says so.

Edit `rubric.md` like any text: change a fact that is wrong about you, keep the rule headings. `candidate.rubric_file`
in `config.json` names the file; delete that line to go back to the built-in rubric. The first lines of a scan
show which rubric is in force (`Scoring rubric: <id>`, `Rubric text: rubric.md`). Scores stored under an older
rubric keep their score; `python scripts/rubric_ids.py` shows which rubric scored how many jobs.

How good is a draft? Measured once, on the only person with labelled jobs (the example profile, 2026-10-14): settings
drafted by `init --resume` from his resume found the same 12 of 14 jobs he would apply to at 70, ranked his 82 labelled
jobs a little worse than his hand-tuned settings (AUC 0.931, against 0.955 and 0.953 the same day) and passed one more
job he would not apply to. Its title words kept every job his kept, plus roles in languages his resume lists
but his own lists exclude: only he knows he doesn't want those jobs. **A resume does not say what you would rather not do; add that
yourself** (`exclude`, `not_suitable`). If scores look wrong, read the **Reason** column of a small scan and fix the
sentence in `rubric.md` that caused it.

## 6. Add companies

`companies.json` lists the career boards that get scanned (about 1,500 companies). Do not edit it by hand:
the `discover` command checks that a board is live, really belongs to the company and has jobs in India.

```bash
autopilot discover --add "Figma, Some Company" --report report.csv --out verified.json --merge companies.json
```

- Names can be pasted in any format. `--add-file paste.txt` reads a file instead.
- `--merge companies.json` adds the verified ones to the list and re-checks every existing entry, so it takes
  **about 3 minutes for 224 boards** (measured: 3 m 21 s for 2 names) and **about 5½ minutes for about 1,500 boards** (measured 2026-10-16: 5 m 19 s for the recheck of 1,515 entries).
- Read `report.csv`: the `verdict` column says `verified` or `no live board on supported ATSs`. A company with
  its own career site that is not on a supported system (Zerodha was the test case) cannot be scanned.
  A name that is already in the list is `verified` and nothing new is added.
- Back up `companies.json` first (`cp companies.json companies.backup.json`).
- **To add hundreds at once**, use the archive harvest instead of typing names: `python scripts/harvest_board_urls.py --out seeds.txt`,
  then `autopilot discover --seeds seeds.txt --report r.csv --out v.json --merge companies.json --no-recheck --workers 20`
  (about 1 board per 0.15 s; read `r.csv`). The harvest lists boards by their web address, so it finds companies whose name you
  would not think to type. Run Workable and Recruitee with `--workers 3`: Workable refuses about half the requests of a long burst (HTTP 429; the scanner now waits and asks again).
- The whole method, with what to check in the report before you merge and where the list can still grow:
  [04 — Growing the list](04-companies-and-scanning.md#growing-the-list).

## 7. Run a scan and read the result

```bash
autopilot scan --limit 3 --posted-within 3
```

`--limit 3` scans only the first 3 companies, `--posted-within 3` looks at the last 3 days only (`all` = no
window). Measured in a fresh copy: 3 companies, 2,354 jobs fetched, 17 sent to Gemini, 17 scored, 3 min 15 s.
A full scan of the whole list is longer (about 35 minutes in the first real run, 2026-10-04). The last lines
of a scan are the **funnel**, which says where every job went:

```
Funnel: fetched 2354 | India 2167 | already scored 0 | pre-filter rejected 2058 | too old 279 | queued 17 | scored 17 (gemini-3.5-flash-lite 17) | failed 0 | left for next scan 0
```

The scan keeps two files at the top of `output/`, replaced by every scan, so you never look for the newest: **`open_matches.xlsx`**
(only what **this** scan found: its jobs above `min_score` that you have not marked as applied; a scan with nothing new leaves it
empty) and **`last_scan.xlsx`** (everything this scan scored, whatever the score). Each has a `.csv` twin. The dated record of every
scan, `jobs_YYYY-MM-DD.csv` and `.xlsx`, goes to `output/history/` and is never overwritten; drafts go to `output/drafts/`. Nothing is
deleted for you: remove old files from `history/` whenever you like, because `data/jobs.db` has every job. **Open the `.xlsx`.** It is the same table made easy to read: the header row and the Score and
Company columns stay in view when you scroll, every column has a filter (use it on **ATS**), Score is green from 85 and amber
from your `min_score`, and "Open" in the Application URL column is the link. The `.csv` is the same data for scripts; it is UTF-8
without a byte-order mark, so if you open it directly and a name such as "Karnātaka" shows as "KarnÄ…taka", choose **UTF-8** in
the import dialog (measured with LibreOffice 7.3 started headless: its default import garbled 5 cells of a 49-row file, and with
UTF-8 chosen none; the `.xlsx` has no such problem there; Excel was not tested).

**Opening the links.** "Open" and "Search" are real hyperlinks, and each program has its own rule for following one. **Excel** (Windows, Mac, the web): one plain click opens it; to select the cell without opening, hold the
click until the pointer turns into the cross, or move onto it with the arrow keys (Microsoft's page on links describes the desktop and web apps; Excel for Mac was not checked separately). **LibreOffice** (Linux, Windows, Mac): **Ctrl+click**
by default, a safeguard so that a click can select the cell; to open on a plain click untick Tools → Options → LibreOffice → Security → Options… → **Ctrl-click required to open hyperlinks** (the label is from LibreOffice 7.3; it is a
setting of your LibreOffice, not of the file, so no file can change it). **Google Sheets**: a link shows a small preview when you point at it and opens with one click (seen when pasting the table in; not tested further). If links
"do nothing" on a click, it is almost always this LibreOffice setting, not a broken file.

| Column | What to do with it |
|---|---|
| Score (%) | 0–100 from Gemini, first because the file is sorted by it. Use it to **order your reading**, not as a verdict |
| Company, ATS, Role, Location, Posted | Who, which hiring platform (`greenhouse`, `lever`, `workday`, …; turn on the spreadsheet's filter for **ATS** to apply only on the platform you prefer), what and where, and how fresh |
| Reason | One sentence on why. **Read this before trusting the score** |
| Application URL | The company's own page. Apply there |
| LinkedIn people | A LinkedIn search for people at that company, to find someone for a referral (needs a LinkedIn login) |
| Worth Applying | `Yes` when the score is at least `candidate.min_score` (always `Yes` in `open_matches`) |

Other commands that read what the last scan saved (none of them needs a key, except `draft`):

```bash
autopilot export --min 85            # the last scan again, only scores of 85 or more
autopilot export --days 7 --min 70   # every job scored in the last 7 days
autopilot mark 1 applied             # row 1 of the last scan: applied | interview | rejected | offer | none
autopilot draft 2                    # a tailored resume and cover letter for row 2, in output/drafts/<company>-<date>/
```

`draft` makes 3 Gemini calls (measured: 16 s) and writes the files for you to **review and send yourself**.
After `mark`, `export` shows an **Application** column with the status and date.

## 8. Run it every day

By hand, with a log (`run_daily.sh` uses the `.venv` folder from section 2):

```bash
./run_daily.sh                      # window and min score come from config.json
./run_daily.sh --posted-within 3    # one run with another window
```

The log goes to `data/scan.log`. To have your computer do it daily, switch the schedule on. It is **off by
default**; nothing schedules a scan until you run `on`:

```bash
autopilot schedule on                # every day at 09:00 (local time)
autopilot schedule on --at 07:30     # another time
autopilot schedule status            # is it on, at what time, when is the next run
autopilot schedule off               # back to no schedule
```

On Linux this is a systemd **user** timer: it runs while you are logged in, and a run missed while the computer was off is
made up **at your next login**; where that is not available, and on macOS, it is one line in your crontab (it runs only while
the computer is on, a missed run is skipped) that `off` removes again. Nothing is lost for good: the scan looks back 7 days
and never scores a job twice. On Windows
`on` tells you how to make the task in Task Scheduler. The scheduled scan needs the same `config.json` and keys as
a scan you start yourself.

Details and the monthly company-list health check: [01](01-install.md#7-run-it-daily).

## 9. When something goes wrong

| What you see | Why | What to do |
|---|---|---|
| `requires a different Python: 3.10.12 not in '>=3.11'` | Old Python | Use `python3.11 -m venv .venv` (or newer) |
| `config.json not found` | You are not in the project folder, or never ran `init` | `cd RoleSight`, then `autopilot init` |
| Scores look wrong for someone else's resume | `.env` still has a live `RESUME_PATH` | Section 3, "A `.env` line beats `config.json`" |
| A setting seems to be ignored | Spelling, or the wrong parent (`candidate.` or none) | Compare with the tables in section 4 |
| Everything is `FAIL` in `doctor`, or "quota" in the scan | The Gemini key is wrong, or the day's free quota (about 500 calls per model) is used up | Check the key in `.env`; wait for the daily reset (midnight Pacific time) and run again. Unscored jobs wait for the next scan |
| One host `FAIL` in `doctor` | A one-off timeout | Run `doctor` again |
| Not enough matches | The filter, `min_score` or the window is strict | `--posted-within all`, or lower `candidate.min_score`, or check section 5 |
| Too many weak matches | `min_score` is low | Raise `candidate.min_score` |

More: [08 — Troubleshooting](08-troubleshooting.md) · all settings in detail:
[07 — Config & scoring](07-config-and-scoring.md) · company scanning: [04](04-companies-and-scanning.md).
