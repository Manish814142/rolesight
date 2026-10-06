"""Dependencies describe what the code imports (T51)."""
import tomllib
from pathlib import Path

ROOT = Path(".")


def _pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def _requirement_names(path):
    names = []
    for line in Path(path).read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            names.append(line.split(">=")[0].split("==")[0].split("<")[0].strip().lower())
    return names


def test_gemini_client_is_a_core_dependency_everywhere():
    """Gemini is the default provider: without google-genai every scoring call fails."""
    core = [d.split(">=")[0].lower() for d in _pyproject()["project"]["dependencies"]]
    assert "google-genai" in core
    assert "google-genai" in _requirement_names("requirements.txt")


def test_requirements_only_name_what_the_code_imports():
    names = _requirement_names("requirements.txt")
    assert "openpyxl" not in names           # nothing in job_hunt/ imports it
    assert {"python-dotenv", "requests", "google-genai"} <= set(names)
