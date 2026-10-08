# 08 — Troubleshooting

Start with `autopilot doctor`. Then look in `data/autopilot.log` (full DEBUG detail);
every job's pre-filter decision, score and reason is there.

## Setup

| Symptom | Cause | Fix |
|---|---|---|
| `config.json not found` / `companies.json not found` | Not run from the repo root, or no config yet | `cd` to the repo; `cp config.example.json config.json` ([01](01-install.md)) |
| Every job logs `Gemini scoring error: google-genai is not installed` | `google-genai` is missing from the environment (an install from before T51, when it was optional) | `pip install -e .` or `pip install -r requirements.txt` |
| `[FAIL] Gemini Quota` in `doctor` | Missing, placeholder or invalid `GEMINI_API_KEY`, or the quota is used up | Check `.env`; try again the next day if the quota is gone |
| After `autopilot init`, a scan fetches nothing ("No direct ATS detected and no valid careers_url") | `init` copies an outdated 140-company list with no ATS entries (T50) | Use the repo's `companies.json` |
| `pip install autopilot-jobhunt` behaves like a different tool | That's the upstream PyPI package | Install this repo with `pip install -e .` |

## During a scan

| Symptom | Cause | Fix |
|---|---|---|
| `Temporary issue or rate-limit on gemini-…, retrying in N s` | 429/503 from Gemini | Normal now and then; it retries, then tries the fallback model |
| `N job(s) could not be scored (LLM error/quota) — left as 'discovered'` | Gemini failed for those jobs, usually the daily quota | Nothing is lost: they're scored on the next scan. Narrow the window (`--posted-within`) to stay under about 1,000 calls a day |
| `Gemini model gemini-…: daily quota exhausted; skipped for the next N h` | That model's 500/day free-tier limit is used up | Nothing: the fallback model scores the rest of the run; the skipped model is tried again after the reset (T64) |
| The log says "Gemini quota exhausted … scoring stopped" | The daily quota is gone: scoring stops once 3 jobs in a row fail on every model (T03); the rest stay `discovered` | Nothing: they are scored on the next scan |
| `Workday <tenant>/<site>: 600s budget spent, stopping at N jobs` | A slow Workday tenant | Jobs past N are missed for this scan only |
| `<ATS> fetch failed for <slug>: …` (e.g. `… still downloading after 900s`), then `No open jobs found` for that company | The board errored or trickled past the hard deadline. The adapter returns no jobs for this scan. These warnings go to the console (and `data/scan.log` via `run_daily.sh`) and to `data/autopilot.log` | Retried automatically on the next scan |
| `No open jobs found via <ats> adapter` for a company, every scan | The board has died or the company moved ATS | `autopilot discover --recheck --merge companies.json --report /tmp/r.csv` and review the diff ([04](04-companies-and-scanning.md#health-check---recheck)) |
| `llm_provider 'openrouter' was removed` | Old config | Set `"llm_provider": "gemini"` |

## Results

| Symptom | Cause | Fix |
|---|---|---|
| A job you expected isn't in today's CSV | (1) the pre-filter rejected it, (2) it was scored in an earlier scan (CSVs only hold that scan's jobs), (3) it's outside `--posted-within`, (4) Workday's India search didn't return it | `grep -i "<title words>" data/autopilot.log` shows the decision; `autopilot export --days 30` shows earlier scores |
| The same job appears several times | Fixed in T47 for Workday paging. If it still happens, the board may list the job twice under different requisitions | Compare the URLs; each should be a different requisition |
| Many jobs score exactly 90 | Scores cluster; the rubric (T48) shifts calibration but not ranking | Read the Reason column to separate them; sub-scores are planned (T41) |
| `run_daily.sh` prints `min_score=70` but the scan uses 60 | `.env`'s `MIN_SCORE` overrides it (T05) | Set `MIN_SCORE` in `.env` to the value you want |
| A large `scan.log` in the repo root | The log used to live there, unrotated; nothing writes it now (T16) | Safe to delete. `data/autopilot.log` rotates at 5 MB and keeps 3 older files |

## Drafting and Telegram

| Symptom | Cause | Fix |
|---|---|---|
| `draft`: "This job is not in the database" or "no stored description" | The job was never scanned, or was scanned before descriptions were stored (T29) | Re-run a scan, or pass the description with `--jd-file FILE` |
| `draft`: `Job #N not in last scan` | N is larger than the number of jobs the last finished scan scored (in `data/jobs.db`) | Use a number from the latest CSV, or pass the URL |
| `Telegram failed: HTTP 404` | Invalid bot token (seen 2026-10-03) | New token from @BotFather; run `autopilot doctor` |
| `Telegram failed: HTTP 400 … chat not found` | Wrong `TELEGRAM_CHAT_ID`, or you never messaged the bot | Message the bot, then read `chat.id` from `getUpdates` ([05](05-outputs-and-notifications.md#telegram-optional)) |
| Hundreds of Telegram messages | One alert per job ≥ `min_score`, plus the digest | Raise `min_score` |

## Tools

| Symptom | Fix |
|---|---|
| `sqlite3: command not found` | Use Python: see [05](05-outputs-and-notifications.md#the-seen-job-database-datajobsdb) |
| `discover` wrote `discovery_report.csv` / `verified_companies.json` into the repo | Pass `--report` and `--out` with scratch paths |
| `validate` (or `harvest --force`) rewrote `companies.json` | `git checkout companies.json`; use `discover` instead ([04](04-companies-and-scanning.md)) |

Still stuck? Add a row to the Inbox of the [task board](tasks.md#inbox) with what you ran
and what you saw.
