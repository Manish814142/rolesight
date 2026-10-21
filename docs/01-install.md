# 01 — Install & first run

From a fresh checkout to the first CSV of scored jobs. (To change a setting or a word list afterwards, the
[user guide](00-user-guide.md) says which file and which line.) It takes about 15 minutes of setup;
the first scan then takes about 35 minutes (measured on 2026-10-04 with 215 companies).

## Prerequisites

- **Python 3.11 or newer** (the repo's `.venv` uses 3.12).
- **A Gemini API key.** It's free: [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
- **Your resume as Markdown or plain text.** Gemini reads it as-is.
- Optional: a Telegram bot, for alerts ([05](05-outputs-and-notifications.md#telegram-optional)).

Not needed: TinyFish or OpenRouter keys. Those belonged to the original project and were removed.

## 1. Install

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Or with `uv`: `uv venv --python 3.12 && uv pip install -e '.[dev]'`.

- **`google-genai`** (Gemini) is a core dependency (T51), so every install above includes it;
  without it every scoring call fails and jobs stay unscored. The `gemini` extra is kept as an
  empty alias.
- **`dev`** adds pytest, ruff and mypy.
- **`mcp`** (optional) adds the Claude Code MCP server ([06](06-mcp-and-skill.md)).
- **`pip install -r requirements.txt`** also works: runtime dependencies only (no pytest/ruff/mypy),
  and no `autopilot` command; run `python -m job_hunt …` from the repo root.
- **RoleSight is not on PyPI.** Install it from a clone, as above. `pip install autopilot-jobhunt` installs the
  original project's package, a different tool.

Check that it worked:

```bash
autopilot --help        # prints the command list
```

## 2. Configure from your resume (one command)

```bash
rolesight init --resume ~/Downloads/my_cv.pdf      # .pdf, .md or .txt
```

It creates the settings files (`config.json`, `.env`, `rubric.md`, `resume/`), asks for your free Gemini key if
`.env` has none ([aistudio.google.com/apikey](https://aistudio.google.com/apikey); saved to `.env`), and then drafts,
with 2 Gemini calls (3 for a PDF):

- in `config.json`: your name, `profile`, `seeking`, `not_suitable`, the title filter (`titles`) and `resume_path`;
- `rubric.md`: the scoring rubric with your years (counted from the dates of your jobs) and your stack;
- for a PDF, `resume/<name>.md`: your resume as text, which the scan sends with every job. Check it.

It prints what it wrote, including the years and the jobs they were counted from. **It is a draft:** read the
candidate part of `config.json` and `rubric.md`, and change what is not you: a resume does not say which jobs you
would rather not take (a Java developer who wants Node.js roles must add `java` to `exclude` by hand). Run it again
with `--yes` to replace the candidate settings; the previous files are kept as `.bak`. `config.json`, `.env`,
`rubric.md` and `resume/*.md` (except the template) are gitignored: never commit them.

### Or configure by hand

`rolesight init` without `--resume` writes the defaults (the example profile: a 3-year Node.js backend engineer). Add `--countries "United Kingdom, Germany"` to look
outside India ([user guide](00-user-guide.md#looking-for-jobs-outside-india)).
Put your key in `.env` (`GEMINI_API_KEY="…"`), copy `resume/YOUR_RESUME.md` to `resume/<your-name>.md`, replace its
text and point `candidate.resume_path` at it, then edit the candidate part of `config.json` and the facts in
`rubric.md`. Every key is documented in [07](07-config-and-scoring.md) and, step by step, in the
[user guide](00-user-guide.md). The whole resume file is sent to Gemini with each job ([PRIVACY.md](../PRIVACY.md)).

## 3. Check what the filter keeps

```bash
rolesight check-filter "Senior Backend Engineer" "Bengaluru, India"
```

`KEPT` means a job with that title and place would be scored; `REJECTED — …` says why not.

## 4. Check the environment

```bash
autopilot doctor
```

It checks that `data/jobs.db` is writable, makes one 1-token Gemini call, checks the
Telegram bot (shown as `WARN` if Telegram isn't configured, which is fine), and checks
network access to the main ATS hosts. Fix any `FAIL` before scanning
([08](08-troubleshooting.md)).

## 5. First scan

```bash
autopilot scan --posted-within 7
```

Why the 7-day window: about 1,270 jobs pass the pre-filter across the 215 companies.
Gemini's free tier allows roughly 1,000 scoring calls a day (2 models × 500 per day,
per Google's published free-tier limits; not verified against the live quota). The
window keeps the first scan to about 226 jobs (measured 2026-10-04). Jobs left over are
not lost: older ones are saved as `skipped` and come back if you widen the window, and
unscored ones stay `discovered` and are retried on the next scan.

What you'll see (abridged, from the 2026-10-04 run):

```
=== Scan started — 215 companies to check ===
Posted-date filter: last 7 day(s) only (jobs without a posted date are kept)
Fetching 215 companies with 8 parallel workers...
Fetch complete in 8.9 min
[1/215] Scanning Amazon...
  Fetched ... job(s) directly via ATS adapter
  ... job(s) passed the pre-filter — queued for scoring
...
Full descriptions fetched for 170 of 226 survivor(s) in 32 s
Scoring 226 job(s) one per Gemini call (~4.2 s each)...
1044 job(s) skipped as posted more than 7 day(s) ago
=== Scan complete — 215/215 companies, 226 jobs found, 5 top matches (34.3 min) ===
Results saved to CSV: output/history/jobs_2026-10-04_1.csv
```

For a quick trial first, `autopilot scan --limit 5` scans only the first 5 companies.

## 6. Read the results

Open `output/open_matches.xlsx` (the jobs this scan found to apply to) or `output/last_scan.xlsx` (everything it scored) in a spreadsheet.
Rows are sorted best score first, the Score is the first column, and every column has a filter. Every scan also keeps a dated copy in
`output/history/`.
Read the **Reason** column before trusting a score. Apply through the
**Application URL**, which is the company's own posting.

What the columns and files mean: [05](05-outputs-and-notifications.md).

## 7. Run it daily

Run it by hand with the runner, which timestamps every output line into `data/scan.log`:

```bash
./run_daily.sh                      # the posted-date window comes from config.json (default 7 days)
./run_daily.sh --posted-within 3    # one run with another window; `all` switches it off
```

To run it every day, switch the schedule on. It is **off until you do** (nothing in RoleSight schedules anything by itself):

```bash
autopilot schedule on                # every day at 09:00 local time
autopilot schedule on --at 07:30     # another time
autopilot schedule status            # ON or OFF, the time, and the next run
autopilot schedule off               # removes everything `on` wrote
```

`on` uses the systemd **user** timer where `systemctl --user` works (Linux), and a single marked line in your crontab
otherwise (Linux without a user manager, macOS).

**If the computer is off at the scheduled time** (say 06:00): with the systemd timer the scan runs when your user manager
next starts, which is **when you next log in** (`Persistent=true`; documented in systemd.timer(5)), and it first waits up to
5 minutes for the network. It does not run at boot before you log in, unless you run `loginctl enable-linger $USER` once.
With cron the run is **skipped** and the next one is the next day at the scheduled time. Either way nothing is lost for good: the
posted-date window is 7 days by default, and jobs already seen are never scored twice, so the next scan picks up what was
posted in between. Only a job that was posted and taken down while the computer was off is missed. Your other crontab lines are never touched, and turning one
method on removes the other, so a day has one run. `--method systemd|cron` chooses. On Windows `on` explains how to make
the task in Task Scheduler. It runs `run_daily.sh`, so the log is `data/scan.log`, and it needs the `config.json` and the
keys a manual scan needs (`on` warns if `config.json` is missing).

The same timer by hand, and the monthly company-list check (`--with-recheck`), are in `scripts/systemd/install.sh`:

```bash
scripts/systemd/install.sh --at 07:30
systemctl --user list-timers job-hunt-scan.timer
systemctl --user start job-hunt-scan.service   # one scan right now
scripts/systemd/install.sh --uninstall
```

Each run first waits up to 5 minutes for a network connection (`scripts/systemd/wait-online.sh`; it gives up with a
line in `data/scan.log`). A user timer cannot wait for the system's `network-online.target`, and a run made up at
login (`Persistent=true`) could otherwise start before Wi-Fi is connected and fetch nothing.

The old `setup_cron.sh` is gone: it installed a cron line that bypassed `run_daily.sh` (T08).

## Next

- [04 — Companies & scanning](04-companies-and-scanning.md): add companies and understand the scan.
- [07 — Config & scoring](07-config-and-scoring.md): tune the profile and the threshold.
