#!/usr/bin/env bash
#set -euo pipefail
set -x

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${REPO_DIR}/backend"
FRONTEND_DIR="${REPO_DIR}/frontend"
RUNTIME_DIR="${REPO_DIR}/.runtime"

sudo ip link set can0 down
sleep 2

sudo ip link set can0 up type can bitrate 500000
sudo ip link set can1 up type can bitrate 500000

mkdir -p "${RUNTIME_DIR}"

echo "[$(date -Is)] start_display.sh starting"
echo "DISPLAY=${DISPLAY:-<unset>} XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-<unset>}"

# If these are already running (e.g. after manual restart), stop old instances.
pkill -f "uvicorn server_logger:app --host 127.0.0.1 --port 8000" || true
pkill -f "python3 -m http.server 8080 --directory ${FRONTEND_DIR}" || true

gnome-terminal -- bash -c "cd '${FRONTEND_DIR}' && npm run build" 
# cd "${BACKEND_DIR}"

# Start backend API/WebSocket server.
gnome-terminal -- bash -c "cd '${BACKEND_DIR}' && .venv/bin/python3 -u -m uvicorn server_logger:app --host 127.0.0.1 --port 8000" 
# cd "${BACKEND_DIR}"
# exec "${BACKEND_DIR}/.venv/bin/python3 " -u -m uvicorn server_logger:app --host 127.0.0.1 --port 8000

echo $! > "${RUNTIME_DIR}/backend.pid"

# Start local frontend HTTP server (fully offline).
gnome-terminal -- bash -c "
  cd "${REPO_DIR}"
  exec python3 -m http.server 8080 --directory "${FRONTEND_DIR}"
"

echo $! > "${RUNTIME_DIR}/frontend.pid"

# Give servers a moment to start before launching browser.

URL="http://127.0.0.1:8080/index.html"



# # Keep the display awake (no screen blanking/power-save) when X is available.
# if command -v xset >/dev/null 2>&1; then
#   xset s off || true
#   xset -dpms || true
#   xset s noblank || true
# fi

# # Hide mouse cursor after a short idle period (optional).
# if command -v unclutter >/dev/null 2>&1; then
#   pkill -f "unclutter.*-root" || true
#   unclutter --idle 0.5 --root >/dev/null 2>&1 &
# fi

mkdir -p "${RUNTIME_DIR}/chromium-profile"

launch_browser_once() {
  if command -v chromium-browser >/dev/null 2>&1; then
    chromium-browser --start-fullscreen --kiosk --incognito --disable-pinch "${URL}"
  elif command -v chromium >/dev/null 2>&1; then
    cchromium-browser --start-fullscreen --kiosk --incognito --disable-pinch "${URL}"
  elif command -v google-chrome >/dev/null 2>&1; then
    gchromium-browser --start-fullscreen --kiosk --incognito --disable-pinch "${URL}"
  elif command -v firefox >/dev/null 2>&1; then
    firefox --start-fullscreen --kiosk --private-window --new-window "${URL}"
  else
    xdg-open "${URL}"
  fi
}

#sleep 5
firefox --new-window "${URL}" 
# Launch once only. If user closes browser, keep it closed.
#launch_browser_once
