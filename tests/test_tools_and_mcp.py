"""Tool layer + MCP server — scanner/drafter/export stubbed; assert cwd is restored."""
from pathlib import Path

import pytest

from job_hunt import tools


def test_tool_scan_no_results(tmp_path, monkeypatch):
    """No finished scan in data/jobs.db (counts from the DB: tests/test_retire_json_state.py, T34)."""
    monkeypatch.setattr(tools, "load_config", lambda: {})
    monkeypatch.setattr(tools, "load_companies", lambda: [])
    monkeypatch.setattr(tools, "run_scan", lambda c, co: None)
    out = tools.tool_scan(config_path=str(tmp_path / "config.json"))
    assert "No finished scan" in out


def test_tool_scan_restores_cwd(tmp_path, monkeypatch):
    before = Path.cwd()
    monkeypatch.setattr(tools, "load_config", lambda: {})
    monkeypatch.setattr(tools, "load_companies", lambda: [])
    monkeypatch.setattr(tools, "run_scan", lambda c, co: None)
    tools.tool_scan(config_path=str(tmp_path / "config.json"))
    assert Path.cwd() == before


def test_tool_draft(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "load_config", lambda: {})
    called = {}
    monkeypatch.setattr(tools, "draft_application", lambda cfg, ref: called.update(ref=ref))
    out = tools.tool_draft("#2", config_path=str(tmp_path / "config.json"))
    assert called["ref"] == "#2" and "output/" in out


def test_tool_export(tmp_path, monkeypatch):
    called = {}
    monkeypatch.setattr(tools, "export_jobs", lambda min_score, days: called.update(m=min_score, d=days))
    out = tools.tool_export(min_score=70, days=7, config_path=str(tmp_path / "config.json"))
    assert called == {"m": 70, "d": 7} and "Export complete" in out


def test_mcp_server_tools_delegate(monkeypatch):
    mcp_server = pytest.importorskip("job_hunt.mcp_server")
    monkeypatch.setattr(mcp_server, "tool_scan", lambda: "scanned")
    monkeypatch.setattr(mcp_server, "tool_draft", lambda ref: f"drafted {ref}")
    monkeypatch.setattr(mcp_server, "tool_export", lambda min_score, days: f"exported {min_score}/{days}")
    assert mcp_server.scan_jobs() == "scanned"
    assert mcp_server.draft_application("#1") == "drafted #1"
    assert mcp_server.export_jobs(50, 3) == "exported 50/3"


# -- T98: a tool that cannot run says why instead of ending the server's call -----------------------------------------

@pytest.mark.parametrize("call, message", [
    (lambda tmp: tools.tool_export(config_path=str(tmp / "config.json")), "No scan found"),
    (lambda tmp: tools.tool_scan(config_path=str(tmp / "config.json")), "config.json not found"),
    (lambda tmp: tools.tool_draft("#1", config_path=str(tmp / "config.json")), "config.json not found"),
])
def test_a_tool_that_cannot_run_raises_a_tool_error_with_the_reason_not_system_exit(tmp_path, monkeypatch, call, message):
    """The CLI helpers end with sys.exit("reason"). Inside an MCP server a SystemExit is not an error reply: the client
    waited for an answer that never came (found with a real client, T98)."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(tools.ToolError) as err:
        call(tmp_path)
    assert message in str(err.value)


def test_a_tool_error_restores_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sub").mkdir()
    before = Path.cwd()
    with pytest.raises(tools.ToolError):
        tools.tool_export(config_path=str(tmp_path / "sub" / "config.json"))
    assert Path.cwd() == before
