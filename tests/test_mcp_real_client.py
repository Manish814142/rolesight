"""T98: the MCP server through a real MCP client (the SDK's own stdio client), on whichever `mcp` is installed.

`mcp` 2.x renamed FastMCP to MCPServer and `ToolAnnotations` to snake_case fields; this file is the check that the server
starts, lists its tools and answers calls (also failing ones) under 1.x and 2.x. It spawns `python -m job_hunt.mcp_server`
in an empty temp directory: no network, no Gemini, no Telegram (the tools that would need them fail on the missing config).
"""
import asyncio
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from job_hunt.db import init_db, save_job, update_job_status  # noqa: E402
from job_hunt.models import JobPosting, job_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 60      # seconds for the whole conversation: a server that never answers fails the test instead of hanging it


def _converse(cwd, steps):
    """Start the server in `cwd`, run `steps(session)` and return its result."""
    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "job_hunt.mcp_server"], cwd=str(cwd),
                                       env={"PYTHONPATH": str(ROOT), "PATH": os.environ.get("PATH", "")})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                return init, await steps(session)
    return asyncio.run(asyncio.wait_for(run(), TIMEOUT))


def _dump(model):
    return model.model_dump(by_alias=True)       # camelCase keys in 1.x and 2.x alike


def _text(result):
    return " ".join(getattr(c, "text", "") for c in result.content)


def test_the_server_starts_names_itself_and_lists_its_three_tools_with_their_hints(tmp_path):
    async def steps(session):
        return (await session.list_tools()).tools

    init, tools = _converse(tmp_path, steps)
    assert _dump(init)["serverInfo"]["name"] == "rolesight"
    by_name = {t.name: _dump(t.annotations) for t in tools}
    assert set(by_name) == {"scan_jobs", "draft_application", "export_jobs"}
    assert by_name["scan_jobs"]["readOnlyHint"] is False and by_name["scan_jobs"]["openWorldHint"] is True
    assert by_name["export_jobs"]["idempotentHint"] is True and by_name["export_jobs"]["openWorldHint"] is False
    assert all(a["destructiveHint"] is False for a in by_name.values())
    assert by_name["export_jobs"]["title"] == "Export jobs to CSV"


def test_calls_that_cannot_run_come_back_as_errors_with_the_reason(tmp_path):
    """No config.json and no database here: each tool says what is missing; the server stays up for the next call."""
    async def steps(session):
        return [await session.call_tool("scan_jobs", {}),
                await session.call_tool("draft_application", {"job_ref": "#1"}),
                await session.call_tool("export_jobs", {"min_score": 0, "days": 0}),
                await session.list_tools()]

    _, (scan, draft, export, still_listing) = _converse(tmp_path, steps)
    for result, reason in ((scan, "config.json not found"), (draft, "config.json not found"), (export, "No scan found")):
        assert _dump(result)["isError"] is True and reason in _text(result), _text(result)
    assert len(still_listing.tools) == 3


def test_export_through_the_client_writes_the_csv_from_the_database(tmp_path):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    job = JobPosting(global_id="greenhouse:x:1", ats="greenhouse", company="Acme", title="Backend Engineer",
                     location="Bengaluru, India", is_remote=False, url="https://x.example/1", description_text="Node.js",
                     posted_at=yesterday)
    db = str(tmp_path / "data" / "jobs.db")
    init_db(db)
    save_job(job, db_path=db)
    update_job_status(job_key(job), "scored", 88, "fits", db_path=db)

    async def steps(session):
        return await session.call_tool("export_jobs", {"min_score": 70, "days": 7})

    _, result = _converse(tmp_path, steps)
    assert _dump(result)["isError"] is False and "Export complete" in _text(result)
    (csv_file,) = (tmp_path / "output").glob("jobs_*.csv")
    assert "Backend Engineer" in csv_file.read_text(encoding="utf-8")
