#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${REPO_DIR}/backend"
FRONTEND_DIR="${REPO_DIR}/frontend"
RUNTIME_DIR="${REPO_DIR}/.runtime"

mkdir -p "${RUNTIME_DIR}"
exec > "${RUNTIME_DIR}/launcher.log" 2>&1

echo "[$(date -Is)] start_display.sh starting"
echo "DISPLAY=${DISPLAY:-<unset>} XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-<unset>}"

# If these are already running (e.g. after manual restart), stop old instances.
pkill -f "uvicorn server_new:app --host 127.0.0.1 --port 8000" || true
pkill -f "python3 -m http.server 8080 --directory ${FRONTEND_DIR}" || true

# Start backend API/WebSocket server.
(
  cd "${BACKEND_DIR}"
  exec "${BACKEND_DIR}/.venv/bin/python" -m uvicorn server_new:app --host 127.0.0.1 --port 8000
) > "${RUNTIME_DIR}/backend.log" 2>&1 &
echo $! > "${RUNTIME_DIR}/backend.pid"

# Start local frontend HTTP server (fully offline).
(
  cd "${REPO_DIR}"
  exec python3 -m http.server 8080 --directory "${FRONTEND_DIR}"
) > "${RUNTIME_DIR}/frontend.log" 2>&1 &
echo $! > "${RUNTIME_DIR}/frontend.pid"

# Give servers a moment to start before launching browser.
sleep 2

URL="http://127.0.0.1:8080/index.html"

# Keep the display awake (no screen blanking/power-save) when X is available.
if command -v xset >/dev/null 2>&1; then
  xset s off || true
  xset -dpms || true
  xset s noblank || true
fi

# Hide mouse cursor after a short idle period (optional).
if command -v unclutter >/dev/null 2>&1; then
  pkill -f "unclutter.*-root" || true
  unclutter --idle 0.5 --root >/dev/null 2>&1 &
fi

launch_browser_once() {
  if command -v chromium-browser >/dev/null 2>&1; then
    chromium-browser --kiosk --incognito --disable-pinch "${URL}"
  elif command -v chromium >/dev/null 2>&1; then
    chromium --kiosk --incognito --disable-pinch "${URL}"
  elif command -v google-chrome >/dev/null 2>&1; then
    google-chrome --kiosk --incognito --disable-pinch "${URL}"
  elif command -v firefox >/dev/null 2>&1; then
    firefox --kiosk --private-window --new-window "${URL}"
  else
    xdg-open "${URL}"
  fi
}

# Launch once only. If user closes browser, keep it closed.
launch_browser_once
