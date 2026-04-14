#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash deploy/setup_kiosk.sh
#
# What it does:
# - installs chromium-browser (if missing)
# - creates autostart entry to open dashboard in kiosk mode at login

USER_NAME="${SUDO_USER:-$USER}"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
AUTOSTART_DIR="${HOME_DIR}/.config/autostart"
DESKTOP_FILE="${AUTOSTART_DIR}/display-kiosk.desktop"

sudo apt update
sudo apt install -y chromium-browser

mkdir -p "${AUTOSTART_DIR}"

cat > "${DESKTOP_FILE}" <<'EOF'
[Desktop Entry]
Type=Application
Name=Display Dashboard
Exec=chromium-browser --kiosk --incognito --noerrdialogs --disable-session-crashed-bubble http://127.0.0.1:5173
X-GNOME-Autostart-enabled=true
EOF

echo ""
echo "Done. Kiosk autostart configured at:"
echo "  ${DESKTOP_FILE}"
echo ""
echo "Important: enable Ubuntu automatic login for this user,"
echo "otherwise kiosk opens only after manual login."
