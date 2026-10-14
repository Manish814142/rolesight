"""T106: every reader of "the current rubric" follows candidate.rubric_file, and SDE6-SDE9 pass the default filter again."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from job_hunt import llm_utils, prefilter, tools

ROOT = Path(__file__).resolve().parent.parent
MINE = "SCORING RUBRIC for Asha\n1. a rule"


def _project(tmp_path):
    (tmp_path / "rubric.md").write_text(MINE + "\n")
    (tmp_path / "config.json").write_text(json.dumps({"candidate": {"rubric_file": "rubric.md"}}))
    return tmp_path


def test_the_mcp_export_compares_with_the_persons_rubric(tmp_path, monkeypatch):
    _project(tmp_path)
    seen = {}
    monkeypatch.setattr(tools, "export_jobs", lambda **kw: seen.setdefault("rubric", llm_utils.SCORING_RUBRIC))
    tools.tool_export(config_path=str(tmp_path / "config.json"))
    assert seen["rubric"] == MINE


def test_the_mcp_export_without_a_rubric_file_keeps_the_built_in_one(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text(json.dumps({"candidate": {}}))
    seen = {}
    monkeypatch.setattr(tools, "export_jobs", lambda **kw: seen.setdefault("rubric", llm_utils.SCORING_RUBRIC))
    tools.tool_export(config_path=str(tmp_path / "config.json"))
    assert seen["rubric"] == llm_utils.DEFAULT_SCORING_RUBRIC


def test_rubric_ids_marks_the_persons_rubric_as_current(tmp_path):
    _project(tmp_path)
    mine = llm_utils.rubric_id(MINE)
    db = tmp_path / "jobs.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE jobs (status TEXT, score INTEGER, score_rubric TEXT)")
    conn.executemany("INSERT INTO jobs VALUES ('scored', 80, ?)", [(mine,), (mine,), (None,)])
    conn.commit()
    conn.close()
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "rubric_ids.py"), "--db", str(db)], cwd=tmp_path,
                         capture_output=True, text=True, check=True).stdout
    assert f"Your rubric (rubric.md): {mine}" in out
    assert f"{mine}  2 scored  (current)" in out


def test_sde6_to_sde9_pass_as_the_old_rule_let_them():
    for title in ("SDE6", "SDE7 - Backend", "SDE8", "SDE9"):
        assert prefilter.title_is_candidate(title), title
    # Accepted difference, measured 2026-10-14: the old `sde\d*` also took SDE10 and above; 0 such titles in 34,624.
    assert not prefilter.title_is_candidate("SDE10")
