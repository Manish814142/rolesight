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


# Import name -> distribution name. Optional imports (the anthropic provider, the MCP server and its pydantic
# models) are installed by extras and imported lazily; everything else must be a core dependency.
_DISTRIBUTION = {"dotenv": "python-dotenv", "google": "google-genai", "requests": "requests", "yaml": "pyyaml"}
_OPTIONAL_IMPORTS = {"anthropic", "mcp", "pydantic"}


def _third_party_imports():
    import ast
    import sys
    found = set()
    for path in (ROOT / "job_hunt").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            found |= {n.split(".")[0] for n in names}
    return {n for n in found if n != "job_hunt" and n not in sys.stdlib_module_names}


def test_every_third_party_import_is_a_declared_dependency():
    """T66: discovery/harvester import yaml, but neither file declared PyYAML, so on a fresh
    `pip install -r requirements.txt` `autopilot discover` died with ModuleNotFoundError."""
    required = _third_party_imports() - _OPTIONAL_IMPORTS
    assert required <= set(_DISTRIBUTION), f"map these imports to a distribution: {required - set(_DISTRIBUTION)}"
    core = {d.split(">=")[0].split("<")[0].strip().lower() for d in _pyproject()["project"]["dependencies"]}
    reqs = set(_requirement_names("requirements.txt"))
    for imp in sorted(required):
        assert _DISTRIBUTION[imp] in core, f"pyproject.toml lacks {_DISTRIBUTION[imp]} (imported as {imp})"
        assert _DISTRIBUTION[imp] in reqs, f"requirements.txt lacks {_DISTRIBUTION[imp]} (imported as {imp})"


def test_nothing_in_packaging_names_the_removed_providers():
    for f in ("pyproject.toml", "requirements.txt", "Dockerfile", "smithery.yaml"):
        text = (ROOT / f).read_text().lower()
        for word in REMOVED:
            assert word not in text, f"{f} still mentions {word}"


def test_project_metadata_does_not_point_at_the_upstream_repo():
    project = _pyproject()["project"]
    assert "urls" not in project or not any("tarunlnmiit" in u for u in project["urls"].values())
    assert "openrouter" not in [k.lower() for k in project["keywords"]]
