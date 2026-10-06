"""Dependencies and packaging metadata describe this fork (T51, T55)."""
import tomllib
from pathlib import Path

ROOT = Path(".")
REMOVED = ("tinyfish", "openrouter")


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
def test_nothing_in_packaging_names_the_removed_providers():
    for f in ("pyproject.toml", "requirements.txt", "Dockerfile", "smithery.yaml"):
        text = (ROOT / f).read_text().lower()
        for word in REMOVED:
            assert word not in text, f"{f} still mentions {word}"


def test_project_metadata_does_not_point_at_the_upstream_repo():
    project = _pyproject()["project"]
    assert "urls" not in project or not any("tarunlnmiit" in u for u in project["urls"].values())
    assert "openrouter" not in [k.lower() for k in project["keywords"]]
