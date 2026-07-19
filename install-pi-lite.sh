#!/usr/bin/env bash
# grbl_turn installer for Raspberry Pi OS Lite (Bookworm, 64-bit) —
# no desktop. Boots into the app alone via the cage Wayland kiosk
# compositor: console autologin on tty1 execs cage running the app.
#
# Run as your normal user from the repo checkout on the Pi — tty1
# autologin lands on this same account (raspi-config uses SUDO_USER):
#     ./install-pi-lite.sh
# Needs sudo rights (asks when required). Reboot when it finishes.
#
# Quitting the app (Device page -> Quit app) drops you at a shell on
# tty1; `exit` from that shell re-enters the kiosk.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$HOME/.local/share/grbl_turn/venv"
PYTHON="$VENV/bin/python"
MARKER="# grbl_turn kiosk"

if [ "$(id -u)" -eq 0 ]; then
    echo "Run as the normal user, not root." >&2
    exit 1
fi

if [ "$(uname -m)" != "aarch64" ]; then
    echo "This needs 64-bit Raspberry Pi OS (aarch64) — PySide6 has no" >&2
    echo "32-bit wheels. Reimage with the 64-bit OS and rerun." >&2
    exit 1
fi

echo "==> System packages (cage = single-app Wayland kiosk)"
sudo apt-get update
# libwayland-cursor0/-egl1: client-side wayland libs the PySide6 wheel's
# platform plugin dlopens; cage (a wayland *server*) doesn't pull them in
sudo apt-get install -y python3-venv python3-pip cage \
    libwayland-cursor0 libwayland-egl1

echo "==> Virtualenv at $VENV"
mkdir -p "$(dirname "$VENV")"
python3 -m venv "$VENV"
"$PYTHON" -m pip install --upgrade pip wheel

echo "==> Installing grbl_turn (pulls PySide6 + pyserial)"
# a stale build/ from an earlier install can shadow newer source files
rm -rf "$REPO_DIR/build"
if ! "$PYTHON" -m pip install "$REPO_DIR"; then
    # No usable PySide6 wheel: fall back to the distro's PySide6
    # (Qt 6.4 on Bookworm — sufficient) via system site packages.
    # qt6-wayland provides the wayland platform plugin cage needs.
    echo "==> pip PySide6 failed; falling back to distro python3-pyside6"
    sudo apt-get install -y python3-pyside6.qtwidgets \
        python3-pyside6.qtsvgwidgets qt6-wayland
    rm -rf "$VENV"
    python3 -m venv --system-site-packages "$VENV"
    "$PYTHON" -m pip install --upgrade pip wheel
    "$PYTHON" -m pip install --no-deps "$REPO_DIR"
    "$PYTHON" -m pip install pyserial
fi

echo "==> Smoke test (imports only)"
"$PYTHON" - <<'EOF'
from PySide6.QtSvgWidgets import QSvgWidget
import serial
import grbl_turn.app
print("imports OK")
EOF

echo "==> Serial port access (dialout group)"
sudo usermod -aG dialout "$USER"

echo "==> Kiosk launch from ~/.profile on tty1"
# ~/.profile, not ~/.bash_profile: creating the latter would stop bash
# from reading an existing ~/.profile (which sources .bashrc on Pi OS)
if ! grep -qF "$MARKER" "$HOME/.profile" 2>/dev/null; then
    cat >> "$HOME/.profile" <<EOF

$MARKER
if [ "\$(tty)" = "/dev/tty1" ] && [ -z "\${WAYLAND_DISPLAY:-}" ]; then
    export QT_QPA_PLATFORM=wayland
    # no exec: quitting the app lands in this shell; 'exit' relaunches
    cage -- "$PYTHON" -m grbl_turn --fullscreen >"\$HOME/cage.log" 2>&1
    clear
    echo "grbl_turn quit — 'exit' relaunches it, 'sudo poweroff' shuts down"
fi
EOF
fi

echo "==> Console autologin on tty1, no screen blanking"
sudo raspi-config nonint do_boot_behaviour B2   # console + autologin
sudo raspi-config nonint do_blanking 1          # disable blanking

echo
echo "Done. Reboot to land in the app:  sudo reboot"
echo "(dialout group membership also needs that reboot/relogin.)"
echo "To run it by hand from the console:"
echo "    QT_QPA_PLATFORM=wayland cage -- $PYTHON -m grbl_turn --fullscreen"
