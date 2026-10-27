#!/usr/bin/env bash
# Instala o atalho no menu de apps e o início automático no login.
# Uso: ./instalar.sh            (atalho + autostart)
#      ./instalar.sh --sem-autostart
#      ./instalar.sh --remover
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
APPS="$HOME/.local/share/applications/monitor-flutuante.desktop"
AUTO="$HOME/.config/autostart/monitor-flutuante.desktop"

if [[ "${1:-}" == "--remover" ]]; then
  rm -f "$APPS" "$AUTO"
  echo "removido: atalho e autostart (config fica em ~/.config/monitor-flutuante)"
  exit 0
fi

mkdir -p "$(dirname "$APPS")" "$(dirname "$AUTO")"
cat > "$APPS" <<DESK
[Desktop Entry]
Type=Application
Name=Monitor Flutuante
Comment=CPU, RAM e GPU numa linha flutuante
Exec=/usr/bin/python3 $DIR/monitor_flutuante.py
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;
StartupNotify=false
DESK
echo "atalho: $APPS"

if [[ "${1:-}" != "--sem-autostart" ]]; then
  # no login sobe só o ícone (cinza); a linha liga pelo menu "Ligado"
  sed 's|monitor_flutuante.py$|monitor_flutuante.py --desligado|' "$APPS" > "$AUTO"
  echo "X-GNOME-Autostart-Delay=3" >> "$AUTO"
  echo "autostart: $AUTO"
fi
