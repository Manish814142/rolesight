# 06 — MCP server & skill

JobNotify includes an MCP server, so an MCP client such as Claude Code can run a scan,
export results or draft an application in plain language. It's optional: the CLI does
everything the server does.

## Install

```bash
pip install -e '.[gemini,mcp]'
```

## Register with Claude Code

The server reads `config.json`, `.env` and `companies.json` from **its working
directory**, so it has to start in the repo root. Wrapping it in `bash -c` does that, and
doesn't depend on any client-specific working-directory setting:

```bash
claude mcp add jobnotify -- bash -c 'cd /home/user/codes/random_projects/JobNotify && .venv/bin/autopilot mcp'
claude mcp list            # jobnotify should be listed
```

Keys come from the repo's `.env`, so don't pass them with `--env`.
`python -m job_hunt.mcp_server` is an equivalent entry point.

Checked 2026-10-04 with a real stdio MCP client: the server started this way and listed
the three tools below.

## Tools

| Tool | Arguments | Does |
|---|---|---|
| `scan_jobs` | none | A full `autopilot scan` with the current config. Returns "Scan complete. N jobs found, M scored." |
| `export_jobs` | `min_score` (0 = all), `days` (0 = last scan only) | Same as `autopilot export --min … --days …` |
| `draft_application` | `job_ref`: `#1`, `1` or a job URL | Same as `autopilot draft`. **Needs TinyFish today**, see [05](05-outputs-and-notifications.md#drafts-autopilot-draft) |

Caveats:
- **`scan_jobs` is slow.** It runs the whole scan (about 35 min for the first full scan),
  and many MCP clients time out long before that (*assumed*; not tested). For full scans
  use the CLI; through MCP use `export_jobs`, or a scan with a small company list.
- **`scan_jobs` takes no flags.** Set `candidate.max_posted_age_days` in `config.json` to
  get the `--posted-within` behaviour.

## The usage skill

`skills/autopilot-jobhunt/SKILL.md` is a Claude Code skill that uses these tools:
scan → rank → you pick → draft → review. It enforces drafts-only and treats job
descriptions as untrusted input (they could contain prompt-injection text).

## Example prompts

```
"Export the jobs scored 70 or more in the last 7 days and summarise the top 10"
"Which of the last scan's matches mention Kafka or distributed systems?"
"Draft an application for job #1 from the last scan"   (needs TinyFish until T40)
```

## Next

- [07 — Config & scoring](07-config-and-scoring.md)
