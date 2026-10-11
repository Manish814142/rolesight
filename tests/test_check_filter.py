"""T80: scripts/check_filter.py lets someone who edits job_hunt/prefilter.py see what the filter does with one job."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_filter.py"


def _run(*args):
    done = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout.strip()


def test_a_backend_job_in_an_indian_city_is_kept():
    code, out = _run("Senior Backend Engineer", "Bengaluru, India")
    assert code == 0 and out == "KEPT"


def test_an_excluded_title_is_rejected_with_the_real_reason():
    code, out = _run("Java Developer", "Bengaluru, India")
    assert code == 0
    assert out.startswith("REJECTED") and "java" in out.lower()


def test_a_location_outside_india_is_rejected():
    _, out = _run("Backend Engineer", "Berlin, Germany")
    assert out.startswith("REJECTED") and "non-India" in out


def test_the_remote_flag_changes_the_answer_for_a_place_the_filter_does_not_know():
    _, without_flag = _run("Backend Engineer", "Lisbon")
    _, with_flag = _run("Backend Engineer", "Lisbon", "--remote")
    assert without_flag.startswith("REJECTED")
    assert with_flag == "KEPT"


def test_it_says_how_to_call_it_when_the_title_is_missing():
    done = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=60)
    assert done.returncode != 0
    assert "Usage" in done.stderr or "usage" in done.stderr
