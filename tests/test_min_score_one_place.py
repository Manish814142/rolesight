"""T05: one MIN_SCORE. config.json's candidate.min_score is the single place; the code default is 70 (Manish, 2026-10-10);
neither run_daily.sh nor the .env template sets a second, competing value."""
import json
import logging
import re
from pathlib import Path

import pytest

from job_hunt import main, scanner
from job_hunt.settings import DEFAULT_MIN_SCORE, min_score_of

ROOT = Path(__file__).resolve().parent.parent


def test_the_default_is_70():
    assert DEFAULT_MIN_SCORE == 70
    assert min_score_of({}) == 70
    assert min_score_of({"candidate": {}}) == 70
    assert min_score_of({"candidate": {"min_score": 65}}) == 65


def test_the_scan_logs_the_min_score_it_uses_when_the_config_names_none(monkeypatch, tmp_path, caplog):
    """The done-when of T05: the scan's own 'Min score:' line shows the value in force."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [])
    (tmp_path / "resume.md").write_text("Node.js")
    caplog.set_level(logging.INFO, logger="autopilot")
    scanner.run_scan({"candidate": {"resume_path": "resume.md"}, "gemini_api_key": "k", "telegram": {}},
                     [{"name": "X", "ats": "greenhouse", "slug": "x"}])
    line = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("Min score:"))
    assert line.startswith("Min score: 70 ")


def test_export_uses_the_same_default(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"candidate": {}}))
    monkeypatch.delenv("MIN_SCORE", raising=False)
    assert main._export_min_score() == 70


def test_run_daily_does_not_set_a_second_min_score():
    """It used to export MIN_SCORE=70 and print it in its banner while .env's 60 won (measured, T05)."""
    script = (ROOT / "run_daily.sh").read_text()
    assert not re.search(r"^\s*export\s+MIN_SCORE", script, re.MULTILINE)
    assert "min_score=${MIN_SCORE" not in script


@pytest.mark.parametrize("template", ["job_hunt/data/config.example.json", "config.example.json"])
def test_example_config_agrees_with_the_default(template):
    assert json.loads((ROOT / template).read_text())["candidate"]["min_score"] == DEFAULT_MIN_SCORE


def test_the_env_template_sets_no_competing_min_score():
    """An active MIN_SCORE in the .env that `autopilot init` writes beats config.json (load_dotenv override), which is
    how a second value crept in. The line may stay as a comment."""
    text = (ROOT / "job_hunt/data/env_example").read_text()
    assert not re.search(r"^\s*MIN_SCORE\s*=", text, re.MULTILINE)
