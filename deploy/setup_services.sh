#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash deploy/setup_services.sh
#
# What it does:
# - creates backend/frontend systemd services
# - enables and starts them at boot
#
# Assumptions:
# - repo is at /home/<user>/display_computer
# - backend venv exists at backend/.venv

USER_NAME="${SUDO_USER:-$USER}"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
PROJECT_DIR="${HOME_DIR}/display_computer"
BACKEND_DIR="${PROJECT_DIR}/backend"
FRONTEND_DIR="${PROJECT_DIR}/frontend"
LOG_FILE="${PROJECT_DIR}/assets/logs/13_02_26_4_success.log"

if [[ ! -d "${PROJECT_DIR}" ]]; then
  echo "Project directory not found: ${PROJECT_DIR}"
  echo "Clone repo first into ${HOME_DIR}"
  exit 1
fi

if [[ ! -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
  echo "Backend venv not found at ${BACKEND_DIR}/.venv"
  echo "Run:"
  echo "  cd ${BACKEND_DIR}"
  echo "  python3 -m venv .venv"
  echo "  ./.venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi

sudo tee /etc/systemd/system/display-backend.service > /dev/null <<EOF
[Unit]
Description=Display Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${BACKEND_DIR}
Environment=DISPLAY_COMPUTER_LOG_FILE=${LOG_FILE}
ExecStart=${BACKEND_DIR}/.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/display-frontend.service > /dev/null <<EOF
[Unit]
Description=Display Frontend (Static Server)
After=network.target

[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${FRONTEND_DIR}
ExecStart=/usr/bin/python3 -m http.server 5173
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable display-backend.service
sudo systemctl enable display-frontend.service
sudo systemctl restart display-backend.service
sudo systemctl restart display-frontend.service

echo ""
echo "Done. Services are enabled and started."
echo "Check:"
echo "  systemctl status display-backend.service --no-pager"
echo "  systemctl status display-frontend.service --no-pager"
