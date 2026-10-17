"""T121: `autopilot schedule on [--at HH:MM] | off | status`, the daily scan as an opt-in switch that is OFF by default.

Manish (2026-10-17): "if someone wants to schedule it on a daily basis it runs automatically, but don't start it on my laptop;
give users the option to turn it on and off, by default it's off."

Nothing here can reach the real scheduler: `systemctl` and `crontab` are stand-in programs at the front of PATH (the real
install.sh and the real subprocess calls run against them), HOME and XDG_CONFIG_HOME are empty temporary folders, and the
`system` fixture checks before every test that PATH really resolves both names to the stand-ins.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from job_hunt import main as cli
from job_hunt import scheduler

ROOT = Path(__file__).resolve().parent.parent

SYSTEMCTL = r"""#!/usr/bin/env bash
echo "systemctl $*" >> "$SHIM_LOG"
[ "$1" = "--user" ] || exit 9                       # a system-wide unit is never touched
shift
case "$1" in
    show-environment) exit "${SHIM_SYSTEMCTL_RC:-0}" ;;
    daemon-reload|list-timers) exit 0 ;;
    enable) if [ -n "$SHIM_ENABLE_FAILS" ]; then echo "Failed to enable unit: Access denied" >&2; exit 1; fi
            touch "$SHIM_STATE/enabled-$3"; exit 0 ;;
    disable) shift 2; for u in "$@"; do rm -f "$SHIM_STATE/enabled-$u"; done; exit 0 ;;
    is-enabled)
        if [ -e "$SHIM_STATE/enabled-$2" ]; then echo enabled; exit 0; fi
        echo "Failed to get unit file state for $2: No such file or directory" >&2; exit 1 ;;
    show) echo "Sun 2026-10-18 09:00:00 IST"; exit 0 ;;
esac
exit 0
"""

CRONTAB = r"""#!/usr/bin/env bash
echo "crontab $*" >> "$SHIM_LOG"
f="$SHIM_STATE/crontab"
case "$1" in
    -l) if [ -n "$SHIM_CRONTAB_DENIED" ]; then echo "crontab: you are not allowed to use this program" >&2; exit 1; fi
        if [ -e "$f" ]; then cat "$f"; else echo "no crontab for $USER" >&2; exit 1; fi ;;
    -r) if [ -e "$f" ]; then rm -f "$f"; else echo "no crontab for $USER" >&2; exit 1; fi ;;
    -*) exit 2 ;;
    *) cp "$1" "$f" ;;
esac
"""


class System:
    def __init__(self, root: Path):
        self.root = root
        self.shims, self.state = root / "shims", root / "state"
        self.log = root / "calls.log"
        self.units = root / "xdg" / "systemd" / "user"
        self.crontab = self.state / "crontab"

    def calls(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []

    def cron_lines(self) -> list[str]:
        return self.crontab.read_text().splitlines() if self.crontab.exists() else []

    def marked(self) -> list[str]:
        return [ln for ln in self.cron_lines() if scheduler.CRON_MARK in ln]


@pytest.fixture
def system(tmp_path, monkeypatch) -> System:
    s = System(tmp_path)
    s.shims.mkdir()
    s.state.mkdir()
    for name, body in (("systemctl", SYSTEMCTL), ("crontab", CRONTAB)):
        (s.shims / name).write_text(body)
        (s.shims / name).chmod(0o755)
    monkeypatch.setenv("PATH", f"{s.shims}:/usr/bin:/bin")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("SHIM_LOG", str(s.log))
    monkeypatch.setenv("SHIM_STATE", str(s.state))
    monkeypatch.delenv("SHIM_SYSTEMCTL_RC", raising=False)
    monkeypatch.delenv("SHIM_CRONTAB_DENIED", raising=False)
    monkeypatch.delenv("SHIM_ENABLE_FAILS", raising=False)
    monkeypatch.setattr(scheduler, "_platform", lambda: "linux")
    # The safety check: the real programs must be shadowed, or this test could change the machine it runs on.
    assert shutil.which("systemctl") == str(s.shims / "systemctl")
    assert shutil.which("crontab") == str(s.shims / "crontab")
    return s


def _cli(monkeypatch, capsys, *args: str) -> tuple[int, str]:
    """Run `autopilot schedule ...` through the real entry point; returns (exit code, everything printed)."""
    monkeypatch.setattr(sys, "argv", ["autopilot", "schedule", *args])
    code = 0
    try:
        cli.main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)     # sys.exit("message") exits 1
        if isinstance(e.code, str):
            print(e.code)
    captured = capsys.readouterr()
    return code, captured.out + captured.err


# --- off by default --------------------------------------------------------------------------

def test_by_default_nothing_is_scheduled(system, monkeypatch, capsys):
    assert scheduler.status() == []
    code, out = _cli(monkeypatch, capsys, "status")
    assert code == 0 and "OFF" in out and "autopilot schedule on" in out


def test_no_other_command_turns_the_schedule_on(system, monkeypatch, tmp_path):
    """The default is off by construction: init, check-filter, export and a status call never write to systemd or cron."""
    monkeypatch.chdir(tmp_path)
    for argv in (["init"], ["check-filter", "Java Developer", "Pune, India"], ["export"], ["schedule", "status"], ["schedule", "off"]):
        monkeypatch.setattr(sys, "argv", ["autopilot", *argv])
        try:
            cli.main()
        except SystemExit:
            pass
    writes = [c for c in system.calls() if re.search(r"enable|daemon-reload|crontab (?!-l)|install\.sh", c)]
    assert writes == [] and not system.units.exists() and not system.crontab.exists()


def test_only_the_schedule_command_can_reach_the_scheduler():
    """The static half of the same guarantee: no other module of the package imports it or the installer script."""
    users = sorted(p.name for p in (ROOT / "job_hunt").glob("*.py")
                   if p.name != "scheduler.py" and ("scheduler" in p.read_text() or "install.sh" in p.read_text()))
    assert users == ["main.py"]


# --- turning it on ---------------------------------------------------------------------------

def test_on_with_systemd_writes_the_units_enables_the_timer_and_leaves_cron_alone(system, monkeypatch, capsys):
    code, out = _cli(monkeypatch, capsys, "on", "--at", "07:30", "--method", "systemd")
    assert code == 0 and "ON" in out and "07:30" in out and "autopilot schedule off" in out
    assert "next login" in out and "logged in" in out          # T125: the user timer needs the user manager, which starts at login
    assert "OnCalendar=*-*-* 07:30:00" in (system.units / "job-hunt-scan.timer").read_text()
    assert "systemctl --user enable --now job-hunt-scan.timer" in system.calls()
    assert not system.crontab.exists()
    (entry,) = scheduler.status()
    assert (entry.method, entry.at) == ("systemd", "07:30") and "2026-10-18 09:00:00" in entry.detail


def test_on_with_cron_adds_one_marked_line_and_keeps_every_other_line(system, monkeypatch, capsys):
    system.crontab.write_text("MAILTO=me\n0 5 * * 1 /usr/bin/backup\n")
    code, out = _cli(monkeypatch, capsys, "on", "--at", "08:15", "--method", "cron")
    assert code == 0 and "08:15" in out
    assert "skipped" in out and "next login" not in out        # T125: cron does not catch up a run missed while the computer was off
    lines = system.cron_lines()
    assert lines[:2] == ["MAILTO=me", "0 5 * * 1 /usr/bin/backup"] and len(lines) == 3
    assert lines[2].startswith("15 8 * * * ") and lines[2].endswith(scheduler.CRON_MARK)
    assert not system.units.exists()
    (entry,) = scheduler.status()
    assert (entry.method, entry.at) == ("cron", "08:15")


def test_a_crontab_that_cannot_be_read_is_never_overwritten(system, monkeypatch, capsys):
    system.crontab.write_text("0 5 * * 1 /usr/bin/backup\n")
    monkeypatch.setenv("SHIM_CRONTAB_DENIED", "1")
    code, out = _cli(monkeypatch, capsys, "on", "--method", "cron")
    assert code == 1 and "could not read your crontab" in out
    assert system.cron_lines() == ["0 5 * * 1 /usr/bin/backup"] and not [c for c in system.calls() if c.startswith("crontab /")]
    code, out = _cli(monkeypatch, capsys, "off")                     # `off` and `status` are not stopped by it
    assert code == 0 and scheduler.status() == []


def test_turning_it_on_twice_is_one_schedule_with_the_new_time(system, monkeypatch, capsys):
    _cli(monkeypatch, capsys, "on", "--at", "08:15", "--method", "cron")
    _cli(monkeypatch, capsys, "on", "--at", "10:00", "--method", "cron")
    assert len(system.marked()) == 1 and system.marked()[0].startswith("0 10 * * * ")
    _cli(monkeypatch, capsys, "on", "--at", "06:05", "--method", "systemd")
    _cli(monkeypatch, capsys, "on", "--at", "06:45", "--method", "systemd")
    assert [e.at for e in scheduler.status()] == ["06:45"]
    assert system.marked() == []                      # switching to systemd took the cron line away: one run a day, not two
    _cli(monkeypatch, capsys, "on", "--at", "07:00", "--method", "cron")
    assert [(e.method, e.at) for e in scheduler.status()] == [("cron", "07:00")]
    assert not (system.units / "job-hunt-scan.timer").exists() and "systemctl --user disable --now job-hunt-scan.timer" in system.calls()


def test_the_default_time_is_nine(system, monkeypatch, capsys):
    _cli(monkeypatch, capsys, "on", "--method", "cron")
    assert system.marked()[0].startswith("0 9 * * * ")


def test_auto_takes_systemd_when_the_user_manager_answers_else_cron(system, monkeypatch, capsys):
    _cli(monkeypatch, capsys, "on")
    assert [e.method for e in scheduler.status()] == ["systemd"]
    _cli(monkeypatch, capsys, "off")
    monkeypatch.setenv("SHIM_SYSTEMCTL_RC", "1")      # `systemctl --user` cannot reach a user manager (a container, ssh without a session)
    _cli(monkeypatch, capsys, "on")
    assert [e.method for e in scheduler.status()] == ["cron"]


def test_on_macos_auto_means_cron(system, monkeypatch, capsys):
    monkeypatch.setattr(scheduler, "_platform", lambda: "darwin")
    _cli(monkeypatch, capsys, "on")
    assert [e.method for e in scheduler.status()] == ["cron"] and not system.units.exists()


def test_with_neither_tool_it_says_so_and_changes_nothing(system, monkeypatch, capsys):
    monkeypatch.setattr(scheduler.shutil, "which", lambda name, *a, **k: None)
    code, out = _cli(monkeypatch, capsys, "on")
    assert code != 0 and "systemd" in out and "cron" in out
    assert system.calls() == []


def test_windows_is_pointed_at_task_scheduler_and_nothing_runs(system, monkeypatch, capsys):
    monkeypatch.setattr(scheduler, "_platform", lambda: "win32")
    code, out = _cli(monkeypatch, capsys, "on")
    assert code != 0 and "Task Scheduler" in out and "-m job_hunt scan" in out
    assert system.calls() == []


@pytest.mark.parametrize("bad", ["25:00", "9:00", "09:60", "noon", "09:00:00", ""])
def test_a_bad_time_changes_nothing(system, monkeypatch, capsys, bad):
    code, out = _cli(monkeypatch, capsys, "on", "--at", bad)
    assert code == 2 and "HH:MM" in out
    assert system.calls() == [] and not system.units.exists() and not system.crontab.exists()


def test_a_missing_action_or_an_unknown_one_prints_the_usage(system, monkeypatch, capsys):
    for args in ([], ["start"], ["on", "--forever"]):
        code, out = _cli(monkeypatch, capsys, *args)
        assert code == 2 and "schedule" in out, args
    assert system.calls() == []


def test_it_still_turns_on_without_config_json_but_says_the_scan_will_fail(system, monkeypatch, capsys, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "run_daily.sh").write_text("exit 0\n")
    monkeypatch.setattr(scheduler, "repo_root", lambda: repo)
    code, out = _cli(monkeypatch, capsys, "on", "--method", "cron")
    assert code == 0 and "config.json" in out and "autopilot init" in out
    assert len(system.marked()) == 1
    (repo / "config.json").write_text("{}")
    _cli(monkeypatch, capsys, "off")
    code, out = _cli(monkeypatch, capsys, "on", "--method", "cron")
    assert code == 0 and "config.json" not in out


# --- turning it off --------------------------------------------------------------------------

def test_off_removes_what_on_wrote_and_nothing_else(system, monkeypatch, capsys):
    system.crontab.write_text("MAILTO=me\n0 5 * * 1 /usr/bin/backup\n")
    system.units.mkdir(parents=True)
    neighbours = ["job-hunt-wallpaper.service", "job-hunt-wallpaper.timer",          # a real neighbour on Manish's machine
                  "job-hunt-recheck.service", "job-hunt-recheck.timer"]               # the monthly check of T28 is not the daily scan
    for name in neighbours:
        (system.units / name).write_text("[Unit]\n")
    _cli(monkeypatch, capsys, "on", "--at", "08:15", "--method", "cron")
    _cli(monkeypatch, capsys, "on", "--at", "08:15", "--method", "systemd")
    _cli(monkeypatch, capsys, "on", "--at", "08:15", "--method", "cron")
    system.units.joinpath("job-hunt-scan.timer").write_text("[Timer]\n")          # a leftover unit file as well
    code, out = _cli(monkeypatch, capsys, "off")
    assert code == 0 and "OFF" in out
    assert system.cron_lines() == ["MAILTO=me", "0 5 * * 1 /usr/bin/backup"]
    assert sorted(p.name for p in system.units.glob("*")) == sorted(neighbours)
    assert scheduler.status() == []
    assert not [c for c in system.calls() if "wallpaper" in c]


def test_off_deletes_the_crontab_when_the_scan_line_was_all_it_held(system, monkeypatch, capsys):
    _cli(monkeypatch, capsys, "on", "--method", "cron")
    _cli(monkeypatch, capsys, "off")
    assert not system.crontab.exists() and "crontab -r" in system.calls()


def test_off_when_nothing_is_on_changes_nothing_and_says_so(system, monkeypatch, capsys):
    code, out = _cli(monkeypatch, capsys, "off")
    assert code == 0 and "OFF" in out and "already" in out.lower()
    assert [c for c in system.calls() if re.search(r"disable|enable|daemon-reload|crontab -r|crontab /", c)] == []


def test_off_works_where_systemd_has_gone_away_but_a_unit_file_is_left(system, monkeypatch, capsys):
    _cli(monkeypatch, capsys, "on", "--method", "systemd")
    wants = system.units / "timers.target.wants"
    wants.mkdir()
    (wants / "job-hunt-scan.timer").symlink_to(system.units / "job-hunt-scan.timer")     # what `systemctl enable` leaves
    monkeypatch.setenv("SHIM_SYSTEMCTL_RC", "1")
    code, _ = _cli(monkeypatch, capsys, "off")
    assert code == 0 and not (system.units / "job-hunt-scan.timer").exists()
    assert not (wants / "job-hunt-scan.timer").is_symlink()


def test_unit_files_left_behind_without_an_enabled_timer_are_not_a_schedule(system, monkeypatch, capsys):
    system.units.mkdir(parents=True)
    (system.units / "job-hunt-scan.timer").write_text("[Timer]\nOnCalendar=*-*-* 09:00:00\n")
    assert scheduler.status() == []
    code, out = _cli(monkeypatch, capsys, "status")
    assert code == 0 and "OFF" in out


def test_status_only_reads(system, monkeypatch, capsys):
    _cli(monkeypatch, capsys, "on", "--method", "systemd")
    system.log.write_text("")
    code, out = _cli(monkeypatch, capsys, "status")
    assert code == 0 and "ON" in out
    assert system.calls() and all(re.match(r"systemctl --user (show-environment|is-enabled|show)\b|crontab -l$", c) for c in system.calls()), system.calls()


# --- the command the schedule runs -------------------------------------------------------------

def test_the_cron_line_runs_run_daily_from_a_folder_with_spaces_and_a_percent_sign(tmp_path):
    repo = tmp_path / "my 100% repo"
    repo.mkdir()
    (repo / "run_daily.sh").write_text('echo "ran in $PWD" > ran.txt\n')
    line = scheduler.cron_line(repo, "07:05")
    minute, hour, dom, month, dow, command = line.split(None, 5)
    assert (minute, hour, dom, month, dow) == ("5", "7", "*", "*", "*")
    assert "100\\% repo" in command                             # an unescaped % would end the command there (crontab(5))
    command = command.replace("\\%", "%")                       # what cron(5) does with an escaped percent sign
    done = subprocess.run(["/bin/sh", "-c", command], env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert (repo / "ran.txt").read_text().strip() == f"ran in {repo}"
    assert line.endswith(scheduler.CRON_MARK)


def test_the_cron_command_reaches_the_scan_through_the_real_run_daily_in_crons_bare_environment(tmp_path):
    """cron starts the command with PATH=/usr/bin:/bin, no HOME and no terminal. A copy of the real run_daily.sh, with a
    stand-in for the venv's python that records its arguments, is run the way cron would run the line."""
    repo = tmp_path / "clone"
    (repo / ".venv" / "bin").mkdir(parents=True)
    shutil.copy(ROOT / "run_daily.sh", repo / "run_daily.sh")
    fake_python = repo / ".venv" / "bin" / "python"
    fake_python.write_text('#!/bin/sh\necho "python got: $*"\n')
    fake_python.chmod(0o755)
    command = scheduler.cron_line(repo, "09:00").split(None, 5)[5]
    done = subprocess.run(["/bin/sh", "-c", command], env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout == "", (done.stdout, done.stderr)       # nothing printed: cron would mail it
    log = (repo / "data" / "scan.log").read_text()
    assert "Starting Autopilot Daily Job Scan" in log and "python got: -m job_hunt scan" in log
    assert "Scan finished with exit code 0" in log


@pytest.mark.parametrize("text, ok", [("00:00", True), ("09:00", True), ("23:59", True), ("24:00", False), ("7:30", False),
                                      ("07:5", False), ("07-30", False), (" 07:30", False), ("09:00\n", False)])
def test_parse_time(text, ok):
    if ok:
        assert scheduler.parse_time(text) == text
    else:
        with pytest.raises(scheduler.ScheduleError):
            scheduler.parse_time(text)


# --- the units themselves ------------------------------------------------------------------------

def test_the_scan_unit_allows_a_run_that_scores_a_whole_day_of_both_models():
    """T119: with no cap (T118) a scan scores up to 1,000 jobs (500 on each model): measured 6.1-7.5 s a job, about 125 minutes,
    plus about 17 minutes to fetch 1,514 boards (the worst case, about 2.4 h); the unit's 3 h left too little room."""
    text = (ROOT / "scripts" / "systemd" / "job-hunt-scan.service.in").read_text()
    hours = int(re.search(r"^TimeoutStartSec=(\d+)h$", text, re.MULTILINE).group(1))
    assert hours >= 4


def test_a_failed_switch_to_systemd_keeps_the_cron_schedule_that_was_there(system, monkeypatch, capsys):
    """T121 review: `on` removes the other method only after the new one is in place; if the systemd timer cannot be
    enabled, the person's existing cron schedule must still be there (a mutant that removed cron first survived)."""
    assert _cli(monkeypatch, capsys, "on", "--method", "cron", "--at", "07:00")[0] == 0
    before = system.marked()
    assert len(before) == 1
    monkeypatch.setenv("SHIM_ENABLE_FAILS", "1")
    code, out = _cli(monkeypatch, capsys, "on", "--method", "systemd", "--at", "08:00")
    assert code == 1 and "failed" in out.lower()
    assert system.marked() == before
