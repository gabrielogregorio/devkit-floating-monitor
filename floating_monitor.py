#!/usr/bin/env python3
"""Floating Monitor: CPU, RAM and GPU on one line, above the screen.

Light on purpose: reads /proc and /sys directly, NVIDIA GPU through NVML (ctypes,
no nvidia-smi), redraws only when the text changes, 2 s tick.
"""
import ctypes
import json
import os
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
except (ValueError, ImportError):
    AppIndicator = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from i18n import tr  # noqa: E402

APP_ID = "io.github.gabrielogregorio.FloatingMonitor"
CONFIG_DIR = os.path.expanduser("~/.config/devkit-floating-monitor")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
# config of the versions before the rename: read once when the new file does not exist yet
LEGACY_CONFIG_PATH = os.path.expanduser("~/.config/monitor-flutuante/config.json")
ICONS_DIR = os.path.expanduser("~/.cache/devkit-floating-monitor/icons")
ICON_NAME = "floating-monitor"
# the autostart passes --off: only the (gray) icon comes up, line hidden and not reading
START_OFF = "--off" in sys.argv

STAT_PATH = "/proc/stat"
MEMINFO_PATH = "/proc/meminfo"
HWMON_DIR = "/sys/class/hwmon"
DRM_DIR = "/sys/class/drm"


def write_icons():
    """22x22 top bar icon: 3 bars (CPU/RAM/GPU). Colored = on, gray = off."""
    os.makedirs(ICONS_DIR, exist_ok=True)
    bars = ((3, 9), (9, 4), (15, 12))  # (x, top)
    for state, colors in (("on", ("#2ecc71", "#3498db", "#e67e22")),
                          ("off", ("#9a9a9a", "#9a9a9a", "#9a9a9a"))):
        body = "".join(f'<rect x="{x}" y="{y}" width="4.5" height="{19 - y}" rx="1" fill="{c}"/>'
                       for (x, y), c in zip(bars, colors, strict=True))
        with open(os.path.join(ICONS_DIR, f"{ICON_NAME}-{state}.svg"), "w") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" '
                    f'viewBox="0 0 22 22">{body}</svg>')


INTERVAL_S = 2
RED = "#ff4d4d"
GRIP = "⠿ "
SHADOW = "rgba(0,0,0,0.9)"
CSS = f"""
#monitor {{ background-color: transparent; }}
.box {{ padding: 3px 8px; border-radius: 6px; background-color: rgba(18,18,23,0); }}
.box.solid {{ background-color: rgba(18,18,23,0.78); }}
.box.hover {{ background-color: rgba(18,18,23,0.40); }}
.box.solid.hover {{ background-color: rgba(18,18,23,0.88); }}
.box label {{
  color: #ffffff; font-family: monospace; font-weight: bold; font-size: 10pt;
  text-shadow: 1px 1px 0 {SHADOW}, -1px -1px 0 {SHADOW}, 1px -1px 0 {SHADOW}, -1px 1px 0 {SHADOW};
}}
.box .grip {{ opacity: 0.9; }}
.box.locked .grip {{ opacity: 0.35; }}
.box.paused .text {{ opacity: 0.55; }}
"""

DEFAULTS = {
    "x": None,
    "y": None,
    "always_on_top": True,
    "transparent": True,
    "locked": False,
    "visible": True,
    "usage_limit": 80,
    "cpu_temp_limit": 85,
    "gpu_temp_limit": 83,
}
# keys of the config written before the rename -> current keys
LEGACY_KEYS = {
    "sempre_acima": "always_on_top",
    "transparente": "transparent",
    "travado": "locked",
    "visivel": "visible",
    "limite_uso": "usage_limit",
    "limite_temp_cpu": "cpu_temp_limit",
    "limite_temp_gpu": "gpu_temp_limit",
}


def _read_json(path):
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def load_config():
    """Defaults merged with the saved file. With no file yet, the pre-rename config is
    carried over (position, modes and limits) so an upgrade keeps what the user set."""
    cfg = dict(DEFAULTS)
    saved = _read_json(CONFIG_PATH)
    if saved is None:
        legacy = _read_json(LEGACY_CONFIG_PATH) or {}
        saved = {LEGACY_KEYS.get(k, k): v for k, v in legacy.items()}
    cfg.update({k: v for k, v in saved.items() if k in DEFAULTS})
    return cfg


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except OSError:
        pass


# ---------------------------------------------------------------- sensors

class Cpu:
    def __init__(self):
        self.prev = self._read()
        self.temp_path = self._find_temp()

    @staticmethod
    def _read():
        with open(STAT_PATH) as f:
            v = [int(x) for x in f.readline().split()[1:]]
        idle = v[3] + v[4]  # idle + iowait
        return sum(v), idle

    def usage(self):
        total, idle = self._read()
        dt, di = total - self.prev[0], idle - self.prev[1]
        self.prev = (total, idle)
        return 0.0 if dt <= 0 else 100.0 * (dt - di) / dt

    @staticmethod
    def _find_temp():
        try:
            hwmons = sorted(os.listdir(HWMON_DIR))
        except OSError:
            return None
        for preferred in ("k10temp", "zenpower", "coretemp", "cpu_thermal"):
            for h in hwmons:
                d = os.path.join(HWMON_DIR, h)
                try:
                    with open(os.path.join(d, "name")) as f:
                        if f.read().strip() != preferred:
                            continue
                except OSError:
                    continue
                # Tctl/Tdie (AMD) or Package id 0 (Intel); else temp1
                for name in sorted(os.listdir(d)):
                    if name.startswith("temp") and name.endswith("_label"):
                        with open(os.path.join(d, name)) as f:
                            if f.read().strip() in ("Tctl", "Tdie", "Package id 0"):
                                return os.path.join(d, name.replace("_label", "_input"))
                t1 = os.path.join(d, "temp1_input")
                if os.path.exists(t1):
                    return t1
        return None

    def temp(self):
        if not self.temp_path:
            return None
        try:
            with open(self.temp_path) as f:
                return int(f.read()) / 1000.0
        except (OSError, ValueError):
            return None


def read_ram():
    info = {}
    with open(MEMINFO_PATH) as f:
        for line in f:
            k, v = line.split(":", 1)
            if k in ("MemTotal", "MemAvailable"):
                info[k] = int(v.split()[0]) * 1024
                if len(info) == 2:
                    break
    total = info["MemTotal"]
    used = total - info["MemAvailable"]
    return used, total, 100.0 * used / total


class _Util(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _Mem(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong),
                ("used", ctypes.c_ulonglong)]


class Gpu:
    """NVIDIA through NVML; AMD/Intel through sysfs (gpu_busy_percent). Absent if neither."""

    def __init__(self, nvml_lib="libnvidia-ml.so.1"):
        self.nv = None
        self.handle = ctypes.c_void_p()
        self.amd = None
        try:
            nv = ctypes.CDLL(nvml_lib)
            if nv.nvmlInit_v2() == 0 and nv.nvmlDeviceGetHandleByIndex_v2(
                    0, ctypes.byref(self.handle)) == 0:
                self.nv = nv
        except OSError:
            pass
        if not self.nv:
            try:
                cards = sorted(os.listdir(DRM_DIR))
            except OSError:
                cards = []
            for card in cards:
                p = os.path.join(DRM_DIR, card, "device", "gpu_busy_percent")
                if os.path.exists(p):
                    self.amd = p
                    break

    @property
    def present(self):
        return bool(self.nv or self.amd)

    def read(self):
        """(usage %, temp °C, VRAM used, VRAM total)"""
        if self.nv:
            u, m, t = _Util(), _Mem(), ctypes.c_uint()
            usage = u.gpu if self.nv.nvmlDeviceGetUtilizationRates(
                self.handle, ctypes.byref(u)) == 0 else None
            temp = t.value if self.nv.nvmlDeviceGetTemperature(
                self.handle, 0, ctypes.byref(t)) == 0 else None
            if self.nv.nvmlDeviceGetMemoryInfo(self.handle, ctypes.byref(m)) == 0:
                return usage, temp, m.used, m.total
            return usage, temp, None, None
        if self.amd:
            try:
                with open(self.amd) as f:
                    return int(f.read()), None, None, None
            except (OSError, ValueError):
                pass
        return None, None, None, None

    def close(self):
        if self.nv:
            self.nv.nvmlShutdown()


# --------------------------------------------------------------------- line

def gb(n):
    return f"{n / 1024 ** 3:.1f}"


def build_line(cfg, cpu, cpu_temp, ram, gpu=None):
    """Pango markup of the line. ram = (used, total, %); gpu = (usage %, temp, VRAM used,
    VRAM total) or None when there is no GPU. A block over its limit turns red."""
    limit = cfg["usage_limit"]

    def block(text, alert):
        return f'<span foreground="{RED}">{text}</span>' if alert else text

    parts = []
    t = f"CPU {cpu:3.0f}%" + (f" {cpu_temp:.0f}°" if cpu_temp is not None else "")
    parts.append(block(t, cpu >= limit or (cpu_temp is not None and cpu_temp >= cfg["cpu_temp_limit"])))

    used, total, pct = ram
    parts.append(block(f"RAM {gb(used)}/{gb(total)}G {pct:3.0f}%", pct >= limit))

    if gpu is not None:
        usage, temp, vram_used, vram_total = gpu
        t = "GPU " + ("--" if usage is None else f"{usage:3d}%")
        alert = (usage or 0) >= limit
        if temp is not None:
            t += f" {temp}°"
            alert = alert or temp >= cfg["gpu_temp_limit"]
        if vram_used is not None and vram_total:
            t += f" {gb(vram_used)}G"
            alert = alert or 100.0 * vram_used / vram_total >= limit
        parts.append(block(t, alert))
    return " │ ".join(parts)


# --------------------------------------------------------------------- app

class Monitor(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.win = None

    # ---- lifecycle
    def do_activate(self):
        if self.win:  # second instance (shortcut/menu): turn on
            self.turn_on(True)
            return
        self.hold()
        self.cfg = load_config()
        self.cpu = Cpu()
        self.gpu = Gpu()
        self.paused = False
        self.hover = False
        self.markup = ""
        self.timer = None
        self._save_id = None

        self._make_window()
        self._make_tray()
        self.cpu.usage()  # drop the 1st sample (no delta)
        self.refresh()
        self._start_timer()
        # the autostart comes up off; opening from the shortcut means turning it on
        self.turn_on(not START_OFF)

    # ---- window
    def _make_window(self):
        w = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        w.set_application(self)
        w.set_name("monitor")
        w.set_title(tr("Floating Monitor"))
        w.set_decorated(False)
        w.set_resizable(False)  # shrinks/grows with the text
        w.set_skip_taskbar_hint(True)
        w.set_skip_pager_hint(True)
        w.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        w.set_accept_focus(False)
        w.stick()  # shows on every workspace
        w.set_keep_above(self.cfg["always_on_top"])
        visual = w.get_screen().get_rgba_visual()
        if visual:
            w.set_visual(visual)
        w.connect("configure-event", self._moved)
        w.connect("delete-event", lambda *_: self.show(False) or True)

        css = Gtk.CssProvider()
        css.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_screen(
            w.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.grip = Gtk.Label(label=GRIP)
        self.grip.get_style_context().add_class("grip")
        self.text = Gtk.Label()
        self.text.get_style_context().add_class("text")
        box = Gtk.Box(spacing=0)
        box.get_style_context().add_class("box")
        box.pack_start(self.grip, False, False, 0)
        box.pack_start(self.text, False, False, 0)

        ev = Gtk.EventBox()
        ev.set_visible_window(False)
        ev.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        ev.connect("button-press-event", self._click)
        ev.connect("enter-notify-event", self._on_hover, True)
        ev.connect("leave-notify-event", self._on_hover, False)
        ev.add(box)
        w.add(ev)
        self.box = box
        self.win = w
        self._apply_style()

    def _apply_style(self):
        st = self.box.get_style_context()
        for css_class, on in (("solid", not self.cfg["transparent"]),
                              ("hover", self.hover),
                              ("locked", self.cfg["locked"]),
                              ("paused", self.paused)):
            (st.add_class if on else st.remove_class)(css_class)

    def _place(self):
        x, y = self.cfg["x"], self.cfg["y"]
        if x is None or y is None:
            geo = Gdk.Display.get_default().get_primary_monitor() \
                or Gdk.Display.get_default().get_monitor(0)
            r = geo.get_workarea()
            width = self.win.get_size()[0]
            x, y = r.x + r.width - width - 16, r.y + 8
        self.win.move(x, y)

    def _on_hover(self, _w, ev, inside):
        if ev.detail == Gdk.NotifyType.INFERIOR:
            return False  # entered/left a child, not the window
        self.hover = inside
        self._apply_style()
        return False

    def _click(self, w, ev):
        if ev.type != Gdk.EventType.BUTTON_PRESS:
            return True
        on_grip = ev.x < self.grip.get_allocation().x + self.grip.get_allocated_width()
        if ev.button == 1 and on_grip and not self.cfg["locked"]:
            self.win.begin_move_drag(ev.button, int(ev.x_root), int(ev.y_root), ev.time)
        else:
            menu = self._menu()
            menu.attach_to_widget(w, None)
            menu.popup_at_pointer(ev)
        return True

    def _moved(self, w, _ev):
        if self._save_id:
            GLib.source_remove(self._save_id)
        self._save_id = GLib.timeout_add(800, self._save_position)
        return False

    def _save_position(self):
        self._save_id = None
        if self.win and self.win.get_visible():
            self.cfg["x"], self.cfg["y"] = self.win.get_position()
        save_config(self.cfg)
        return False

    # ---- reading
    def _start_timer(self):
        if self.timer is None:
            self.timer = GLib.timeout_add_seconds(INTERVAL_S, self.refresh)

    def refresh(self):
        if self.paused:
            self.timer = None
            return False
        gpu = self.gpu.read() if self.gpu.present else None
        self._set_text(build_line(self.cfg, self.cpu.usage(), self.cpu.temp(), read_ram(), gpu))
        return True

    def _set_text(self, markup):
        if markup != self.markup:  # nothing changed: no redraw
            self.markup = markup
            self.text.set_markup(markup)

    # ---- actions
    def show(self, visible):
        self.cfg["visible"] = visible
        if visible:
            self.win.show_all()
            self._place()
            self.win.set_keep_above(self.cfg["always_on_top"])
        else:
            self._save_position()
            self.win.hide()
        save_config(self.cfg)
        self._update_tray()

    def is_on(self):
        return bool(self.win and self.win.get_visible()) and not self.paused

    def turn_on(self, on):
        """On = line visible and reading. Off = hidden and no timer (only the icon stays)."""
        if on:
            if self.paused:
                self.toggle_pause()
            self.show(True)
        else:
            if not self.paused:
                self.toggle_pause()
            self.show(False)

    def toggle(self, key):
        self.cfg[key] = not self.cfg[key]
        if key == "always_on_top":
            self.win.set_keep_above(self.cfg[key])
        save_config(self.cfg)
        self._apply_style()
        self._update_tray()

    def toggle_pause(self, *_):
        self.paused = not self.paused
        if self.paused:
            if self.timer:
                GLib.source_remove(self.timer)
                self.timer = None
        else:
            self.cpu.usage()
            self.refresh()
            self._start_timer()
        self._apply_style()
        self._update_tray()

    def open_system_monitor(self, *_):
        for cmd in (["gnome-system-monitor"], ["plasma-systemmonitor"],
                    ["xfce4-taskmanager"], ["x-terminal-emulator", "-e", "htop"]):
            try:
                subprocess.Popen(cmd, start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                continue

    # ---- menu (the same menu on the window and on the top bar)
    def _menu(self):
        m = Gtk.Menu()

        def item(label, cb):
            i = Gtk.MenuItem(label=label)
            i.connect("activate", cb)
            m.append(i)

        def check(label, active, cb):
            i = Gtk.CheckMenuItem(label=label)
            i.set_active(active)
            i.connect("toggled", cb)
            m.append(i)

        check(tr("On"), self.is_on(), lambda w: self.turn_on(w.get_active()))
        m.append(Gtk.SeparatorMenuItem())
        check(tr("Always on top"), self.cfg["always_on_top"], lambda *_: self.toggle("always_on_top"))
        check(tr("Transparent (white text)"), self.cfg["transparent"], lambda *_: self.toggle("transparent"))
        check(tr("Lock position"), self.cfg["locked"], lambda *_: self.toggle("locked"))
        check(tr("Pause reading"), self.paused, self.toggle_pause)
        item(tr("Back to the screen corner"), self._reset_position)
        m.append(Gtk.SeparatorMenuItem())
        item(tr("Open System Monitor"), self.open_system_monitor)
        # no "Quit" on purpose: the icon always stays on the bar; unchecking "On" turns it off
        m.show_all()
        return m

    def _reset_position(self, *_):
        self.cfg["x"] = self.cfg["y"] = None
        self._place()

    # ---- top bar
    def _make_tray(self):
        self.ind = self.icon = None
        write_icons()
        if AppIndicator:
            self.ind = AppIndicator.Indicator.new(
                ICON_NAME, f"{ICON_NAME}-on", AppIndicator.IndicatorCategory.SYSTEM_SERVICES)
            self.ind.set_icon_theme_path(ICONS_DIR)
            self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
            self.ind.set_title(tr("Floating Monitor"))
            self._update_tray()
        else:
            # fallback: legacy icon, the ubuntu-appindicators extension shows it on the top bar
            icon = Gtk.StatusIcon.new_from_file(os.path.join(ICONS_DIR, f"{ICON_NAME}-on.svg"))
            icon.set_tooltip_text(tr("Floating Monitor"))
            icon.set_title(tr("Floating Monitor"))
            icon.connect("activate", lambda *_: self.turn_on(not self.is_on()))
            icon.connect("popup-menu", self._icon_menu)
            self.icon = icon

    def _icon_menu(self, icon, button, time):
        self._tray_menu = self._menu()
        self._tray_menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, time)

    def _update_tray(self):
        state = "on" if self.is_on() else "off"
        if self.icon:
            self.icon.set_from_file(os.path.join(ICONS_DIR, f"{ICON_NAME}-{state}.svg"))
        if self.ind:
            label = tr("Floating Monitor: on") if state == "on" else tr("Floating Monitor: off")
            self.ind.set_icon_full(f"{ICON_NAME}-{state}", label)
            self._tray_menu = self._menu()
            self.ind.set_menu(self._tray_menu)


def main():
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)  # Gtk.StatusIcon
    GLib.set_prgname(ICON_NAME)
    Monitor().run([a for a in sys.argv if a != "--off"])  # GApplication refuses unknown options


if __name__ == "__main__":
    main()
