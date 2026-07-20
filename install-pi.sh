#!/usr/bin/env bash
# grbl_turn installer for Raspberry Pi 4 + official 7" touchscreen.
#
# Run as your normal desktop user from the repo checkout on the Pi —
# desktop autologin lands on this same account (via SUDO_USER):
#     ./install-pi.sh            install; on an existing working
#                                install, update the app code only
#     ./install-pi.sh --fresh    wipe the venv, full reinstall
# Needs sudo rights (asks when required). Reboot when it finishes;
# the Pi then boots straight into the app, fullscreen.
#
# The app fullscreens itself on screens <= 820x500, so the 7" panel
# (800x480) needs no extra flags.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$HOME/.local/share/grbl_turn/venv"
PYTHON="$VENV/bin/python"

if [ "$(id -u)" -eq 0 ]; then
    echo "Run as the normal desktop user, not root." >&2
    exit 1
fi

if [ "$(uname -m)" != "aarch64" ]; then
    echo "This needs 64-bit Raspberry Pi OS (aarch64) — PySide6 has no" >&2
    echo "32-bit wheels. Reimage with the 64-bit OS and rerun." >&2
    exit 1
fi

if [ "${1:-}" = "--fresh" ]; then
    echo "==> --fresh: removing $VENV"
    rm -rf "$VENV"
fi

# with a working venv only the app package needs replacing — skip apt,
# venv creation, and dependency resolution (PySide6 stays as-is)
UPDATE=0
if "$PYTHON" -c "import grbl_turn" >/dev/null 2>&1; then
    UPDATE=1
fi

# a stale build/ from an earlier install can shadow newer source files
rm -rf "$REPO_DIR/build"

if [ "$UPDATE" -eq 1 ]; then
    echo "==> Existing install found: updating app code only" \
         "(--fresh for a full reinstall)"
    "$PYTHON" -m pip install --no-deps "$REPO_DIR"
fi

if [ "$UPDATE" -eq 0 ]; then
echo "==> System packages"
sudo apt-get update
# libxcb-cursor0: required by Qt 6's xcb platform plugin
sudo apt-get install -y python3-venv python3-pip libxcb-cursor0

echo "==> Virtualenv at $VENV"
mkdir -p "$(dirname "$VENV")"
python3 -m venv "$VENV"
"$PYTHON" -m pip install --upgrade pip wheel

echo "==> Installing grbl_turn (pulls PySide6 + pyserial)"
if ! "$PYTHON" -m pip install "$REPO_DIR"; then
    # No usable PySide6 wheel (old OS image): fall back to the distro's
    # PySide6 (Qt 6.4 on Bookworm — sufficient) via system site packages.
    echo "==> pip PySide6 failed; falling back to distro python3-pyside6"
    sudo apt-get install -y python3-pyside6.qtwidgets \
        python3-pyside6.qtsvgwidgets
    rm -rf "$VENV"
    python3 -m venv --system-site-packages "$VENV"
    "$PYTHON" -m pip install --upgrade pip wheel
    "$PYTHON" -m pip install --no-deps "$REPO_DIR"
    "$PYTHON" -m pip install pyserial
fi
fi   # UPDATE=0 (full install)

echo "==> Smoke test (imports only)"
"$PYTHON" - <<'EOF'
from PySide6.QtSvgWidgets import QSvgWidget
import serial
import grbl_turn.app
print("imports OK")
EOF

if [ "$UPDATE" -eq 0 ]; then
    echo "==> Serial port access (dialout group)"
    sudo usermod -aG dialout "$USER"
fi

echo "==> Autostart entry"
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/grbl_turn.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=grbl_turn
Comment=Conversational lathe GUI
Exec=$PYTHON -m grbl_turn
X-GNOME-Autostart-enabled=true
EOF

if [ "$UPDATE" -eq 1 ]; then
    echo
    echo "Done. Update installed — restart the app to run the new code."
    exit 0
fi

echo "==> Boot to desktop with autologin, no screen blanking"
sudo raspi-config nonint do_boot_behaviour B4   # desktop + autologin
sudo raspi-config nonint do_blanking 1          # disable blanking

echo
echo "Done. Reboot to land in the app:  sudo reboot"
echo "(dialout group membership also needs that reboot/relogin.)"
echo "To run it by hand:  $PYTHON -m grbl_turn"
