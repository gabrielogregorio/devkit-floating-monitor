# CLAUDE.md - Floating Monitor

Rules and context for any agent that touches this project. Read it all before editing. This
folder is self-contained: it depends on no external repo or document.

## What it is

A floating line on the desktop with CPU (% and temperature), RAM (used/total and %) and GPU (%,
temperature and VRAM), refreshed every 2 s. Each block turns red over its limit. It has an icon on
the GNOME top bar and its own menu on click.

## Target environment

- Ubuntu 24.04, GNOME, **X11 session** (`$XDG_SESSION_TYPE = x11`).
- System Python 3 (`/usr/bin/python3`) + PyGObject + GTK3. **No pip, no venv to run it** (the
  `.venv` is only for the dev tools: pytest, ruff).
- NVIDIA GPU through the proprietary driver (`libnvidia-ml.so.1`).
- `ubuntu-appindicators@ubuntu.com` extension on (it shows both the AppIndicator and the legacy
  tray icon).
- Not required: `python3-gi-cairo`, `xdotool`, `wmctrl`. `gir1.2-ayatanaappindicator3-0.1` is
  optional (native indicator; without it the legacy `Gtk.StatusIcon` is used).

## Project rules

1. **No new dependency.** Only the standard library + `gi` (Gtk/Gdk/GLib 3.0). If a change needs a
   package, write the `sudo apt install ...` for the user to run; the code must keep working
   without it (fallback).
2. **No cairo.** The `draw` signal with cairo breaks without `python3-gi-cairo`. The look is done
   with `Gtk.Label` + CSS (classes on/off). Do not bring `draw` back.
3. **Pin the gi versions** before importing (`Gtk 3.0` **and** `Gdk 3.0`). Without `Gdk`, PyGObject
   loads Gdk 4.0 and the app dies on import.
4. **Truly light.** No subprocess in the tick (no `nvidia-smi`, `sensors`, `ps`). Read `/proc` and
   `/sys` directly, GPU through NVML via `ctypes`. Redraw only when the text changed. Measured
   reference: ~71 MB RSS, CPU ~0.
5. **One line only.** New data comes as a `│ ...` block on the same line, with an alert rule, in
   `build_line()` (pure, tested).
6. **Do not break what the user set:** `~/.config/devkit-floating-monitor/config.json` stores
   position and modes. A new key goes into `DEFAULTS` (merge), never rewrite the file from scratch.
   Unknown keys are dropped on load. The pre-rename file (`~/.config/monitor-flutuante/`) is read
   once through `LEGACY_KEYS` when the new one does not exist; do not remove that path.
7. No `rm` on user files: trash goes to `./lixo/` or `./trash/` (ignored by git).
8. Code, comments, docs and commits in **English**; menu and titles through `tr()` with the pt-BR
   line in `PT_BR` (`i18n.py`). Commits: one line, imperative.

## On/off

- **No "Quit" item**: the icon always stays on the bar. Turning off = unchecking "On" (line hidden +
  timer stopped). Colored icon when on, gray when off (SVG written to
  `~/.cache/devkit-floating-monitor/icons/`).
- The autostart runs with `--off` (only the icon comes up). Opening from the shortcut = turning on.
  `--off` is removed from argv before `run()`: GApplication refuses an unknown option.

## Architecture (`floating_monitor.py`, single file)

| Part | What it does |
|---|---|
| `DEFAULTS`, `LEGACY_KEYS`, `load_config`, `save_config` | JSON config merged over the defaults, legacy migration; writes to `.tmp` + `os.replace` |
| `Cpu` | % from the `/proc/stat` delta (idle = idle + iowait); temp from hwmon (`k10temp`/`zenpower`/`coretemp`/`cpu_thermal`, label `Tctl`/`Tdie`/`Package id 0`, else `temp1`), path resolved once |
| `read_ram` | `/proc/meminfo`: used = `MemTotal - MemAvailable` |
| `Gpu` | NVML through `ctypes` (`nvmlInit_v2`, `GetHandleByIndex_v2`, `GetUtilizationRates`, `GetTemperature`, `GetMemoryInfo`); AMD/Intel fallback in `/sys/class/drm/card*/device/gpu_busy_percent` (untested on hardware); without a GPU the block is hidden |
| `build_line` | Pango markup of the line, `<span foreground=RED>` on a block over its limit |
| `STAT_PATH`, `MEMINFO_PATH`, `HWMON_DIR`, `DRM_DIR` | the paths the sensors read; the tests point them into `tmp_path` |
| `Monitor(Gtk.Application)` | single instance by `APP_ID`; a 2nd run only turns it on; `hold()` keeps it alive while hidden |
| `_make_window` | undecorated window, RGBA, UTILITY, `stick()`, `set_keep_above`, no focus; `EventBox` → `Box.box` → `⠿` label + text label |
| `CSS` | background by class (`solid`, `hover`, `locked`, `paused`), white text with a 4-side `text-shadow`, monospace font |
| `_click` | button 1 on the `⠿` → `begin_move_drag`; any other click → `Gtk.Menu.popup_at_pointer` |
| `_moved` / `_save_position` | saves the position with an 800 ms debounce |
| `refresh` | `INTERVAL_S` tick; calls `build_line` |
| `_menu` | the same menu serves the window and the top bar (rebuilt on every open) |
| `_make_tray` | `AyatanaAppIndicator3` if the typelib exists; else `Gtk.StatusIcon` (left toggles, right menu) |
| `open_system_monitor` | `gnome-system-monitor`, with fallbacks |

## Traps already paid for (do not repeat)

- `Requiring namespace 'Gdk' version '3.0', but '4.0' is already loaded` → missing
  `gi.require_version("Gdk", "3.0")`.
- `Couldn't find foreign struct converter for 'cairo.Context'` → missing `python3-gi-cairo`; that
  is why there is no cairo here.
- `Namespace AyatanaAppIndicator3 not available` → the `.so` exists, the typelib does not; the
  `StatusIcon` fallback covers it.
- `pgrep -f "python3 floating_monitor.py"` finds the agent's own shell. The autostart runs as
  `/usr/bin/python3 <folder>/floating_monitor.py --off`: use `pgrep -af floating_monitor | grep -v
  pgrep` and kill **by PID**, never with `pkill -f`.
- `set_keep_above` does not work on Wayland (the compositor vetoes it). If the session becomes
  Wayland, run with `GDK_BACKEND=x11` (XWayland). Untested.
- GTK4 does not work: it dropped `set_keep_above` and `StatusIcon`. Stay on GTK3.

## How to test after a change

1. `./run-tests.sh` - ruff, ShellCheck, pytest (fake `/proc`/`/sys`, config in `tmp_path`,
   `install.sh` in a fake `HOME`) and `./verify.sh` (compiles, reads the real sensors once without
   a window, prints the line). It must end in `ALL GREEN`.
2. Restart the running instance (the new one does not start while the old one exists, because of
   the single instance):
   ```bash
   PID=$(pgrep -f floating_monitor.py | head -1); [ -n "$PID" ] && kill "$PID"
   mkdir -p tmp && setsid /usr/bin/python3 "$PWD/floating_monitor.py" \
     > tmp/floating-monitor.log 2>&1 &
   ```
   Run it as its own script file, not pasted into a `bash -c` that contains the file name in the
   `pgrep` pattern.
3. Screenshot of the screen corner with no extra tool:
   ```bash
   python3 -c "import gi; gi.require_version('Gdk','3.0'); from gi.repository import Gdk
   r=Gdk.get_default_root_window(); w=r.get_width()
   Gdk.pixbuf_get_from_window(r,w-700,0,700,80).savev('tmp/monitor-print.png','png',[],[])"
   ```
4. Dragging and the menu cannot be tested by script (no `xdotool`). Ask the user.

## Files

- `floating_monitor.py` - the app. `i18n.py` - menu/title strings.
- `install.sh` - shortcut in `~/.local/share/applications/` + autostart in `~/.config/autostart/`
  (`--no-autostart`, `--remove`).
- `verify.sh` - quick check without GUI. `run-tests.sh` - every layer, same as the CI.
- `tests/` - pytest. `pyproject.toml` / `uv.lock` / `requirements-dev.txt` - dev tools.
- `README.md` - usage and new PC setup.
- Outside: `~/.config/devkit-floating-monitor/config.json` (state), test log in
  `tmp/floating-monitor.log` (ignored by git).

## Ideas not done (only if the user asks)

- Limits editable from the menu (today only in the JSON).
- Click-through (empty input shape on X11) so the text does not block clicks.
- Network (KB/s) and disk as extra blocks.
