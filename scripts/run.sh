#!/usr/bin/env bash
# Ouroboros server runner with restart-on-exit-42 logic.
# Exit codes:
#   42 = restart requested (self-modification, /restart command)
#   99 = panic stop (do NOT restart)
#   anything else = crash (restart after delay)
#
# Usage: bash scripts/run.sh
# Or via systemd: see scripts/ouroboros.service

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$REPO_DIR/.venv/bin/python3"
SERVER="$REPO_DIR/server.py"

# Fallback to system python if no venv
if [ ! -x "$VENV_PYTHON" ]; then
    VENV_PYTHON="python3"
fi

CRASH_DELAY=5          # seconds to wait after an unexpected crash
MAX_RAPID_CRASHES=5    # consecutive crashes before giving up
RAPID_WINDOW=60        # seconds — if a crash happens within this window, it counts as rapid

rapid_crash_count=0
last_start_time=0

echo "[ouroboros] Starting Ouroboros server loop"
echo "[ouroboros] Repo: $REPO_DIR"
echo "[ouroboros] Python: $VENV_PYTHON"

while true; do
    last_start_time=$(date +%s)

    echo "[ouroboros] $(date -Iseconds) — Launching server.py"
    set +e
    cd "$REPO_DIR" && "$VENV_PYTHON" "$SERVER"
    exit_code=$?
    set -e
    echo "[ouroboros] $(date -Iseconds) — server.py exited with code $exit_code"

    # Exit code 42: intentional restart (self-modification)
    if [ $exit_code -eq 42 ]; then
        echo "[ouroboros] Restart requested (exit 42). Restarting immediately..."
        rapid_crash_count=0
        sleep 1  # brief pause to let git operations settle
        continue
    fi

    # Exit code 99: panic stop — do NOT restart
    if [ $exit_code -eq 99 ]; then
        echo "[ouroboros] PANIC STOP (exit 99). Not restarting."
        exit 99
    fi

    # Exit code 0: clean shutdown — do NOT restart
    if [ $exit_code -eq 0 ]; then
        echo "[ouroboros] Clean shutdown (exit 0). Not restarting."
        exit 0
    fi

    # Any other exit code: unexpected crash
    now=$(date +%s)
    elapsed=$((now - last_start_time))

    if [ $elapsed -lt $RAPID_WINDOW ]; then
        rapid_crash_count=$((rapid_crash_count + 1))
        echo "[ouroboros] Rapid crash #$rapid_crash_count (ran for ${elapsed}s)"
    else
        rapid_crash_count=1
        echo "[ouroboros] Crash after ${elapsed}s of runtime"
    fi

    if [ $rapid_crash_count -ge $MAX_RAPID_CRASHES ]; then
        echo "[ouroboros] $MAX_RAPID_CRASHES rapid crashes in a row. Giving up."
        echo "[ouroboros] Check logs: ~/Ouroboros/data/logs/"
        exit 1
    fi

    echo "[ouroboros] Restarting in ${CRASH_DELAY}s..."
    sleep $CRASH_DELAY
done
