"""T88: the repo is published as RoleSight under the MIT licence, built on tarunlnmiit/autopilot-jobhunt.

What these guard: the name is used everywhere a reader or a shell sees it, the original author's copyright and a credit
stay (MIT requires the notice), nothing still points at the original project's owner as if it were this project's, and no
personal or company e-mail address sits in a file that goes public.
"""
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# History, not product text: they record what was done under the old name.
HISTORY_FILES = {"CHANGELOG.md", "docs/tasks.md", "tests/test_public_release.py"}
# Files that may name the original project's owner: the credit, the board's history and this test.
CREDIT_FILES = {"README.md", "ARCHITECTURE.md", "CLAUDE.md", "CHANGELOG.md", "docs/tasks.md", "tests/test_packaging.py",
                "tests/test_public_release.py"}
# Verbatim job postings and test fixtures hold other people's addresses; they are data, not our contact details.
EMAIL_EXEMPT_PREFIXES = ("tests/", "scripts/golden_set")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PLACEHOLDER_EMAIL = re.compile(r"^(your@email\.com|[^@]+@example\.(com|org)|noreply@anthropic\.com)$", re.I)


def _tracked_text_files() -> dict[str, str]:
    done = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    if done.returncode != 0:
        pytest.skip("not a git checkout")
    out = {}
    for name in done.stdout.splitlines():
        path = ROOT / name
        if not path.is_file():
            continue
        try:
            out[name] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue   # a binary file (the PNG, the GIF)
    return out


def test_the_distribution_and_its_command_are_called_rolesight():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["name"] == "rolesight"
    assert "rolesight" in project["scripts"] and "autopilot" in project["scripts"]
    assert "autopilot-jobhunt" not in project["scripts"], "that alias existed for the upstream package's registry listing"


def test_the_old_project_name_is_left_only_in_history():
    stray = {name: len(re.findall("jobnotify", text, re.I)) for name, text in _tracked_text_files().items()
             if name not in HISTORY_FILES and re.search("jobnotify", text, re.I)}
    assert not stray, f"still called JobNotify: {stray}"


def test_the_licence_keeps_the_original_copyright_and_adds_the_owner():
    first_lines = (ROOT / "LICENSE").read_text().splitlines()[:6]
    text = "\n".join(first_lines)
    assert "Copyright (c) 2025 Tarun Gupta" in text, "MIT requires the original notice to stay"
    assert re.search(r"Copyright \(c\) 2026 Manish Singh", text)
    assert first_lines[0].strip() == "MIT License"


def test_the_readme_credits_the_original_project():
    readme = (ROOT / "README.md").read_text()
    assert readme.startswith("# RoleSight")
    assert "https://github.com/tarunlnmiit/autopilot-jobhunt" in readme
    assert "MIT" in readme


def test_nothing_else_names_the_original_owner():
    stray = [name for name, text in _tracked_text_files().items()
             if name not in CREDIT_FILES and re.search(r"tarunlnmiit|tarungupta", text, re.I)]
    assert not stray, f"these still point at the original project's owner: {stray}"


def test_no_registry_listing_for_the_original_package_is_shipped():
    """server.json and glama.json register the upstream package under its owner's name."""
    assert not (ROOT / "server.json").exists() and not (ROOT / "glama.json").exists()


def test_no_personal_or_company_email_address_is_in_a_published_file():
    found = {}
    for name, text in _tracked_text_files().items():
        if name.startswith(EMAIL_EXEMPT_PREFIXES):
            continue
        real = sorted({m for m in EMAIL.findall(text) if not PLACEHOLDER_EMAIL.match(m)})
        if real:
            found[name] = real
    assert not found, f"e-mail addresses in published files: {found}"


def test_the_secret_scan_ignores_only_the_verbatim_job_postings():
    """CI runs gitleaks over the whole history. The golden sets hold posting text, and a phrase like "APIs,
    middleware/integration" trips its generic-api-key rule (measured: 1 finding in 303 commits, scripts/golden_set.csv).
    The allowlist is by path, not by commit, because the commit hashes change when history is rewritten."""
    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
    assert config["extend"]["useDefault"] is True
    paths = config["allowlist"]["paths"]
    assert len(paths) == 1 and all(re.fullmatch(p, f) for p in paths for f in ("scripts/golden_set.csv", "scripts/golden_set_ai.csv"))
    assert not any(re.fullmatch(p, f) for p in paths for f in (".env", "config.json", "job_hunt/llm_utils.py", "scripts/score_golden_set.py"))
    # Our own notes quote that phrase (CHANGELOG, the board, this file), which trips the same rule: allow that one string only.
    regexes = config["allowlist"]["regexes"]
    assert len(regexes) == 1 and re.search(regexes[0], "middleware/integration")
    # Built at run time: written out, key-shaped strings would trip the very scan this test is about.
    not_allowed = ("AIza" + "Sy" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q", "sk-" + "ant-api03-" + "abcdefghijklmnop", "ghp" + "_" + "a1B2" * 9)
    assert not any(re.search(regexes[0], secret) for secret in not_allowed)


# -- Manish's answers of 2026-10-13: no PyPI, keep the golden sets with a notice, publish at Manish814142/rolesight -----

REPO_URL = "https://github.com/Manish814142/rolesight"


def test_ci_does_not_publish_to_pypi_and_does_not_run_on_tags():
    """He has no PyPI account and does not want one (T88). The upstream `publish` job would fail on every `v*` tag."""
    import yaml
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "pypi" not in text.lower() and "hatch" not in text.lower()
    workflow = yaml.safe_load(text)
    assert "publish" not in workflow["jobs"]
    triggers = workflow.get("on", workflow.get(True))   # PyYAML reads the key `on` as True
    assert "tags" not in triggers["push"], "the upstream release tags must not start CI runs"


def test_the_readme_says_the_golden_sets_hold_other_peoples_posting_text():
    readme = (ROOT / "README.md").read_text()
    assert "scripts/golden_set.csv" in readme and "scripts/golden_set_ai.csv" in readme
    assert re.search(r"public job postings", readme) and re.search(r"removed (on|at) request|will be removed", readme)


def test_the_project_links_point_at_the_new_repository():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["urls"]["Repository"] == REPO_URL
    assert project["urls"]["Issues"] == REPO_URL + "/issues"
    readme = (ROOT / "README.md").read_text()
    assert f"{REPO_URL}/actions/workflows/ci.yml" in readme, "the CI badge"


# -- T93: the old product name in messages and names a user sees -------------------------------------------------------

def test_no_source_file_still_names_the_old_product():
    offenders = [str(f.relative_to(ROOT)) for f in [*(ROOT / "job_hunt").rglob("*.py"), ROOT / "conftest.py"]
                 if "autopilot-jobs" in f.read_text()]
    assert not offenders, offenders


def test_the_mcp_server_reports_its_name_and_a_working_install_hint(monkeypatch):
    import importlib
    import sys
    pytest.importorskip("mcp")
    server = importlib.import_module("job_hunt.mcp_server")
    assert server.mcp.name == "rolesight"
    monkeypatch.delitem(sys.modules, "job_hunt.mcp_server")
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", None)          # the module is "not installed"
    with pytest.raises(ImportError) as err:
        importlib.import_module("job_hunt.mcp_server")
    assert "pip install -e '.[mcp]'" in str(err.value)
    assert "autopilot-jobs" not in str(err.value)


def test_the_claude_provider_hint_is_the_command_that_works(monkeypatch):
    import sys

    from job_hunt import llm_utils
    monkeypatch.setitem(sys.modules, "anthropic", None)                   # the module is "not installed"
    with pytest.raises(ImportError) as err:
        llm_utils._chat_with_anthropic({}, [], 0.1, 10)
    assert "pip install -e '.[claude]'" in str(err.value)
    assert "autopilot-jobs" not in str(err.value)


def test_the_doctor_banner_says_rolesight(monkeypatch, capsys, tmp_path):
    from job_hunt import doctor
    monkeypatch.setattr(doctor, "check_sqlite_write", lambda p="x": (True, "OK"))
    monkeypatch.setattr(doctor, "check_gemini_quota", lambda *a, **k: (True, "OK"))
    monkeypatch.setattr(doctor, "check_telegram_credentials", lambda *a, **k: (False, "off"))
    monkeypatch.setattr(doctor, "check_ats_egress", lambda: {})
    doctor.run_doctor(db_path=str(tmp_path / "x.db"), env_path=str(tmp_path / "no.env"))
    out = capsys.readouterr().out
    assert "ROLESIGHT DOCTOR DIAGNOSTICS" in out and "AUTOPILOT" not in out


def test_no_source_file_names_a_personal_path():
    offenders = [str(f.relative_to(ROOT)) for f in (ROOT / "job_hunt").rglob("*.py") if "/home/user" in f.read_text()]
    assert not offenders, offenders
