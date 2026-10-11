"""T81: the .env that `autopilot init` writes must leave the candidate's name, resume path and top-N to config.json.

Found by following the user guide in a fresh checkout (T80): the template set CANDIDATE_NAME="Your Name" and
RESUME_PATH="resume/YOUR_RESUME.md" as live lines, and main.load_config lets those beat config.json without a
placeholder check, so a new user who edited config.json still scanned against the template resume, silently.
"""
import json
import os
import re
import shutil
from pathlib import Path
from unittest import mock

from job_hunt import main

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "job_hunt" / "data" / "env_example"
OVERRIDES = ("CANDIDATE_NAME", "RESUME_PATH", "MIN_SCORE", "TOP_N")


def test_the_env_template_has_no_live_candidate_override():
    live = [name for name in OVERRIDES if re.search(rf"^\s*{name}\s*=", TEMPLATE.read_text(), re.MULTILINE)]
    assert not live, f"these lines in the template beat config.json for every new user: {live}"


def test_the_env_template_still_explains_the_overrides():
    """Commented, not deleted: it documents that these variables exist and that they win over config.json."""
    text = TEMPLATE.read_text()
    for name in OVERRIDES:
        assert re.search(rf"^#\s*{name}\s*=", text, re.MULTILINE), f"{name} should stay as a commented example"


def test_a_config_edited_after_init_is_what_the_scan_uses(tmp_path, monkeypatch):
    """The real consumer: `autopilot init` in an empty directory, then edit config.json, then load_config."""
    monkeypatch.chdir(tmp_path)
    main.init_project()

    cfg = json.loads(Path("config.json").read_text())
    cfg["candidate"].update(name="Asha Rao", resume_path="resume/asha.md", top_n=9, min_score=65)
    Path("config.json").write_text(json.dumps(cfg))
    shutil.copy("resume/YOUR_RESUME.md", "resume/asha.md")

    # load_config loads .env into os.environ for good; patch.dict puts the real environment back afterwards
    with mock.patch.dict(os.environ):
        for name in OVERRIDES:
            os.environ.pop(name, None)
        got = main.load_config()["candidate"]
    assert (got["name"], got["resume_path"], got["top_n"], got["min_score"]) == ("Asha Rao", "resume/asha.md", 9, 65)
