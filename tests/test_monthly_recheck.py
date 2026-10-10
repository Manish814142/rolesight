"""T28: the monthly `discover --recheck` run only reports. It works on a COPY of companies.json and leaves a diff and a
report for Manish to read; the real list is never written. The tests replace the Python interpreter with a stub, so no
network is touched."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "monthly_recheck.sh"

# What `python -m job_hunt discover --recheck --merge COPY --report REPORT` would do on a bad day: drop one board from
# the copy and write the report. Anything else (a write to any other file) would show in the assertions below.
STUB = textwrap.dedent("""\
    #!/usr/bin/env bash
    [ "$1" = "-m" ] && [ "$2" = "job_hunt" ] && [ "$3" = "discover" ] && [ "$4" = "--recheck" ] || { echo "unexpected: $*" >&2; exit 9; }
    copy=""; report=""
    while [ $# -gt 0 ]; do
        case "$1" in --merge) copy="$2"; shift 2 ;; --report) report="$2"; shift 2 ;; *) shift ;; esac
    done
    grep -v '"name": "Gone Inc"' "$copy" > "$copy.tmp" && mv "$copy.tmp" "$copy"
    echo "seed,verdict" > "$report"; echo "Gone Inc,dropped" >> "$report"
""")

LIST = '[\n  {"name": "Stays", "ats": "greenhouse", "slug": "stays"},\n  {"name": "Gone Inc", "ats": "lever", "slug": "gone"}\n]\n'


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _setup(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "scripts" / "monthly_recheck.sh")
    (repo / "companies.json").write_text(LIST)
    stub = tmp_path / "fakepython"
    stub.write_text(STUB)
    stub.chmod(0o755)
    return repo


def _run(tmp_path: Path, repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHON": str(tmp_path / "fakepython")}
    return subprocess.run(["bash", str(repo / "scripts" / "monthly_recheck.sh"), *args], capture_output=True, text=True,
                          env=env, cwd=tmp_path)


def test_the_run_leaves_a_diff_and_a_report_and_never_touches_the_real_list(tmp_path):
    repo = _setup(tmp_path)
    before = _sha(repo / "companies.json")
    r = _run(tmp_path, repo)
    assert r.returncode == 0, r.stderr
    assert _sha(repo / "companies.json") == before                        # the done-when: companies.json is unchanged
    out = repo / "data" / "recheck"
    [diff] = list(out.glob("diff.*.txt"))
    [report] = list(out.glob("report.*.csv"))
    [copy] = list(out.glob("companies.*.json"))
    assert '-  {"name": "Gone Inc", "ats": "lever", "slug": "gone"}' in diff.read_text()
    assert "Gone Inc,dropped" in report.read_text()
    assert "Gone Inc" not in copy.read_text() and "Stays" in copy.read_text()
    assert "1 line" in r.stdout and str(diff.relative_to(repo)) in r.stdout    # tells the reader where to look


def test_an_unchanged_list_says_so(tmp_path):
    repo = _setup(tmp_path)
    (repo / "companies.json").write_text(LIST.replace('  {"name": "Gone Inc", "ats": "lever", "slug": "gone"}\n', "").replace('},\n]', '}\n]'))
    r = _run(tmp_path, repo)
    assert r.returncode == 0 and "no changes" in r.stdout.lower()


def test_a_failing_recheck_fails_loudly_and_still_leaves_the_real_list_alone(tmp_path):
    repo = _setup(tmp_path)
    (tmp_path / "fakepython").write_text("#!/usr/bin/env bash\necho boom >&2\nexit 3\n")
    before = _sha(repo / "companies.json")
    r = _run(tmp_path, repo)
    assert r.returncode == 3 and "boom" in r.stderr + r.stdout
    assert _sha(repo / "companies.json") == before
