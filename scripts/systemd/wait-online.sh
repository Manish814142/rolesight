#!/usr/bin/env bash
# ExecStartPre of the job-hunt units: wait until the network is up before a scan or recheck starts.
#
# A user unit cannot wait for the system's network-online.target: the user manager has no such unit
# (`systemctl --user show network-online.target` -> LoadState=not-found, 2026-10-10), so Wants=/After= on it do nothing.
# Persistent=true makes up a missed run as soon as the user manager starts (login, wake), often before Wi-Fi is
# connected, and a scan started then fetches nothing. This waits until a TCP connection to the Gemini API opens.
#
#   WAIT_ONLINE_SECONDS   how long to wait before giving up (default 300)
#   WAIT_ONLINE_INTERVAL  seconds between tries (default 5)
#   WAIT_ONLINE_PROBE     replaces the connection test with a command (tests use it; no network)
set -u

LIMIT="${WAIT_ONLINE_SECONDS:-300}"
INTERVAL="${WAIT_ONLINE_INTERVAL:-5}"
HOST="generativelanguage.googleapis.com"

probe() {
    if [ -n "${WAIT_ONLINE_PROBE:-}" ]; then
        bash -c "$WAIT_ONLINE_PROBE"
    else
        timeout 10 bash -c ": < /dev/tcp/$HOST/443" 2>/dev/null
    fi
}

start=$SECONDS
until probe; do
    if [ $((SECONDS - start)) -ge "$LIMIT" ]; then
        msg="[$(date -u '+%Y-%m-%d %H:%M:%SZ')] Not started: no network after ${LIMIT}s (no connection to $HOST:443)"
        echo "$msg" >&2
        if [ -d data ]; then echo "$msg" >> data/scan.log; fi
        exit 1
    fi
    sleep "$INTERVAL"
done
