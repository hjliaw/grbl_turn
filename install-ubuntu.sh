#!/usr/bin/env bash
# grbl_turn installer for Ubuntu (22.04+, x86_64 or arm64).
#
# Run as your normal user from the repo checkout:
#     ./install-ubuntu.sh              install + app-menu launcher
#     ./install-ubuntu.sh --autostart  also start the app at login
#
# Installs into ~/.local/share/grbl_turn/venv and adds a launcher to
# the applications menu. Log out/in once afterwards so the dialout
# group (serial port access) takes effect.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$HOME/.local/share/grbl_turn/venv"
PYTHON="$VENV/bin/python"

if [ "$(id -u)" -eq 0 ]; then
    echo "Run as your normal user, not root." >&2
    exit 1
fi

echo "==> System packages"
sudo apt-get update
# libxcb-cursor0: required by Qt 6's xcb platform plugin
sudo apt-get install -y python3-venv python3-pip libxcb-cursor0

echo "==> Virtualenv at $VENV"
mkdir -p "$(dirname "$VENV")"
python3 -m venv "$VENV"
"$PYTHON" -m pip install --upgrade pip wheel

echo "==> Installing grbl_turn (pulls PySide6 + pyserial)"
# a stale build/ from an earlier install can shadow newer source files
rm -rf "$REPO_DIR/build"
"$PYTHON" -m pip install "$REPO_DIR"

echo "==> Smoke test (imports only)"
"$PYTHON" - <<'EOF'
from PySide6.QtSvgWidgets import QSvgWidget
import serial
import grbl_turn.app
print("imports OK")
EOF

echo "==> Serial port access (dialout group)"
sudo usermod -aG dialout "$USER"

echo "==> Application-menu launcher"
ICON="$("$PYTHON" -c 'from grbl_turn import ICONS; print(ICONS / "grbl_turn-256.png")')"
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/grbl_turn.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=grbl_turn
Comment=Conversational lathe GUI
Exec=$PYTHON -m grbl_turn
Icon=$ICON
Categories=Utility;Engineering;
Terminal=false
EOF

if [ "${1:-}" = "--autostart" ]; then
    echo "==> Autostart at login"
    mkdir -p "$HOME/.config/autostart"
    cp "$HOME/.local/share/applications/grbl_turn.desktop" \
       "$HOME/.config/autostart/grbl_turn.desktop"
fi

echo
echo "Done. Launch 'grbl_turn' from the applications menu, or:"
echo "    $PYTHON -m grbl_turn"
echo "Log out and back in once for serial-port (dialout) access."
echo "GRBL appears as /dev/ttyUSB0 or /dev/ttyACM0."
