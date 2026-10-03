#!/usr/bin/env bash
# ==============================================================================
# Autopilot Job Hunt - Daily Automated Scan Runner
# ==============================================================================
# Executes scheduled scans across native ATS adapters, appends timestamped logs
# to data/scan.log, and dispatches Telegram notifications for high matches (>= 70).
# ==============================================================================
set -euo pipefail

# Ensure working directory is the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure runtime directories exist
mkdir -p data logs state output

# Select Python environment (.venv if available, otherwise python3)
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo "ERROR: Python runtime not found." >&2
    exit 1
fi

# Ensure threshold for Telegram alerts is set to >= 70
export MIN_SCORE="${MIN_SCORE:-70}"

LOG_FILE="data/scan.log"
START_TIMESTAMP="$(date -u '+%Y-%m-%d %H:%M:%SZ')"

echo "======================================================================" >> "$LOG_FILE"
echo "[$START_TIMESTAMP] Starting Autopilot Daily Job Scan (min_score=${MIN_SCORE})" | tee -a "$LOG_FILE"
echo "======================================================================" >> "$LOG_FILE"

# Optional pre-flight diagnostics
if [ "${RUN_PREFLIGHT_DOCTOR:-0}" = "1" ]; then
    echo "[$START_TIMESTAMP] Running pre-flight doctor check..." | tee -a "$LOG_FILE"
    "$PYTHON" -m job_hunt doctor 2>&1 | tee -a "$LOG_FILE"
fi

# Execute scan with per-line timestamped logging to data/scan.log
set +e
"$PYTHON" -m job_hunt scan "$@" 2>&1 | while IFS= read -r line; do
    echo "[$(date -u '+%Y-%m-%d %H:%M:%SZ')] $line"
done | tee -a "$LOG_FILE"
SCAN_STATUS=${PIPESTATUS[0]}
set -e

END_TIMESTAMP="$(date -u '+%Y-%m-%d %H:%M:%SZ')"
echo "----------------------------------------------------------------------" >> "$LOG_FILE"
echo "[$END_TIMESTAMP] Scan finished with exit code ${SCAN_STATUS}" | tee -a "$LOG_FILE"
echo "======================================================================" >> "$LOG_FILE"

exit "$SCAN_STATUS"
