"""What `autopilot init` ships must work for a new user without TinyFish or OpenRouter (T50)."""
import json
from pathlib import Path

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
