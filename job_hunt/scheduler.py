"""`autopilot schedule on | off | status`: the daily scan, when the person asks for it (T121).

It is OFF by default: nothing in the package turns it on except `schedule on`, and `schedule off` removes what `on` wrote.
  - Linux: the systemd *user* timer of scripts/systemd (T07), which also makes up a run missed while the computer was off.
  - cron is the fallback (Linux without a user manager, and macOS): one line ending in `# rolesight-scan`; every other line
    of the crontab is left exactly as it was. A run missed while the computer is off is skipped.
  - Windows: not built; `on` says how to make the task in Task Scheduler.
Both methods run `run_daily.sh`, which logs to data/scan.log. Turning one method on removes the other, so a day has one run.
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

DEFAULT_TIME = "09:00"
CRON_MARK = "# rolesight-scan"             # ends every cron line this module writes, so `off` finds exactly those
TIMER_UNIT = "job-hunt-scan.timer"
UNIT_FILES = ("job-hunt-scan.service", TIMER_UNIT)     # never the recheck units (T28) or anything else named job-hunt-*
_TIME = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")


class ScheduleError(Exception):
    """Something the person can fix or should know; `main` prints it and exits 1."""


@dataclass(frozen=True)
class Entry:
    method: str        # "systemd" or "cron"
    at: str            # "HH:MM", local time
    detail: str = ""   # e.g. the timer's next run


def _platform() -> str:
    return sys.platform


def repo_root() -> Path:
    """The clone this package runs from: run_daily.sh and scripts/systemd live next to job_hunt/."""
    return Path(__file__).resolve().parent.parent


def parse_time(text: str) -> str:
    if not _TIME.fullmatch(text or ""):
        raise ScheduleError(f"the time must be a 24-hour HH:MM, for example 09:00 (got {text!r})")
    return text


def _run(argv: List[str], **kw) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(argv, capture_output=True, text=True, **kw)


# --- systemd ---------------------------------------------------------------------------------

def _unit_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")      # as scripts/systemd/install.sh spells it
    return Path(base) / "systemd" / "user"


def _systemd_usable() -> bool:
    """`systemctl --user` reaches a user manager (not so in a container, or over ssh without a session)."""
    return (_platform().startswith("linux") and shutil.which("systemctl") is not None
            and _run(["systemctl", "--user", "show-environment"]).returncode == 0)


def _systemd_installed() -> bool:
    return any((_unit_dir() / name).exists() for name in UNIT_FILES)


def _systemd_entry() -> Optional[Entry]:
    timer = _unit_dir() / TIMER_UNIT
    if not timer.exists() or shutil.which("systemctl") is None:
        return None
    if _run(["systemctl", "--user", "is-enabled", TIMER_UNIT]).stdout.strip() != "enabled":
        return None                      # files left behind, nothing scheduled
    found = re.search(r"^OnCalendar=\*-\*-\* (\d\d:\d\d):\d\d$", timer.read_text(), re.MULTILINE)
    nxt = _run(["systemctl", "--user", "show", TIMER_UNIT, "-p", "NextElapseUSecRealtime", "--value"]).stdout.strip()
    return Entry("systemd", found.group(1) if found else "?", f"next run {nxt}" if nxt else "")


def _enable_systemd(root: Path, at: str) -> None:
    installer = root / "scripts" / "systemd" / "install.sh"
    if not installer.is_file():
        raise ScheduleError(f"{installer} not found: schedule works from a clone of the repository")
    done = _run(["bash", str(installer), "--at", at])
    if done.returncode != 0:
        raise ScheduleError(f"installing the systemd timer failed: {(done.stderr or done.stdout).strip()}")


def _disable_systemd() -> bool:
    """Remove the scan timer (only job-hunt-scan.*) if it is there. Returns whether anything was."""
    if not _systemd_installed():
        return False
    usable = _systemd_usable()
    if usable:
        _run(["systemctl", "--user", "disable", "--now", TIMER_UNIT])
    for name in UNIT_FILES:
        (_unit_dir() / name).unlink(missing_ok=True)
    (_unit_dir() / "timers.target.wants" / TIMER_UNIT).unlink(missing_ok=True)       # the enable link, when systemctl could not
    if usable:
        _run(["systemctl", "--user", "daemon-reload"])
    return True


# --- cron ------------------------------------------------------------------------------------

def cron_line(repo: Path, at: str) -> str:
    """`M H * * * cd REPO && bash ./run_daily.sh >/dev/null 2>&1 # rolesight-scan` (run_daily.sh writes data/scan.log itself).
    A percent sign is a newline to cron unless escaped (crontab(5)); the folder name is shell-quoted."""
    hour, minute = parse_time(at).split(":")
    command = f"cd {shlex.quote(str(repo))} && bash ./run_daily.sh >/dev/null 2>&1".replace("%", "\\%")
    return f"{int(minute)} {int(hour)} * * * {command} {CRON_MARK}"


def _crontab_lines(strict: bool) -> List[str]:
    """The current crontab. No crontab is an empty one; any other failure raises when `strict` (so a write never starts
    from a crontab that could not be read) and reads as empty otherwise."""
    done = _run(["crontab", "-l"])
    if done.returncode == 0:
        return done.stdout.splitlines()
    if "no crontab" in done.stderr.lower() or not strict:
        return []
    raise ScheduleError(f"could not read your crontab: {done.stderr.strip()}")


def _write_crontab(lines: List[str]) -> None:
    if not any(line.strip() for line in lines):
        _run(["crontab", "-r"])
        return
    with tempfile.NamedTemporaryFile("w", suffix=".cron", delete=False) as fh:
        fh.write("\n".join(lines) + "\n")
    try:
        done = _run(["crontab", fh.name])
    finally:
        os.unlink(fh.name)
    if done.returncode != 0:
        raise ScheduleError(f"could not write your crontab: {done.stderr.strip()}")


def _cron_entry() -> Optional[Entry]:
    if shutil.which("crontab") is None:
        return None
    for line in _crontab_lines(strict=False):
        if CRON_MARK in line:
            fields = line.split()
            if len(fields) > 5 and fields[0].isdigit() and fields[1].isdigit():
                return Entry("cron", f"{int(fields[1]):02d}:{int(fields[0]):02d}")
            return Entry("cron", "?")
    return None


def _enable_cron(root: Path, at: str) -> None:
    kept = [line for line in _crontab_lines(strict=True) if CRON_MARK not in line]
    _write_crontab(kept + [cron_line(root, at)])


def _disable_cron() -> bool:
    if shutil.which("crontab") is None:
        return False
    lines = _crontab_lines(strict=False)
    kept = [line for line in lines if CRON_MARK not in line]
    if len(kept) == len(lines):
        return False
    _write_crontab(kept)
    return True


# --- the three actions -----------------------------------------------------------------------

WINDOWS_HELP = ("this computer runs Windows, where `schedule` is not built. Make the daily task yourself in Task Scheduler: "
                "a basic task, daily, action 'Start a program', program = your python (the .venv one), arguments = "
                "-m job_hunt scan, start in = the folder of this clone.")


def status() -> List[Entry]:
    if _platform().startswith("win"):
        return []
    return [e for e in (_systemd_entry(), _cron_entry()) if e]


def _choose(method: str) -> str:
    if method == "systemd":
        if not _systemd_usable():
            raise ScheduleError("a systemd user timer is not available here (`systemctl --user` cannot reach a user manager); "
                                "use --method cron")
        return "systemd"
    if method == "cron":
        if shutil.which("crontab") is None:
            raise ScheduleError("cron is not available here (no `crontab` program)")
        return "cron"
    if _systemd_usable():
        return "systemd"
    if shutil.which("crontab") is not None:
        return "cron"
    raise ScheduleError("neither a systemd user timer nor cron is available on this computer; run "
                        "`python -m job_hunt scan` from your own scheduler")


def enable(at: str = DEFAULT_TIME, method: str = "auto") -> Entry:
    """Turn the daily scan on at `at` (HH:MM, local time). Replaces any earlier schedule of ours, by either method."""
    at = parse_time(at)
    if _platform().startswith("win"):
        raise ScheduleError(WINDOWS_HELP)
    root = repo_root()
    if not (root / "run_daily.sh").is_file():
        raise ScheduleError(f"{root / 'run_daily.sh'} not found: schedule works from a clone of the repository (pip install -e .)")
    chosen = _choose(method)
    if chosen == "systemd":
        _enable_systemd(root, at)
        _disable_cron()
    else:
        _enable_cron(root, at)
        _disable_systemd()
    return Entry(chosen, at)


def disable() -> List[str]:
    """Turn it off by every method. Returns which ones had something to remove."""
    removed: List[str] = []
    if _platform().startswith("win"):
        return removed
    if _disable_systemd():
        removed.append("systemd timer")
    if _disable_cron():
        removed.append("cron line")
    return removed


# --- the command -----------------------------------------------------------------------------

def _time_arg(text: str) -> str:
    try:
        return parse_time(text)
    except ScheduleError as e:
        raise argparse.ArgumentTypeError(str(e))


def _describe(entry: Entry) -> str:
    how = ("systemd user timer; a run missed while the computer was off is made up when it is back on"
           if entry.method == "systemd" else "cron; a run missed while the computer is off is skipped")
    return f"every day at {entry.at} ({how}){'; ' + entry.detail if entry.detail else ''}"


def main(argv: List[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="autopilot schedule",
        description="Run the daily scan by itself. Off by default; `off` removes everything `on` wrote.",
        epilog="Both methods run run_daily.sh, which logs to data/scan.log.")
    parser.add_argument("action", choices=("on", "off", "status"))
    parser.add_argument("--at", type=_time_arg, default=DEFAULT_TIME, metavar="HH:MM",
                        help=f"time of day, 24-hour, local time (default {DEFAULT_TIME})")
    parser.add_argument("--method", choices=("auto", "systemd", "cron"), default="auto",
                        help="auto: the systemd user timer where it works, else cron")
    args = parser.parse_args(argv)
    try:
        if args.action == "on":
            entry = enable(args.at, args.method)
            print(f"Daily scan: ON, {_describe(entry)}.")
            print(f"  log: {repo_root() / 'data' / 'scan.log'}      turn it off: autopilot schedule off")
            if not (repo_root() / "config.json").exists():
                print(f"  Warning: {repo_root() / 'config.json'} is missing, so the scheduled scan will fail until you run: autopilot init")
        elif args.action == "off":
            removed = disable()
            print(f"Daily scan: OFF (removed: {', '.join(removed)})." if removed
                  else "Daily scan: OFF (it was already off; nothing changed).")
        else:
            entries = status()
            if not entries:
                print("Daily scan: OFF (the default; nothing is scheduled). Turn it on: autopilot schedule on [--at HH:MM]")
            for entry in entries:
                print(f"Daily scan: ON, {_describe(entry)}.")
            if len(entries) > 1:
                print("  Two schedules would run the scan twice a day: `autopilot schedule on` keeps one.")
    except ScheduleError as e:
        sys.exit(f"autopilot schedule: {e}")
