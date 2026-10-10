#!/usr/bin/env bash
# Monthly health check of companies.json (T28). It only REPORTS: the check runs on a copy, and the real list is never
# written. Read data/recheck/diff.<date>.txt, then apply what you agree with by hand:
#   cp data/recheck/companies.<date>.json companies.json && cp companies.json job_hunt/data/companies.json
#
# `discover --recheck` re-verifies every board (liveness, India jobs, staleness); boards that fail are re-discovered by
# name (an ATS migration) or dropped. A transient failure drops a board too, so look at the diff before copying anything.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

if [ -n "${PYTHON:-}" ]; then
    PY="$PYTHON"
elif [ -x "$REPO/.venv/bin/python" ]; then
    PY="$REPO/.venv/bin/python"
else
    PY="python3"
fi

STAMP="$(date +%Y-%m-%d)"
OUT="data/recheck"
COPY="$OUT/companies.$STAMP.json"
REPORT="$OUT/report.$STAMP.csv"
VERIFIED="$OUT/verified.$STAMP.json"     # discover writes this next to the report instead of into the repository root
DIFF="$OUT/diff.$STAMP.txt"
mkdir -p "$OUT"
cp companies.json "$COPY"

echo "Rechecking $(basename "$REPO")/companies.json on a copy: $COPY"
"$PY" -m job_hunt discover --recheck --merge "$COPY" --report "$REPORT" --out "$VERIFIED"

diff -u companies.json "$COPY" > "$DIFF" || true     # diff exits 1 when the files differ
changed="$(grep -c '^[-+] ' "$DIFF" || true)"
if [ "$changed" = "0" ]; then
    echo "No changes: every board is still live. Report: $REPORT"
else
    echo "$changed line(s) differ from companies.json. Read the diff: $DIFF   (report: $REPORT)"
fi
echo "companies.json itself was not changed."
