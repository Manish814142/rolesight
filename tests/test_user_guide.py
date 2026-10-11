"""docs/00-user-guide.md names settings, variables, commands and files; each must exist in the code (T80).

The guide is for someone who only edits files, so a wrong name costs them an evening: a setting that
the code never reads is ignored without any message. The checks below use the code itself (ast over
job_hunt/, the real prefilter), not a second copy of the facts.
"""
import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "00-user-guide.md"


def _guide() -> str:
    assert GUIDE.exists(), "docs/00-user-guide.md is missing (T80)"
    return GUIDE.read_text(encoding="utf-8")


def _section(heading: str) -> str:
    """The text under `### heading` up to the next heading of the same or a higher level."""
    text = _guide()
    m = re.search(rf"^###\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    assert m, f"the guide has no '### {heading}' section"
    rest = text[m.end():]
    nxt = re.search(r"^#{1,3}\s", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def _table_rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        if line.startswith("|") and not re.match(r"^\|\s*:?-{3,}", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(cells)
    return rows[1:]                      # the first row is the header


def _first_column_tokens(heading: str) -> list[str]:
    tokens = []
    for cells in _table_rows(_section(heading)):
        m = re.fullmatch(r"`([^`]+)`", cells[0])
        assert m, f"first column of '{heading}' must be one `name` in backticks, got: {cells[0]!r}"
        tokens.append(m.group(1))
    assert tokens, f"'{heading}' has no rows"
    return tokens


def _python_sources() -> dict[Path, str]:
    return {p: p.read_text(encoding="utf-8") for p in (ROOT / "job_hunt").rglob("*.py")}


def _config_reads() -> dict[str, set[str]]:
    """key -> where the code reads it: 'top' (config["k"]), 'candidate' (cand.get("k")) or 'telegram'."""
    kinds: dict[str, set[str]] = {}
    for src in _python_sources().values():
        for node in ast.walk(ast.parse(src)):
            key = recv = None
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                key, recv = node.args[0].value, ast.unparse(node.func.value)
            elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                key, recv = node.slice.value, ast.unparse(node.value)
            if key is None or recv is None:
                continue
            if "cand" in recv:
                kind = "candidate"
            elif "telegram" in recv or "tg_cfg" in recv:
                kind = "telegram"
            elif recv in {"config", "cfg", "self.config"}:
                kind = "top"
            else:
                continue
            kinds.setdefault(key, set()).add(kind)
    return kinds


def _setting_location(token: str) -> tuple[str, str]:
    """`candidate.min_score` -> ("candidate", "min_score"); `fetch_workers` -> ("top", "fetch_workers")."""
    if "." in token:
        parent, key = token.split(".", 1)
        return parent, key
    return "top", token


def test_the_guide_exists_and_is_linked_from_the_docs_index():
    _guide()
    assert "00-user-guide.md" in (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "00-user-guide.md" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_every_config_setting_the_guide_names_is_read_where_the_guide_says():
    """The bug this catches: docs/07 listed `scoring_mode` and `max_jobs_to_score_per_run` under `candidate`,
    but the code reads them at the top level, so a value put under `candidate` was ignored silently."""
    reads = _config_reads()
    wrong = []
    for token in _first_column_tokens("config.json settings"):
        parent, key = _setting_location(token)
        if parent not in reads.get(key, set()):
            wrong.append(f"{token}: the code reads {key!r} at {sorted(reads.get(key, set())) or 'nowhere'}")
    assert not wrong, "\n".join(wrong)


def test_every_key_of_the_example_config_is_in_the_guide():
    named = set(_first_column_tokens("config.json settings"))
    example = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    missing = []
    for key, value in example.items():
        if isinstance(value, dict):
            missing += [f"{key}.{k}" for k in value if f"{key}.{k}" not in named]
        elif key not in named:
            missing.append(key)
    assert not missing, f"config.example.json has keys the guide does not explain: {missing}"


def test_numeric_defaults_in_the_guide_are_the_ones_the_code_uses():
    from job_hunt import scanner
    from job_hunt.settings import max_posted_age_of, min_score_of

    expected = {
        "candidate.min_score": min_score_of({}),
        "candidate.max_posted_age_days": max_posted_age_of({}),
        "candidate.top_n": 5,
        "fetch_workers": scanner.DEFAULT_FETCH_WORKERS,
        "max_jobs_to_score_per_run": scanner.DEFAULT_MAX_JOBS_TO_SCORE,
    }
    rows = {cells[0].strip("`"): cells[1] for cells in _table_rows(_section("config.json settings"))}
    for token, value in expected.items():
        assert token in rows, f"the guide does not list {token}"
        assert rows[token].strip("` ") == str(value), f"{token}: guide says {rows[token]!r}, the code uses {value}"


def test_every_env_variable_the_guide_names_is_read_by_the_code():
    sources = "\n".join(_python_sources().values())
    unread = [v for v in _first_column_tokens(".env variables") if f'"{v}"' not in sources and f"'{v}'" not in sources]
    assert not unread, f"the code never reads: {unread}"


def test_every_prefilter_pattern_the_guide_names_is_a_regex_in_prefilter():
    from job_hunt import prefilter

    for name in _first_column_tokens("Pre-filter patterns"):
        assert isinstance(getattr(prefilter, name, None), re.Pattern), f"prefilter.{name} is not a compiled regex"


def test_the_filter_examples_in_the_guide_behave_as_the_guide_says():
    """The worked examples are run through the real `should_evaluate_job`, so the guide cannot go stale quietly."""
    from job_hunt.models import JobPosting
    from job_hunt.prefilter import should_evaluate_job

    rows = _table_rows(_section("What the filter does with these"))
    assert len(rows) >= 6
    for title, location, result in (r[:3] for r in rows):
        job = JobPosting(global_id="t:1", ats="t", company="X", title=title, location=location, is_remote=False,
                         url="https://example.com/1")
        kept, _ = should_evaluate_job(job)
        assert (result == "kept") is kept, f"{title!r} / {location!r}: the guide says {result!r}, the filter says kept={kept}"


def _backtick_spans() -> list[str]:
    """Every inline `span` and every command line inside a fenced block (comments after '#' removed)."""
    text = _guide()
    spans = []
    for block in re.findall(r"^```[a-z]*\n(.*?)^```", text, re.MULTILINE | re.DOTALL):
        spans += [line.split("  #")[0].strip() for line in block.splitlines() if line.strip() and not line.startswith("#")]
    spans += re.findall(r"(?<!`)`([^`\n]+)`(?!`)", re.sub(r"^```.*?^```", "", text, flags=re.MULTILINE | re.DOTALL))
    return spans


EXTERNAL_TOOLS = ("python3", "pip", "git", "cd ", "source", "cp ", "mkdir", "systemctl")   # not ours: their flags are theirs


def _flag_is_defined(flag: str) -> bool:
    """The flag appears as a whole word in the CLI, a script or a launcher."""
    files = [*_python_sources(), *(ROOT / "scripts").rglob("*.py"), *(ROOT / "scripts").rglob("*.sh"), ROOT / "run_daily.sh"]
    pattern = re.compile(rf"(?<![\w-]){re.escape(flag)}(?![\w-])")
    return any(pattern.search(Path(f).read_text(encoding="utf-8")) for f in files)


def test_every_autopilot_command_and_flag_in_the_guide_exists():
    main_src = (ROOT / "job_hunt" / "main.py").read_text(encoding="utf-8")
    bad = []
    for span in _backtick_spans():
        m = re.match(r"autopilot\s+([a-z]+)\b", span)
        if m and f'cmd == "{m.group(1)}"' not in main_src:
            bad.append(f"command: {span}")
        if span.startswith(EXTERNAL_TOOLS):
            continue
        for flag in re.findall(r"(?<![\w-])--[a-z][a-z-]*", span):
            if not _flag_is_defined(flag):
                bad.append(f"flag: {flag} (in `{span}`)")
    assert not bad, "\n".join(sorted(set(bad)))


def test_the_commands_in_the_fenced_blocks_are_really_checked():
    """The first version of this test never looked inside ``` blocks, where most commands are."""
    spans = _backtick_spans()
    assert any(s.startswith("autopilot scan") for s in spans)
    assert any(s.startswith("scripts/systemd/install.sh") for s in spans)
    assert _flag_is_defined("--posted-within") and _flag_is_defined("--uninstall")
    assert not _flag_is_defined("--no-such-flag")


LOCAL_ONLY = {".env", "config.json"}                      # gitignored: not in a fresh checkout
GENERATED = ("output/", "data/", "state/")                 # written by a scan


def test_every_repo_path_the_guide_names_exists():
    """Checks each word of every span and command line, so a path inside `python scripts/x.py ...` counts too."""
    known_files = {"config.example.json", "companies.json", "run_daily.sh", "README.md", "CLAUDE.md", "resume/YOUR_RESUME.md"}
    missing = []
    for span in _backtick_spans():
        for word in span.split():
            token = word.strip(",;:()\"'").removeprefix("./")
            if token in LOCAL_ONLY or token.startswith(GENERATED) or re.search(r"[<>*]|YYYY", token):
                continue
            if re.match(r"(docs|scripts|job_hunt|tests)/[\w./-]+$", token) or token in known_files:
                if not (ROOT / token).exists():
                    missing.append(token)
    assert not missing, f"the guide names files that do not exist: {missing}"


def test_the_path_check_sees_paths_inside_commands():
    spans = _backtick_spans()
    assert any("scripts/check_filter.py" in s for s in spans), "the guide's worked example must name the script"


@pytest.mark.parametrize("phrase", [
    "pip install -e",             # a plain install copies prefilter.py, and edits to the checkout would do nothing
    "RESUME_PATH",                # .env silently beats config.json for the resume path and the name
])
def test_the_guide_warns_about_the_two_traps(phrase):
    assert phrase in _guide()


def test_every_link_inside_the_guide_points_at_a_real_heading_or_file():
    text = _guide()
    slugs = set()
    for heading in re.findall(r"^#{1,6}\s+(.*)$", text, re.MULTILINE):
        slug = re.sub(r"[^\w\s-]", "", heading.lower().replace("`", "")).strip().replace(" ", "-")
        slugs.add(slug)
    broken = []
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        if target.startswith("#"):
            if target[1:] not in slugs:
                broken.append(target)
        elif not target.startswith("http"):
            path = target.split("#")[0]
            if not (GUIDE.parent / path).resolve().exists():
                broken.append(target)
    assert not broken, f"broken links in the guide: {broken}"
