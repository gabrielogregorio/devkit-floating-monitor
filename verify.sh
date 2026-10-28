#!/usr/bin/env bash
# Quick check without opening a window: compiles and reads the sensors once.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1  # leaves no __pycache__ in the folder
DIR="$(cd "$(dirname "$0")" && pwd)"
PY3="${PYTHON3:-/usr/bin/python3}"  # the interpreter the shortcuts run (gi comes from apt)
echo "[1/3] session: ${XDG_SESSION_TYPE:-?} (x11 is needed for 'always on top')"
echo "[2/3] compiling"
"$PY3" -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$DIR/floating_monitor.py"
echo "[3/3] reading the sensors"
"$PY3" - "$DIR" <<'PY'
import sys, time
sys.path.insert(0, sys.argv[1])
import floating_monitor as m

cpu = m.Cpu()
time.sleep(0.5)
usage = cpu.usage()
temp = cpu.temp()
print(f"  CPU {usage:.0f}%  temp={temp}  (sensor: {cpu.temp_path})")
ram = m.read_ram()
print(f"  RAM {m.gb(ram[0])}/{m.gb(ram[1])}G {ram[2]:.0f}%")
g = m.Gpu()
gpu = None
if g.present:
    gpu = g.read()
    print("  GPU", gpu, "(NVML)" if g.nv else "(sysfs)")
    g.close()
else:
    print("  no GPU found (the block is hidden)")
print("  line:", m.build_line(m.DEFAULTS, usage, temp, ram, gpu))
print("  indicator:", "AyatanaAppIndicator3" if m.AppIndicator else "Gtk.StatusIcon (legacy)")
print("OK")
PY
