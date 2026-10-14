"""
MCP server for RoleSight.

Register with Claude Code (one command):
  claude mcp add rolesight \\
    --env GEMINI_API_KEY=your_key \\
    --env TELEGRAM_TOKEN=your_token \\
    --env TELEGRAM_CHAT_ID=your_chat_id \\
    -- python -m job_hunt.mcp_server

Or add to ~/.claude.json manually — see README for full JSON block.

cwd must be the cloned repo root (config.json and companies.json are read from there).
"""
import functools
import importlib
from typing import Annotated, Any, Callable

from pydantic import Field

from job_hunt.tools import ToolError, tool_draft, tool_export, tool_scan

_INSTALL_HINT = (
    "MCP SDK not installed. In your clone of the repository run: pip install -e '.[mcp]'\n"
    "Or: pip install 'mcp>=1.9,<3'"
)


def _load_sdk() -> tuple[Any, Any, Any]:
    """(server class, ToolAnnotations, ToolError) of the installed `mcp`. The class is `MCPServer` in mcp 2.x
    (mcp.server.mcpserver) and `FastMCP` in 1.x (mcp.server.fastmcp); ToolAnnotations is in mcp.types in both."""
    try:
        annotations = importlib.import_module("mcp.types").ToolAnnotations
    except ImportError:
        raise ImportError(_INSTALL_HINT) from None
    for package, name in (("mcp.server.mcpserver", "MCPServer"), ("mcp.server.fastmcp", "FastMCP")):
        try:
            server = getattr(importlib.import_module(package), name)
            return server, annotations, importlib.import_module(f"{package}.exceptions").ToolError
        except (ImportError, AttributeError):
            continue
    raise ImportError(_INSTALL_HINT)


FastMCP, ToolAnnotations, SdkToolError = _load_sdk()


def _tell_the_client_why(func: Callable[..., str]) -> Callable[..., str]:
    """A tool that cannot run (no config.json, no scan yet) raises job_hunt.tools.ToolError. mcp 2.x shows a client only
    its own ToolError's message and replaces any other exception's with "Error executing tool <name>", so translate."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return func(*args, **kwargs)
        except ToolError as why:
            raise SdkToolError(str(why)) from None
    return wrapper


def _hints(title: str, *, read_only: bool, destructive: bool, idempotent: bool, open_world: bool) -> Any:
    """Tool annotations, built from the camelCase names: 1.x has them as field names and 2.x as aliases next to its
    snake_case fields, so one call works with either."""
    return ToolAnnotations.model_validate({
        "title": title, "readOnlyHint": read_only, "destructiveHint": destructive,
        "idempotentHint": idempotent, "openWorldHint": open_world,
    })


mcp = FastMCP("rolesight")


@mcp.tool(
    annotations=_hints("Scan & score job postings", read_only=False, destructive=False, idempotent=False, open_world=True)
)
@_tell_the_client_why
def scan_jobs() -> str:
    """
    Scan all configured company careers pages for new job postings,
    score them with AI against your resume, and send a Telegram notification
    with the top matches. Reads config.json and companies.json from the
    working directory.
    """
    return tool_scan()


@mcp.tool(
    annotations=_hints("Draft application (never applies)", read_only=False, destructive=False, idempotent=False, open_world=True)
)
@_tell_the_client_why
def draft_application(
    job_ref: Annotated[
        str,
        Field(
            description="Job reference: '#1' or '1' (index from the last scan), "
            "or a full job posting URL."
        ),
    ],
) -> str:
    """
    Draft a tailored resume and cover letter for a specific job.

    Never applies — every draft is saved for human review and manual submission.
    Returns a summary of where the output files were saved.
    """
    return tool_draft(job_ref)


@mcp.tool(
    annotations=_hints("Export jobs to CSV", read_only=False, destructive=False, idempotent=True, open_world=False)
)
@_tell_the_client_why
def export_jobs(
    min_score: Annotated[
        int, Field(description="Only include jobs with fit score >= this value (0 = all).")
    ] = 0,
    days: Annotated[
        int, Field(description="Export from the last N days of history (0 = last scan only).")
    ] = 0,
) -> str:
    """
    Export job scan results to a CSV file in the output/ directory.

    Returns a summary of the export.
    """
    return tool_export(min_score=min_score, days=days)


if __name__ == "__main__":
    mcp.run()
