#!/usr/bin/env python3
"""
Usage:
  autopilot init              — set up working directory (first-time pip install setup)
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
  autopilot mcp               — run the MCP server over stdio (for Claude Code)
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

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
    load_dotenv(dotenv_path=Path(".env"), override=True)
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


def init_project() -> None:
    import importlib.resources as pkg_resources

    cwd = Path.cwd()
    data_pkg = pkg_resources.files("job_hunt.data")

    def _copy(src_name: str, dest: Path, label: str) -> None:
        if dest.exists():
            print(f"  {dest.name} already exists, skipping")
        else:
            dest.write_text(data_pkg.joinpath(src_name).read_text(encoding="utf-8"), encoding="utf-8")
            print(f"✓ {label}")

    _copy("companies.json", cwd / "companies.json", "companies.json created (130+ companies pre-loaded)")
    _copy("config.example.json", cwd / "config.json", "config.json created — fill in your API keys and profile")
    _copy("env_example", cwd / ".env", ".env created — fill in your API keys")

    resume_dir = cwd / "resume"
    resume_dir.mkdir(exist_ok=True)
    _copy("resume_template.md", resume_dir / "YOUR_RESUME.md", "resume/YOUR_RESUME.md created — replace with your resume")

    (cwd / "state").mkdir(exist_ok=True)
    (cwd / "output").mkdir(exist_ok=True)

    print("\nNext:")
    print("  1. Edit config.json — set your name, profile, and API keys")
    print("  2. Replace resume/YOUR_RESUME.md with your actual resume")
    print("  3. Run: autopilot scan")


LAST_SCAN_FILE = Path("state/last_scan.json")
JOB_HISTORY_FILE = Path("state/job_history.json")

from job_hunt.exporter import export_jobs_to_csv, job_to_export_row  # noqa: E402

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


def export_jobs(min_score: int = 0, days: int = 0) -> None:
    if days > 0:
        if not JOB_HISTORY_FILE.exists():
            sys.exit(
                "No history yet. Run 'autopilot scan' at least once after this update."
            )
        all_jobs: list[dict] = json.loads(JOB_HISTORY_FILE.read_text())
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        jobs = [j for j in all_jobs if j.get("scan_date", "9999") >= cutoff]
        source_label = f"last {days} days"
    else:
        if not LAST_SCAN_FILE.exists():
            sys.exit("No scan found. Run: autopilot scan")
        jobs = json.loads(LAST_SCAN_FILE.read_text())
        source_label = "last scan"

    filtered = [j for j in jobs if j.get("score", 0) >= min_score]

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
        init_project()
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
        discover_main(sys.argv[2:])
        return

    # export reads local scan state only — no API keys needed, so skip load_config()
    if cmd == "export":
        min_score, days = _parse_export_args(sys.argv)
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
                days = int(sys.argv[sys.argv.index("--posted-within") + 1])
            except (IndexError, ValueError):
                sys.exit("--posted-within requires an integer number of days, e.g. --posted-within 3")
            config.setdefault("candidate", {})["max_posted_age_days"] = days
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
            "Use: init | doctor | validate | harvest | discover | scan | draft | export | mcp"
        )


if __name__ == "__main__":
    main()
