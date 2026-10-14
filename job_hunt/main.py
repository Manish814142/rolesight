#!/usr/bin/env python3
"""
Usage:
  autopilot init              — set up working directory (first-time pip install setup)
  autopilot init --resume CV.pdf  — also draft your profile, title filter and rubric.md from your resume (Gemini)
  autopilot check-filter "Java Developer" "Pune, India"  — would this job be scored? (your config.json filter)
  autopilot doctor            — run environment and network sanity checks
  autopilot validate          — probe and prune 404/403 ATS boards from companies.json
  autopilot harvest           — probe all ATS engines and rebuild companies.json
  autopilot discover          — verify company names against ATS boards (see job_hunt/discovery.py)
  autopilot scan              — run daily job scan
  autopilot scan --posted-within 3  — only score jobs posted in the last 3 days (undated jobs kept)
  autopilot draft #1          — draft application for job #1 from last scan
  autopilot draft https://... — draft application for a specific URL (add --jd-file FILE to paste the description)
  autopilot export            — export last scan to CSV (output/jobs_YYYY-MM-DD.csv)
  autopilot export --min 60   — export only jobs with score >= 60
  autopilot export --days 7   — export jobs from last 7 days (requires scan history)
  autopilot export --days 7 --min 60  — combine filters
  autopilot mark #1 applied   — record an application: applied | interview | rejected | offer (none clears it)
  autopilot mark https://... interview  — the same for a job URL
  autopilot mcp               — run the MCP server over stdio (for Claude Code)
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from job_hunt.settings import load_env_file, min_score_of

_PLACEHOLDERS = {
    "YOUR_ANTHROPIC_API_KEY", "your_anthropic_api_key_here",
    "YOUR_GEMINI_API_KEY", "your_gemini_api_key_here",
}


def _is_placeholder(val: str) -> bool:
    return val in _PLACEHOLDERS or val.startswith("YOUR_") or val.endswith("_HERE") or val.endswith("_here")


def _use_env(val: str | None) -> bool:
    """An env var overrides config.json only if it's set and not a placeholder.

    Without the placeholder guard, the default `.env` template (which `autopilot
    init` writes with `your_..._here` values) would clobber real keys in
    config.json — the classic "config.json and .env don't compose" bug.
    """
    if not val:
        return False
    return not _is_placeholder(val)


def load_config() -> dict:
    load_env_file(".env")
    p = Path("config.json")
    if not p.exists():
        sys.exit("config.json not found.\nRun 'autopilot init' to set up your working directory.")

    config = json.loads(p.read_text())

    env_mapping = {
        "LLM_PROVIDER": "llm_provider",
        "CLAUDE_CLI_MODEL": "claude_cli_model",
        "ANTHROPIC_API_KEY": "anthropic_api_key",
        "ANTHROPIC_MODEL": "anthropic_model",
        "GEMINI_API_KEY": "gemini_api_key",
        "GEMINI_MODEL": "gemini_model",
    }

    for env_key, config_key in env_mapping.items():
        val = os.getenv(env_key)
        if val is not None and _use_env(val):
            config[config_key] = val

    config.setdefault("gemini_model", "gemini-3.5-flash-lite")
    # Direct ATS adapters + Gemini is the pipeline; TinyFish and OpenRouter were removed (T42).
    config.setdefault("llm_provider", "gemini")

    # Telegram is optional. Placeholder values from the templates are dropped so
    # every downstream check sees "not configured" rather than a bogus chat_id.
    tg_cfg = config.get("telegram")
    if isinstance(tg_cfg, dict):
        for k in ("token", "chat_id"):
            v = tg_cfg.get(k)
            if v is not None and not _use_env(str(v)):
                tg_cfg.pop(k)
    tg_token_env = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    tg_token = tg_token_env if _use_env(tg_token_env) else None
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID") if _use_env(os.getenv("TELEGRAM_CHAT_ID")) else None
    if tg_token or tg_chat_id:
        if "telegram" not in config:
            config["telegram"] = {}
        if tg_token:
            config["telegram"]["token"] = tg_token
        if tg_chat_id:
            config["telegram"]["chat_id"] = tg_chat_id

    cand_name = os.getenv("CANDIDATE_NAME")
    cand_resume = os.getenv("RESUME_PATH")
    cand_min_score = os.getenv("MIN_SCORE")
    cand_top_n = os.getenv("TOP_N")
    if cand_name or cand_resume or cand_min_score or cand_top_n:
        if "candidate" not in config:
            config["candidate"] = {}
        if cand_name:
            config["candidate"]["name"] = cand_name
        if cand_resume:
            config["candidate"]["resume_path"] = cand_resume
        if cand_min_score:
            config["candidate"]["min_score"] = int(cand_min_score)
        if cand_top_n:
            config["candidate"]["top_n"] = int(cand_top_n)

    return config


def load_companies() -> list:
    p = Path("companies.json")
    if not p.exists():
        sys.exit("companies.json not found.\nRun 'autopilot init' to set up your working directory.")
    return json.loads(p.read_text())


def init_project(resume: str | None = None, yes: bool = False) -> None:
    """Templates into the working directory; with `resume`, the person's settings drafted from it (T103, job_hunt.onboarding)."""
    from job_hunt.onboarding import init_project as _init
    _init(resume=resume, yes=yes)


from job_hunt.exporter import export_jobs_to_csv, job_from_db_row, job_to_export_row  # noqa: E402

_job_to_row = job_to_export_row


def _parse_export_args(argv: list[str]) -> tuple[int, int]:
    """Parse --min / --days flags for the export command. No API keys required."""
    min_score = 0
    days = 0
    if "--min" in argv:
        idx = argv.index("--min")
        try:
            min_score = int(argv[idx + 1])
        except (IndexError, ValueError):
            sys.exit("--min requires an integer, e.g. --min 60")
    if "--days" in argv:
        idx = argv.index("--days")
        try:
            days = int(argv[idx + 1])
        except (IndexError, ValueError):
            sys.exit("--days requires an integer, e.g. --days 7")
    return min_score, days


def _export_min_score() -> int | None:
    """The min_score a scan run here would use (config.json + .env, via load_config), for the "Worth Applying" column.
    None without config.json: export needs no config or API keys, and the column is then left blank."""
    if not Path("config.json").exists():
        return None
    return min_score_of(load_config())


def export_jobs(min_score: int = 0, days: int = 0) -> None:
    """Write a CSV of scored jobs from data/jobs.db: the last finished scan, or with `days` every job scored in the
    last N days (UTC dates), best first (T32)."""
    from job_hunt.db import last_scan_jobs, scored_jobs_since
    if days > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = scored_jobs_since(cutoff)
        if rows is None:
            sys.exit("No history yet. Run 'autopilot scan' at least once after this update.")
        source_label = f"last {days} days"
    else:
        rows = last_scan_jobs()
        if rows is None:
            sys.exit("No scan found. Run: autopilot scan")
        source_label = "last scan"

    threshold = _export_min_score()
    jobs = [job_from_db_row(r, threshold) for r in rows]
    filtered = [j for j in jobs if (j.get("score") or 0) >= min_score]

    if not filtered:
        print(f"No jobs with score >= {min_score} in {source_label}")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    day_suffix = f"_last{days}d" if days else ""
    base_name = f"jobs_{date_str}{day_suffix}"
    out_path = export_jobs_to_csv(filtered, base_name=base_name, out_dir="output")

    print(f"Exported {len(filtered)} jobs ({source_label}) → {out_path}")
    if min_score:
        print(f"Filter: score >= {min_score} (skipped {len(jobs) - len(filtered)})")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "init":
        from job_hunt.onboarding import parse_init_args
        init_project(**parse_init_args(sys.argv[2:]))
        return

    # check-filter: KEPT or REJECTED for one title, with the config.json filter — local, no key (T80, T103)
    if cmd == "check-filter":
        from job_hunt.onboarding import check_filter_command
        check_filter_command(sys.argv[2:])
        return

    # mcp starts the stdio server; it loads config lazily per tool call, so it
    # must NOT require config.json to exist just to launch.
    if cmd == "mcp":
        from job_hunt.mcp_server import mcp
        mcp.run()
        return

    # doctor runs diagnostics without a full config
    if cmd == "doctor":
        from job_hunt.doctor import run_doctor
        success = run_doctor()
        sys.exit(0 if success else 1)

    # validate probes ATS company boards and prunes inactive/404 entries
    if cmd == "validate":
        from job_hunt.validator import validate_and_prune
        validate_and_prune("companies.json")
        return

    # harvest rebuilds companies.json by probing all ATS engines across india.yml slugs
    if cmd == "harvest":
        from job_hunt.harvester import main as harvest_main
        harvest_main(sys.argv[2:])
        return

    # discover verifies company names against public ATS boards — no API keys needed
    if cmd == "discover":
        from job_hunt.discovery import main as discover_main
        from job_hunt.onboarding import configure_titles_or_exit, optional_config
        configure_titles_or_exit(optional_config())      # "has a job that passes the filter" uses the person's filter (T103)
        discover_main(sys.argv[2:])
        return

    # mark records an application status in data/jobs.db (T38) — no API keys needed
    if cmd == "mark":
        from job_hunt.tracker import main as mark_main
        mark_main(sys.argv[2:])
        return

    # export reads local scan state only — no API keys needed, so skip load_config()
    if cmd == "export":
        min_score, days = _parse_export_args(sys.argv)
        from job_hunt.onboarding import use_rubric_of_config_file
        use_rubric_of_config_file()
        export_jobs(min_score=min_score, days=days)
        return

    config = load_config()

    if cmd == "scan":
        limit = None
        if "--limit" in sys.argv:
            try:
                limit_idx = sys.argv.index("--limit")
                limit = int(sys.argv[limit_idx + 1])
            except (IndexError, ValueError):
                pass
        if "--posted-within" in sys.argv:
            try:
                arg = sys.argv[sys.argv.index("--posted-within") + 1]
                window = None if arg == "all" else int(arg)
            except (IndexError, ValueError):
                sys.exit("--posted-within requires a number of days, e.g. --posted-within 3, or 'all' for no window")
            config.setdefault("candidate", {})["max_posted_age_days"] = window
        from job_hunt.scanner import run_scan
        comps = load_companies()
        if limit and limit > 0:
            comps = comps[:limit]
        run_scan(config, comps)

    elif cmd == "draft":
        args = sys.argv[2:]
        jd_file = None
        if "--jd-file" in args:
            k = args.index("--jd-file")
            try:
                jd_file = args[k + 1]
            except IndexError:
                sys.exit("--jd-file requires a path")
            del args[k:k + 2]
        if not args:
            sys.exit("Usage: autopilot draft #N | URL [--jd-file FILE]")
        from job_hunt.drafter import draft_application
        draft_application(config, args[0], jd_file=jd_file)

    else:
        sys.exit(
            f"Unknown command: {cmd}\n"
            "Use: init | check-filter | doctor | validate | harvest | discover | scan | draft | export | mark | mcp"
        )


if __name__ == "__main__":
    main()
