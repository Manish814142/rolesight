# 05 — Outputs & notifications

Everything a scan writes, how to read it, and the optional channels on top. All of these
paths are gitignored.

## The CSV (primary output)

`output/jobs_YYYY-MM-DD.csv`. One file per scan; if the name is taken, the scan writes
`_1`, `_2`, … and never overwrites. Rows are **sorted best score first**. Row N of the CSV
is job N of the last completed scan, which `draft N` and `mark N` look up in `data/jobs.db` (table `scans`, T31).

| Column | Meaning |
|---|---|
| Company | `name` from `companies.json` |
| Role | Job title as the ATS gives it |
| Location | Raw location string from the ATS |
| Posted | `YYYY-MM-DD`, or Workday's relative text ("Posted 5 Days Ago") |
| Application URL | The company's own posting. Apply there |
| LinkedIn people | A LinkedIn people search for `<company> software engineer`, to find someone for a referral. Opening it needs you to be logged in to LinkedIn |
| Score (%) | Gemini's 0–100 fit score |
| Reason | Gemini's one sentence on why it scored that way. **Read this before trusting the number** |
| Worth Applying | `Yes` if score ≥ `min_score` |
| Scan Date | UTC date of the scan |

A column appears only when some job in the file has a value for it: **Stack** (from the deprecated non-Gemini
scorer) and, with `scoring_mode: structured`, **Stack fit**, **Role fit**, **Seniority fit**, **Location fit**,
**Min years** and **Capped by**. A default Gemini scan writes none of them (T36).
**Model** (T71) appears when some job in the file was scored by a model other than the default primary
`gemini-3.5-flash-lite`, i.e. the fallback answered (primary failed or out of quota) or `gemini_model` is set to another
model. The models score differently (T70: `gemini-3.1-flash-lite` gives weak fits ~7 points more), so compare scores
only within one model.

A CSV contains only jobs scored in that scan. Jobs scored on earlier days are in earlier
CSVs and in `state/job_history.json`.

**Reading it:** sort or filter on Score, read the Reason, then open the URL. The first real
scan (2026-10-04) had 74 rows ≥ 60, 67 ≥ 70 and 38 ≥ 80, and 21 jobs tied at exactly 90
(before the rubric; ties remain, T41). Treat the number as a ranking hint, not a verdict.

## `autopilot export`

Writes a fresh CSV from saved results. It needs no API keys.

```bash
autopilot export                    # last scan            → output/jobs_DATE.csv
autopilot export --min 70           # last scan, score ≥ 70
autopilot export --days 7 --min 70  # every job scored in the last 7 days → output/jobs_DATE_last7d.csv
```

It reads `state/last_scan.json` / `state/job_history.json`, not the DB (T32), except for the **Application**
column, which it looks up in `data/jobs.db` (read-only) and writes only when some exported job has been marked.

## Tracking applications: `autopilot mark`

```bash
autopilot mark 1 applied                 # job #1 of the last scan (= CSV row 1, the same job `draft 1` drafts)
autopilot mark https://… interview       # any job in data/jobs.db, by its URL
autopilot mark 1 none                    # clear a mistaken mark
```

Statuses: `applied`, `interview`, `rejected`, `offer`. Each mark stores the status and today's local date in
`application_status` / `application_date`; a later mark replaces the earlier one (only the latest is kept). It needs
no API keys and never contacts the employer: it only records what you did. `export` then shows e.g.
`applied 2026-10-08` in its Application column (T38).

## The seen-job database: `data/jobs.db`

SQLite, table `jobs`. Columns: `global_id` (the ATS's job ID; with `ats` it is the unique
key), `canonical_hash` (MD5 of title + company + location; fallback key and an index),
`url_hash`, `title`, `company`, `ats`,
`url`, `score`, `score_reason`, `status`, `discovered_at`, `scored_at`, and (T29) `location`,
`posted_at` and `description`. Skipped postings keep location and date only; queued ones keep
the description the scorer saw. Rows from before T29 have these empty. `score_model` (T71) is the
Gemini model that produced `score`; it is empty for rows scored before T71 and for the deprecated providers.
`application_status` / `application_date` (T38) are set by `autopilot mark`, independent of `status`.
Table `scans` (T31) has one row per scan run (`started_at`, `finished_at`); `draft N` / `mark N` mean job N among
the jobs scored during the last finished scan, best score first (equal scores in scoring order), as in its CSV.

| status | meaning | next scan |
|---|---|---|
| `skipped` | Rejected by the pre-filter or outside the posted-date window | Re-checked (cheap, local), so filter fixes and a wider window apply retroactively |
| `discovered` | Passed, not scored yet, **or scoring failed** | Scored again |
| `scored` | Gemini score stored | Final: never re-scored |
| `notified` | Scored **and** a Telegram alert was accepted (HTTP 200) | Final |

To look inside it (the `sqlite3` CLI may not be installed):

```bash
.venv/bin/python -c "import sqlite3; c=sqlite3.connect('data/jobs.db'); print(c.execute('select status,count(*) from jobs group by status').fetchall())"
```

Deleting `data/jobs.db` makes the next scan treat every job as new, so all of them are
scored again. That costs Gemini quota; use `--posted-within`.

**Keys (T30):** a posting is identified by `(ats, global_id)`, so two openings with the
same title, company and location are separate rows and both reach Gemini. The first real
scan had 22 such groups (34 extra rows) that the old title-based key had merged.
`PRAGMA user_version` records that Workday ids were re-derived from job URLs; this runs
once per database.

## State files: `state/`

| File | Contents | Used by |
|---|---|---|
| `last_scan.json` | Jobs scored in the latest scan, best first | `export` (no `--days`), MCP `scan_jobs` summary (`draft N` reads the DB since T31) |
| `job_history.json` | Every job ever scored (deduplicated by URL), with `scan_date` | `export --days N` |
| `seen_jobs.json` | URLs seen (a leftover from the old scanner) | nothing reads it; retiring it is T34 |

These overlap with the DB; consolidating them into SQLite is planned (T31–T34).

## Logs

| File | Contents |
|---|---|
| `data/autopilot.log` | Every run's full DEBUG log: each job's pre-filter decision, score and reason, plus the adapters' warnings. Rotates at 5 MB and keeps 3 older files (`autopilot.log.1` to `.3`); `JOBNOTIFY_LOG=<path>` moves it |
| `data/scan.log` | Timestamped console output of `./run_daily.sh` runs, with start and end banners and the exit code |

`LOG_LEVEL=DEBUG autopilot scan` shows the per-job detail on the console as well.

## Drafts: `autopilot draft`

```bash
autopilot draft 1          # job #1 of the last scan (= CSV row 1)
autopilot draft https://…  # any posting URL
```

It writes `output/<company>-<date>/`: `resume_<company>.md` (a tailored resume),
`cover_letter_<company>.md` and `application_info.txt`. **It never submits anything.**

Current limits:
- **The description comes from the database** (stored for queued jobs since T29). For a job
  the database doesn't have, or that was scanned before T29, pass `--jd-file FILE` with the
  pasted description (T40).
- It sends the whole resume to the cover-letter prompt (T14).
- **It uses `llm_provider`** for the LLM ([02](02-providers.md)).

## Telegram (optional)

The CSV is complete without it. Telegram only adds push alerts.

**Status:** the last sends (2026-10-03) failed with HTTP 404, which usually means a bad
bot token. Treat Telegram as off until `autopilot doctor` passes (T06).

### Set it up

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Send your bot any message, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `chat.id`.
3. Add to `.env`:

   ```bash
   TELEGRAM_TOKEN=123456:ABC...     # TELEGRAM_BOT_TOKEN also works
   TELEGRAM_CHAT_ID=123456789
   ```

4. Run `autopilot doctor` and look for `[PASS] Telegram Bot`.

Empty or placeholder values (`YOUR_…`, `…_here`) count as "not configured". The scan
then skips Telegram quietly.

### What gets sent

- **During scoring:** one alert **per job** with score ≥ `min_score`. It shows the
  company with its headcount badge, role, location, score, reason and link. A job whose
  alert is accepted is marked `notified`.
- **After the scan:** a digest of the top `top_n` matches. It sends "No new matches today"
  if there are none, and a separate message if some companies failed.

With `min_score` 60, the first real scan would have sent about 74 individual alerts
(*inferred* from its CSV). Set `min_score` with that in mind (T05).

## Next

- [06 — MCP server & skill](06-mcp-and-skill.md)
- [08 — Troubleshooting](08-troubleshooting.md)
