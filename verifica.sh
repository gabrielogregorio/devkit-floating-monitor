#!/usr/bin/env bash
# Checagem rápida sem abrir janela: compila e lê os sensores uma vez.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1  # não deixa __pycache__ na pasta
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "[1/3] sessão: ${XDG_SESSION_TYPE:-?} (precisa x11 para 'sempre acima')"
echo "[2/3] compilando"
python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$DIR/monitor_flutuante.py"
echo "[3/3] lendo sensores"
python3 - "$DIR" <<'PY'
import sys, time
sys.path.insert(0, sys.argv[1])
import monitor_flutuante as m

cpu = m.Cpu()
time.sleep(0.5)
uso = cpu.uso()
print(f"  CPU {uso:.0f}%  temp={cpu.temp()}  (sensor: {cpu.temp_path})")
u, t, p = m.ler_ram()
print(f"  RAM {m.gb(u)}/{m.gb(t)}G {p:.0f}%")
g = m.Gpu()
if g.existe:
    print("  GPU", g.ler(), "(NVML)" if g.nv else "(sysfs)")
    g.fechar()
else:
    print("  GPU não encontrada (bloco some)")
print("  indicador:", "AyatanaAppIndicator3" if m.AppIndicator else "Gtk.StatusIcon (legado)")
print("OK")
PY
