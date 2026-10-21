"""What `autopilot init` ships must work for a new user without TinyFish or OpenRouter (T50)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

DATA = Path("job_hunt/data")


def _names(path):
    return {c["name"] for c in json.loads(Path(path).read_text())}


def test_packaged_company_list_is_the_curated_one():
    """`init` used to copy 140 careers-URL-only entries that only TinyFish could scan: a new user's first
    scan fetched nothing. After `discover --merge`, copy companies.json to job_hunt/data/companies.json."""
    packaged = json.loads((DATA / "companies.json").read_text())
    assert len(packaged) >= 200
    assert all(c.get("ats") for c in packaged), "every packaged company needs an ATS the scanner can fetch"
    assert _names(DATA / "companies.json") == _names("companies.json")


def test_config_examples_do_not_mention_removed_providers():
    for f in (DATA / "config.example.json", Path("config.example.json"), DATA / "env_example"):
        text = f.read_text().lower()
        assert "tinyfish" not in text and "openrouter" not in text, f


def test_config_examples_are_identical_and_valid_json():
    a, b = Path("config.example.json").read_text(), (DATA / "config.example.json").read_text()
    assert a == b
    cfg = json.loads(a)
    assert cfg["llm_provider"] == "gemini" and "gemini_api_key" in cfg
    assert "search_keywords" not in cfg["candidate"]            # TinyFish-search-only fields


def test_git_does_not_ignore_what_the_wheel_ships():
    """T134: hatchling leaves out of the wheel whatever .gitignore matches. `data/` once matched job_hunt/data/ too, so a
    non-editable install had none of these files and `autopilot init` failed (`No module named 'job_hunt.data'`). git's own
    matcher decides here; the root data/ (personal state) must stay ignored."""
    if shutil.which("git") is None or not Path(".git").exists():
        pytest.skip("needs git and the repository")
    paths = sorted(str(f) for f in DATA.iterdir() if f.is_file()) + [str(DATA / "a_new_file.json")]
    r = subprocess.run(["git", "check-ignore", "--no-index", *paths], capture_output=True, text=True)
    assert r.stdout == "", f"ignored by .gitignore, so left out of the wheel:\n{r.stdout}"
    assert subprocess.run(["git", "check-ignore", "--no-index", "-q", "data/jobs.db"]).returncode == 0
