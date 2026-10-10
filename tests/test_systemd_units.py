"""T07: the daily scan as a systemd USER timer. The tests render the units into a temporary directory with
--no-systemctl: nothing is ever enabled or started, and the real ~/.config/systemd/user is never touched."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "scripts" / "systemd" / "install.sh"


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path), "HOME": str(tmp_path / "home")}
    return subprocess.run(["bash", str(INSTALL), *args], capture_output=True, text=True, env=env, cwd=tmp_path)


def _units(tmp_path: Path) -> Path:
    return tmp_path / "systemd" / "user"


def test_install_renders_both_units_with_this_repos_paths(tmp_path):
    r = _run(tmp_path, "--no-systemctl")
    assert r.returncode == 0, r.stderr
    service = (_units(tmp_path) / "job-hunt-scan.service").read_text()
    timer = (_units(tmp_path) / "job-hunt-scan.timer").read_text()
    assert f"WorkingDirectory={ROOT}" in service
    assert f"ExecStart=/usr/bin/env bash {ROOT}/run_daily.sh" in service
    assert "Type=oneshot" in service
    assert "OnCalendar=*-*-* 09:00:00" in timer and "Persistent=true" in timer and "WantedBy=timers.target" in timer
    assert "@" not in service + timer                                  # every placeholder was filled


def test_the_time_of_day_can_be_chosen(tmp_path):
    assert _run(tmp_path, "--no-systemctl", "--at", "07:45").returncode == 0
    assert "OnCalendar=*-*-* 07:45:00" in (_units(tmp_path) / "job-hunt-scan.timer").read_text()


@pytest.mark.parametrize("bad", ["25:00", "9:00", "09:60", "noon", "09:00:00"])
def test_a_bad_time_installs_nothing(tmp_path, bad):
    r = _run(tmp_path, "--no-systemctl", "--at", bad)
    assert r.returncode == 2 and "HH:MM" in r.stderr
    assert not _units(tmp_path).exists()


def test_an_unknown_flag_installs_nothing(tmp_path):
    r = _run(tmp_path, "--no-systemctl", "--enable-everything")
    assert r.returncode == 2
    assert not _units(tmp_path).exists()


def test_uninstall_removes_the_units(tmp_path):
    assert _run(tmp_path, "--no-systemctl").returncode == 0
    assert _run(tmp_path, "--no-systemctl", "--uninstall").returncode == 0
    assert not list(_units(tmp_path).glob("job-hunt-scan.*"))


def test_other_units_in_the_directory_are_left_alone(tmp_path):
    _units(tmp_path).mkdir(parents=True)
    other = _units(tmp_path) / "job-hunt-wallpaper.timer"
    other.write_text("keep me")
    assert _run(tmp_path, "--no-systemctl").returncode == 0
    assert _run(tmp_path, "--no-systemctl", "--uninstall").returncode == 0
    assert other.read_text() == "keep me"


@pytest.mark.skipif(shutil.which("systemd-analyze") is None, reason="systemd-analyze not installed")
def test_systemd_itself_accepts_the_rendered_units(tmp_path):
    """The real consumer: systemd-analyze parses the files the way the user manager would."""
    assert _run(tmp_path, "--no-systemctl").returncode == 0
    r = subprocess.run(["systemd-analyze", "--user", "verify", str(_units(tmp_path) / "job-hunt-scan.service"),
                        str(_units(tmp_path) / "job-hunt-scan.timer")], capture_output=True, text=True)
    assert r.returncode == 0 and r.stderr.strip() == "", r.stderr


# -- T28: the monthly recheck timer is optional and report-only ---------------------------------------------------

def test_the_recheck_timer_is_only_installed_on_request(tmp_path):
    assert _run(tmp_path, "--no-systemctl").returncode == 0
    assert not (_units(tmp_path) / "job-hunt-recheck.timer").exists()
    assert _run(tmp_path, "--no-systemctl", "--with-recheck").returncode == 0
    service = (_units(tmp_path) / "job-hunt-recheck.service").read_text()
    timer = (_units(tmp_path) / "job-hunt-recheck.timer").read_text()
    assert f"ExecStart=/usr/bin/env bash {ROOT}/scripts/monthly_recheck.sh" in service
    assert f"WorkingDirectory={ROOT}" in service
    assert "OnCalendar=*-*-01 10:00:00" in timer and "Persistent=true" in timer
    assert "@" not in service + timer


def test_uninstall_removes_the_recheck_units_too(tmp_path):
    assert _run(tmp_path, "--no-systemctl", "--with-recheck").returncode == 0
    assert _run(tmp_path, "--no-systemctl", "--uninstall").returncode == 0
    assert not list(_units(tmp_path).glob("job-hunt-*"))


@pytest.mark.skipif(shutil.which("systemd-analyze") is None, reason="systemd-analyze not installed")
def test_systemd_accepts_the_recheck_units(tmp_path):
    assert _run(tmp_path, "--no-systemctl", "--with-recheck").returncode == 0
    r = subprocess.run(["systemd-analyze", "--user", "verify", str(_units(tmp_path) / "job-hunt-recheck.service"),
                        str(_units(tmp_path) / "job-hunt-recheck.timer")], capture_output=True, text=True)
    assert r.returncode == 0 and r.stderr.strip() == "", r.stderr
