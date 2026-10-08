"""
Protocol-agnostic tool layer.

These functions contain zero MCP/OpenAI/Google dependencies.
The MCP server, future OpenAI tool adapter, and future Gemini function adapter
all import from here — one place to update, all adapters benefit.
"""
from pathlib import Path

from job_hunt.db import last_scan_jobs
from job_hunt.drafter import draft_application
from job_hunt.main import export_jobs, load_companies, load_config
from job_hunt.scanner import run_scan


def tool_scan(config_path: str = "config.json", companies_path: str = "companies.json") -> str:
    """
    Discover new jobs, score them, send Telegram notification.
    Returns a summary string.
    """
    import os
    old_cwd = Path.cwd()
    project_root = Path(config_path).parent.resolve()
    os.chdir(project_root)
    try:
        config = load_config()
        companies = load_companies()
        run_scan(config, companies)
        jobs = last_scan_jobs()           # data/jobs.db, the scan's only record since T34
        if jobs is None:
            return "Scan complete. No finished scan recorded in data/jobs.db."
        scored = [j for j in jobs if j.get("score")]
        return f"Scan complete. {len(jobs)} jobs found, {len(scored)} scored."
    finally:
        os.chdir(old_cwd)


def tool_draft(job_ref: str, config_path: str = "config.json") -> str:
    """
    Draft a tailored resume + cover letter for a job.
    job_ref: '#1', '1', or a full job URL.
    Returns path to output directory.
    """
    import os
    old_cwd = Path.cwd()
    project_root = Path(config_path).parent.resolve()
    os.chdir(project_root)
    try:
        config = load_config()
        draft_application(config, job_ref)
        return "Application drafted in output/ directory."
    finally:
        os.chdir(old_cwd)


def tool_export(min_score: int = 0, days: int = 0, config_path: str = "config.json") -> str:
    """
    Export jobs to CSV.
    Returns path to exported CSV.
    """
    import os
    old_cwd = Path.cwd()
    project_root = Path(config_path).parent.resolve()
    os.chdir(project_root)
    try:
        export_jobs(min_score=min_score, days=days)
        return "Export complete. Check output/ directory."
    finally:
        os.chdir(old_cwd)
