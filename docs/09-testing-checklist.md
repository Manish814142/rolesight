# 09 — Testing checklist

How to confirm a change works: first the offline gates, then a real run through the
program itself.

## 1. Gates (offline, run before every commit)

```bash
pytest                    # whole suite; coverage gate 85% (pyproject.toml)
ruff check job_hunt       # CI also lints tests/ and conftest.py: ruff check job_hunt/ tests/ conftest.py
mypy                      # checks job_hunt/
```

Last recorded: 398 tests passing, coverage 89.99%, after the T30 review fix (2026-10-04).

**Tests must never touch the network.**

- `conftest.py` stubs `scanner.enrich_job` for every test and provides the `fake_llm`,
  `clean_env`, `sample_config` and `sample_job` fixtures.
- Stub `requests.get` / `requests.post` (or `adapters.base.http_get` / `http_post`) for
  adapters, `score_job_with_gemini` / `_get_genai_client_and_types` for Gemini, and
  `scanner.send_telegram` for Telegram.
- The suite logs to a temporary directory (`JOBNOTIFY_LOG`, set by `conftest.py`); it never touches `./scan.log`.

**CI.** `.github/workflows/ci.yml` runs the same gates on Python 3.11, 3.12 and 3.13, plus a
gitleaks secret scan. This fork isn't pushed anywhere yet (T01), so **CI doesn't run for
it**. The local gates are the only check.

## 2. CLI smoke tests (no keys needed)

```bash
autopilot --help                       # command list, exit 0
autopilot export --min 101; echo $?    # "No jobs with score >= 101 in last scan", no traceback
```

## 3. Environment

```bash
autopilot doctor
```

Expect `[PASS]` for SQLite, Gemini and the ATS egress checks. Telegram is `WARN` when
it isn't configured.

## 4. A real, small scan

This costs a few Gemini calls and writes to the real `data/jobs.db`, `state/` and
`output/`:

```bash
autopilot scan --limit 3 --posted-within 7
```

Check, in order:
1. The first log lines show the expected `Min score`, provider and model.
2. Each company logs `Fetched N job(s)` or `No open jobs found`.
3. `Full descriptions fetched for K of N survivor(s)` appears when Workday,
   SmartRecruiters or Oracle HCM jobs survived.
4. A new `output/jobs_*.csv`, best first, with Reason filled.
5. The DB status counts moved
   ([05](05-outputs-and-notifications.md#the-seen-job-database-datajobsdb)).

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
    p = StdioServerParameters(command="bash", args=["-c", "cd /home/user/codes/random_projects/JobNotify && .venv/bin/autopilot mcp"])
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
