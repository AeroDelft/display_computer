#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="${HOME}/.config/autostart"
DESKTOP_FILE="${AUTOSTART_DIR}/display-computer-dashboard.desktop"
START_SCRIPT="${REPO_DIR}/start_display.sh"

mkdir -p "${AUTOSTART_DIR}"
chmod +x "${START_SCRIPT}"

cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Name=Display Computer Dashboard
Comment=Launch dashboard on login
Exec=${START_SCRIPT}
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=8
EOF

echo "Autostart installed:"
echo "  ${DESKTOP_FILE}"
echo
echo "Next step: reboot and verify dashboard starts automatically."
