# 09 — Testing checklist

How to confirm a change works: first the offline gates, then a real run through the
program itself.

## 1. Gates (offline, run before every commit)

```bash
pytest                    # whole suite; coverage gate 85% (pyproject.toml)
ruff check job_hunt/ tests/ conftest.py   # the same paths CI lints
mypy                      # checks job_hunt/
```

Last recorded: 2,284 tests passing on Python 3.12 (2026-10-23, after T144's review, T153, T154 and T126), coverage 94.23%, ruff and mypy clean. Python 3.11 and 3.13 were last run on 2026-10-18 (1,808 + 1 skipped, `mcp` 2.3.0); CI runs all three on the next push.

**Tests must never touch the network.**

- `conftest.py` stubs `scanner.enrich_job` for every test and provides the `fake_llm`,
  `clean_env`, `sample_config` and `sample_job` fixtures.
- Stub `requests.get` / `requests.post` (or `adapters.base.http_get` / `http_post`) for
  adapters, `score_job_with_gemini` / `_get_genai_client_and_types` for Gemini, and
  `scanner.send_telegram` for Telegram.
- The suite logs to a temporary directory (`ROLESIGHT_LOG`, set by `conftest.py`); it never touches `./scan.log`.

**CI.** `.github/workflows/ci.yml` runs the same gates on Python 3.11, 3.12 and 3.13 (note that it lints
`job_hunt/ tests/ conftest.py`, not only `job_hunt/`) and a gitleaks scan of the whole history. Nothing publishes a package.

## 2. CLI smoke tests (no keys needed)

```bash
autopilot --help                       # command list, exit 0
autopilot export --min 101; echo $?    # "No jobs with score >= 101 in last scan", no traceback
autopilot schedule status              # "Daily scan: OFF (the default; …)"; reads only, changes nothing (T121)
```

Do not run `autopilot schedule on` on a working machine just to test it: it starts a real daily scan. The tests
([test_schedule.py](../tests/test_schedule.py)) run the real `install.sh` and the real subprocess calls against stand-in
`systemctl` and `crontab` programs; the one thing they cannot show is a real power-off and login.

## 3. Environment

```bash
autopilot doctor
```

Expect `[PASS]` for SQLite, Gemini and the ATS egress checks. Telegram is `WARN` when
it isn't configured.

## 4. A real, small scan

This costs a few Gemini calls and writes to the real `data/jobs.db` and
`output/`:

```bash
autopilot scan --limit 3 --posted-within 7
```

Check, in order:
1. The first log lines show the expected `Min score`, provider and model.
2. Each company logs `Fetched N job(s)` or `No open jobs found`.
3. `Full descriptions fetched for K of N survivor(s)` appears when Workday,
   SmartRecruiters or Oracle HCM jobs survived.
4. A new `output/history/jobs_*.csv`, best first, with the Score in the first column, Reason filled and the **ATS** column (third) filled on every row (T122, T128), and a `jobs_*.xlsx` of the same name beside it: open it and check the frozen header, the filter arrows, the green/amber scores and that Reason is readable (T128).
5. `output/last_scan.*` holds everything the scan scored (header only when it scored nothing), and `output/open_matches.*` holds only the jobs this scan scored at or above `min_score`, not marked applied; a scan
   that found nothing new leaves the header and no rows (T124). `"open_matches_scope": "all_open"` in `config.json`
   gives the rolling list of every unmarked match instead.
6. The DB status counts moved
   ([05](05-outputs-and-notifications.md#the-seen-job-database-datajobsdb)).

`--limit N` takes the first N companies of `companies.json`: Amazon, then Ashby boards in alphabetical order. On a
database that has never seen those jobs, Amazon alone queued 44 jobs for Gemini on 2026-10-17 (measured by fetching and
pre-filtering, no scoring), so "a few Gemini calls" holds only when the jobs were scored before. To choose the companies, or to keep your real `data/jobs.db` and `output/` as they are, run from an empty folder that has
its own `companies.json` (the companies you want), `config.json`, `.env` and the resume file: `scan` reads and writes
everything relative to the folder it is started in. Remove the `telegram` block and the `TELEGRAM_*` lines there if you
do not want phone alerts from a trial.

For a change that only affects fetching, call the adapter directly. That makes no Gemini
calls and writes no state:

```bash
.venv/bin/python -c "from job_hunt.adapters import fetch_company_jobs; \
jobs = fetch_company_jobs({'name':'Adyen','ats':'greenhouse','slug':'adyen'}); \
print(len(jobs), jobs[0].title if jobs else '-')"
```

## 5. MCP server

The server should list `scan_jobs`, `draft_application` and `export_jobs`
([06](06-mcp-and-skill.md)). Check it with a real client:

```bash
.venv/bin/python - <<'EOF'
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    p = StdioServerParameters(command="bash", args=["-c", "cd /path/to/rolesight && .venv/bin/autopilot mcp"])
    async with stdio_client(p) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        print([t.name for t in (await s.list_tools()).tools])
asyncio.run(main())
EOF
```

## 6. Drafts-only invariant

Any change near `drafter.py`, `tools.py` or `mcp_server.py` must still only write files
under `output/`. Nothing may submit, apply or fill in a form. Reviewers check this on
every diff ([SECURITY.md](../SECURITY.md)).

## 7. Recording results

When a task is finished, record the exact commands and their output in the task board's
Review queue ([tasks.md](tasks.md#review-queue)). The verifier re-runs them.
