#!/usr/bin/env bash
# Install (or remove) the daily scan as a systemd USER timer. Nothing is installed until you run this script.
#
#   scripts/systemd/install.sh                 # every day at 09:00 local time
#   scripts/systemd/install.sh --at 07:30      # another time
#   scripts/systemd/install.sh --with-recheck  # also the monthly companies.json health check (report only, T28)
#   scripts/systemd/install.sh --uninstall     # stop the timers and delete the unit files
#   scripts/systemd/install.sh --no-systemctl  # only write the unit files (what the tests use)
#
# It writes ~/.config/systemd/user/job-hunt-scan.service and .timer (paths filled in for this checkout) and runs
# `systemctl --user daemon-reload` and `systemctl --user enable --now job-hunt-scan.timer`. It touches no other unit.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="$REPO/scripts/systemd"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
AT="09:00"
ACTION="install"
SYSTEMCTL=1
RECHECK=0

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --at) [ $# -ge 2 ] || { echo "--at needs a time, HH:MM" >&2; exit 2; }; AT="$2"; shift 2 ;;
        --uninstall) ACTION="uninstall"; shift ;;
        --no-systemctl) SYSTEMCTL=0; shift ;;
        --with-recheck) RECHECK=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if ! [[ "$AT" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
    echo "--at must be a 24-hour time written HH:MM (for example 09:00), got '$AT'" >&2
    exit 2
fi

if [ "$ACTION" = "uninstall" ]; then
    if [ "$SYSTEMCTL" = 1 ]; then
        systemctl --user disable --now job-hunt-scan.timer job-hunt-recheck.timer 2>/dev/null || true
    fi
    rm -f "$UNIT_DIR"/job-hunt-scan.service "$UNIT_DIR"/job-hunt-scan.timer \
          "$UNIT_DIR"/job-hunt-recheck.service "$UNIT_DIR"/job-hunt-recheck.timer
    if [ "$SYSTEMCTL" = 1 ]; then systemctl --user daemon-reload; fi
    echo "Removed the job-hunt-scan and job-hunt-recheck units from $UNIT_DIR"
    exit 0
fi

# The clone may sit in a folder whose name has a space, %, $, " or \ ("my repo"). systemd splits a command line at spaces
# unless the word is quoted and reads % as a specifier (literal: %%) and, in a command line, $ as a variable (literal: $$)
# (systemd.service(5), systemd.syntax(7)); sed needs \, & and its | delimiter escaped in the replacement.
REPO_DIR="${REPO//\%/%%}"
REPO_ARG="${REPO//\\/\\\\}"; REPO_ARG="${REPO_ARG//\"/\\\"}"; REPO_ARG="${REPO_ARG//\%/%%}"; REPO_ARG="${REPO_ARG//\$/\$\$}"
sed_escape() { printf '%s' "$1" | sed -e 's/[\\&|]/\\&/g'; }

mkdir -p "$UNIT_DIR"
UNITS="job-hunt-scan"
[ "$RECHECK" = 1 ] && UNITS="$UNITS job-hunt-recheck"
for unit in $UNITS; do
    for kind in service timer; do
        sed -e "s|@REPO_DIR@|$(sed_escape "$REPO_DIR")|g" -e "s|@REPO_ARG@|$(sed_escape "$REPO_ARG")|g" -e "s|@AT@|$AT|g" \
            "$SRC/$unit.$kind.in" > "$UNIT_DIR/$unit.$kind"
    done
    echo "Wrote $UNIT_DIR/$unit.service and $unit.timer"
done

if [ "$SYSTEMCTL" = 1 ]; then
    systemctl --user daemon-reload
    for unit in $UNITS; do systemctl --user enable --now "$unit.timer"; done
    systemctl --user list-timers 'job-hunt-*' --no-pager
    echo "Run one scan now with:  systemctl --user start job-hunt-scan.service   (log: data/scan.log, journalctl --user -u job-hunt-scan)"
fi
