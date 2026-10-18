"""
Protocol-agnostic tool layer.

These functions contain zero MCP/OpenAI/Google dependencies.
The MCP server, future OpenAI tool adapter, and future Gemini function adapter
all import from here — one place to update, all adapters benefit.
"""
import functools
from pathlib import Path
from typing import Callable, TypeVar, cast

from job_hunt.db import last_scan_jobs
from job_hunt.drafter import draft_application
from job_hunt.main import export_jobs, load_companies, load_config
from job_hunt.scanner import run_scan

F = TypeVar("F", bound=Callable[..., str])


class ToolError(RuntimeError):
    """A tool could not run for a reason the user can act on (no config.json, no scan yet...); the message says what to do."""


def _exit_as_tool_error(func: F) -> F:
    """The CLI helpers the tools call end with sys.exit("reason"). Inside a server a SystemExit is not an error reply: the
    client never got an answer (found with a real MCP client, T98). It becomes a ToolError carrying the reason."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SystemExit as stop:
            raise ToolError(stop.code if isinstance(stop.code, str) and stop.code
                            else f"{func.__name__} stopped (exit code {stop.code}).") from None
    return cast(F, wrapper)


@_exit_as_tool_error
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


@_exit_as_tool_error
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
        folder = draft_application(config, job_ref)
        return f"Application drafted in {folder or 'output/drafts/'}"
    finally:
        os.chdir(old_cwd)


@_exit_as_tool_error
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
        from job_hunt.onboarding import use_rubric_of_config_file
        use_rubric_of_config_file()                     # T106: the person's rubric is "current" for the Rubric column
        written = export_jobs(min_score=min_score, days=days)
        if written is None:
            return "Export complete. No job matched, so no file was written."
        return f"Export complete: {written} (the same table as an .xlsx beside it)."
    finally:
        os.chdir(old_cwd)
