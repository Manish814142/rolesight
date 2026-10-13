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
| Use my own resume | the resume file and `candidate.resume_path` | [3](#3-set-up-your-files) |
| Say who I am, what I want and what I never want | `candidate.profile`, `candidate.seeking`, `candidate.not_suitable` | [4](#4-the-settings-file-configjson) |
| See fewer or more matches | `candidate.min_score` | [4](#4-the-settings-file-configjson) |
| Look only at newer jobs | `candidate.max_posted_age_days` | [4](#4-the-settings-file-configjson) |
| Allow or block job titles (Java, Data Engineer, …) | the title words in `job_hunt/prefilter.py` | [5](#5-which-jobs-reach-gemini-the-word-lists) |
| Allow or block places | the location words in `job_hunt/prefilter.py` | [5](#5-which-jobs-reach-gemini-the-word-lists) |
| Scan more companies | `autopilot discover --add` | [6](#6-add-companies) |
| Get alerts on Telegram | `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | [4](#4-the-settings-file-configjson) |
| Run it every day by itself | `scripts/systemd/install.sh` | [8](#8-run-it-every-day) |

If you only do one thing: put your resume in, write the three profile sentences, add your Gemini key.
Everything else has a working default.

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

- **Use `pip install -e .` (with `-e`).** The `-e` makes the installed program read the files in this folder,
  so the edits in section 5 take effect. A plain `pip install .` copies the code and your edits would do nothing.
- If `python3 --version` prints 3.10 or lower, pip stops with `requires a different Python: 3.10.12 not in '>=3.11'`.
  Use a newer interpreter for the `venv` line, e.g. `python3.11 -m venv .venv`.
- `pip install -e .` takes about half a minute (measured: 32 s).
- Every later session: `cd RoleSight && source .venv/bin/activate` first.

## 3. Set up your files

```bash
autopilot init
```

`autopilot init` creates whatever is missing and skips what already exists: `config.json` (your settings),
`.env` (your keys), `resume/YOUR_RESUME.md` (a template) and the company list `companies.json`.
All of them stay on your computer; `config.json`, `.env` and your resume are kept out of git.

1. **Your key.** Open `.env` and replace `your_gemini_api_key_here` with your key:
   `GEMINI_API_KEY="…"`.
2. **Your resume.** Copy the template and replace its text with your resume, as plain text or Markdown:
   `cp resume/YOUR_RESUME.md resume/my_resume.md`. Then set `candidate.resume_path` in `config.json` to
   `resume/my_resume.md`. The **whole file** is sent to Gemini with every job (see [PRIVACY.md](../PRIVACY.md)).
3. **Your profile.** Edit the settings in section 4.
4. **Check it:** `autopilot doctor`. Each line starts with `PASS`, `WARN` or `FAIL`. A `WARN` for Telegram is
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
| `llm_provider` | `gemini` | Leave as `gemini` |
| `gemini_api_key` | — | Your key; usually put in `.env` instead (`GEMINI_API_KEY`) |
| `gemini_model` | `gemini-3.5-flash-lite` | Which Gemini model scores. Don't change without a reason: scores differ between models |
| `gemini_scoring_mode` | `single` | `single` scores one job per call (accurate). `batch` is faster but was measured to inflate scores. Leave as `single` |
| `fetch_workers` | 8 | How many companies are fetched at once. Lower it if your connection struggles |
| `max_jobs_to_score_per_run` | 400 | Most jobs scored in one run, newest first; the rest wait for the next scan. `0` = no limit. Gemini's free tier allows about 500 calls per model per day |
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

Before any job is scored, a free local filter in **`job_hunt/prefilter.py`** drops what obviously doesn't fit.
It saves Gemini calls (each costs time and a share of the free daily quota). A job the filter rejects is never
scored, so a wrong word here hides jobs from you. The lists are tuned for one person (a 3-year backend
engineer in India), so a different person should read them once.

Open `job_hunt/prefilter.py`. The word lists are the text between quotes, separated by `|`.

### Pre-filter patterns

| Name | What it decides | Edit it to… |
|---|---|---|
| `TITLE_INCLUDE_PATTERN` | A title must contain **at least one** of these words to continue | add a role you want, e.g. `\|data\s*engineer` |
| `TITLE_EXCLUDE_PATTERN` | A title with **any** of these words is rejected (checked first) | remove a word you want to see (`java`); add one you never want |
| `LOCATION_INDIA_PATTERN` | Places that count as "in India": a job in one of them passes the location check, even if other countries are listed too | add a city |
| `LOCATION_EXCLUDE_PATTERN` | Regions that count as "not workable from India", e.g. a remote job tied to the US | add a country or city to reject |

The order: the exclude words are checked first, then the include words, then the location. A job that the board
flags as "remote" passes the location check only if its location names no place: "Remote" passes, "Singapore" or
"Remote - Poland" is rejected (some boards flag their foreign offices as remote). Words that are not places ("Full
time", "Contract", "IST", "Office") and India's code `IND` keep the job. "Senior" is not
excluded on purpose (in India it often means 3–6 years). `\b` means "word boundary" and `\s*` means "optional
space"; copy the style of the words next to the one you add.

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

(`Data Engineer` is rejected because no include word matches it. `Java Developer` is rejected by the exclude
list.) These rows are checked against the real filter by a test, so they cannot drift from the code.

### Change a word, then check it

1. Make a copy of `job_hunt/prefilter.py` if you want a way back (or use `git diff` / `git checkout
   job_hunt/prefilter.py`).
2. Edit one word. To **remove** a word from a list, delete the word and one `|`. To **add** one, type `|word`
   before the closing quote of the list.
3. Save, then ask the filter about a job, without running a scan:

```bash
python scripts/check_filter.py "Java Developer" "Bengaluru, India"
```

It prints `KEPT` (the job would be scored) or `REJECTED — <the filter's reason>`. Add `--remote` if the job
board flags the job as remote.

Worked example (run in a fresh copy for this guide): `Java Developer` / `Bengaluru, India` printed
`REJECTED — Title matched exclude pattern: 'Java'`. After deleting `|java` from `TITLE_EXCLUDE_PATTERN`, it
printed `KEPT`. After adding `|data\s*engineer` to `TITLE_INCLUDE_PATTERN`, `Data Engineer` / `Pune, India` also
printed `KEPT`. Undoing the edits restored `REJECTED`.

A changed filter applies to jobs seen before as well: a job the old filter rejected is checked again by the
next scan. A job already scored keeps its score.

### The scoring text is also tuned to one person

Whatever passes the filter, Gemini scores with a fixed rubric in `job_hunt/llm_utils.py`
(`SCORING_RUBRIC`). It contains one person's facts: "about 3.3 years of experience" and "Node.js, TypeScript,
Python", plus caps for stack mismatch and for AI/ML requirements. If you are not that person, edit those
sentences to your own stack and years, then check the effect with `python scripts/score_golden_set.py` on jobs
you label yourself (about 150 Gemini calls). The rubric's behaviour was measured only for the person it was
written for.

## 6. Add companies

`companies.json` lists the career boards that get scanned (about 220 companies). Do not edit it by hand:
the `discover` command checks that a board is live, really belongs to the company and has jobs in India.

```bash
autopilot discover --add "Figma, Some Company" --report report.csv --out verified.json --merge companies.json
```

- Names can be pasted in any format. `--add-file paste.txt` reads a file instead.
- `--merge companies.json` adds the verified ones to the list and re-checks every existing entry, so it takes
  **about 3 minutes** (measured: 3 m 21 s for 2 names against 224 boards).
- Read `report.csv`: the `verdict` column says `verified` or `no live board on supported ATSs`. A company with
  its own career site that is not on a supported system (Zerodha was the test case) cannot be scanned.
  A name that is already in the list is `verified` and nothing new is added.
- Back up `companies.json` first (`cp companies.json companies.backup.json`).

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

The scan writes `output/jobs_YYYY-MM-DD.csv` (only the jobs scored in that scan, best first; a new file each
time) and `output/open_matches.csv` (every job above `min_score` that you have not marked as applied and that
is inside the window). Open either in a spreadsheet.

| Column | What to do with it |
|---|---|
| Role, Company, Location, Posted | What and where |
| Score (%) | 0–100 from Gemini. Use it to **order your reading**, not as a verdict |
| Reason | One sentence on why. **Read this before trusting the score** |
| Worth Applying | `Yes` when the score is at least `candidate.min_score` |
| Application URL | The company's own page. Apply there |
| LinkedIn people | A LinkedIn search for people at that company, to find someone for a referral (needs a LinkedIn login) |

Other commands that read what the last scan saved (none of them needs a key, except `draft`):

```bash
autopilot export --min 85            # the last scan again, only scores of 85 or more
autopilot export --days 7 --min 70   # every job scored in the last 7 days
autopilot mark 1 applied             # row 1 of the last scan: applied | interview | rejected | offer | none
autopilot draft 2                    # a tailored resume and cover letter for row 2, in output/<company>-<date>/
```

`draft` makes 3 Gemini calls (measured: 16 s) and writes the files for you to **review and send yourself**.
After `mark`, `export` shows an **Application** column with the status and date.

## 8. Run it every day

By hand, with a log (`run_daily.sh` uses the `.venv` folder from section 2):

```bash
./run_daily.sh                      # window and min score come from config.json
./run_daily.sh --posted-within 3    # one run with another window
```

The log goes to `data/scan.log`. To have your computer do it daily, the systemd **user** timer
(Linux; nothing is installed until you run this):

```bash
scripts/systemd/install.sh              # every day at 09:00, catches up a missed run
scripts/systemd/install.sh --at 07:30   # another time
scripts/systemd/install.sh --uninstall
```

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
