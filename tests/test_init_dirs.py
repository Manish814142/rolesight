"""T83: nothing reads or writes state/ any more (T34), so neither `autopilot init` nor run_daily.sh creates it."""
import re
from pathlib import Path

from job_hunt import main

ROOT = Path(__file__).resolve().parent.parent


def test_init_creates_the_folders_a_scan_uses_and_no_state_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main.init_project()
    assert (tmp_path / "output").is_dir() and (tmp_path / "resume").is_dir()
    assert not (tmp_path / "state").exists()


def test_run_daily_does_not_create_a_state_folder():
    mkdirs = re.findall(r"^mkdir -p (.*)$", (ROOT / "run_daily.sh").read_text(), re.MULTILINE)
    assert mkdirs and all("state" not in line.split() for line in mkdirs), mkdirs
    assert "data" in mkdirs[0].split() and "output" in mkdirs[0].split()
