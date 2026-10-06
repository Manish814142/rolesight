# 01 — Install & first run

From a fresh checkout to the first CSV of scored jobs. It takes about 15 minutes of setup;
the first scan then takes about 35 minutes (measured on 2026-10-04 with 215 companies).

## Prerequisites

- **Python 3.11 or newer** (the repo's `.venv` uses 3.12).
- **A Gemini API key.** It's free: [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
- **Your resume as Markdown or plain text.** Gemini reads it as-is.
- Optional: a Telegram bot, for alerts ([05](05-outputs-and-notifications.md#telegram-optional)).

Not needed: TinyFish or OpenRouter keys. Those were part of the upstream project and were removed here.

## 1. Install

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[gemini,dev]'
```

Or with `uv`: `uv venv --python 3.12 && uv pip install -e '.[gemini,dev]'`.

- The **`gemini` extra is required.** It installs `google-genai`; without it, every scoring
  call fails and jobs stay unscored.
- **`dev`** adds pytest, ruff and mypy.
- **`mcp`** (optional) adds the Claude Code MCP server ([06](06-mcp-and-skill.md)).
- **Don't install from `requirements.txt`.** `google-genai` is commented out there.
- **Don't run `pip install autopilot-jobhunt`.** That installs the upstream package from
  PyPI, not this fork.

Check that it worked:

```bash
autopilot --help        # prints the command list
```

## 2. Configure

```bash
cp config.example.json config.json
cp job_hunt/data/env_example .env
```

Both files are gitignored. Never commit them.

**`.env`** holds the keys:

```bash
GEMINI_API_KEY=your-key
# optional
# TELEGRAM_TOKEN=...
# TELEGRAM_CHAT_ID=...
```

**`config.json`** holds the candidate profile. Gemini reads these fields with every job, so
write them for the person you're searching for:

```json
{
  "llm_provider": "gemini",
  "gemini_model": "gemini-3.5-flash-lite",
  "candidate": {
    "name": "<your name>",
    "resume_path": "resume/<your-name>.md",
    "profile": "<years> YOE <role>. Stack: <your main skills>",
    "seeking": "<role types, cities, remote policy>",
    "not_suitable": "<roles you never want to see>",
    "min_score": 70,
    "top_n": 5
  }
}
```

The example config holds only fields the pipeline reads. Every key is documented in
[07](07-config-and-scoring.md).

## 3. Add your resume

```bash
cp resume/YOUR_RESUME.md resume/<your-name>.md     # then replace the contents
```

Point `candidate.resume_path` at it. Every `resume/*.md` file except the template is
gitignored, so your real resume stays out of git. The whole file is sent to Gemini with
each job ([PRIVACY.md](../PRIVACY.md)).

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
Results saved to CSV: output/jobs_2026-10-04_1.csv
```

For a quick trial first, `autopilot scan --limit 5` scans only the first 5 companies.

## 6. Read the results

Open the newest `output/jobs_*.csv` in a spreadsheet. Rows are sorted best score first.
Read the **Reason** column before trusting a score. Apply through the
**Application URL**, which is the company's own posting.

What the columns and files mean: [05](05-outputs-and-notifications.md).

## 7. Run it daily

Scheduling isn't set up yet (task T07 on the [board](tasks.md)). Until it is, run it by hand:

```bash
./run_daily.sh --posted-within 7    # same scan, each output line timestamped into data/scan.log
```

Don't use `setup_cron.sh`. It installs an outdated command that bypasses `run_daily.sh`
(T08).

## Next

- [04 — Companies & scanning](04-companies-and-scanning.md): add companies and understand the scan.
- [07 — Config & scoring](07-config-and-scoring.md): tune the profile and the threshold.
