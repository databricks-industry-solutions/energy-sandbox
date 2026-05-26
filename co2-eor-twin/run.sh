#!/usr/bin/env bash
# Launches both processes for the CO2-EOR Digital Twin demo:
#   1. FastAPI sidecar on port 8001 (Genie + Supervisor)
#   2. Express server on port 8000  (twin / commercial / map / agent / shift + SPA + /api/genie + /api/supervisor proxy)
#
# Used by Databricks Apps via app.yaml. Both processes log to the foreground;
# if either dies the launcher exits non-zero so Apps restarts the container.

set -euo pipefail

cd "$(dirname "$0")"

export AI_PORT="${AI_PORT:-8001}"
export PORT="${PORT:-8000}"
export TWIN_BASE_URL="${TWIN_BASE_URL:-http://localhost:${PORT}}"
export AI_BASE_URL="${AI_BASE_URL:-http://localhost:${AI_PORT}}"

# Ensure Python deps are present (Apps installs requirements.txt at root automatically;
# in local dev this is a no-op if already installed).
if [ -f pyserver/requirements.txt ] && [ "${SKIP_PIP_INSTALL:-0}" != "1" ]; then
  python3 -m pip install --quiet --disable-pip-version-check -r pyserver/requirements.txt || true
fi

# Start the FastAPI sidecar in the background.
python3 -m uvicorn pyserver.app:app --host 0.0.0.0 --port "${AI_PORT}" &
AI_PID=$!

cleanup() {
  echo "Shutting down (AI_PID=${AI_PID})"
  kill "${AI_PID}" 2>/dev/null || true
  wait "${AI_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Start Express in the foreground; if it exits we tear down the sidecar.
exec node dist/index.js
