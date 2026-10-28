#!/usr/bin/env bash
# Installs the app menu shortcut and the start at login.
# Usage: ./install.sh                 (shortcut + autostart)
#        ./install.sh --no-autostart
#        ./install.sh --remove
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications/devkit-floating-monitor.desktop"
AUTO="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/devkit-floating-monitor.desktop"

if [[ "${1:-}" == "--remove" ]]; then
  rm -f "$APPS" "$AUTO"
  echo "removed: shortcut and autostart (the config stays in ~/.config/devkit-floating-monitor)"
  exit 0
fi

mkdir -p "$(dirname "$APPS")" "$(dirname "$AUTO")"
cat > "$APPS" <<DESK
[Desktop Entry]
Type=Application
Name=Floating Monitor
Name[pt_BR]=Monitor flutuante
Comment=CPU, RAM and GPU on a floating line
Comment[pt_BR]=CPU, RAM e GPU numa linha flutuante
Exec=/usr/bin/python3 $DIR/floating_monitor.py
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;
StartupNotify=false
DESK
echo "shortcut: $APPS"

if [[ "${1:-}" != "--no-autostart" ]]; then
  # at login only the (gray) icon comes up; the line turns on from the "On" menu item
  sed 's|floating_monitor.py$|floating_monitor.py --off|' "$APPS" > "$AUTO"
  echo "X-GNOME-Autostart-Delay=3" >> "$AUTO"
  echo "autostart: $AUTO"
fi
